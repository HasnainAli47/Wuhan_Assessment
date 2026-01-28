"""
Database Configuration Module

EXPLANATION FOR VIVA:
=====================
This module sets up the database connection using SQLAlchemy ORM (Object-Relational Mapping).

Key Concepts:
1. ORM: Maps Python classes to database tables
2. Async: Uses async/await for non-blocking database operations
3. Session: Manages database transactions
4. Connection Pool: Reuses database connections for efficiency

Why SQLAlchemy?
- Industry standard Python ORM
- Supports multiple databases (SQLite, PostgreSQL, MySQL)
- Provides both ORM and raw SQL options
- Handles connection pooling and transaction management

We use SQLite for simplicity (file-based, no server needed), but the code
can easily switch to PostgreSQL for production.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import event
import os
import logging

logger = logging.getLogger(__name__)

# Database URL - using SQLite for development, PostgreSQL for production
# Heroku provides DATABASE_URL with postgres:// scheme, but asyncpg needs postgresql://
_database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./collaborative_editing.db")

# Convert Heroku's postgres:// to postgresql+asyncpg://
if _database_url.startswith("postgres://"):
    DATABASE_URL = _database_url.replace("postgres://", "postgresql+asyncpg://", 1)
elif _database_url.startswith("postgresql://"):
    DATABASE_URL = _database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    DATABASE_URL = _database_url

# Create async engine
# echo=True logs all SQL statements (useful for debugging)
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True to see SQL queries
    future=True
)

# Create async session factory
# expire_on_commit=False keeps objects accessible after commit
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for all models
# All ORM models will inherit from this
Base = declarative_base()


async def init_db():
    """
    Initialize the database by creating all tables.
    
    EXPLANATION FOR VIVA:
    ====================
    This creates all tables defined by models that inherit from Base.
    It's idempotent - running it multiple times won't duplicate tables.
    
    In production, you'd use migrations (like Alembic) instead of create_all
    to handle schema changes gracefully.
    """
    async with engine.begin() as conn:
        # Import all models so they're registered with Base
        from . import user, document, version
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")


async def get_db():
    """
    Dependency injection function for FastAPI.
    
    EXPLANATION FOR VIVA:
    ====================
    This is a generator function that:
    1. Creates a new database session
    2. Yields it for use in the request
    3. Ensures cleanup (close) after the request
    
    The 'yield' makes this a context manager - the session is automatically
    closed when the request completes (success or failure).
    
    This pattern is called Dependency Injection - the database session is
    "injected" into route handlers that need it.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_session() -> AsyncSession:
    """
    Get a database session for use outside of FastAPI routes.
    
    EXPLANATION FOR VIVA:
    ====================
    Agents need database access but aren't in a FastAPI route context.
    This function provides a session that must be manually managed.
    
    Usage:
        session = await get_session()
        try:
            # do database operations
            await session.commit()
        finally:
            await session.close()
    """
    return AsyncSessionLocal()
