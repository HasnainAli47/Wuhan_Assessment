"""
Tests for Document Editing Agent

================================================================================
DEVELOPED BY: Hasnain Ali | Wuhan University | Supervisor: Prof. Liang Peng
================================================================================

EXPLANATION FOR VIVA:
=====================
These tests verify all functionality of the Document Editing Agent, which is
the heart of the collaborative editing system.

Test Coverage:
1. Document Creation - Creating new documents
2. Document Reading - Fetching document content
3. Document Updating - Editing content and titles
4. Document Deletion - Soft deleting documents
5. Collaboration - Joining/leaving editing sessions
6. Permissions - Access control for documents

Why Document Agent is Important:
- It's the "main feature" of the application
- Handles both single-user and multi-user scenarios
- Maintains document integrity
- Coordinates with Version Control Agent for history

NOTE FOR ASSESSMENT:
- Documents support "soft delete" (marked as deleted, not actually removed)
- Word count is automatically calculated
- Changes are tracked for version history
"""

import pytest
import pytest_asyncio

from core.agent_base import AgentMessage, MessageType


# ==============================================================================
# HELPER FUNCTION
# ==============================================================================
# This helper creates a user and returns their ID to avoid repetition

async def create_test_user(broker, username, email):
    """
    Helper function to create a user for testing.
    Returns the user ID.
    
    This follows the DRY (Don't Repeat Yourself) principle -
    we create users in almost every test, so let's not duplicate that code.
    """
    import uuid
    # Add unique suffix to prevent conflicts between tests
    unique_suffix = uuid.uuid4().hex[:8]
    unique_username = f"{username}_{unique_suffix}"
    unique_email = email.replace("@", f"_{unique_suffix}@")
    
    response = await broker.request(AgentMessage(
        type=MessageType.USER_REGISTER,
        sender="test",
        recipient="user_management_agent",
        payload={
            "username": unique_username,
            "email": unique_email,
            "password": "test_password_123"
        }
    ), timeout=10.0)
    
    assert response.payload.get("success"), f"User creation failed: {response.payload.get('error')}"
    return response.payload["user"]["id"]


# ==============================================================================
# DOCUMENT CREATION TESTS
# ==============================================================================

class TestDocumentCreation:
    """
    Tests for document creation functionality.
    
    Creating documents is the starting point for all collaboration.
    The user who creates the document becomes its owner.
    """
    
    @pytest.mark.asyncio
    async def test_user_can_create_document_with_title_and_content(self, all_agents):
        """
        SCENARIO: User wants to start writing a new document
        GIVEN: A registered user "hasnain"
        WHEN: They create a document with title "My Thesis" and some content
        THEN: Document is created with correct title, content, and ownership
        """
        broker = all_agents["broker"]
        
        # Arrange - Create user
        user_id = await create_test_user(broker, "hasnain", "hasnain@whu.edu.cn")
        
        # Act - Create document
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "My Thesis on Collaborative Systems",
                "content": "Chapter 1: Introduction to Agent-Based Architecture",
                "is_public": False
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        
        doc = response.payload["document"]
        assert doc["title"] == "My Thesis on Collaborative Systems"
        assert "Introduction to Agent-Based Architecture" in doc["content"]
        assert doc["owner_id"] == user_id
        assert doc["is_public"] is False
        assert doc["word_count"] > 0, "Word count should be calculated"
    
    @pytest.mark.asyncio
    async def test_creating_public_document(self, all_agents):
        """
        SCENARIO: User wants to create a document anyone can view
        GIVEN: Registered user
        WHEN: They create a document with is_public=True
        THEN: Document is accessible to everyone
        
        Use case: Sharing research notes with colleagues.
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "public_author", "public@whu.edu.cn")
        
        # Act
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Open Research Notes",
                "content": "These notes are public for all to see",
                "is_public": True  # Anyone can view!
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert response.payload["document"]["is_public"] is True
    
    @pytest.mark.asyncio
    async def test_document_creation_requires_valid_user(self, all_agents):
        """
        SCENARIO: System receives create request without valid user
        GIVEN: No user_id provided
        WHEN: Create document request is made
        THEN: Request fails with clear error
        
        This prevents orphan documents that no one can manage.
        """
        broker = all_agents["broker"]
        
        # Act - Try to create without user_id
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "title": "Orphan Document",
                "content": "No owner specified"
                # Missing user_id!
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is False
    
    @pytest.mark.asyncio
    async def test_document_title_can_be_empty(self, all_agents):
        """
        SCENARIO: User creates document without specifying a title
        GIVEN: Registered user
        WHEN: They create document with empty/no title
        THEN: Document is created with default title "Untitled Document"
        
        This is common UX - Google Docs does the same.
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "untitled_user", "untitled@whu.edu.cn")
        
        # Act
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "content": "Document without a title"
                # No title provided
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        # Should have some default title
        assert response.payload["document"]["title"] is not None


