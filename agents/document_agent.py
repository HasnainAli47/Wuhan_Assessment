"""
Document Editing Agent - Handles Document Operations and Collaboration

================================================================================
DEVELOPED BY: Hasnain Ali | Wuhan University | Supervisor: Prof. Liang Peng
================================================================================

EXPLANATION FOR VIVA:
=====================
This agent manages all document-related operations, including the core
collaborative editing functionality.

Key Responsibilities:
1. Create Document - New document creation
2. Edit Document - Collaborative editing with conflict detection
3. Track Changes - Real-time change tracking for collaboration

Collaborative Editing Concepts:
- Operational Transformation (OT): Algorithm for resolving concurrent edits
- Last-Write-Wins: Simpler approach where latest edit wins
- CRDT (Conflict-free Replicated Data Types): Alternative to OT

We implement a simplified version suitable for demonstration:
- Track active editors per document
- Broadcast changes to all viewers
- Basic conflict detection (warn, don't auto-resolve)

Real systems like Google Docs use sophisticated OT algorithms.
"""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
import logging
import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.agent_base import Agent, AgentMessage, MessageType
from core.event_bus import EventBus, Event, EventType
from models.database import get_session
from models.document import Document
from models.user import User
from models.version import DocumentChange

logger = logging.getLogger(__name__)


