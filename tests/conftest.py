"""
Test Configuration and Fixtures

================================================================================
DEVELOPED BY: Hasnain Ali | Wuhan University | Supervisor: Prof. Liang Peng
================================================================================

EXPLANATION FOR VIVA:
=====================
This file configures pytest and provides reusable test fixtures.
Think of fixtures as "setup helpers" that prepare everything a test needs.

What are Fixtures?
- Reusable test setup code that runs before each test
- Automatically clean up after tests complete
- Can be "scoped" to function, class, module, or session

Why Use Fixtures?
1. DRY (Don't Repeat Yourself): Write setup code once, use in many tests
2. Isolation: Each test gets a fresh, clean state
3. Maintainability: Change setup in one place, affects all tests
4. Readability: Tests focus on what they're testing, not setup

NOTE FOR ASSESSMENT:
- Tests use in-memory SQLite for speed (no file I/O)
- Each test function gets isolated database state
- Agents are properly started and stopped to prevent resource leaks
"""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from main import app
from models.database import Base, get_db
from core.message_broker import MessageBroker
from agents.user_agent import UserManagementAgent
from agents.document_agent import DocumentEditingAgent
from agents.version_agent import VersionControlAgent

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """
    Create an event loop for the test session.
    
    EXPLANATION FOR VIVA:
    ====================
    pytest-asyncio needs an event loop to run async tests.
    We create one that lasts the entire test session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db():
    """
    Create a test database for each test function.
    
    EXPLANATION FOR VIVA:
    ====================
    Uses in-memory SQLite so tests are fast and isolated.
    Tables are created fresh for each test.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    TestingSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with TestingSessionLocal() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(test_db):
    """
    Create a test HTTP client.
    
    EXPLANATION FOR VIVA:
    ====================
    httpx.AsyncClient allows making HTTP requests to our FastAPI app
    without actually starting a server. This is faster and more reliable
    for testing.
    """
    # Override database dependency
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def message_broker():
    """
    Create a fresh message broker for each test.
    
    EXPLANATION FOR VIVA:
    ====================
    The message broker is a singleton, so we need to reset it
    between tests to ensure isolation.
    """
    # Reset singleton
    MessageBroker._instance = None
    broker = MessageBroker()
    
    yield broker
    
    # Cleanup
    await broker.stop_all_agents()
    MessageBroker._instance = None


@pytest_asyncio.fixture(scope="function")
async def user_agent(message_broker):
    """Create and register a user management agent."""
    agent = UserManagementAgent()
    message_broker.register_agent(agent)
    await agent.start()
    
    yield agent
    
    await agent.stop()


@pytest_asyncio.fixture(scope="function")
async def document_agent(message_broker):
    """Create and register a document editing agent."""
    agent = DocumentEditingAgent()
    message_broker.register_agent(agent)
    await agent.start()
    
    yield agent
    
    await agent.stop()


@pytest_asyncio.fixture(scope="function")
async def version_agent(message_broker):
    """Create and register a version control agent."""
    agent = VersionControlAgent()
    message_broker.register_agent(agent)
    await agent.start()
    
    yield agent
    
    await agent.stop()


@pytest_asyncio.fixture(scope="function")
async def all_agents(message_broker):
    """Create and register all agents."""
    user_agent = UserManagementAgent()
    document_agent = DocumentEditingAgent()
    version_agent = VersionControlAgent()
    
    for agent in [user_agent, document_agent, version_agent]:
        message_broker.register_agent(agent)
    
    await message_broker.start_all_agents()
    
    yield {
        "user": user_agent,
        "document": document_agent,
        "version": version_agent,
        "broker": message_broker
    }
    
    await message_broker.stop_all_agents()


# Test data factories
def create_test_user_data(username="testuser", email="test@example.com"):
    """Factory for creating test user data."""
    return {
        "username": username,
        "email": email,
        "password": "testpass123",
        "display_name": f"Test {username.title()}"
    }


def create_test_document_data(title="Test Document"):
    """Factory for creating test document data."""
    return {
        "title": title,
        "content": "This is test content for the document.",
        "is_public": False
    }
