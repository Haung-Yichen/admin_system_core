"""API module - REST endpoints."""
from api.status_api import router, init_status_api

__all__ = ["router", "init_status_api"]
