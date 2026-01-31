"""
Unit Tests for core.app_context module.

Tests ConfigLoader and AppContext classes.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestConfigLoader:
    """Tests for ConfigLoader class."""
    
    def test_load_creates_config_dict(self, mock_env_vars):
        """Test that load() populates the config dictionary."""
        from core.app_context import ConfigLoader
        
        loader = ConfigLoader()
        loader.load()
        
        assert loader._config is not None
        assert "server" in loader._config
        assert "app" in loader._config
        assert "line" in loader._config
        assert "ragic" in loader._config
    
    def test_get_returns_nested_value(self, config_loader):
        """Test get() with dot notation returns correct nested value."""
        assert config_loader.get("server.host") == "127.0.0.1"
        assert config_loader.get("server.port") == 8000
        assert config_loader.get("app.debug") is True
    
    def test_get_returns_default_for_missing_key(self, config_loader):
        """Test get() returns default when key doesn't exist."""
        assert config_loader.get("nonexistent.key") is None
        assert config_loader.get("nonexistent.key", "default") == "default"
        assert config_loader.get("server.nonexistent", 123) == 123
    
    def test_get_security_config(self, config_loader):
        """Test security configuration loading."""
        assert config_loader.get("security.jwt_secret_key") == "test-secret-key-12345"
        assert config_loader.get("security.jwt_algorithm") == "HS256"
        assert config_loader.get("security.magic_link_expire_minutes") == 30
    
    def test_get_email_config(self, config_loader):
        """Test email configuration loading."""
        assert config_loader.get("email.host") == "smtp.test.com"
        assert config_loader.get("email.port") == 587
        assert config_loader.get("email.username") == "test@test.com"
    
    def test_get_vector_config(self, config_loader):
        """Test vector search configuration loading."""
        assert config_loader.get("vector.model_name") == "test-model"
        assert config_loader.get("vector.dimension") == 384
        assert config_loader.get("vector.top_k") == 5
    
    def test_is_line_configured_true(self, config_loader):
        """Test is_line_configured() returns True when credentials exist."""
        assert config_loader.is_line_configured() is True
    
    def test_is_line_configured_false(self, mock_env_vars, monkeypatch):
        """Test is_line_configured() returns False when credentials missing."""
        from core.app_context import ConfigLoader
        
        monkeypatch.setenv("LINE_CHANNEL_SECRET", "")
        monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "")
        
        loader = ConfigLoader()
        loader.load()
        
        assert loader.is_line_configured() is False
    
    def test_is_ragic_configured_true(self, config_loader):
        """Test is_ragic_configured() returns True when credentials exist."""
        assert config_loader.is_ragic_configured() is True
    
    def test_is_ragic_configured_false(self, mock_env_vars, monkeypatch):
        """Test is_ragic_configured() returns False when credentials missing."""
        from core.app_context import ConfigLoader
        
        monkeypatch.setenv("RAGIC_API_KEY", "")
        
        loader = ConfigLoader()
        loader.load()
        
        assert loader.is_ragic_configured() is False


class TestAppContext:
    """Tests for AppContext class."""
    
    def test_initialization(self, app_context):
        """Test AppContext initializes correctly."""
        # AppContext now uses providers, check the provider references
        assert app_context._config_provider is not None
        assert app_context._log_service is not None
        assert app_context._server_state is not None
    
    def test_config_property(self, app_context):
        """Test config property returns ConfigLoader."""
        from core.app_context import ConfigLoader
        
        assert isinstance(app_context.config, ConfigLoader)
        assert app_context.config.get("server.host") == "127.0.0.1"
    
    def test_log_event_adds_to_log(self, app_context):
        """Test log_event() adds formatted message to event log."""
        app_context.log_event("Test message", "INFO")
        
        log = app_context.get_event_log()
        assert len(log) >= 1
        assert any("Test message" in entry for entry in log)
    
    def test_log_event_respects_max_entries(self, app_context):
        """Test log_event() trims old entries when max reached."""
        # Access log service to set max entries
        app_context._log_service._max_entries = 5
        app_context._log_service._event_log.clear()
        
        for i in range(10):
            app_context.log_event(f"Message {i}")
        
        log = app_context.get_event_log()
        assert len(log) == 5
        assert "Message 9" in log[-1]
    
    def test_get_event_log_returns_copy(self, app_context):
        """Test get_event_log() returns a copy, not the original."""
        app_context.log_event("Test")
        
        log1 = app_context.get_event_log()
        log2 = app_context.get_event_log()
        
        assert log1 == log2
        assert log1 is not log2  # Different objects
    
    def test_set_server_status(self, app_context):
        """Test set_server_status() updates status correctly."""
        app_context.set_server_status(True, 9000)
        
        running, port = app_context.get_server_status()
        assert running is True
        assert port == 9000
    
    def test_get_server_status_defaults(self, app_context):
        """Test get_server_status() returns initial defaults."""
        # Reset server state for clean test
        app_context._server_state.running = False
        app_context._server_state.port = 8000
        
        running, port = app_context.get_server_status()
        
        assert running is False
        assert port == 8000
    
    def test_line_client_lazy_init(self, mock_env_vars):
        """Test line_client property lazily initializes."""
        from core.app_context import AppContext
        
        with patch('services.line_client.LineClient') as MockLineClient:
            mock_instance = MagicMock()
            MockLineClient.return_value = mock_instance
            
            ctx = AppContext()
            
            # First access creates client
            client = ctx.line_client
            MockLineClient.assert_called_once()
            
            # Second access returns same instance
            client2 = ctx.line_client
            assert client2 is client
    
    def test_ragic_service_lazy_init(self, mock_env_vars):
        """Test ragic_service property lazily initializes."""
        from core.app_context import AppContext
        
        with patch('core.ragic.RagicService') as MockRagicService:
            mock_instance = MagicMock()
            MockRagicService.return_value = mock_instance
            
            ctx = AppContext()
            
            # First access creates service
            service = ctx.ragic_service
            MockRagicService.assert_called_once()
            
            # Second access returns same instance
            service2 = ctx.ragic_service
            assert service2 is service
