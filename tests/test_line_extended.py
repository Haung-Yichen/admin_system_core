"""
Unit Tests for LINE Extended Services.

Tests LINE API services in the administrative module:
- RichMenuService: Rich Menu CRUD operations
- LiffService: LIFF App management (already has tests, these complement them)

This test suite ensures comprehensive coverage before refactoring
to integrate these services with the core LineClient.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
import httpx
from pydantic import SecretStr


# =============================================================================
# RichMenuService Tests
# =============================================================================

class TestRichMenuServiceInit:
    """Tests for RichMenuService initialization."""

    @pytest.fixture
    def mock_admin_settings(self):
        """Create mock AdminSettings."""
        settings = MagicMock()
        settings.line_channel_access_token = SecretStr("test_access_token")
        settings.line_liff_id_leave = "1234567890-AbCdEfGh"
        return settings

    def test_init_with_settings(self, mock_admin_settings):
        """Test service initializes with settings."""
        from modules.administrative.services.rich_menu import RichMenuService
        service = RichMenuService(settings=mock_admin_settings)
        
        assert service._settings == mock_admin_settings
        assert service._http_client is None

    def test_init_default_base_url(self, mock_admin_settings):
        """Test service uses default LINE API base URL."""
        from modules.administrative.services.rich_menu import RichMenuService
        service = RichMenuService(settings=mock_admin_settings)
        
        assert "api.line.me" in service.LINE_API_BASE

    def test_init_without_settings(self):
        """Test service uses get_admin_settings when no settings provided."""
        with patch('modules.administrative.services.rich_menu.get_admin_settings') as mock_get:
            mock_get.return_value = MagicMock()
            mock_get.return_value.line_channel_access_token = SecretStr("test")
            mock_get.return_value.line_liff_id_leave = ""
            
            from modules.administrative.services.rich_menu import RichMenuService
            service = RichMenuService()
            mock_get.assert_called_once()


class TestRichMenuServiceMenuDefinition:
    """Tests for rich menu definition generation."""

    @pytest.fixture
    def rich_menu_service(self):
        """Create RichMenuService with mock settings."""
        settings = MagicMock()
        settings.line_channel_access_token = SecretStr("test_token")
        settings.line_liff_id_leave = "test-liff-id"
        
        from modules.administrative.services.rich_menu import RichMenuService
        return RichMenuService(settings=settings)

    def test_get_menu_definition_returns_valid_structure(self, rich_menu_service):
        """Test menu definition has required fields."""
        menu_def = rich_menu_service._get_menu_definition()
        
        assert "size" in menu_def
        assert menu_def["size"]["width"] == 2500
        assert menu_def["size"]["height"] == 1686
        assert "areas" in menu_def
        assert len(menu_def["areas"]) == 6  # 2 rows x 3 columns
        assert "chatBarText" in menu_def
        assert menu_def["selected"] is True

    def test_get_menu_definition_includes_liff_uri(self, rich_menu_service):
        """Test first action uses LIFF URI."""
        menu_def = rich_menu_service._get_menu_definition()
        
        first_area = menu_def["areas"][0]
        assert first_area["action"]["type"] == "uri"
        assert "line://app/test-liff-id" in first_area["action"]["uri"]

    def test_get_menu_definition_areas_cover_full_size(self, rich_menu_service):
        """Test menu areas cover the full menu size properly."""
        menu_def = rich_menu_service._get_menu_definition()
        
        # Check all areas have valid bounds
        for area in menu_def["areas"]:
            bounds = area["bounds"]
            assert bounds["x"] >= 0
            assert bounds["y"] >= 0
            assert bounds["width"] > 0
            assert bounds["height"] > 0
            # Bounds should be within menu size
            assert bounds["x"] + bounds["width"] <= 2500
            assert bounds["y"] + bounds["height"] <= 1686


class TestRichMenuServiceCRUD:
    """Tests for RichMenuService CRUD operations."""

    @pytest.fixture
    def mock_admin_settings(self):
        """Create mock AdminSettings."""
        settings = MagicMock()
        settings.line_channel_access_token = SecretStr("test_access_token")
        settings.line_liff_id_leave = "test-liff-id"
        return settings

    @pytest.fixture
    def rich_menu_service(self, mock_admin_settings):
        """Create RichMenuService instance."""
        from modules.administrative.services.rich_menu import RichMenuService
        return RichMenuService(settings=mock_admin_settings)

    @pytest.mark.asyncio
    async def test_create_rich_menu_success(
        self, rich_menu_service, mock_line_api_response
    ):
        """Test successful rich menu creation."""
        mock_response = mock_line_api_response(
            json_data={"richMenuId": "richmenu-abc123"}
        )
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        rich_menu_service._http_client = mock_client
        
        result = await rich_menu_service.create_rich_menu()
        
        assert result == "richmenu-abc123"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_rich_menu_api_error(self, rich_menu_service):
        """Test handling of API error during creation."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "400 Bad Request",
                request=MagicMock(),
                response=MagicMock(status_code=400)
            )
        )
        rich_menu_service._http_client = mock_client
        
        result = await rich_menu_service.create_rich_menu()
        
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_rich_menu_success(
        self, rich_menu_service, mock_line_api_response
    ):
        """Test successful rich menu deletion."""
        mock_response = mock_line_api_response(json_data={})
        
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_response)
        rich_menu_service._http_client = mock_client
        
        result = await rich_menu_service.delete_rich_menu("richmenu-xyz")
        
        assert result is True
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_rich_menu_api_error(self, rich_menu_service):
        """Test handling of API error during deletion."""
        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "404 Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404)
            )
        )
        rich_menu_service._http_client = mock_client
        
        result = await rich_menu_service.delete_rich_menu("richmenu-xyz")
        
        assert result is False

    @pytest.mark.asyncio
    async def test_set_default_menu_success(
        self, rich_menu_service, mock_line_api_response
    ):
        """Test setting rich menu as default."""
        mock_response = mock_line_api_response(json_data={})
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        rich_menu_service._http_client = mock_client
        
        result = await rich_menu_service.set_default_menu("richmenu-abc")
        
        assert result is True
        call_args = mock_client.post.call_args
        assert "/user/all/richmenu/richmenu-abc" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_rich_menus_success(
        self, rich_menu_service, mock_line_api_response
    ):
        """Test listing all rich menus."""
        mock_response = mock_line_api_response(
            json_data={
                "richmenus": [
                    {"richMenuId": "menu1", "name": "Menu 1"},
                    {"richMenuId": "menu2", "name": "Menu 2"},
                ]
            }
        )
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        rich_menu_service._http_client = mock_client
        
        result = await rich_menu_service.list_rich_menus()
        
        assert len(result) == 2
        assert result[0]["richMenuId"] == "menu1"

    @pytest.mark.asyncio
    async def test_list_rich_menus_api_error(self, rich_menu_service):
        """Test handling of API error during list."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500)
            )
        )
        rich_menu_service._http_client = mock_client
        
        result = await rich_menu_service.list_rich_menus()
        
        assert result == []


class TestRichMenuServiceImageUpload:
    """Tests for rich menu image upload functionality."""

    @pytest.fixture
    def mock_admin_settings(self):
        """Create mock AdminSettings."""
        settings = MagicMock()
        settings.line_channel_access_token = SecretStr("test_access_token")
        settings.line_liff_id_leave = "test-liff-id"
        return settings

    @pytest.fixture
    def rich_menu_service(self, mock_admin_settings):
        """Create RichMenuService instance."""
        from modules.administrative.services.rich_menu import RichMenuService
        return RichMenuService(settings=mock_admin_settings)

    @pytest.mark.asyncio
    async def test_upload_menu_image_success(
        self, rich_menu_service, mock_line_api_response, mock_pil_image, tmp_path
    ):
        """Test successful image upload."""
        # Create a small test image file
        test_image_path = tmp_path / "test_menu.png"
        test_image_path.write_bytes(b"fake image data")
        
        mock_response = mock_line_api_response(json_data={})
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        rich_menu_service._http_client = mock_client
        
        # Mock _compress_image to return test data
        with patch.object(
            rich_menu_service, '_compress_image', return_value=b"compressed image data"
        ):
            result = await rich_menu_service.upload_menu_image(
                "richmenu-123", test_image_path
            )
        
        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "richmenu-123/content" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_upload_menu_image_file_not_found(self, rich_menu_service):
        """Test handling of missing image file."""
        result = await rich_menu_service.upload_menu_image(
            "richmenu-123", "/nonexistent/path/image.png"
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_upload_menu_image_api_error(
        self, rich_menu_service, mock_pil_image, tmp_path
    ):
        """Test handling of API error during upload."""
        test_image_path = tmp_path / "test_menu.png"
        test_image_path.write_bytes(b"fake image data")
        
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "413 Payload Too Large",
                request=MagicMock(),
                response=MagicMock(status_code=413)
            )
        )
        rich_menu_service._http_client = mock_client
        
        with patch.object(
            rich_menu_service, '_compress_image', return_value=b"compressed image"
        ):
            result = await rich_menu_service.upload_menu_image(
                "richmenu-123", test_image_path
            )
        
        assert result is False


class TestRichMenuServiceImageCompression:
    """Tests for image compression functionality."""

    @pytest.fixture
    def mock_admin_settings(self):
        """Create mock AdminSettings."""
        settings = MagicMock()
        settings.line_channel_access_token = SecretStr("test_access_token")
        settings.line_liff_id_leave = ""
        return settings

    @pytest.fixture
    def rich_menu_service(self, mock_admin_settings):
        """Create RichMenuService instance."""
        from modules.administrative.services.rich_menu import RichMenuService
        return RichMenuService(settings=mock_admin_settings)

    def test_compress_image_resizes_to_target(
        self, rich_menu_service, mock_pil_image, tmp_path
    ):
        """Test image is resized to target dimensions."""
        # Mock image with different original size
        mock_pil_image.size = (3000, 2000)
        
        test_image_path = tmp_path / "test.png"
        test_image_path.write_bytes(b"fake")
        
        with patch('PIL.Image.open', return_value=mock_pil_image):
            with patch.object(mock_pil_image, 'save') as mock_save:
                # Return small data so compression loop exits
                mock_buffer = MagicMock()
                mock_buffer.getvalue.return_value = b"x" * 1000
                
                with patch('io.BytesIO', return_value=mock_buffer):
                    rich_menu_service._compress_image(test_image_path)
        
        # Verify resize was called with target dimensions
        mock_pil_image.resize.assert_called()
        resize_args = mock_pil_image.resize.call_args[0]
        assert resize_args[0] == (2500, 1686)


class TestRichMenuServiceSetupAndActivate:
    """Tests for complete setup workflow."""

    @pytest.fixture
    def mock_admin_settings(self):
        """Create mock AdminSettings."""
        settings = MagicMock()
        settings.line_channel_access_token = SecretStr("test_access_token")
        settings.line_liff_id_leave = "test-liff"
        return settings

    @pytest.fixture
    def rich_menu_service(self, mock_admin_settings):
        """Create RichMenuService instance."""
        from modules.administrative.services.rich_menu import RichMenuService
        return RichMenuService(settings=mock_admin_settings)

    @pytest.mark.asyncio
    async def test_setup_and_activate_full_workflow(
        self, rich_menu_service, mock_line_api_response, tmp_path
    ):
        """Test complete setup workflow."""
        # Create test image
        test_image = tmp_path / "menu.png"
        test_image.write_bytes(b"fake image")
        
        # Mock all the methods
        with patch.object(
            rich_menu_service, 'list_rich_menus',
            new=AsyncMock(return_value=[{"richMenuId": "old-menu"}])
        ), patch.object(
            rich_menu_service, 'delete_rich_menu',
            new=AsyncMock(return_value=True)
        ), patch.object(
            rich_menu_service, 'create_rich_menu',
            new=AsyncMock(return_value="new-menu-id")
        ), patch.object(
            rich_menu_service, 'upload_menu_image',
            new=AsyncMock(return_value=True)
        ), patch.object(
            rich_menu_service, 'set_default_menu',
            new=AsyncMock(return_value=True)
        ):
            result = await rich_menu_service.setup_and_activate_menu(test_image)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_setup_and_activate_image_not_found(self, rich_menu_service):
        """Test setup fails gracefully when image not found."""
        result = await rich_menu_service.setup_and_activate_menu(
            "/nonexistent/image.png"
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_setup_and_activate_create_fails(
        self, rich_menu_service, tmp_path
    ):
        """Test setup handles create failure."""
        test_image = tmp_path / "menu.png"
        test_image.write_bytes(b"fake")
        
        with patch.object(
            rich_menu_service, 'list_rich_menus',
            new=AsyncMock(return_value=[])
        ), patch.object(
            rich_menu_service, 'create_rich_menu',
            new=AsyncMock(return_value=None)  # Creation fails
        ):
            result = await rich_menu_service.setup_and_activate_menu(test_image)
        
        assert result is False


class TestRichMenuServiceSingleton:
    """Tests for singleton pattern."""

    def test_get_rich_menu_service_returns_singleton(self):
        """Test singleton returns same instance."""
        import modules.administrative.services.rich_menu as rm_module
        rm_module._rich_menu_service = None
        
        with patch('modules.administrative.services.rich_menu.get_admin_settings') as mock_get:
            mock_get.return_value = MagicMock()
            mock_get.return_value.line_channel_access_token = SecretStr("test")
            mock_get.return_value.line_liff_id_leave = ""
            
            from modules.administrative.services.rich_menu import get_rich_menu_service
            
            service1 = get_rich_menu_service()
            service2 = get_rich_menu_service()
            
            assert service1 is service2


# =============================================================================
# Additional LiffService Tests (complement existing tests)
# =============================================================================

class TestLiffServiceEdgeCases:
    """Additional edge case tests for LiffService."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock AdminSettings."""
        settings = MagicMock()
        settings.line_channel_access_token = SecretStr("test_access_token")
        return settings

    @pytest.fixture
    def liff_service(self, mock_settings):
        """Create LIFF service instance."""
        from modules.administrative.services.liff import LiffService
        return LiffService(settings=mock_settings)

    @pytest.mark.asyncio
    async def test_list_liff_apps_empty(self, liff_service, mock_line_api_response):
        """Test listing when no LIFF apps exist."""
        mock_response = mock_line_api_response(json_data={"apps": []})
        
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client
        
        result = await liff_service.list_liff_apps()
        
        assert result == []

    @pytest.mark.asyncio
    async def test_update_liff_app_success(self, liff_service, mock_line_api_response):
        """Test successful LIFF app update."""
        mock_response = mock_line_api_response(json_data={})
        
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client
        
        result = await liff_service.update_liff_app(
            "liff-123",
            "https://new-endpoint.com/app",
            "tall"
        )
        
        assert result is True
        mock_client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_liff_app_failure(self, liff_service):
        """Test LIFF app update failure."""
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "404",
                request=MagicMock(),
                response=MagicMock(status_code=404)
            )
        )
        liff_service._http_client = mock_client
        
        result = await liff_service.update_liff_app(
            "liff-nonexistent",
            "https://example.com",
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_close_releases_client(self, liff_service):
        """Test close method releases HTTP client."""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        liff_service._http_client = mock_client
        
        await liff_service.close()
        
        assert liff_service._http_client is None
        mock_client.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_when_no_client(self, liff_service):
        """Test close is safe when no client exists."""
        assert liff_service._http_client is None
        
        # Should not raise
        await liff_service.close()
        
        assert liff_service._http_client is None


# =============================================================================
# Core LineClient Integration Tests
# =============================================================================

class TestLineClientIntegration:
    """Tests ensuring core LineClient works with module services."""

    @pytest.fixture
    def mock_env_vars(self, monkeypatch):
        """Set up LINE env vars."""
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
        monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "test-token")

    def test_line_client_supports_custom_credentials(self, mock_env_vars):
        """Test LineClient accepts custom credentials."""
        from services.line_client import LineClient
        
        client = LineClient(
            channel_secret="custom-secret",
            access_token="custom-token",
        )
        
        assert client._channel_secret == "custom-secret"
        assert client._access_token == "custom-token"

    def test_line_client_is_configured(self, mock_env_vars):
        """Test is_configured returns correct status."""
        from services.line_client import LineClient
        
        configured = LineClient(
            channel_secret="secret",
            access_token="token",
        )
        assert configured.is_configured() is True
        
        not_configured = LineClient(
            channel_secret="",
            access_token="",
        )
        assert not_configured.is_configured() is False

    @pytest.mark.asyncio
    async def test_line_client_post_reply(self, mock_env_vars, mock_async_client):
        """Test LineClient reply functionality."""
        from services.line_client import LineClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_async_client.post = AsyncMock(return_value=mock_response)
        
        client = LineClient(
            channel_secret="secret",
            access_token="token",
        )
        client._client = mock_async_client
        
        result = await client.post_reply(
            "reply-token-123",
            [{"type": "text", "text": "Hello"}]
        )
        
        assert result is True

    @pytest.mark.asyncio
    async def test_line_client_post_push(self, mock_env_vars, mock_async_client):
        """Test LineClient push functionality."""
        from services.line_client import LineClient
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_async_client.post = AsyncMock(return_value=mock_response)
        
        client = LineClient(
            channel_secret="secret",
            access_token="token",
        )
        client._client = mock_async_client
        
        result = await client.post_push(
            "user-id-123",
            [{"type": "text", "text": "Push message"}]
        )
        
        assert result is True
