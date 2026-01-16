"""
IAppModule - Abstract Base Class for all application modules.
Follows Interface Segregation Principle (ISP) and Open/Closed Principle (OCP).
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.app_context import AppContext


class IAppModule(ABC):
    """
    Abstract interface for pluggable application modules.
    All business modules must implement this interface to be registered.
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
            context: The application context containing shared services
        """
        pass

    @abstractmethod
    def handle_event(self, context: "AppContext", event: dict) -> Optional[dict]:
        """
        Handles incoming events routed to this module.
        
        Args:
            context: The application context containing shared services
            event: The event payload dictionary
            
        Returns:
            Optional response dictionary
        """
        pass

    def get_menu_config(self) -> dict:
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

    def on_shutdown(self) -> None:
        """
        Called when the module is being unloaded.
        Override for cleanup logic.
        """
        pass

    def get_status(self) -> dict:
        """
        Returns the current status of the module for monitoring.
        
        Returns:
            dict: Status info with structure:
                  {
                      "status": "active" | "warning" | "error" | "initializing",
                      "details": { "key": "value" }
                  }
        """
        return {
            "status": "active",
            "details": {}
        }
