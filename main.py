"""
Admin System Core - Entry Point.

Headless ASGI application for uvicorn execution.
Removed PyQt GUI dependencies.

Usage:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Or run directly:
    python main.py
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from core.app_context import AppContext
from core.database import close_db_connections, init_database
from core.logging_config import setup_logging
from core.registry import ModuleLoader, ModuleRegistry
from core.router import EventRouter, WebhookDispatcher
from core.server import FastAPIServer

# Module directory path
MODULES_DIR = "modules"


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
    from api.system import router as system_router, set_app_context, set_registry
    from api.webhooks import router as webhooks_router
    from core.api.auth import router as auth_router

    # Create FastAPIServer instance for webhook handling
    port = context.config.get("server.port", 8000)
    server = FastAPIServer(context, port=port, registry=registry)

    # Create router and dispatcher for webhook handling
    router = EventRouter(registry, context)
    webhook_dispatcher = WebhookDispatcher(router, context)

    def handle_webhook(payload: dict) -> dict:
        """Handle incoming webhook events."""
        if "events" in payload:  # LINE webhook
            return webhook_dispatcher.dispatch_line_webhook(payload)
        else:
            return router.route(payload)

    server.set_webhook_handler(handle_webhook)

    # Get the FastAPI app from server
    app = server.app

    # Set shared context and registry for system API
    set_app_context(context)
    set_registry(registry)

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

    return app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Handles startup and shutdown events.
    """
    logger = logging.getLogger(__name__)

    # Startup
    logger.info("Starting Admin System Core...")

    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Start background sync for all registered Ragic services
    from core.ragic import get_sync_manager
    sync_manager = get_sync_manager()
    sync_manager.start_background_sync()
    logger.info("Ragic sync manager started")

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
        "log_level": "info",
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
