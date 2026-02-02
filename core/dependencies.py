"""
FastAPI Dependencies - Dependency Injection for API Routers.

Provides `Annotated[Service, Depends(get_service)]` patterns for
clean dependency injection in FastAPI route handlers.

Usage:
    from core.dependencies import ConfigDep, DbSessionDep, LogDep
    
    @router.get("/items")
    async def get_items(
        config: ConfigDep,
        db: DbSessionDep,
        log: LogDep
    ):
        log.log_event("Fetching items")
        ...
"""

import logging
from collections.abc import AsyncGenerator
from typing import Annotated, Optional, TYPE_CHECKING

import httpx
from fastapi import Depends, HTTPException, Query, Request, status

from core.http_client import get_http_client_from_app
from core.providers import (
    ConfigurationProvider,
    LogService,
    get_configuration_provider,
    get_log_service,
    get_line_client,
    get_server_state,
    ServerState,
)
from core.security.webhook import (
    WebhookAuthContext,
    WebhookAuthResult,
    WebhookSecurityService,
    get_webhook_security_service,
)

if TYPE_CHECKING:
    from core.line_client import LineClient
    from core.ragic import RagicService
    from sqlalchemy.ext.asyncio import AsyncSession

_webhook_logger = logging.getLogger("webhook.security")


# =============================================================================
# Configuration Dependencies
# =============================================================================

def get_config() -> ConfigurationProvider:
    """
    FastAPI dependency for configuration provider.
    
    Returns:
        ConfigurationProvider: The configuration provider instance
    """
    return get_configuration_provider()


# Type alias for dependency injection
ConfigDep = Annotated[ConfigurationProvider, Depends(get_config)]


def get_settings_value(key: str, default: str = ""):
    """
    Create a dependency that returns a specific config value.
    
    Usage:
        @router.get("/health")
        async def health(debug: bool = Depends(get_settings_value("app.debug", False))):
            ...
    """
    def _get_value() -> str:
        config = get_configuration_provider()
        return config.get(key, default)
    return _get_value


# =============================================================================
# Database Session Dependencies
# =============================================================================

async def get_db() -> AsyncGenerator["AsyncSession", None]:
    """
    FastAPI dependency for async database session.
    
    This is a re-export from core.database.session for convenience.
    
    Yields:
        AsyncSession: Database session that auto-closes after request
        
    Example:
        @router.get("/users")
        async def get_users(db: DbSessionDep):
            result = await db.execute(select(User))
            return result.scalars().all()
    """
    from core.database.session import get_db_session
    async for session in get_db_session():
        yield session


# Type alias for dependency injection
DbSessionDep = Annotated["AsyncSession", Depends(get_db)]


# =============================================================================
# Logging Dependencies
# =============================================================================

def get_log() -> LogService:
    """
    FastAPI dependency for log service.
    
    Returns:
        LogService: The centralized log service
    """
    return get_log_service()


# Type alias for dependency injection
LogDep = Annotated[LogService, Depends(get_log)]


# =============================================================================
# LINE Client Dependencies
# =============================================================================

def get_line() -> "LineClient":
    """
    FastAPI dependency for LINE client.
    
    Returns:
        LineClient: The LINE API client
        
    Raises:
        RuntimeError: If LINE is not configured
    """
    config = get_configuration_provider()
    if not config.is_line_configured():
        raise RuntimeError("LINE is not configured. Check environment variables.")
    return get_line_client()


# Type alias for dependency injection
LineClientDep = Annotated["LineClient", Depends(get_line)]


# Optional LINE client (returns None if not configured)
def get_line_optional() -> "LineClient | None":
    """
    FastAPI dependency for optional LINE client.
    
    Returns:
        LineClient or None if not configured
    """
    config = get_configuration_provider()
    if not config.is_line_configured():
        return None
    return get_line_client()


LineClientOptionalDep = Annotated["LineClient | None", Depends(get_line_optional)]


# =============================================================================
# HTTP Client Dependencies
# =============================================================================

def get_http_client(request: Request) -> httpx.AsyncClient:
    """
    FastAPI dependency for shared HTTP client.
    
    Gets the HTTP client from app.state via the centralized helper.
    
    Args:
        request: FastAPI request object.
    
    Returns:
        httpx.AsyncClient: The shared HTTP client.
    
    Raises:
        RuntimeError: If HTTP client is not available or closed.
    """
    return get_http_client_from_app(request.app)


# Type alias for dependency injection
HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


