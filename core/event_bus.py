"""
Event Bus Module - Real-time Event Distribution

EXPLANATION FOR VIVA:
=====================
The Event Bus is specifically designed for real-time, UI-facing events.
While the Message Broker handles agent-to-agent communication, the Event Bus
handles broadcasting events to connected clients (via WebSockets).

This is the Observer Pattern at the system level:
- Events are published when state changes occur
- WebSocket connections subscribe to events
- When an event occurs, all subscribers are notified

Real-world analogy: Think of it like a radio station
- The station (Event Bus) broadcasts
- Radios (WebSocket clients) tune in to receive
- Anyone can tune in without the station knowing who's listening

This enables features like:
- Real-time collaborative editing (see others' changes instantly)
- Live presence indicators (see who's online)
- Instant notifications
"""

import asyncio
from typing import Dict, List, Callable, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
import json

logger = logging.getLogger(__name__)


class EventType(Enum):
    """
    Types of real-time events in the system.
    
    EXPLANATION FOR VIVA:
    ====================
    These are user-facing events, distinct from internal agent messages.
    They represent state changes that the UI needs to know about.
    """
    
    # User Events
    USER_JOINED = "user_joined"
    USER_LEFT = "user_left"
    USER_UPDATED = "user_updated"
    
    # Document Events
    DOCUMENT_CREATED = "document_created"
    DOCUMENT_UPDATED = "document_updated"
    DOCUMENT_DELETED = "document_deleted"
    CURSOR_MOVED = "cursor_moved"
    SELECTION_CHANGED = "selection_changed"
    
    # Collaboration Events
    EDIT_STARTED = "edit_started"
    EDIT_COMPLETED = "edit_completed"
    CONFLICT_DETECTED = "conflict_detected"
    SYNC_REQUIRED = "sync_required"
    
    # Version Events
    VERSION_CREATED = "version_created"
    VERSION_REVERTED = "version_reverted"
    
    # System Events
    SYSTEM_MESSAGE = "system_message"
    ERROR = "error"


