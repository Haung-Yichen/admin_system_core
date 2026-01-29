"""
Unit Tests for Ragic Sync Service.

Tests synchronization of Ragic Account data to local PostgreSQL cache.
"""

import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from pydantic import SecretStr

from modules.administrative.services.ragic_sync import (
    RagicSyncService,
    AccountRecordSchema,
    parse_date,
    parse_bool,
    parse_float,
    parse_int,
    parse_string,
    transform_ragic_record,
)
from modules.administrative.core.config import AdminSettings


@pytest.fixture
def mock_settings():
    """Create mock AdminSettings."""
    settings = MagicMock(spec=AdminSettings)
    settings.ragic_api_key = SecretStr("test_api_key")
    settings.ragic_url_account = "https://ragic.example.com/account"
    settings.sync_timeout_seconds = 30
    settings.sync_batch_size = 100
    return settings


@pytest.fixture
def ragic_service(mock_settings):
    """Create RagicSyncService with mock settings."""
    return RagicSyncService(settings=mock_settings)


class TestParsingHelpers:
    """Tests for data parsing helper functions."""

    def test_parse_date_valid(self):
        """Test parsing valid date string."""
        result = parse_date("2024-03-15")
        assert result == date(2024, 3, 15)

    def test_parse_date_empty(self):
        """Test parsing empty string returns None."""
        assert parse_date("") is None
        assert parse_date(None) is None

    def test_parse_date_invalid(self):
        """Test parsing invalid date returns None."""
        assert parse_date("invalid-date") is None
        assert parse_date("15/03/2024") is None

    def test_parse_bool_values(self):
        """Test parsing boolean values."""
        assert parse_bool("1") is True
        assert parse_bool("0") is False
        assert parse_bool(1) is True
        assert parse_bool(0) is False
        assert parse_bool("true") is True
        assert parse_bool("是") is True
        assert parse_bool("") is None
        assert parse_bool(None) is None

    def test_parse_float_values(self):
        """Test parsing float values."""
        assert parse_float("0.85") == 0.85
        assert parse_float("100") == 100.0
        assert parse_float(0.5) == 0.5
        assert parse_float("1,234.56") == 1234.56
        assert parse_float("") is None
        assert parse_float(None) is None

    def test_parse_int_values(self):
        """Test parsing integer values."""
        assert parse_int("123") == 123
        assert parse_int(456) == 456
        assert parse_int("1,000") == 1000
        assert parse_int("") is None
        assert parse_int(None) is None

    def test_parse_string_values(self):
        """Test parsing string values."""
        assert parse_string("  test  ") == "test"
        assert parse_string("") is None
        assert parse_string(None) is None
        assert parse_string(123) == "123"


class TestTransformRagicRecord:
    """Tests for transform_ragic_record function."""

    def test_transform_basic_fields(self):
        """Test transforming basic fields from Ragic record."""
        record = {
            "_ragicId": 123,
            "1005971": "123",  # ragic_id
            "1005972": "A001",  # account_id
            "1005975": "Test User",  # name
            "1005974": "1",  # status
        }
        
        result = transform_ragic_record(record)
        
        assert result["ragic_id"] == 123
        assert result["account_id"] == "A001"
        assert result["name"] == "Test User"
        assert result["status"] is True

    def test_transform_date_fields(self):
        """Test transforming date fields."""
        record = {
            "_ragicId": 1,
            "1005972": "A001",
            "1005975": "Test",
            "1005974": "1",
            "1006016": "2024-01-15",  # approval_date
            "1006017": "2024-02-01",  # effective_date
        }
        
        result = transform_ragic_record(record)
        
        assert result["approval_date"] == date(2024, 1, 15)
        assert result["effective_date"] == date(2024, 2, 1)

    def test_transform_float_fields(self):
        """Test transforming float fields."""
        record = {
            "_ragicId": 1,
            "1005972": "A001",
            "1005975": "Test",
            "1005974": "1",
            "1005982": "0.85",  # assessment_rate
            "1006025": "0.01",  # court_withholding_rate
        }
        
        result = transform_ragic_record(record)
        
        assert result["assessment_rate"] == 0.85
        assert result["court_withholding_rate"] == 0.01


