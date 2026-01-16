"""
Router - Event dispatcher for routing messages to appropriate modules.
Implements Single Responsibility Principle (SRP).
"""
from typing import Optional, Dict, Any, Tuple
import logging
import re

from core.registry import ModuleRegistry
from core.app_context import AppContext


class EventRouter:
    """
    Routes incoming events to the appropriate module handlers.
    
    Event Format:
        - Prefixed: "module_name:action:data" -> routed to specific module
        - Generic: JSON payload with "module" field -> routed by field value
    """
    
    def __init__(self, registry: ModuleRegistry, context: AppContext) -> None:
        self._registry = registry
        self._context = context
        self._logger = logging.getLogger(__name__)
        
        # Regex pattern for module:action:data prefix format
        self._prefix_pattern = re.compile(r'^(\w+):(.*)$')
    
    def parse_message(self, message: str) -> Tuple[Optional[str], str]:
        """
        Parse a message to extract module name and payload.
        
        Args:
            message: Raw message string
            
        Returns:
            Tuple of (module_name, payload)
        """
        match = self._prefix_pattern.match(message)
        if match:
            module_name = match.group(1)
            payload = match.group(2)
            return (module_name, payload)
        
        return (None, message)
    
    def route(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Route an event to the appropriate module.
        
        Args:
            event: Event dictionary containing:
                   - "type": Event type (webhook, internal, etc.)
                   - "source": Event source identifier
                   - "message": The event message/payload
                   - "module": (optional) Explicit module target
                   
        Returns:
            Response dictionary from the handler or None
        """
        # Extract module target from event
        module_name: Optional[str] = None
        
        # First, check for explicit module field
        if "module" in event:
            module_name = event["module"]
        
        # Second, try to parse from message prefix
        elif "message" in event and isinstance(event["message"], str):
            parsed_module, parsed_payload = self.parse_message(event["message"])
            if parsed_module:
                module_name = parsed_module
                event["parsed_payload"] = parsed_payload
        
        # Route to module
        if module_name:
            return self._dispatch_to_module(module_name, event)
        
        # No module found - broadcast to default handler or log
        self._context.log_event(f"Unrouted event: {event.get('type', 'unknown')}", "WARN")
        return {"status": "unrouted", "message": "No module handler found"}
    
    def _dispatch_to_module(
        self, 
        module_name: str, 
        event: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Dispatch event to a specific module.
        
        Args:
            module_name: Target module name
            event: Event dictionary
            
        Returns:
            Response from module handler
        """
        module = self._registry.get_module(module_name)
        
        if module is None:
            self._logger.warning(f"Module '{module_name}' not found for routing.")
            self._context.log_event(f"Module '{module_name}' not found", "ERROR")
            return {"status": "error", "message": f"Module '{module_name}' not found"}
        
        try:
            self._context.log_event(f"Routing to '{module_name}'", "INFO")
            response = module.handle_event(self._context, event)
            self._context.log_event(f"Module '{module_name}' handled event", "SUCCESS")
            return response
            
        except Exception as e:
            self._logger.error(f"Error in module '{module_name}' handler: {e}")
            self._context.log_event(f"Error in '{module_name}': {e}", "ERROR")
            return {"status": "error", "message": str(e)}
    
    def broadcast(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Broadcast an event to all registered modules.
        
        Args:
            event: Event dictionary to broadcast
            
        Returns:
            Dictionary of module responses
        """
        responses: Dict[str, Any] = {}
        
        for module in self._registry.get_all_modules():
            module_name = module.get_module_name()
            try:
                response = module.handle_event(self._context, event)
                responses[module_name] = response
            except Exception as e:
                responses[module_name] = {"error": str(e)}
                self._logger.error(f"Broadcast error in '{module_name}': {e}")
        
        return responses


class WebhookDispatcher:
    """
    Specialized dispatcher for LINE webhook events.
    """
    
    def __init__(self, router: EventRouter, context: AppContext) -> None:
        self._router = router
        self._context = context
        self._logger = logging.getLogger(__name__)
    
    def dispatch_line_webhook(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and dispatch LINE webhook payload.
        
        Args:
            payload: LINE webhook payload
            
        Returns:
            Response dictionary
        """
        events = payload.get("events", [])
        responses = []
        
        for event in events:
            event_type = event.get("type", "unknown")
            self._context.log_event(f"LINE webhook: {event_type}", "WEBHOOK")
            
            # Transform LINE event to internal format
            internal_event = {
                "type": "line_webhook",
                "source": event.get("source", {}),
                "reply_token": event.get("replyToken"),
                "event_type": event_type,
                "message": event.get("message", {}).get("text", ""),
                "raw": event
            }
            
            response = self._router.route(internal_event)
            responses.append(response)
        
        return {"processed": len(responses), "responses": responses}
