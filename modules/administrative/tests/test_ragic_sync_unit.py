"""
Unit Tests for Ragic Sync Service.

Tests synchronization of Ragic data to local PostgreSQL cache.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from pydantic import SecretStr

from modules.administrative.services.ragic_sync import RagicSyncService
from modules.administrative.core.config import AdminSettings


@pytest.fixture
def mock_settings():
    """Create mock AdminSettings."""
    settings = MagicMock(spec=AdminSettings)
    settings.ragic_api_key = SecretStr("test_api_key")
    settings.ragic_url_employee = "https://ragic.example.com/employee"
    settings.ragic_url_dept = "https://ragic.example.com/department"
    settings.field_employee_email = "1000001"
    settings.field_employee_name = "1000002"
    settings.field_employee_department = "1000003"
    settings.field_employee_supervisor_email = "1000004"
    settings.field_department_name = "1000001"
    settings.field_department_manager_email = "1000002"
    settings.sync_timeout_seconds = 30
    settings.sync_batch_size = 100
    return settings


@pytest.fixture
def ragic_service(mock_settings):
    """Create RagicSyncService with mock settings."""
    return RagicSyncService(settings=mock_settings)


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
                "1000001": {"name": "Email"},
                "1000002": {"name": "Name"},
            }
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        ragic_service._http_client = mock_client

        result = await ragic_service._fetch_form_schema("https://test.com/form")

        assert "fields" in result
        assert "1000001" in result["fields"]

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
        """Test validation passes when all fields exist."""
        employee_schema = {
            "fields": {
                "1000001": {"name": "Email"},
                "1000002": {"name": "Name"},
                "1000003": {"name": "Department"},
                "1000004": {"name": "Supervisor"},
            }
        }
        dept_schema = {
            "fields": {
                "1000001": {"name": "Name"},
                "1000002": {"name": "Manager"},
            }
        }

        with patch.object(ragic_service, '_fetch_form_schema', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [employee_schema, dept_schema]

            issues = await ragic_service._validate_field_mappings()

            assert issues["employee"] == []
            assert issues["department"] == []

    @pytest.mark.asyncio
    async def test_validate_missing_employee_field(self, ragic_service):
        """Test validation detects missing employee field."""
        employee_schema = {
            "fields": {
                "1000001": {"name": "Email"},
                # Missing 1000002, 1000003, 1000004
            }
        }
        dept_schema = {
            "fields": {
                "1000001": {"name": "Name"},
                "1000002": {"name": "Manager"},
            }
        }

        with patch.object(ragic_service, '_fetch_form_schema', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = [employee_schema, dept_schema]

            issues = await ragic_service._validate_field_mappings()

            assert len(issues["employee"]) == 3  # 3 missing fields
            assert issues["department"] == []


class TestFetchFormData:
    """Tests for _fetch_form_data method."""

    @pytest.mark.asyncio
    async def test_fetch_data_success(self, ragic_service):
        """Test successful data fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "1": {"1000001": "test@example.com", "1000002": "Test User"},
            "2": {"1000001": "user2@example.com", "1000002": "User Two"},
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


class TestUpsertEmployees:
    """Tests for _upsert_employees method."""

    @pytest.mark.asyncio
    async def test_upsert_employees_with_email(self, ragic_service):
        """Test upserting employees with valid emails."""
        mock_session = AsyncMock()

        records = [
            {
                "_ragicId": 1,
                "1000001": "emp1@example.com",
                "1000002": "Employee One",
                "1000003": "Engineering",
                "1000004": "manager@example.com",
            },
            {
                "_ragicId": 2,
                "1000001": "emp2@example.com",
                "1000002": "Employee Two",
                "1000003": "HR",
                "1000004": "hr_mgr@example.com",
            },
        ]

        with patch.object(ragic_service, '_build_name_to_email_map', new_callable=AsyncMock) as mock_map:
            mock_map.return_value = {}

            count = await ragic_service._upsert_employees(records, mock_session)

            assert count == 2
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_employees_empty(self, ragic_service):
        """Test upserting empty list returns 0."""
        mock_session = AsyncMock()

        count = await ragic_service._upsert_employees([], mock_session)

        assert count == 0
        mock_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_upsert_employees_email_recovery(self, ragic_service):
        """Test email recovery from User table."""
        mock_session = AsyncMock()

        records = [
            {
                "_ragicId": 1,
                "1000001": "",  # Missing email
                "1000002": "Employee One",
                "1000003": "Engineering",
                "1000004": "manager@example.com",
            },
        ]

        with patch.object(ragic_service, '_build_name_to_email_map', new_callable=AsyncMock) as mock_map:
            # Simulate finding email by name in User table
            mock_map.return_value = {"Employee One": "emp1@example.com"}

            count = await ragic_service._upsert_employees(records, mock_session)

            assert count == 1  # Should recover and upsert

    @pytest.mark.asyncio
    async def test_upsert_employees_skip_no_email(self, ragic_service):
        """Test skipping records without email and no fallback."""
        mock_session = AsyncMock()

        records = [
            {
                "_ragicId": 1,
                "1000001": "",  # Missing email
                "1000002": "Unknown Employee",
                "1000003": "Engineering",
                "1000004": "",
            },
        ]

        with patch.object(ragic_service, '_build_name_to_email_map', new_callable=AsyncMock) as mock_map:
            mock_map.return_value = {}  # No fallback available

            count = await ragic_service._upsert_employees(records, mock_session)

            assert count == 0  # Should skip, not upsert


