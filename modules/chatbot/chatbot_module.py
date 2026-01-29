"""
Chatbot Module Entry Point.

Implements IAppModule interface for integration with the admin system framework.
"""

import asyncio
import logging
from typing import Any, Dict, Optional, TYPE_CHECKING

from fastapi import APIRouter

from core.interface import IAppModule
from modules.chatbot.core.config import get_chatbot_settings
from modules.chatbot.routers import sop_router

if TYPE_CHECKING:
    from core.app_context import AppContext


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
        # Note: Auth router is now handled by core framework at /auth/*
        # Note: LINE webhook is now handled by core framework at /webhook/line/{module_name}
        self._api_router = APIRouter()
        self._api_router.include_router(sop_router)

        # Preload embedding model to avoid first-query delay
        self._preload_model()

        context.log_event(
            "Chatbot module loaded with LINE Bot SOP search", "CHATBOT")

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

        # Start file watcher for sop_samples.json
        self._start_file_watcher()

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

    def _start_file_watcher(self) -> None:
        """Start file watcher to monitor sop_samples.json and sync changes to DB."""
        import threading
        import json
        import time
        import hashlib
        from pathlib import Path

        self._last_file_hash: str | None = None

        def get_file_hash(filepath: Path) -> str | None:
            """Calculate MD5 hash of file content."""
            if not filepath.exists():
                return None
            try:
                with open(filepath, "rb") as f:
                    return hashlib.md5(f.read()).hexdigest()
            except Exception:
                return None

        # Store reference to main event loop for thread-safe scheduling
        try:
            main_loop = asyncio.get_running_loop()
        except RuntimeError:
            main_loop = None
            logger.warning(
                "No running event loop found, file watcher will use thread-local loop")

        def sync_file_to_db():
            """Sync JSON file content to database."""
            import asyncio
            from sqlalchemy import text, select
            from core.database.session import get_thread_local_session
            from modules.chatbot.services.vector_service import get_vector_service
            from modules.chatbot.models import SOPDocument

            json_path = Path(__file__).parent / "data" / "sop_samples.json"

            # Check if file exists - if not, just skip (don't delete DB data)
            if not json_path.exists():
                logger.info(
                    "sop_samples.json not found, keeping existing DB data.")
                return

            # Check if file changed
            current_hash = get_file_hash(json_path)
            if current_hash == self._last_file_hash:
                return  # No change

            self._last_file_hash = current_hash
            logger.info("sop_samples.json changed, syncing to database...")

            async def do_sync():
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        samples = json.load(f)
                except Exception as e:
                    logger.error(f"Failed to read sop_samples.json: {e}")
                    return

                # 使用框架提供的 Thread-Local Session
                async with get_thread_local_session() as session:
                    vector_service = get_vector_service()

                    for item in samples:
                        original_id = item.get("id")

                        # Check if document exists by original_id
                        stmt = select(SOPDocument).where(
                            SOPDocument.metadata_[
                                'original_id'].astext == original_id
                        )
                        result = await session.execute(stmt)
                        existing_doc = result.scalar_one_or_none()

                        text_to_embed = f"{item['title']}\n\n{item['content']}"
                        # generate_embedding is CPU-bound, safe to call from any thread
                        embedding = vector_service.generate_embedding(
                            text_to_embed)

                        if existing_doc:
                            # Update existing using ORM to ensure encryption works
                            existing_doc.title = item["title"]
                            existing_doc.content = item["content"]
                            existing_doc.category = item.get("category")
                            existing_doc.tags = item.get("tags", [])
                            existing_doc.embedding = embedding
                            # metadata is JSONB, better to update copy
                            meta = dict(existing_doc.metadata_ or {})
                            meta["updated_at"] = time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                            existing_doc.metadata_ = meta

                            logger.info(f"Updated SOP: {item['title']}")
                        else:
                            # Insert new
                            doc = SOPDocument(
                                title=item["title"],
                                content=item["content"],
                                category=item.get("category"),
                                tags=item.get("tags", []),
                                metadata_={"source": "sop_samples.json",
                                           "original_id": original_id},
                                is_published=True,
                                embedding=embedding,
                            )
                            session.add(doc)
                            logger.info(f"Inserted SOP: {item['title']}")

                    await session.commit()
                    logger.info(
                        f"Sync completed: {len(samples)} SOPs processed.")

            try:
                # Use thread-local event loop and session to avoid cross-loop issues
                # This is the safest approach for background threads
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(do_sync())
                finally:
                    loop.close()
            except Exception as e:
                logger.warning(f"Failed to sync SOP data: {e}")
                # Reset hash so next iteration will retry
                self._last_file_hash = None

        def watch_loop():
            """Watch loop that checks file every 5 seconds."""
            # Initial sync on startup
            time.sleep(5)  # Wait for model to load
            sync_file_to_db()

            while True:
                time.sleep(5)  # Check every 5 seconds
                try:
                    sync_file_to_db()
                except Exception as e:
                    logger.warning(f"File watcher error: {e}")

        # Run watcher in background thread
        thread = threading.Thread(target=watch_loop, daemon=True)
        thread.start()
        logger.info("File watcher started for sop_samples.json")

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
            is_auth, auth_messages = await line_auth_check(user_id, db)

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
            is_auth, auth_messages = await line_auth_check(user_id, db)

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
