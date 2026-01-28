"""
Document Model - Database Schema for Document Management

EXPLANATION FOR VIVA:
=====================
This model represents documents in the collaborative editing system.

Key Design Decisions:
1. Content storage: Stored as Text for flexibility
2. Versioning: Linked to Version model for history
3. Collaboration: Tracks active editors and permissions
4. Soft delete: Documents aren't truly deleted (is_deleted flag)

The relationship with User is Many-to-One (many documents, one owner).
The relationship with Version is One-to-Many (one document, many versions).
"""

from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .database import Base


class Document(Base):
    """
    Document model for storing and managing documents.
    
    EXPLANATION FOR VIVA:
    ====================
    A document contains:
    1. Identity: id, title
    2. Content: content (the actual text)
    3. Ownership: owner_id (who created it)
    4. Sharing: is_public, collaborators
    5. State: is_deleted (soft delete), is_locked
    6. Metadata: created_at, updated_at, word_count
    
    Soft Delete Pattern:
    - Instead of DELETE, we SET is_deleted = True
    - This allows recovery and maintains referential integrity
    - Queries filter out deleted documents by default
    """
    
    __tablename__ = "documents"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Document content
    title = Column(String(255), nullable=False, default="Untitled Document")
    content = Column(Text, default="")  # The actual document content
    
    # Ownership
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Sharing and permissions
    is_public = Column(Boolean, default=False)
    collaborators = Column(JSON, default=list)  # List of user IDs with access
    
    # Document state
    is_deleted = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)  # Prevents editing
    locked_by = Column(String(36), nullable=True)  # User who locked it
    
    # Optimistic locking for conflict detection
    # Increments on each edit - clients compare their version with server version
    edit_version = Column(Integer, default=1)
    
    # Metadata
    word_count = Column(Integer, default=0)
    character_count = Column(Integer, default=0)
    
    # Active editing session info
    active_editors = Column(JSON, default=list)  # Users currently editing
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_edited_by = Column(String(36), nullable=True)
    
    # Relationships
    owner = relationship("User", back_populates="documents")
    versions = relationship("Version", back_populates="document", lazy="dynamic", 
                           order_by="desc(Version.version_number)")
    changes = relationship("DocumentChange", back_populates="document", lazy="dynamic",
                          order_by="desc(DocumentChange.created_at)")
    
    def __repr__(self):
        return f"<Document(id={self.id}, title={self.title})>"
    
    def to_dict(self, include_content: bool = True) -> dict:
        """
        Convert document to dictionary for API responses.
        
        EXPLANATION FOR VIVA:
        ====================
        The include_content flag allows listing documents without
        loading their full content (more efficient for document lists).
        """
        data = {
            "id": self.id,
            "title": self.title,
            "owner_id": self.owner_id,
            "is_public": self.is_public,
            "collaborators": self.collaborators or [],
            "is_locked": self.is_locked,
            "locked_by": self.locked_by,
            "edit_version": self.edit_version or 1,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "active_editors": self.active_editors or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_edited_by": self.last_edited_by
        }
        
        if include_content:
            data["content"] = self.content
        
        return data
    
    def to_summary_dict(self) -> dict:
        """Return summary info for document lists."""
        return {
            "id": self.id,
            "title": self.title,
            "owner_id": self.owner_id,
            "word_count": self.word_count,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "is_public": self.is_public
        }
    
    def update_counts(self):
        """
        Update word and character counts.
        
        EXPLANATION FOR VIVA:
        ====================
        These counts are cached for performance - we don't want to
        count words every time someone views the document list.
        They're updated whenever the content changes.
        """
        if self.content:
            self.character_count = len(self.content)
            self.word_count = len(self.content.split())
        else:
            self.character_count = 0
            self.word_count = 0
    
    def can_edit(self, user_id: str) -> bool:
        """
        Check if a user can edit this document.
        
        EXPLANATION FOR VIVA:
        ====================
        Permission check logic:
        1. Owner can always edit
        2. Collaborators can edit
        3. Public documents can be edited by anyone (collaborative editing)
        
        This is called Authorization - determining what a user can do.
        (Authentication determines who the user is)
        
        For a collaborative editing system like Google Docs, public documents
        are editable by anyone with the link.
        """
        if self.is_locked and self.locked_by != user_id:
            return False
        if self.owner_id == user_id:
            return True
        if user_id in (self.collaborators or []):
            return True
        # Public documents can be edited by anyone (collaborative feature)
        if self.is_public:
            return True
        return False
    
    def can_view(self, user_id: str) -> bool:
        """Check if a user can view this document."""
        if self.is_public:
            return True
        if self.owner_id == user_id:
            return True
        if user_id in (self.collaborators or []):
            return True
        return False
