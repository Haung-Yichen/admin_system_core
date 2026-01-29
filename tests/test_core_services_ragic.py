"""
Unit Tests for core.services.ragic.

Tests RagicService for employee verification.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch


class TestRagicFieldConfig:
    """Tests for RagicFieldConfig."""
    
    def test_field_config_initialization(self):
        """Test RagicFieldConfig loads field IDs from config."""
        from core.services.ragic import RagicFieldConfig
        
        config = {
            "ragic": {
                "field_email": "1005977",
                "field_name": "1005975",
                "field_door_access_id": "1005983"
            }
        }
        
        field_config = RagicFieldConfig(config)
        
        assert field_config.email_id == "1005977"
        assert field_config.name_id == "1005975"
        assert field_config.door_access_id == "1005983"
    
    def test_field_config_defaults(self):
        """Test RagicFieldConfig uses defaults if fields missing."""
        from core.services.ragic import RagicFieldConfig
        
        config = {"ragic": {}}
        field_config = RagicFieldConfig(config)
        
        assert field_config.email_id is not None
        assert field_config.name_id is not None


class TestRagicService:
    """Tests for RagicService class."""
    
    @pytest.fixture
    def ragic_service(self, mock_env_vars):
        """Create RagicService instance."""
        from core.services.ragic import RagicService
        
        return RagicService()
    
    def test_ragic_service_initialization(self, ragic_service):
        """Test RagicService initializes correctly."""
        assert ragic_service._base_url is not None
        assert ragic_service._field_config is not None
    
    def test_fuzzy_match_exact(self, ragic_service):
        """Test _fuzzy_match() with exact match."""
        result = ragic_service._fuzzy_match("Email", "Email")
        
        assert result is True
    
    def test_fuzzy_match_case_insensitive(self, ragic_service):
        """Test _fuzzy_match() is case-insensitive."""
        result = ragic_service._fuzzy_match("EMAIL", "email")
        
        assert result is True
    
    def test_fuzzy_match_different(self, ragic_service):
        """Test _fuzzy_match() with different strings."""
        result = ragic_service._fuzzy_match("Email", "Name", threshold=0.8)
        
        assert result is False
    
    def test_get_field_value_by_id(self, ragic_service):
        """Test _get_field_value() retrieves by field ID."""
        record = {
            "1005977": "test@example.com",
            "1005975": "Test User"
        }
        
        value = ragic_service._get_field_value(record, "1005977")
        
        assert value == "test@example.com"
    
    def test_get_field_value_by_underscore_id(self, ragic_service):
        """Test _get_field_value() retrieves by underscore-prefixed ID."""
        record = {
            "_1005977": "test@example.com"
        }
        
        value = ragic_service._get_field_value(record, "1005977")
        
        assert value == "test@example.com"
    
    def test_get_field_value_not_found(self, ragic_service):
        """Test _get_field_value() returns None if not found."""
        record = {
            "other_field": "value"
        }
        
        value = ragic_service._get_field_value(record, "1005977")
        
        assert value is None
    
    def test_get_field_value_strips_whitespace(self, ragic_service):
        """Test _get_field_value() strips whitespace."""
        record = {
            "1005977": "  test@example.com  "
        }
        
        value = ragic_service._get_field_value(record, "1005977")
        
        assert value == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_get_all_employees_success(self, ragic_service):
        """Test get_all_employees() fetches records from Ragic."""
        mock_response = {
            "1": {"_ragic_id": "1", "1000381": "test1@example.com", "1000376": "User 1"},
            "2": {"_ragic_id": "2", "1000381": "test2@example.com", "1000376": "User 2"}
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_resp = Mock()
            mock_resp.json = Mock(return_value=mock_response)
            mock_resp.raise_for_status = Mock()
            
            async def mock_get(*args, **kwargs):
                return mock_resp
            
            mock_client.get = mock_get
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            employees = await ragic_service.get_all_employees()
            
            assert len(employees) == 2
            assert employees[0]["_ragic_id"] == "1"
    
    @pytest.mark.asyncio
    async def test_get_all_employees_error(self, ragic_service):
        """Test get_all_employees() handles errors gracefully."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("Network error")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client
            
            employees = await ragic_service.get_all_employees()
            
            assert employees == []
    
    @pytest.mark.asyncio
    async def test_verify_email_exists_found(self, ragic_service):
        """Test verify_email_exists() finds matching email."""
        with patch.object(ragic_service, 'get_all_employees', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"_ragic_id": "1", "1005977": "test@example.com", "1005975": "Test User"}
            ]
            
            result = await ragic_service.verify_email_exists("test@example.com")
            
            assert result is not None
            assert result.email == "test@example.com"
            assert result.name == "Test User"
    
    @pytest.mark.asyncio
    async def test_verify_email_exists_not_found(self, ragic_service):
        """Test verify_email_exists() returns None if not found."""
        with patch.object(ragic_service, 'get_all_employees', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"_ragic_id": "1", "1005977": "other@example.com", "1005975": "Other User"}
            ]
            
            result = await ragic_service.verify_email_exists("test@example.com")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_verify_email_exists_case_insensitive(self, ragic_service):
        """Test verify_email_exists() is case-insensitive."""
        with patch.object(ragic_service, 'get_all_employees', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = [
                {"_ragic_id": "1", "1005977": "Test@Example.COM", "1005975": "Test User"}
            ]
            
            result = await ragic_service.verify_email_exists("test@example.com")
            
            assert result is not None
    
    def test_parse_employee_record(self, ragic_service):
        """Test _parse_employee_record() creates RagicEmployeeData."""
        record = {
            "_ragic_id": "1",
            "1005977": "test@example.com",
            "1005975": "Test User",
            "1005983": "EMP001"
        }
        
        result = ragic_service._parse_employee_record(record)
        
        assert result.employee_id == "EMP001"
        assert result.email == "test@example.com"
        assert result.name == "Test User"
        assert result.is_active is True
    
    def test_parse_employee_record_fallback_to_ragic_id(self, ragic_service):
        """Test _parse_employee_record() uses ragic_id if no employee ID."""
        record = {
            "_ragic_id": "123",
            "1005977": "test@example.com",
            "1005975": "Test User"
        }
        
        result = ragic_service._parse_employee_record(record)
        
        assert result.employee_id == "123"
    
    def test_get_ragic_service_singleton(self, mock_env_vars):
        """Test get_ragic_service() returns singleton."""
        from core.services.ragic import get_ragic_service
        import core.services.ragic as ragic_module
        
        ragic_module._ragic_service = None
        
        service1 = get_ragic_service()
        service2 = get_ragic_service()
        
        assert service1 is service2
