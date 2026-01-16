"""
Unit Tests for core.registry module.

Tests ModuleRegistry and ModuleLoader classes.
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


class TestModuleRegistry:
    """Tests for ModuleRegistry class."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        from core.registry import ModuleRegistry
        
        # Reset singleton state
        ModuleRegistry._instance = None
        yield
        ModuleRegistry._instance = None
    
    def test_singleton_pattern(self):
        """Test ModuleRegistry follows singleton pattern."""
        from core.registry import ModuleRegistry
        
        registry1 = ModuleRegistry()
        registry2 = ModuleRegistry()
        
        assert registry1 is registry2
    
    def test_initialization(self):
        """Test ModuleRegistry initializes correctly."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        
        assert registry._modules == {}
        assert registry._context is None
        assert registry._initialized is True
    
    def test_set_context(self, app_context):
        """Test set_context() stores the context."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        registry.set_context(app_context)
        
        assert registry._context is app_context
    
    def test_register_module(self, mock_module):
        """Test register() adds module to registry."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        result = registry.register(mock_module)
        
        assert result is True
        assert "mock_module" in registry._modules
        assert registry._modules["mock_module"] is mock_module
    
    def test_register_duplicate_returns_false(self, mock_module_factory):
        """Test register() returns False for duplicate module names."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        module1 = mock_module_factory("test")
        module2 = mock_module_factory("test")
        
        registry.register(module1)
        result = registry.register(module2)
        
        assert result is False
    
    def test_register_initializes_module_with_context(self, app_context, mock_module):
        """Test register() calls on_entry when context available."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        registry.set_context(app_context)
        registry.register(mock_module)
        
        assert mock_module._initialized is True
    
    def test_register_class(self, app_context, mock_module):
        """Test register_class() instantiates and registers module."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        registry.set_context(app_context)
        
        # Use the mock_module's class
        MockModuleClass = type(mock_module)
        result = registry.register_class(MockModuleClass)
        
        assert result is True
        assert "mock_module" in registry._modules
    
    def test_unregister_module(self, mock_module):
        """Test unregister() removes module and calls shutdown."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        registry.register(mock_module)
        
        result = registry.unregister("mock_module")
        
        assert result is True
        assert "mock_module" not in registry._modules
        assert mock_module._shutdown is True
    
    def test_unregister_nonexistent_returns_false(self):
        """Test unregister() returns False for unknown module."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        result = registry.unregister("nonexistent")
        
        assert result is False
    
    def test_get_module(self, mock_module):
        """Test get_module() returns correct module."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        registry.register(mock_module)
        
        found = registry.get_module("mock_module")
        
        assert found is mock_module
    
    def test_get_module_not_found(self):
        """Test get_module() returns None for unknown module."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        found = registry.get_module("nonexistent")
        
        assert found is None
    
    def test_get_all_modules(self, mock_module_factory):
        """Test get_all_modules() returns all registered modules."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        module1 = mock_module_factory("module1")
        module2 = mock_module_factory("module2")
        
        registry.register(module1)
        registry.register(module2)
        
        modules = registry.get_all_modules()
        
        assert len(modules) == 2
        assert module1 in modules
        assert module2 in modules
    
    def test_get_module_names(self, mock_module_factory):
        """Test get_module_names() returns list of names."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        registry.register(mock_module_factory("alpha"))
        registry.register(mock_module_factory("beta"))
        
        names = registry.get_module_names()
        
        assert "alpha" in names
        assert "beta" in names
    
    def test_get_menu_configs(self, mock_module_factory):
        """Test get_menu_configs() returns configs from all modules."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        registry.register(mock_module_factory("module1"))
        registry.register(mock_module_factory("module2"))
        
        configs = registry.get_menu_configs()
        
        assert len(configs) == 2
        assert any(c["label"] == "Module1" for c in configs)
        assert any(c["label"] == "Module2" for c in configs)
    
    def test_shutdown_all(self, mock_module_factory):
        """Test shutdown_all() unregisters all modules."""
        from core.registry import ModuleRegistry
        
        registry = ModuleRegistry()
        module1 = mock_module_factory("m1")
        module2 = mock_module_factory("m2")
        
        registry.register(module1)
        registry.register(module2)
        registry.shutdown_all()
        
        assert len(registry._modules) == 0
        assert module1._shutdown is True
        assert module2._shutdown is True


class TestModuleLoader:
    """Tests for ModuleLoader class."""
    
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before each test."""
        from core.registry import ModuleRegistry
        ModuleRegistry._instance = None
        yield
        ModuleRegistry._instance = None
    
    def test_load_from_nonexistent_directory(self):
        """Test load_from_directory() handles missing directory."""
        from core.registry import ModuleRegistry, ModuleLoader
        
        registry = ModuleRegistry()
        loader = ModuleLoader(registry)
        
        count = loader.load_from_directory("/nonexistent/path")
        
        assert count == 0
    
    def test_loader_initialization(self):
        """Test ModuleLoader initializes with registry."""
        from core.registry import ModuleRegistry, ModuleLoader
        
        registry = ModuleRegistry()
        loader = ModuleLoader(registry)
        
        assert loader._registry is registry
