"""
Database Session Management Module.

Provides async database session management using SQLAlchemy 2.0+ async patterns.
Follows Dependency Inversion Principle - high-level modules depend on abstractions.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.database.engine import get_engine, get_thread_local_engine, close_engine


# Global session factory (initialized lazily)
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


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


@asynccontextmanager
async def get_thread_local_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions in background threads.

    This creates a session using a thread-local engine, which is required
    when running async code in a separate thread with its own event loop.

    IMPORTANT: Only use this in background threads that have their own event loop.
    For normal async code in the main thread, use get_standalone_session() instead.

    Yields:
        AsyncSession: Database session bound to the current thread's engine.

    Example:
        def background_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def do_work():
                async with get_thread_local_session() as session:
                    result = await session.execute(text("SELECT 1"))
                    ...

            loop.run_until_complete(do_work())
    """
    engine = get_thread_local_engine()
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_database() -> None:
    """
    Initialize database schema.
    
    Creates all tables defined in models if they don't exist.
    Should be called during application startup.
    """
    from sqlalchemy import text
    from core.database.base import Base
    import core.models  # noqa: F401 - Import to register models with Base.metadata
    
    engine = get_engine()
    async with engine.begin() as conn:
        # Enable pgvector extension first
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)


async def close_db_connections() -> None:
    """
    Close all database connections.

    Should be called during application shutdown.
    """
    global _async_session_factory

    await close_engine()
    _async_session_factory = None


# Type alias for dependency injection
DBSession = Annotated[AsyncSession, Depends(get_db_session)]