class TestAccountRecordSchema:
    """Tests for AccountRecordSchema Pydantic model."""

    def test_schema_validates_required_fields(self):
        """Test schema validates required fields."""
        data = {
            "ragic_id": 123,
            "account_id": "A001",
            "name": "Test User",
            "status": True,
        }
        
        schema = AccountRecordSchema(**data)
        
        assert schema.ragic_id == 123
        assert schema.account_id == "A001"

    def test_schema_with_all_fields(self):
        """Test schema with all optional fields."""
        data = {
            "ragic_id": 123,
            "account_id": "A001",
            "name": "Test User",
            "status": True,
            "emails": "test@example.com",
            "org_code": "ORG001",
            "org_name": "Engineering",
            "approval_date": date(2024, 1, 1),
            "assessment_rate": 0.85,
        }
        
        schema = AccountRecordSchema(**data)
        
        assert schema.emails == "test@example.com"
        assert schema.org_code == "ORG001"
        assert schema.assessment_rate == 0.85


class TestRagicSyncServiceInit:
    """Tests for RagicSyncService initialization."""

    def test_init_with_settings(self, mock_settings):
        """Test service initializes with provided settings."""
        service = RagicSyncService(settings=mock_settings)
        assert service._settings == mock_settings

    def test_init_without_settings(self):
        """Test service uses get_admin_settings when no settings provided."""
        with patch('modules.administrative.services.ragic_sync.get_admin_settings') as mock_get:
            mock_get.return_value = MagicMock()
            service = RagicSyncService()
            mock_get.assert_called_once()


class TestGetAuthHeaders:
    """Tests for _get_auth_headers method."""

    def test_auth_headers_format(self, ragic_service):
        """Test authentication headers are properly formatted."""
        headers = ragic_service._get_auth_headers()

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")


class TestFetchFormSchema:
    """Tests for _fetch_form_schema method."""

    @pytest.mark.asyncio
    async def test_fetch_schema_success(self, ragic_service):
        """Test successful schema fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "fields": {
                "1005971": {"name": "帳號系統編號"},
                "1005972": {"name": "帳號"},
                "1005975": {"name": "姓名"},
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        ragic_service._http_client = mock_client

        result = await ragic_service._fetch_form_schema("https://test.com/form")

        assert "fields" in result
        assert "1005971" in result["fields"]

    @pytest.mark.asyncio
    async def test_fetch_schema_http_error(self, ragic_service):
        """Test handling HTTP error during schema fetch."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPError("Connection failed"))
        ragic_service._http_client = mock_client

        with pytest.raises(httpx.HTTPError):
            await ragic_service._fetch_form_schema("https://test.com/form")


class TestValidateFieldMappings:
    """Tests for _validate_field_mappings method."""

    @pytest.mark.asyncio
    async def test_validate_all_fields_exist(self, ragic_service):
        """Test validation passes when all critical fields exist."""
        schema = {
            "fields": {
                "1005971": {"name": "帳號系統編號"},
                "1005972": {"name": "帳號"},
                "1005975": {"name": "姓名"},
                "1005974": {"name": "狀態"},
            }
        }

        with patch.object(ragic_service, '_fetch_form_schema', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = schema

            issues = await ragic_service._validate_field_mappings()

            assert issues == []

    @pytest.mark.asyncio
    async def test_validate_missing_critical_field(self, ragic_service):
        """Test validation detects missing critical field."""
        schema = {
            "fields": {
                "1005971": {"name": "帳號系統編號"},
                # Missing 1005972, 1005975, 1005974
            }
        }

        with patch.object(ragic_service, '_fetch_form_schema', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = schema

            issues = await ragic_service._validate_field_mappings()

            assert len(issues) == 3


class TestFetchFormData:
    """Tests for _fetch_form_data method."""

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, ragic_service):
        """Test successful data fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "1": {"1005972": "A001", "1005975": "User One"},
            "2": {"1005972": "A002", "1005975": "User Two"},
            "_metaData": {"total": 2},  # Should be skipped
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        ragic_service._http_client = mock_client

        records = await ragic_service._fetch_form_data("https://test.com/form")

        assert len(records) == 2
        assert records[0]["_ragicId"] == 1
        assert records[1]["_ragicId"] == 2

    @pytest.mark.asyncio
    async def test_fetch_data_empty(self, ragic_service):
        """Test fetching empty data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"_metaData": {"total": 0}}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        ragic_service._http_client = mock_client

        records = await ragic_service._fetch_form_data("https://test.com/form")

        assert records == []


