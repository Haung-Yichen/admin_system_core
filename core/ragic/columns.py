"""
Ragic Columns Configuration Loader.

DEPRECATED: This module is deprecated. Use core.ragic.registry instead.

This module now serves as a backward-compatible shim that internally
uses the new RagicRegistry. All functionality is delegated to the
single source of truth: ragic_registry.json.

The new RagicRegistry provides:
- Centralized configuration from ragic_registry.json
- Hot-reloading support
- Sync strategy definitions
- Better error handling

Example migration:
    # Old way (deprecated)
    from core.ragic.columns import get_account_form
    form = get_account_form()
    
    # New way
    from core.ragic.registry import get_ragic_registry
    registry = get_ragic_registry()
    form = registry.get_form_config("account_form")
"""

import warnings
from functools import lru_cache
from typing import Any


def _deprecation_warning(func_name: str) -> None:
    """Emit deprecation warning for legacy functions."""
    warnings.warn(
        f"{func_name}() is deprecated. Use core.ragic.registry.get_ragic_registry() instead.",
        DeprecationWarning,
        stacklevel=3
    )


def _get_registry():
    """Get the RagicRegistry instance (lazy import to avoid circular imports)."""
    from core.ragic.registry import get_ragic_registry
    return get_ragic_registry()


def get_form_config(form_name: str) -> dict[str, Any]:
    """
    Get configuration for a specific form.
    
    DEPRECATED: Use get_ragic_registry().get_form_config() instead.
    
    Args:
        form_name: One of 'account_form', 'leave_form', 'leave_type_form', etc.
    
    Returns:
        dict containing 'url', 'sheet_path', 'fields', etc. (legacy format)
    
    Raises:
        KeyError: If form_name is not found.
    """
    _deprecation_warning("get_form_config")
    registry = _get_registry()
    form_config = registry.get_form_config(form_name)
    
    # Convert to legacy format for backward compatibility
    return {
        "url": f"{registry.base_url}{form_config.ragic_path}",
        "sheet_path": form_config.ragic_path,
        "description": form_config.description,
        "key_field": form_config.key_field,
        "fields": dict(form_config.field_mapping),
    }


def get_form_url(form_name: str) -> str:
    """Get the full URL for a form."""
    _deprecation_warning("get_form_url")
    return _get_registry().get_ragic_url(form_name)


def get_sheet_path(form_name: str) -> str:
    """Get the sheet path (e.g., /HSIBAdmSys/ychn-test/11) for a form."""
    _deprecation_warning("get_sheet_path")
    return _get_registry().get_form_config(form_name).ragic_path


def get_field_id(form_name: str, field_name: str) -> str:
    """
    Get a specific field ID from a form.
    
    DEPRECATED: Use get_ragic_registry().get_field_id() instead.
    
    Args:
        form_name: Form name (e.g., 'account_form').
        field_name: Field name (e.g., 'EMPLOYEE_ID').
    
    Returns:
        Ragic field ID string.
    
    Raises:
        KeyError: If form or field not found.
    """
    _deprecation_warning("get_field_id")
    return _get_registry().get_field_id(form_name, field_name)


def get_all_field_ids(form_name: str) -> dict[str, str]:
    """Get all field IDs for a form as a dict."""
    _deprecation_warning("get_all_field_ids")
    return dict(_get_registry().get_form_config(form_name).field_mapping)


class RagicFormConfig:
    """
    Helper class for accessing a specific form's configuration.
    
    DEPRECATED: Use get_ragic_registry().get_form_config() instead.
    
    Usage:
        account = RagicFormConfig("account_form")
        print(account.url)
        print(account.field("EMPLOYEE_ID"))
    """
    
    def __init__(self, form_name: str) -> None:
        _deprecation_warning("RagicFormConfig")
        self._form_name = form_name
        registry = _get_registry()
        self._form_config = registry.get_form_config(form_name)
        self._base_url = registry.base_url
    
    @property
    def url(self) -> str:
        return f"{self._base_url}{self._form_config.ragic_path}"
    
    @property
    def sheet_path(self) -> str:
        return self._form_config.ragic_path
    
    @property
    def description(self) -> str:
        return self._form_config.description or ""
    
    @property
    def key_field(self) -> str | None:
        return self._form_config.key_field
    
    @property
    def fields(self) -> dict[str, str]:
        return dict(self._form_config.field_mapping)
    
    def field(self, name: str) -> str:
        """Get a field ID by name."""
        mapping = self._form_config.field_mapping
        if name not in mapping:
            raise KeyError(f"Field '{name}' not found in {self._form_name}")
        return mapping[name]
    
    def __getattr__(self, name: str) -> str:
        """Allow attribute-style access to field IDs (e.g., config.EMPLOYEE_ID)."""
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._form_config.field_mapping[name]
        except KeyError:
            raise AttributeError(f"Field '{name}' not found in {self._form_name}")


# Pre-configured form accessors (singleton-like)
# DEPRECATED: These functions are deprecated. Use RagicRegistry instead.

@lru_cache(maxsize=5)
def get_account_form() -> RagicFormConfig:
    """
    Get Account form configuration.
    
    DEPRECATED: Use get_ragic_registry().get_form_config("account_form")
    """
    _deprecation_warning("get_account_form")
    return RagicFormConfig("account_form")


@lru_cache(maxsize=5)
def get_leave_form() -> RagicFormConfig:
    """
    Get Leave form configuration.
    
    DEPRECATED: Use get_ragic_registry().get_form_config("leave_form")
    """
    _deprecation_warning("get_leave_form")
    return RagicFormConfig("leave_form")


@lru_cache(maxsize=5)
def get_leave_type_form() -> RagicFormConfig:
    """
    Get Leave Type form configuration.
    
    DEPRECATED: Use get_ragic_registry().get_form_config("leave_type_form")
    """
    _deprecation_warning("get_leave_type_form")
    return RagicFormConfig("leave_type_form")


@lru_cache(maxsize=5)
def get_user_form() -> RagicFormConfig:
    """
    Get User Identity form configuration.
    
    DEPRECATED: Use get_ragic_registry().get_form_config("user_form")
    """
    _deprecation_warning("get_user_form")
    return RagicFormConfig("user_form")


@lru_cache(maxsize=5)
def get_sop_form() -> RagicFormConfig:
    """
    Get SOP Knowledge Base form configuration.
    
    DEPRECATED: Use get_ragic_registry().get_form_config("sop_form")
    """
    _deprecation_warning("get_sop_form")
    return RagicFormConfig("sop_form")
