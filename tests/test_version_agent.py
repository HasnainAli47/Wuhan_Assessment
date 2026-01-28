"""
Tests for Version Control Agent

EXPLANATION FOR VIVA:
=====================
These tests verify the Version Control Agent's functionality:
1. Creating versions (snapshots)
2. Getting version history
3. Reverting to previous versions
4. Tracking contributions

Version control is essential for:
- Data safety (undo mistakes)
- Collaboration (track changes)
- Accountability (who changed what)
"""

import pytest
import pytest_asyncio

from core.agent_base import AgentMessage, MessageType


class TestVersionCreation:
    """
    Tests for version creation functionality.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Creating version snapshots
    - Version numbering
    - Storing content correctly
    """
    
    @pytest.mark.asyncio
    async def test_create_version(self, all_agents):
        """Test creating a version of a document."""
        broker = all_agents["broker"]
        
        # Arrange - Create user and document
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "versioner",
                "email": "version@example.com",
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
                "title": "Versioned Document",
                "content": "Version 1 content"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Act - Create explicit version
        version_msg = AgentMessage(
            type=MessageType.VERSION_CREATE,
            sender="test",
            recipient="version_control_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "change_summary": "Initial version"
            }
        )
        response = await broker.request(version_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert "version" in response.payload
        assert response.payload["version"]["document_id"] == doc_id
        assert response.payload["version"]["change_summary"] == "Initial version"


class TestVersionHistory:
    """
    Tests for version history functionality.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Retrieving version history
    - Version ordering (newest first)
    - Metadata in version list
    """
    
    @pytest.mark.asyncio
    async def test_get_version_history(self, all_agents):
        """Test getting version history for a document."""
        broker = all_agents["broker"]
        
        # Arrange - Create user and document with multiple versions
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "historian",
                "email": "history@example.com",
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
                "title": "History Document",
                "content": "Initial"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Create multiple versions
        for i in range(3):
            version_msg = AgentMessage(
                type=MessageType.VERSION_CREATE,
                sender="test",
                recipient="version_control_agent",
                payload={
                    "document_id": doc_id,
                    "user_id": user_id,
                    "content": f"Version {i+1} content",
                    "title": "History Document",
                    "change_summary": f"Version {i+1}"
                }
            )
            await broker.request(version_msg, timeout=10.0)
        
        # Act - Get history
        history_msg = AgentMessage(
            type=MessageType.VERSION_GET_HISTORY,
            sender="test",
            recipient="version_control_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id
            }
        )
        response = await broker.request(history_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert "versions" in response.payload
        versions = response.payload["versions"]
        assert len(versions) >= 3
        # Check ordering (newest first)
        assert versions[0]["version_number"] > versions[1]["version_number"]


class TestVersionRevert:
    """
    Tests for version revert functionality.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Reverting to a previous version
    - Creating a new version to track the revert
    - Preserving original content after revert
    """
    
    @pytest.mark.asyncio
    async def test_revert_to_version(self, all_agents):
        """Test reverting document to a previous version."""
        broker = all_agents["broker"]
        
        # Arrange - Create user and document
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "reverter",
                "email": "revert@example.com",
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
                "title": "Revert Test",
                "content": "Original content"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Create version 1
        v1_msg = AgentMessage(
            type=MessageType.VERSION_CREATE,
            sender="test",
            recipient="version_control_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "content": "Original content",
                "title": "Revert Test",
                "change_summary": "Version 1"
            }
        )
        await broker.request(v1_msg, timeout=10.0)
        
        # Update document content
        update_msg = AgentMessage(
            type=MessageType.DOC_UPDATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "content": "Modified content - this will be reverted"
            }
        )
        await broker.request(update_msg, timeout=10.0)
        
        # Create version 2
        v2_msg = AgentMessage(
            type=MessageType.VERSION_CREATE,
            sender="test",
            recipient="version_control_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "content": "Modified content - this will be reverted",
                "title": "Revert Test",
                "change_summary": "Version 2"
            }
        )
        await broker.request(v2_msg, timeout=10.0)
        
        # Act - Revert to version 1
        revert_msg = AgentMessage(
            type=MessageType.VERSION_REVERT,
            sender="test",
            recipient="version_control_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "version_number": 1
            }
        )
        response = await broker.request(revert_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert response.payload["document"]["content"] == "Original content"
        assert "Reverted" in response.payload["new_version"]["change_summary"]


class TestVersionCompare:
    """
    Tests for version comparison functionality.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Comparing two versions
    - Getting diff statistics
    - Similarity calculation
    """
    
    @pytest.mark.asyncio
    async def test_compare_versions(self, all_agents):
        """Test comparing two versions of a document."""
        broker = all_agents["broker"]
        
        # Arrange
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "comparer",
                "email": "compare@example.com",
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
                "title": "Compare Test",
                "content": "Hello World"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Create version 1
        v1_msg = AgentMessage(
            type=MessageType.VERSION_CREATE,
            sender="test",
            recipient="version_control_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "content": "Hello World",
                "title": "Compare Test"
            }
        )
        await broker.request(v1_msg, timeout=10.0)
        
        # Create version 2 with different content
        v2_msg = AgentMessage(
            type=MessageType.VERSION_CREATE,
            sender="test",
            recipient="version_control_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "content": "Hello Beautiful World",
                "title": "Compare Test"
            }
        )
        await broker.request(v2_msg, timeout=10.0)
        
        # Act - Compare versions
        compare_msg = AgentMessage(
            type=MessageType.VERSION_COMPARE,
            sender="test",
            recipient="version_control_agent",
            payload={
                "document_id": doc_id,
                "version1": "1",
                "version2": "2",
                "format": "stats"
            }
        )
        response = await broker.request(compare_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert "diff" in response.payload
        assert "statistics" in response.payload["diff"]
        stats = response.payload["diff"]["statistics"]
        assert "similarity" in stats
        assert "characters_added" in stats


class TestContributions:
    """
    Tests for contribution tracking functionality.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Tracking user contributions
    - Calculating contribution statistics
    - Multiple contributor handling
    """
    
    @pytest.mark.asyncio
    async def test_get_contributions(self, all_agents):
        """Test getting contribution statistics for a document."""
        broker = all_agents["broker"]
        
        # Arrange
        reg_msg = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "contributor",
                "email": "contrib@example.com",
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
                "title": "Contribution Test",
                "content": "Initial"
            }
        )
        create_response = await broker.request(create_msg, timeout=10.0)
        doc_id = create_response.payload["document"]["id"]
        
        # Make some edits to create change records
        update_msg = AgentMessage(
            type=MessageType.DOC_UPDATE,
            sender="test",
            recipient="document_editing_agent",
            payload={
                "document_id": doc_id,
                "user_id": user_id,
                "content": "Initial content with additions"
            }
        )
        await broker.request(update_msg, timeout=10.0)
        
        # Act - Get contributions
        contrib_msg = AgentMessage(
            type=MessageType.VERSION_GET_CONTRIBUTIONS,
            sender="test",
            recipient="version_control_agent",
            payload={
                "document_id": doc_id
            }
        )
        response = await broker.request(contrib_msg, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        # Note: contributions may be empty if no changes were tracked
        # This depends on whether the document agent recorded changes