class DocumentEditingAgent(Agent):
    """
    Agent responsible for document management and collaborative editing.
    
    EXPLANATION FOR VIVA:
    ====================
    This agent demonstrates:
    
    1. CRUD Operations: Create, Read, Update, Delete documents
    2. Collaboration: Multiple users editing simultaneously
    3. Real-time Updates: Broadcasting changes via EventBus
    4. Permission Management: Who can view/edit what
    
    Operations Implemented (as required):
    1. Create Document (create_document)
    2. Edit Document Collaboratively (edit_document)
    3. Track Changes in Real-time (track_change)
    
    Plus additional operations:
    4. Read Document (get_document)
    5. List Documents (list_documents)
    6. Delete Document (delete_document)
    7. Join/Leave Editing Session (for presence tracking)
    """
    
    def __init__(self):
        super().__init__(
            agent_id="document_editing_agent",
            name="Document Editing Agent"
        )
        self.event_bus = EventBus()
        
        # Track active editing sessions
        # Structure: {document_id: {user_id: {"cursor_position": int, "last_activity": datetime}}}
        self._active_editors: Dict[str, Dict[str, Dict]] = {}
        
        # Track document locks for conflict prevention
        self._document_locks: Dict[str, str] = {}  # document_id -> user_id
        
        # Register message handlers
        self.register_handler(MessageType.DOC_CREATE, self._handle_create)
        self.register_handler(MessageType.DOC_READ, self._handle_read)
        self.register_handler(MessageType.DOC_UPDATE, self._handle_update)
        self.register_handler(MessageType.DOC_DELETE, self._handle_delete)
        self.register_handler(MessageType.DOC_LIST, self._handle_list)
        self.register_handler(MessageType.DOC_COLLABORATE, self._handle_collaborate)
        self.register_handler(MessageType.DOC_TRACK_CHANGE, self._handle_track_change)
    
    def get_capabilities(self) -> List[MessageType]:
        """Return message types this agent handles."""
        return [
            MessageType.DOC_CREATE,
            MessageType.DOC_READ,
            MessageType.DOC_UPDATE,
            MessageType.DOC_DELETE,
            MessageType.DOC_LIST,
            MessageType.DOC_COLLABORATE,
            MessageType.DOC_TRACK_CHANGE
        ]
    
    async def on_start(self):
        """Initialize the agent."""
        logger.info(f"{self.name} started and ready")
    
    async def on_stop(self):
        """Cleanup on shutdown."""
        logger.info(f"{self.name} stopping, clearing editing sessions")
        self._active_editors.clear()
        self._document_locks.clear()
    
    # ==================== DOCUMENT CRUD OPERATIONS ====================
    
    async def _handle_create(self, message: AgentMessage) -> AgentMessage:
        """
        Create a new document.
        
        EXPLANATION FOR VIVA:
        ====================
        Document creation:
        1. Validate input (title required, user must be authenticated)
        2. Create document with initial content
        3. Automatically create first version (Version 1)
        4. Publish event for real-time updates
        
        The owner is the user who creates it.
        They automatically have full permissions.
        """
        payload = message.payload
        
        user_id = payload.get("user_id")
        title = payload.get("title", "").strip() or "Untitled Document"
        content = payload.get("content", "")
        is_public = payload.get("is_public", False)
        
        if not user_id:
            return message.create_response(
                {"success": False, "error": "User ID required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                # Verify user exists
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    logger.error(f"User not found for ID: {user_id}")
                    return message.create_response(
                        {"success": False, "error": f"User not found. Please log out and log in again."},
                        success=False
                    )
                
                # Create document
                document = Document(
                    title=title,
                    content=content,
                    owner_id=user_id,
                    is_public=is_public,
                    collaborators=[],
                    active_editors=[]
                )
                document.update_counts()  # Calculate word/char counts
                
                session.add(document)
                await session.commit()
                await session.refresh(document)
                
                logger.info(f"Document created: {document.title} by {user.username}")
                
                # Publish event
                await self.event_bus.publish(Event(
                    event_type=EventType.DOCUMENT_CREATED,
                    data={"document": document.to_dict()},
                    user_id=user_id,
                    document_id=document.id
                ))
                
                # Send message to version control agent to create initial version
                version_message = AgentMessage(
                    type=MessageType.VERSION_CREATE,
                    sender=self.agent_id,
                    recipient="version_control_agent",
                    payload={
                        "document_id": document.id,
                        "user_id": user_id,
                        "title": document.title,
                        "content": document.content,
                        "change_summary": "Initial document creation"
                    }
                )
                await self.send_message(version_message)
                
                return message.create_response({
                    "success": True,
                    "document": document.to_dict(),
                    "message": "Document created successfully"
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Create document error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_read(self, message: AgentMessage) -> AgentMessage:
        """
        Read/Get a document.
        
        EXPLANATION FOR VIVA:
        ====================
        Read operation with permission check:
        1. Check if document exists
        2. Check if user has view permission
        3. Return document data
        
        This demonstrates authorization - the user must have permission
        to view the document (owner, collaborator, or public document).
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        user_id = payload.get("user_id")
        
        if not document_id:
            return message.create_response(
                {"success": False, "error": "Document ID required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(Document).where(
                        and_(
                            Document.id == document_id,
                            Document.is_deleted == False
                        )
                    )
                )
                document = result.scalar_one_or_none()
                
                if not document:
                    return message.create_response(
                        {"success": False, "error": "Document not found"},
                        success=False
                    )
                
                # Permission check
                if not document.can_view(user_id):
                    return message.create_response(
                        {"success": False, "error": "Access denied"},
                        success=False
                    )
                
                # Get active editors for this document
                active = self._active_editors.get(document_id, {})
                
                return message.create_response({
                    "success": True,
                    "document": document.to_dict(),
                    "active_editors": list(active.keys()),
                    "can_edit": document.can_edit(user_id) if user_id else False
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Read document error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_update(self, message: AgentMessage) -> AgentMessage:
        """
        Update/Edit a document.
        
        EXPLANATION FOR VIVA:
        ====================
        This is the core of collaborative editing:
        
        1. Permission Check: User must be able to edit
        2. Conflict Detection: Check if someone else is editing
        3. Apply Changes: Update the content
        4. Track Changes: Store what changed for version control
        5. Broadcast: Notify all viewers of the change
        
        Conflict Handling Strategy (simplified):
        - We use optimistic locking
        - If content changed since user loaded it, warn about conflict
        - Real systems use OT or CRDT for seamless merging
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        user_id = payload.get("user_id")
        new_content = payload.get("content")
        new_title = payload.get("title")
        expected_version = payload.get("expected_version")  # For conflict detection
        create_version = payload.get("create_version", False)  # Save as new version?
        
        if not document_id or not user_id:
            return message.create_response(
                {"success": False, "error": "Document ID and User ID required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(Document).where(
                        and_(
                            Document.id == document_id,
                            Document.is_deleted == False
                        )
                    )
                )
                document = result.scalar_one_or_none()
                
                if not document:
                    return message.create_response(
                        {"success": False, "error": "Document not found"},
                        success=False
                    )
                
                # Permission check
                if not document.can_edit(user_id):
                    return message.create_response(
                        {"success": False, "error": "Edit permission denied"},
                        success=False
                    )
                
                # Conflict detection using optimistic locking
                # If client sends expected_version, check it matches current version
                current_version = document.edit_version or 1
                if expected_version is not None and expected_version != current_version:
                    # Conflict detected! Someone else edited since user loaded
                    logger.warning(f"Edit conflict detected for document {document_id}: "
                                   f"expected v{expected_version}, current v{current_version}")
                    return message.create_response({
                        "success": False,
                        "error": "Conflict detected: Document was modified by another user",
                        "conflict": True,
                        "expected_version": expected_version,
                        "current_version": current_version,
                        "server_content": document.content,
                        "server_title": document.title,
                        "last_edited_by": document.last_edited_by
                    }, success=False)
                
                # Track what changed (for change history)
                old_content = document.content
                changes_made = []
                
                # Update content if provided
                if new_content is not None and new_content != document.content:
                    # Calculate changes for tracking
                    changes = DocumentChange.calculate_diff(old_content, new_content)
                    
                    document.content = new_content
                    document.update_counts()
                    document.last_edited_by = user_id
                    changes_made.append("content")
                    
                    # Store individual changes for contribution tracking
                    for change in changes:
                        doc_change = DocumentChange(
                            document_id=document_id,
                            user_id=user_id,
                            change_type=change['type'],
                            position=change['position'],
                            length=change['length'],
                            old_content=change.get('old_content'),
                            new_content=change.get('new_content')
                        )
                        session.add(doc_change)
                
                # Update title if provided
                if new_title is not None and new_title != document.title:
                    document.title = new_title
                    changes_made.append("title")
                
                # Increment edit version for optimistic locking
                if changes_made:
                    document.edit_version = current_version + 1
                
                document.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(document)
                
                logger.info(f"Document updated: {document.title} by user {user_id}")
                
                # Publish real-time update event
                await self.event_bus.publish(Event(
                    event_type=EventType.DOCUMENT_UPDATED,
                    data={
                        "document_id": document_id,
                        "changes": changes_made,
                        "updated_by": user_id,
                        "content": document.content if "content" in changes_made else None,
                        "title": document.title if "title" in changes_made else None
                    },
                    user_id=user_id,
                    document_id=document_id
                ))
                
                # Create version if requested
                if create_version:
                    version_message = AgentMessage(
                        type=MessageType.VERSION_CREATE,
                        sender=self.agent_id,
                        recipient="version_control_agent",
                        payload={
                            "document_id": document_id,
                            "user_id": user_id,
                            "title": document.title,
                            "content": document.content,
                            "change_summary": payload.get("change_summary", "Manual save")
                        }
                    )
                    await self.send_message(version_message)
                
                return message.create_response({
                    "success": True,
                    "document": document.to_dict(),
                    "changes_made": changes_made,
                    "message": "Document updated successfully"
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Update document error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_delete(self, message: AgentMessage) -> AgentMessage:
        """
        Delete a document (soft delete).
        
        EXPLANATION FOR VIVA:
        ====================
        Only the owner can delete a document.
        We use soft delete (is_deleted = True) to:
        1. Allow recovery
        2. Maintain version history
        3. Keep contribution records intact
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        user_id = payload.get("user_id")
        
        if not document_id or not user_id:
            return message.create_response(
                {"success": False, "error": "Document ID and User ID required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()
                
                if not document:
                    return message.create_response(
                        {"success": False, "error": "Document not found"},
                        success=False
                    )
                
                # Only owner can delete
                if document.owner_id != user_id:
                    return message.create_response(
                        {"success": False, "error": "Only owner can delete document"},
                        success=False
                    )
                
                # Soft delete
                document.is_deleted = True
                document.updated_at = datetime.utcnow()
                await session.commit()
                
                # Clear active editors
                if document_id in self._active_editors:
                    del self._active_editors[document_id]
                
                logger.info(f"Document deleted: {document.title}")
                
                # Publish event
                await self.event_bus.publish(Event(
                    event_type=EventType.DOCUMENT_DELETED,
                    data={"document_id": document_id},
                    user_id=user_id,
                    document_id=document_id
                ))
                
                return message.create_response({
                    "success": True,
                    "message": "Document deleted successfully"
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Delete document error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_list(self, message: AgentMessage) -> AgentMessage:
        """
        List documents for a user.
        
        EXPLANATION FOR VIVA:
        ====================
        Returns documents the user can access:
        1. Documents they own
        2. Documents shared with them (collaborator)
        3. Public documents (optionally)
        
        Pagination is important for large numbers of documents.
        """
        payload = message.payload
        
        user_id = payload.get("user_id")
        include_public = payload.get("include_public", False)
        limit = payload.get("limit", 50)
        offset = payload.get("offset", 0)
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                # Build query for accessible documents
                if user_id:
                    # Get owned + collaborated documents
                    result = await session.execute(
                        select(Document).where(
                            and_(
                                Document.is_deleted == False,
                                (Document.owner_id == user_id) | 
                                (Document.collaborators.contains([user_id])) |
                                (Document.is_public == True if include_public else False)
                            )
                        ).order_by(Document.updated_at.desc()).limit(limit).offset(offset)
                    )
                else:
                    # Only public documents
                    result = await session.execute(
                        select(Document).where(
                            and_(
                                Document.is_deleted == False,
                                Document.is_public == True
                            )
                        ).order_by(Document.updated_at.desc()).limit(limit).offset(offset)
                    )
                
                documents = result.scalars().all()
                
                return message.create_response({
                    "success": True,
                    "documents": [doc.to_summary_dict() for doc in documents],
                    "count": len(documents)
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"List documents error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    # ==================== COLLABORATION OPERATIONS ====================
    
    async def _handle_collaborate(self, message: AgentMessage) -> AgentMessage:
        """
        Handle collaboration session (join/leave editing).
        
        EXPLANATION FOR VIVA:
        ====================
        Collaboration tracking:
        1. Join: Add user to active editors list
        2. Leave: Remove user from list
        3. Update cursor: Track cursor position for presence
        
        This enables features like:
        - See who's viewing/editing
        - Show cursors in real-time
        - Prevent conflicts
        
        The presence system helps users coordinate:
        "I see John is editing paragraph 2, I'll work on paragraph 5"
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        user_id = payload.get("user_id")
        action = payload.get("action")  # "join", "leave", "update_cursor"
        cursor_position = payload.get("cursor_position", 0)
        
        if not document_id or not user_id or not action:
            return message.create_response(
                {"success": False, "error": "document_id, user_id, and action required"},
                success=False
            )
        
        try:
            if action == "join":
                # Initialize document's editor tracking if needed
                if document_id not in self._active_editors:
                    self._active_editors[document_id] = {}
                
                # Add user to active editors
                self._active_editors[document_id][user_id] = {
                    "cursor_position": cursor_position,
                    "last_activity": datetime.utcnow(),
                    "joined_at": datetime.utcnow()
                }
                
                logger.info(f"User {user_id} joined document {document_id}")
                
                # Publish join event
                await self.event_bus.publish(Event(
                    event_type=EventType.EDIT_STARTED,
                    data={
                        "document_id": document_id,
                        "user_id": user_id,
                        "active_editors": list(self._active_editors[document_id].keys())
                    },
                    user_id=user_id,
                    document_id=document_id
                ))
                
                return message.create_response({
                    "success": True,
                    "action": "joined",
                    "active_editors": list(self._active_editors[document_id].keys())
                })
            
            elif action == "leave":
                # Remove user from active editors
                if document_id in self._active_editors:
                    self._active_editors[document_id].pop(user_id, None)
                    
                    # Clean up empty document entries
                    if not self._active_editors[document_id]:
                        del self._active_editors[document_id]
                
                logger.info(f"User {user_id} left document {document_id}")
                
                # Publish leave event
                await self.event_bus.publish(Event(
                    event_type=EventType.EDIT_COMPLETED,
                    data={
                        "document_id": document_id,
                        "user_id": user_id,
                        "active_editors": list(
                            self._active_editors.get(document_id, {}).keys()
                        )
                    },
                    user_id=user_id,
                    document_id=document_id
                ))
                
                return message.create_response({
                    "success": True,
                    "action": "left"
                })
            
            elif action == "update_cursor":
                # Update cursor position
                if document_id in self._active_editors:
                    if user_id in self._active_editors[document_id]:
                        self._active_editors[document_id][user_id].update({
                            "cursor_position": cursor_position,
                            "last_activity": datetime.utcnow()
                        })
                
                # Publish cursor update event
                await self.event_bus.publish(Event(
                    event_type=EventType.CURSOR_MOVED,
                    data={
                        "document_id": document_id,
                        "user_id": user_id,
                        "cursor_position": cursor_position
                    },
                    user_id=user_id,
                    document_id=document_id
                ))
                
                return message.create_response({
                    "success": True,
                    "action": "cursor_updated"
                })
            
            else:
                return message.create_response(
                    {"success": False, "error": f"Unknown action: {action}"},
                    success=False
                )
                
        except Exception as e:
            logger.error(f"Collaborate error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_track_change(self, message: AgentMessage) -> AgentMessage:
        """
        Track a real-time change for broadcasting.
        
        EXPLANATION FOR VIVA:
        ====================
        This handles granular, real-time changes (keystroke-level):
        
        1. Receive change from one user
        2. Validate change
        3. Broadcast to all other viewers
        
        This is different from _handle_update which saves to database.
        Track changes are for real-time sync, then periodically saved.
        
        Change types:
        - insert: Character(s) inserted at position
        - delete: Character(s) deleted at position
        - replace: Selection replaced with new text
        
        This enables the "see typing in real-time" feature.
        """
        payload = message.payload
        
        document_id = payload.get("document_id")
        user_id = payload.get("user_id")
        change_type = payload.get("change_type")  # insert, delete, replace
        position = payload.get("position", 0)
        content = payload.get("content", "")
        length = payload.get("length", 0)
        
        if not document_id or not user_id or not change_type:
            return message.create_response(
                {"success": False, "error": "document_id, user_id, and change_type required"},
                success=False
            )
        
        try:
            # Update last activity for the user
            if document_id in self._active_editors:
                if user_id in self._active_editors[document_id]:
                    self._active_editors[document_id][user_id]["last_activity"] = datetime.utcnow()
            
            # Broadcast the change to all document viewers
            await self.event_bus.publish(Event(
                event_type=EventType.DOCUMENT_UPDATED,
                data={
                    "document_id": document_id,
                    "user_id": user_id,
                    "change": {
                        "type": change_type,
                        "position": position,
                        "content": content,
                        "length": length
                    },
                    "realtime": True  # Flag to indicate this is a realtime change
                },
                user_id=user_id,
                document_id=document_id
            ))
            
            return message.create_response({
                "success": True,
                "broadcast": True
            })
            
        except Exception as e:
            logger.error(f"Track change error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    # ==================== UTILITY METHODS ====================
    
    def get_active_editors(self, document_id: str) -> Dict[str, Dict]:
        """Get all active editors for a document."""
        return self._active_editors.get(document_id, {}).copy()
    
    def get_all_active_documents(self) -> List[str]:
        """Get list of documents with active editing sessions."""
        return list(self._active_editors.keys())
    
    async def add_collaborator(self, document_id: str, user_id: str, owner_id: str) -> bool:
        """
        Add a collaborator to a document.
        
        EXPLANATION FOR VIVA:
        ====================
        Sharing a document with another user.
        Only the owner can add collaborators.
        """
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()
                
                if not document or document.owner_id != owner_id:
                    return False
                
                collaborators = document.collaborators or []
                if user_id not in collaborators:
                    collaborators.append(user_id)
                    document.collaborators = collaborators
                    await session.commit()
                
                return True
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Add collaborator error: {e}")
            return False
    
    async def remove_collaborator(self, document_id: str, user_id: str, owner_id: str) -> bool:
        """Remove a collaborator from a document."""
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(Document).where(Document.id == document_id)
                )
                document = result.scalar_one_or_none()
                
                if not document or document.owner_id != owner_id:
                    return False
                
                collaborators = document.collaborators or []
                if user_id in collaborators:
                    collaborators.remove(user_id)
                    document.collaborators = collaborators
                    await session.commit()
                
                return True
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Remove collaborator error: {e}")
            return False
