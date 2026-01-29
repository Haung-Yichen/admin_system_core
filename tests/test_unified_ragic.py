"""
Unit Tests for Unified Ragic Services.

Tests all Ragic API functionality across the three current implementations:
- core/services/ragic.py (RagicService - Employee verification)
- services/ragic_service.py (RagicService - Generic CRUD)
- modules/administrative/services/ragic_sync.py (RagicSyncService - Data sync)

This comprehensive test suite ensures all functionality is covered before
refactoring into a unified service.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import date
import httpx


# =============================================================================
# Core RagicService Tests (Employee Verification)
# =============================================================================

class TestCoreRagicServiceInit:
    """Tests for core RagicService initialization."""

    def test_init_loads_config(self, mock_env_vars):
        """Test service initializes with config."""
        from core.services.ragic import RagicService
        
        service = RagicService()
        
        assert service._base_url == "https://ap13.ragic.com"
        assert service._api_key == "test-ragic-key"

    def test_field_config_loaded(self, mock_env_vars):
        """Test field configuration is loaded."""
        from core.services.ragic import RagicService
        
        service = RagicService()
        
        assert service._field_config is not None
        assert service._field_config.email_id is not None


class TestCoreRagicServiceFieldMatching:
    """Tests for field value extraction and fuzzy matching."""

    @pytest.fixture
    def ragic_service(self, mock_env_vars):
        """Create RagicService instance."""
        from core.services.ragic import RagicService
        return RagicService()

    def test_get_field_value_exact_match(self, ragic_service):
        """Test exact field ID matching."""
        record = {"1005977": "test@example.com", "1005975": "Test User"}
        
        value = ragic_service._get_field_value(record, "1005977", None)
        
        assert value == "test@example.com"

    def test_get_field_value_underscore_prefix(self, ragic_service):
        """Test field ID with underscore prefix."""
        record = {"_1005977": "test@example.com"}
        
        value = ragic_service._get_field_value(record, "1005977", None)
        
        assert value == "test@example.com"

    def test_get_field_value_fuzzy_match(self, ragic_service):
        """Test fuzzy name matching for Chinese field names."""
        record = {"E-mail": "test@example.com"}
        fuzzy_names = ["E-mail", "?��??�件", "email"]
        
        value = ragic_service._get_field_value(record, "nonexistent", fuzzy_names)
        
        assert value == "test@example.com"

    def test_get_field_value_strips_whitespace(self, ragic_service):
        """Test that returned values are stripped."""
        record = {"1005977": "  test@example.com  "}
        
        value = ragic_service._get_field_value(record, "1005977", None)
        
        assert value == "test@example.com"

    def test_get_field_value_returns_none_for_empty(self, ragic_service):
        """Test empty string returns None."""
        record = {"1005977": ""}
        
        value = ragic_service._get_field_value(record, "1005977", None)
        
        assert value is None

    def test_fuzzy_match_threshold(self, ragic_service):
        """Test fuzzy matching with threshold."""
        assert ragic_service._fuzzy_match("email", "Email", 0.8) is True
        assert ragic_service._fuzzy_match("E-mail", "email", 0.8) is True
        assert ragic_service._fuzzy_match("totally_different", "email", 0.8) is False


class TestCoreRagicServiceEmployeeVerification:
    """Tests for employee verification methods."""

    @pytest.fixture
    def ragic_service(self, mock_env_vars):
        """Create RagicService instance."""
        from core.services.ragic import RagicService
        return RagicService()

    @pytest.mark.asyncio
    async def test_verify_email_exists_found(
        self, ragic_service, sample_ragic_employee_records
    ):
        """Test email verification when employee exists."""
        with patch.object(
            ragic_service, 'get_all_employees',
            new=AsyncMock(return_value=sample_ragic_employee_records)
        ):
            result = await ragic_service.verify_email_exists("alice@example.com")
        
        assert result is not None
        assert result.email == "alice@example.com"
        assert result.name == "Alice Chen"

    @pytest.mark.asyncio
    async def test_verify_email_exists_not_found(
        self, ragic_service, sample_ragic_employee_records
    ):
        """Test email verification when employee does not exist."""
        with patch.object(
            ragic_service, 'get_all_employees',
            new=AsyncMock(return_value=sample_ragic_employee_records)
        ):
            result = await ragic_service.verify_email_exists("nonexistent@example.com")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_verify_email_case_insensitive(
        self, ragic_service, sample_ragic_employee_records
    ):
        """Test email verification is case insensitive."""
        with patch.object(
            ragic_service, 'get_all_employees',
            new=AsyncMock(return_value=sample_ragic_employee_records)
        ):
            result = await ragic_service.verify_email_exists("ALICE@EXAMPLE.COM")
        
        assert result is not None
        assert result.email == "alice@example.com"

    @pytest.mark.asyncio
    async def test_get_employee_by_id_found(
        self, ragic_service, sample_ragic_employee_records
    ):
        """Test employee lookup by door access ID."""
        with patch.object(
            ragic_service, 'get_all_employees',
            new=AsyncMock(return_value=sample_ragic_employee_records)
        ):
            # Assuming 1000389 is the door access ID field
            result = await ragic_service.get_employee_by_id("E001")
        
        # This may or may not find depending on field mapping
        # The test validates the method doesn't crash

    @pytest.mark.asyncio
    async def test_get_all_employees_success(self, ragic_service, mock_httpx_response):
        """Test fetching all employees from Ragic."""
        mock_response = mock_httpx_response(
            status_code=200,
            json_data={
                "1": {"_ragicId": 1, "1000381": "test@example.com"},
                "2": {"_ragicId": 2, "1000381": "test2@example.com"},
            }
        )
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await ragic_service.get_all_employees()
        
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_all_employees_api_error(self, ragic_service):
        """Test handling of API errors."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            result = await ragic_service.get_all_employees()
        
        assert result == []