def get_http_client_optional(request: Request) -> httpx.AsyncClient | None:
    """
    FastAPI dependency for optional HTTP client.
    
    Returns None if HTTP client is not available (e.g., during testing).
    
    Args:
        request: FastAPI request object.
    
    Returns:
        httpx.AsyncClient or None if not available.
    """
    if not hasattr(request.app.state, "http_client"):
        return None
    
    client: httpx.AsyncClient | None = request.app.state.http_client
    
    if client is None or client.is_closed:
        return None
    
    return client


HttpClientOptionalDep = Annotated[httpx.AsyncClient | None, Depends(get_http_client_optional)]


# =============================================================================
# Ragic Service Dependencies
# =============================================================================

def get_ragic(request: Request) -> "RagicService":
    """
    FastAPI dependency for Ragic service.
    
    Injects the shared HTTP client into RagicService for proper
    lifecycle management.
    
    Args:
        request: FastAPI request object.
    
    Returns:
        RagicService: The Ragic API service with shared HTTP client.
        
    Raises:
        RuntimeError: If Ragic is not configured.
    """
    from core.ragic import RagicService
    
    config = get_configuration_provider()
    if not config.is_ragic_configured():
        raise RuntimeError("Ragic is not configured. Check environment variables.")
    
    # Get shared HTTP client from app state
    http_client = get_http_client_optional(request)
    
    return RagicService(http_client=http_client)


# Type alias for dependency injection
RagicServiceDep = Annotated["RagicService", Depends(get_ragic)]


# Optional Ragic service
def get_ragic_optional(request: Request) -> "RagicService | None":
    """
    FastAPI dependency for optional Ragic service.
    
    Args:
        request: FastAPI request object.
    
    Returns:
        RagicService or None if not configured.
    """
    from core.ragic import RagicService
    
    config = get_configuration_provider()
    if not config.is_ragic_configured():
        return None
    
    # Get shared HTTP client from app state
    http_client = get_http_client_optional(request)
    
    return RagicService(http_client=http_client)


RagicServiceOptionalDep = Annotated["RagicService | None", Depends(get_ragic_optional)]


# =============================================================================
# Server State Dependencies
# =============================================================================

def get_server() -> ServerState:
    """
    FastAPI dependency for server state.
    
    Returns:
        ServerState: The server runtime state
    """
    return get_server_state()


# Type alias for dependency injection
ServerStateDep = Annotated[ServerState, Depends(get_server)]


# =============================================================================
# Composite Dependencies (Multiple services bundled)
# =============================================================================

class CoreServices:
    """
    Composite container for commonly-used core services.
    
    Use this when you need multiple services in a single handler
    to reduce parameter count.
    """
    
    def __init__(
        self,
        config: ConfigurationProvider,
        log: LogService,
        server: ServerState,
    ) -> None:
        self.config = config
        self.log = log
        self.server = server


def get_core_services(
    config: ConfigDep,
    log: LogDep,
    server: ServerStateDep,
) -> CoreServices:
    """
    FastAPI dependency for bundled core services.
    
    Returns:
        CoreServices: Container with config, log, and server state
    """
    return CoreServices(config=config, log=log, server=server)


CoreServicesDep = Annotated[CoreServices, Depends(get_core_services)]


# =============================================================================
# Request-scoped Dependencies
# =============================================================================

class RequestContext:
    """
    Request-scoped context containing request-specific data.
    
    This is created fresh for each request and can hold
    request-specific state like user info, trace IDs, etc.
    """
    
    def __init__(self, config: ConfigurationProvider, log: LogService) -> None:
        self._config = config
        self._log = log
        self._data: dict = {}
    
    @property
    def config(self) -> ConfigurationProvider:
        return self._config
    
    @property
    def log(self) -> LogService:
        return self._log
    
    def set(self, key: str, value) -> None:
        """Set request-scoped data."""
        self._data[key] = value
    
    def get(self, key: str, default=None):
        """Get request-scoped data."""
        return self._data.get(key, default)


def get_request_context(
    config: ConfigDep,
    log: LogDep,
) -> RequestContext:
    """
    FastAPI dependency for request-scoped context.
    
    A new RequestContext is created for each request.
    """
    return RequestContext(config=config, log=log)


RequestContextDep = Annotated[RequestContext, Depends(get_request_context)]


# =============================================================================
# Webhook Security Dependencies
# =============================================================================

