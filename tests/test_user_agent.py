"""
Tests for User Management Agent

================================================================================
DEVELOPED BY: Hasnain Ali | Wuhan University | Supervisor: Prof. Liang Peng
================================================================================

EXPLANATION FOR VIVA:
=====================
These tests verify all functionality of the User Management Agent. They are 
organized by feature (registration, authentication, profile management) and 
follow best practices for testing.

Test Philosophy:
- Each test should be independent and not rely on other tests
- Test both "happy path" (success) and "sad path" (failure) scenarios
- Use descriptive names that explain what is being tested
- Follow Arrange-Act-Assert (AAA) pattern for clarity

Test Coverage:
1. User Registration
   - Successful registration
   - Duplicate username rejection
   - Duplicate email rejection
   - Password validation

2. User Authentication
   - Successful login
   - Login with email
   - Invalid credentials rejection
   - JWT token generation

3. Profile Management
   - Get own profile
   - Update profile
   - Delete account

NOTE FOR ASSESSMENT:
- These tests run against an in-memory database
- No external services are called (pure unit/integration tests)
- All tests should pass when run with: pytest tests/test_user_agent.py -v
"""

import pytest
import pytest_asyncio
from datetime import datetime

from core.agent_base import AgentMessage, MessageType


# ==============================================================================
# REGISTRATION TESTS
# ==============================================================================
# These tests verify that users can create accounts properly

