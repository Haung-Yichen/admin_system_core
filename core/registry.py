"""
Module Registry - Dynamic module registration and management.
Implements Open/Closed Principle (OCP) for extensibility.
"""
from typing import Dict, List, Optional, Type
import logging

from core.interface import IAppModule
from core.app_context import AppContext


class ModuleRegistry:
    """
    Registry for managing application modules.
    Allows dynamic registration and lookup of modules.
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
        self._context: Optional[AppContext] = None
        self._initialized = True
    
    def set_context(self, context: AppContext) -> None:
        """Set the application context for module initialization."""
        self._context = context
    
    def register(self, module: IAppModule) -> bool:
        """
        Register a module with the registry.
        
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
        
        Args:
            module_class: The module class to instantiate and register
            
        Returns:
            bool: True if registration successful, False otherwise
        """
        try:
            module_instance = module_class()
            return self.register(module_instance)
        except Exception as e:
            self._logger.error(f"Failed to instantiate module class: {e}")
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
    
    def shutdown_all(self) -> None:
        """Shutdown all registered modules."""
        for module_name in list(self._modules.keys()):
            self.unregister(module_name)
        self._logger.info("All modules shut down.")


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
