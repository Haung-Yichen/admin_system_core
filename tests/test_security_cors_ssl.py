"""
Tests for CORS and Database SSL security fixes.

These tests verify:
1. CORS no longer falls back to ["*"] in production
2. Database SSL mode configuration works correctly
"""

import os
import ssl
from unittest.mock import MagicMock, patch

import pytest


# =============================================================================
# CORS Security Tests
# =============================================================================

class TestCORSSecurityFix:
    """
    Tests for CORS middleware configuration security.
    
    Verifies:
    - CORS does NOT fallback to ["*"] when BASE_URL is not configured
    - Debug mode allows localhost origins as fallback
    - Production mode blocks all cross-origin requests if BASE_URL missing
    """

    @pytest.fixture
    def mock_context(self):
        """Create a mock AppContext."""
        context = MagicMock()
        context.config = MagicMock()
        return context

    def test_cors_includes_base_url_when_configured(self, mock_context):
        """Test: BASE_URL is included in allowed origins."""
        from core.server import create_base_app
        
        mock_context.config.get = MagicMock(side_effect=lambda key, default=None: {
            "server.base_url": "https://production.example.com",
            "app.debug": False,
        }.get(key, default))
        
        app = create_base_app(mock_context)
        
        # Find CORS middleware
        cors_middleware = None
        for middleware in app.user_middleware:
            if hasattr(middleware, 'kwargs') and 'allow_origins' in middleware.kwargs:
                cors_middleware = middleware
                break
        
        # Check allowed origins in middleware configuration
        assert cors_middleware is not None
        allowed_origins = cors_middleware.kwargs.get('allow_origins', [])
        assert "https://production.example.com" in allowed_origins
        assert "*" not in allowed_origins

    def test_cors_does_not_fallback_to_wildcard_in_production(self, mock_context, caplog):
        """Test: CORS does NOT use ["*"] when BASE_URL is missing in production."""
        from core.server import create_base_app
        import logging
        
        # Simulate production without BASE_URL
        mock_context.config.get = MagicMock(side_effect=lambda key, default=None: {
            "server.base_url": "",
            "app.debug": False,
        }.get(key, default))
        
        with caplog.at_level(logging.ERROR):
            app = create_base_app(mock_context)
        
        # Find CORS middleware
        cors_middleware = None
        for middleware in app.user_middleware:
            if hasattr(middleware, 'kwargs') and 'allow_origins' in middleware.kwargs:
                cors_middleware = middleware
                break
        
        assert cors_middleware is not None
        allowed_origins = cors_middleware.kwargs.get('allow_origins', [])
        
        # Should NOT contain wildcard
        assert "*" not in allowed_origins
        # Should be empty list (blocks all cross-origin requests)
        assert allowed_origins == []
        # Should log error
        assert any("CRITICAL" in record.message for record in caplog.records)

    def test_cors_allows_localhost_in_debug_mode(self, mock_context):
        """Test: Debug mode allows localhost origins."""
        from core.server import create_base_app
        
        mock_context.config.get = MagicMock(side_effect=lambda key, default=None: {
            "server.base_url": "https://dev.example.com",
            "app.debug": True,
        }.get(key, default))
        
        app = create_base_app(mock_context)
        
        # Find CORS middleware
        cors_middleware = None
        for middleware in app.user_middleware:
            if hasattr(middleware, 'kwargs') and 'allow_origins' in middleware.kwargs:
                cors_middleware = middleware
                break
        
        assert cors_middleware is not None
        allowed_origins = cors_middleware.kwargs.get('allow_origins', [])
        
        # Should include localhost in debug mode
        assert "http://localhost:8000" in allowed_origins
        assert "http://127.0.0.1:8000" in allowed_origins
        # Should include base_url
        assert "https://dev.example.com" in allowed_origins

    def test_cors_debug_mode_fallback_without_base_url(self, mock_context):
        """Test: Debug mode with no BASE_URL still has localhost origins."""
        from core.server import create_base_app
        
        mock_context.config.get = MagicMock(side_effect=lambda key, default=None: {
            "server.base_url": "",
            "app.debug": True,
        }.get(key, default))
        
        app = create_base_app(mock_context)
        
        # Find CORS middleware
        cors_middleware = None
        for middleware in app.user_middleware:
            if hasattr(middleware, 'kwargs') and 'allow_origins' in middleware.kwargs:
                cors_middleware = middleware
                break
        
        assert cors_middleware is not None
        allowed_origins = cors_middleware.kwargs.get('allow_origins', [])
        
        # Debug mode always adds localhost origins, even without BASE_URL
        assert "http://localhost:8000" in allowed_origins
        assert "http://127.0.0.1:8000" in allowed_origins
        assert "*" not in allowed_origins


