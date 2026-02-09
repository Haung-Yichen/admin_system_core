"""
Module Registry - Dynamic module registration and management.

Implements Open/Closed Principle (OCP) for extensibility.
Now integrates with the DI provider system for cleaner dependency management.

Key Principles:
- OCP: New modules can be added without modifying the registry
- DIP: Registry depends on abstractions (IAppModule), not concrete modules
- SRP: Registry only handles module lifecycle, not business logic
"""

from typing import Any, Callable, Dict, List, Optional, Type
import inspect
import logging

from core.interface import IAppModule, IModuleContext, ModuleContext
from core.providers import (
    ConfigurationProvider,
    LogService,
    get_configuration_provider,
    get_log_service,
    get_provider_registry,
)

# TYPE_CHECKING import to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.app_context import AppContext


class ModuleRegistry:
    """
    Registry for managing application modules.
    
    Allows dynamic registration and lookup of modules.
    Supports both legacy AppContext injection and modern DI patterns.
    
    Usage (legacy):
        registry = ModuleRegistry()
        registry.set_context(app_context)
        registry.register(MyModule())
        
    Usage (modern DI):
        registry = ModuleRegistry()
        registry.register_with_di(MyModule)  # Dependencies auto-resolved
    """
    
    _instance: Optional["ModuleRegistry"] = None
    
    def __new__(cls) -> "ModuleRegistry":
        """Singleton pattern to ensure single registry instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        if self._initialized:
            return
        
        self._modules: Dict[str, IAppModule] = {}
        self._logger = logging.getLogger(__name__)
        self._context: Optional["AppContext"] = None
        self._module_context: Optional[IModuleContext] = None
        self._initialized = True
    
    def set_context(self, context: "AppContext") -> None:
        """
        Set the application context for module initialization.
        
        This also creates a lightweight ModuleContext for DI-aware modules.
        """
        self._context = context
        # Create lightweight context from providers
        self._module_context = ModuleContext(
            config=get_configuration_provider(),
            log_service=get_log_service(),
        )
    
    def get_module_context(self) -> IModuleContext:
        """
        Get the lightweight module context for DI.
        
        Returns:
            IModuleContext: The module context
        """
        if self._module_context is None:
            self._module_context = ModuleContext(
                config=get_configuration_provider(),
                log_service=get_log_service(),
            )
        return self._module_context
    
    def register(self, module: IAppModule) -> bool:
        """
        Register a module with the registry (legacy method).
        
        Args:
            module: The module instance to register
            
        Returns:
            bool: True if registration successful, False otherwise
        """
        module_name = module.get_module_name()
        
        if module_name in self._modules:
            self._logger.warning(f"Module '{module_name}' already registered. Skipping.")
            return False
        
        self._modules[module_name] = module
        self._logger.info(f"Module '{module_name}' registered successfully.")
        
        # Initialize module if context is available
        if self._context:
            try:
                module.on_entry(self._context)
                self._context.log_event(f"Module '{module_name}' initialized", "SUCCESS")
            except Exception as e:
                self._logger.error(f"Failed to initialize module '{module_name}': {e}")
                self._context.log_event(f"Module '{module_name}' init failed: {e}", "ERROR")
        
        return True
    
    def register_class(self, module_class: Type[IAppModule]) -> bool:
        """
        Register a module by its class (instantiates automatically).
        
        Attempts DI-style constructor injection if the class accepts
        typed dependencies. Falls back to no-arg construction.
        
        Args:
            module_class: The module class to instantiate and register
            
        Returns:
            bool: True if registration successful, False otherwise
        """
        try:
            module_instance = self._create_instance_with_di(module_class)
            return self.register(module_instance)
        except Exception as e:
            self._logger.error(f"Failed to instantiate module class: {e}")
            return False
    
    def _create_instance_with_di(self, module_class: Type[IAppModule]) -> IAppModule:
        """
        Create a module instance, injecting dependencies if possible.
        
        Inspects __init__ signature and provides matching providers.
        
        Args:
            module_class: The module class to instantiate
            
        Returns:
            IAppModule: The instantiated module
        """
        # Check if __init__ has typed parameters we can inject
        sig = inspect.signature(module_class.__init__)
        params = sig.parameters
        
        # Skip 'self' parameter
        injectable_params = {
            name: param for name, param in params.items() 
            if name != 'self'
        }
        
        if not injectable_params:
            # No parameters - simple instantiation
            return module_class()
        
        # Attempt to resolve dependencies
        kwargs = {}
        provider_registry = get_provider_registry()
        
        for name, param in injectable_params.items():
            annotation = param.annotation
            
            # Skip parameters without annotations or with defaults
            if annotation is inspect.Parameter.empty:
                continue
            
            # Try to resolve based on type annotation
            try:
                if annotation is ConfigurationProvider or annotation.__name__ == 'ConfigurationProvider':
                    kwargs[name] = provider_registry.get("config")
                elif annotation is LogService or annotation.__name__ == 'LogService':
                    kwargs[name] = provider_registry.get("log")
                # Add more type mappings as needed
            except (KeyError, AttributeError):
                pass  # Can't resolve - will use default or fail
        
        return module_class(**kwargs)
    
    def register_with_di(
        self,
        module_class: Type[IAppModule],
        dependencies: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Register a module with explicit dependency injection.
        
        This method allows passing specific dependencies to the module
        constructor, useful for testing or custom configurations.
        
        Args:
            module_class: The module class to instantiate
            dependencies: Dict of parameter_name -> value for constructor
            
        Returns:
            bool: True if registration successful
            
        Example:
            registry.register_with_di(
                MyModule,
                dependencies={
                    "config": custom_config,
                    "log": custom_logger,
                }
            )
        """
        try:
            if dependencies:
                module_instance = module_class(**dependencies)
            else:
                module_instance = self._create_instance_with_di(module_class)
            return self.register(module_instance)
        except Exception as e:
            self._logger.error(f"Failed to register module with DI: {e}")
            return False
    
    def unregister(self, module_name: str) -> bool:
        """
        Unregister a module from the registry.
        
        Args:
            module_name: The name of the module to unregister
            
        Returns:
            bool: True if unregistration successful, False otherwise
        """
        if module_name not in self._modules:
            self._logger.warning(f"Module '{module_name}' not found in registry.")
            return False
        
        module = self._modules[module_name]
        try:
            module.on_shutdown()
        except Exception as e:
            self._logger.error(f"Error during module '{module_name}' shutdown: {e}")
        
        del self._modules[module_name]
        self._logger.info(f"Module '{module_name}' unregistered.")
        return True
    
    def get_module(self, module_name: str) -> Optional[IAppModule]:
        """
        Retrieve a module by name.
        
        Args:
            module_name: The name of the module to retrieve
            
        Returns:
            The module instance or None if not found
        """
        return self._modules.get(module_name)
    
    def get_all_modules(self) -> List[IAppModule]:
        """Get all registered modules."""
        return list(self._modules.values())
    
    def get_module_names(self) -> List[str]:
        """Get names of all registered modules."""
        return list(self._modules.keys())
    
    def get_menu_configs(self) -> List[dict]:
        """Get menu configurations from all modules."""
        configs = []
        for module in self._modules.values():
            try:
                config = module.get_menu_config()
                if config:
                    configs.append(config)
            except Exception as e:
                self._logger.error(f"Error getting menu config from module: {e}")
        return configs
    
    async def async_startup_all(self) -> None:
        """
        Call async_startup() on all registered modules.
        
        This should be called during the FastAPI lifespan startup
        when the async event loop is running.
        """
        for module_name, module in self._modules.items():
            if hasattr(module, 'async_startup'):
                try:
                    await module.async_startup()
                    self._logger.info(f"Module '{module_name}' async startup completed.")
                except Exception as e:
                    self._logger.error(f"Module '{module_name}' async startup failed: {e}")

    def shutdown_all(self) -> None:
        """Shutdown all registered modules."""
        for module_name in list(self._modules.keys()):
            self.unregister(module_name)
        self._logger.info("All modules shut down.")
    
    # -------------------------------------------------------------------------
    # Testing Utilities
    # -------------------------------------------------------------------------
    
    @classmethod
    def reset(cls) -> None:
        """
        Reset the singleton instance (for testing only).
        
        This clears all registered modules and allows a fresh start.
        """
        if cls._instance is not None:
            cls._instance._modules.clear()
            cls._instance._context = None
            cls._instance._module_context = None
        cls._instance = None
    
    @classmethod
    def create_test_registry(
        cls,
        modules: Optional[List[IAppModule]] = None,
    ) -> "ModuleRegistry":
        """
        Create a test registry with optional pre-registered modules.
        
        Args:
            modules: Optional list of modules to register
            
        Returns:
            A fresh ModuleRegistry for testing
        """
        cls.reset()
        registry = cls()
        
        # Set up a minimal context
        registry._module_context = ModuleContext(
            config=get_configuration_provider(),
            log_service=get_log_service(),
        )
        
        if modules:
            for module in modules:
                registry.register(module)
        
        return registry


