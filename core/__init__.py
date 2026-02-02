"""Core module - Application kernel components."""
from core.app_context import AppContext, ConfigLoader, IModuleContext, get_app_context
from core.interface import IAppModule, IConfigurable, ILoggable, ModuleContext
from core.logging_config import setup_logging
from core.registry import ModuleRegistry, ModuleLoader
from core.server import create_base_app, set_registry
from core import database

# LINE Client
from core.line_client import LineClient

# HTTP Client Lifecycle Management
from core.http_client import (
    HttpClientManager,
    create_http_client_context,
    get_http_client_from_app,
    get_global_http_client,
    set_global_http_client,
    is_http_client_available,
)

# Dependency Injection Providers
from core.providers import (
    ConfigurationProvider,
    LogService,
    ServerState,
    ServiceProvider,
    ProviderRegistry,
    get_configuration_provider,
    get_settings,
    get_log_service,
    get_line_client,
    get_server_state,
    get_provider_registry,
)

# FastAPI Dependencies (for use with Annotated[..., Depends(...)])
from core.dependencies import (
    ConfigDep,
    DbSessionDep,
    LogDep,
    HttpClientDep,
    HttpClientOptionalDep,
    LineClientDep,
    LineClientOptionalDep,
    RagicServiceDep,
    RagicServiceOptionalDep,
    ServerStateDep,
    CoreServicesDep,
    RequestContextDep,
    get_config,
    get_db,
    get_log,
    get_http_client,
    get_http_client_optional,
    get_line,
    get_ragic,
    get_server,
    get_core_services,
    get_request_context,
)

# Unified LINE Authentication (framework-level)
from core.line_auth import (
    LineAuthMessages,
    VerifiedUser,
    line_auth_check,
    get_verified_user,
    AUTH_ERROR_MESSAGES,
    AccountNotBoundResponse,
)

__all__ = [
    # Core exports
    "AppContext", "ConfigLoader", "IAppModule",
    "ModuleRegistry", "ModuleLoader",
    "create_base_app", "set_registry",
    "setup_logging", "database",
    # LINE Client
    "LineClient",
    # HTTP Client Lifecycle Management
    "HttpClientManager",
    "create_http_client_context",
    "get_http_client_from_app",
    "get_global_http_client",
    "set_global_http_client",
    "is_http_client_available",
    # New DI exports
    "IModuleContext", "get_app_context", "IConfigurable", "ILoggable", "ModuleContext",
    "ConfigurationProvider", "LogService", "ServerState", "ServiceProvider", "ProviderRegistry",
    "get_configuration_provider", "get_settings", "get_log_service",
    "get_line_client", "get_server_state", "get_provider_registry",
    # FastAPI Dependencies
    "ConfigDep", "DbSessionDep", "LogDep",
    "HttpClientDep", "HttpClientOptionalDep",
    "LineClientDep", "LineClientOptionalDep",
    "RagicServiceDep", "RagicServiceOptionalDep", "ServerStateDep",
    "CoreServicesDep", "RequestContextDep",
    "get_config", "get_db", "get_log",
    "get_http_client", "get_http_client_optional",
    "get_line", "get_ragic", "get_server",
    "get_core_services", "get_request_context",
    # LINE Auth
    "LineAuthMessages", "VerifiedUser", "line_auth_check",
    "get_verified_user", "AUTH_ERROR_MESSAGES", "AccountNotBoundResponse",
]