# =============================================================================
# Database SSL Security Tests
# =============================================================================

class TestDatabaseSSLConfiguration:
    """
    Tests for database SSL configuration.
    
    Verifies:
    - SSL mode environment variable is respected
    - verify-full mode requires certificate path
    - Fallback behavior for invalid configurations
    """

    @pytest.fixture(autouse=True)
    def reset_env(self, monkeypatch):
        """Reset SSL-related environment variables before each test."""
        monkeypatch.delenv("DATABASE_SSL_MODE", raising=False)
        monkeypatch.delenv("DATABASE_SSL_CERT_PATH", raising=False)

    def test_ssl_mode_require_returns_context_without_verification(self, monkeypatch):
        """Test: 'require' mode returns SSL context without certificate verification."""
        from core.database.engine import _get_ssl_context
        
        monkeypatch.setenv("DATABASE_SSL_MODE", "require")
        
        ctx = _get_ssl_context()
        
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_ssl_mode_disable_returns_none(self, monkeypatch, caplog):
        """Test: 'disable' mode returns None and logs warning."""
        from core.database.engine import _get_ssl_context
        import logging
        
        monkeypatch.setenv("DATABASE_SSL_MODE", "disable")
        
        with caplog.at_level(logging.WARNING):
            ctx = _get_ssl_context()
        
        assert ctx is None
        assert any("SSL is disabled" in record.message for record in caplog.records)

    def test_ssl_mode_verify_full_without_cert_falls_back_to_require(
        self, monkeypatch, caplog
    ):
        """Test: verify-full without cert path falls back to require mode."""
        from core.database.engine import _get_ssl_context
        import logging
        
        monkeypatch.setenv("DATABASE_SSL_MODE", "verify-full")
        # No DATABASE_SSL_CERT_PATH set
        
        with caplog.at_level(logging.ERROR):
            ctx = _get_ssl_context()
        
        # Should fall back to require mode (SSL context without verification)
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE
        # Should log error
        assert any("requires DATABASE_SSL_CERT_PATH" in record.message for record in caplog.records)

    def test_ssl_mode_verify_full_with_valid_cert(self, monkeypatch, tmp_path, caplog):
        """Test: verify-full with valid cert path attempts to create verified SSL context."""
        from core.database.engine import _get_ssl_context
        import logging
        
        # Create a temporary cert file (content doesn't matter for this test)
        cert_file = tmp_path / "test-ca.crt"
        cert_file.write_text("dummy cert content")
        
        monkeypatch.setenv("DATABASE_SSL_MODE", "verify-full")
        monkeypatch.setenv("DATABASE_SSL_CERT_PATH", str(cert_file))
        
        # Mock ssl.create_default_context to test the logic path
        mock_ctx = MagicMock(spec=ssl.SSLContext)
        mock_ctx.check_hostname = False  # Initial value
        mock_ctx.verify_mode = ssl.CERT_NONE  # Initial value
        
        with patch("core.database.engine.ssl.create_default_context", return_value=mock_ctx) as mock_create:
            with caplog.at_level(logging.INFO):
                ctx = _get_ssl_context()
        
        # Should have called create_default_context with cafile
        mock_create.assert_called_once_with(cafile=str(cert_file))
        
        # Should have set check_hostname and verify_mode
        assert mock_ctx.check_hostname is True
        assert mock_ctx.verify_mode == ssl.CERT_REQUIRED
        
        # Should log verify-full mode
        assert any("verify-full" in record.message for record in caplog.records)

    def test_ssl_mode_verify_full_with_invalid_cert_path(self, monkeypatch, caplog):
        """Test: verify-full with invalid cert path falls back to require mode."""
        from core.database.engine import _get_ssl_context
        import logging
        
        monkeypatch.setenv("DATABASE_SSL_MODE", "verify-full")
        monkeypatch.setenv("DATABASE_SSL_CERT_PATH", "/nonexistent/path/to/cert.crt")
        
        with caplog.at_level(logging.ERROR):
            ctx = _get_ssl_context()
        
        # Should fall back to require mode
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False
        assert any("Failed to load SSL certificate" in record.message for record in caplog.records)

    def test_ssl_mode_prefer_returns_context_without_verification(self, monkeypatch):
        """Test: 'prefer' mode returns SSL context similar to 'require'."""
        from core.database.engine import _get_ssl_context
        
        monkeypatch.setenv("DATABASE_SSL_MODE", "prefer")
        
        ctx = _get_ssl_context()
        
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_ssl_mode_unknown_defaults_to_require(self, monkeypatch, caplog):
        """Test: Unknown SSL mode defaults to 'require' behavior."""
        from core.database.engine import _get_ssl_context
        import logging
        
        monkeypatch.setenv("DATABASE_SSL_MODE", "invalid-mode")
        
        with caplog.at_level(logging.WARNING):
            ctx = _get_ssl_context()
        
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE
        assert any("Unknown DATABASE_SSL_MODE" in record.message for record in caplog.records)

    def test_ssl_mode_default_is_require(self, monkeypatch):
        """Test: Default SSL mode (no env var) is 'require'."""
        from core.database.engine import _get_ssl_context
        
        # Ensure no SSL mode is set
        monkeypatch.delenv("DATABASE_SSL_MODE", raising=False)
        
        ctx = _get_ssl_context()
        
        # Should use require mode (SSL context without verification)
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE


