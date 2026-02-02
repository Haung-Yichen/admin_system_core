"""
IAppModule - Abstract Base Class for all application modules.

Follows Interface Segregation Principle (ISP) and Open/Closed Principle (OCP).

Dependency Injection Migration:
    The interface supports two approaches for compatibility:
    
    1. Legacy (current) - Modules receive full AppContext:
        def on_entry(self, context: AppContext) -> None:
            self._config = context.config
            self._log = context.log_event
    
    2. Modern (recommended) - Modules declare explicit dependencies:
        def on_entry(self, context: IModuleContext) -> None:
            # Use only the interface you need
            self._config = context.config
            
        # Or use constructor injection:
        def __init__(self, config: ConfigurationProvider, log: LogService):
            self._config = config
            self._log = log
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from core.app_context import AppContext
    from core.providers import ConfigurationProvider, LogService


# =============================================================================
# Module Context Protocols (Interface Segregation)
# =============================================================================

@runtime_checkable
class IConfigurable(Protocol):
    """Protocol for components that need configuration access."""
    
    @property
    def config(self) -> "ConfigurationProvider":
        """Access configuration."""
        ...


@runtime_checkable
class ILoggable(Protocol):
    """Protocol for components that need logging capability."""
    
    def log_event(self, message: str, level: str = "INFO") -> None:
        """Log an event."""
        ...
    
    def get_event_log(self) -> list[str]:
        """Get event history."""
        ...


@runtime_checkable
class IModuleContext(IConfigurable, ILoggable, Protocol):
    """
    Minimal interface that modules need from the application context.
    
    This protocol defines only what modules typically need:
    - Configuration access
    - Event logging
    
    Modules should depend on this protocol (or even narrower protocols)
    rather than the full AppContext, following ISP.
    
    Example:
        class MyModule(IAppModule):
            def on_entry(self, context: IModuleContext) -> None:
                # Type checker knows context has .config and .log_event
                port = context.config.get("server.port")
                context.log_event("Module initialized")
    """
    pass


# =============================================================================
# Lightweight Module Context (Alternative to AppContext)
# =============================================================================

class ModuleContext:
    """
    Lightweight context implementation for modules.
    
    This can be used as an alternative to passing the full AppContext,
    providing only what modules need.
    
    Example:
        from core.providers import get_configuration_provider, get_log_service
        
        context = ModuleContext(
            config=get_configuration_provider(),
            log_service=get_log_service()
        )
        module.on_entry(context)
    """
    
    def __init__(
        self,
        config: "ConfigurationProvider",
        log_service: "LogService",
    ) -> None:
        self._config = config
        self._log_service = log_service
    
    @property
    def config(self) -> "ConfigurationProvider":
        """Access configuration."""
        return self._config
    
    def log_event(self, message: str, level: str = "INFO") -> None:
        """Log an event."""
        self._log_service.log_event(message, level)
    
    def get_event_log(self) -> list[str]:
        """Get event history."""
        return self._log_service.get_event_log()


# =============================================================================
# Module Interface
# =============================================================================

class IAppModule(ABC):
    """
    Abstract interface for pluggable application modules.
    
    All business modules must implement this interface to be registered.
    
    Dependency Injection Support:
        Modules can opt-in to constructor injection by defining __init__
        with typed parameters. The ModuleRegistry will attempt to resolve
        these dependencies automatically.
        
        Example with explicit dependencies:
            class MyModule(IAppModule):
                def __init__(
                    self,
                    config: ConfigurationProvider = None,
                    log: LogService = None
                ):
                    # Dependencies injected, or use defaults from providers
                    from core.providers import (
                        get_configuration_provider,
                        get_log_service
                    )
                    self._config = config or get_configuration_provider()
                    self._log = log or get_log_service()
    """

    @abstractmethod
    def get_module_name(self) -> str:
        """
        Returns the unique identifier for this module.
        Used for routing and registry lookup.
        
        Returns:
            str: The module's unique name (e.g., 'leave', 'expense')
        """
        pass

    @abstractmethod
    def on_entry(self, context: "AppContext") -> None:
        """
        Called when the module is first loaded/activated.
        Use this for initialization logic.
        
        Args:
            context: The application context containing shared services.
                     Implements IModuleContext protocol - you can type hint
                     this as IModuleContext if you only need config/logging.
                     
        Note:
            For new modules, consider depending on IModuleContext instead
            of the full AppContext to follow Interface Segregation.
            
        Example:
            def on_entry(self, context: IModuleContext) -> None:
                # Only uses config and logging - cleaner interface
                self._config = context.config
                context.log_event(f"{self.get_module_name()} initialized")
        """
        pass

    def handle_event(
        self,
        context: "AppContext",
        event: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        """
        Handles incoming events routed to this module (OPTIONAL).
        
        This method is kept for backward compatibility with legacy modules.
        New modules should implement handle_line_event() instead for LINE
        webhook handling, or define custom API endpoints.
        
        Args:
            context: The application context (implements IModuleContext)
            event: The event payload dictionary
            
        Returns:
            Optional response dictionary
            
        Note:
            Default implementation returns None. Override only if your
            module needs custom internal event handling.
        """
        return None

    def get_menu_config(self) -> dict[str, Any]:
        """
        Returns menu configuration for GUI integration.
        Override this method to provide custom menu items.
        
        Returns:
            dict: Menu configuration with structure:
                  {
                      "label": "Menu Label",
                      "icon": "icon_name",
                      "actions": [...]
                  }
        """
        return {
            "label": self.get_module_name(),
            "icon": None,
            "actions": []
        }

    async def async_startup(self) -> None:
        """
        Called during application startup when the async event loop is running.
        
        Override this method to perform async initialization tasks such as:
        - Starting background sync tasks
        - Setting up LINE Rich Menus
        - Connecting to external services
        
        This is called AFTER on_entry() during the FastAPI lifespan startup,
        ensuring that asyncio.get_running_loop() will succeed.
        
        Note:
            Default implementation does nothing. Override as needed.
        """
        pass

    def on_shutdown(self) -> None:
        """
        Called when the module is being unloaded.
        Override for cleanup logic.
        """
        pass

    def get_status(self) -> dict[str, Any]:
        """
        Returns the current status of the module for dashboard monitoring.
        
        **Dashboard Card SOP (Standard Operating Procedure)**
        
        All modules should implement this method to display status cards
        on the admin dashboard. The returned data will be rendered as a card
        with a status indicator (green/yellow/red) and key-value details.
        
        Returns:
            dict: Status info with structure:
                {
                    "status": "healthy" | "warning" | "error" | "initializing",
                    "message": "Optional status message shown under the title",
                    "details": {
                        "Primary Metric": "100",       # First item shown prominently
                        "Secondary Info": "Normal",    # Additional key-value pairs
                        "Last Sync": "2 min ago",
                    },
                    "subsystems": [                     # Optional: show child system status
                        {"name": "Leave System", "status": "healthy"},
                        {"name": "Expense System", "status": "warning"},
                    ]
                }
        
        Status Values:
            - "healthy": Green indicator - everything working normally
            - "warning": Yellow indicator - degraded but operational
            - "error": Red indicator - critical issue requires attention
            - "initializing": Blue indicator - module is starting up
        
        Example Implementation:
            def get_status(self) -> dict:
                sop_count = self._get_sop_count()
                return {
                    "status": "healthy" if sop_count > 0 else "warning",
                    "message": "Knowledge base loaded",
                    "details": {
                        "SOP Documents": str(sop_count),
                        "Model Status": "Ready",
                    }
                }
        """
        return {
            "status": "healthy",
            "message": "",
            "details": {},
            "subsystems": []
        }

    # =========================================================================
    # LINE Bot Integration (Optional)
    # =========================================================================
    # 以下方法為選擇性實作，若模組需要處理 LINE Webhook 則實作這些方法。
    # 框架會透過這些方法取得模組的 LINE 設定並分派事件。

    def get_line_bot_config(self) -> Optional[dict]:
        """
        Returns LINE Bot configuration for this module.
        
        If the module handles LINE Bot webhooks, implement this method
        to provide the channel credentials. The framework will use these
        to verify webhook signatures.
        
        Returns:
            Optional[dict]: LINE Bot config with structure:
                  {
                      "channel_secret": "...",
                      "channel_access_token": "..."
                  }
                  Returns None if this module does not handle LINE webhooks.
        """
        return None

    async def handle_line_event(
        self,
        event: dict,
        context: "AppContext",
    ) -> Optional[dict]:
        """
        Handle a LINE webhook event routed to this module.
        
        This method is called by the framework after signature verification.
        The event is a single LINE event object (not the full webhook payload).
        
        Args:
            event: A single LINE event dictionary containing:
                   - type: Event type (message, follow, postback, etc.)
                   - replyToken: Token for replying to this event
                   - source: Source object with userId, groupId, etc.
                   - message: (for message events) The message object
            context: The application context for accessing shared services
            
        Returns:
            Optional response dictionary for logging/debugging.
            Note: Actual LINE replies should be sent via LineClient.post_reply()
        """
        return None
