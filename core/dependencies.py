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

from collections.abc import AsyncGenerator
from typing import Annotated, TYPE_CHECKING

from fastapi import Depends

from core.providers import (
    ConfigurationProvider,
    LogService,
    get_configuration_provider,
    get_log_service,
    get_line_client,
    get_ragic_service,
    get_server_state,
    ServerState,
)

if TYPE_CHECKING:
    from services.line_client import LineClient
    from core.ragic import RagicService
    from sqlalchemy.ext.asyncio import AsyncSession


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
# Ragic Service Dependencies
# =============================================================================

def get_ragic() -> "RagicService":
    """
    FastAPI dependency for Ragic service.
    
    Returns:
        RagicService: The Ragic API service
        
    Raises:
        RuntimeError: If Ragic is not configured
    """
    config = get_configuration_provider()
    if not config.is_ragic_configured():
        raise RuntimeError("Ragic is not configured. Check environment variables.")
    return get_ragic_service()


# Type alias for dependency injection
RagicServiceDep = Annotated["RagicService", Depends(get_ragic)]


# Optional Ragic service
def get_ragic_optional() -> "RagicService | None":
    """
    FastAPI dependency for optional Ragic service.
    
    Returns:
        RagicService or None if not configured
    """
    config = get_configuration_provider()
    if not config.is_ragic_configured():
        return None
    return get_ragic_service()


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
