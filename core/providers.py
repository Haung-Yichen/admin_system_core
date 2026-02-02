"""
Service Providers - Dependency Injection Components.

Implements Interface Segregation Principle (ISP) by breaking down
the monolithic AppContext into focused, single-responsibility providers.

Each provider follows:
- Single Responsibility Principle (SRP)
- Dependency Inversion Principle (DIP)
- Interface Segregation Principle (ISP)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generic, Optional, Protocol, TypeVar, TYPE_CHECKING
import logging
import os

from dotenv import load_dotenv

if TYPE_CHECKING:
    from core.line_client import LineClient
    from core.ragic import RagicService
    from sqlalchemy.ext.asyncio import AsyncSession


# =============================================================================
# Configuration Provider
# =============================================================================

class IConfigurationProvider(Protocol):
    """Protocol for configuration access - follows ISP."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key."""
        ...
    
    def is_line_configured(self) -> bool:
        """Check if LINE credentials are configured."""
        ...
    
    def is_ragic_configured(self) -> bool:
        """Check if Ragic credentials are configured."""
        ...


@dataclass
class ConfigurationProvider:
    """
    Provides configuration values loaded from environment variables.
    
    Implements IConfigurationProvider protocol for type-safe configuration access.
    """
    
    _config: Dict[str, Any] = field(default_factory=dict)
    _loaded: bool = field(default=False)
    
    def load(self, env_path: Optional[str] = None) -> "ConfigurationProvider":
        """
        Load configuration from .env file.
        
        Args:
            env_path: Optional path to .env file
            
        Returns:
            Self for method chaining
        """
        if self._loaded:
            return self
            
        if env_path:
            load_dotenv(env_path)
        else:
            project_root = Path(__file__).parent.parent
            env_file = project_root / ".env"
            if env_file.exists():
                load_dotenv(env_file)
        
        self._config = {
            "server": {
                "host": os.getenv("SERVER_HOST", "127.0.0.1"),
                "port": int(os.getenv("SERVER_PORT", "8000")),
                "base_url": os.getenv("BASE_URL", "")
            },
            "app": {
                "debug": os.getenv("APP_DEBUG", "true").lower() == "true",
                "log_level": os.getenv("APP_LOG_LEVEL", "INFO")
            },
            "database": {
                "url": os.getenv("DATABASE_URL", "")
            },
            "security": {
                "key": os.getenv("SECURITY_KEY", ""),
                "jwt_secret_key": os.getenv("JWT_SECRET_KEY", ""),
                "jwt_algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
                "magic_link_expire_minutes": int(os.getenv("MAGIC_LINK_EXPIRE_MINUTES", "15"))
            },
            "email": {
                "host": os.getenv("SMTP_HOST", ""),
                "port": int(os.getenv("SMTP_PORT", "587")),
                "username": os.getenv("SMTP_USERNAME", ""),
                "password": os.getenv("SMTP_PASSWORD", ""),
                "from_email": os.getenv("SMTP_FROM_EMAIL", ""),
                "from_name": os.getenv("SMTP_FROM_NAME", "Admin System")
            },
            "vector": {
                "model_name": os.getenv("EMBEDDING_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2"),
                "dimension": int(os.getenv("EMBEDDING_DIMENSION", "384")),
                "top_k": int(os.getenv("SEARCH_TOP_K", "3")),
                "similarity_threshold": float(os.getenv("SEARCH_SIMILARITY_THRESHOLD", "0.3"))
            },
            "line": {
                "channel_id": os.getenv("LINE_CHANNEL_ID", ""),
                "channel_secret": os.getenv("LINE_CHANNEL_SECRET", ""),
                "channel_access_token": os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
            },
            "ragic": {
                "api_key": os.getenv("RAGIC_API_KEY", ""),
                "base_url": os.getenv("RAGIC_BASE_URL", "https://ap13.ragic.com"),
                "employee_sheet_path": os.getenv("RAGIC_EMPLOYEE_SHEET_PATH", "/HSIBAdmSys/ychn-test/11"),
                "field_email": os.getenv("RAGIC_FIELD_EMAIL", "1005977"),
                "field_name": os.getenv("RAGIC_FIELD_NAME", "1005975"),
                "field_door_access_id": os.getenv("RAGIC_FIELD_DOOR_ACCESS_ID", "1005983")
            },
            "webhook": {
                "default_secret": os.getenv("WEBHOOK_DEFAULT_SECRET", ""),
                "secrets": {
                    # Source-specific secrets (e.g., WEBHOOK_SECRET_RAGIC, WEBHOOK_SECRET_CHATBOT_SOP)
                    "ragic": os.getenv("WEBHOOK_SECRET_RAGIC", ""),
                    "chatbot_sop": os.getenv("WEBHOOK_SECRET_CHATBOT_SOP", ""),
                    "chatbot_qa": os.getenv("WEBHOOK_SECRET_CHATBOT_QA", ""),
                }
            }
        }
        self._loaded = True
        return self
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by dot notation key.
        
        Args:
            key: Dot-separated key path (e.g., "server.port")
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def is_line_configured(self) -> bool:
        """Check if LINE credentials are set."""
        return bool(
            self.get("line.channel_secret") and 
            self.get("line.channel_access_token")
        )
    
    def is_ragic_configured(self) -> bool:
        """Check if Ragic credentials are set."""
        return bool(
            self.get("ragic.api_key") and 
            self.get("ragic.base_url")
        )


