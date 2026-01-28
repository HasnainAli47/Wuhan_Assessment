"""
Version Model - Database Schema for Version Control

EXPLANATION FOR VIVA:
=====================
This module implements version control for documents, similar to Git but simpler.

Key Concepts:
1. Version: A snapshot of a document at a point in time
2. DocumentChange: Individual changes (like Git commits)
3. Diff: The difference between versions

Why Version Control?
- Undo/Redo: Revert to any previous state
- Audit Trail: See who changed what and when
- Collaboration: Resolve conflicts, track contributions
- Recovery: Restore accidentally deleted content

This is similar to how Google Docs tracks "Version History".
"""

from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .database import Base


class Version(Base):
    """
    Version model - stores complete document snapshots.
    
    EXPLANATION FOR VIVA:
    ====================
    Each version is a complete copy of the document at that moment.
    
    Trade-off:
    - Pro: Fast retrieval (no need to reconstruct from diffs)
    - Con: Uses more storage
    
    Alternative approach (not used here):
    - Store only diffs (changes) between versions
    - Pro: Less storage
    - Con: Slower retrieval (must apply all diffs)
    
    We chose the first approach for simplicity and speed.
    For large documents, you might use delta compression.
    """
    
    __tablename__ = "versions"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Document reference
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    
    # Version identification
    version_number = Column(Integer, nullable=False)  # Sequential: 1, 2, 3...
    
    # Content snapshot
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    
    # Who created this version
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    
    # Version metadata
    change_summary = Column(String(500), nullable=True)  # Optional description
    word_count = Column(Integer, default=0)
    character_count = Column(Integer, default=0)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    document = relationship("Document", back_populates="versions")
    
    def __repr__(self):
        return f"<Version(id={self.id}, doc={self.document_id}, v={self.version_number})>"
    
    def to_dict(self, include_content: bool = False) -> dict:
        """
        Convert version to dictionary.
        
        EXPLANATION FOR VIVA:
        ====================
        By default, we don't include content in the response.
        Version history lists show metadata only - content is
        loaded only when viewing a specific version.
        """
        data = {
            "id": self.id,
            "document_id": self.document_id,
            "version_number": self.version_number,
            "title": self.title,
            "created_by": self.created_by,
            "change_summary": self.change_summary,
            "word_count": self.word_count,
            "character_count": self.character_count,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
        
        if include_content:
            data["content"] = self.content
        
        return data


class DocumentChange(Base):
    """
    DocumentChange model - tracks individual changes for contribution tracking.
    
    EXPLANATION FOR VIVA:
    ====================
    While Version stores complete snapshots, DocumentChange stores individual
    edits. This enables:
    
    1. Contribution tracking: Count how much each user contributed
    2. Real-time sync: Apply individual changes to other users' views
    3. Fine-grained history: See exactly what changed, not just the result
    
    Change Types:
    - insert: New text added
    - delete: Text removed
    - replace: Text replaced (insert + delete)
    
    Position tracking:
    - position: Where the change occurred (character offset)
    - length: How many characters affected
    
    This is similar to Operational Transformation (OT) used in Google Docs,
    though simplified. OT handles concurrent edits by transforming operations.
    """
    
    __tablename__ = "document_changes"
    
    # Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # References
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    
    # Change details
    change_type = Column(String(20), nullable=False)  # insert, delete, replace
    position = Column(Integer, nullable=False)  # Character position
    length = Column(Integer, default=0)  # Characters affected
    
    # Content of the change
    old_content = Column(Text, nullable=True)  # What was there before (for delete/replace)
    new_content = Column(Text, nullable=True)  # What was added (for insert/replace)
    
    # Session tracking (for grouping changes)
    session_id = Column(String(36), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="changes")
    user = relationship("User", back_populates="contributions")
    
    def __repr__(self):
        return f"<DocumentChange(id={self.id}, type={self.change_type}, pos={self.position})>"
    
    def to_dict(self) -> dict:
        """Convert change to dictionary."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "user_id": self.user_id,
            "change_type": self.change_type,
            "position": self.position,
            "length": self.length,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def calculate_diff(cls, old_text: str, new_text: str) -> list:
        """
        Calculate the differences between two texts.
        
        EXPLANATION FOR VIVA:
        ====================
        This is a simple diff algorithm. For production, you'd use
        a proper diff library like 'difflib' or specialized OT algorithms.
        
        The output is a list of changes that, when applied to old_text,
        produce new_text.
        """
        import difflib
        
        changes = []
        matcher = difflib.SequenceMatcher(None, old_text, new_text)
        
        for opcode, i1, i2, j1, j2 in matcher.get_opcodes():
            if opcode == 'replace':
                changes.append({
                    'type': 'replace',
                    'position': i1,
                    'length': i2 - i1,
                    'old_content': old_text[i1:i2],
                    'new_content': new_text[j1:j2]
                })
            elif opcode == 'delete':
                changes.append({
                    'type': 'delete',
                    'position': i1,
                    'length': i2 - i1,
                    'old_content': old_text[i1:i2],
                    'new_content': None
                })
            elif opcode == 'insert':
                changes.append({
                    'type': 'insert',
                    'position': i1,
                    'length': 0,
                    'old_content': None,
                    'new_content': new_text[j1:j2]
                })
        
        return changes


def get_contribution_stats(changes: list, user_id: str) -> dict:
    """
    Calculate contribution statistics for a user.
    
    EXPLANATION FOR VIVA:
    ====================
    This aggregates DocumentChanges to show:
    - How many changes the user made
    - How many characters they added/removed
    - Their percentage of total contributions
    
    This is useful for:
    - Recognizing contributors
    - Academic citation (who wrote what)
    - Workload analysis
    """
    user_changes = [c for c in changes if c.user_id == user_id]
    total_changes = len(changes)
    
    chars_added = sum(
        len(c.new_content or '') 
        for c in user_changes 
        if c.change_type in ['insert', 'replace']
    )
    
    chars_removed = sum(
        len(c.old_content or '') 
        for c in user_changes 
        if c.change_type in ['delete', 'replace']
    )
    
    return {
        "user_id": user_id,
        "total_changes": len(user_changes),
        "percentage": (len(user_changes) / total_changes * 100) if total_changes > 0 else 0,
        "characters_added": chars_added,
        "characters_removed": chars_removed,
        "net_characters": chars_added - chars_removed
    }
