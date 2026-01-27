"""
Admin System Core - Entry Point.
Initializes all components and starts the application.
"""
import sys
import logging
from typing import Dict, Any

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

from core.app_context import AppContext
from core.registry import ModuleRegistry, ModuleLoader
from core.router import EventRouter, WebhookDispatcher
from core.server import FastAPIServer
from core.logging_config import setup_logging
from gui.splash import AnimatedSplashScreen
from gui.main_window import MainWindow
from gui.tray_icon import SystemTrayManager
from api.status_api import init_status_api

# 模組目錄路徑
MODULES_DIR = "modules"


class AdminSystemApp:
    """Main application orchestrator."""
    
    def __init__(self) -> None:
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        
        # Core components
        self._context = AppContext()
        
        # Connect logging to GUI
        from core.logging_config import GUIHandler
        GUIHandler.set_context(self._context)
        
        self._registry = ModuleRegistry()
        self._registry.set_context(self._context)
        
        # Load modules from /modules directory
        self._load_modules()
        
        # Router
        self._router = EventRouter(self._registry, self._context)
        self._webhook_dispatcher = WebhookDispatcher(self._router, self._context)
        
        # Server (注入 registry 以支援動態 LINE webhook 路由)
        port = self._context.config.get("server.port", 8000)
        self._server = FastAPIServer(self._context, port=port, registry=self._registry)
        self._server.set_webhook_handler(self._handle_webhook)
        
        # Register module API routers
        self._register_module_routers()
        
        # Add status API
        status_router = init_status_api(self._context, self._registry)
        self._server.add_router(status_router)
        
        # GUI (initialized later)
        self._main_window: MainWindow = None  # type: ignore
        self._tray: SystemTrayManager = None  # type: ignore
        self._splash: AnimatedSplashScreen = None  # type: ignore
    
    def _register_module_routers(self) -> None:
        """Register API routers from all modules that have get_api_router()."""
        for name, module in self._registry._modules.items():
            if hasattr(module, 'get_api_router'):
                router = module.get_api_router()
                if router is not None:
                    # Mount all module routers under /api prefix
                    # This ensures paths like /api/administrative/... and /api/sop/... work as expected
                    self._server.add_router(router, prefix="/api")
                    self._context.log_event(f"Registered API router for module: {name} at /api", "LOADER")
    
    def _load_modules(self) -> None:
        """Load all modules from the modules directory."""
        from pathlib import Path
        modules_path = Path(__file__).parent / MODULES_DIR
        
        loader = ModuleLoader(self._registry)
        count = loader.load_from_directory(str(modules_path))
        self._context.log_event(f"Loaded {count} module(s) from {MODULES_DIR}/", "LOADER")
    
    def _handle_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming webhook events."""
        if "events" in payload:  # LINE webhook
            return self._webhook_dispatcher.dispatch_line_webhook(payload)
        else:
            return self._router.route(payload)
    
    def _init_gui(self) -> None:
        """Initialize GUI components after splash."""
        self._main_window = MainWindow(self._context, self._registry)
        self._tray = SystemTrayManager()
        
        # Connect signals
        self._tray.show_window_requested.connect(self._show_main_window)
        self._tray.exit_requested.connect(self._exit_app)
        self._main_window.close_to_tray.connect(self._on_minimize_to_tray)
        
        # Start server
        self._server.start()
        self._tray.update_server_status(True, self._context.config.get("server.port", 8000))
        
        # Show GUI
        self._tray.show()
        self._main_window.show()
        
        self._context.log_event("Application started successfully", "SUCCESS")
    
    def _show_main_window(self) -> None:
        """Show and activate the main window."""
        self._main_window.show()
        self._main_window.activateWindow()
        self._main_window.raise_()
    
    def _on_minimize_to_tray(self) -> None:
        """Handle minimize to tray event."""
        self._tray.show_notification("Admin System", "Running in background")
    
    def _exit_app(self) -> None:
        """Clean shutdown of the application."""
        self._context.log_event("Shutting down...", "INFO")
        self._server.stop()
        self._server.join(timeout=3.0)
        self._registry.shutdown_all()
    # Windows-specific: Add slight delay or dummy async call to let ProactorLoop finish
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.stop()
        except Exception:
            pass
            
        self._app.quit()

    
    def run(self) -> int:
        """Run the application."""
        # Show splash screen
        self._splash = AnimatedSplashScreen()
        self._splash.show_loading_sequence(self._init_gui)
        
        return self._app.exec()


def main() -> None:
    """Application entry point."""
    setup_logging()
    app = AdminSystemApp()
    sys.exit(app.run())


if __name__ == "__main__":
    main()