class ModuleLoader:
    """
    Dynamic module loader for discovering and loading modules.
    """
    
    def __init__(self, registry: ModuleRegistry) -> None:
        self._registry = registry
        self._logger = logging.getLogger(__name__)
    
    def load_from_directory(self, modules_path: str) -> int:
        """
        Load modules from a directory.
        
        Supports:
        - Single-file modules: modules/*.py (e.g., echo_module.py)
        - Package modules: modules/<name>/__init__.py (e.g., chatbot/)
        
        Args:
            modules_path: Path to the modules directory
            
        Returns:
            int: Number of modules loaded
        """
        import importlib.util
        import importlib
        from pathlib import Path
        
        path = Path(modules_path)
        if not path.exists():
            self._logger.warning(f"Modules directory '{modules_path}' does not exist.")
            return 0
        
        loaded_count = 0
        
        # 1. Load single-file modules (*.py)
        for module_file in path.glob("*.py"):
            if module_file.name.startswith("_"):
                continue
            
            try:
                spec = importlib.util.spec_from_file_location(
                    module_file.stem, 
                    module_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Look for module classes that implement IAppModule
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and 
                            issubclass(attr, IAppModule) and 
                            attr is not IAppModule):
                            if self._registry.register_class(attr):
                                loaded_count += 1
                                
            except Exception as e:
                self._logger.error(f"Error loading module from '{module_file}': {e}")
        
        # 2. Load package modules (subdirectories with __init__.py)
        for subdir in path.iterdir():
            if not subdir.is_dir():
                continue
            if subdir.name.startswith("_"):
                continue
            
            init_file = subdir / "__init__.py"
            if not init_file.exists():
                continue
            
            try:
                # Import the package using its dotted name
                package_name = f"modules.{subdir.name}"
                module = importlib.import_module(package_name)
                
                # Look for IAppModule implementations
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, IAppModule) and 
                        attr is not IAppModule):
                        if self._registry.register_class(attr):
                            loaded_count += 1
                            self._logger.info(f"Loaded package module: {subdir.name}")
                            
            except Exception as e:
                self._logger.error(f"Error loading package module '{subdir.name}': {e}")
        
        return loaded_count
