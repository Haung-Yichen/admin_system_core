"""
Status API - System health and monitoring endpoints.
Provides endpoints for external monitoring integration.
"""
from typing import Any, Dict, List, TYPE_CHECKING
import platform

from fastapi import APIRouter
import psutil

if TYPE_CHECKING:
    from core.app_context import AppContext
    from core.registry import ModuleRegistry


# Global references set during initialization
_context: "AppContext" = None  # type: ignore
_registry: "ModuleRegistry" = None  # type: ignore

router = APIRouter(prefix="/api", tags=["status"])


def init_status_api(context: "AppContext", registry: "ModuleRegistry") -> APIRouter:
    """
    Initialize the status API with required dependencies.
    
    Args:
        context: Application context
        registry: Module registry
        
    Returns:
        Configured APIRouter
    """
    global _context, _registry
    _context = context
    _registry = registry
    return router


@router.get("/status")
async def get_status() -> Dict[str, Any]:
    """
    Get system status and loaded modules.
    
    Returns:
        JSON with status information
    """
    server_running, server_port = _context.get_server_status()
    
    return {
        "status": "running" if server_running else "stopped",
        "port": server_port,
        "modules_loaded": _registry.get_module_names() if _registry else []
    }


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Simple health check endpoint."""
    return {"status": "healthy"}


@router.get("/system")
async def get_system_info() -> Dict[str, Any]:
    """
    Get detailed system information.
    
    Returns:
        JSON with system metrics
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": platform.python_version()
        },
        "cpu": {
            "percent": cpu_percent,
            "cores": psutil.cpu_count(),
            "cores_physical": psutil.cpu_count(logical=False)
        },
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        }
    }


@router.get("/modules")
async def get_modules() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get detailed information about loaded modules.
    
    Returns:
        JSON with module details
    """
    modules_info = []
    
    if _registry:
        for module in _registry.get_all_modules():
            modules_info.append({
                "name": module.get_module_name(),
                "menu_config": module.get_menu_config()
            })
    
    return {"modules": modules_info}


@router.get("/logs")
async def get_logs(limit: int = 100) -> Dict[str, List[str]]:
    """
    Get recent event logs.
    
    Args:
        limit: Maximum number of log entries to return
        
    Returns:
        JSON with log entries
    """
    logs = _context.get_event_log() if _context else []
    return {"logs": logs[-limit:]}
