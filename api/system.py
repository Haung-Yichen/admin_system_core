"""
System API.

Provides system status, logs, and module information for the web dashboard.
"""

import time
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
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
    message: str = ""
    has_line_webhook: bool
    has_api_router: bool
    details: dict[str, str] = {}
    subsystems: list[dict[str, str]] = []


class ModulesResponse(BaseModel):
    """Modules response."""

    modules: list[ModuleInfo]
    total: int


class ServiceHealth(BaseModel):
    """Core service health status."""
    
    name: str
    status: str
    message: str = ""
    details: dict[str, str] = {}


class DashboardResponse(BaseModel):
    """Complete dashboard data response."""
    
    server: ServerStatus
    version: str
    environment: str
    services: list[ServiceHealth]
    modules: list[ModuleInfo]


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
        List of modules with their capabilities and detailed status
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
        
        # Get module status from get_status() method
        module_status = module.get_status()
        status = module_status.get("status", "healthy")
        message = module_status.get("message", "")
        details = module_status.get("details", {})
        subsystems = module_status.get("subsystems", [])

        modules_info.append(
            ModuleInfo(
                name=name,
                status=status,
                message=message,
                has_line_webhook=has_line_webhook,
                has_api_router=has_api_router,
                details=details,
                subsystems=subsystems,
            )
        )

    return ModulesResponse(modules=modules_info, total=len(modules_info))


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard_data(
    request: Request,
    admin: CurrentAdmin,
) -> DashboardResponse:
    """
    Get all dashboard data in a single request.
    
    This endpoint aggregates:
    - Server status and uptime
    - Core service health (Ragic, LINE)
    - All module statuses with details
    
    Requires: Admin authentication
    
    Returns:
        Complete dashboard data for rendering status cards
    """
    context = get_app_context()
    registry = get_registry()
    
    # Server status
    running, port = context.get_server_status()
    uptime = time.time() - _start_time
    started_at = datetime.fromtimestamp(_start_time, tz=timezone.utc).isoformat()
    
    server = ServerStatus(
        running=running,
        port=port,
        host=context.config.get("server.host", "127.0.0.1"),
        uptime_seconds=uptime,
        started_at=started_at,
    )
    
    # Core services health check
    services: list[ServiceHealth] = []
    
    # Check Ragic (requires HTTP client from request)
    try:
        from core.ragic.service import create_ragic_service
        http_client = request.app.state.http_client
        ragic_service = create_ragic_service(http_client)
        ragic_health = await ragic_service.check_connection()
        services.append(ServiceHealth(
            name="Ragic",
            status=ragic_health.get("status", "error"),
            message=ragic_health.get("message", ""),
            details=ragic_health.get("details", {}),
        ))
    except Exception as e:
        services.append(ServiceHealth(
            name="Ragic",
            status="error",
            message="Service unavailable",
            details={"Error": str(e)[:50]},
        ))
    
    # Check LINE Bots from Modules
    if registry is not None:
        for module in registry.get_all_modules():
            line_config = module.get_line_bot_config()
            if line_config:
                module_name = module.get_module_name().capitalize()
                service_name = f"LINE Bot ({module_name})"
                
                try:
                    from core.line_client import LineClient
                    # Create dedicated client for this module
                    mod_line_client = LineClient(
                        channel_secret=line_config.get("channel_secret"),
                        access_token=line_config.get("channel_access_token")
                    )
                    
                    line_health = await mod_line_client.check_connection()
                    services.append(ServiceHealth(
                        name=service_name,
                        status=line_health.get("status", "error"),
                        message=line_health.get("message", ""),
                        details=line_health.get("details", {}),
                    ))
                    await mod_line_client.close()
                    
                except Exception as e:
                    services.append(ServiceHealth(
                        name=service_name,
                        status="error",
                        message="Service unavailable",
                        details={"Error": str(e)[:50]},
                    ))

    # Check Core/Admin LINE Bot (if configured globally and distinct)
    # This covers cases where there might be a system-wide bot not tied to a specific module
    # or if the Administrative module uses the global config but we want to fail-safe check it.
    try:
        from core.line_client import LineClient
        # Use global config provider
        line_client = LineClient(config=context.config)
        
        # Only check if globally configured
        if line_client.is_configured():
            # Check if this global bot is already covered by a module to avoid duplicates
            # (Simple heuristic: compare channel secret if possible, or just append distinct name)
            # Since we can't easily peek secrets, we'll name it "System LINE Bot"
            # It might duplicate "LINE Bot (Administrative)" if they share configs, 
            # but that's acceptable for visibility.
            
            line_health = await line_client.check_connection()
            
            # Check for duplicates by Bot ID if available
            bot_id = line_health.get("details", {}).get("Bot ID")
            is_duplicate = False
            for s in services:
                if s.details.get("Bot ID") == bot_id:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                services.append(ServiceHealth(
                    name="System LINE Bot",
                    status=line_health.get("status", "error"),
                    message=line_health.get("message", ""),
                    details=line_health.get("details", {}),
                ))
            
            await line_client.close()
            
    except Exception as e:
         # Only report error if we expected a system bot but it failed
         # If not configured, we ignore
         pass
    
    # Module statuses
    modules_info: list[ModuleInfo] = []
    if registry is not None:
        for module in registry.get_all_modules():
            name = module.get_module_name()
            has_line_webhook = module.get_line_bot_config() is not None
            has_api_router = hasattr(module, "get_api_router") and module.get_api_router() is not None
            
            module_status = module.get_status()
            
            modules_info.append(ModuleInfo(
                name=name,
                status=module_status.get("status", "healthy"),
                message=module_status.get("message", ""),
                has_line_webhook=has_line_webhook,
                has_api_router=has_api_router,
                details=module_status.get("details", {}),
                subsystems=module_status.get("subsystems", []),
            ))
    
    return DashboardResponse(
        server=server,
        version="1.0.0",
        environment="development" if context.config.get("app.debug", True) else "production",
        services=services,
        modules=modules_info,
    )