class TestUserRegistration:
    """
    Tests for user registration functionality.
    
    Registration is the first step for any user - they need to create an account
    before they can use the system. These tests ensure:
    - Valid registrations succeed
    - Invalid data is rejected with helpful error messages
    - Security rules (like password length) are enforced
    """
    
    @pytest.mark.asyncio
    async def test_user_can_register_with_valid_data(self, user_agent, message_broker):
        """
        SCENARIO: A new user wants to create an account
        GIVEN: Valid registration details (username, email, password)
        WHEN: They submit the registration form
        THEN: Their account is created successfully
        
        This is the "happy path" - everything works as expected.
        """
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        # Arrange - Prepare the registration request
        registration_request = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="registration_form",
            recipient="user_management_agent",
            payload={
                "username": f"hasnain_ali_{unique_id}",
                "email": f"hasnain_{unique_id}@whu.edu.cn",
                "password": "secure_password_123",
                "display_name": "Hasnain Ali"
            }
        )
        
        # Act - Send the registration request to the agent
        response = await message_broker.request(registration_request, timeout=10.0)
        
        # Assert - Verify the registration was successful
        assert response is not None, "Response should not be None"
        assert response.payload["success"] is True, "Registration should succeed"
        assert "user" in response.payload, "Response should include user data"
        
        # Verify the user data is correct
        user_data = response.payload["user"]
        assert "hasnain_ali" in user_data["username"]
        assert "whu.edu.cn" in user_data["email"]
        
        # Security check: Password should NEVER be returned
        assert "password" not in user_data, "Password must not be in response"
        assert "password_hash" not in user_data, "Password hash must not be in response"
    
    @pytest.mark.asyncio
    async def test_registration_fails_for_duplicate_username(self, user_agent, message_broker):
        """
        SCENARIO: Someone tries to register with a username that already exists
        GIVEN: A user "professor_liang" already exists
        WHEN: Another person tries to register with username "professor_liang"
        THEN: Registration fails with a clear error message
        
        This prevents users from impersonating others.
        """
        # Arrange - First, create a user
        first_registration = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "professor_liang",
                "email": "first@whu.edu.cn",
                "password": "password123"
            }
        )
        await message_broker.request(first_registration, timeout=10.0)
        
        # Act - Try to register with the same username but different email
        duplicate_registration = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "professor_liang",  # Same username!
                "email": "different@whu.edu.cn",  # Different email
                "password": "anotherpassword"
            }
        )
        response = await message_broker.request(duplicate_registration, timeout=10.0)
        
        # Assert - Registration should fail with clear error
        assert response is not None
        assert response.payload["success"] is False
        assert "already taken" in response.payload["error"].lower()
    
    @pytest.mark.asyncio
    async def test_registration_fails_for_duplicate_email(self, user_agent, message_broker):
        """
        SCENARIO: Someone tries to register with an email that's already in use
        GIVEN: An account with email "student@whu.edu.cn" exists
        WHEN: Another registration uses the same email
        THEN: Registration fails because each account needs a unique email
        
        This ensures password reset and notifications go to the right person.
        """
        # Arrange - Create first user
        first_registration = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "first_student",
                "email": "shared@whu.edu.cn",
                "password": "password123"
            }
        )
        await message_broker.request(first_registration, timeout=10.0)
        
        # Act - Try to register with same email
        second_registration = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "second_student",  # Different username
                "email": "shared@whu.edu.cn",  # Same email!
                "password": "password456"
            }
        )
        response = await message_broker.request(second_registration, timeout=10.0)
        
        # Assert
        assert response.payload["success"] is False
        assert "email" in response.payload["error"].lower()
    
    @pytest.mark.asyncio
    async def test_registration_fails_for_weak_password(self, user_agent, message_broker):
        """
        SCENARIO: User tries to create account with a password that's too short
        GIVEN: Minimum password length is 6 characters
        WHEN: User submits password "12345" (only 5 characters)
        THEN: Registration fails with password requirement error
        
        This enforces basic password security.
        Note: In production, we'd also check for complexity (uppercase, numbers, etc.)
        """
        # Arrange
        weak_password_registration = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "weak_password_user",
                "email": "weak@whu.edu.cn",
                "password": "12345"  # Only 5 characters - too short!
            }
        )
        
        # Act
        response = await message_broker.request(weak_password_registration, timeout=10.0)
        
        # Assert
        assert response.payload["success"] is False
        assert "password" in response.payload["error"].lower()
    
    @pytest.mark.asyncio
    async def test_registration_creates_user_with_correct_timestamps(self, user_agent, message_broker):
        """
        SCENARIO: Verify that timestamps are recorded when user registers
        GIVEN: Current time
        WHEN: User registers
        THEN: created_at timestamp is set to approximately current time
        
        Timestamps are important for:
        - Auditing when accounts were created
        - Sorting users by registration date
        - Identifying inactive accounts
        """
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        # Arrange
        before_registration = datetime.utcnow()
        
        registration = AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": f"timestamp_test_user_{unique_id}",
                "email": f"timestamp_{unique_id}@whu.edu.cn",
                "password": "password123"
            }
        )
        
        # Act
        response = await message_broker.request(registration, timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert "created_at" in response.payload["user"]


# ==============================================================================
# AUTHENTICATION TESTS
# ==============================================================================
# These tests verify login and logout functionality

class TestUserAuthentication:
    """
    Tests for user login/logout (authentication) functionality.
    
    Authentication answers the question: "Who is this person?"
    After logging in, users receive a JWT token they can use for subsequent requests.
    """
    
    @pytest.mark.asyncio
    async def test_user_can_login_with_correct_credentials(self, user_agent, message_broker):
        """
        SCENARIO: Registered user logs into their account
        GIVEN: User "student_wang" exists with password "my_password"
        WHEN: They login with correct username and password
        THEN: They receive a JWT token for authentication
        
        The JWT token is used for all subsequent API calls to identify the user.
        """
        # Arrange - First register the user
        await message_broker.request(AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "student_wang",
                "email": "wang@whu.edu.cn",
                "password": "my_password"
            }
        ), timeout=10.0)
        
        # Act - Login with correct credentials
        login_request = AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="login_form",
            recipient="user_management_agent",
            payload={
                "username": "student_wang",
                "password": "my_password"
            }
        )
        response = await message_broker.request(login_request, timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True, "Login should succeed"
        assert "token" in response.payload, "Should receive JWT token"
        assert len(response.payload["token"]) > 50, "Token should be a substantial JWT"
        assert "user" in response.payload, "Should receive user data"
    
    @pytest.mark.asyncio
    async def test_user_can_login_with_email_instead_of_username(self, user_agent, message_broker):
        """
        SCENARIO: User forgets username but remembers email
        GIVEN: User registered with email "zhang@whu.edu.cn"
        WHEN: They login using their email address
        THEN: Login succeeds (we allow both username and email for login)
        
        This is a common UX pattern - Google, GitHub, etc. all allow this.
        """
        # Arrange
        await message_broker.request(AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "zhang_wei",
                "email": "zhang@whu.edu.cn",
                "password": "test_password"
            }
        ), timeout=10.0)
        
        # Act - Login with email
        response = await message_broker.request(AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "zhang@whu.edu.cn",  # Using email as username
                "password": "test_password"
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
    
    @pytest.mark.asyncio
    async def test_login_fails_with_wrong_password(self, user_agent, message_broker):
        """
        SCENARIO: Someone tries to login with the wrong password
        GIVEN: User "li_ming" has password "correct_password"
        WHEN: Login attempted with "wrong_password"
        THEN: Login is rejected with generic error (for security)
        
        Note: We don't say "wrong password" specifically because that would
        confirm the username exists, which is a security risk.
        """
        # Arrange
        await message_broker.request(AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "li_ming",
                "email": "li@whu.edu.cn",
                "password": "correct_password"
            }
        ), timeout=10.0)
        
        # Act - Try login with wrong password
        response = await message_broker.request(AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "li_ming",
                "password": "wrong_password"  # Incorrect!
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is False
        assert "invalid" in response.payload["error"].lower()
    
    @pytest.mark.asyncio
    async def test_login_fails_for_nonexistent_user(self, user_agent, message_broker):
        """
        SCENARIO: Someone tries to login with a username that doesn't exist
        GIVEN: No user "ghost_user" exists
        WHEN: Login attempted for "ghost_user"
        THEN: Login fails with same generic error (doesn't reveal user existence)
        """
        # Act - Try to login as non-existent user
        response = await message_broker.request(AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "ghost_user_that_does_not_exist",
                "password": "any_password"
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is False


# ==============================================================================
# PROFILE MANAGEMENT TESTS
# ==============================================================================
# These tests verify users can view and update their profiles

class TestProfileManagement:
    """
    Tests for user profile operations.
    
    Profile management allows users to:
    - View their own profile (includes private data like email)
    - Update their display name, bio, etc.
    - (View others' public profiles - coming in future)
    """
    
    @pytest.mark.asyncio
    async def test_user_can_view_their_own_profile(self, user_agent, message_broker):
        """
        SCENARIO: User wants to see their profile information
        GIVEN: Logged in user "chen_xiaoming"
        WHEN: They request their own profile
        THEN: They see all their data including private fields like email
        """
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        # Arrange - Create user
        reg_response = await message_broker.request(AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": f"chen_xiaoming_{unique_id}",
                "email": f"chen_{unique_id}@whu.edu.cn",
                "password": "password123",
                "display_name": "Chen Xiaoming"
            }
        ), timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        # Act - Get own profile
        response = await message_broker.request(AgentMessage(
            type=MessageType.USER_GET_PROFILE,
            sender="test",
            recipient="user_management_agent",
            payload={
                "user_id": user_id,
                "requesting_user_id": user_id  # Same user - viewing own profile
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert "chen_xiaoming" in response.payload["user"]["username"]
        assert "whu.edu.cn" in response.payload["user"]["email"]  # Private data visible
        assert response.payload["user"]["display_name"] == "Chen Xiaoming"
    
    @pytest.mark.asyncio
    async def test_user_can_update_their_display_name(self, user_agent, message_broker):
        """
        SCENARIO: User wants to change how their name appears
        GIVEN: User "wu_fang" with display name "Wu Fang"
        WHEN: They update display name to "Dr. Wu Fang (PhD)"
        THEN: Display name is updated successfully
        
        Common use case: Student graduates and wants to add their title.
        """
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        # Arrange
        reg_response = await message_broker.request(AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": f"wu_fang_{unique_id}",
                "email": f"wu_{unique_id}@whu.edu.cn",
                "password": "password123",
                "display_name": "Wu Fang"
            }
        ), timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        # Act - Update display name
        response = await message_broker.request(AgentMessage(
            type=MessageType.USER_UPDATE_PROFILE,
            sender="test",
            recipient="user_management_agent",
            payload={
                "user_id": user_id,
                "updates": {
                    "display_name": "Dr. Wu Fang (PhD)"
                }
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert response.payload["user"]["display_name"] == "Dr. Wu Fang (PhD)"
    
    @pytest.mark.asyncio
    async def test_user_can_add_bio_to_profile(self, user_agent, message_broker):
        """
        SCENARIO: User wants to add a biography to their profile
        GIVEN: User without a bio
        WHEN: They add a bio describing themselves
        THEN: Bio is saved and appears on their profile
        """
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        # Arrange
        reg_response = await message_broker.request(AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": f"researcher_liu_{unique_id}",
                "email": f"liu_{unique_id}@whu.edu.cn",
                "password": "password123"
            }
        ), timeout=10.0)
        user_id = reg_response.payload["user"]["id"]
        
        # Act - Add bio
        response = await message_broker.request(AgentMessage(
            type=MessageType.USER_UPDATE_PROFILE,
            sender="test",
            recipient="user_management_agent",
            payload={
                "user_id": user_id,
                "updates": {
                    "bio": "PhD candidate researching collaborative systems at Wuhan University"
                }
            }
        ), timeout=10.0)
        
        # Assert
        assert response.payload["success"] is True
        assert "collaborative systems" in response.payload["user"]["bio"]


# ==============================================================================
# JWT TOKEN TESTS
# ==============================================================================
# These tests verify our JWT implementation is secure and correct

class TestJWTTokens:
    """
    Tests for JWT (JSON Web Token) functionality.
    
    JWT is an industry standard for securely transmitting information.
    We use it to identify users without needing to query the database
    on every request (stateless authentication).
    
    A JWT contains:
    - Header: Algorithm used (HS256)
    - Payload: User data (id, username, expiration)
    - Signature: Ensures token wasn't tampered with
    """
    
    @pytest.mark.asyncio
    async def test_jwt_token_contains_correct_user_info(self, user_agent, message_broker):
        """
        SCENARIO: Verify JWT tokens contain the expected user information
        GIVEN: User logs in successfully
        WHEN: We decode their JWT token
        THEN: Token contains username and user ID
        
        This is important because we use these fields to identify users.
        """
        # Arrange - Register and login
        await message_broker.request(AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "token_test_user",
                "email": "token@whu.edu.cn",
                "password": "password123"
            }
        ), timeout=10.0)
        
        login_response = await message_broker.request(AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "token_test_user",
                "password": "password123"
            }
        ), timeout=10.0)
        token = login_response.payload["token"]
        
        # Act - Verify the token
        decoded_payload = user_agent.verify_token(token)
        
        # Assert
        assert decoded_payload is not None, "Token should be valid"
        assert decoded_payload["username"] == "token_test_user"
        assert "sub" in decoded_payload, "Should contain subject (user ID)"
        assert "exp" in decoded_payload, "Should contain expiration time"
        assert "iat" in decoded_payload, "Should contain issued-at time"
    
    @pytest.mark.asyncio
    async def test_invalid_token_is_rejected(self, user_agent, message_broker):
        """
        SCENARIO: Someone tries to use a fake or modified token
        GIVEN: An invalid JWT token
        WHEN: We try to verify it
        THEN: Verification fails (returns None)
        
        This is critical security - we must reject tampered tokens.
        """
        # Act - Try to verify a fake token
        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.FAKE.INVALID"
        result = user_agent.verify_token(fake_token)
        
        # Assert
        assert result is None, "Invalid token should be rejected"


