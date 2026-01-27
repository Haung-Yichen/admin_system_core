"""
Unit Tests for Leave Service.

Tests the LeaveService class which handles leave request business logic.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from modules.administrative.services.leave import (
    LeaveService,
    LeaveError,
    EmployeeNotFoundError,
    DepartmentNotFoundError,
    SubmissionError,
    get_leave_service,
)
from modules.administrative.models import AdministrativeEmployee, AdministrativeDepartment


@pytest.fixture
def mock_admin_settings():
    """Create mock admin settings."""
    settings = MagicMock()
    settings.ragic_api_key = MagicMock()
    settings.ragic_api_key.get_secret_value.return_value = "test-api-key"
    settings.sync_timeout_seconds = 30
    settings.field_employee_email = "1001132"
    settings.field_employee_name = "1001129"
    settings.field_employee_supervisor_email = "1001182"
    settings.field_department_manager_email = "1002509"
    return settings


@pytest.fixture
def leave_service(mock_admin_settings):
    """Create LeaveService with mock settings."""
    return LeaveService(settings=mock_admin_settings)


@pytest.fixture
def mock_employee():
    """Create a mock employee record."""
    employee = MagicMock(spec=AdministrativeEmployee)
    employee.email = "john.doe@company.com"
    employee.name = "John Doe"
    employee.department_name = "Engineering"
    employee.supervisor_email = "manager@company.com"
    employee.ragic_id = 12345
    return employee


@pytest.fixture
def mock_department():
    """Create a mock department record."""
    dept = MagicMock(spec=AdministrativeDepartment)
    dept.name = "Engineering"
    dept.manager_email = "dept_head@company.com"
    dept.ragic_id = 100
    return dept


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session


class TestLeaveServiceInit:
    """Tests for LeaveService initialization."""

    def test_init_with_default_settings(self, mock_admin_settings):
        """Test service initializes with default settings."""
        with patch('modules.administrative.services.leave.get_admin_settings', return_value=mock_admin_settings):
            service = LeaveService()
            assert service._settings == mock_admin_settings

    def test_init_with_custom_settings(self, mock_admin_settings):
        """Test service initializes with custom settings."""
        service = LeaveService(settings=mock_admin_settings)
        assert service._settings == mock_admin_settings

    def test_http_client_lazy_init(self, leave_service):
        """Test HTTP client is lazily initialized."""
        assert leave_service._http_client is None
        # Access the client property would trigger initialization


class TestLeaveServiceGetInitData:
    """Tests for get_init_data method."""

    @pytest.mark.asyncio
    async def test_get_init_data_success(self, leave_service, mock_employee, mock_db_session):
        """Test successful init data retrieval."""
        # Setup mock query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_employee
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await leave_service.get_init_data("john.doe@company.com", mock_db_session)

        assert result["name"] == "John Doe"
        assert result["department"] == "Engineering"
        assert result["email"] == "john.doe@company.com"
        # Supervisor email should NOT be exposed
        assert "supervisor" not in result
        assert "supervisor_email" not in result

    @pytest.mark.asyncio
    async def test_get_init_data_employee_not_found(self, leave_service, mock_db_session):
        """Test raises EmployeeNotFoundError when employee not in cache."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(EmployeeNotFoundError) as exc_info:
            await leave_service.get_init_data("unknown@company.com", mock_db_session)

        assert "unknown@company.com" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_init_data_empty_department(self, leave_service, mock_employee, mock_db_session):
        """Test handles employee with no department."""
        mock_employee.department_name = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_employee
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = await leave_service.get_init_data("john.doe@company.com", mock_db_session)

        assert result["department"] == ""


class TestLeaveServiceSubmitRequest:
    """Tests for submit_leave_request method."""

    @pytest.mark.asyncio
    async def test_submit_request_success(
        self, leave_service, mock_employee, mock_department, mock_db_session
    ):
        """Test successful leave request submission."""
        # Setup employee lookup
        mock_emp_result = MagicMock()
        mock_emp_result.scalar_one_or_none.return_value = mock_employee

        # Setup department lookup
        mock_dept_result = MagicMock()
        mock_dept_result.scalar_one_or_none.return_value = mock_department

        # Configure execute to return different results for different queries
        mock_db_session.execute = AsyncMock(
            side_effect=[mock_emp_result, mock_dept_result])

        result = await leave_service.submit_leave_request(
            email="john.doe@company.com",
            leave_date="2024-03-15",
            reason="Personal matters",
            db=mock_db_session,
            leave_type="personal",
        )

        assert result["success"] is True
        assert result["employee"] == "John Doe"
        assert result["date"] == "2024-03-15"
        assert result["supervisor"] == "manager@company.com"
        assert result["dept_manager"] == "dept_head@company.com"

    @pytest.mark.asyncio
    async def test_submit_request_employee_not_found(self, leave_service, mock_db_session):
        """Test raises EmployeeNotFoundError when employee not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(EmployeeNotFoundError):
            await leave_service.submit_leave_request(
                email="unknown@company.com",
                leave_date="2024-03-15",
                reason="Test",
                db=mock_db_session,
            )

    @pytest.mark.asyncio
    async def test_submit_request_no_department_manager(
        self, leave_service, mock_employee, mock_db_session
    ):
        """Test handles missing department manager gracefully."""
        mock_emp_result = MagicMock()
        mock_emp_result.scalar_one_or_none.return_value = mock_employee

        mock_dept_result = MagicMock()
        mock_dept_result.scalar_one_or_none.return_value = None

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_emp_result, mock_dept_result])

        result = await leave_service.submit_leave_request(
            email="john.doe@company.com",
            leave_date="2024-03-15",
            reason="Test",
            db=mock_db_session,
        )

        assert result["success"] is True
        assert result["dept_manager"] is None

    @pytest.mark.asyncio
    async def test_submit_request_with_time_range(
        self, leave_service, mock_employee, mock_department, mock_db_session
    ):
        """Test submission with start and end times."""
        mock_emp_result = MagicMock()
        mock_emp_result.scalar_one_or_none.return_value = mock_employee

        mock_dept_result = MagicMock()
        mock_dept_result.scalar_one_or_none.return_value = mock_department

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_emp_result, mock_dept_result])

        result = await leave_service.submit_leave_request(
            email="john.doe@company.com",
            leave_date="2024-03-15",
            reason="Morning appointment",
            db=mock_db_session,
            leave_type="personal",
            start_time="09:00",
            end_time="12:00",
        )

        assert result["success"] is True


class TestGetLeaveServiceSingleton:
    """Tests for get_leave_service singleton."""

    def test_singleton_returns_same_instance(self):
        """Test get_leave_service returns same instance."""
        import modules.administrative.services.leave as leave_module

        # Reset singleton
        leave_module._leave_service = None

        with patch.object(leave_module, 'get_admin_settings'):
            service1 = get_leave_service()
            service2 = get_leave_service()

        assert service1 is service2

        # Cleanup
        leave_module._leave_service = None


class TestLeaveExceptions:
    """Tests for custom exceptions."""

    def test_leave_error_is_base_exception(self):
        """Test LeaveError is the base exception."""
        assert issubclass(EmployeeNotFoundError, LeaveError)
        assert issubclass(DepartmentNotFoundError, LeaveError)
        assert issubclass(SubmissionError, LeaveError)

    def test_exception_messages(self):
        """Test exception messages are preserved."""
        msg = "Employee not found"
        exc = EmployeeNotFoundError(msg)
        assert str(exc) == msg

        msg = "Submission failed"
        exc = SubmissionError(msg)
        assert str(exc) == msg
