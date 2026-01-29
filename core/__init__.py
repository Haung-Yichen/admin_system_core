"""Core module - Application kernel components."""
from core.app_context import AppContext, ConfigLoader
from core.interface import IAppModule
from core.logging_config import setup_logging
from core.registry import ModuleRegistry, ModuleLoader
from core.router import EventRouter, WebhookDispatcher
from core.server import FastAPIServer
from core import database

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
    "AppContext", "ConfigLoader", "IAppModule",
    "ModuleRegistry", "ModuleLoader",
    "EventRouter", "WebhookDispatcher", "FastAPIServer",
    "setup_logging", "database",
    # LINE Auth
    "LineAuthMessages", "VerifiedUser", "line_auth_check",
    "get_verified_user", "AUTH_ERROR_MESSAGES", "AccountNotBoundResponse",
]


