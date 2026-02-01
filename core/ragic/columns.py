"""
Ragic Columns Configuration Loader.

Loads column definitions from the centralized ragic_columns.json file.
This is the single source of truth for all Ragic field IDs and form URLs.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


# Path to the centralized config file (project root)
_CONFIG_FILE = Path(__file__).parent.parent.parent / "ragic_columns.json"


@lru_cache(maxsize=1)
def _load_ragic_columns() -> dict[str, Any]:
    """Load and cache the ragic_columns.json file."""
    if not _CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"Ragic columns config not found: {_CONFIG_FILE}. "
            "Please ensure ragic_columns.json exists in the project root."
        )
    
    with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_form_config(form_name: str) -> dict[str, Any]:
    """
    Get configuration for a specific form.
    
    Args:
        form_name: One of 'account_form', 'leave_form', 'leave_type_form'.
    
    Returns:
        dict containing 'url', 'sheet_path', 'fields', etc.
    
    Raises:
        KeyError: If form_name is not found.
    """
    config = _load_ragic_columns()
    if form_name not in config:
        raise KeyError(f"Form '{form_name}' not found in ragic_columns.json")
    return config[form_name]


def get_form_url(form_name: str) -> str:
    """Get the full URL for a form."""
    return get_form_config(form_name)["url"]


def get_sheet_path(form_name: str) -> str:
    """Get the sheet path (e.g., /HSIBAdmSys/ychn-test/11) for a form."""
    return get_form_config(form_name)["sheet_path"]


def get_field_id(form_name: str, field_name: str) -> str:
    """
    Get a specific field ID from a form.
    
    Args:
        form_name: Form name (e.g., 'account_form').
        field_name: Field name (e.g., 'EMPLOYEE_ID').
    
    Returns:
        Ragic field ID string.
    
    Raises:
        KeyError: If form or field not found.
    """
    fields = get_form_config(form_name)["fields"]
    if field_name not in fields:
        raise KeyError(f"Field '{field_name}' not found in {form_name}")
    return fields[field_name]


def get_all_field_ids(form_name: str) -> dict[str, str]:
    """Get all field IDs for a form as a dict."""
    return get_form_config(form_name)["fields"]


class RagicFormConfig:
    """
    Helper class for accessing a specific form's configuration.
    
    Usage:
        account = RagicFormConfig("account_form")
        print(account.url)
        print(account.field("EMPLOYEE_ID"))
    """
    
    def __init__(self, form_name: str) -> None:
        self._form_name = form_name
        self._config = get_form_config(form_name)
    
    @property
    def url(self) -> str:
        return self._config["url"]
    
    @property
    def sheet_path(self) -> str:
        return self._config["sheet_path"]
    
    @property
    def description(self) -> str:
        return self._config.get("description", "")
    
    @property
    def key_field(self) -> str | None:
        return self._config.get("key_field")
    
    @property
    def fields(self) -> dict[str, str]:
        return self._config["fields"]
    
    def field(self, name: str) -> str:
        """Get a field ID by name."""
        return self._config["fields"][name]
    
    def __getattr__(self, name: str) -> str:
        """Allow attribute-style access to field IDs (e.g., config.EMPLOYEE_ID)."""
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._config["fields"][name]
        except KeyError:
            raise AttributeError(f"Field '{name}' not found in {self._form_name}")


# Pre-configured form accessors (singleton-like)
@lru_cache(maxsize=5)
def get_account_form() -> RagicFormConfig:
    """Get Account form configuration."""
    return RagicFormConfig("account_form")


@lru_cache(maxsize=5)
def get_leave_form() -> RagicFormConfig:
    """Get Leave form configuration."""
    return RagicFormConfig("leave_form")


@lru_cache(maxsize=5)
def get_leave_type_form() -> RagicFormConfig:
    """Get Leave Type form configuration."""
    return RagicFormConfig("leave_type_form")


@lru_cache(maxsize=5)
def get_user_form() -> RagicFormConfig:
    """Get User Identity form configuration."""
    return RagicFormConfig("user_form")


@lru_cache(maxsize=5)
def get_sop_form() -> RagicFormConfig:
    """Get SOP Knowledge Base form configuration."""
    return RagicFormConfig("sop_form")
