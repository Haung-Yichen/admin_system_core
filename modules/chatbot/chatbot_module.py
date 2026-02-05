"""
Chatbot Module Entry Point.

Implements IAppModule interface for integration with the admin system framework.
"""

import asyncio
import logging
import threading
from typing import Any, Dict, Optional, TYPE_CHECKING

from fastapi import APIRouter

from core.interface import IAppModule
from core.ragic import get_sync_manager
from modules.chatbot.core.config import get_chatbot_settings
from modules.chatbot.routers import sop_router
from modules.chatbot.services.ragic_sync import get_sop_sync_service

if TYPE_CHECKING:
    from core.app_context import AppContext


logger = logging.getLogger(__name__)


class ChatbotModule(IAppModule):
    """
    SOP Chatbot Module.

    Provides LINE Bot integration for SOP search with Magic Link authentication.
    
    Features:
        - SOP knowledge base synced from Ragic on startup
        - Webhook endpoint for real-time Ragic updates
        - Vector embedding search for SOP queries
        - LINE Bot integration
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
        logger.info("Chatbot module initializing...")

        # Build the aggregated API router
        # Note: Auth router is now handled by core framework at /auth/*
        # Note: LINE webhook is now handled by core framework at /webhook/line/{module_name}
        # Note: Ragic webhook is now handled by core framework at /api/webhooks/ragic?source=chatbot_sop
        self._api_router = APIRouter()
        self._api_router.include_router(sop_router)

        # Register SOP sync service with the core SyncManager
        # The SyncManager handles background sync on startup and webhook dispatch
        sync_manager = get_sync_manager()
        sync_manager.register(
            key="chatbot_sop",
            name="SOP Knowledge Base",
            service=get_sop_sync_service(),
            module_name=self.get_module_name(),
            auto_sync_on_startup=True,
        )

        # Preload embedding model to avoid first-query delay
        self._preload_model()

        context.log_event(
            "Chatbot module loaded with LINE Bot SOP search", "CHATBOT")
        logger.info("Chatbot module initialized")

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
            from core.database.session import get_thread_local_session

            # Create a dedicated event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def fetch_stats():
                # 使用框架提供的 Thread-Local Session
                async with get_thread_local_session() as session:
                    res_sop = await session.execute(text("SELECT count(*) FROM sop_documents"))
                    count_sop = res_sop.scalar() or 0

                    res_users = await session.execute(text("SELECT count(*) FROM users"))
                    count_users = res_users.scalar() or 0

                    return count_sop, count_users

            while True:
                try:
                    sop_count, user_count = loop.run_until_complete(
                        fetch_stats())
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

        This module primarily handles events via its API routers
        and LINE webhook handlers.
        """
        event_type = event.get("type", "")
        content = event.get("content", "")

        # Basic echo for direct events
        return {
            "success": True,
            "module": self.get_module_name(),
            "message": f"Chatbot received: {content}"
        }

    # =========================================================================
    # LINE Bot Integration (框架化介面實作)
    # =========================================================================

    def get_line_bot_config(self) -> Optional[Dict[str, str]]:
        """
        Return LINE Bot configuration for framework-level webhook handling.

        The framework uses this to verify webhook signatures before
        dispatching events to handle_line_event().

        Returns:
            dict: LINE channel credentials from module settings.
        """
        try:
            settings = get_chatbot_settings()
            return {
                "channel_secret": settings.line_channel_secret.get_secret_value(),
                "channel_access_token": settings.line_channel_access_token.get_secret_value(),
            }
        except Exception as e:
            logger.error(f"Failed to load LINE bot config: {e}")
            return None

    async def handle_line_event(
        self,
        event: Dict[str, Any],
        context: "AppContext",
    ) -> Optional[Dict[str, Any]]:
        """
        Handle a LINE webhook event dispatched by the framework.

        This is the main entry point for LINE event processing.
        The framework has already verified the webhook signature.

        Args:
            event: A single LINE event (message, follow, postback, etc.)
            context: Application context for logging
        """
        event_type = event.get("type")
        reply_token = event.get("replyToken")
        source = event.get("source", {})
        user_id = source.get("userId")

        if not user_id:
            logger.warning("LINE event without userId, skipping")
            return {"status": "skipped", "reason": "no userId"}

        logger.info(
            f"Processing LINE event: {event_type} from user: {user_id}")

        try:
            if event_type == "follow":
                await self._handle_follow_event(user_id, reply_token)
            elif event_type == "message":
                message_data = event.get("message", {})
                if message_data.get("type") == "text":
                    text = message_data.get("text", "").strip()
                    await self._handle_text_message(user_id, text, reply_token)
            else:
                logger.debug(f"Unhandled LINE event type: {event_type}")

            return {"status": "ok", "event_type": event_type}

        except Exception as e:
            logger.error(f"Error handling LINE event: {e}")
            return {"status": "error", "error": str(e)}

    async def _handle_follow_event(self, user_id: str, reply_token: str | None) -> None:
        """Handle LINE follow event (user added the bot)."""
        if not reply_token:
            return

        from core.database.session import get_thread_local_session
        from core.line_auth import line_auth_check, LineAuthMessages
        from modules.chatbot.services import get_line_service

        line_service = get_line_service()

        async with get_thread_local_session() as db:
            is_auth, auth_messages = await line_auth_check(user_id, db, app_context="chatbot")

        if is_auth:
            await line_service.reply(reply_token, [
                {"type": "text", "text": "👋 歡迎回來！您可以直接輸入問題查詢 SOP。"}
            ])
        else:
            # 使用框架統一的驗證訊息
            welcome_msg = {"type": "text", "text": "👋 歡迎使用 HSIB SOP Bot！"}
            await line_service.reply(reply_token, [welcome_msg] + auth_messages)

    async def _handle_text_message(
        self, user_id: str, text: str, reply_token: str | None
    ) -> None:
        """Handle LINE text message event (SOP search)."""
        if not reply_token:
            return

        from core.database.session import get_thread_local_session
        from core.line_auth import line_auth_check
        from modules.chatbot.services import get_line_service, get_vector_service
        from modules.chatbot.routers.bot import (
            create_sop_result_flex,
            create_no_result_flex,
        )

        line_service = get_line_service()
        vector_service = get_vector_service()

        async with get_thread_local_session() as db:
            # 使用框架統一的驗證機制
            is_auth, auth_messages = await line_auth_check(user_id, db, app_context="chatbot")

            if not is_auth:
                await line_service.reply(reply_token, auth_messages)
                return

            try:
                result = await vector_service.get_best_match(text, db)

                if result:
                    doc, similarity = result
                    flex_content = create_sop_result_flex(
                        doc.title, doc.content, similarity, doc.category
                    )
                    await line_service.reply(reply_token, [
                        {"type": "flex", "altText": f"SOP: {doc.title}",
                            "contents": flex_content}
                    ])
                else:
                    flex_content = create_no_result_flex(text)
                    await line_service.reply(reply_token, [
                        {"type": "flex", "altText": "找不到相關 SOP",
                            "contents": flex_content}
                    ])

            except Exception as e:
                logger.error(f"Search error: {e}")
                await line_service.reply(reply_token, [
                    {"type": "text", "text": "⚠️ 搜尋時發生錯誤，請稍後再試。"}
                ])

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
        - Ragic sync status
        """
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

        # 3. DB Stats (from background updater)
        if hasattr(self, "_stats"):
            details["SOP Documents"] = str(self._stats.get("sop_count", 0))
            details["LINE Users"] = str(self._stats.get("user_count", 0))
        
        # 4. Ragic Sync Status (from core SyncManager)
        try:
            sync_manager = get_sync_manager()
            sync_info = sync_manager.get_service_info("chatbot_sop")
            if sync_info:
                details["Ragic Sync"] = sync_info.status.capitalize()
                if sync_info.last_sync_result:
                    details["SOPs Synced"] = str(sync_info.last_sync_result.synced)
                    if sync_info.last_sync_result.errors > 0:
                        details["Sync Errors"] = str(sync_info.last_sync_result.errors)
                if sync_info.last_sync_time:
                    details["Last Sync"] = sync_info.last_sync_time.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            details["Ragic Sync"] = "Error"
            logger.warning(f"Error getting sync status: {e}")

        return {
            "status": status,
            "details": details
        }
