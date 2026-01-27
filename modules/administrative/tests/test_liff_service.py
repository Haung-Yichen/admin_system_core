"""
Unit Tests for LIFF Service.

Tests the LINE LIFF App management service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from pydantic import SecretStr

from modules.administrative.services.liff import LiffService, get_liff_service


@pytest.fixture
def mock_settings():
    """Create mock AdminSettings."""
    settings = MagicMock()
    settings.line_channel_access_token = SecretStr("test_access_token")
    return settings


@pytest.fixture
def liff_service(mock_settings):
    """Create LIFF service instance with mock settings."""
    return LiffService(settings=mock_settings)


class TestLiffServiceInit:
    """Tests for LiffService initialization."""

    def test_init_with_settings(self, mock_settings):
        """Test service initializes with settings."""
        service = LiffService(settings=mock_settings)
        assert service._settings == mock_settings
        assert service._http_client is None

    def test_init_default_base_url(self, mock_settings):
        """Test service uses default LINE API base URL."""
        service = LiffService(settings=mock_settings)
        assert "api.line.me" in service.LINE_API_BASE

    def test_init_without_settings(self):
        """Test service uses get_admin_settings when no settings provided."""
        with patch('modules.administrative.services.liff.get_admin_settings') as mock_get:
            mock_get.return_value = MagicMock()
            mock_get.return_value.line_channel_access_token = SecretStr("test")
            service = LiffService()
            mock_get.assert_called_once()


class TestCreateLiffApp:
    """Tests for create_liff_app method."""

    @pytest.mark.asyncio
    async def test_create_liff_app_success(self, liff_service):
        """Test successful LIFF app creation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"liffId": "1234567890-AbCdEfGh"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client

        result = await liff_service.create_liff_app(
            endpoint_url="https://example.com/app"
        )

        assert result == "1234567890-AbCdEfGh"
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_liff_app_with_custom_view_type(self, liff_service):
        """Test LIFF app creation with custom view type."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"liffId": "1234567890-XyZ"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client

        result = await liff_service.create_liff_app(
            endpoint_url="https://example.com/compact-app",
            view_type="compact"
        )

        assert result == "1234567890-XyZ"

    @pytest.mark.asyncio
    async def test_create_liff_app_api_error(self, liff_service):
        """Test handling LINE API error."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400 Bad Request",
            request=MagicMock(),
            response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client

        result = await liff_service.create_liff_app(
            endpoint_url="invalid-url"
        )

        assert result is None


class TestListLiffApps:
    """Tests for list_liff_apps method."""

    @pytest.mark.asyncio
    async def test_list_liff_apps_success(self, liff_service):
        """Test successful LIFF apps listing."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "apps": [
                {"liffId": "app1", "view": {"type": "full", "url": "https://a.com"}},
                {"liffId": "app2", "view": {"type": "compact", "url": "https://b.com"}},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client

        result = await liff_service.list_liff_apps()

        assert len(result) == 2
        assert result[0]["liffId"] == "app1"

    @pytest.mark.asyncio
    async def test_list_liff_apps_empty(self, liff_service):
        """Test listing when no LIFF apps exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"apps": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client

        result = await liff_service.list_liff_apps()

        assert result == []

    @pytest.mark.asyncio
    async def test_list_liff_apps_error(self, liff_service):
        """Test handling error during listing."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPError("Network error"))
        liff_service._http_client = mock_client

        result = await liff_service.list_liff_apps()

        assert result == []


class TestDeleteLiffApp:
    """Tests for delete_liff_app method."""

    @pytest.mark.asyncio
    async def test_delete_liff_app_success(self, liff_service):
        """Test successful LIFF app deletion."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client

        result = await liff_service.delete_liff_app("1234567890-AbCd")

        assert result is True
        mock_client.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_liff_app_not_found(self, liff_service):
        """Test deleting non-existent LIFF app."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found",
            request=MagicMock(),
            response=mock_response
        )

        mock_client = AsyncMock()
        mock_client.delete = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client

        result = await liff_service.delete_liff_app("nonexistent-id")

        assert result is False


class TestUpdateLiffApp:
    """Tests for update_liff_app method."""

    @pytest.mark.asyncio
    async def test_update_liff_app_success(self, liff_service):
        """Test successful LIFF app update."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put = AsyncMock(return_value=mock_response)
        liff_service._http_client = mock_client

        result = await liff_service.update_liff_app(
            liff_id="1234567890-AbCd",
            endpoint_url="https://updated.example.com"
        )

        assert result is True
        mock_client.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_liff_app_error(self, liff_service):
        """Test handling update error."""
        mock_client = AsyncMock()
        mock_client.put = AsyncMock(
            side_effect=httpx.HTTPError("Network error"))
        liff_service._http_client = mock_client

        result = await liff_service.update_liff_app(
            liff_id="1234567890-AbCd",
            endpoint_url="https://updated.example.com"
        )

        assert result is False


class TestClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_close_client(self, liff_service):
        """Test closing HTTP client."""
        mock_client = AsyncMock()
        liff_service._http_client = mock_client

        await liff_service.close()

        mock_client.aclose.assert_called_once()
        assert liff_service._http_client is None

    @pytest.mark.asyncio
    async def test_close_no_client(self, liff_service):
        """Test closing when no client exists."""
        liff_service._http_client = None

        await liff_service.close()  # Should not raise

        assert liff_service._http_client is None


class TestGetLiffServiceSingleton:
    """Tests for get_liff_service function."""

    def test_singleton_pattern(self):
        """Test singleton returns same instance."""
        with patch('modules.administrative.services.liff._liff_service', None):
            with patch('modules.administrative.services.liff.get_admin_settings') as mock_settings:
                mock_settings.return_value = MagicMock()
                mock_settings.return_value.line_channel_access_token = SecretStr(
                    "test")

                service1 = get_liff_service()
                service2 = get_liff_service()

                # Both should be same instance
                assert service1 is service2