# =============================================================================
# Integration Tests - Ensure existing functionality still works
# =============================================================================

class TestExistingFunctionalityPreserved:
    """
    Integration tests to ensure security fixes don't break existing functionality.
    """

    def test_server_creates_app_successfully_with_base_url(self, mock_env_vars):
        """Test: create_base_app works correctly with proper configuration."""
        from core.server import create_base_app
        from core.app_context import AppContext, ConfigLoader
        from core.providers import ProviderRegistry
        
        # Reset singletons
        AppContext.reset()
        ProviderRegistry.reset()
        
        context = AppContext()
        app = create_base_app(context)
        
        # App should be created successfully
        assert app is not None
        assert app.title == "Admin System Core API"

    def test_database_engine_can_be_created(self, mock_env_vars, monkeypatch):
        """Test: Database engine creation still works with SSL configuration."""
        from core.database.engine import get_engine
        import core.database.engine as engine_module
        
        # Reset engine singleton
        engine_module._engine = None
        
        # Set SSL mode to disable for test (no actual DB connection needed)
        monkeypatch.setenv("DATABASE_SSL_MODE", "disable")
        
        # This should not raise
        engine = get_engine()
        
        assert engine is not None
        
        # Cleanup
        engine_module._engine = None

    def test_security_headers_still_added(self, mock_env_vars):
        """Test: Security headers middleware is still present."""
        from core.server import create_base_app
        from core.app_context import AppContext, ConfigLoader
        from core.providers import ProviderRegistry
        from fastapi.testclient import TestClient
        
        # Reset singletons
        AppContext.reset()
        ProviderRegistry.reset()
        
        context = AppContext()
        app = create_base_app(context)
        
        client = TestClient(app)
        response = client.get("/health")
        
        # Check security headers are present
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_line_webhook_route_still_exists(self, mock_env_vars):
        """Test: LINE webhook route is still registered."""
        from core.server import create_base_app
        from core.app_context import AppContext
        from core.providers import ProviderRegistry
        
        # Reset singletons
        AppContext.reset()
        ProviderRegistry.reset()
        
        context = AppContext()
        app = create_base_app(context)
        
        # Check webhook route exists
        routes = [route.path for route in app.routes]
        assert any("webhook" in route for route in routes)
