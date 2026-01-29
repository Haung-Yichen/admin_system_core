"""
System API.

Provides system status, logs, and module information for the web dashboard.
"""

import time
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.admin_auth import CurrentAdmin
from core.app_context import AppContext


router = APIRouter(prefix="/system", tags=["System"])


# Module-level start time for uptime calculation
_start_time: float = time.time()


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class ServerStatus(BaseModel):
    """Server status information."""

    running: bool
    port: int
    host: str
    uptime_seconds: float
    started_at: str


class SystemStatusResponse(BaseModel):
    """System status response."""

    server: ServerStatus
    version: str
    environment: str


class LogEntry(BaseModel):
    """Single log entry."""

    message: str
    timestamp: str | None = None


class LogsResponse(BaseModel):
    """Logs response."""

    logs: list[LogEntry]
    total: int


class ModuleInfo(BaseModel):
    """Module information."""

    name: str
    status: str
    has_line_webhook: bool
    has_api_router: bool


class ModulesResponse(BaseModel):
    """Modules response."""

    modules: list[ModuleInfo]
    total: int


# -----------------------------------------------------------------------------
# Context Singleton
# -----------------------------------------------------------------------------

# Note: AppContext is a singleton-like object. In production, you would
# inject this properly. For now, we create a shared instance.
_context: AppContext | None = None


def get_app_context() -> AppContext:
    """Get or create the shared AppContext instance."""
    global _context
    if _context is None:
        _context = AppContext()
    return _context


def set_app_context(context: AppContext) -> None:
    """Set the shared AppContext instance (called during app startup)."""
    global _context
    _context = context


# Registry reference (set during app startup)
_registry: Any = None


def set_registry(registry: Any) -> None:
    """Set the module registry reference."""
    global _registry
    _registry = registry


def get_registry() -> Any:
    """Get the module registry."""
    return _registry


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    admin: CurrentAdmin,
) -> SystemStatusResponse:
    """
    Get current system status.

    Requires: Admin authentication

    Returns:
        Server status, uptime, and version information
    """
    context = get_app_context()
    running, port = context.get_server_status()

    uptime = time.time() - _start_time
    started_at = datetime.fromtimestamp(_start_time, tz=timezone.utc).isoformat()

    return SystemStatusResponse(
        server=ServerStatus(
            running=running,
            port=port,
            host=context.config.get("server.host", "127.0.0.1"),
            uptime_seconds=uptime,
            started_at=started_at,
        ),
        version="1.0.0",
        environment="development" if context.config.get("app.debug", True) else "production",
    )


@router.get("/logs", response_model=LogsResponse)
async def get_system_logs(
    admin: CurrentAdmin,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LogsResponse:
    """
    Get recent system logs.

    Requires: Admin authentication

    Args:
        limit: Maximum number of logs to return (1-500)
        offset: Number of logs to skip

    Returns:
        List of log entries
    """
    context = get_app_context()
    all_logs = context.get_event_log()

    # Apply pagination (reverse order - newest first)
    reversed_logs = list(reversed(all_logs))
    paginated = reversed_logs[offset : offset + limit]

    entries = []
    for log_line in paginated:
        # Parse log format: [HH:MM:SS] [LEVEL] message
        # Extract timestamp if present
        timestamp = None
        message = log_line

        if log_line.startswith("["):
            try:
                # Find closing bracket for timestamp
                ts_end = log_line.index("]", 1)
                timestamp = log_line[1:ts_end]
                message = log_line[ts_end + 1 :].strip()
            except ValueError:
                pass

        entries.append(LogEntry(message=message, timestamp=timestamp))

    return LogsResponse(logs=entries, total=len(all_logs))


@router.get("/modules", response_model=ModulesResponse)
async def get_loaded_modules(
    admin: CurrentAdmin,
) -> ModulesResponse:
    """
    Get list of loaded modules and their status.

    Requires: Admin authentication

    Returns:
        List of modules with their capabilities
    """
    registry = get_registry()

    if registry is None:
        return ModulesResponse(modules=[], total=0)

    modules_info = []
    for module in registry.get_all_modules():
        name = module.get_module_name()

        # Check capabilities
        has_line_webhook = module.get_line_bot_config() is not None
        has_api_router = hasattr(module, "get_api_router") and module.get_api_router() is not None

        modules_info.append(
            ModuleInfo(
                name=name,
                status="active",  # All registered modules are active
                has_line_webhook=has_line_webhook,
                has_api_router=has_api_router,
            )
        )

    return ModulesResponse(modules=modules_info, total=len(modules_info))