# Singleton instance
_configuration_provider: Optional[ConfigurationProvider] = None


def get_configuration_provider() -> ConfigurationProvider:
    """
    Get the singleton ConfigurationProvider instance.
    
    Returns:
        ConfigurationProvider: The configuration provider
    """
    global _configuration_provider
    if _configuration_provider is None:
        _configuration_provider = ConfigurationProvider()
        _configuration_provider.load()
    return _configuration_provider


def get_settings() -> ConfigurationProvider:
    """Alias for get_configuration_provider for cleaner DI."""
    return get_configuration_provider()


# =============================================================================
# Log Service
# =============================================================================

class ILogService(Protocol):
    """Protocol for logging service - follows ISP."""
    
    def log_event(self, message: str, level: str = "INFO") -> None:
        """Log an event."""
        ...
    
    def get_event_log(self) -> list[str]:
        """Get the event log history."""
        ...


@dataclass
class LogService:
    """
    Centralized logging service with event history.
    
    Provides both standard logging and an in-memory event log
    for GUI/dashboard display.
    """
    
    _event_log: list[str] = field(default_factory=list)
    _max_entries: int = 500
    _logger: logging.Logger = field(default_factory=lambda: logging.getLogger("LogService"))
    
    def log_event(self, message: str, level: str = "INFO") -> None:
        """
        Log an event to both logger and event log.
        
        Args:
            message: The message to log
            level: Log level (INFO, ERROR, SUCCESS, WARN, etc.)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        
        self._event_log.append(formatted)
        if len(self._event_log) > self._max_entries:
            self._event_log = self._event_log[-self._max_entries:]
        
        # Map to standard logging levels
        log_level = getattr(logging, level.upper(), logging.INFO)
        self._logger.log(log_level, message)
    
    def get_event_log(self) -> list[str]:
        """
        Get a copy of the event log.
        
        Returns:
            List of formatted log entries
        """
        return self._event_log.copy()
    
    def clear_event_log(self) -> None:
        """Clear the event log."""
        self._event_log.clear()


# Singleton instance
_log_service: Optional[LogService] = None


def get_log_service() -> LogService:
    """
    Get the singleton LogService instance.
    
    Returns:
        LogService: The log service
    """
    global _log_service
    if _log_service is None:
        _log_service = LogService()
    return _log_service


# =============================================================================
# Service Provider (Generic Factory Pattern)
# =============================================================================

T = TypeVar("T")


class ServiceProvider(Generic[T]):
    """
    Generic service provider with lazy initialization.
    
    Follows Factory pattern for creating service instances on demand.
    """
    
    def __init__(self, factory: callable, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the service provider.
        
        Args:
            factory: Callable that creates the service instance
            *args: Positional arguments for the factory
            **kwargs: Keyword arguments for the factory
        """
        self._factory = factory
        self._args = args
        self._kwargs = kwargs
        self._instance: Optional[T] = None
    
    def get(self) -> T:
        """
        Get or create the service instance.
        
        Returns:
            The service instance
        """
        if self._instance is None:
            self._instance = self._factory(*self._args, **self._kwargs)
        return self._instance
    
    def reset(self) -> None:
        """Reset the cached instance (useful for testing)."""
        self._instance = None