@dataclass
class Event:
    """
    Represents an event to be broadcast to subscribers.
    
    EXPLANATION FOR VIVA:
    ====================
    Events are immutable records of something that happened.
    They contain:
    - What happened (event_type)
    - Details about it (data)
    - Who caused it (user_id)
    - What it relates to (document_id)
    - When it happened (timestamp)
    
    This is the Event Sourcing pattern - we record events as they happen,
    which enables features like audit logs and event replay.
    """
    
    event_type: EventType
    data: Dict[str, Any]
    user_id: Optional[str] = None
    document_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize event for transmission over WebSocket."""
        return {
            "type": self.event_type.value,
            "data": self.data,
            "user_id": self.user_id,
            "document_id": self.document_id,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_json(self) -> str:
        """Convert to JSON string for WebSocket transmission."""
        return json.dumps(self.to_dict())


class EventBus:
    """
    Manages real-time event subscriptions and broadcasting.
    
    EXPLANATION FOR VIVA:
    ====================
    This is a Publish-Subscribe (Pub/Sub) system with filtering.
    
    Key features:
    1. Topic-based subscriptions: Subscribe to specific event types
    2. Document-scoped subscriptions: Only get events for documents you're viewing
    3. Async callbacks: Non-blocking event delivery
    
    Architecture decisions:
    - In-memory for simplicity (could be Redis Pub/Sub for scaling)
    - Callbacks are async to prevent slow subscribers from blocking
    - Weak references could be used to prevent memory leaks (not implemented here)
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize the event bus."""
        if self._initialized:
            return
            
        # Subscribers by event type
        self._subscribers: Dict[EventType, List[Callable]] = {}
        
        # Document-specific subscribers (for collaborative editing)
        self._document_subscribers: Dict[str, Set[Callable]] = {}
        
        # All-events subscribers (for logging/monitoring)
        self._global_subscribers: List[Callable] = []
        
        # Event history (for debugging and replay)
        self._event_history: List[Event] = []
        self._max_history = 1000
        
        self._initialized = True
        logger.info("EventBus initialized")
    
    def subscribe(
        self, 
        event_type: EventType, 
        callback: Callable[[Event], Any]
    ) -> Callable:
        """
        Subscribe to a specific event type.
        
        EXPLANATION FOR VIVA:
        ====================
        Callbacks are functions that will be called when an event occurs.
        Returns an unsubscribe function for cleanup.
        
        Usage:
            unsubscribe = event_bus.subscribe(EventType.DOCUMENT_UPDATED, my_handler)
            # Later, to stop receiving events:
            unsubscribe()
        
        This pattern is common in JavaScript (addEventListener returns removeEventListener)
        and React (useEffect cleanup functions).
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        
        self._subscribers[event_type].append(callback)
        logger.debug(f"Subscribed to {event_type.value}: {callback}")
        
        # Return unsubscribe function
        def unsubscribe():
            if callback in self._subscribers.get(event_type, []):
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from {event_type.value}: {callback}")
        
        return unsubscribe
    
    def subscribe_to_document(
        self, 
        document_id: str, 
        callback: Callable[[Event], Any]
    ) -> Callable:
        """
        Subscribe to all events for a specific document.
        
        EXPLANATION FOR VIVA:
        ====================
        This is crucial for collaborative editing. When a user opens a document,
        they subscribe to that document's events. They'll receive:
        - Other users' edits
        - Cursor positions
        - Version changes
        
        This prevents users from receiving events for documents they're not viewing,
        which would be wasteful and confusing.
        """
        if document_id not in self._document_subscribers:
            self._document_subscribers[document_id] = set()
        
        self._document_subscribers[document_id].add(callback)
        logger.debug(f"Subscribed to document {document_id}")
        
        def unsubscribe():
            if document_id in self._document_subscribers:
                self._document_subscribers[document_id].discard(callback)
                if not self._document_subscribers[document_id]:
                    del self._document_subscribers[document_id]
        
        return unsubscribe
    
    def subscribe_all(self, callback: Callable[[Event], Any]) -> Callable:
        """Subscribe to all events (useful for logging/monitoring)."""
        self._global_subscribers.append(callback)
        
        def unsubscribe():
            if callback in self._global_subscribers:
                self._global_subscribers.remove(callback)
        
        return unsubscribe
    
    async def publish(self, event: Event):
        """
        Publish an event to all relevant subscribers.
        
        EXPLANATION FOR VIVA:
        ====================
        Publishing broadcasts the event to:
        1. Type-specific subscribers
        2. Document-specific subscribers (if document_id is set)
        3. Global subscribers
        
        Callbacks are called asynchronously to prevent blocking.
        Errors in callbacks don't affect other subscribers.
        """
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]
        
        logger.debug(f"Publishing event: {event.event_type.value}")
        
        callbacks_to_call = []
        
        # Type-specific subscribers
        if event.event_type in self._subscribers:
            callbacks_to_call.extend(self._subscribers[event.event_type])
        
        # Document-specific subscribers
        if event.document_id and event.document_id in self._document_subscribers:
            callbacks_to_call.extend(self._document_subscribers[event.document_id])
        
        # Global subscribers
        callbacks_to_call.extend(self._global_subscribers)
        
        # Call all callbacks concurrently
        for callback in callbacks_to_call:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
    
    def get_history(
        self, 
        event_type: Optional[EventType] = None,
        document_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Event]:
        """
        Get recent event history with optional filtering.
        
        EXPLANATION FOR VIVA:
        ====================
        Event history is useful for:
        1. Debugging: See what events occurred
        2. Late joiners: Catch up on recent events
        3. Audit: Track who did what
        """
        events = self._event_history
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        if document_id:
            events = [e for e in events if e.document_id == document_id]
        
        return events[-limit:]
    
    def get_document_subscribers_count(self, document_id: str) -> int:
        """Get number of active subscribers for a document."""
        return len(self._document_subscribers.get(document_id, set()))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            "total_subscribers": sum(len(s) for s in self._subscribers.values()),
            "document_rooms": len(self._document_subscribers),
            "global_subscribers": len(self._global_subscribers),
            "events_in_history": len(self._event_history),
            "subscribers_by_type": {
                et.value: len(subs) 
                for et, subs in self._subscribers.items()
            }
        }
