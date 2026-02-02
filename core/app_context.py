"""
AppContext - Dependency Injection Container (Refactored).

This module now delegates to specific providers while maintaining
backward compatibility with existing code.

Implements:
- Dependency Inversion Principle (DIP)
- Interface Segregation Principle (ISP) via delegation to providers
- Open/Closed Principle (OCP) via provider registry

Migration Path:
    OLD: context.config.get("server.port")
    NEW: from core.dependencies import ConfigDep
         @router.get("/") 
         def handler(config: ConfigDep): ...
         
    OLD: context.log_event("message")
    NEW: from core.dependencies import LogDep
         @router.get("/")
         def handler(log: LogDep): 
             log.log_event("message")
"""

from typing import Any, Optional, Protocol, TYPE_CHECKING
import logging
import warnings

from core.providers import (
    ConfigurationProvider,
    LogService,
    ServerState,
    get_configuration_provider,
    get_log_service,
    get_line_client,
    get_server_state,
    get_provider_registry,
)

if TYPE_CHECKING:
    from core.line_client import LineClient
    from core.ragic import RagicService


# =============================================================================
# Backward Compatibility Alias
# =============================================================================

# ConfigLoader is now an alias for ConfigurationProvider
# This maintains backward compatibility with existing imports
ConfigLoader = ConfigurationProvider


# =============================================================================
# Module Context Protocol (for type hints)
# =============================================================================

class IModuleContext(Protocol):
    """
    Protocol defining the minimal interface modules need from context.
    
    Modules should depend on this protocol, not the concrete AppContext.
    This enables easier testing and follows the Interface Segregation Principle.
    """
    
    @property
    def config(self) -> ConfigurationProvider:
        """Access configuration."""
        ...
    
    def log_event(self, message: str, level: str = "INFO") -> None:
        """Log an event."""
        ...
    
    def get_event_log(self) -> list[str]:
        """Get event history."""
        ...


# =============================================================================
# AppContext - Facade over DI Providers
# =============================================================================

