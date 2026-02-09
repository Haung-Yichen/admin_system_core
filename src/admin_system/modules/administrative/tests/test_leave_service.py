"""
Unit Tests for Leave Service.

Tests the LeaveService class for leave request handling.
Updated to match current architecture (2026-01).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date


@pytest.fixture
def mock_admin_settings():
    """Create mock admin settings."""
    settings = MagicMock()
    settings.ragic_api_key = MagicMock()
    settings.ragic_api_key.get_secret_value.return_value = "test-api-key"
    settings.ragic_url_leave_request = "https://test.ragic.com/leave"
    settings.ragic_url_leave = "https://test.ragic.com/leave"
    settings.sync_timeout_seconds = 30
    return settings


@pytest.fixture
def mock_account():
    """Create mock AdministrativeAccount."""
    account = MagicMock()
    account.name = "John Doe"
    account.primary_email = "john.doe@company.com"
    account.emails = "john.doe@company.com"
    account.sales_dept = "Sales Division"
    account.sales_dept_manager = "Manager Name"
    account.org_name = "Jane Manager/HR"
    account.mentor_name = "Jane Manager"
    account.mentor_id_card = "A123456789"
    return account


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def leave_service(mock_admin_settings):
    """Create LeaveService with mocked settings."""
    with patch('modules.administrative.services.leave.get_admin_settings', return_value=mock_admin_settings):
        from modules.administrative.services.leave import LeaveService
        service = LeaveService(settings=mock_admin_settings)
        return service


class TestLeaveServiceInit:
    """Tests for LeaveService initialization."""

    def test_init_with_settings(self, mock_admin_settings):
        """Test service initializes with provided settings."""
        with patch('modules.administrative.services.leave.get_admin_settings', return_value=mock_admin_settings):
            from modules.administrative.services.leave import LeaveService
            service = LeaveService(settings=mock_admin_settings)
            assert service._settings == mock_admin_settings

    def test_init_with_default_settings(self, mock_admin_settings):
        """Test service initializes with default settings."""
        with patch('modules.administrative.services.leave.get_admin_settings', return_value=mock_admin_settings):
            from modules.administrative.services.leave import LeaveService
            service = LeaveService()
            assert service._settings == mock_admin_settings


class TestLeaveServiceGetInitData:
    """Tests for get_init_data method."""

    @pytest.mark.asyncio
    async def test_get_init_data_success(self, leave_service, mock_account, mock_db_session):
        """Test successful init data retrieval."""
        # Setup mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_account
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await leave_service.get_init_data("john.doe@company.com", mock_db_session)

        assert result["name"] == "John Doe"
        assert result["email"] == "john.doe@company.com"
        # Current schema uses these fields
        assert "sales_dept" in result
        assert "sales_dept_manager" in result
        assert "direct_supervisor" in result

    @pytest.mark.asyncio
    async def test_get_init_data_employee_not_found(self, leave_service, mock_db_session):
        """Test raises EmployeeNotFoundError when account not in cache."""
        from modules.administrative.services.leave import EmployeeNotFoundError
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(EmployeeNotFoundError) as exc_info:
            await leave_service.get_init_data("unknown@company.com", mock_db_session)

        assert "unknown@company.com" in str(exc_info.value)


class TestLeaveServiceSubmitRequest:
    """Tests for submit_leave_request method."""

    @pytest.mark.asyncio
    async def test_submit_request_employee_not_found(self, leave_service, mock_db_session):
        """Test raises EmployeeNotFoundError when account not found."""
        from modules.administrative.services.leave import EmployeeNotFoundError
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(EmployeeNotFoundError):
            await leave_service.submit_leave_request(
                email="unknown@company.com",
                leave_dates=["2024-03-15"],
                reason="Test",
                db=mock_db_session,
            )


class TestGetLeaveServiceSingleton:
    """Tests for get_leave_service singleton."""

    def test_singleton_returns_same_instance(self, mock_admin_settings):
        """Test get_leave_service returns same instance."""
        with patch('modules.administrative.services.leave.get_admin_settings', return_value=mock_admin_settings):
            from modules.administrative.services.leave import get_leave_service
            import modules.administrative.services.leave as leave_module
            
            # Reset singleton
            leave_module._leave_service = None
            
            service1 = get_leave_service()
            service2 = get_leave_service()
            
            assert service1 is service2
