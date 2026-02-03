"""
Admin System Core - Entry Point.

Headless ASGI application for uvicorn execution.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Or run directly:
    python main.py
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.app_context import AppContext
from core.database import close_db_connections, init_database
from core.http_client import create_http_client_context
from core.logging_config import setup_logging
from core.registry import ModuleLoader, ModuleRegistry
from core.server import create_base_app, set_registry

# Module directory path
MODULES_DIR = "modules"


# -----------------------------------------------------------------------------
# Core Sync Service Registration
# -----------------------------------------------------------------------------


def _register_core_sync_services() -> None:
    """
    Register framework-level Ragic sync services.
    
    Core sync services handle data that is shared across all modules,
    such as User Identity (LINE <-> Email binding).
    
    This follows the same pattern as module-level sync services but
    is registered by the framework during startup.
    """
    from core.ragic import get_sync_manager
    from core.services.user_sync import get_user_sync_service
    
    logger = logging.getLogger(__name__)
    sync_manager = get_sync_manager()
    
    try:
        sync_manager.register(
            key="core_user",
            name="User Identity (LINE Binding)",
            service=get_user_sync_service(),
            module_name="core",
            auto_sync_on_startup=True,  # Sync user data on startup
        )
        logger.info("Registered core_user sync service")
    except Exception as e:
        logger.error(f"Failed to register UserSyncService: {e}")


# -----------------------------------------------------------------------------
# Application Factory
# -----------------------------------------------------------------------------


def create_app_context() -> AppContext:
    """Create and configure the AppContext."""
    return AppContext()


def create_registry(context: AppContext) -> ModuleRegistry:
    """Create and configure the ModuleRegistry with loaded modules."""
    registry = ModuleRegistry()
    registry.set_context(context)

    # Load modules from /modules directory
    modules_path = Path(__file__).parent / MODULES_DIR
    loader = ModuleLoader(registry)
    count = loader.load_from_directory(str(modules_path))
    context.log_event(f"Loaded {count} module(s) from {MODULES_DIR}/", "LOADER")

    return registry


def create_fastapi_app(context: AppContext, registry: ModuleRegistry) -> FastAPI:
    """Create the FastAPI application with all routers configured."""
    from api.admin_auth import router as admin_auth_router
    from api.status_api import init_status_api
    from api.system import router as system_router
    from api.system import set_app_context as set_system_context
    from api.system import set_registry as set_system_registry
    from api.webhooks import router as webhooks_router

    # Create base FastAPI app with webhook routes
    app = create_base_app(context, registry)

    # Set registry for dynamic webhook routing
    set_registry(app, registry)

    # Set shared context and registry for system API
    set_system_context(context)
    set_system_registry(registry)

    # Register admin auth router
    app.include_router(admin_auth_router, prefix="/api")

    # Register system router (protected by admin auth)
    app.include_router(system_router, prefix="/api")

    # Register unified webhooks router (Ragic, etc.)
    app.include_router(webhooks_router, prefix="/api")

    # Add status API
    status_router = init_status_api(context, registry)
    app.include_router(status_router)

    # Register module API routers
    for name, module in registry._modules.items():
        if hasattr(module, "get_api_router"):
            module_router = module.get_api_router()
            if module_router is not None:
                app.include_router(module_router, prefix="/api")
                context.log_event(f"Registered API router for module: {name} at /api", "LOADER")

    # Mount static files for web dashboard
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Mount core framework static files (auth pages, etc.)
    core_static_dir = Path(__file__).parent / "core" / "static"
    if core_static_dir.exists():
        app.mount("/static/core", StaticFiles(directory=str(core_static_dir)), name="core-static")

    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Handles startup and shutdown events.
    Properly manages HTTP client lifecycle via dependency injection.
    """
    logger = logging.getLogger(__name__)

    # Startup
    logger.info("Starting Admin System Core...")

    # Initialize HTTP client with proper lifecycle management
    # The HTTP client is stored in app.state for dependency injection in routes
    # Background tasks create their own isolated clients (RAII pattern)
    async with create_http_client_context(app, timeout=30.0, max_connections=100) as http_manager:
        logger.info("HTTP client initialized (stored in app.state for DI)")

        try:
            await init_database()
            logger.info("Database initialized")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

        # Register core sync services (User Identity Ragic sync)
        _register_core_sync_services()
        logger.info("Core sync services registered")

        # Start background sync for all registered Ragic services
        # Note: Background sync creates its own HTTP client (thread isolation)
        from core.ragic import get_sync_manager
        sync_manager = get_sync_manager()
        sync_manager.start_background_sync()
        logger.info("Ragic sync manager started")

        # Call async_startup on all modules (event loop is now running)
        if _registry:
            await _registry.async_startup_all()
            logger.info("Module async startup completed")

        # Update server status
        context = _context
        if context:
            context.set_server_status(True, context.config.get("server.port", 8000))
            context.log_event("Application started successfully", "SUCCESS")

        yield

        # Shutdown
        logger.info("Shutting down Admin System Core...")

        if _registry:
            _registry.shutdown_all()

        await close_db_connections()
        logger.info("Cleanup complete")


# -----------------------------------------------------------------------------
# Module-level Application Instance
# -----------------------------------------------------------------------------

# Setup logging first
setup_logging()

# Create core components
_context = create_app_context()
_registry = create_registry(_context)

# Create FastAPI app with lifespan
_app = create_fastapi_app(_context, _registry)
_app.router.lifespan_context = lifespan

# Export for uvicorn
app = _app


# -----------------------------------------------------------------------------
# Direct Execution
# -----------------------------------------------------------------------------


def main() -> None:
    """Run the application directly with uvicorn."""
    host = _context.config.get("server.host", "127.0.0.1")
    port = _context.config.get("server.port", 8000)
    debug = _context.config.get("app.debug", False)

    uvicorn_config = {
        "host": host,
        "port": port,
        "reload": debug,
        "log_level": "warning",  # Suppress uvicorn info logs
        "access_log": False,     # Disable uvicorn access logs
    }

    # If reload is enabled, exclude logs and cache directories
    if debug:
        uvicorn_config["reload_excludes"] = [
            "logs/*",
            "**/__pycache__/*",
            "**/*.pyc",
            ".venv/*",
            "*.log",
        ]

    uvicorn.run("main:app", **uvicorn_config)


if __name__ == "__main__":
    main()