# ==============================================================================
# DOCUMENT READ TESTS
# ==============================================================================

class TestDocumentReading:
    """
    Tests for reading/fetching documents.
    
    Reading is the most common operation - users need to see their documents!
    """
    
    @pytest.mark.asyncio
    async def test_owner_can_read_their_document(self, all_agents):
        """
        SCENARIO: Document owner wants to view their work
        GIVEN: User created a document
        WHEN: They request to read it
        THEN: They receive the full document content
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "reader", "reader@whu.edu.cn")
        
        # Create document
        create_response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "My Research Paper",
                "content": "Abstract: This paper explores collaborative systems..."
            }
        ), timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Read document
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_READ,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert response.payload["document"]["title"] == "My Research Paper"
        assert "collaborative systems" in response.payload["document"]["content"]
    
    @pytest.mark.asyncio
    async def test_user_can_list_their_documents(self, all_agents):
        """
        SCENARIO: User wants to see all their documents
        GIVEN: User has created multiple documents
        WHEN: They request document list
        THEN: They see all their documents
        
        This is the dashboard view.
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "multi_doc_user", "multi@whu.edu.cn")
        
        # Create multiple documents
        for i in range(3):
            await broker.request(AgentMessage(
                type=MessageType.DOC_CREATE,
                sender="test",
                recipient="document_editing_agent",
                payload={
                    "user_id": user_id,
                    "title": f"Document {i + 1}",
                    "content": f"Content for document {i + 1}"
                }
            ), timeout=10.0)
        
        # Act - List documents
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_LIST,
            sender="test",
            recipient="document_editing_agent",
            payload={"user_id": user_id}
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert len(response.payload["documents"]) >= 3


# ==============================================================================
# DOCUMENT UPDATE TESTS
# ==============================================================================

class TestDocumentUpdating:
    """
    Tests for editing/updating documents.
    
    This is the core functionality - users edit their documents!
    """
    
    @pytest.mark.asyncio
    async def test_owner_can_update_document_content(self, all_agents):
        """
        SCENARIO: User edits their document
        GIVEN: User owns document with initial content
        WHEN: They submit updated content
        THEN: Document content is changed
        
        This is what happens every time you type in the editor!
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "editor", "editor@whu.edu.cn")
        
        # Create document
        create_response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Work in Progress",
                "content": "First draft..."
            }
        ), timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Update content
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_UPDATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "content": "Second draft with more details and better writing."
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert "Second draft" in response.payload["document"]["content"]
        assert "content" in response.payload["changes_made"]
    
    @pytest.mark.asyncio
    async def test_owner_can_change_document_title(self, all_agents):
        """
        SCENARIO: User wants to rename their document
        GIVEN: Document with title "Untitled"
        WHEN: User updates title to "My Research Proposal"
        THEN: Title is changed
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "renamer", "renamer@whu.edu.cn")
        
        # Create document
        create_response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Untitled",
                "content": "Content here"
            }
        ), timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Update title
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_UPDATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "title": "My Research Proposal"
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert response.payload["document"]["title"] == "My Research Proposal"
    
    @pytest.mark.asyncio
    async def test_word_count_updates_after_edit(self, all_agents):
        """
        SCENARIO: Verify word count is recalculated after edit
        GIVEN: Document with short content (5 words)
        WHEN: User adds more content
        THEN: Word count increases accordingly
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "word_counter", "words@whu.edu.cn")
        
        # Create document with few words
        create_response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Word Count Test",
                "content": "One two three four five"  # 5 words
            }
        ), timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        initial_count = create_response.payload["document"]["word_count"]
        
        # Act - Add more content
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_UPDATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "content": "One two three four five six seven eight nine ten"  # 10 words
            }
        ), timeout=10.0)
        
        # Assert
        new_count = response.payload["document"]["word_count"]
        assert new_count > initial_count


# ==============================================================================
# DOCUMENT DELETION TESTS
# ==============================================================================

class TestDocumentDeletion:
    """
    Tests for document deletion (soft delete).
    
    We use "soft delete" - documents are marked as deleted but not actually
    removed from the database. This allows for recovery if needed.
    """
    
    @pytest.mark.asyncio
    async def test_owner_can_delete_their_document(self, all_agents):
        """
        SCENARIO: User wants to delete a document they own
        GIVEN: User owns document "To Be Deleted"
        WHEN: They delete it
        THEN: Document is marked as deleted and no longer accessible
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "deleter", "deleter@whu.edu.cn")
        
        # Create document
        create_response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "To Be Deleted",
                "content": "This will be deleted"
            }
        ), timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Delete document
        delete_response = await broker.request(AgentMessage(
            type=MessageType.DOC_DELETE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id
            }
        ), timeout=10.0)
        
        # Assert deletion succeeded
        assert delete_response.payload["success"] is True
        
        # Verify document is no longer accessible
        read_response = await broker.request(AgentMessage(
            type=MessageType.DOC_READ,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id
            }
        ), timeout=10.0)
        assert read_response.payload["success"] is False


