"""
Administrative Module Entry Point.

Implements IAppModule interface for integration with the admin system framework.
Handles Leave Request System and data synchronization from Ragic.
"""

import asyncio
import logging
import re
import threading
from typing import Any, Optional, TYPE_CHECKING

from fastapi import APIRouter

from core.interface import IAppModule
from modules.administrative.core.config import get_admin_settings
from modules.administrative.routers import leave_router, liff_router
from modules.administrative.services.ragic_sync import RagicSyncService

if TYPE_CHECKING:
    from core.app_context import AppContext

logger = logging.getLogger(__name__)


class AdministrativeModule(IAppModule):
    """
    Administrative Module for Leave Request System.

    Features:
        - Leave request submission via LINE LIFF
        - Employee/Department data sync from Ragic
        - Auto-routing of approvals based on org hierarchy
        - LINE Flex Message menu integration

    Startup:
        - Syncs Employee and Department cache from Ragic
        - Registers API routers
    """

    # Trigger keywords for showing the admin menu
    MENU_TRIGGERS = ["行政", "admin", "選單", "menu", "請假", "leave"]

    def __init__(self) -> None:
        self._context: Optional["AppContext"] = None
        self._api_router: Optional[APIRouter] = None
        self._sync_service: Optional[RagicSyncService] = None
        self._sync_status: dict[str, Any] = {
            "status": "pending",
            "employees": 0,
            "departments": 0,
            "last_error": None,
        }
        self._settings = get_admin_settings()

    def get_module_name(self) -> str:
        """Return module identifier."""
        return "administrative"

    def on_entry(self, context: "AppContext") -> None:
        """
        Initialize the administrative module.

        Called by the framework during application startup.

        Args:
            context: Application context from the main framework.
        """
        self._context = context
        logger.info("Administrative module initializing...")

        # Build API router
        self._api_router = APIRouter(prefix="/administrative")
        self._api_router.include_router(leave_router)
        self._api_router.include_router(liff_router)

        # Initialize sync service
        self._sync_service = RagicSyncService()

        # Trigger async data sync in background
        self._start_ragic_sync()

        context.log_event(
            "Administrative module loaded with Leave Request System",
            "ADMINISTRATIVE",
        )
        logger.info("Administrative module initialized")

    def _start_ragic_sync(self) -> None:
        """
        Start Ragic data sync in background thread.

        Uses a separate thread with its own event loop to avoid
        blocking the main application startup.
        """
        def sync_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                logger.info("Starting Ragic data sync...")
                self._sync_status["status"] = "syncing"

                result = loop.run_until_complete(
                    self._sync_service.sync_all_data()
                )

                self._sync_status["status"] = "completed"
                self._sync_status["employees"] = result.get(
                    "employees_synced", 0)
                self._sync_status["departments"] = result.get(
                    "departments_synced", 0)

                logger.info(
                    f"Ragic sync completed: "
                    f"{self._sync_status['employees']} employees, "
                    f"{self._sync_status['departments']} departments"
                )

            except Exception as e:
                logger.error(f"Ragic sync failed: {e}")
                self._sync_status["status"] = "error"
                self._sync_status["last_error"] = str(e)

            finally:
                # Cleanup thread-local database engine
                from core.database import dispose_thread_local_engine
                try:
                    loop.run_until_complete(dispose_thread_local_engine())
                except Exception as e:
                    logger.warning(f"Error disposing thread local engine: {e}")

                # Close the sync service's HTTP client
                try:
                    loop.run_until_complete(self._sync_service.close())
                except Exception as e:
                    logger.warning(f"Error closing sync service: {e}")

                # Windows-specific: Cancel all pending tasks and allow transports to close
                try:
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    # Give cancelled tasks time to clean up
                    if pending:
                        loop.run_until_complete(asyncio.gather(
                            *pending, return_exceptions=True))
                except Exception:
                    pass

                # Allow SSL transports to close gracefully
                try:
                    loop.run_until_complete(asyncio.sleep(0.250))
                except Exception:
                    pass

                loop.close()

        # Run sync in background thread
        sync_thread = threading.Thread(target=sync_worker, daemon=True)
        sync_thread.start()
        logger.info("Ragic sync started in background")

    def handle_event(self, context: "AppContext", event: dict) -> Optional[dict]:
        """
        Handle events routed to this module.

        This module primarily operates via its API routers.
        """
        event_type = event.get("type", "")

        if event_type == "sync_ragic":
            # Manual sync trigger
            self._start_ragic_sync()
            return {"status": "sync_started"}

        return {
            "success": True,
            "module": self.get_module_name(),
            "message": f"Event received: {event_type}",
        }

    # =========================================================================
    # LINE Bot Integration
    # =========================================================================

    def get_line_bot_config(self) -> Optional[dict[str, str]]:
        """
        Return LINE Bot configuration for this module.

        This module uses an independent LINE Official Account.
        Returns the channel credentials for webhook verification.
        """
        try:
            return {
                "channel_secret": self._settings.line_channel_secret.get_secret_value(),
                "channel_access_token": self._settings.line_channel_access_token.get_secret_value(),
            }
        except Exception as e:
            logger.error(f"Failed to load LINE bot config: {e}")
            return None

    async def handle_line_event(
        self,
        event: dict[str, Any],
        context: "AppContext",
    ) -> Optional[dict[str, Any]]:
        """
        Handle LINE webhook events routed to this module.

        Responds to:
            - Text messages containing trigger keywords -> Show admin menu
            - Postback events with "coming_soon" action -> Show coming soon message

        Args:
            event: LINE event dictionary.
            context: Application context.

        Returns:
            Response dict for logging.
        """
        event_type = event.get("type")
        reply_token = event.get("replyToken")
        source = event.get("source", {})
        user_id = source.get("userId")

        if not user_id:
            logger.warning("LINE event without userId, skipping")
            return {"status": "skipped", "reason": "no userId"}

        logger.info(
            f"Administrative module handling LINE event: {event_type} from {user_id}")

        try:
            if event_type == "message":
                message_data = event.get("message", {})
                if message_data.get("type") == "text":
                    text = message_data.get("text", "").strip().lower()
                    if self._should_show_menu(text):
                        await self._handle_menu_request(user_id, reply_token)
                        return {"status": "ok", "action": "show_menu"}

            elif event_type == "postback":
                postback_data = event.get("postback", {}).get("data", "")
                await self._handle_postback(user_id, reply_token, postback_data)
                return {"status": "ok", "action": "postback"}

            return {"status": "ignored", "reason": "not handled"}

        except Exception as e:
            logger.error(f"Error handling LINE event: {e}")
            return {"status": "error", "error": str(e)}

    def _should_show_menu(self, text: str) -> bool:
        """Check if the text message should trigger the admin menu."""
        return any(trigger in text for trigger in self.MENU_TRIGGERS)

    async def _handle_menu_request(
        self, user_id: str, reply_token: str | None
    ) -> None:
        """Handle request to show the administrative menu."""
        if not reply_token:
            return

        from core.database.session import get_thread_local_session
        from core.services import get_auth_service
        from modules.administrative.messages import (
            create_admin_menu_flex,
            create_auth_required_flex,
        )

        # Get LINE service from chatbot module (shared)
        from modules.chatbot.services import get_line_service
        line_service = get_line_service()
        auth_service = get_auth_service()

        # Check if user is authenticated
        async with get_thread_local_session() as db:
            is_auth = await auth_service.is_user_authenticated(user_id, db)

        if is_auth:
            # Show admin menu
            flex_content = create_admin_menu_flex()
            await line_service.reply(reply_token, [
                {"type": "flex", "altText": "行政作業模組", "contents": flex_content}
            ])
        else:
            # Show auth required message
            flex_content = create_auth_required_flex(user_id)
            await line_service.reply(reply_token, [
                {"type": "flex", "altText": "請先驗證身份", "contents": flex_content}
            ])

    async def _handle_postback(
        self, user_id: str, reply_token: str | None, postback_data: str
    ) -> None:
        """Handle postback events from menu buttons."""
        if not reply_token:
            return

        from modules.chatbot.services import get_line_service
        from modules.administrative.messages import create_coming_soon_flex

        line_service = get_line_service()

        # Parse postback data
        params = dict(re.findall(r"(\w+)=([^&]+)", postback_data))
        action = params.get("action", "")
        feature = params.get("feature", "")

        if action == "coming_soon":
            flex_content = create_coming_soon_flex(feature)
            await line_service.reply(reply_token, [
                {"type": "flex", "altText": "功能開發中", "contents": flex_content}
            ])

    # =========================================================================
    # Standard IAppModule Methods
    # =========================================================================

    def get_api_router(self) -> Optional[APIRouter]:
        """
        Return the API router for this module.

        Called by the main application to register routes.

        Returns:
            APIRouter with leave endpoints at /api/administrative/*
        """
        return self._api_router

    def get_menu_config(self) -> dict:
        """Return menu configuration for GUI integration."""
        return {
            "icon": "📋",
            "title": "Administrative",
            "description": "Leave requests and HR functions",
            "actions": [
                {"label": "Leave Request", "action": "open_leave_form"},
                {"label": "Sync Data", "action": "sync_ragic"},
            ],
        }

    def get_status(self) -> dict[str, Any]:
        """
        Return current module status for monitoring.

        Exposes:
            - Ragic sync status
            - Cache counts
        """
        status = "active"
        details = {}

        # Sync status
        sync_status = self._sync_status.get("status", "unknown")
        if sync_status == "syncing":
            status = "initializing"
        elif sync_status == "error":
            status = "warning"

        details["Sync Status"] = sync_status.title()
        details["Cached Employees"] = str(
            self._sync_status.get("employees", 0))
        details["Cached Departments"] = str(
            self._sync_status.get("departments", 0))

        if self._sync_status.get("last_error"):
            details["Last Error"] = self._sync_status["last_error"][:100]

        return {
            "status": status,
            "details": details,
        }

    def on_shutdown(self) -> None:
        """Cleanup when module is shutting down."""
        logger.info("Administrative module shutting down")
        # Sync service runs in a daemon thread, so we don't need to explicitly close it
        # trying to close it here (main thread) can cause Event Loop Closed errors


# Module factory function for dynamic loading
def create_module() -> AdministrativeModule:
    """Factory function for module instantiation."""
    return AdministrativeModule()
