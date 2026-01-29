"""
Unit Tests for Administrative Module Configuration.

Tests for AdminSettings and get_admin_settings.
"""

import pytest
from unittest.mock import patch, MagicMock
import os

from modules.administrative.core.config import (
    AdminSettings,
    RagicAccountFieldMapping,
    get_admin_settings,
)


class TestRagicAccountFieldMapping:
    """Tests for RagicAccountFieldMapping constants."""

    def test_primary_identification_fields(self):
        """Test primary identification field mappings are defined."""
        assert RagicAccountFieldMapping.RAGIC_ID == "1005971"
        assert RagicAccountFieldMapping.ACCOUNT_ID == "1005972"
        assert RagicAccountFieldMapping.ID_CARD_NUMBER == "1005973"
        assert RagicAccountFieldMapping.EMPLOYEE_ID == "1005983"

    def test_basic_info_fields(self):
        """Test basic info field mappings are defined."""
        assert RagicAccountFieldMapping.STATUS == "1005974"
        assert RagicAccountFieldMapping.NAME == "1005975"
        assert RagicAccountFieldMapping.GENDER == "1005976"
        assert RagicAccountFieldMapping.BIRTHDAY == "1005985"

    def test_contact_fields(self):
        """Test contact field mappings are defined."""
        assert RagicAccountFieldMapping.EMAILS == "1005977"
        assert RagicAccountFieldMapping.PHONES == "1005986"
        assert RagicAccountFieldMapping.MOBILES == "1005987"

    def test_organization_fields(self):
        """Test organization field mappings are defined."""
        assert RagicAccountFieldMapping.ORG_CODE == "1005978"
        assert RagicAccountFieldMapping.ORG_NAME == "1006049"
        assert RagicAccountFieldMapping.RANK_CODE == "1005979"
        assert RagicAccountFieldMapping.RANK_NAME == "1006050"

    def test_date_fields(self):
        """Test date field mappings are defined."""
        assert RagicAccountFieldMapping.APPROVAL_DATE == "1006016"
        assert RagicAccountFieldMapping.EFFECTIVE_DATE == "1006017"
        assert RagicAccountFieldMapping.RESIGNATION_DATE == "1006019"

    def test_license_fields(self):
        """Test license field mappings are defined."""
        assert RagicAccountFieldMapping.LIFE_LICENSE_NUMBER == "1005998"
        assert RagicAccountFieldMapping.PROPERTY_LICENSE_NUMBER == "1006002"
        assert RagicAccountFieldMapping.AH_LICENSE_NUMBER == "1006021"


class TestAdminSettings:
    """Tests for AdminSettings pydantic model."""

    @pytest.fixture
    def mock_env_vars(self, monkeypatch):
        """Set up required environment variables."""
        env_vars = {
            "ADMIN_RAGIC_API_KEY": "test_api_key",
            "ADMIN_RAGIC_URL_ACCOUNT": "https://ragic.example.com/account",
            "ADMIN_LINE_CHANNEL_SECRET": "test_channel_secret",
            "ADMIN_LINE_CHANNEL_ACCESS_TOKEN": "test_access_token",
        }
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

    def test_load_required_settings(self, mock_env_vars):
        """Test loading required settings from environment."""
        # Clear cache to force reload
        get_admin_settings.cache_clear()

        settings = AdminSettings()

        assert settings.ragic_api_key.get_secret_value() == "test_api_key"
        assert settings.ragic_url_account == "https://ragic.example.com/account"

    def test_secret_values(self, mock_env_vars):
        """Test that secret values are properly protected."""
        get_admin_settings.cache_clear()

        settings = AdminSettings()

        # Should not expose secret in str representation
        assert "test_api_key" not in str(settings)
        assert "test_channel_secret" not in str(settings)

        # But can access via get_secret_value
        assert settings.ragic_api_key.get_secret_value() == "test_api_key"

    def test_default_values(self, mock_env_vars):
        """Test default values are applied."""
        get_admin_settings.cache_clear()

        settings = AdminSettings()

        assert settings.sync_batch_size == 100
        assert settings.sync_timeout_seconds == 60

    def test_override_defaults(self, monkeypatch):
        """Test overriding default values via environment."""
        get_admin_settings.cache_clear()

        monkeypatch.setenv("ADMIN_RAGIC_API_KEY", "test_key")
        monkeypatch.setenv("ADMIN_RAGIC_URL_ACCOUNT", "https://test.com/account")
        monkeypatch.setenv("ADMIN_LINE_CHANNEL_SECRET", "secret")
        monkeypatch.setenv("ADMIN_LINE_CHANNEL_ACCESS_TOKEN", "token")
        monkeypatch.setenv("ADMIN_SYNC_BATCH_SIZE", "200")
        monkeypatch.setenv("ADMIN_SYNC_TIMEOUT_SECONDS", "120")

        settings = AdminSettings()

        assert settings.sync_batch_size == 200
        assert settings.sync_timeout_seconds == 120


class TestGetAdminSettings:
    """Tests for get_admin_settings cached function."""

    def test_returns_settings_instance(self, monkeypatch):
        """Test returns AdminSettings instance."""
        get_admin_settings.cache_clear()

        monkeypatch.setenv("ADMIN_RAGIC_API_KEY", "test_key")
        monkeypatch.setenv("ADMIN_RAGIC_URL_ACCOUNT", "https://test.com/account")
        monkeypatch.setenv("ADMIN_LINE_CHANNEL_SECRET", "secret")
        monkeypatch.setenv("ADMIN_LINE_CHANNEL_ACCESS_TOKEN", "token")

        settings = get_admin_settings()

        assert isinstance(settings, AdminSettings)

    def test_caches_instance(self, monkeypatch):
        """Test function returns cached instance."""
        get_admin_settings.cache_clear()

        monkeypatch.setenv("ADMIN_RAGIC_API_KEY", "test_key")
        monkeypatch.setenv("ADMIN_RAGIC_URL_ACCOUNT", "https://test.com/account")
        monkeypatch.setenv("ADMIN_LINE_CHANNEL_SECRET", "secret")
        monkeypatch.setenv("ADMIN_LINE_CHANNEL_ACCESS_TOKEN", "token")

        settings1 = get_admin_settings()
        settings2 = get_admin_settings()

        assert settings1 is settings2


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_all_required_fields_present(self, monkeypatch):
        """Test settings load successfully with all required fields."""
        get_admin_settings.cache_clear()

        monkeypatch.setenv("ADMIN_RAGIC_API_KEY", "test_key")
        monkeypatch.setenv("ADMIN_RAGIC_URL_ACCOUNT", "https://test.com/account")
        monkeypatch.setenv("ADMIN_LINE_CHANNEL_SECRET", "secret")
        monkeypatch.setenv("ADMIN_LINE_CHANNEL_ACCESS_TOKEN", "token")

        settings = AdminSettings()

        assert settings.ragic_api_key.get_secret_value() == "test_key"
        assert settings.ragic_url_account == "https://test.com/account"
        assert settings.line_channel_secret.get_secret_value() == "secret"
        assert settings.line_channel_access_token.get_secret_value() == "token"
