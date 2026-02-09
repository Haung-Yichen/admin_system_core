"""
Unit Tests for Administrative Module.

Tests the AdministrativeModule class that implements IAppModule interface.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Optional

from modules.administrative.administrative_module import (
    AdministrativeModule,
    create_module,
)


@pytest.fixture
def admin_module():
    """Create AdministrativeModule instance for testing."""
    with patch('modules.administrative.administrative_module.get_admin_settings') as mock_settings:
        mock_settings.return_value = MagicMock()
        module = AdministrativeModule()
    return module


@pytest.fixture
def mock_context():
    """Create mock AppContext."""
    context = MagicMock()
    context.log_event = MagicMock()
    return context


class TestAdministrativeModuleInit:
    """Tests for AdministrativeModule initialization."""

    def test_init_state(self, admin_module):
        """Test initial state is correct."""
        assert admin_module._context is None
        assert admin_module._api_router is None
        assert admin_module._sync_service is None
        assert admin_module._sync_status["status"] == "pending"

    def test_get_module_name(self, admin_module):
        """Test module name is returned correctly."""
        assert admin_module.get_module_name() == "administrative"

    def test_menu_triggers(self, admin_module):
        """Test menu triggers are defined."""
        assert "行政" in admin_module.MENU_TRIGGERS
        assert "admin" in admin_module.MENU_TRIGGERS
        assert "請假" in admin_module.MENU_TRIGGERS
        assert "leave" in admin_module.MENU_TRIGGERS


class TestOnEntry:
    """Tests for on_entry method."""

    def test_on_entry_sets_context(self, admin_module, mock_context):
        """Test on_entry sets context."""
        with patch.object(admin_module, '_start_ragic_sync'):
            admin_module.on_entry(mock_context)

        assert admin_module._context == mock_context

    def test_on_entry_creates_router(self, admin_module, mock_context):
        """Test on_entry creates API router."""
        with patch.object(admin_module, '_start_ragic_sync'):
            admin_module.on_entry(mock_context)

        assert admin_module._api_router is not None

    def test_on_entry_initializes_sync_service(self, admin_module, mock_context):
        """Test on_entry initializes sync service."""
        with patch.object(admin_module, '_start_ragic_sync'):
            admin_module.on_entry(mock_context)

        assert admin_module._sync_service is not None

    def test_on_entry_logs_event(self, admin_module, mock_context):
        """Test on_entry logs to context."""
        with patch.object(admin_module, '_start_ragic_sync'):
            admin_module.on_entry(mock_context)

        mock_context.log_event.assert_called_once()

    def test_on_entry_starts_sync(self, admin_module, mock_context):
        """Test on_entry starts Ragic sync."""
        with patch.object(admin_module, '_start_ragic_sync') as mock_sync:
            admin_module.on_entry(mock_context)

        mock_sync.assert_called_once()


class TestStartRagicSync:
    """Tests for _start_ragic_sync method."""

    def test_start_sync_creates_thread(self, admin_module):
        """Test sync starts in background thread."""
        admin_module._sync_service = MagicMock()

        with patch('threading.Thread') as mock_thread:
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance

            admin_module._start_ragic_sync()

            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()


class TestHandleEvent:
    """Tests for handle_event method."""

    def test_handle_sync_event(self, admin_module, mock_context):
        """Test handling sync_ragic event."""
        admin_module._context = mock_context
        admin_module._sync_service = MagicMock()

        with patch.object(admin_module, '_start_ragic_sync') as mock_sync:
            result = admin_module.handle_event(
                mock_context,
                {"type": "sync_ragic"}
            )

        mock_sync.assert_called_once()
        assert result["status"] == "sync_started"

    def test_handle_unknown_event(self, admin_module, mock_context):
        """Test handling unknown event type."""
        admin_module._context = mock_context

        result = admin_module.handle_event(
            mock_context,
            {"type": "unknown_event"}
        )

        assert result["success"] is True
        assert result["module"] == "administrative"


class TestGetLineBotConfig:
    """Tests for get_line_bot_config method."""

    def test_get_config_success(self, admin_module):
        """Test getting LINE bot config."""
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "test_secret"
        mock_token = MagicMock()
        mock_token.get_secret_value.return_value = "test_token"

        admin_module._settings = MagicMock()
        admin_module._settings.line_channel_secret = mock_secret
        admin_module._settings.line_channel_access_token = mock_token

        config = admin_module.get_line_bot_config()

        assert config["channel_secret"] == "test_secret"
        assert config["channel_access_token"] == "test_token"

    def test_get_config_error_returns_none(self, admin_module):
        """Test returns None on error."""
        admin_module._settings = MagicMock()
        admin_module._settings.line_channel_secret.get_secret_value.side_effect = Exception(
            "Error")

        config = admin_module.get_line_bot_config()

        assert config is None


class TestHandleLineEvent:
    """Tests for handle_line_event method."""

    @pytest.mark.asyncio
    async def test_handle_event_no_user_id(self, admin_module, mock_context):
        """Test skipping event without userId."""
        event = {"type": "message", "source": {}}

        result = await admin_module.handle_line_event(event, mock_context)

        assert result["status"] == "skipped"
        assert result["reason"] == "no userId"

    @pytest.mark.asyncio
    async def test_handle_text_message_with_trigger(self, admin_module, mock_context):
        """Test handling text message with menu trigger."""
        event = {
            "type": "message",
            "replyToken": "test_token",
            "source": {"userId": "U12345"},
            "message": {"type": "text", "text": "請假"},
        }

        with patch.object(admin_module, '_handle_menu_request', new_callable=AsyncMock) as mock_menu:
            result = await admin_module.handle_line_event(event, mock_context)

        mock_menu.assert_called_once_with("U12345", "test_token")
        assert result["status"] == "ok"
        assert result["action"] == "show_menu"

    @pytest.mark.asyncio
    async def test_handle_text_message_without_trigger(self, admin_module, mock_context):
        """Test ignoring text message without menu trigger."""
        event = {
            "type": "message",
            "replyToken": "test_token",
            "source": {"userId": "U12345"},
            "message": {"type": "text", "text": "hello"},
        }

        result = await admin_module.handle_line_event(event, mock_context)

        assert result["status"] == "ignored"

    @pytest.mark.asyncio
    async def test_handle_postback(self, admin_module, mock_context):
        """Test handling postback event."""
        event = {
            "type": "postback",
            "replyToken": "test_token",
            "source": {"userId": "U12345"},
            "postback": {"data": "action=coming_soon&feature=test"},
        }

        with patch.object(admin_module, '_handle_postback', new_callable=AsyncMock) as mock_postback:
            result = await admin_module.handle_line_event(event, mock_context)

        mock_postback.assert_called_once_with(
            "U12345", "test_token", "action=coming_soon&feature=test"
        )
        assert result["status"] == "ok"
        assert result["action"] == "postback"


class TestShouldShowMenu:
    """Tests for _should_show_menu method."""

    def test_trigger_chinese(self, admin_module):
        """Test Chinese trigger word."""
        assert admin_module._should_show_menu("行政") is True
        assert admin_module._should_show_menu("請假申請") is True

    def test_trigger_english(self, admin_module):
        """Test English trigger word."""
        assert admin_module._should_show_menu("admin") is True
        assert admin_module._should_show_menu("show menu") is True
        assert admin_module._should_show_menu("leave request") is True

    def test_no_trigger(self, admin_module):
        """Test text without trigger."""
        assert admin_module._should_show_menu("hello") is False
        assert admin_module._should_show_menu("how are you") is False


class TestGetApiRouter:
    """Tests for get_api_router method."""

    def test_get_router_before_init(self, admin_module):
        """Test getting router before initialization."""
        assert admin_module.get_api_router() is None

    def test_get_router_after_init(self, admin_module, mock_context):
        """Test getting router after initialization."""
        with patch.object(admin_module, '_start_ragic_sync'):
            admin_module.on_entry(mock_context)

        router = admin_module.get_api_router()
        assert router is not None


class TestGetMenuConfig:
    """Tests for get_menu_config method."""

    def test_menu_config_structure(self, admin_module):
        """Test menu config has required fields."""
        config = admin_module.get_menu_config()

        assert "icon" in config
        assert "title" in config
        assert "description" in config
        assert "actions" in config
        assert isinstance(config["actions"], list)


class TestGetStatus:
    """Tests for get_status method."""

    def test_status_pending(self, admin_module):
        """Test status when sync pending."""
        admin_module._sync_status = {
            "status": "pending", "accounts": 0, "skipped": 0}

        status = admin_module.get_status()

        assert "Sync Status" in status["details"]
        assert status["details"]["Sync Status"] == "Pending"

    def test_status_syncing(self, admin_module):
        """Test status when sync in progress."""
        admin_module._sync_status = {
            "status": "syncing", "accounts": 0, "skipped": 0}

        status = admin_module.get_status()

        assert status["status"] == "initializing"

    def test_status_completed(self, admin_module):
        """Test status when sync completed."""
        admin_module._sync_status = {
            "status": "completed",
            "accounts": 100,
            "skipped": 5,
        }

        status = admin_module.get_status()

        assert status["status"] == "active"
        assert status["details"]["Cached Accounts"] == "100"
        assert status["details"]["Skipped"] == "5"

    def test_status_error(self, admin_module):
        """Test status when sync has error."""
        admin_module._sync_status = {
            "status": "error",
            "accounts": 0,
            "skipped": 0,
            "last_error": "Connection timeout",
        }

        status = admin_module.get_status()

        assert status["status"] == "warning"
        assert "Last Error" in status["details"]


class TestOnShutdown:
    """Tests for on_shutdown method."""

    def test_shutdown_logs(self, admin_module):
        """Test shutdown logs message."""
        # Should not raise
        admin_module.on_shutdown()


class TestCreateModule:
    """Tests for create_module factory function."""

    def test_create_module_returns_instance(self):
        """Test factory returns module instance."""
        with patch('modules.administrative.administrative_module.get_admin_settings') as mock_settings:
            mock_settings.return_value = MagicMock()
            module = create_module()

        assert isinstance(module, AdministrativeModule)
