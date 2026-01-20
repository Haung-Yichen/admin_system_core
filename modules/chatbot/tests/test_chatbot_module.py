"""
Unit tests for Chatbot Module.

Tests core functionality without requiring external services.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestChatbotModuleImports:
    """Test that all module components can be imported."""
    
    def test_import_chatbot_module(self):
        """Test importing the main ChatbotModule class."""
        from modules.chatbot import ChatbotModule
        assert ChatbotModule is not None
    
    def test_import_config(self):
        """Test importing config module."""
        from modules.chatbot.core.config import ChatbotSettings
        assert ChatbotSettings is not None
    
    def test_import_security(self):
        """Test importing security module."""
        from core.services import (
            TokenExpiredError,
            TokenInvalidError,
        )
        from core.schemas.auth import MagicLinkRequest
        assert TokenExpiredError is not None
    
    def test_import_models(self):
        """Test importing models."""
        from modules.chatbot.models import User, SOPDocument, UsedToken
        assert User is not None
        assert SOPDocument is not None
        assert UsedToken is not None
    
    def test_import_schemas(self):
        """Test importing schemas."""
        from modules.chatbot.schemas import (
            MagicLinkRequest,
            MagicLinkResponse,
            SOPDocumentCreate,
            SearchQuery,
            UserResponse,
        )
        assert MagicLinkRequest is not None
        assert SearchQuery is not None
    
    def test_import_services(self):
        """Test importing services."""
        from core.services import (
            AuthService,
            RagicService,
        )
        from modules.chatbot.services import (
            VectorService,
            JsonImportService,
            LineService,
        )
        assert AuthService is not None
        assert VectorService is not None
    
    def test_import_routers(self):
        """Test importing routers."""
        from modules.chatbot.routers import bot_router, sop_router
        # auth_router is now in core
        from core.api import auth_router
        assert auth_router is not None
        assert bot_router is not None
        assert sop_router is not None


class TestChatbotModuleInterface:
    """Test ChatbotModule implements IAppModule correctly."""
    
    def test_module_name(self):
        """Test get_module_name returns expected value."""
        from modules.chatbot import ChatbotModule
        module = ChatbotModule()
        assert module.get_module_name() == "chatbot"
    
    def test_on_entry_initializes_router(self):
        """Test on_entry creates the API router."""
        from modules.chatbot import ChatbotModule
        module = ChatbotModule()
        
        mock_context = MagicMock()
        mock_context.log_event = MagicMock()
        
        module.on_entry(mock_context)
        
        router = module.get_api_router()
        assert router is not None
        mock_context.log_event.assert_called()
    
    def test_get_menu_config(self):
        """Test menu config is returned."""
        from modules.chatbot import ChatbotModule
        module = ChatbotModule()
        config = module.get_menu_config()
        
        assert config is not None
        assert "icon" in config
        assert "title" in config


class TestSchemaValidation:
    """Test Pydantic schema validation."""
    
    def test_magic_link_request_normalizes_email(self):
        """Test email is normalized to lowercase."""
        from core.schemas.auth import MagicLinkRequest
        
        request = MagicLinkRequest(
            email="Test.User@Example.COM",
            line_user_id="U1234567890"
        )
        
        assert request.email == "test.user@example.com"
    
    def test_search_query_defaults(self):
        """Test SearchQuery has correct defaults."""
        from modules.chatbot.schemas import SearchQuery
        
        query = SearchQuery(query="test query")
        
        assert query.top_k == 3
        assert query.similarity_threshold == 0.3
        assert query.category is None
    
    def test_sop_document_response_from_attributes(self):
        """Test SOPDocumentResponse can be created from ORM object."""
        from modules.chatbot.schemas import SOPDocumentResponse
        from datetime import datetime
        
        mock_doc = MagicMock()
        mock_doc.id = "test-id"
        mock_doc.title = "Test SOP"
        mock_doc.content = "Test content"
        mock_doc.category = "Test"
        mock_doc.tags = ["tag1"]
        mock_doc.metadata_ = {}
        mock_doc.is_published = True
        mock_doc.created_at = datetime.now()
        mock_doc.updated_at = datetime.now()
        
        response = SOPDocumentResponse.model_validate(mock_doc)
        assert response.id == "test-id"
        assert response.title == "Test SOP"


class TestLineServiceWrapper:
    """Test LineService uses module config."""
    
    @patch('modules.chatbot.services.line_service.get_chatbot_settings')
    @patch('modules.chatbot.services.line_service.LineClient')
    def test_line_service_uses_module_config(self, mock_client_class, mock_settings):
        """Test LineService initializes with module-specific credentials."""
        mock_settings_instance = MagicMock()
        mock_settings_instance.line_channel_secret.get_secret_value.return_value = "test_secret"
        mock_settings_instance.line_channel_access_token.get_secret_value.return_value = "test_token"
        mock_settings.return_value = mock_settings_instance
        
        from modules.chatbot.services.line_service import LineService
        
        service = LineService()
        
        mock_client_class.assert_called_once_with(
            channel_secret="test_secret",
            access_token="test_token",
        )


class TestRagicServiceFuzzyMatch:
    """Test Ragic service fuzzy matching."""
    
    def test_fuzzy_match_exact(self):
        """Test exact string match."""
        # Patching core.services.ragic.ConfigLoader instead of settings
        # Because the new RagicService uses ConfigLoader directly
        pass
        
    def test_fuzzy_match_implementation(self):
        """Test exact string match."""
        from core.services.ragic import RagicService
        
        # We can test the static method directly or mock ConfigLoader
        # Here we just assume default config is fine for unit test if we mock nothing
        # But wait, RagicService __init__ loads config. 
        
        with patch('core.services.ragic.ConfigLoader') as MockConfigLoader:
            mock_loader = MockConfigLoader.return_value
            mock_loader.get.return_value = {} # Default config
            
            service = RagicService()
            
            # Test fuzzy match
            assert service._fuzzy_match("Email", "email", 0.8) is True
            assert service._fuzzy_match("E-mail", "email", 0.8) is True
            assert service._fuzzy_match("完全不同", "email", 0.8) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
