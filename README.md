# Collaborative Editing System - Agent-Based Architecture

A real-time collaborative document editing system built using an **agent-based architecture** in Python.

## Table of Contents

1. [Overview](#overview)
2. [Architecture Explained](#architecture-explained)
3. [Agent Design](#agent-design)
4. [Running the Application](#running-the-application)
5. [API Documentation](#api-documentation)
6. [Testing](#testing)
7. [Key Concepts for Viva](#key-concepts-for-viva)

---

## Overview

This system implements a collaborative editing platform similar to Google Docs or Overleaf, using an agent-based approach instead of traditional microservices.

### Features

- **User Management**: Registration, authentication (JWT), profile management
- **Document Editing**: Create, edit, delete documents with real-time collaboration
- **Version Control**: Complete version history, revert capability, contribution tracking
- **Real-time Updates**: WebSocket-based live collaboration

### Technology Stack

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy
- **Database**: SQLite (easily switchable to PostgreSQL)
- **Authentication**: JWT (JSON Web Tokens)
- **Real-time**: WebSockets
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Testing**: pytest, pytest-asyncio

---

## Architecture Explained

### Why Agent-Based vs Microservices?

| Aspect | Agent-Based | Microservices |
|--------|------------|---------------|
| Communication | Message passing | HTTP/REST APIs |
| Coupling | Loose via broker | Loose via APIs |
| State | Each agent has own state | Each service has own DB |
| Scaling | Add more agents | Add more containers |
| Complexity | Simpler for our use case | Better for large teams |

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Client (Browser)                          │
│                 HTML/CSS/JavaScript UI                       │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │ HTTP/REST     │ WebSocket     │
          ▼               ▼               │
┌─────────────────────────────────────────────────────────────┐
│                   FastAPI Application                        │
│    ┌──────────────┐  ┌───────────────┐  ┌────────────────┐  │
│    │  API Routes  │  │  WebSocket    │  │ Static Files   │  │
│    │  (Gateway)   │  │  Manager      │  │ (UI)           │  │
│    └──────┬───────┘  └───────┬───────┘  └────────────────┘  │
└───────────┼──────────────────┼──────────────────────────────┘
            │                  │
            ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    Message Broker                            │
│              (Central Communication Hub)                     │
│                                                              │
│   Responsibilities:                                          │
│   • Route messages to correct agent                          │
│   • Handle request-response correlation                      │
│   • Broadcast messages when needed                           │
└─────────────────────────┬───────────────────────────────────┘
                          │
     ┌────────────────────┼────────────────────┐
     │                    │                    │
     ▼                    ▼                    ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    User     │    │  Document   │    │  Version    │
│ Management  │    │   Editing   │    │  Control    │
│   Agent     │    │    Agent    │    │   Agent     │
│             │    │             │    │             │
│ Operations: │    │ Operations: │    │ Operations: │
│ • Register  │    │ • Create    │    │ • Create    │
│ • Login     │    │ • Edit      │    │ • History   │
│ • Logout    │    │ • Track     │    │ • Revert    │
│ • Profile   │    │ • Collab    │    │ • Compare   │
│ • Delete    │    │ • Delete    │    │ • Contrib   │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       └──────────────────┴──────────────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │    Database     │
                 │   (SQLite)      │
                 │                 │
                 │  Tables:        │
                 │  • users        │
                 │  • documents    │
                 │  • versions     │
                 │  • changes      │
                 └─────────────────┘
```

### Communication Flow

1. **Client → API Gateway**: HTTP requests or WebSocket messages
2. **API Gateway → Message Broker**: Converts to AgentMessage
3. **Message Broker → Agent**: Routes to appropriate agent
4. **Agent → Database**: Performs operations
5. **Agent → Message Broker**: Returns response
6. **Message Broker → API Gateway**: Forwards response
7. **API Gateway → Client**: HTTP response or WebSocket message

---

## Agent Design

### Base Agent Class

```python
class Agent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self._message_queue = asyncio.Queue()
        self._handlers = {}  # MessageType -> Handler function
    
    def register_handler(self, message_type, handler):
        """Register a function to handle a message type"""
        self._handlers[message_type] = handler
    
    async def receive_message(self, message):
        """Add message to queue for processing"""
        await self._message_queue.put(message)
    
    async def _process_messages(self):
        """Main loop - process messages from queue"""
        while self._running:
            message = await self._message_queue.get()
            handler = self._handlers.get(message.type)
            if handler:
                await handler(message)
```

### Agent Message Structure

```python
@dataclass
class AgentMessage:
    type: MessageType       # What operation (USER_LOGIN, DOC_CREATE, etc.)
    sender: str            # Who sent it
    recipient: str         # Who should receive it
    payload: Dict          # The actual data
    id: str               # Unique identifier
    correlation_id: str   # Links response to request
    timestamp: datetime   # When created
```

### The Three Agents

#### 1. User Management Agent
**Responsibility**: Handle all user-related operations

| Operation | Message Type | Description |
|-----------|--------------|-------------|
| Register | USER_REGISTER | Create new user account |
| Login | USER_LOGIN | Authenticate and return JWT |
| Logout | USER_LOGOUT | End user session |
| Get Profile | USER_GET_PROFILE | Retrieve user information |
| Update Profile | USER_UPDATE_PROFILE | Modify user data |
| Delete | USER_DELETE | Soft delete account |

#### 2. Document Editing Agent
**Responsibility**: Handle document CRUD and collaboration

| Operation | Message Type | Description |
|-----------|--------------|-------------|
| Create | DOC_CREATE | Create new document |
| Read | DOC_READ | Get document content |
| Update | DOC_UPDATE | Modify document |
| Delete | DOC_DELETE | Soft delete document |
| Collaborate | DOC_COLLABORATE | Join/leave editing session |
| Track Change | DOC_TRACK_CHANGE | Real-time change broadcast |

#### 3. Version Control Agent
**Responsibility**: Handle versioning and history

| Operation | Message Type | Description |
|-----------|--------------|-------------|
| Create Version | VERSION_CREATE | Save document snapshot |
| Get History | VERSION_GET_HISTORY | List all versions |
| Revert | VERSION_REVERT | Restore previous version |
| Compare | VERSION_COMPARE | Diff between versions |
| Get Contributions | VERSION_GET_CONTRIBUTIONS | User contribution stats |

---

## Running the Application

### Prerequisites

- Python 3.9 or higher
- Node.js 16+ and npm (for React frontend)
- pip (Python package manager)

### Backend Setup

```bash
# 1. Navigate to project directory
cd "Wuhun University Assessment"

# 2. Create virtual environment (recommended)
python -m venv venv

# 3. Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the backend server
python main.py
```

### Frontend Setup (React)

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start development server
npm start
```

### Access the Application

**Option 1: React Frontend (Recommended)**
- **React App**: http://localhost:3000 (development server)
- Backend API proxied automatically to port 8000

**Option 2: Simple HTML UI**
- **Web UI**: http://localhost:8000 (served by backend)

**API Documentation**
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## API Documentation

### Authentication

All protected endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <your_token>
```

### User Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/users/register | Register new user |
| POST | /api/users/login | Login and get token |
| POST | /api/users/logout | Logout user |
| GET | /api/users/me | Get current user profile |
| PUT | /api/users/me | Update current user profile |
| GET | /api/users/{id} | Get user by ID |

### Document Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/documents | List user's documents |
| POST | /api/documents | Create new document |
| GET | /api/documents/{id} | Get document by ID |
| PUT | /api/documents/{id} | Update document |
| DELETE | /api/documents/{id} | Delete document |
| POST | /api/documents/{id}/collaborate | Join/leave editing |
| POST | /api/documents/{id}/changes | Track real-time change |

### Version Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/documents/{id}/versions | Get version history |
| POST | /api/documents/{id}/versions | Create new version |
| POST | /api/documents/{id}/revert | Revert to version |
| POST | /api/documents/{id}/compare | Compare versions |
| GET | /api/documents/{id}/contributions | Get contributions |

### WebSocket

Connect to: `ws://localhost:8000/ws?token=<jwt_token>`

Message types:
- `join_document`: Join a document room
- `leave_document`: Leave a document room
- `text_change`: Send text change to others
- `cursor_update`: Update cursor position

---

## Testing

### Run All Tests

```bash
# From project root
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_user_agent.py -v
pytest tests/test_document_agent.py -v
pytest tests/test_version_agent.py -v
```

### Run with Coverage

```bash
pip install pytest-cov
pytest tests/ --cov=. --cov-report=html
```

---

## Key Concepts for Viva

### 1. Why Agent-Based Architecture?

**Answer**: Agent-based architecture provides:
- **Encapsulation**: Each agent handles one domain (Single Responsibility)
- **Loose Coupling**: Agents communicate via messages, not direct calls
- **Scalability**: Can add more agent instances if needed
- **Testability**: Agents can be tested in isolation
- **Flexibility**: Easy to add new operations or agents

### 2. How Does Message Passing Work?

**Answer**: 
1. A request comes in (HTTP or WebSocket)
2. API Gateway creates an `AgentMessage` with type and payload
3. `MessageBroker` routes the message to the correct agent
4. Agent processes the message via registered handler
5. Agent returns a response message
6. MessageBroker correlates response with original request
7. API Gateway returns response to client

### 3. How is Real-Time Collaboration Achieved?

**Answer**:
1. Users connect via WebSocket
2. When opening a document, client sends "join_document" message
3. WebSocketManager adds them to that document's "room"
4. When user types, changes are sent via WebSocket
5. Server broadcasts changes to all others in the room
6. Their editors update in real-time

### 4. How Does Version Control Work?

**Answer**:
- **Snapshots**: Each version stores complete document content
- **Version Numbers**: Sequential integers (1, 2, 3...)
- **Revert**: Copies old version content to current, creates new version
- **Contributions**: Tracks individual changes with user IDs

### 5. How is Security Handled?

**Answer**:
- **Password Hashing**: bcrypt with automatic salting
- **JWT Tokens**: Stateless authentication with expiration
- **Authorization**: Permission checks before operations
- **Input Validation**: Pydantic schemas validate all input

### 6. Design Patterns Used

1. **Singleton**: MessageBroker, EventBus (one instance)
2. **Observer**: EventBus subscriptions
3. **Mediator**: MessageBroker mediates agent communication
4. **Command**: Each MessageType is a command
5. **Template Method**: Base Agent defines skeleton
6. **Factory**: Test fixtures create test data

### 7. Async/Await Explained

**Answer**: Python's async/await enables non-blocking I/O:
- `async def`: Declares a coroutine function
- `await`: Pauses until operation completes
- Event loop manages multiple coroutines concurrently
- Essential for WebSockets and database operations

### 8. Why SQLite?

**Answer**: SQLite for development because:
- No server setup needed
- File-based, easy to reset
- Full SQL support
- Can switch to PostgreSQL by changing connection string

---

## Project Structure

```
Wuhun University Assessment/
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── README.md              # This documentation
│
├── core/                  # Core infrastructure
│   ├── __init__.py
│   ├── agent_base.py      # Base Agent class, AgentMessage
│   ├── message_broker.py  # Central message routing
│   └── event_bus.py       # Real-time event distribution
│
├── agents/                # The three agents
│   ├── __init__.py
│   ├── user_agent.py      # User Management Agent
│   ├── document_agent.py  # Document Editing Agent
│   └── version_agent.py   # Version Control Agent
│
├── models/                # Database models
│   ├── __init__.py
│   ├── database.py        # DB configuration
│   ├── user.py            # User model
│   ├── document.py        # Document model
│   └── version.py         # Version & Change models
│
├── api/                   # API layer
│   ├── __init__.py
│   ├── routes.py          # REST API endpoints
│   └── websocket.py       # WebSocket handler
│
├── static/                # Frontend
│   └── index.html         # Single-page application
│
└── tests/                 # Test suite
    ├── __init__.py
    ├── conftest.py        # Test fixtures
    ├── test_user_agent.py
    ├── test_document_agent.py
    └── test_version_agent.py
```

---

## Author

Created for Wuhan University Assessment - Collaborative Editing System Task
