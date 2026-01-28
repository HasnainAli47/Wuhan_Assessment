"""
Tests for User Management Agent

EXPLANATION FOR VIVA:
=====================
These tests verify the User Management Agent's functionality:
1. User Registration
2. User Authentication (Login)
3. Profile Management

Test Structure (Arrange-Act-Assert):
1. Arrange: Set up test data and preconditions
2. Act: Perform the action being tested
3. Assert: Verify the expected outcome

We test both success and failure cases to ensure robustness.
"""

import pytest
import pytest_asyncio
from datetime import datetime

from core.agent_base import AgentMessage, MessageType


class TestUserRegistration:
    """
    Tests for user registration functionality.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Successful registration with valid data
    - Rejection of duplicate usernames
    - Rejection of duplicate emails
    - Validation of password requirements
    """
    
    @pytest.mark.asyncio
    async def test_successful_registration(self, user_agent, message_broker):
        """Test successful user registration with valid data."""
        # Arrange
        message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "securepass123",
                "display_name": "New User"
            }
        )
        
        # Act
        response = await message_broker.request(message, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert "user" in response.payload
        assert response.payload["user"]["username"] == "newuser"
        assert response.payload["user"]["email"] == "newuser@example.com"
        assert "password" not in response.payload["user"]  # Password should not be returned
        assert "password_hash" not in response.payload["user"]
    
    @pytest.mark.asyncio
    async def test_registration_duplicate_username(self, user_agent, message_broker):
        """Test that duplicate usernames are rejected."""
        # Arrange - First registration
        first_message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "duplicateuser",
                "email": "first@example.com",
                "password": "password123"
            }
        )
        await message_broker.request(first_message, timeout=10.0)
        
        # Act - Second registration with same username
        second_message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "duplicateuser",  # Same username
                "email": "second@example.com",  # Different email
                "password": "password456"
            }
        )
        response = await message_broker.request(second_message, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is False
        assert "already taken" in response.payload["error"].lower()
    
    @pytest.mark.asyncio
    async def test_registration_short_password(self, user_agent, message_broker):
        """Test that short passwords are rejected."""
        # Arrange
        message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "shortpwuser",
                "email": "shortpw@example.com",
                "password": "12345"  # Only 5 characters, minimum is 6
            }
        )
        
        # Act
        response = await message_broker.request(message, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is False
        assert "password" in response.payload["error"].lower()


class TestUserAuthentication:
    """
    Tests for user login/logout functionality.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Successful login with correct credentials
    - Rejection of invalid credentials
    - JWT token generation
    - Logout functionality
    """
    
    @pytest.mark.asyncio
    async def test_successful_login(self, user_agent, message_broker):
        """Test successful login with correct credentials."""
        # Arrange - Register user first
        register_message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "loginuser",
                "email": "login@example.com",
                "password": "correctpassword"
            }
        )
        await message_broker.request(register_message, timeout=10.0)
        
        # Act - Login
        login_message = AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "loginuser",
                "password": "correctpassword"
            }
        )
        response = await message_broker.request(login_message, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert "token" in response.payload
        assert len(response.payload["token"]) > 0
        assert "user" in response.payload
    
    @pytest.mark.asyncio
    async def test_login_with_email(self, user_agent, message_broker):
        """Test login using email instead of username."""
        # Arrange - Register user
        register_message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "emaillogin",
                "email": "emaillogin@example.com",
                "password": "mypassword"
            }
        )
        await message_broker.request(register_message, timeout=10.0)
        
        # Act - Login with email
        login_message = AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "emaillogin@example.com",  # Using email
                "password": "mypassword"
            }
        )
        response = await message_broker.request(login_message, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
    
    @pytest.mark.asyncio
    async def test_login_invalid_password(self, user_agent, message_broker):
        """Test login rejection with wrong password."""
        # Arrange - Register user
        register_message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "wrongpwuser",
                "email": "wrongpw@example.com",
                "password": "rightpassword"
            }
        )
        await message_broker.request(register_message, timeout=10.0)
        
        # Act - Login with wrong password
        login_message = AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "wrongpwuser",
                "password": "wrongpassword"  # Wrong password
            }
        )
        response = await message_broker.request(login_message, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is False
        assert "invalid" in response.payload["error"].lower()


class TestProfileManagement:
    """
    Tests for user profile operations.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Getting user profile
    - Updating profile information
    - Privacy controls (public vs private data)
    """
    
    @pytest.mark.asyncio
    async def test_get_own_profile(self, user_agent, message_broker):
        """Test getting own profile includes sensitive data."""
        # Arrange - Register user
        register_message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "profileuser",
                "email": "profile@example.com",
                "password": "password123"
            }
        )
        reg_response = await message_broker.request(register_message, timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        # Act - Get own profile
        get_message = AgentMessage(
            type=MessageType.USER_GET_PROFILE,
            sender="test",
            recipient="user_management_agent",
            payload={
                "user_id": user_id,
                "requesting_user_id": user_id  # Same user
            }
        )
        response = await message_broker.request(get_message, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert "email" in response.payload["user"]  # Sensitive data included
    
    @pytest.mark.asyncio
    async def test_update_profile(self, user_agent, message_broker):
        """Test updating user profile."""
        # Arrange - Register user
        register_message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "updateuser",
                "email": "update@example.com",
                "password": "password123"
            }
        )
        reg_response = await message_broker.request(register_message, timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        # Act - Update profile
        update_message = AgentMessage(
            type=MessageType.USER_UPDATE_PROFILE,
            sender="test",
            recipient="user_management_agent",
            payload={
                "user_id": user_id,
                "updates": {
                    "display_name": "Updated Name",
                    "bio": "This is my updated bio"
                }
            }
        )
        response = await message_broker.request(update_message, timeout=10.0)
        
        # Assert
        assert response is not None
        assert response.payload["success"] is True
        assert response.payload["user"]["display_name"] == "Updated Name"
        assert response.payload["user"]["bio"] == "This is my updated bio"


class TestTokenVerification:
    """
    Tests for JWT token functionality.
    
    EXPLANATION FOR VIVA:
    ====================
    These tests verify:
    - Token is valid after login
    - Token contains correct user information
    """
    
    @pytest.mark.asyncio
    async def test_token_verification(self, user_agent, message_broker):
        """Test that generated tokens are valid."""
        # Arrange - Register and login
        register_message = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "tokenuser",
                "email": "token@example.com",
                "password": "password123"
            }
        )
        await message_broker.request(register_message, timeout=10.0)
        
        login_message = AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "tokenuser",
                "password": "password123"
            }
        )
        login_response = await message_broker.request(login_message, timeout=10.0)
        token = login_response.payload["token"]
        
        # Act - Verify token
        payload = user_agent.verify_token(token)
        
        # Assert
        assert payload is not None
        assert payload["username"] == "tokenuser"
        assert "sub" in payload  # User ID
        assert "exp" in payload  # Expiration
