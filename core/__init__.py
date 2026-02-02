"""Core module - Application kernel components."""
from core.app_context import AppContext, ConfigLoader, IModuleContext, get_app_context
from core.interface import IAppModule, IConfigurable, ILoggable, ModuleContext
from core.logging_config import setup_logging
from core.registry import ModuleRegistry, ModuleLoader
from core.router import EventRouter, WebhookDispatcher
from core.server import create_base_app, set_registry, set_webhook_handler
from core import database

# LINE Client
from core.line_client import LineClient

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
    get_ragic_service,
    get_server_state,
    get_provider_registry,
)

# FastAPI Dependencies (for use with Annotated[..., Depends(...)])
from core.dependencies import (
    ConfigDep,
    DbSessionDep,
    LogDep,
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
    # Legacy exports (backward compatibility)
    "AppContext", "ConfigLoader", "IAppModule",
    "ModuleRegistry", "ModuleLoader",
    "EventRouter", "WebhookDispatcher",
    "create_base_app", "set_registry", "set_webhook_handler",
    "setup_logging", "database",
    # LINE Client
    "LineClient",
    # New DI exports
    "IModuleContext", "get_app_context", "IConfigurable", "ILoggable", "ModuleContext",
    "ConfigurationProvider", "LogService", "ServerState", "ServiceProvider", "ProviderRegistry",
    "get_configuration_provider", "get_settings", "get_log_service",
    "get_line_client", "get_ragic_service", "get_server_state", "get_provider_registry",
    # FastAPI Dependencies
    "ConfigDep", "DbSessionDep", "LogDep", "LineClientDep", "LineClientOptionalDep",
    "RagicServiceDep", "RagicServiceOptionalDep", "ServerStateDep",
    "CoreServicesDep", "RequestContextDep",
    "get_config", "get_db", "get_log", "get_line", "get_ragic", "get_server",
    "get_core_services", "get_request_context",
    # LINE Auth
    "LineAuthMessages", "VerifiedUser", "line_auth_check",
    "get_verified_user", "AUTH_ERROR_MESSAGES", "AccountNotBoundResponse",
]


