"""
WebSocket Manager - Real-time Communication Handler

EXPLANATION FOR VIVA:
=====================
WebSockets enable bidirectional, real-time communication between client and server.

HTTP vs WebSocket:
- HTTP: Request-Response, client initiates, connection closes after response
- WebSocket: Persistent connection, both sides can send messages anytime

Why WebSockets for Collaborative Editing?
1. Real-time updates: See others' changes instantly
2. Efficiency: No polling needed (saves bandwidth)
3. Low latency: Direct push, no request overhead
4. Bidirectional: Server can push, client can push

WebSocket Lifecycle:
1. Client connects (HTTP upgrade to WebSocket)
2. Connection stays open
3. Either side can send messages
4. Connection closes when client disconnects or server shuts down

Architecture:
- WebSocketManager handles all connections
- Connections grouped by document (rooms)
- Events from EventBus are broadcast to relevant clients
"""

import asyncio
import json
from typing import Dict, Set, Optional, Any
from datetime import datetime
import logging

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from core.event_bus import EventBus, Event, EventType
from core.message_broker import MessageBroker
from core.agent_base import AgentMessage, MessageType

logger = logging.getLogger(__name__)

# Module-level singleton instance (more robust than class-level)
_ws_manager_instance = None


class WebSocketManager:
    """
    Manages WebSocket connections for real-time collaboration.
    
    EXPLANATION FOR VIVA:
    ====================
    This class implements the Pub/Sub pattern for WebSockets:
    
    1. Connection Management: Track all connected clients
    2. Room/Document Grouping: Group connections by document
    3. Broadcasting: Send updates to all relevant clients
    4. Event Integration: Subscribe to EventBus for agent events
    
    Design Patterns:
    - Singleton: One manager for all connections
    - Observer: Clients observe document changes
    - Mediator: Manager mediates between clients and agents
    """
    
    def __new__(cls):
        """Singleton pattern using module-level instance."""
        global _ws_manager_instance
        if _ws_manager_instance is None:
            _ws_manager_instance = super().__new__(cls)
            _ws_manager_instance._initialized = False
        return _ws_manager_instance
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        if self._initialized:
            return
        
        # All active connections: user_id -> WebSocket
        self._connections: Dict[str, WebSocket] = {}
        
        # Document rooms: document_id -> set of user_ids
        self._document_rooms: Dict[str, Set[str]] = {}
        
        # User info: user_id -> {username, connected_at, etc.}
        self._user_info: Dict[str, Dict[str, Any]] = {}
        
        # Event bus for agent events
        self._event_bus = EventBus()
        
        # Subscribe to all events for broadcasting
        self._event_bus.subscribe_all(self._handle_event)
        
        self._initialized = True
        logger.info("WebSocketManager initialized")
    
    async def connect(
        self, 
        websocket: WebSocket, 
        user_id: str, 
        username: str
    ):
        """
        Accept a new WebSocket connection.
        
        EXPLANATION FOR VIVA:
        ====================
        Connection process:
        1. Accept the WebSocket upgrade
        2. Store connection reference
        3. Store user info
        4. Send welcome message
        
        The websocket object represents the persistent connection.
        We keep it in memory to send messages later.
        """
        await websocket.accept()
        
        # Store connection
        self._connections[user_id] = websocket
        self._user_info[user_id] = {
            "username": username,
            "connected_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"WebSocket connected: {username} ({user_id})")
        
        # Send welcome message
        await self._send_to_user(user_id, {
            "type": "connected",
            "message": "Connected to collaborative editing server",
            "user_id": user_id
        })
    
    async def disconnect(self, user_id: str):
        """
        Handle client disconnection.
        
        EXPLANATION FOR VIVA:
        ====================
        Cleanup process:
        1. Remove from all document rooms
        2. Remove connection reference
        3. Notify other users in shared rooms
        
        This is important for:
        - Memory cleanup
        - Accurate presence information
        - Resource management
        """
        # Remove from all document rooms
        for doc_id in list(self._document_rooms.keys()):
            if user_id in self._document_rooms[doc_id]:
                self._document_rooms[doc_id].discard(user_id)
                
                # Notify others in the room
                await self._broadcast_to_document(doc_id, {
                    "type": "user_left",
                    "user_id": user_id,
                    "document_id": doc_id,
                    "active_users": list(self._document_rooms[doc_id])
                }, exclude_user=user_id)
                
                # Clean up empty rooms
                if not self._document_rooms[doc_id]:
                    del self._document_rooms[doc_id]
        
        # Remove connection
        username = self._user_info.get(user_id, {}).get("username", "Unknown")
        self._connections.pop(user_id, None)
        self._user_info.pop(user_id, None)
        
        logger.info(f"WebSocket disconnected: {username} ({user_id})")
    
    async def join_document(self, user_id: str, document_id: str):
        """
        Add user to a document room.
        
        EXPLANATION FOR VIVA:
        ====================
        Room = group of users viewing the same document
        
        When user joins:
        1. Add to room set
        2. Notify existing users
        3. Subscribe to document events in EventBus
        
        This enables targeted broadcasting - only users viewing
        a document receive updates for that document.
        """
        if document_id not in self._document_rooms:
            self._document_rooms[document_id] = set()
        
        self._document_rooms[document_id].add(user_id)
        
        username = self._user_info.get(user_id, {}).get("username", "Unknown")
        
        logger.info(f"User {username} joined document {document_id}")
        
        # Get all active users with their info
        active_users_info = self._get_active_users_info(document_id)
        
        # Notify others
        await self._broadcast_to_document(document_id, {
            "type": "user_joined",
            "user_id": user_id,
            "username": username,
            "document_id": document_id,
            "active_users": active_users_info
        }, exclude_user=user_id)
        
        # Send current users list to the joining user
        await self._send_to_user(user_id, {
            "type": "room_info",
            "document_id": document_id,
            "active_users": active_users_info
        })
    
    def _get_active_users_info(self, document_id: str) -> list:
        """Get list of active users with their info for a document."""
        if document_id not in self._document_rooms:
            return []
        
        users = []
        for uid in self._document_rooms[document_id]:
            info = self._user_info.get(uid, {})
            users.append({
                "user_id": uid,
                "username": info.get("username", "Unknown"),
                "color": self._get_user_color(uid)
            })
        return users
    
    async def leave_document(self, user_id: str, document_id: str):
        """Remove user from a document room."""
        if document_id in self._document_rooms:
            self._document_rooms[document_id].discard(user_id)
            
            username = self._user_info.get(user_id, {}).get("username", "Unknown")
            
            logger.info(f"User {username} left document {document_id}")
            
            # Get remaining active users with info
            active_users_info = self._get_active_users_info(document_id)
            
            # Notify others
            await self._broadcast_to_document(document_id, {
                "type": "user_left",
                "user_id": user_id,
                "username": username,
                "document_id": document_id,
                "active_users": active_users_info
            })
            
            # Clean up empty rooms
            if not self._document_rooms[document_id]:
                del self._document_rooms[document_id]
    
    async def handle_message(self, user_id: str, data: dict):
        """
        Handle incoming WebSocket message from client.
        
        EXPLANATION FOR VIVA:
        ====================
        Message types from client:
        - join_document: Enter a document room
        - leave_document: Exit a document room
        - cursor_update: User moved cursor
        - text_change: User made an edit
        - ping: Keepalive
        
        This processes client messages and routes to appropriate handlers
        or forwards to agents via MessageBroker.
        """
        message_type = data.get("type")
        
        if message_type == "join_document":
            document_id = data.get("document_id")
            if document_id:
                await self.join_document(user_id, document_id)
        
        elif message_type == "leave_document":
            document_id = data.get("document_id")
            if document_id:
                await self.leave_document(user_id, document_id)
        
        elif message_type == "cursor_update":
            document_id = data.get("document_id")
            position = data.get("position", 0)
            selection_start = data.get("selection_start")
            selection_end = data.get("selection_end")
            if document_id:
                await self._broadcast_cursor_update(
                    user_id, document_id, position,
                    selection_start, selection_end
                )
        
        elif message_type == "text_change":
            document_id = data.get("document_id")
            change = data.get("change", {})
            if document_id:
                await self._broadcast_text_change(user_id, document_id, change)
        
        elif message_type == "ping":
            await self._send_to_user(user_id, {"type": "pong"})
        
        else:
            logger.warning(f"Unknown message type: {message_type}")
    
    def _get_user_color(self, user_id: str) -> str:
        """Generate a consistent color for a user based on their ID."""
        # Use hash of user_id to generate consistent HSL color
        hash_val = sum(ord(c) for c in user_id)
        hue = hash_val % 360
        return f"hsl({hue}, 70%, 50%)"
    
    async def _broadcast_cursor_update(
        self, 
        user_id: str, 
        document_id: str, 
        position: int,
        selection_start: int = None,
        selection_end: int = None
    ):
        """
        Broadcast cursor position to all users in document room.
        
        EXPLANATION FOR VIVA:
        ====================
        Shows real-time cursor positions like Google Docs.
        Each user sees colored cursors of other editors.
        
        Cursor data includes:
        - position: cursor position
        - selection_start/end: for text selection highlighting
        - color: consistent color per user
        
        We exclude the sender - they already know their cursor position.
        """
        username = self._user_info.get(user_id, {}).get("username", "Unknown")
        color = self._get_user_color(user_id)
        
        await self._broadcast_to_document(document_id, {
            "type": "cursor_update",
            "user_id": user_id,
            "username": username,
            "document_id": document_id,
            "position": position,
            "selection_start": selection_start,
            "selection_end": selection_end,
            "color": color
        }, exclude_user=user_id)
    
    async def _broadcast_text_change(
        self, 
        user_id: str, 
        document_id: str, 
        change: dict
    ):
        """
        Broadcast text change to all users in document room.
        
        EXPLANATION FOR VIVA:
        ====================
        This is the core of real-time collaboration.
        When user A types, the change is immediately sent to users B, C, etc.
        
        Change structure:
        - type: insert, delete, replace
        - position: where the change happened
        - content: the new text (for insert/replace)
        - length: characters affected (for delete/replace)
        
        In a production system, you'd use Operational Transformation (OT)
        or CRDT to handle concurrent edits and conflicts.
        """
        username = self._user_info.get(user_id, {}).get("username", "Unknown")
        
        
        await self._broadcast_to_document(document_id, {
            "type": "text_change",
            "user_id": user_id,
            "username": username,
            "document_id": document_id,
            "change": change,
            "timestamp": datetime.utcnow().isoformat()
        }, exclude_user=user_id)
    
    async def _handle_event(self, event: Event):
        """
        Handle events from the EventBus (from agents).
        
        EXPLANATION FOR VIVA:
        ====================
        Agents publish events when things happen:
        - Document updated
        - Version created
        - User joined
        
        We receive these events and broadcast to relevant WebSocket clients.
        This connects the agent system to the real-time UI.
        """
        try:
            if event.document_id:
                # Broadcast to document room
                await self._broadcast_to_document(
                    event.document_id,
                    event.to_dict(),
                    exclude_user=event.user_id  # Don't echo back to originator
                )
            elif event.user_id:
                # Send to specific user
                await self._send_to_user(event.user_id, event.to_dict())
                
        except Exception as e:
            logger.error(f"Error handling event: {e}")
    
    async def _send_to_user(self, user_id: str, data: dict):
        """Send a message to a specific user."""
        websocket = self._connections.get(user_id)
        if websocket and websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")
                await self.disconnect(user_id)
    
    async def _broadcast_to_document(
        self, 
        document_id: str, 
        data: dict,
        exclude_user: Optional[str] = None
    ):
        """
        Broadcast a message to all users in a document room.
        
        EXPLANATION FOR VIVA:
        ====================
        Sends the same message to all users viewing a document.
        
        exclude_user: Don't send to this user (usually the sender)
        This prevents echo - user doesn't need to receive their own changes.
        """
        if document_id not in self._document_rooms:
            return
        
        tasks = []
        for user_id in self._document_rooms[document_id]:
            if user_id != exclude_user:
                tasks.append(self._send_to_user(user_id, data))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def broadcast_to_all(self, data: dict, exclude_user: Optional[str] = None):
        """Broadcast a message to all connected users."""
        tasks = []
        for user_id in self._connections:
            if user_id != exclude_user:
                tasks.append(self._send_to_user(user_id, data))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_online_users(self) -> list:
        """Get list of all online users."""
        return [
            {
                "user_id": user_id,
                **info
            }
            for user_id, info in self._user_info.items()
        ]
    
    def get_document_users(self, document_id: str) -> list:
        """Get list of users in a document room."""
        if document_id not in self._document_rooms:
            return []
        
        return [
            {
                "user_id": user_id,
                **self._user_info.get(user_id, {})
            }
            for user_id in self._document_rooms[document_id]
        ]
    
    def get_stats(self) -> dict:
        """Get WebSocket manager statistics."""
        return {
            "total_connections": len(self._connections),
            "document_rooms": len(self._document_rooms),
            "users_per_room": {
                doc_id: len(users) 
                for doc_id, users in self._document_rooms.items()
            }
        }


# WebSocket route handler
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    username: str
):
    """
    WebSocket endpoint handler.
    
    EXPLANATION FOR VIVA:
    ====================
    This function handles the entire WebSocket lifecycle:
    
    1. Connect: Accept connection, register user
    2. Loop: Receive and process messages
    3. Disconnect: Clean up on close or error
    
    The try-except-finally ensures cleanup happens even if client
    disconnects abruptly (closes browser, network failure, etc.).
    """
    manager = WebSocketManager()
    
    try:
        await manager.connect(websocket, user_id, username)
        
        while True:
            data = await websocket.receive_json()
            await manager.handle_message(user_id, data)
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for {user_id}: {e}")
    finally:
        await manager.disconnect(user_id)
