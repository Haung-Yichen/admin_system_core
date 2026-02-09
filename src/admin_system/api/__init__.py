"""API module - REST endpoints."""
from api.status_api import router as status_router, init_status_api
from api.admin_auth import router as admin_auth_router, get_current_admin, CurrentAdmin
from api.system import router as system_router

__all__ = [
    "status_router",
    "init_status_api",
    "admin_auth_router",
    "get_current_admin",
    "CurrentAdmin",
    "system_router",
]
