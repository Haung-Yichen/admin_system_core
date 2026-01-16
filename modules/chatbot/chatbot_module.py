"""
Chatbot Module Entry Point.

Implements IAppModule interface for integration with the admin system framework.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter

from core.interface import IAppModule
from modules.chatbot.routers import auth_router, bot_router, sop_router


logger = logging.getLogger(__name__)


class ChatbotModule(IAppModule):
    """
    SOP Chatbot Module.
    
    Provides LINE Bot integration for SOP search with Magic Link authentication.
    """
    
    def __init__(self) -> None:
        self._context = None
        self._api_router: Optional[APIRouter] = None
    
    def get_module_name(self) -> str:
        return "chatbot"
    
    def on_entry(self, context: Any) -> None:
        """
        Initialize the chatbot module.
        
        Args:
            context: Application context from the main framework.
        """
        self._context = context
        logger.info("Chatbot module initialized")
        
        # Build the aggregated API router
        self._api_router = APIRouter()
        self._api_router.include_router(auth_router)
        self._api_router.include_router(bot_router)
        self._api_router.include_router(sop_router)
        
        # Preload embedding model to avoid first-query delay
        self._preload_model()
        
        context.log_event("Chatbot module loaded with LINE Bot SOP search", "CHATBOT")
    
    def _preload_model(self) -> None:
        """Preload the embedding model in background to reduce first query latency."""
        import threading
        
        def load():
            try:
                from modules.chatbot.services.vector_service import get_vector_service
                service = get_vector_service()
                service._get_model()  # Trigger model loading
                logger.info("Embedding model preloaded successfully")
            except Exception as e:
                logger.warning(f"Failed to preload embedding model: {e}")
        
        # Load in background thread to not block startup
        thread = threading.Thread(target=load, daemon=True)
        thread.start()
        
        # Start stats updater
        self._start_stats_updater()

    def _start_stats_updater(self) -> None:
        """Start a background thread to update module stats periodically."""
        import threading
        import time
        
        self._stats = {"sop_count": 0, "user_count": 0}
        
        def update_loop():
            import asyncio
            from sqlalchemy import text
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
            from core.app_context import ConfigLoader
            from modules.chatbot.core.config import get_chatbot_settings
            
            # Create a dedicated event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Create a dedicated engine for this thread's loop
            settings = get_chatbot_settings()
            config_loader = ConfigLoader()
            config_loader.load()
            database_url = config_loader.get("database.url", "")
            
            engine = create_async_engine(
                str(database_url),
                echo=False,
                pool_pre_ping=True,
                pool_size=2,
                max_overflow=0,
            )
            session_factory = async_sessionmaker(
                bind=engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            
            async def fetch_stats():
                async with session_factory() as session:
                    res_sop = await session.execute(text("SELECT count(*) FROM sop_documents"))
                    count_sop = res_sop.scalar() or 0
                    
                    res_users = await session.execute(text("SELECT count(*) FROM users"))
                    count_users = res_users.scalar() or 0
                    
                    return count_sop, count_users
            
            while True:
                try:
                    sop_count, user_count = loop.run_until_complete(fetch_stats())
                    self._stats["sop_count"] = sop_count
                    self._stats["user_count"] = user_count
                except Exception as e:
                    logger.warning(f"Failed to update chatbot stats: {e}")
                
                time.sleep(30)  # Update every 30 seconds
        
        stats_thread = threading.Thread(target=update_loop, daemon=True)
        stats_thread.start()

    def handle_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle events routed to this module.
        
        This module primarily handles events via its API routers,
        but can also process events from the EventRouter if needed.
        """
        event_type = event.get("type", "")
        content = event.get("content", "")
        
        # Basic echo for direct events
        return {
            "success": True,
            "module": self.get_module_name(),
            "message": f"Chatbot received: {content}"
        }
    
    def get_menu_config(self) -> Optional[Dict[str, Any]]:
        """Return menu configuration for GUI integration."""
        return {
            "icon": "💬",
            "title": "SOP Bot",
            "description": "LINE Bot for SOP search",
        }
    
    def get_api_router(self) -> Optional[APIRouter]:
        """
        Return the aggregated API router for this module.
        
        This method is called by the main application to register
        the module's API endpoints with the FastAPI server.
        
        Returns:
            APIRouter: Combined router with auth, bot, and sop endpoints.
        """
        return self._api_router
    
    def on_shutdown(self) -> None:
        """Cleanup when module is shutting down."""
        logger.info("Chatbot module shutting down")

    def get_status(self) -> Dict[str, Any]:
        """
        Return the current status of the module for monitoring.
        
        Exposes:
        - Embedding model status
        - Rate limiter statistics
        """
        from modules.chatbot.core.rate_limiter import magic_link_limiter
        from modules.chatbot.services.vector_service import get_vector_service
        
        status = "active"
        details = {}
        
        # 1. Check Vector Model Status
        try:
            svc = get_vector_service()
            # Check if model is loaded (checking private attribute _model)
            is_loaded = svc._model is not None
            details["Embedding Model"] = svc._model_name
            details["Model Status"] = "Ready" if is_loaded else "Loading..."
            details["Device"] = svc.get_device()
            
            if not is_loaded:
                status = "initializing"
        except Exception as e:
            details["Vector Service"] = "Error"
            logger.error(f"Error getting vector service status: {e}")
            status = "error"

        # 2. Check Rate Limiter Stats
        try:
            # simplistic count of tracked IPs
            tracked_count = len(magic_link_limiter._requests)
            details["Active IPs"] = str(tracked_count)
        except Exception:
            details["Rate Limiter"] = "Unavailable"
            
        # 3. DB Stats (from background updater)
        if hasattr(self, "_stats"):
            details["SOP Documents"] = str(self._stats.get("sop_count", 0))
            details["LINE Users"] = str(self._stats.get("user_count", 0))

        return {
            "status": status,
            "details": details
        }
