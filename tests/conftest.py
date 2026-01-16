"""
Pytest Configuration and Shared Fixtures.

Provides common test fixtures for framework unit tests.
"""

import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


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
    
    loader = ConfigLoader()
    loader.load()
    return loader


@pytest.fixture
def app_context(mock_env_vars):
    """Create an AppContext instance with mock environment."""
    from core.app_context import AppContext
    
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
