"""
Unit Tests for core.interface module.

Tests IAppModule abstract interface and implementations.
"""

import pytest
from abc import ABC


class TestIAppModuleInterface:
    """Tests for IAppModule abstract interface."""
    
    def test_iappmodule_is_abstract(self):
        """Test IAppModule is an abstract class."""
        from core.interface import IAppModule
        
        assert issubclass(IAppModule, ABC)
    
    def test_cannot_instantiate_directly(self):
        """Test IAppModule cannot be instantiated directly."""
        from core.interface import IAppModule
        
        with pytest.raises(TypeError):
            IAppModule()
    
    def test_abstract_methods_defined(self):
        """Test required abstract methods are defined."""
        from core.interface import IAppModule
        
        abstract_methods = IAppModule.__abstractmethods__
        
        assert "get_module_name" in abstract_methods
        assert "on_entry" in abstract_methods
        # handle_event is no longer abstract, has default implementation
    
    def test_get_menu_config_has_default(self):
        """Test get_menu_config() has default implementation."""
        from core.interface import IAppModule
        
        # get_menu_config should not be abstract (has default impl)
        assert "get_menu_config" not in IAppModule.__abstractmethods__
    
    def test_on_shutdown_has_default(self):
        """Test on_shutdown() has default implementation."""
        from core.interface import IAppModule
        
        # on_shutdown should not be abstract (has default impl)
        assert "on_shutdown" not in IAppModule.__abstractmethods__


class TestConcreteModuleImplementation:
    """Test a concrete implementation of IAppModule."""
    
    def test_mock_module_implements_interface(self, mock_module):
        """Test MockModule implements required interface."""
        from core.interface import IAppModule
        
        # Check it has all required methods
        assert hasattr(mock_module, "get_module_name")
        assert hasattr(mock_module, "on_entry")
        assert hasattr(mock_module, "handle_event")
        assert hasattr(mock_module, "get_menu_config")
        assert hasattr(mock_module, "on_shutdown")
    
    def test_get_module_name_returns_string(self, mock_module):
        """Test get_module_name() returns a string."""
        name = mock_module.get_module_name()
        
        assert isinstance(name, str)
        assert name == "mock_module"
    
    def test_on_entry_accepts_context(self, mock_module, app_context):
        """Test on_entry() accepts AppContext."""
        mock_module.on_entry(app_context)
        
        assert mock_module._initialized is True
    
    def test_handle_event_returns_dict_or_none(self, mock_module, app_context):
        """Test handle_event() returns dict or None."""
        result = mock_module.handle_event(app_context, {"test": "data"})
        
        assert result is None or isinstance(result, dict)
    
    def test_get_menu_config_returns_dict(self, mock_module):
        """Test get_menu_config() returns proper structure."""
        config = mock_module.get_menu_config()
        
        assert isinstance(config, dict)
        assert "label" in config
        assert "icon" in config
        assert "actions" in config
    
    def test_on_shutdown_is_callable(self, mock_module):
        """Test on_shutdown() can be called."""
        mock_module.on_shutdown()
        
        assert mock_module._shutdown is True


class TestCustomModuleImplementation:
    """Test creating custom module implementations."""
    
    def test_can_create_minimal_implementation(self):
        """Test creating a minimal valid IAppModule implementation."""
        from core.interface import IAppModule
        
        class MinimalModule(IAppModule):
            def get_module_name(self):
                return "minimal"
            
            def on_entry(self, context):
                pass
            
            def handle_event(self, context, event):
                return None
        
        module = MinimalModule()
        
        assert module.get_module_name() == "minimal"
        assert module.get_menu_config() == {
            "label": "minimal",
            "icon": None,
            "actions": []
        }
    
    def test_can_override_optional_methods(self):
        """Test overriding get_menu_config and on_shutdown."""
        from core.interface import IAppModule
        
        class CustomModule(IAppModule):
            def __init__(self):
                self.cleaned_up = False
            
            def get_module_name(self):
                return "custom"
            
            def on_entry(self, context):
                pass
            
            def handle_event(self, context, event):
                return {"status": "ok"}
            
            def get_menu_config(self):
                return {
                    "label": "Custom Module",
                    "icon": "custom_icon",
                    "actions": [{"name": "action1"}]
                }
            
            def on_shutdown(self):
                self.cleaned_up = True
        
        module = CustomModule()
        config = module.get_menu_config()
        
        assert config["label"] == "Custom Module"
        assert config["icon"] == "custom_icon"
        assert len(config["actions"]) == 1
        
        module.on_shutdown()
        assert module.cleaned_up is True