class TestUpsertAccounts:
    """Tests for _upsert_accounts method."""

    @pytest.mark.asyncio
    async def test_upsert_accounts_success(self, ragic_service):
        """Test upserting accounts with valid data."""
        mock_session = AsyncMock()

        records = [
            {
                "_ragicId": 1,
                "1005971": "1",
                "1005972": "A001",
                "1005975": "User One",
                "1005974": "1",
            },
            {
                "_ragicId": 2,
                "1005971": "2",
                "1005972": "A002",
                "1005975": "User Two",
                "1005974": "1",
            },
        ]

        synced, skipped = await ragic_service._upsert_accounts(records, mock_session)

        assert synced == 2
        assert skipped == 0
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_accounts_empty(self, ragic_service):
        """Test upserting empty list returns 0."""
        mock_session = AsyncMock()

        synced, skipped = await ragic_service._upsert_accounts([], mock_session)

        assert synced == 0
        assert skipped == 0
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_accounts_skip_no_account_id(self, ragic_service):
        """Test skipping records without account_id."""
        mock_session = AsyncMock()

        records = [
            {
                "_ragicId": 1,
                "1005971": "1",
                "1005972": "",  # Missing account_id
                "1005975": "Unknown User",
                "1005974": "1",
            },
        ]

        synced, skipped = await ragic_service._upsert_accounts(records, mock_session)

        assert synced == 0
        assert skipped == 1


class TestSyncAllData:
    """Tests for sync_all_data method."""

    @pytest.mark.asyncio
    async def test_sync_all_success(self, ragic_service):
        """Test successful full sync."""
        with patch.object(ragic_service, '_validate_field_mappings', new_callable=AsyncMock) as mock_validate, \
                patch.object(ragic_service, '_ensure_tables_exist', new_callable=AsyncMock) as mock_ensure, \
                patch.object(ragic_service, '_fetch_form_data', new_callable=AsyncMock) as mock_fetch, \
                patch.object(ragic_service, '_upsert_accounts', new_callable=AsyncMock) as mock_upsert, \
                patch.object(ragic_service, 'close', new_callable=AsyncMock) as mock_close, \
                patch('modules.administrative.services.ragic_sync.get_thread_local_session') as mock_session:

            mock_validate.return_value = []
            mock_fetch.return_value = [{"_ragicId": 1}]
            mock_upsert.return_value = (10, 2)

            # Setup async context manager for session
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            result = await ragic_service.sync_all_data()

            assert result["accounts_synced"] == 10
            assert result["accounts_skipped"] == 2
            assert result["schema_issues"] == []
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_with_schema_issues(self, ragic_service):
        """Test sync continues despite schema validation issues."""
        with patch.object(ragic_service, '_validate_field_mappings', new_callable=AsyncMock) as mock_validate, \
                patch.object(ragic_service, '_ensure_tables_exist', new_callable=AsyncMock), \
                patch.object(ragic_service, '_fetch_form_data', new_callable=AsyncMock) as mock_fetch, \
                patch.object(ragic_service, '_upsert_accounts', new_callable=AsyncMock) as mock_upsert, \
                patch.object(ragic_service, 'close', new_callable=AsyncMock), \
                patch('modules.administrative.services.ragic_sync.get_thread_local_session') as mock_session:

            mock_validate.return_value = ["1005974"]  # Missing field
            mock_fetch.return_value = []
            mock_upsert.return_value = (0, 0)

            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            result = await ragic_service.sync_all_data()

            # Should still complete despite schema issues
            assert result["schema_issues"] == ["1005974"]


class TestClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_close_client(self, ragic_service):
        """Test closing HTTP client."""
        mock_client = AsyncMock()
        ragic_service._http_client = mock_client

        await ragic_service.close()

        mock_client.aclose.assert_called_once()
        assert ragic_service._http_client is None

    @pytest.mark.asyncio
    async def test_close_no_client(self, ragic_service):
        """Test closing when no client exists."""
        ragic_service._http_client = None

        await ragic_service.close()  # Should not raise

        assert ragic_service._http_client is None