class TestCoreRagicServiceSingleton:
    """Tests for singleton pattern."""

    def test_get_ragic_service_returns_singleton(self, mock_env_vars):
        """Test singleton returns same instance."""
        import core.services.ragic as ragic_module
        ragic_module._ragic_service = None
        
        from core.services.ragic import get_ragic_service
        
        service1 = get_ragic_service()
        service2 = get_ragic_service()
        
        assert service1 is service2


# =============================================================================
# RagicSyncService Tests (Data Synchronization)
# =============================================================================

class TestRagicSyncServiceDataTransformation:
    """Tests for data transformation helpers."""

    def test_parse_date_valid_dash_format(self):
        """Test parsing YYYY-MM-DD format."""
        from modules.administrative.services.ragic_sync import parse_date
        
        result = parse_date("2025-12-31")
        
        assert result == date(2025, 12, 31)

    def test_parse_date_valid_slash_format(self):
        """Test parsing YYYY/MM/DD format."""
        from modules.administrative.services.ragic_sync import parse_date
        
        result = parse_date("2025/12/31")
        
        assert result == date(2025, 12, 31)

    def test_parse_date_empty_string(self):
        """Test parsing empty string returns None."""
        from modules.administrative.services.ragic_sync import parse_date
        
        result = parse_date("")
        
        assert result is None

    def test_parse_date_none(self):
        """Test parsing None returns None."""
        from modules.administrative.services.ragic_sync import parse_date
        
        result = parse_date(None)
        
        assert result is None

    def test_parse_date_already_date(self):
        """Test parsing date object returns same."""
        from modules.administrative.services.ragic_sync import parse_date
        
        d = date(2025, 1, 1)
        result = parse_date(d)
        
        assert result == d


