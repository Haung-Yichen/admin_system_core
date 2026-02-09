"""
Conftest for Administrative Module Tests.

Provides shared fixtures for unit testing the administrative module.
"""

import pytest
from datetime import date
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
    settings.ragic_url_account = "https://ragic.example.com/account"
    settings.sync_timeout_seconds = 30
    settings.sync_batch_size = 100
    settings.line_channel_secret = SecretStr("test_channel_secret")
    settings.line_channel_access_token = SecretStr("test_access_token")
    settings.line_liff_id_leave = ""
    return settings


@pytest.fixture
def sample_account_data():
    """Sample account data for testing."""
    return {
        "ragic_id": 123,
        "account_id": "A001",
        "name": "Test User",
        "status": True,
        "emails": "test@example.com",
        "org_code": "ORG001",
        "org_name": "Engineering",
        "rank_code": "R01",
        "rank_name": "Manager",
        "mentor_id_card": "A123456789",
        "mentor_name": "Jane Manager",
        "sales_dept": "Sales North",
        "sales_dept_manager": "Bob Director",
    }


@pytest.fixture
def sample_ragic_account_record():
    """Sample Ragic account record (with field IDs)."""
    return {
        "_ragicId": 123,
        "1005971": "123",  # ragic_id
        "1005972": "A001",  # account_id
        "1005975": "Test User",  # name
        "1005974": "1",  # status (active)
        "1005977": "test@example.com",  # emails
        "1005978": "ORG001",  # org_code
        "1006049": "Engineering",  # org_name
        "1005979": "R01",  # rank_code
        "1006050": "Manager",  # rank_name
        "1005981": "A123456789",  # mentor_id_card
        "1006043": "Jane Manager",  # mentor_name
        "1006058": "Sales North",  # sales_dept
        "1006059": "Bob Director",  # sales_dept_manager
        "1006016": "2020-01-15",  # approval_date
        "1006017": "2020-02-01",  # effective_date
        "1005982": "0.85",  # assessment_rate
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
