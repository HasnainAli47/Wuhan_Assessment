"""
User Model - Database Schema for User Management

EXPLANATION FOR VIVA:
=====================
This defines the User table structure using SQLAlchemy ORM.

ORM Mapping:
- Python class 'User' maps to database table 'users'
- Class attributes map to table columns
- Relationships define foreign key connections

Security Considerations:
1. Passwords are NEVER stored in plain text
2. We store a hash using bcrypt (one-way function)
3. Even if database is compromised, passwords are safe

The model follows the Active Record pattern - the class both represents
the data and provides methods to interact with the database.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .database import Base


class User(Base):
    """
    User model for authentication and profile management.
    
    EXPLANATION FOR VIVA:
    ====================
    This model stores:
    1. Identity: id, username, email
    2. Authentication: password_hash (NEVER plain password)
    3. Profile: display_name, bio, avatar_url
    4. Status: is_active, is_admin, last_login
    5. Audit: created_at, updated_at
    
    The __tablename__ sets the actual database table name.
    """
    
    __tablename__ = "users"
    
    # Primary Key - Using UUID for security (not sequential)
    # Sequential IDs leak information (how many users exist, creation order)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Authentication fields
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)  # Bcrypt hash
    
    # Profile fields
    display_name = Column(String(100), nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Status fields
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    last_login = Column(DateTime, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships - define connections to other tables
    # These are loaded lazily (only when accessed) to improve performance
    documents = relationship("Document", back_populates="owner", lazy="dynamic")
    contributions = relationship("DocumentChange", back_populates="user", lazy="dynamic")
    
    def __repr__(self):
        """String representation for debugging."""
        return f"<User(id={self.id}, username={self.username})>"
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """
        Convert user to dictionary for API responses.
        
        EXPLANATION FOR VIVA:
        ====================
        We control what data is exposed via API:
        - Public data: id, username, display_name, etc.
        - Sensitive data: email (only with flag)
        - NEVER exposed: password_hash
        
        This is called Data Transfer Object (DTO) pattern.
        """
        data = {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "bio": self.bio,
            "avatar_url": self.avatar_url,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        
        if include_sensitive:
            data["email"] = self.email
            data["is_admin"] = self.is_admin
            data["last_login"] = self.last_login.isoformat() if self.last_login else None
            data["updated_at"] = self.updated_at.isoformat() if self.updated_at else None
        
        return data
    
    def to_public_dict(self) -> dict:
        """Return only public information (for other users to see)."""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name or self.username,
            "avatar_url": self.avatar_url
        }
