"""
Conftest for Administrative Module Tests.

Provides shared fixtures for unit testing the administrative module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import SecretStr


@pytest.fixture
def mock_db_session():
    """Create mock async database session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_admin_settings():
    """Create mock AdminSettings for testing."""
    settings = MagicMock()
    settings.ragic_api_key = SecretStr("test_api_key")
    settings.ragic_url_employee = "https://ragic.example.com/employee"
    settings.ragic_url_dept = "https://ragic.example.com/department"
    settings.field_employee_email = "1001132"
    settings.field_employee_name = "1001129"
    settings.field_employee_department = "1001194"
    settings.field_employee_supervisor_email = "1001182"
    settings.field_department_name = "1002508"
    settings.field_department_manager_email = "1002509"
    settings.sync_timeout_seconds = 30
    settings.sync_batch_size = 100
    settings.line_channel_secret = SecretStr("test_channel_secret")
    settings.line_channel_access_token = SecretStr("test_access_token")
    settings.line_liff_id_leave = ""
    return settings


@pytest.fixture
def sample_employee_data():
    """Sample employee data for testing."""
    return {
        "email": "test@example.com",
        "name": "Test User",
        "department_name": "Engineering",
        "supervisor_email": "manager@example.com",
        "ragic_id": 123,
    }


@pytest.fixture
def sample_department_data():
    """Sample department data for testing."""
    return {
        "name": "Engineering",
        "manager_email": "eng_manager@example.com",
        "ragic_id": 1,
    }


@pytest.fixture
def sample_ragic_employee_record():
    """Sample Ragic employee record (with field IDs)."""
    return {
        "_ragicId": 123,
        "1001132": "test@example.com",  # email
        "1001129": "Test User",  # name
        "1001194": "Engineering",  # department
        "1001182": "manager@example.com",  # supervisor
    }


@pytest.fixture
def sample_ragic_department_record():
    """Sample Ragic department record (with field IDs)."""
    return {
        "_ragicId": 1,
        "1002508": "Engineering",  # name
        "1002509": "eng_manager@example.com",  # manager
    }


@pytest.fixture
def mock_app_context():
    """Create mock AppContext for testing."""
    context = MagicMock()
    context.log_event = MagicMock()
    context.get_config = MagicMock(return_value={})
    return context


@pytest.fixture
def mock_leave_service():
    """Create mock LeaveService."""
    service = MagicMock()
    service.get_init_data = AsyncMock()
    service.submit_leave_request = AsyncMock()
    return service


@pytest.fixture
def mock_auth_service():
    """Create mock AuthService."""
    service = MagicMock()
    service.check_binding_status = AsyncMock()
    service.is_user_authenticated = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_line_service():
    """Create mock LINE service."""
    service = MagicMock()
    service.reply = AsyncMock()
    service.push = AsyncMock()
    return service
