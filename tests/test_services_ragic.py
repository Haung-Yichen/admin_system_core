"""
Unit Tests for services.ragic_service module.

Tests RagicService class for Ragic API integration.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestRagicServiceInitialization:
    """Tests for RagicService initialization."""
    
    def test_init_with_config_loader(self, config_loader):
        """Test initialization with ConfigLoader."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        assert service._api_key == "test-ragic-key"
        assert service._base_url == "https://ap13.ragic.com"
    
    def test_init_strips_trailing_slash(self, mock_env_vars, monkeypatch):
        """Test base_url has trailing slash stripped."""
        from core.app_context import ConfigLoader
        from services.ragic_service import RagicService
        
        monkeypatch.setenv("RAGIC_BASE_URL", "https://test.ragic.com/")
        
        loader = ConfigLoader()
        loader.load()
        service = RagicService(loader)
        
        assert service._base_url == "https://test.ragic.com"


class TestRagicServiceIsConfigured:
    """Tests for is_configured() method."""
    
    def test_is_configured_true(self, config_loader):
        """Test is_configured() returns True when credentials exist."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        assert service.is_configured() is True
    
    def test_is_configured_false_missing_api_key(self, mock_env_vars, monkeypatch):
        """Test is_configured() returns False when API key missing."""
        from core.app_context import ConfigLoader
        from services.ragic_service import RagicService
        
        monkeypatch.setenv("RAGIC_API_KEY", "")
        
        loader = ConfigLoader()
        loader.load()
        service = RagicService(loader)
        
        assert service.is_configured() is False


class TestRagicServiceBuildUrl:
    """Tests for _build_url() method."""
    
    def test_build_url_without_record_id(self, config_loader):
        """Test _build_url() builds sheet URL correctly."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        url = service._build_url("forms/1")
        
        assert url == "https://ap13.ragic.com/forms/1"
    
    def test_build_url_with_record_id(self, config_loader):
        """Test _build_url() builds record URL correctly."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        url = service._build_url("forms/1", 123)
        
        assert url == "https://ap13.ragic.com/forms/1/123"


class TestRagicServiceGetRecords:
    """Tests for get_records() method."""
    
    @pytest.mark.asyncio
    async def test_get_records_success(self, config_loader):
        """Test get_records() returns list on success."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_data = {"1": {"field": "value1"}, "2": {"field": "value2"}}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_data
        
        with patch.object(service._client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await service.get_records("forms/1")
            
            assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_get_records_with_filters(self, config_loader):
        """Test get_records() applies filters correctly."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        
        with patch.object(service._client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            await service.get_records("forms/1", filters={"1000001": "test"})
            
            call_args = mock_get.call_args
            params = call_args.kwargs["params"]
            assert "where_1000001" in params
    
    @pytest.mark.asyncio
    async def test_get_records_not_configured(self, mock_env_vars, monkeypatch):
        """Test get_records() returns empty list when not configured."""
        from core.app_context import ConfigLoader
        from services.ragic_service import RagicService
        
        monkeypatch.setenv("RAGIC_API_KEY", "")
        
        loader = ConfigLoader()
        loader.load()
        service = RagicService(loader)
        
        result = await service.get_records("forms/1")
        
        assert result == []
    
    @pytest.mark.asyncio
    async def test_get_records_failure(self, config_loader):
        """Test get_records() returns empty list on HTTP error."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch.object(service._client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await service.get_records("forms/1")
            
            assert result == []


class TestRagicServiceGetRecord:
    """Tests for get_record() method."""
    
    @pytest.mark.asyncio
    async def test_get_record_success(self, config_loader):
        """Test get_record() returns record on success."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        expected = {"_ragicId": 123, "field": "value"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = expected
        
        with patch.object(service._client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await service.get_record("forms/1", 123)
            
            assert result == expected
    
    @pytest.mark.asyncio
    async def test_get_record_not_found(self, config_loader):
        """Test get_record() returns None on 404."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch.object(service._client, 'get', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            
            result = await service.get_record("forms/1", 999)
            
            assert result is None


class TestRagicServiceCreateRecord:
    """Tests for create_record() method."""
    
    @pytest.mark.asyncio
    async def test_create_record_success(self, config_loader):
        """Test create_record() returns record ID on success."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"_ragicId": 456}
        
        with patch.object(service._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await service.create_record("forms/1", {"field": "value"})
            
            assert result == 456
    
    @pytest.mark.asyncio
    async def test_create_record_failure(self, config_loader):
        """Test create_record() returns None on failure."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_response = MagicMock()
        mock_response.status_code = 400
        
        with patch.object(service._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await service.create_record("forms/1", {})
            
            assert result is None


class TestRagicServiceUpdateRecord:
    """Tests for update_record() method."""
    
    @pytest.mark.asyncio
    async def test_update_record_success(self, config_loader):
        """Test update_record() returns True on success."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(service._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await service.update_record("forms/1", 123, {"field": "updated"})
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_update_record_failure(self, config_loader):
        """Test update_record() returns False on failure."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        
        with patch.object(service._client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await service.update_record("forms/1", 123, {})
            
            assert result is False


class TestRagicServiceDeleteRecord:
    """Tests for delete_record() method."""
    
    @pytest.mark.asyncio
    async def test_delete_record_success(self, config_loader):
        """Test delete_record() returns True on success."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(service._client, 'delete', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_response
            
            result = await service.delete_record("forms/1", 123)
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_record_failure(self, config_loader):
        """Test delete_record() returns False on failure."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        mock_response = MagicMock()
        mock_response.status_code = 404
        
        with patch.object(service._client, 'delete', new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = mock_response
            
            result = await service.delete_record("forms/1", 999)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_record_not_configured(self, mock_env_vars, monkeypatch):
        """Test delete_record() returns False when not configured."""
        from core.app_context import ConfigLoader
        from services.ragic_service import RagicService
        
        monkeypatch.setenv("RAGIC_API_KEY", "")
        
        loader = ConfigLoader()
        loader.load()
        service = RagicService(loader)
        
        result = await service.delete_record("forms/1", 123)
        
        assert result is False


class TestRagicServiceClose:
    """Tests for close() method."""
    
    @pytest.mark.asyncio
    async def test_close_calls_aclose(self, config_loader):
        """Test close() calls underlying client aclose."""
        from services.ragic_service import RagicService
        
        service = RagicService(config_loader)
        
        with patch.object(service._client, 'aclose', new_callable=AsyncMock) as mock_close:
            await service.close()
            
            mock_close.assert_called_once()
