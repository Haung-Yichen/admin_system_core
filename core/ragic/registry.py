"""
Ragic Registry - Centralized configuration management.

Singleton class responsible for loading, parsing, and providing access
to all Ragic form configurations. This is the ONLY place in the system
that should know about raw Ragic URLs or Field IDs.

Features:
    - Hot-reloading support via reload() method
    - Pydantic validation of configuration
    - Thread-safe singleton pattern
    - Lazy loading of configuration
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.ragic.enums import SyncStrategy
from core.ragic.exceptions import RagicConfigurationError
from core.ragic.registry_models import FormConfig, GlobalSettings, RagicRegistryConfig

logger = logging.getLogger(__name__)


class RagicRegistry:
    """
    Singleton registry for Ragic form configurations.
    
    This class is the single source of truth for all Ragic configurations.
    It loads configuration from ragic_registry.json and provides methods
    to access form configs, field IDs, and URLs.
    
    Usage:
        registry = get_ragic_registry()
        form_config = registry.get_form_config("account_form")
        field_id = registry.get_field_id("account_form", "EMPLOYEE_ID")
        url = registry.get_ragic_url("account_form")
    
    Hot Reload:
        registry.reload()  # Reloads configuration from file
    """
    
    _instance: Optional["RagicRegistry"] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> "RagicRegistry":
        """Ensure singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the registry (only on first instantiation)."""
        if self._initialized:
            return
            
        self._config: Optional[RagicRegistryConfig] = None
        self._config_path: Optional[Path] = None
        self._config_lock = threading.RLock()
        self._initialized = True
    
    # =========================================================================
    # Loading and Reloading
    # =========================================================================
    
    def load(self, config_path: Optional[Path] = None) -> None:
        """
        Load configuration from JSON file.
        
        Args:
            config_path: Path to ragic_registry.json. If not provided,
                        searches in standard locations.
        
        Raises:
            RagicConfigurationError: If configuration file not found or invalid.
        """
        with self._config_lock:
            # Find config file
            if config_path:
                self._config_path = Path(config_path)
            else:
                self._config_path = self._find_config_file()
            
            if not self._config_path or not self._config_path.exists():
                raise RagicConfigurationError(
                    f"Configuration file not found: {self._config_path}"
                )
            
            logger.info(f"Loading Ragic registry from: {self._config_path}")
            
            try:
                with open(self._config_path, "r", encoding="utf-8") as f:
                    raw_config = json.load(f)
                
                # Remove JSON schema keys
                raw_config.pop("$schema", None)
                raw_config.pop("$comment", None)
                
                # Parse and validate with Pydantic
                self._config = RagicRegistryConfig.model_validate(raw_config)
                
                logger.info(
                    f"Loaded {len(self._config.forms)} form configurations: "
                    f"{list(self._config.forms.keys())}"
                )
                
            except json.JSONDecodeError as e:
                raise RagicConfigurationError(f"Invalid JSON in config file: {e}")
            except Exception as e:
                raise RagicConfigurationError(f"Failed to load configuration: {e}")
    
    def reload(self) -> None:
        """
        Reload configuration from file.
        
        Useful for hot-reloading after admin panel updates.
        Thread-safe operation.
        """
        logger.info("Reloading Ragic registry configuration...")
        self.load(self._config_path)
    
    def _find_config_file(self) -> Optional[Path]:
        """Find ragic_registry.json in standard locations."""
        search_paths = [
            Path.cwd() / "ragic_registry.json",
            Path(__file__).parent.parent.parent / "ragic_registry.json",
            Path(__file__).parent.parent.parent.parent / "ragic_registry.json",
        ]
        
        for path in search_paths:
            if path.exists():
                return path
        
        return search_paths[0]  # Return default path for error message
    
    def _ensure_loaded(self) -> None:
        """Ensure configuration is loaded."""
        if self._config is None:
            self.load()
    
    # =========================================================================
    # Configuration Access
    # =========================================================================
    
    @property
    def settings(self) -> GlobalSettings:
        """Get global settings."""
        self._ensure_loaded()
        return self._config.settings
    
    @property
    def base_url(self) -> str:
        """Get the Ragic base URL."""
        return self.settings.base_url
    
    @property
    def default_timeout(self) -> float:
        """Get the default HTTP timeout."""
        return self.settings.default_timeout
    
    def get_form_config(self, form_key: str) -> FormConfig:
        """
        Get configuration for a specific form.
        
        Args:
            form_key: The form key (e.g., "account_form").
        
        Returns:
            FormConfig object.
        
        Raises:
            RagicConfigurationError: If form key not found.
        """
        self._ensure_loaded()
        return self._config.get_form_strict(form_key)
    
    def get_form_config_optional(self, form_key: str) -> Optional[FormConfig]:
        """
        Get configuration for a form, or None if not found.
        
        Args:
            form_key: The form key.
        
        Returns:
            FormConfig or None.
        """
        self._ensure_loaded()
        return self._config.get_form(form_key)
    
    def get_form_by_webhook_key(self, webhook_key: str) -> Optional[FormConfig]:
        """
        Find form configuration by webhook key.
        
        Args:
            webhook_key: The webhook routing key (e.g., "chatbot_sop").
        
        Returns:
            FormConfig or None if not found.
        """
        self._ensure_loaded()
        return self._config.get_form_by_webhook_key(webhook_key)
    
    def list_forms(self) -> List[str]:
        """Get list of all registered form keys."""
        self._ensure_loaded()
        return list(self._config.forms.keys())
    
    def list_webhook_keys(self) -> List[str]:
        """Get list of all webhook keys."""
        self._ensure_loaded()
        return [
            form.webhook_key 
            for form in self._config.forms.values() 
            if form.webhook_key
        ]
    
    # =========================================================================
    # Field Access
    # =========================================================================
    
    def get_field_id(self, form_key: str, field_name: str) -> str:
        """
        Get the Ragic field ID for a logical field name.
        
        Args:
            form_key: The form key (e.g., "account_form").
            field_name: The logical field name (e.g., "EMPLOYEE_ID").
        
        Returns:
            The Ragic field ID (e.g., "1005983").
        
        Raises:
            RagicConfigurationError: If form or field not found.
        """
        form = self.get_form_config(form_key)
        return form.get_field_id_strict(field_name)
    
    def get_field_id_optional(
        self, 
        form_key: str, 
        field_name: str
    ) -> Optional[str]:
        """
        Get field ID or None if not found.
        
        Args:
            form_key: The form key.
            field_name: The logical field name.
        
        Returns:
            Field ID or None.
        """
        try:
            form = self.get_form_config(form_key)
            return form.get_field_id(field_name)
        except RagicConfigurationError:
            return None
    
    def get_all_field_ids(self, form_key: str) -> Dict[str, str]:
        """
        Get all field mappings for a form.
        
        Args:
            form_key: The form key.
        
        Returns:
            Dictionary mapping logical names to field IDs.
        """
        form = self.get_form_config(form_key)
        return form.field_mapping.copy()
    
    # =========================================================================
    # URL Access
    # =========================================================================
    
    def get_ragic_url(self, form_key: str) -> str:
        """
        Get the full Ragic URL for a form.
        
        Args:
            form_key: The form key.
        
        Returns:
            Full URL (e.g., "https://ap13.ragic.com/HSIBAdmSys/ychn-test/11").
        """
        form = self.get_form_config(form_key)
        return f"{self.base_url}{form.ragic_path}"
    
    def get_sheet_path(self, form_key: str) -> str:
        """
        Get the Ragic sheet path for a form.
        
        Args:
            form_key: The form key.
        
        Returns:
            Sheet path (e.g., "/HSIBAdmSys/ychn-test/11").
        """
        form = self.get_form_config(form_key)
        return form.ragic_path
    
    # =========================================================================
    # Strategy Access
    # =========================================================================
    
    def get_sync_strategy(self, form_key: str) -> SyncStrategy:
        """
        Get the sync strategy for a form.
        
        Args:
            form_key: The form key.
        
        Returns:
            SyncStrategy enum value.
        """
        form = self.get_form_config(form_key)
        return form.sync_strategy
    
    def get_forms_by_strategy(self, strategy: SyncStrategy) -> List[FormConfig]:
        """
        Get all forms using a specific sync strategy.
        
        Args:
            strategy: The sync strategy to filter by.
        
        Returns:
            List of FormConfig objects.
        """
        self._ensure_loaded()
        return [
            form 
            for form in self._config.forms.values() 
            if form.sync_strategy == strategy
        ]


# =============================================================================
# Singleton Access Functions
# =============================================================================


_registry: Optional[RagicRegistry] = None


def get_ragic_registry() -> RagicRegistry:
    """
    Get the singleton RagicRegistry instance.
    
    Returns:
        The global RagicRegistry instance.
    """
    global _registry
    if _registry is None:
        _registry = RagicRegistry()
    return _registry


def reset_ragic_registry() -> None:
    """
    Reset the singleton registry (for testing).
    """
    global _registry
    RagicRegistry._instance = None
    _registry = None
