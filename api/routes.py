"""
API Routes - FastAPI REST Endpoints

EXPLANATION FOR VIVA:
=====================
This module defines REST API endpoints that act as a gateway to our agents.

API Gateway Pattern:
- Single entry point for all client requests
- Routes requests to appropriate agents
- Handles authentication, validation, rate limiting
- Transforms agent responses to HTTP responses

REST API Design:
- Stateless: Each request contains all info needed
- Resource-based: URLs represent resources (users, documents, versions)
- HTTP Methods: GET (read), POST (create), PUT (update), DELETE (delete)
- Status Codes: 200 OK, 201 Created, 400 Bad Request, 401 Unauthorized, etc.

Request Flow:
1. Client sends HTTP request
2. FastAPI validates request (Pydantic schemas)
3. Route handler creates AgentMessage
4. Message sent to appropriate agent via MessageBroker
5. Agent processes and returns response
6. Route handler converts to HTTP response

This decouples the API layer from business logic (agents).
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
import logging

from core.agent_base import AgentMessage, MessageType
from core.message_broker import MessageBroker

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Security scheme
security = HTTPBearer(auto_error=False)


# ==================== PYDANTIC SCHEMAS ====================
# These define the structure of request/response bodies

class UserRegisterRequest(BaseModel):
    """
    Schema for user registration.
    
    EXPLANATION FOR VIVA:
    ====================
    Pydantic provides:
    1. Data validation (email format, min length)
    2. Automatic documentation (OpenAPI/Swagger)
    3. Serialization/deserialization
    
    Field() adds extra validation and documentation.
    """
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    display_name: Optional[str] = None


class UserLoginRequest(BaseModel):
    """Schema for user login."""
    username: str  # Can be username or email
    password: str


class UserUpdateRequest(BaseModel):
    """Schema for profile updates."""
    display_name: Optional[str] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    email: Optional[EmailStr] = None


class DocumentCreateRequest(BaseModel):
    """Schema for document creation."""
    title: str = Field(default="Untitled Document", max_length=255)
    content: str = ""
    is_public: bool = False


class DocumentUpdateRequest(BaseModel):
    """Schema for document updates."""
    title: Optional[str] = None
    content: Optional[str] = None
    create_version: bool = False
    change_summary: Optional[str] = None


class CollaborateRequest(BaseModel):
    """Schema for collaboration actions."""
    action: str = Field(..., pattern="^(join|leave|update_cursor)$")
    cursor_position: int = 0


class TrackChangeRequest(BaseModel):
    """Schema for tracking real-time changes."""
    change_type: str = Field(..., pattern="^(insert|delete|replace)$")
    position: int
    content: str = ""
    length: int = 0


class RevertRequest(BaseModel):
    """Schema for version revert."""
    version_id: Optional[str] = None
    version_number: Optional[int] = None


class CompareRequest(BaseModel):
    """Schema for version comparison."""
    version1: str  # Version number or "current"
    version2: str
    format: str = Field(default="unified", pattern="^(unified|html|stats)$")


# ==================== HELPER FUNCTIONS ====================

def get_broker() -> MessageBroker:
    """Get the message broker instance."""
    return MessageBroker()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[dict]:
    """
    Extract and validate user from JWT token.
    
    EXPLANATION FOR VIVA:
    ====================
    This is a Dependency Injection function.
    FastAPI calls it automatically for protected routes.
    
    Process:
    1. Extract token from Authorization header
    2. Validate token signature and expiration
    3. Return user info if valid, None if not
    
    Routes can make this required or optional:
    - Required: Depends(get_current_user) raises 401 if not authenticated
    - Optional: Returns None if not authenticated
    """
    if not credentials:
        return None
    
    from agents.user_agent import UserManagementAgent
    
    # Create a temporary agent to verify token
    agent = UserManagementAgent()
    payload = agent.verify_token(credentials.credentials)
    
    if payload:
        return {
            "user_id": payload.get("sub"),
            "username": payload.get("username")
        }
    return None


def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    """Require authentication - raises 401 if not authenticated."""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


# ==================== USER ROUTES ====================

@router.post("/users/register", tags=["Users"])
async def register_user(request: UserRegisterRequest):
    """
    Register a new user.
    
    EXPLANATION FOR VIVA:
    ====================
    This endpoint demonstrates the Request -> Agent -> Response flow:
    
    1. FastAPI validates request body (Pydantic)
    2. Create AgentMessage with registration data
    3. Send to MessageBroker for routing
    4. UserManagementAgent processes it
    5. Return response to client
    
    Status codes:
    - 201: Created successfully
    - 400: Validation error
    - 409: Username/email already exists
    """
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.USER_REGISTER,
        sender="api_gateway",
        recipient="user_management_agent",
        payload={
            "username": request.username,
            "email": request.email,
            "password": request.password,
            "display_name": request.display_name
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=response.payload.get("error", "Registration failed")
        )
    
    return response.payload


@router.post("/users/login", tags=["Users"])
async def login_user(request: UserLoginRequest):
    """
    Authenticate user and return JWT token.
    
    EXPLANATION FOR VIVA:
    ====================
    Login returns a JWT token that the client must include
    in subsequent requests in the Authorization header:
    
    Authorization: Bearer <token>
    
    The token contains user_id and expires after 24 hours.
    """
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.USER_LOGIN,
        sender="api_gateway",
        recipient="user_management_agent",
        payload={
            "username": request.username,
            "password": request.password
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=401, 
            detail=response.payload.get("error", "Login failed")
        )
    
    return response.payload


@router.post("/users/logout", tags=["Users"])
async def logout_user(user: dict = Depends(require_auth)):
    """Logout the current user."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.USER_LOGOUT,
        sender="api_gateway",
        recipient="user_management_agent",
        payload={"user_id": user["user_id"]}
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    return response.payload