class TestUpsertDepartments:
    """Tests for _upsert_departments method."""

    @pytest.mark.asyncio
    async def test_upsert_departments_success(self, ragic_service):
        """Test successful department upsert."""
        mock_session = AsyncMock()

        records = [
            {
                "_ragicId": 1,
                "1000001": "Engineering",
                "1000002": "eng_mgr@example.com",
            },
            {
                "_ragicId": 2,
                "1000001": "HR",
                "1000002": "hr_mgr@example.com",
            },
        ]

        count = await ragic_service._upsert_departments(records, mock_session)

        assert count == 2
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_departments_empty(self, ragic_service):
        """Test upserting empty list returns 0."""
        mock_session = AsyncMock()

        count = await ragic_service._upsert_departments([], mock_session)

        assert count == 0

    @pytest.mark.asyncio
    async def test_upsert_departments_skip_no_name(self, ragic_service):
        """Test skipping records without name."""
        mock_session = AsyncMock()

        records = [
            {
                "_ragicId": 1,
                "1000001": "",  # Missing name
                "1000002": "mgr@example.com",
            },
        ]

        count = await ragic_service._upsert_departments(records, mock_session)

        assert count == 0


class TestSyncAllData:
    """Tests for sync_all_data method."""

    @pytest.mark.asyncio
    async def test_sync_all_success(self, ragic_service):
        """Test successful full sync."""
        with patch.object(ragic_service, '_validate_field_mappings', new_callable=AsyncMock) as mock_validate, \
                patch.object(ragic_service, '_ensure_tables_exist', new_callable=AsyncMock) as mock_ensure, \
                patch.object(ragic_service, '_fetch_form_data', new_callable=AsyncMock) as mock_fetch, \
                patch.object(ragic_service, '_upsert_employees', new_callable=AsyncMock) as mock_emp, \
                patch.object(ragic_service, '_upsert_departments', new_callable=AsyncMock) as mock_dept, \
                patch.object(ragic_service, 'close', new_callable=AsyncMock) as mock_close, \
                patch('modules.administrative.services.ragic_sync.get_thread_local_session') as mock_session:

            mock_validate.return_value = {"employee": [], "department": []}
            mock_fetch.side_effect = [
                [{"_ragicId": 1}],  # Employee records
                [{"_ragicId": 1}],  # Department records
            ]
            mock_emp.return_value = 10
            mock_dept.return_value = 5

            # Setup async context manager for session
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            result = await ragic_service.sync_all_data()

            assert result["employees_synced"] == 10
            assert result["departments_synced"] == 5
            assert result["schema_issues"] == {
                "employee": [], "department": []}
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_with_schema_issues(self, ragic_service):
        """Test sync continues despite schema validation issues."""
        with patch.object(ragic_service, '_validate_field_mappings', new_callable=AsyncMock) as mock_validate, \
                patch.object(ragic_service, '_ensure_tables_exist', new_callable=AsyncMock), \
                patch.object(ragic_service, '_fetch_form_data', new_callable=AsyncMock) as mock_fetch, \
                patch.object(ragic_service, '_upsert_employees', new_callable=AsyncMock) as mock_emp, \
                patch.object(ragic_service, '_upsert_departments', new_callable=AsyncMock) as mock_dept, \
                patch.object(ragic_service, 'close', new_callable=AsyncMock), \
                patch('modules.administrative.services.ragic_sync.get_thread_local_session') as mock_session:

            mock_validate.return_value = {
                "employee": ["1000005"],  # Missing field
                "department": [],
            }
            mock_fetch.side_effect = [[], []]
            mock_emp.return_value = 0
            mock_dept.return_value = 0

            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            result = await ragic_service.sync_all_data()

            # Should still complete despite schema issues
            assert result["schema_issues"]["employee"] == ["1000005"]


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