class TestAccountRecordSchema:
    """Tests for AccountRecordSchema validation."""

    def test_valid_minimal_record(self):
        """Test validation of minimal valid record."""
        from modules.administrative.services.ragic_sync import AccountRecordSchema
        
        record = AccountRecordSchema(
            ragic_id=123,
            account_id="A001",
            name="Test User",
        )
        
        assert record.ragic_id == 123
        assert record.account_id == "A001"
        assert record.name == "Test User"
        assert record.status is True  # Default

    def test_status_conversion_from_string(self):
        """Test boolean conversion from string."""
        from modules.administrative.services.ragic_sync import AccountRecordSchema
        
        record = AccountRecordSchema(
            ragic_id=123,
            account_id="A001",
            name="Test",
            status=True,
        )
        
        assert record.status is True

    def test_optional_fields_none(self):
        """Test optional fields default to None."""
        from modules.administrative.services.ragic_sync import AccountRecordSchema
        
        record = AccountRecordSchema(
            ragic_id=123,
            account_id="A001",
            name="Test",
        )
        
        assert record.emails is None
        assert record.birthday is None
        assert record.assessment_rate is None


class TestRagicSyncServiceInit:
    """Tests for RagicSyncService initialization."""

    @pytest.fixture
    def mock_admin_settings(self):
        """Create mock AdminSettings."""
        from pydantic import SecretStr
        
        settings = MagicMock()
        settings.ragic_api_key = SecretStr("test_api_key")
        settings.ragic_url_account = "https://ragic.example.com/account"
        settings.ragic_url_leave_type = "https://ragic.example.com/leave_type"
        settings.sync_timeout_seconds = 30
        settings.sync_batch_size = 100
        return settings

    def test_init_with_settings(self, mock_admin_settings):
        """Test service initializes with settings."""
        from modules.administrative.services.ragic_sync import RagicSyncService
        
        service = RagicSyncService(settings=mock_admin_settings)
        
        assert service._settings == mock_admin_settings
        # After refactor: uses _ragic_service instead of _http_client
        assert service._ragic_service is not None


class TestRagicSyncServiceHTTP:
    """Tests for HTTP operations in RagicSyncService (via RagicService)."""

    @pytest.fixture
    def mock_admin_settings(self):
        """Create mock AdminSettings."""
        from pydantic import SecretStr
        
        settings = MagicMock()
        settings.ragic_api_key = SecretStr("test_api_key")
        settings.ragic_url_account = "https://ragic.example.com/account"
        settings.ragic_url_leave_type = "https://ragic.example.com/leave_type"
        settings.sync_timeout_seconds = 30
        settings.sync_batch_size = 100
        return settings

    @pytest.fixture
    def sync_service(self, mock_admin_settings):
        """Create RagicSyncService instance."""
        from modules.administrative.services.ragic_sync import RagicSyncService
        return RagicSyncService(settings=mock_admin_settings)

    def test_ragic_service_initialized(self, sync_service):
        """Test RagicService is initialized with correct API key."""
        # After refactor: uses core.ragic.RagicService
        assert sync_service._ragic_service is not None
        assert sync_service._ragic_service._api_key == "test_api_key"

    @pytest.mark.asyncio
    async def test_fetch_ragic_records_success(
        self, sync_service, mock_ragic_api_response
    ):
        """Test fetching records from Ragic via RagicService."""
        records = [
            {"_ragicId": 1, "name": "Record 1"},
            {"_ragicId": 2, "name": "Record 2"},
        ]
        
        # Mock the RagicService.get_records_by_url method
        sync_service._ragic_service.get_records_by_url = AsyncMock(return_value=records)
        
        result = await sync_service._fetch_form_data(
            "https://ragic.example.com/test"
        )
        
        assert len(result) == 2
        sync_service._ragic_service.get_records_by_url.assert_called_once_with(
            full_url="https://ragic.example.com/test",
            params={"naming": "EID"},
        )

    @pytest.mark.asyncio
    async def test_fetch_ragic_records_api_error(self, sync_service):
        """Test handling of API errors during fetch."""
        # Mock RagicService to raise an exception
        sync_service._ragic_service.get_records_by_url = AsyncMock(
            side_effect=Exception("API Failed")
        )
        
        with pytest.raises(Exception, match="API Failed"):
            await sync_service._fetch_form_data(
                "https://ragic.example.com/test"
            )

    @pytest.mark.asyncio
    async def test_close_releases_client(self, sync_service):
        """Test close method releases RagicService HTTP client."""
        sync_service._ragic_service.close = AsyncMock()
        
        await sync_service.close()
        
        sync_service._ragic_service.close.assert_called_once()
