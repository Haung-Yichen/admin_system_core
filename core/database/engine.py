"""
Database Engine Management Module.

Provides a singleton AsyncEngine for the entire application.
Uses configuration from core.app_context.ConfigLoader.
"""

import threading
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from core.app_context import ConfigLoader


# Global engine instance (singleton for main thread)
_engine: AsyncEngine | None = None

# Thread-local storage for background thread engines
_thread_local = threading.local()



def _get_ssl_context():
    """Create a permissive SSL context for database connections."""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def get_engine(debug: bool = False) -> AsyncEngine:
    """
    Get or create the async database engine (singleton).

    Args:
        debug: Enable SQLAlchemy echo mode for debugging.

    Returns:
        AsyncEngine: SQLAlchemy async engine instance.
    """
    global _engine

    if _engine is None:
        config_loader = ConfigLoader()
        config_loader.load()
        database_url = config_loader.get("database.url", "")
        # app_debug = config_loader.get("app.debug", False) # Unused variable

        _engine = create_async_engine(
            str(database_url),
            echo=False,  # Force disabled to prevent vector log spam
            pool_pre_ping=True,
            pool_size=20,  # Increased from 10 for high concurrency (100 users)
            max_overflow=40,  # Increased from 20 for burst traffic
            connect_args={
                "ssl": _get_ssl_context(),  # Use permissive SSL context
            },
        )

    return _engine


def get_thread_local_engine() -> AsyncEngine:
    """
    Get or create a thread-local async database engine.

    This is specifically designed for background threads that run their own
    event loops. Each thread gets its own engine to avoid cross-loop issues.

    Returns:
        AsyncEngine: Thread-local SQLAlchemy async engine instance.

    Example:
        def background_task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            engine = get_thread_local_engine()
            # Use engine with this thread's loop
    """
    if not hasattr(_thread_local, "engine") or _thread_local.engine is None:
        config_loader = ConfigLoader()
        config_loader.load()
        database_url = config_loader.get("database.url", "")

        _thread_local.engine = create_async_engine(
            str(database_url),
            echo=False,
            pool_pre_ping=True,
            pool_size=2,  # Smaller pool for background threads
            max_overflow=0,
            connect_args={
                "ssl": _get_ssl_context(),  # Use permissive SSL context
            },
        )

    return _thread_local.engine


async def close_engine() -> None:
    """
    Close the database engine and release all connections.

    Should be called during application shutdown.
    """
    global _engine

    if _engine is not None:
        await _engine.dispose()
        _engine = None


async def dispose_thread_local_engine() -> None:
    """
    Dispose the thread-local engine if it exists.
    
    This must be called before closing the event loop in a background thread
    to ensure all asyncpg connections are closed properly.
    """
    if hasattr(_thread_local, "engine") and _thread_local.engine is not None:
        await _thread_local.engine.dispose()
        _thread_local.engine = None
