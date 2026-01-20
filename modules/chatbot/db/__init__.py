"""
Chatbot Database Package (Legacy Re-exports).

This package now re-exports from core.database for backward compatibility.
New code should import directly from core.database.
"""

from core.database import (
    Base,
    TimestampMixin,
    UUIDPrimaryKey,
    DBSession,
    close_db_connections,
    get_db_session,
    get_standalone_session,
)

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDPrimaryKey",
    "DBSession",
    "close_db_connections",
    "get_db_session",
    "get_standalone_session",
]
