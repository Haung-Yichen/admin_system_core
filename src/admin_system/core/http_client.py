"""
HTTP Client Lifecycle Management.

Provides RAII-style lifecycle-managed httpx.AsyncClient for use across the application.
Follows the principle that resource lifecycle should be explicitly bound to its scope,
avoiding global/thread-local state anti-patterns.

Design Principles:
    1. NO global singletons or thread-local storage
    2. Resources are bound to their owning scope (Event Loop/Thread)
    3. Explicit dependency injection - no implicit state
    4. RAII pattern: acquisition = initialization, release = scope exit

Usage:
    # In main.py lifespan (main thread):
    async with create_http_client_context(app) as http_manager:
        yield
    
    # In FastAPI routes (via dependency injection):
    def get_http_client(request: Request) -> httpx.AsyncClient:
        return request.app.state.http_client
    
    # In background threads (create isolated client):
    async with create_standalone_http_client() as client:
        service = RagicService(http_client=client)
        await service.do_work()
"""

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncGenerator, Optional, Protocol, runtime_checkable

import httpx

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)


# =============================================================================
# Protocol Definitions (for Type Safety and Testability)
# =============================================================================


@runtime_checkable
class HttpClientProtocol(Protocol):
    """
    Protocol for HTTP client operations.
    
    Allows mocking in tests and abstracting the actual client implementation.
    """
    
    async def get(
        self,
        url: str,
        *,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response: ...
    
    async def post(
        self,
        url: str,
        *,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
        headers: Optional[dict] = None,
        timeout: Optional[float] = None,
    ) -> httpx.Response: ...
    
    @property
    def is_closed(self) -> bool: ...
    
    async def aclose(self) -> None: ...


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


@asynccontextmanager
async def create_standalone_http_client(
    timeout: float = 30.0,
    max_connections: int = 50,
    max_keepalive_connections: int = 20,
    keepalive_expiry: float = 30.0,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    Create a standalone HTTP client for isolated execution contexts.
    
    This follows RAII pattern: the client lifecycle is bound to the context manager scope.
    Use this for background threads/tasks that need their own HTTP client.
    
    Args:
        timeout: Request timeout in seconds.
        max_connections: Maximum concurrent connections.
        max_keepalive_connections: Maximum keep-alive connections.
        keepalive_expiry: Keep-alive connection expiry in seconds.
    
    Yields:
        httpx.AsyncClient instance bound to the caller's event loop.
    
    Example:
        async def background_worker():
            async with create_standalone_http_client() as client:
                service = RagicService(http_client=client)
                await service.sync_data()
    """
    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_keepalive_connections,
        keepalive_expiry=keepalive_expiry,
    )
    
    client = httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    )
    
    logger.debug(
        f"Standalone HTTP client created (timeout={timeout}s, "
        f"max_connections={max_connections})"
    )
    
    try:
        yield client
    finally:
        await client.aclose()
        logger.debug("Standalone HTTP client closed")


def get_http_client_from_app(app: "FastAPI") -> httpx.AsyncClient:
    """
    Get HTTP client from FastAPI app state.
    
    This is the single source of truth for accessing the HTTP client from app state.
    
    Args:
        app: FastAPI application instance.
    
    Returns:
        The shared httpx.AsyncClient.
    
    Raises:
        RuntimeError: If HTTP client is not configured or is closed.
    """
    if not hasattr(app.state, "http_client"):
        raise RuntimeError(
            "HTTP client not available. Ensure lifespan context is properly configured."
        )
    
    client: httpx.AsyncClient = app.state.http_client
    
    if client is None or client.is_closed:
        raise RuntimeError("HTTP client is not running or has been closed.")
    
    return client

