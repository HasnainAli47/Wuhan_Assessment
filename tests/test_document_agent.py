"""
Tests for Document Editing Agent

EXPLANATION FOR VIVA:
=====================
These tests verify the Document Editing Agent's functionality:
1. Document Creation
2. Document Editing (Collaborative)
3. Real-time Change Tracking

Each test follows the Arrange-Act-Assert pattern for clarity.
"""

import pytest
import pytest_asyncio

from core.agent_base import AgentMessage, MessageType


class TestDocumentCreation:
    """
    Tests for document creation functionality.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Creating a document with valid data
    - Document initialization (counts, timestamps)
    - Permission assignment (owner)
    """
    
    @pytest.mark.asyncio
    async def test_create_document(self, all_agents):
        """Test creating a new document."""
        broker = all_agents["broker"]
        
        # Arrange - First create a user
        register_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "docuser",
                "email": "docuser@example.com",
                "password": "password123"
            }
        )
        reg_response = await broker.request(register_msg, timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        # Act - Create document
        create_msg = AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "My Test Document",
                "content": "This is the initial content.",
                "is_public": False
            }
        )
        response = await broker.request(create_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert "document" in response.payload
        doc = response.payload["document"]
        assert doc["title"] == "My Test Document"
        assert doc["content"] == "This is the initial content."
        assert doc["owner_id"] == user_id
        assert doc["word_count"] > 0
    
    @pytest.mark.asyncio
    async def test_create_document_without_user(self, all_agents):
        """Test that document creation requires a valid user."""
        broker = all_agents["broker"]
        
        # Act - Try to create without user_id
        create_msg = AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "title": "Orphan Document",
                "content": "No user"
            }
        )
        response = await broker.request(create_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is False


class TestDocumentOperations:
    """
    Tests for document read, update, delete operations.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify CRUD operations:
    - Reading documents (with permission checks)
    - Updating document content and title
    - Soft deleting documents
    """
    
    @pytest.mark.asyncio
    async def test_read_document(self, all_agents):
        """Test reading a document."""
        broker = all_agents["broker"]
        
        # Arrange - Create user and document
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "reader",
                "email": "reader@example.com",
                "password": "password123"
            }
        )
        reg_response = await broker.request(reg_msg, timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        create_msg = AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Readable Document",
                "content": "Content to read"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Read document
        read_msg = AgentMessage(
            type=MessageType.DOC_READ,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id
            }
        )
        response = await broker.request(read_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert response.payload["document"]["title"] == "Readable Document"
    
    @pytest.mark.asyncio
    async def test_update_document_content(self, all_agents):
        """Test updating document content."""
        broker = all_agents["broker"]
        
        # Arrange
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "editor",
                "email": "editor@example.com",
                "password": "password123"
            }
        )
        reg_response = await broker.request(reg_msg, timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        create_msg = AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Editable Document",
                "content": "Original content"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Update content
        update_msg = AgentMessage(
            type=MessageType.DOC_UPDATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "content": "Updated content with more text"
            }
        )
        response = await broker.request(update_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert "content" in response.payload["changes_made"]
        assert response.payload["document"]["content"] == "Updated content with more text"
    
    @pytest.mark.asyncio
    async def test_delete_document(self, all_agents):
        """Test deleting a document (soft delete)."""
        broker = all_agents["broker"]
        
        # Arrange
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "deleter",
                "email": "deleter@example.com",
                "password": "password123"
            }
        )
        reg_response = await broker.request(reg_msg, timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        create_msg = AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Deletable Document",
                "content": "To be deleted"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Delete document
        delete_msg = AgentMessage(
            type=MessageType.DOC_DELETE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id
            }
        )
        response = await broker.request(delete_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        
        # Verify document is no longer accessible
        read_msg = AgentMessage(
            type=MessageType.DOC_READ,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id
            }
        )
        read_response = await broker.request(read_msg, timeout=10.0)
        assert read_response.payload["success"] is False


class TestCollaboration:
    """
    Tests for collaborative editing features.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Joining/leaving editing sessions
    - Tracking active editors
    - Permission checks for editing
    """
    
    @pytest.mark.asyncio
    async def test_join_document_session(self, all_agents):
        """Test joining a collaborative editing session."""
        broker = all_agents["broker"]
        
        # Arrange
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "collaborator",
                "email": "collab@example.com",
                "password": "password123"
            }
        )
        reg_response = await broker.request(reg_msg, timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        create_msg = AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Collaborative Document",
                "content": "Let's work together"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Join editing session
        join_msg = AgentMessage(
            type=MessageType.DOC_COLLABORATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "action": "join",
                "cursor_position": 0
            }
        )
        response = await broker.request(join_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert response.payload["action"] == "joined"
        assert user_id in response.payload["active_editors"]
    
    @pytest.mark.asyncio
    async def test_leave_document_session(self, all_agents):
        """Test leaving a collaborative editing session."""
        broker = all_agents["broker"]
        
        # Arrange - Join first
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "leaver",
                "email": "leaver@example.com",
                "password": "password123"
            }
        )
        reg_response = await broker.request(reg_msg, timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        create_msg = AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Leave Test Document",
                "content": "Goodbye"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Join
        join_msg = AgentMessage(
            type=MessageType.DOC_COLLABORATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "action": "join"
            }
        )
        await broker.request(join_msg, timeout=10.0)
        
        # Act - Leave
        leave_msg = AgentMessage(
            type=MessageType.DOC_COLLABORATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "action": "leave"
            }
        )
        response = await broker.request(leave_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert response.payload["action"] == "left"


class TestDocumentPermissions:
    """
    Tests for document permission system.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Owner has full access
    - Non-owners cannot edit unless collaborator
    - Public documents are viewable by all
    """
    
    @pytest.mark.asyncio
    async def test_non_owner_cannot_delete(self, all_agents):
        """Test that non-owners cannot delete documents."""
        broker = all_agents["broker"]
        
        # Arrange - Create owner and document
        owner_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "owner",
                "email": "owner@example.com",
                "password": "password123"
            }
        )
        owner_response = await broker.request(owner_msg, timeout=10.0)
        owner_id = owner_response.payload["user"]["id"]
        
        create_msg = AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": owner_id,
                "title": "Owner's Document",
                "content": "Private"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Create another user
        other_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "other",
                "email": "other@example.com",
                "password": "password123"
            }
        )
        other_response = await broker.request(other_msg, timeout=10.0)
        other_id = other_response.payload["user"]["id"]
        
        # Act - Try to delete as non-owner
        delete_msg = AgentMessage(
            type=MessageType.DOC_DELETE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": other_id  # Not the owner
            }
        )
        response = await broker.request(delete_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is False
        assert "owner" in response.payload["error"].lower()