# ==============================================================================
# COLLABORATION TESTS
# ==============================================================================

class TestCollaboration:
    """
    Tests for collaborative editing features.
    
    This is what makes it like Google Docs - multiple users editing together!
    """
    
    @pytest.mark.asyncio
    async def test_user_can_join_editing_session(self, all_agents):
        """
        SCENARIO: User opens a document for editing
        GIVEN: Document exists
        WHEN: User joins the editing session
        THEN: They appear in the list of active editors
        
        This is what happens when you click "Edit" on a document.
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "collaborator", "collab@whu.edu.cn")
        
        # Create document
        create_response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": user_id,
                "title": "Collaborative Document",
                "content": "Let's work together!"
            }
        ), timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Join session
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_COLLABORATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "action": "join",
                "cursor_position": 0
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert response.payload["action"] == "joined"
        assert user_id in response.payload["active_editors"]
    
    @pytest.mark.asyncio
    async def test_user_can_leave_editing_session(self, all_agents):
        """
        SCENARIO: User finishes editing and closes the document
        GIVEN: User is in an active editing session
        WHEN: They leave the session
        THEN: They are removed from active editors list
        """
        broker = all_agents["broker"]
        user_id = await create_test_user(broker, "leaver", "leaver@whu.edu.cn")
        
        # Create and join
        create_response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={"user_id": user_id, "title": "Test", "content": "Test"}
        ), timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        await broker.request(AgentMessage(
            type=MessageType.DOC_COLLABORATE,
            sender="test",
            recipient="document_editing_agent",
            payload={"document_id": doc_id, "user_id": user_id, "action": "join"}
        ), timeout=10.0)
        
        # Act - Leave session
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_COLLABORATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "action": "leave"
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert response.payload["action"] == "left"


# ==============================================================================
# PERMISSION TESTS
# ==============================================================================

class TestPermissions:
    """
    Tests for document permission system.
    
    Security is important - users should only access what they're allowed to!
    """
    
    @pytest.mark.asyncio
    async def test_non_owner_cannot_delete_document(self, all_agents):
        """
        SCENARIO: Someone tries to delete a document they don't own
        GIVEN: Document owned by user A
        WHEN: User B tries to delete it
        THEN: Deletion is rejected
        
        Only owners can delete their documents.
        """
        broker = all_agents["broker"]
        
        # Create owner and document
        owner_id = await create_test_user(broker, "owner", "owner@whu.edu.cn")
        create_response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": owner_id,
                "title": "Owner's Document",
                "content": "Only I can delete this"
            }
        ), timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Create another user
        other_id = await create_test_user(broker, "other", "other@whu.edu.cn")
        
        # Act - Other user tries to delete
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_DELETE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": other_id  # Not the owner!
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is False
        assert "owner" in response.payload["error"].lower()
    
    @pytest.mark.asyncio
    async def test_anyone_can_view_public_document(self, all_agents):
        """
        SCENARIO: Public document should be viewable by anyone
        GIVEN: Public document created by user A
        WHEN: User B (random user) tries to read it
        THEN: They can see the content
        
        This is for sharing research openly.
        """
        broker = all_agents["broker"]
        
        # Create owner and public document
        owner_id = await create_test_user(broker, "public_owner", "pubown@whu.edu.cn")
        create_response = await broker.request(AgentMessage(
            type=MessageType.DOC_CREATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "user_id": owner_id,
                "title": "Public Research Notes",
                "content": "These notes are for everyone",
                "is_public": True
            }
        ), timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Create another user
        reader_id = await create_test_user(broker, "random_reader", "random@whu.edu.cn")
        
        # Act - Other user reads public document
        response = await broker.request(AgentMessage(
            type=MessageType.DOC_READ,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": reader_id
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert "everyone" in response.payload["document"]["content"]


# ==============================================================================
# For the viva, be prepared to explain:
# 1. Why we use "soft delete" instead of permanent deletion
# 2. How word count is calculated
# 3. What happens when multiple users edit simultaneously
# 4. How permissions are checked before each operation
# 5. Why document ID is a UUID (universal uniqueness)
# ==============================================================================