class AppContext:
    """
    Application Context - Facade over DI providers.
    
    This class now acts as a facade that delegates to specific providers,
    maintaining backward compatibility while internally using proper DI.
    
    For new code, prefer injecting specific providers directly:
        - ConfigDep for configuration
        - LogDep for logging
        - DbSessionDep for database sessions
        
    Example (new style):
        from core.dependencies import ConfigDep, LogDep
        
        @router.get("/items")
        async def get_items(config: ConfigDep, log: LogDep):
            port = config.get("server.port")
            log.log_event("Fetching items")
            ...
    """
    
    _instance: Optional["AppContext"] = None
    
    def __new__(cls) -> "AppContext":
        """
        Singleton pattern to ensure consistent state across the application.
        
        Note: For testing, use AppContext.reset() to clear the singleton.
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the AppContext with DI providers."""
        if self._initialized:
            return
            
        self._logger = logging.getLogger(__name__)
        
        # Delegate to DI providers instead of owning state
        self._config_provider = get_configuration_provider()
        self._log_service = get_log_service()
        self._server_state = get_server_state()
        
        # Set initial server port from config
        port = self._config_provider.get("server.port", 8000)
        self._server_state.port = port
        
        self._initialized = True
    
    # -------------------------------------------------------------------------
    # Configuration Access (delegates to ConfigurationProvider)
    # -------------------------------------------------------------------------
    
    @property
    def config(self) -> ConfigurationProvider:
        """
        Access the configuration provider.
        
        Returns:
            ConfigurationProvider: The configuration provider instance
            
        Note:
            For FastAPI routes, prefer using ConfigDep:
                from core.dependencies import ConfigDep
                async def handler(config: ConfigDep): ...
        """
        return self._config_provider
    
    # -------------------------------------------------------------------------
    # LINE Client Access (delegates to provider)
    # -------------------------------------------------------------------------
    
    @property
    def line_client(self) -> "LineClient":
        """
        Access the LINE client (lazy initialization via provider).
        
        Returns:
            LineClient: The LINE API client
            
        Note:
            For FastAPI routes, prefer using LineClientDep:
                from core.dependencies import LineClientDep
                async def handler(line: LineClientDep): ...
        """
        return get_line_client()
    
    # -------------------------------------------------------------------------
    # Ragic Service Access (delegates to provider)
    # -------------------------------------------------------------------------
    
    @property
    def ragic_service(self) -> "RagicService":
        """
        Access the Ragic service.
        
        DEPRECATED: Use dependency injection instead.
        
        Returns:
            RagicService: The Ragic API service
            
        Note:
            For FastAPI routes, use RagicServiceDep:
                from core.dependencies import RagicServiceDep
                async def handler(ragic: RagicServiceDep): ...
                
            For background tasks:
                from core.http_client import create_standalone_http_client
                from core.ragic.service import RagicService
                
                async with create_standalone_http_client() as http_client:
                    service = RagicService(http_client=http_client)
        
        Raises:
            RuntimeError: Always raises as global client is no longer supported.
        """
        warnings.warn(
            "AppContext.ragic_service is deprecated. Use RagicServiceDep dependency injection.",
            DeprecationWarning,
            stacklevel=2,
        )
        raise RuntimeError(
            "AppContext.ragic_service is no longer supported. "
            "Use RagicServiceDep for FastAPI routes, or create_standalone_http_client() "
            "for background tasks with explicit HTTP client injection."
        )
    
    # -------------------------------------------------------------------------
    # Logging (delegates to LogService)
    # -------------------------------------------------------------------------
    
    def log_event(self, message: str, level: str = "INFO") -> None:
        """
        Log an event to both logger and event log.
        
        Args:
            message: The message to log
            level: Log level (INFO, ERROR, SUCCESS, WARN, etc.)
            
        Note:
            For FastAPI routes, prefer using LogDep:
                from core.dependencies import LogDep
                async def handler(log: LogDep):
                    log.log_event("message")
        """
        self._log_service.log_event(message, level)
    
    def get_event_log(self) -> list[str]:
        """
        Get a copy of the event log.
        
        Returns:
            List of formatted log entries
        """
        return self._log_service.get_event_log()
    
    # -------------------------------------------------------------------------
    # Server State (delegates to ServerState)
    # -------------------------------------------------------------------------
    
    def set_server_status(self, running: bool, port: int = 8000) -> None:
        """
        Update server status.
        
        Args:
            running: Whether the server is running
            port: The server port
        """
        self._server_state.set_status(running, port)
    
    def get_server_status(self) -> tuple[bool, int]:
        """
        Get current server status.
        
        Returns:
            Tuple of (is_running, port)
        """
        return self._server_state.get_status()
    
    # -------------------------------------------------------------------------
    # Direct Provider Access (for explicit DI)
    # -------------------------------------------------------------------------
    
    def get_config_provider(self) -> ConfigurationProvider:
        """Get the configuration provider directly."""
        return self._config_provider
    
    def get_log_service(self) -> LogService:
        """Get the log service directly."""
        return self._log_service
    
    def get_server_state(self) -> ServerState:
        """Get the server state directly."""
        return self._server_state
    
    # -------------------------------------------------------------------------
    # Testing Support
    # -------------------------------------------------------------------------
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance (for testing only).
        
        This also resets the underlying providers.
        """
        cls._instance = None
        from core.providers import ProviderRegistry
        ProviderRegistry.reset()
    
    @classmethod
    def create_test_context(
        cls,
        config_overrides: Optional[dict] = None,
    ) -> "AppContext":
        """
        Create a test context with optional config overrides.
        
        Args:
            config_overrides: Optional dict of config values to override
            
        Returns:
            A fresh AppContext for testing
        """
        cls.reset()
        context = cls()
        
        if config_overrides:
            for key, value in config_overrides.items():
                keys = key.split('.')
                current = context._config_provider._config
                for k in keys[:-1]:
                    if k not in current:
                        current[k] = {}
                    current = current[k]
                current[keys[-1]] = value
        
        return context


# =============================================================================
# Factory Function
# =============================================================================

def get_app_context() -> AppContext:
    """
    Get the AppContext singleton.
    
    This is the preferred way to obtain the AppContext instance.
    
    Returns:
        AppContext: The application context singleton
    """
    return AppContext()
