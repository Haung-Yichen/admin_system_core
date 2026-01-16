"""
Database Session Management Module.

Provides async database session management using SQLAlchemy 2.0+ async patterns.
Follows Dependency Inversion Principle - high-level modules depend on abstractions.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.app_context import ConfigLoader
from modules.chatbot.core.config import get_chatbot_settings


# Global engine and session factory (initialized lazily)
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Get or create the async database engine.
    
    Returns:
        AsyncEngine: SQLAlchemy async engine instance.
    """
    global _engine
    
    if _engine is None:
        settings = get_chatbot_settings()
        
        # Load global database config
        config_loader = ConfigLoader()
        config_loader.load()
        database_url = config_loader.get("database.url", "")
        
        _engine = create_async_engine(
            str(database_url),
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
    
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the async session factory.
    
    Returns:
        async_sessionmaker[AsyncSession]: Session factory for creating database sessions.
    """
    global _async_session_factory
    
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for database session injection.
    
    Yields:
        AsyncSession: Database session that auto-closes after request.
    
    Example:
        @router.get("/items")
        async def get_items(db: Annotated[AsyncSession, Depends(get_db_session)]):
            ...
    """
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_standalone_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for standalone database sessions (outside FastAPI request context).
    
    Useful for background tasks, CLI commands, or testing.
    
    Yields:
        AsyncSession: Database session with automatic cleanup.
    
    Example:
        async with get_standalone_session() as session:
            user = await session.get(User, user_id)
    """
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db_connections() -> None:
    """
    Close all database connections.
    
    Should be called during application shutdown.
    """
    global _engine, _async_session_factory
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None


# Type alias for dependency injection
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
