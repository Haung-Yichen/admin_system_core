"""
HTTP Client Lifecycle Management.

Provides a properly lifecycle-managed httpx.AsyncClient for use across the application.
This follows FastAPI best practices by:
1. Using lifespan events to manage client lifecycle
2. Storing client in app.state for access
3. Providing dependency injection for services

Usage:
    # In main.py lifespan:
    async with create_http_client_context(app):
        yield
    
    # In dependencies:
    def get_http_client(request: Request) -> httpx.AsyncClient:
        return request.app.state.http_client
"""

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator, Optional

import httpx

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


class HttpClientManager:
    """
    Manages the lifecycle of httpx.AsyncClient.
    
    This class provides a clean interface for creating and closing
    HTTP clients, ensuring proper resource cleanup.
    """
    
    def __init__(
        self,
        timeout: float = 30.0,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
        keepalive_expiry: float = 30.0,
    ) -> None:
        """
        Initialize the HTTP client manager.
        
        Args:
            timeout: Default timeout for requests in seconds.
            max_connections: Maximum number of concurrent connections.
            max_keepalive_connections: Maximum keep-alive connections.
            keepalive_expiry: Keep-alive connection expiry in seconds.
        """
        self._timeout = timeout
        self._limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            keepalive_expiry=keepalive_expiry,
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def start(self) -> httpx.AsyncClient:
        """
        Create and start the HTTP client.
        
        Returns:
            The initialized httpx.AsyncClient.
        
        Raises:
            RuntimeError: If client is already started.
        """
        if self._client is not None:
            raise RuntimeError("HTTP client already started")
        
        self._client = httpx.AsyncClient(
            timeout=self._timeout,
            limits=self._limits,
            follow_redirects=True,
        )
        logger.info(
            f"HTTP client started (timeout={self._timeout}s, "
            f"max_connections={self._limits.max_connections})"
        )
        return self._client
    
    async def stop(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("HTTP client closed")
    
    @property
    def client(self) -> httpx.AsyncClient:
        """
        Get the managed HTTP client.
        
        Returns:
            The httpx.AsyncClient instance.
        
        Raises:
            RuntimeError: If client is not started.
        """
        if self._client is None:
            raise RuntimeError(
                "HTTP client not started. Ensure lifespan context is properly configured."
            )
        return self._client
    
    @property
    def is_running(self) -> bool:
        """Check if the HTTP client is running."""
        return self._client is not None and not self._client.is_closed


@asynccontextmanager
async def create_http_client_context(
    app: "FastAPI",
    timeout: float = 30.0,
    max_connections: int = 100,
) -> AsyncGenerator[HttpClientManager, None]:
    """
    Async context manager for HTTP client lifecycle.
    
    Use this in FastAPI lifespan to properly manage HTTP client resources.
    
    Args:
        app: FastAPI application instance.
        timeout: Request timeout in seconds.
        max_connections: Maximum concurrent connections.
    
    Yields:
        HttpClientManager instance.
    
    Example:
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with create_http_client_context(app) as http_manager:
                yield
    """
    manager = HttpClientManager(timeout=timeout, max_connections=max_connections)
    
    try:
        client = await manager.start()
        # Store in app.state for access via dependencies
        app.state.http_client = client
        app.state.http_client_manager = manager
        yield manager
    finally:
        await manager.stop()
        # Clean up app.state
        if hasattr(app.state, "http_client"):
            delattr(app.state, "http_client")
        if hasattr(app.state, "http_client_manager"):
            delattr(app.state, "http_client_manager")


def get_http_client_from_app(app: "FastAPI") -> httpx.AsyncClient:
    """
    Get HTTP client from FastAPI app state.
    
    Args:
        app: FastAPI application instance.
    
    Returns:
        The shared httpx.AsyncClient.
    
    Raises:
        RuntimeError: If HTTP client is not configured.
    """
    if not hasattr(app.state, "http_client"):
        raise RuntimeError(
            "HTTP client not available. Ensure lifespan context is properly configured."
        )
    return app.state.http_client


# =============================================================================
# Module-level singleton for non-request contexts (background tasks, etc.)
# Uses thread-local storage to support background sync threads with their own clients
# =============================================================================

import threading

_global_http_client: Optional[httpx.AsyncClient] = None
_thread_local = threading.local()


def set_global_http_client(client: Optional[httpx.AsyncClient]) -> None:
    """
    Set the HTTP client reference for the current thread.
    
    In the main thread (lifespan), this also sets the global default.
    In background threads, this sets a thread-local client.
    
    Args:
        client: The HTTP client or None to clear.
    """
    global _global_http_client
    
    # Always set thread-local
    _thread_local.http_client = client
    
    # In main thread, also set global (for backward compatibility)
    if threading.current_thread() is threading.main_thread():
        _global_http_client = client


def get_global_http_client() -> httpx.AsyncClient:
    """
    Get the HTTP client for the current thread.
    
    First checks thread-local storage (for background sync threads),
    then falls back to the global client (set by main thread lifespan).
    
    Returns:
        The httpx.AsyncClient for this thread.
    
    Raises:
        RuntimeError: If HTTP client is not available.
    """
    # Check thread-local first
    thread_client = getattr(_thread_local, 'http_client', None)
    if thread_client is not None:
        return thread_client
    
    # Fall back to global
    if _global_http_client is None:
        raise RuntimeError(
            "Global HTTP client not available. "
            "Ensure the application lifespan has started."
        )
    return _global_http_client


def is_http_client_available() -> bool:
    """Check if an HTTP client is available for the current thread."""
    thread_client = getattr(_thread_local, 'http_client', None)
    if thread_client is not None:
        return not thread_client.is_closed
    return _global_http_client is not None and not _global_http_client.is_closed
