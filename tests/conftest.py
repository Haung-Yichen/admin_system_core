"""
Pytest Configuration and Shared Fixtures.

Provides common test fixtures for framework unit tests.
"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any, Callable


# =============================================================================
# Environment Fixtures
# =============================================================================


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    env_vars = {
        "SERVER_HOST": "127.0.0.1",
        "SERVER_PORT": "8000",
        "BASE_URL": "https://test.example.com",
        "APP_DEBUG": "true",
        "APP_LOG_LEVEL": "DEBUG",
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "JWT_SECRET_KEY": "test-secret-key-12345",
        "JWT_ALGORITHM": "HS256",
        "MAGIC_LINK_EXPIRE_MINUTES": "30",
        "SMTP_HOST": "smtp.test.com",
        "SMTP_PORT": "587",
        "SMTP_USERNAME": "test@test.com",
        "SMTP_PASSWORD": "testpass",
        "SMTP_FROM_EMAIL": "noreply@test.com",
        "SMTP_FROM_NAME": "Test System",
        "EMBEDDING_MODEL_NAME": "test-model",
        "EMBEDDING_DIMENSION": "384",
        "SEARCH_TOP_K": "5",
        "SEARCH_SIMILARITY_THRESHOLD": "0.5",
        "LINE_CHANNEL_SECRET": "test-line-secret",
        "LINE_CHANNEL_ACCESS_TOKEN": "test-line-token",
        "RAGIC_API_KEY": "test-ragic-key",
        "RAGIC_BASE_URL": "https://ap13.ragic.com",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars


@pytest.fixture
def config_loader(mock_env_vars):
    """Create a ConfigLoader instance with mock environment."""
    from core.app_context import ConfigLoader
    from core.providers import ProviderRegistry
    
    # Reset providers to ensure fresh config
    ProviderRegistry.reset()
    
    loader = ConfigLoader()
    loader.load()
    return loader


@pytest.fixture
def app_context(mock_env_vars):
    """Create an AppContext instance with mock environment."""
    from core.app_context import AppContext
    from core.providers import ProviderRegistry
    
    # Reset singletons for clean test state
    AppContext.reset()
    ProviderRegistry.reset()
    
    return AppContext()


@pytest.fixture
def mock_httpx_response():
    """Factory fixture for creating mock httpx responses."""
    def _create_response(status_code=200, json_data=None):
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data or {}
        mock_response.text = str(json_data)
        return mock_response
    
    return _create_response


@pytest.fixture
def mock_async_client():
    """Create a mock async httpx client."""
    mock_client = MagicMock()
    mock_client.get = AsyncMock()
    mock_client.post = AsyncMock()
    mock_client.delete = AsyncMock()
    mock_client.aclose = AsyncMock()
    return mock_client


class MockModule:
    """Mock module implementation for testing."""
    
    def __init__(self, name: str = "mock_module"):
        self._name = name
        self._initialized = False
        self._shutdown = False
    
    def get_module_name(self) -> str:
        return self._name
    
    def on_entry(self, context) -> None:
        self._initialized = True
    
    def handle_event(self, context, event: dict) -> dict | None:
        return {"handled": True, "module": self._name}
    
    def get_menu_config(self) -> dict:
        return {
            "label": self._name.title(),
            "icon": "test_icon",
            "actions": []
        }
    
    def on_shutdown(self) -> None:
        self._shutdown = True


@pytest.fixture
def mock_module():
    """Create a mock module instance."""
    return MockModule()


@pytest.fixture
def mock_module_factory():
    """Factory for creating mock modules with custom names."""
    def _create(name: str):
        return MockModule(name)
    return _create


# =============================================================================
# HTTP Client Fixtures
# =============================================================================

@pytest.fixture
def mock_httpx_response_factory() -> Callable[..., MagicMock]:
    """
    Factory fixture for creating mock httpx responses.
    
    Returns a callable that creates mock responses with customizable properties.
    """
    def _create_response(
        status_code: int = 200,
        json_data: dict | list | None = None,
        text: str | None = None,
        content: bytes | None = None,
        raise_for_status_error: Exception | None = None,
    ) -> MagicMock:
        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_response.json.return_value = json_data or {}
        mock_response.text = text or str(json_data)
        mock_response.content = content or (text.encode() if text else b"")
        
        if raise_for_status_error:
            mock_response.raise_for_status.side_effect = raise_for_status_error
        else:
            mock_response.raise_for_status = MagicMock()
        
        return mock_response
    
    return _create_response


@pytest.fixture
def mock_httpx_client_factory() -> Callable[..., MagicMock]:
    """
    Factory for creating mock async httpx clients with pre-configured responses.
    """
    def _create_client(
        get_response: MagicMock | None = None,
        post_response: MagicMock | None = None,
        put_response: MagicMock | None = None,
        delete_response: MagicMock | None = None,
    ) -> MagicMock:
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=get_response)
        mock_client.post = AsyncMock(return_value=post_response)
        mock_client.put = AsyncMock(return_value=put_response)
        mock_client.delete = AsyncMock(return_value=delete_response)
        mock_client.aclose = AsyncMock()
        return mock_client
    
    return _create_client


# =============================================================================
# SMTP/Email Fixtures
# =============================================================================

@pytest.fixture
def mock_smtp_server():
    """
    Mock synchronous SMTP server for email tests.
    
    Usage:
        def test_send_email(mock_smtp_server):
            # Send email code...
            mock_smtp_server.sendmail.assert_called_once()
    """
    with patch('smtplib.SMTP') as mock_smtp:
        server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = server
        yield server


@pytest.fixture
def mock_aiosmtplib():
    """
    Mock async SMTP for aiosmtplib.send().
    
    Usage:
        @pytest.mark.asyncio
        async def test_async_send_email(mock_aiosmtplib):
            # Async send code...
            mock_aiosmtplib.assert_called_once()
    """
    with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
        yield mock_send


# =============================================================================
# Ragic API Fixtures
# =============================================================================

@pytest.fixture
def mock_ragic_api_response() -> Callable[..., MagicMock]:
    """
    Factory for creating mock Ragic API responses.
    
    Ragic API returns records as dict with ragic_id as keys:
    {"1": {...record1...}, "2": {...record2...}}
    """
    def _create(
        records: list[dict] | None = None,
        status_code: int = 200,
        error_message: str | None = None,
    ) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        
        if error_message:
            mock_resp.json.return_value = {"error": error_message}
            mock_resp.raise_for_status.side_effect = Exception(error_message)
        else:
            # Convert list to Ragic's dict format
            records = records or []
            data = {str(r.get("_ragicId", i)): r for i, r in enumerate(records)}
            mock_resp.json.return_value = data
            mock_resp.raise_for_status = MagicMock()
        
        return mock_resp
    
    return _create


@pytest.fixture
def sample_ragic_employee_records() -> list[dict]:
    """Sample employee records from Ragic (unified Account table)."""
    return [
        {
            "_ragicId": 1,
            "1005977": "alice@example.com",  # EMAILS
            "1005975": "Alice Chen",  # NAME
            "1005974": True,  # STATUS
            "1005983": "E001",  # EMPLOYEE_ID
        },
        {
            "_ragicId": 2,
            "1005977": "bob@example.com,bob.wang@company.com",  # Multi-value EMAILS
            "1005975": "Bob Wang",  # NAME
            "1005974": True,  # STATUS
            "1005983": "E002",  # EMPLOYEE_ID
        },
    ]


# =============================================================================
# LINE API Fixtures
# =============================================================================

@pytest.fixture
def mock_line_api_response() -> Callable[..., MagicMock]:
    """Factory for creating mock LINE API responses."""
    def _create(
        json_data: dict | list | None = None,
        status_code: int = 200,
    ) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.status_code = status_code
        mock_resp.json.return_value = json_data or {}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp
    
    return _create


@pytest.fixture
def mock_pil_image():
    """Mock PIL Image for rich menu image tests."""
    with patch('PIL.Image.open') as mock_open:
        mock_img = MagicMock()
        mock_img.size = (2500, 1686)
        mock_img.mode = 'RGB'
        mock_img.resize.return_value = mock_img
        mock_img.convert.return_value = mock_img
        mock_open.return_value = mock_img
        yield mock_img


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest.fixture
def mock_async_db_session():
    """Create mock async database session with common operations."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    
    # For context manager usage
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    
    return session
