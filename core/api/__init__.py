"""
Core API Package.

Provides framework-level API routers used by the server.
"""

from core.api.auth import router as auth_router

__all__ = ["auth_router"]
