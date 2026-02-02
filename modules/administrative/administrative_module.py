"""
Administrative Module Entry Point.

Implements IAppModule interface for integration with the admin system framework.
Handles Leave Request System and data synchronization from Ragic.
"""

import asyncio
import logging
import re
from typing import Any, Optional, TYPE_CHECKING

from fastapi import APIRouter

from core.interface import IAppModule
from core.ragic import get_sync_manager
from modules.administrative.core.config import get_admin_settings
from modules.administrative.routers import leave_router, liff_router
from modules.administrative.services.account_sync import AccountSyncService, get_account_sync_service
from modules.administrative.services.leave_type_sync import LeaveTypeSyncService, get_leave_type_sync_service
from modules.administrative.services.rich_menu import RichMenuService

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
        self._account_sync_service: Optional[AccountSyncService] = None
        self._leave_type_sync_service: Optional[LeaveTypeSyncService] = None
        self._sync_status: dict[str, Any] = {
            "status": "pending",
            "accounts": 0,
            "leave_types": 0,
            "skipped": 0,
            "last_error": None,
        }
        self._settings = get_admin_settings()
        # Store background task references to prevent garbage collection
        self._background_tasks: list[asyncio.Task[Any]] = []

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

        # Initialize sync services (new architecture)
        self._account_sync_service = get_account_sync_service()
        self._leave_type_sync_service = get_leave_type_sync_service()

        # Register SyncManager Services (for webhook support and centralized management)
        try:
            sync_manager = get_sync_manager()
            
            # Register Account Sync Service
            sync_manager.register(
                key="administrative_account",
                name="Employee Accounts",
                service=self._account_sync_service,
                module_name=self.get_module_name(),
                auto_sync_on_startup=False,  # We trigger sync manually in async_startup
            )
            
            # Register Leave Type Sync Service
            sync_manager.register(
                key="administrative_leave_type",
                name="Leave Types",
                service=self._leave_type_sync_service,
                module_name=self.get_module_name(),
                auto_sync_on_startup=False,  # We trigger sync manually in async_startup
            )
            
            logger.info("Registered AccountSyncService and LeaveTypeSyncService with SyncManager")
            
        except Exception as e:
            logger.error(f"Failed to register sync services with SyncManager: {e}")

        # Note: Async tasks (Ragic sync, Rich Menu setup) are deferred to async_startup()
        # because no event loop is running during on_entry()

        context.log_event(
            "Administrative module loaded with Leave Request System",
            "ADMINISTRATIVE",
        )
        logger.info("Administrative module initialized")

    async def async_startup(self) -> None:
        """
        Perform async initialization when the event loop is running.
        
        Called by the framework during FastAPI lifespan startup.
        """
        logger.info("Administrative module async startup...")
        
        # Trigger async data sync in background
        self._start_ragic_sync()
        
        # Setup and activate LINE Rich Menu in background
        self._start_rich_menu_setup()
        
        logger.info("Administrative module async startup completed")

    def _start_ragic_sync(self) -> None:
        """
        Start Ragic data sync as a background async task.

        Uses asyncio.create_task to run the sync operation concurrently
        without blocking the main application startup.
        
        Uses the new AccountSyncService and LeaveTypeSyncService architecture.
        """
        async def sync_worker() -> None:
            """Async worker for Ragic data synchronization."""
            try:
                logger.info("Starting Ragic data sync...")
                self._sync_status["status"] = "syncing"

                # Sync accounts using new service
                account_result = await self._account_sync_service.sync_all_data()
                self._sync_status["accounts"] = account_result.synced
                self._sync_status["skipped"] = account_result.skipped

                # Sync leave types using new service
                leave_type_result = await self._leave_type_sync_service.sync_all_data()
                self._sync_status["leave_types"] = leave_type_result.synced
                self._sync_status["skipped"] += leave_type_result.skipped

                self._sync_status["status"] = "completed"

                logger.info(
                    f"Ragic sync completed: "
                    f"{self._sync_status['accounts']} accounts synced, "
                    f"{self._sync_status['leave_types']} leave types synced, "
                    f"{self._sync_status['skipped']} skipped"
                )

            except asyncio.CancelledError:
                logger.info("Ragic sync task was cancelled")
                self._sync_status["status"] = "cancelled"
                raise

            except Exception as e:
                logger.exception(f"Ragic sync failed: {e}")
                self._sync_status["status"] = "error"
                self._sync_status["last_error"] = str(e)

        def handle_task_exception(task: asyncio.Task[Any]) -> None:
            """Callback to handle task exceptions without crashing the app."""
            if task.cancelled():
                return
            exc = task.exception()
            if exc is not None:
                logger.error(
                    f"Background Ragic sync task failed with exception: {exc}",
                    exc_info=exc,
                )

        # Create and schedule the background task
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(sync_worker(), name="ragic_sync")
            task.add_done_callback(handle_task_exception)
            self._background_tasks.append(task)
            logger.info("Ragic sync started in background")
        except RuntimeError:
            # No running event loop - this shouldn't happen in normal operation
            logger.error("Cannot start Ragic sync: no running event loop")
            self._sync_status["status"] = "error"
            self._sync_status["last_error"] = "No running event loop"

    def _start_rich_menu_setup(self) -> None:
        """
        Start LINE Rich Menu setup as a background async task.

        Flow:
            1. Delete all existing menus
            2. Create new menu
            3. Upload menu image
            4. Set as default menu
        """
        async def setup_worker() -> None:
            """Async worker for Rich Menu setup."""
            rich_menu_service = RichMenuService()

            try:
                logger.info("Starting Rich Menu setup...")
                success = await rich_menu_service.setup_and_activate_menu()

                if success:
                    logger.info("Rich Menu setup completed successfully")
                else:
                    logger.warning("Rich Menu setup failed")

            except asyncio.CancelledError:
                logger.info("Rich Menu setup task was cancelled")
                raise

            except Exception as e:
                logger.exception(f"Rich Menu setup error: {e}")

            finally:
                # Close HTTP client
                try:
                    await rich_menu_service.close()
                except Exception as e:
                    logger.warning(f"Error closing rich menu service: {e}")

        def handle_task_exception(task: asyncio.Task[Any]) -> None:
            """Callback to handle task exceptions without crashing the app."""
            if task.cancelled():
                return
            exc = task.exception()
            if exc is not None:
                logger.error(
                    f"Background Rich Menu setup task failed with exception: {exc}",
                    exc_info=exc,
                )

        # Create and schedule the background task
        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(setup_worker(), name="rich_menu_setup")
            task.add_done_callback(handle_task_exception)
            self._background_tasks.append(task)
            logger.info("Rich Menu setup started in background")
        except RuntimeError:
            # No running event loop - this shouldn't happen in normal operation
            logger.error("Cannot start Rich Menu setup: no running event loop")

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
        details["Cached Accounts"] = str(
            self._sync_status.get("accounts", 0))
        details["Cached Leave Types"] = str(
            self._sync_status.get("leave_types", 0))
        details["Skipped"] = str(
            self._sync_status.get("skipped", 0))

        if self._sync_status.get("last_error"):
            details["Last Error"] = self._sync_status["last_error"][:100]

        return {
            "status": status,
            "details": details,
        }

    def on_shutdown(self) -> None:
        """Cleanup when module is shutting down."""
        logger.info("Administrative module shutting down")

        # Cancel any running background tasks
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                logger.debug(f"Cancelled background task: {task.get_name()}")

        self._background_tasks.clear()


# Module factory function for dynamic loading
def create_module() -> AdministrativeModule:
    """Factory function for module instantiation."""
    return AdministrativeModule()