# =============================================================================
# LINE Client Provider
# =============================================================================

class ILineClientProvider(Protocol):
    """Protocol for LINE client access."""
    
    def get_line_client(self) -> "LineClient":
        """Get the LINE client instance."""
        ...


_line_client_provider: Optional[ServiceProvider] = None


def get_line_client_provider() -> ServiceProvider:
    """Get the LINE client service provider."""
    global _line_client_provider
    if _line_client_provider is None:
        def create_line_client():
            from core.line_client import LineClient
            return LineClient(get_configuration_provider())
        _line_client_provider = ServiceProvider(create_line_client)
    return _line_client_provider


def get_line_client() -> "LineClient":
    """Get the LINE client instance."""
    return get_line_client_provider().get()


# =============================================================================
# Server State Provider
# =============================================================================

@dataclass
class ServerState:
    """Holds server runtime state."""
    
    running: bool = False
    port: int = 8000
    
    def set_status(self, running: bool, port: int = 8000) -> None:
        """Update server status."""
        self.running = running
        self.port = port
    
    def get_status(self) -> tuple[bool, int]:
        """Get current server status."""
        return (self.running, self.port)


_server_state: Optional[ServerState] = None


def get_server_state() -> ServerState:
    """Get the server state singleton."""
    global _server_state
    if _server_state is None:
        _server_state = ServerState()
    return _server_state


# =============================================================================
# Provider Registry (Service Locator with DI backing)
# =============================================================================

class ProviderRegistry:
    """
    Central registry for all service providers.
    
    This acts as a lightweight DI container that can be used
    to override providers for testing or different configurations.
    """
    
    _instance: Optional["ProviderRegistry"] = None
    _providers: Dict[str, Any]
    _initialized: bool
    
    def __new__(cls) -> "ProviderRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        self._register_defaults()
        self._initialized = True
    
    def _register_defaults(self) -> None:
        """Register default providers."""
        self._providers = {
            "config": get_configuration_provider,
            "log": get_log_service,
            "line_client": get_line_client,
            "server_state": get_server_state,
        }
    
    def register(self, name: str, provider: callable) -> None:
        """
        Register a custom provider.
        
        Args:
            name: Provider name
            provider: Callable that returns the service
        """
        self._providers[name] = provider
    
    def get(self, name: str) -> Any:
        """
        Get a service from the registry.
        
        Args:
            name: Provider name
            
        Returns:
            The service instance
            
        Raises:
            KeyError: If provider not found
        """
        if name not in self._providers:
            raise KeyError(f"Provider '{name}' not found in registry")
        return self._providers[name]()
    
    def resolve(self, name: str) -> callable:
        """
        Get the provider callable (for dependency injection).
        
        Args:
            name: Provider name
            
        Returns:
            The provider callable
        """
        return self._providers[name]
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing)."""
        cls._instance = None


def get_provider_registry() -> ProviderRegistry:
    """Get the provider registry singleton."""
    return ProviderRegistry()