# ==============================================================================
# EDGE CASES AND ERROR HANDLING
# ==============================================================================
# These tests verify the system handles unusual situations gracefully

class TestEdgeCases:
    """
    Tests for edge cases and error handling.
    
    Good software handles unexpected situations gracefully.
    These tests verify we don't crash or behave unexpectedly.
    """
    
    @pytest.mark.asyncio
    async def test_registration_with_empty_display_name_uses_username(self, user_agent, message_broker):
        """
        SCENARIO: User doesn't provide a display name
        GIVEN: Registration without display_name field
        WHEN: Registration completes
        THEN: Username is used as fallback display name
        """
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        
        # Arrange & Act
        response = await message_broker.request(AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": f"no_display_name_user_{unique_id}",
                "email": f"nodisplay_{unique_id}@whu.edu.cn",
                "password": "password123"
                # No display_name provided
            }
        ), timeout=10.0)
        
        # Assert - Should succeed, using username as fallback
        assert response.payload["success"] is True
    
    @pytest.mark.asyncio
    async def test_login_handles_empty_password_gracefully(self, user_agent, message_broker):
        """
        SCENARIO: Login form submits with empty password
        GIVEN: Registered user
        WHEN: Login attempted with empty password
        THEN: Login fails with appropriate error (doesn't crash)
        """
        # Arrange - Create user
        await message_broker.request(AgentMessage(
            type=MessageType.USER_REGISTER,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "empty_password_test",
                "email": "empty@whu.edu.cn",
                "password": "real_password"
            }
        ), timeout=10.0)
        
        # Act - Login with empty password
        response = await message_broker.request(AgentMessage(
            type=MessageType.USER_LOGIN,
            sender="test",
            recipient="user_management_agent",
            payload={
                "username": "empty_password_test",
                "password": ""  # Empty!
            }
        ), timeout=10.0)
        
        # Assert - Should fail gracefully
        assert response.payload["success"] is False


# ==============================================================================
# For the viva, be prepared to explain:
# 1. Why we use JWT for authentication
# 2. Why passwords are hashed (bcrypt) not encrypted
# 3. Why we don't tell users "wrong password" specifically
# 4. How the message broker routes messages to agents
# 5. Why each test is independent (doesn't rely on other tests)
# ==============================================================================
