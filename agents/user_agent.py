"""
User Management Agent - Handles Authentication and User Operations

================================================================================
DEVELOPED BY: Hasnain Ali | Wuhan University | Supervisor: Prof. Liang Peng
================================================================================

EXPLANATION FOR VIVA:
=====================
This agent is responsible for all user-related operations:
1. User Registration - Creating new accounts
2. User Authentication - Login/logout with JWT tokens
3. Profile Management - Viewing and updating user profiles

Agent Responsibilities (following Single Responsibility Principle):
- This agent ONLY handles user operations
- Document operations are handled by DocumentEditingAgent
- Version operations are handled by VersionControlAgent

Security Implementation:
- Passwords hashed with bcrypt (industry standard)
- JWT tokens for stateless authentication
- Token expiration for security

Why Agent-Based?
- Encapsulation: All user logic in one place
- Scalability: Can run on separate servers
- Testability: Easy to test in isolation
- Maintainability: Changes don't affect other agents
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import logging

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.agent_base import Agent, AgentMessage, MessageType
from core.event_bus import EventBus, Event, EventType
from models.database import get_session
from models.user import User

logger = logging.getLogger(__name__)

# Security configuration
import os
SECRET_KEY = os.getenv("SECRET_KEY", "your-super-secret-key-change-in-production-abc123xyz")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days (extended for demo/testing)


class UserManagementAgent(Agent):
    """
    Agent responsible for user management operations.
    
    EXPLANATION FOR VIVA:
    ====================
    This agent demonstrates the core agent-based architecture concepts:
    
    1. Message Handlers: Each operation has a dedicated handler method
    2. Async Operations: All database operations are async
    3. Event Publishing: User events are published for other components
    4. Error Handling: Comprehensive error handling with meaningful responses
    
    Operations Implemented (as required):
    1. User Registration (register_user)
    2. User Authentication (login_user, logout_user)
    3. Profile Management (get_profile, update_profile)
    
    Plus additional operations for completeness:
    4. Delete User (soft delete)
    5. Token Validation
    """
    
    def __init__(self):
        super().__init__(
            agent_id="user_management_agent",
            name="User Management Agent"
        )
        self.event_bus = EventBus()
        self._active_sessions: Dict[str, Dict] = {}  # Track active user sessions
        
        # Register message handlers
        self.register_handler(MessageType.USER_REGISTER, self._handle_register)
        self.register_handler(MessageType.USER_LOGIN, self._handle_login)
        self.register_handler(MessageType.USER_LOGOUT, self._handle_logout)
        self.register_handler(MessageType.USER_UPDATE_PROFILE, self._handle_update_profile)
        self.register_handler(MessageType.USER_GET_PROFILE, self._handle_get_profile)
        self.register_handler(MessageType.USER_DELETE, self._handle_delete_user)
    
    def get_capabilities(self) -> List[MessageType]:
        """Return the message types this agent can handle."""
        return [
            MessageType.USER_REGISTER,
            MessageType.USER_LOGIN,
            MessageType.USER_LOGOUT,
            MessageType.USER_UPDATE_PROFILE,
            MessageType.USER_GET_PROFILE,
            MessageType.USER_DELETE
        ]
    
    async def on_start(self):
        """Called when the agent starts."""
        logger.info(f"{self.name} started and ready to handle requests")
    
    async def on_stop(self):
        """Called when the agent stops."""
        logger.info(f"{self.name} stopping, clearing active sessions")
        self._active_sessions.clear()
    
    # ==================== PASSWORD UTILITIES ====================
    
    def _hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.
        
        EXPLANATION FOR VIVA:
        ====================
        Bcrypt is a key derivation function designed for passwords:
        1. Slow by design (prevents brute force)
        2. Includes salt (prevents rainbow table attacks)
        3. Configurable cost factor (can increase over time)
        
        The hash includes the salt, so we don't store it separately.
        
        We use bcrypt directly (not passlib) for better compatibility
        with newer Python and bcrypt library versions.
        """
        # Encode password to bytes, hash it, then decode back to string for storage
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    
    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        try:
            password_bytes = plain_password.encode('utf-8')
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    # ==================== JWT TOKEN UTILITIES ====================
    
    def _create_access_token(self, user_id: str, username: str) -> str:
        """
        Create a JWT access token.
        
        EXPLANATION FOR VIVA:
        ====================
        JWT (JSON Web Token) is a standard for stateless authentication:
        
        Structure: header.payload.signature
        - Header: Algorithm and token type
        - Payload: User data (claims) - user_id, username, expiration
        - Signature: Cryptographic signature to verify integrity
        
        Benefits:
        1. Stateless: Server doesn't need to store sessions
        2. Self-contained: All needed info is in the token
        3. Secure: Can't be tampered with (signature verification)
        
        The token is sent with each request in the Authorization header.
        """
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode = {
            "sub": user_id,  # Subject (standard claim)
            "username": username,
            "exp": expire,  # Expiration (standard claim)
            "iat": datetime.utcnow()  # Issued at (standard claim)
        }
        return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify and decode a JWT token.
        
        EXPLANATION FOR VIVA:
        ====================
        Returns the token payload if valid, None if invalid.
        
        Verification checks:
        1. Signature is valid (not tampered)
        2. Token hasn't expired
        3. Required claims are present
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"Token verification failed: {e}")
            return None
    
    # ==================== MESSAGE HANDLERS ====================
    
    async def _handle_register(self, message: AgentMessage) -> AgentMessage:
        """
        Handle user registration.
        
        EXPLANATION FOR VIVA:
        ====================
        Registration flow:
        1. Validate input (username, email, password)
        2. Check for existing user (prevent duplicates)
        3. Hash password (NEVER store plain text)
        4. Create user in database
        5. Publish event (for real-time updates)
        6. Return success with user data (no password!)
        
        This demonstrates:
        - Input validation
        - Database transaction
        - Event publishing
        - Proper error handling
        """
        payload = message.payload
        
        # Input validation
        username = payload.get("username", "").strip()
        email = payload.get("email", "").strip().lower()
        password = payload.get("password", "")
        display_name = payload.get("display_name", "").strip()
        
        if not username or len(username) < 3:
            return message.create_response(
                {"success": False, "error": "Username must be at least 3 characters"},
                success=False
            )
        
        if not email or "@" not in email:
            return message.create_response(
                {"success": False, "error": "Valid email is required"},
                success=False
            )
        
        if not password or len(password) < 6:
            return message.create_response(
                {"success": False, "error": "Password must be at least 6 characters"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                # Check for existing user
                result = await session.execute(
                    select(User).where(
                        (User.username == username) | (User.email == email)
                    )
                )
                existing_user = result.scalar_one_or_none()
                
                if existing_user:
                    if existing_user.username == username:
                        return message.create_response(
                            {"success": False, "error": "Username already taken"},
                            success=False
                        )
                    else:
                        return message.create_response(
                            {"success": False, "error": "Email already registered"},
                            success=False
                        )
                
                # Create new user
                new_user = User(
                    username=username,
                    email=email,
                    password_hash=self._hash_password(password),
                    display_name=display_name or username
                )
                
                session.add(new_user)
                await session.commit()
                await session.refresh(new_user)
                
                logger.info(f"User registered: {username}")
                
                # Publish event
                await self.event_bus.publish(Event(
                    event_type=EventType.USER_JOINED,
                    data={"user": new_user.to_public_dict()},
                    user_id=new_user.id
                ))
                
                return message.create_response({
                    "success": True,
                    "user": new_user.to_dict(include_sensitive=True),
                    "message": "Registration successful"
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return message.create_response(
                {"success": False, "error": f"Registration failed: {str(e)}"},
                success=False
            )
    
    async def _handle_login(self, message: AgentMessage) -> AgentMessage:
        """
        Handle user login.
        
        EXPLANATION FOR VIVA:
        ====================
        Login flow:
        1. Find user by username or email
        2. Verify password against hash
        3. Generate JWT token
        4. Update last_login timestamp
        5. Track session (for logout/monitoring)
        6. Publish event
        
        Security considerations:
        - Generic error message (don't reveal if user exists)
        - Password verified with timing-safe comparison
        - Token has expiration
        """
        payload = message.payload
        
        username_or_email = payload.get("username", "").strip()
        password = payload.get("password", "")
        
        if not username_or_email or not password:
            return message.create_response(
                {"success": False, "error": "Username/email and password required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                # Find user by username or email
                result = await session.execute(
                    select(User).where(
                        (User.username == username_or_email) | 
                        (User.email == username_or_email.lower())
                    )
                )
                user = result.scalar_one_or_none()
                
                # Generic error to prevent user enumeration
                if not user or not self._verify_password(password, user.password_hash):
                    return message.create_response(
                        {"success": False, "error": "Invalid credentials"},
                        success=False
                    )
                
                if not user.is_active:
                    return message.create_response(
                        {"success": False, "error": "Account is deactivated"},
                        success=False
                    )
                
                # Update last login
                user.last_login = datetime.utcnow()
                await session.commit()
                
                # Generate token
                token = self._create_access_token(user.id, user.username)
                
                # Track session
                self._active_sessions[user.id] = {
                    "username": user.username,
                    "login_time": datetime.utcnow().isoformat()
                }
                
                logger.info(f"User logged in: {user.username}")
                
                # Publish event
                await self.event_bus.publish(Event(
                    event_type=EventType.USER_JOINED,
                    data={"user": user.to_public_dict()},
                    user_id=user.id
                ))
                
                return message.create_response({
                    "success": True,
                    "token": token,
                    "user": user.to_dict(include_sensitive=True),
                    "message": "Login successful"
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return message.create_response(
                {"success": False, "error": f"Login failed: {str(e)}"},
                success=False
            )
    
    async def _handle_logout(self, message: AgentMessage) -> AgentMessage:
        """
        Handle user logout.
        
        EXPLANATION FOR VIVA:
        ====================
        With JWT, true "logout" is challenging because tokens are stateless.
        Options:
        1. Client deletes token (what we do + track sessions)
        2. Token blacklist (requires storage)
        3. Short token expiry + refresh tokens
        
        We track active sessions to know who's online.
        """
        payload = message.payload
        user_id = payload.get("user_id")
        
        if user_id and user_id in self._active_sessions:
            username = self._active_sessions[user_id].get("username", "Unknown")
            del self._active_sessions[user_id]
            
            logger.info(f"User logged out: {username}")
            
            # Publish event
            await self.event_bus.publish(Event(
                event_type=EventType.USER_LEFT,
                data={"user_id": user_id},
                user_id=user_id
            ))
        
        return message.create_response({
            "success": True,
            "message": "Logged out successfully"
        })
    
    async def _handle_get_profile(self, message: AgentMessage) -> AgentMessage:
        """
        Handle get user profile request.
        
        EXPLANATION FOR VIVA:
        ====================
        Two modes:
        1. Own profile: Include sensitive data (email, etc.)
        2. Other user's profile: Public data only
        
        This is authorization - controlling what data is visible.
        """
        payload = message.payload
        user_id = payload.get("user_id")
        requesting_user_id = payload.get("requesting_user_id")
        
        if not user_id:
            return message.create_response(
                {"success": False, "error": "User ID required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return message.create_response(
                        {"success": False, "error": "User not found"},
                        success=False
                    )
                
                # Include sensitive data only for own profile
                is_own_profile = requesting_user_id == user_id
                
                return message.create_response({
                    "success": True,
                    "user": user.to_dict(include_sensitive=is_own_profile)
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Get profile error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_update_profile(self, message: AgentMessage) -> AgentMessage:
        """
        Handle profile update request.
        
        EXPLANATION FOR VIVA:
        ====================
        Update flow:
        1. Verify user exists
        2. Validate new data
        3. Check for conflicts (email uniqueness)
        4. Update database
        5. Publish event
        
        Only certain fields can be updated (not username, password here).
        Password change would be a separate operation with additional verification.
        """
        payload = message.payload
        user_id = payload.get("user_id")
        updates = payload.get("updates", {})
        
        if not user_id:
            return message.create_response(
                {"success": False, "error": "User ID required"},
                success=False
            )
        
        # Allowed fields to update
        allowed_fields = {"display_name", "bio", "avatar_url", "email"}
        update_data = {k: v for k, v in updates.items() if k in allowed_fields}
        
        if not update_data:
            return message.create_response(
                {"success": False, "error": "No valid fields to update"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return message.create_response(
                        {"success": False, "error": "User not found"},
                        success=False
                    )
                
                # Check email uniqueness if changing email
                if "email" in update_data and update_data["email"] != user.email:
                    email_check = await session.execute(
                        select(User).where(User.email == update_data["email"].lower())
                    )
                    if email_check.scalar_one_or_none():
                        return message.create_response(
                            {"success": False, "error": "Email already in use"},
                            success=False
                        )
                    update_data["email"] = update_data["email"].lower()
                
                # Apply updates
                for key, value in update_data.items():
                    setattr(user, key, value)
                
                user.updated_at = datetime.utcnow()
                await session.commit()
                await session.refresh(user)
                
                logger.info(f"Profile updated: {user.username}")
                
                # Publish event
                await self.event_bus.publish(Event(
                    event_type=EventType.USER_UPDATED,
                    data={"user": user.to_public_dict()},
                    user_id=user.id
                ))
                
                return message.create_response({
                    "success": True,
                    "user": user.to_dict(include_sensitive=True),
                    "message": "Profile updated successfully"
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Update profile error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    async def _handle_delete_user(self, message: AgentMessage) -> AgentMessage:
        """
        Handle user deletion (soft delete).
        
        EXPLANATION FOR VIVA:
        ====================
        Soft delete means we don't actually remove the data.
        Instead, we set is_active = False.
        
        Benefits:
        1. Recovery possible if mistake
        2. Maintains data integrity (foreign keys)
        3. Audit trail preserved
        
        For GDPR compliance, you'd need a separate hard delete process
        that anonymizes/removes personal data after a retention period.
        """
        payload = message.payload
        user_id = payload.get("user_id")
        
        if not user_id:
            return message.create_response(
                {"success": False, "error": "User ID required"},
                success=False
            )
        
        try:
            session: AsyncSession = await get_session()
            
            try:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return message.create_response(
                        {"success": False, "error": "User not found"},
                        success=False
                    )
                
                # Soft delete
                user.is_active = False
                user.updated_at = datetime.utcnow()
                await session.commit()
                
                # Remove from active sessions
                if user_id in self._active_sessions:
                    del self._active_sessions[user_id]
                
                logger.info(f"User deactivated: {user.username}")
                
                return message.create_response({
                    "success": True,
                    "message": "Account deactivated successfully"
                })
                
            finally:
                await session.close()
                
        except Exception as e:
            logger.error(f"Delete user error: {e}")
            return message.create_response(
                {"success": False, "error": str(e)},
                success=False
            )
    
    # ==================== UTILITY METHODS ====================
    
    def get_active_sessions(self) -> Dict[str, Dict]:
        """Get all active user sessions."""
        return self._active_sessions.copy()
    
    def is_user_online(self, user_id: str) -> bool:
        """Check if a user is currently logged in."""
        return user_id in self._active_sessions