@router.get("/users/me", tags=["Users"])
async def get_current_user_profile(user: dict = Depends(require_auth)):
    """Get the current user's profile."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.USER_GET_PROFILE,
        sender="api_gateway",
        recipient="user_management_agent",
        payload={
            "user_id": user["user_id"],
            "requesting_user_id": user["user_id"]
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=404, 
            detail=response.payload.get("error", "User not found")
        )
    
    return response.payload


@router.get("/users/{user_id}", tags=["Users"])
async def get_user_profile(
    user_id: str, 
    current_user: Optional[dict] = Depends(get_current_user)
):
    """Get a user's public profile."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.USER_GET_PROFILE,
        sender="api_gateway",
        recipient="user_management_agent",
        payload={
            "user_id": user_id,
            "requesting_user_id": current_user["user_id"] if current_user else None
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=404, 
            detail=response.payload.get("error", "User not found")
        )
    
    return response.payload


@router.put("/users/me", tags=["Users"])
async def update_current_user_profile(
    request: UserUpdateRequest,
    user: dict = Depends(require_auth)
):
    """Update the current user's profile."""
    broker = get_broker()
    
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    
    message = AgentMessage(
        type=MessageType.USER_UPDATE_PROFILE,
        sender="api_gateway",
        recipient="user_management_agent",
        payload={
            "user_id": user["user_id"],
            "updates": updates
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=response.payload.get("error", "Update failed")
        )
    
    return response.payload


# ==================== DOCUMENT ROUTES ====================

@router.post("/documents", tags=["Documents"])
async def create_document(
    request: DocumentCreateRequest,
    user: dict = Depends(require_auth)
):
    """
    Create a new document.
    
    EXPLANATION FOR VIVA:
    ====================
    Document creation:
    1. User must be authenticated (require_auth)
    2. Validates request (Pydantic)
    3. Sends to DocumentEditingAgent
    4. Agent creates document and initial version
    5. Returns document data
    """
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.DOC_CREATE,
        sender="api_gateway",
        recipient="document_editing_agent",
        payload={
            "user_id": user["user_id"],
            "title": request.title,
            "content": request.content,
            "is_public": request.is_public
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=response.payload.get("error", "Creation failed")
        )
    
    return response.payload


@router.get("/documents", tags=["Documents"])
async def list_documents(
    include_public: bool = False,
    limit: int = 50,
    offset: int = 0,
    user: Optional[dict] = Depends(get_current_user)
):
    """List documents accessible to the current user."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.DOC_LIST,
        sender="api_gateway",
        recipient="document_editing_agent",
        payload={
            "user_id": user["user_id"] if user else None,
            "include_public": include_public,
            "limit": limit,
            "offset": offset
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    return response.payload


@router.get("/documents/{document_id}", tags=["Documents"])
async def get_document(
    document_id: str,
    user: Optional[dict] = Depends(get_current_user)
):
    """Get a document by ID."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.DOC_READ,
        sender="api_gateway",
        recipient="document_editing_agent",
        payload={
            "document_id": document_id,
            "user_id": user["user_id"] if user else None
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=404, 
            detail=response.payload.get("error", "Document not found")
        )
    
    return response.payload


@router.put("/documents/{document_id}", tags=["Documents"])
async def update_document(
    document_id: str,
    request: DocumentUpdateRequest,
    user: dict = Depends(require_auth)
):
    """Update a document."""
    broker = get_broker()
    
    payload = {
        "document_id": document_id,
        "user_id": user["user_id"],
        "create_version": request.create_version
    }
    
    if request.title is not None:
        payload["title"] = request.title
    if request.content is not None:
        payload["content"] = request.content
    if request.change_summary:
        payload["change_summary"] = request.change_summary
    
    message = AgentMessage(
        type=MessageType.DOC_UPDATE,
        sender="api_gateway",
        recipient="document_editing_agent",
        payload=payload
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=response.payload.get("error", "Update failed")
        )
    
    return response.payload


@router.delete("/documents/{document_id}", tags=["Documents"])
async def delete_document(
    document_id: str,
    user: dict = Depends(require_auth)
):
    """Delete a document (soft delete)."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.DOC_DELETE,
        sender="api_gateway",
        recipient="document_editing_agent",
        payload={
            "document_id": document_id,
            "user_id": user["user_id"]
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=response.payload.get("error", "Delete failed")
        )
    
    return response.payload


@router.post("/documents/{document_id}/collaborate", tags=["Documents"])
async def collaborate_on_document(
    document_id: str,
    request: CollaborateRequest,
    user: dict = Depends(require_auth)
):
    """Join/leave editing session or update cursor position."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.DOC_COLLABORATE,
        sender="api_gateway",
        recipient="document_editing_agent",
        payload={
            "document_id": document_id,
            "user_id": user["user_id"],
            "action": request.action,
            "cursor_position": request.cursor_position
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    return response.payload


@router.post("/documents/{document_id}/changes", tags=["Documents"])
async def track_document_change(
    document_id: str,
    request: TrackChangeRequest,
    user: dict = Depends(require_auth)
):
    """Track a real-time change for broadcasting."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.DOC_TRACK_CHANGE,
        sender="api_gateway",
        recipient="document_editing_agent",
        payload={
            "document_id": document_id,
            "user_id": user["user_id"],
            "change_type": request.change_type,
            "position": request.position,
            "content": request.content,
            "length": request.length
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    return response.payload


# ==================== VERSION CONTROL ROUTES ====================

@router.get("/documents/{document_id}/versions", tags=["Versions"])
async def get_document_versions(
    document_id: str,
    limit: int = 50,
    include_content: bool = False,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Get version history for a document.
    
    EXPLANATION FOR VIVA:
    ====================
    Returns list of versions with metadata.
    Content excluded by default for performance.
    """
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.VERSION_GET_HISTORY,
        sender="api_gateway",
        recipient="version_control_agent",
        payload={
            "document_id": document_id,
            "user_id": user["user_id"] if user else None,
            "limit": limit,
            "include_content": include_content
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=404, 
            detail=response.payload.get("error", "Not found")
        )
    
    return response.payload


@router.post("/documents/{document_id}/versions", tags=["Versions"])
async def create_document_version(
    document_id: str,
    change_summary: Optional[str] = None,
    user: dict = Depends(require_auth)
):
    """Create a new version of the document."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.VERSION_CREATE,
        sender="api_gateway",
        recipient="version_control_agent",
        payload={
            "document_id": document_id,
            "user_id": user["user_id"],
            "change_summary": change_summary or "Manual save"
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=response.payload.get("error", "Version creation failed")
        )
    
    return response.payload


@router.post("/documents/{document_id}/revert", tags=["Versions"])
async def revert_document(
    document_id: str,
    request: RevertRequest,
    user: dict = Depends(require_auth)
):
    """
    Revert document to a previous version.
    
    EXPLANATION FOR VIVA:
    ====================
    This is a destructive operation (changes current content).
    Requires edit permission.
    Creates a new version to track the revert.
    """
    broker = get_broker()
    
    if not request.version_id and not request.version_number:
        raise HTTPException(
            status_code=400, 
            detail="Either version_id or version_number required"
        )
    
    message = AgentMessage(
        type=MessageType.VERSION_REVERT,
        sender="api_gateway",
        recipient="version_control_agent",
        payload={
            "document_id": document_id,
            "user_id": user["user_id"],
            "version_id": request.version_id,
            "version_number": request.version_number
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=response.payload.get("error", "Revert failed")
        )
    
    return response.payload


@router.post("/documents/{document_id}/compare", tags=["Versions"])
async def compare_versions(
    document_id: str,
    request: CompareRequest,
    user: Optional[dict] = Depends(get_current_user)
):
    """Compare two versions of a document."""
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.VERSION_COMPARE,
        sender="api_gateway",
        recipient="version_control_agent",
        payload={
            "document_id": document_id,
            "version1": request.version1,
            "version2": request.version2,
            "format": request.format
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    if response.type == MessageType.ERROR or not response.payload.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=response.payload.get("error", "Compare failed")
        )
    
    return response.payload


@router.get("/documents/{document_id}/contributions", tags=["Versions"])
async def get_document_contributions(
    document_id: str,
    user_id: Optional[str] = None,
    user: Optional[dict] = Depends(get_current_user)
):
    """
    Get contribution statistics for a document.
    
    EXPLANATION FOR VIVA:
    ====================
    Shows who contributed what to the document.
    Can filter for a specific user.
    """
    broker = get_broker()
    
    message = AgentMessage(
        type=MessageType.VERSION_GET_CONTRIBUTIONS,
        sender="api_gateway",
        recipient="version_control_agent",
        payload={
            "document_id": document_id,
            "user_id": user_id
        }
    )
    
    response = await broker.request(message, timeout=30.0)
    
    if not response:
        raise HTTPException(status_code=500, detail="Request timeout")
    
    return response.payload


# ==================== SYSTEM ROUTES ====================

@router.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint.
    
    EXPLANATION FOR VIVA:
    ====================
    Used by load balancers and monitoring systems to check if the service is running.
    Returns broker statistics for debugging.
    """
    broker = get_broker()
    return {
        "status": "healthy",
        "broker_stats": broker.get_stats()
    }