def get_webhook_security() -> WebhookSecurityService:
    """
    FastAPI dependency for webhook security service.
    
    Returns:
        WebhookSecurityService: The webhook security service
    """
    return get_webhook_security_service()


WebhookSecurityDep = Annotated[WebhookSecurityService, Depends(get_webhook_security)]


def _get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request.
    
    Checks X-Forwarded-For header first (for reverse proxy setups),
    then falls back to direct client IP.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Client IP address string
    """
    # Check for forwarded header (common in reverse proxy setups)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs; take the first (original client)
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header (used by some proxies)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client IP
    if request.client:
        return request.client.host
    
    return "unknown"


async def verify_webhook_signature(
    request: Request,
    source: str = Query(..., description="Webhook source identifier"),
    token: Optional[str] = Query(None, description="URL-based authentication token"),
) -> WebhookAuthContext:
    """
    FastAPI dependency that verifies webhook signatures.
    
    This dependency reads the raw request body and verifies it against
    either the X-Hub-Signature-256 header or URL token parameter.
    
    Args:
        request: FastAPI request object
        source: Webhook source identifier (from query param)
        token: Optional URL-based token
        
    Returns:
        WebhookAuthContext: Authentication result context
        
    Raises:
        HTTPException: 401 if signature is missing, 403 if invalid
    """
    security_service = get_webhook_security_service()
    client_ip = _get_client_ip(request)
    
    # Get raw request body for signature verification
    body = await request.body()
    
    # Get signature header
    signature_header = request.headers.get("X-Hub-Signature-256")
    
    # Authenticate the request
    auth_context = security_service.authenticate_request(
        payload=body,
        signature_header=signature_header,
        url_token=token,
        source=source,
        client_ip=client_ip,
    )
    
    # Handle authentication failures
    if not auth_context.verified:
        # Log the failed attempt with details
        _webhook_logger.warning(
            f"Webhook authentication failed: "
            f"source={source}, "
            f"result={auth_context.result.value}, "
            f"ip={client_ip}, "
            f"has_signature_header={bool(signature_header)}, "
            f"has_url_token={bool(token)}"
        )
        
        # Determine appropriate HTTP status code
        if auth_context.result == WebhookAuthResult.SECRET_NOT_CONFIGURED:
            # Server configuration error - 500
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook not properly configured",
            )
        elif auth_context.result in (
            WebhookAuthResult.MISSING_SIGNATURE,
            WebhookAuthResult.MISSING_TOKEN,
        ):
            # Missing credentials - 401 Unauthorized
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing webhook signature or token",
                headers={"WWW-Authenticate": "X-Hub-Signature-256"},
            )
        else:
            # Invalid credentials - 403 Forbidden
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid webhook signature or token",
            )
    
    return auth_context


# Type alias for webhook authentication dependency
WebhookAuthDep = Annotated[WebhookAuthContext, Depends(verify_webhook_signature)]


async def verify_webhook_signature_optional(
    request: Request,
    source: str = Query(..., description="Webhook source identifier"),
    token: Optional[str] = Query(None, description="URL-based authentication token"),
) -> WebhookAuthContext:
    """
    FastAPI dependency that verifies webhook signatures without raising exceptions.
    
    Unlike verify_webhook_signature, this returns the auth context even on
    failure, allowing the handler to decide how to proceed.
    
    Useful for gradual migration or endpoints that need custom error handling.
    
    Args:
        request: FastAPI request object
        source: Webhook source identifier (from query param)
        token: Optional URL-based token
        
    Returns:
        WebhookAuthContext: Authentication result context (may be unverified)
    """
    security_service = get_webhook_security_service()
    client_ip = _get_client_ip(request)
    
    # Get raw request body for signature verification
    body = await request.body()
    
    # Get signature header
    signature_header = request.headers.get("X-Hub-Signature-256")
    
    # Authenticate the request
    auth_context = security_service.authenticate_request(
        payload=body,
        signature_header=signature_header,
        url_token=token,
        source=source,
        client_ip=client_ip,
    )
    
    # Log failed attempts but don't raise
    if not auth_context.verified:
        _webhook_logger.warning(
            f"Webhook authentication failed (non-blocking): "
            f"source={source}, "
            f"result={auth_context.result.value}, "
            f"ip={client_ip}"
        )
    
    return auth_context


# Type alias for optional webhook authentication
WebhookAuthOptionalDep = Annotated[WebhookAuthContext, Depends(verify_webhook_signature_optional)]
