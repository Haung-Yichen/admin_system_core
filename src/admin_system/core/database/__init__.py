"""
Core Database Package.

Provides centralized database management for the framework.
Modules should use these components instead of creating their own connections.
"""

from core.database.base import Base, TimestampMixin, UUIDPrimaryKey, CreatedAt, UpdatedAt
from core.database.engine import get_engine, get_thread_local_engine, dispose_thread_local_engine, close_engine
from core.database.session import (
    get_session_factory,
    get_db_session,
    get_standalone_session,
    get_thread_local_session,
    close_db_connections,
    init_database,
    DBSession,
)

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKey",
    "CreatedAt",
    "UpdatedAt",
    # Engine
    "get_engine",
    "get_thread_local_engine",
    "dispose_thread_local_engine",
    "close_engine",
    # Session
    "get_session_factory",
    "get_db_session",
    "get_standalone_session",
    "get_thread_local_session",
    "close_db_connections",
    "init_database",
    "DBSession",
]
