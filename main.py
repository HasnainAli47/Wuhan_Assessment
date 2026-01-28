"""
Main Application Entry Point

================================================================================
COLLABORATIVE EDITING SYSTEM - Agent-Based Architecture
================================================================================
Developed by: Hasnain Ali
Institution:  Wuhan University
Supervisor:   Professor Liang Peng
Date:         January 2026
================================================================================

EXPLANATION FOR VIVA:
=====================
This is the entry point of the entire application. It:

1. Creates the FastAPI application
2. Initializes the database
3. Creates and starts all agents
4. Sets up the MessageBroker
5. Mounts routes and static files
6. Handles application lifecycle (startup/shutdown)

Application Architecture Summary:
================================
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Browser)                         │
│                    (HTML/CSS/JS Frontend)                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │ HTTP REST        │ WebSocket        │
          ▼                  ▼                  │
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ REST Routes │  │  WebSocket  │  │    Static Files         │  │
│  │ (api/routes)│  │  Manager    │  │    (HTML, CSS, JS)      │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────────┘  │
└─────────┼────────────────┼──────────────────────────────────────┘
          │                │
          ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Message Broker                              │
│                  (Central Communication Hub)                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
     ┌───────────────────────┼───────────────────────┐
     │                       │                       │
     ▼                       ▼                       ▼
┌────────────┐        ┌────────────┐        ┌────────────┐
│   User     │        │  Document  │        │  Version   │
│ Management │        │  Editing   │        │  Control   │
│   Agent    │        │   Agent    │        │   Agent    │
└─────┬──────┘        └─────┬──────┘        └─────┬──────┘
      │                     │                     │
      └─────────────────────┴─────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │    Database     │
                   │   (SQLite)      │
                   └─────────────────┘

Communication Flow:
1. Client sends HTTP request or WebSocket message
2. FastAPI routes request to appropriate handler
3. Handler creates AgentMessage
4. MessageBroker routes message to appropriate agent
5. Agent processes message, interacts with database
6. Response flows back through same path
7. For real-time: EventBus publishes events, WebSocketManager broadcasts
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from core.message_broker import MessageBroker
from core.event_bus import EventBus
from agents.user_agent import UserManagementAgent
from agents.document_agent import DocumentEditingAgent
from agents.version_agent import VersionControlAgent
from api.routes import router
from api.websocket import websocket_endpoint, WebSocketManager
from models.database import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global instances
message_broker = None
agents = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    EXPLANATION FOR VIVA:
    ====================
    This handles startup and shutdown:
    
    Startup:
    1. Initialize database (create tables)
    2. Create agent instances
    3. Register agents with broker
    4. Start agents (begin processing messages)
    
    Shutdown:
    1. Stop all agents (graceful shutdown)
    2. Clean up resources
    
    The @asynccontextmanager decorator with yield creates a context:
    - Code before yield runs at startup
    - Code after yield runs at shutdown
    
    This ensures proper cleanup even if the application crashes.
    """
    global message_broker, agents
    
    logger.info("Starting Collaborative Editing System...")
    
    # Initialize database
    logger.info("Initializing database...")
    await init_db()
    
    # Create message broker
    message_broker = MessageBroker()
    
    # Create agents
    logger.info("Creating agents...")
    user_agent = UserManagementAgent()
    document_agent = DocumentEditingAgent()
    version_agent = VersionControlAgent()
    
    agents = [user_agent, document_agent, version_agent]
    
    # Register agents with broker
    logger.info("Registering agents with message broker...")
    for agent in agents:
        message_broker.register_agent(agent)
    
    # Start all agents
    logger.info("Starting agents...")
    await message_broker.start_all_agents()
    
    # Initialize WebSocket manager singleton at startup
    from api.websocket import WebSocketManager
    ws_manager = WebSocketManager()
    logger.info(f"WebSocketManager initialized with id: {id(ws_manager)}")
    
    logger.info("Collaborative Editing System is ready!")
    logger.info("Access the application at: http://localhost:8000")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("Shutting down Collaborative Editing System...")
    await message_broker.stop_all_agents()
    logger.info("Shutdown complete.")


# Create FastAPI application
app = FastAPI(
    title="Collaborative Editing System",
    description="""
    An agent-based collaborative document editing system.
    
    ## Features
    - User Management: Registration, authentication, profiles
    - Document Editing: Create, edit, real-time collaboration
    - Version Control: History, revert, contribution tracking
    
    ## Architecture
    Built with an agent-based architecture where specialized agents
    handle different domains (users, documents, versions).
    """,
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
# This allows the frontend to make requests to the API
# In production, set ALLOWED_ORIGINS environment variable
import os
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")


# ==================== WEBSOCKET ENDPOINT ====================

@app.websocket("/ws")
async def websocket_route(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket connection endpoint.
    
    EXPLANATION FOR VIVA:
    ====================
    WebSocket connections are authenticated via query parameter.
    
    Example: ws://localhost:8000/ws?token=<jwt_token>
    
    Process:
    1. Extract token from query
    2. Validate token to get user info
    3. Establish WebSocket connection
    4. Handle messages until disconnect
    """
    # Validate token
    user_agent = UserManagementAgent()
    payload = user_agent.verify_token(token)
    
    if not payload:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    user_id = payload.get("sub")
    username = payload.get("username")
    
    # Handle WebSocket connection
    await websocket_endpoint(websocket, user_id, username)


# ==================== STATIC FILES ====================

# Serve static files (HTML, CSS, JS)
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.get("/")
async def root():
    """
    Serve the main application page.
    
    EXPLANATION FOR VIVA:
    ====================
    This serves the single-page application (SPA) HTML file.
    The frontend is a single HTML file with embedded CSS and JS.
    """
    index_path = static_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "Welcome to Collaborative Editing System API"}


# ==================== MAIN ====================

if __name__ == "__main__":
    """
    Run the application.
    
    EXPLANATION FOR VIVA:
    ====================
    uvicorn is an ASGI server that runs FastAPI applications.
    
    ASGI (Asynchronous Server Gateway Interface):
    - Python standard for async web servers
    - Successor to WSGI
    - Supports WebSockets natively
    
    Options:
    - host: "0.0.0.0" allows external connections
    - port: 8000 is the default
    - reload: True enables auto-reload during development
    """
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
