"""
Pydantic models for Ragic Registry configuration.

Provides strict validation for ragic_registry.json structure.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


from core.ragic.enums import SyncStrategy


class FieldMapping(BaseModel):
    """
    Mapping of a logical field name to its Ragic field ID.
    
    Attributes:
        field_id: The Ragic field ID (e.g., "1005971").
        description: Optional human-readable description.
        required: Whether this field is required for operations.
    """
    field_id: str
    description: Optional[str] = None
    required: bool = False


class FormConfig(BaseModel):
    """
    Configuration for a single Ragic form.
    
    Attributes:
        form_key: Unique identifier for this form (e.g., "account_form").
        description: Human-readable description of the form.
        ragic_path: Path to the Ragic sheet (e.g., "/HSIBAdmSys/ychn-test/11").
        sync_strategy: How data syncs between local DB and Ragic.
        local_model_path: Optional Python path to the SQLAlchemy model.
        key_field: Optional field ID that serves as the primary key.
        webhook_key: Optional key for webhook routing (e.g., "administrative_account").
        field_mapping: Dictionary mapping logical names to Ragic field IDs.
    """
    form_key: str
    description: str = ""
    ragic_path: str
    sync_strategy: SyncStrategy = SyncStrategy.RAGIC_MASTER
    local_model_path: Optional[str] = None
    key_field: Optional[str] = None
    webhook_key: Optional[str] = None
    field_mapping: Dict[str, str] = Field(default_factory=dict)
    
    @field_validator("ragic_path")
    @classmethod
    def validate_ragic_path(cls, v: str) -> str:
        """Ensure ragic_path starts with /"""
        if not v.startswith("/"):
            return f"/{v}"
        return v
    
    def get_field_id(self, field_name: str) -> Optional[str]:
        """Get the Ragic field ID for a logical field name."""
        return self.field_mapping.get(field_name)
    
    def get_field_id_strict(self, field_name: str) -> str:
        """Get field ID or raise error if not found."""
        from core.ragic.exceptions import RagicConfigurationError
        
        field_id = self.field_mapping.get(field_name)
        if field_id is None:
            raise RagicConfigurationError(
                f"Field '{field_name}' not found in form '{self.form_key}'",
                form_key=self.form_key,
            )
        return field_id


class GlobalSettings(BaseModel):
    """
    Global Ragic settings.
    
    Attributes:
        base_url: Base URL for Ragic API.
        default_timeout: Default HTTP timeout in seconds.
        naming: Default naming convention for API calls.
    """
    base_url: str = "https://ap13.ragic.com"
    default_timeout: float = 30.0
    naming: str = "EID"
    
    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Remove trailing slash from base_url."""
        return v.rstrip("/")


class RagicRegistryConfig(BaseModel):
    """
    Root configuration model for ragic_registry.json.
    
    Attributes:
        schema_version: Version of the registry schema.
        settings: Global Ragic settings.
        forms: Dictionary of form configurations keyed by form_key.
    """
    schema_version: str = "1.0"
    settings: GlobalSettings = Field(default_factory=GlobalSettings)
    forms: Dict[str, FormConfig] = Field(default_factory=dict)
    
    def get_form(self, form_key: str) -> Optional[FormConfig]:
        """Get form config by key."""
        return self.forms.get(form_key)
    
    def get_form_strict(self, form_key: str) -> FormConfig:
        """Get form config or raise error if not found."""
        from core.ragic.exceptions import RagicConfigurationError
        
        form = self.forms.get(form_key)
        if form is None:
            available = list(self.forms.keys())
            raise RagicConfigurationError(
                f"Form key '{form_key}' not found in registry. "
                f"Available forms: {available}",
                form_key=form_key,
            )
        return form
    
    def get_form_by_webhook_key(self, webhook_key: str) -> Optional[FormConfig]:
        """Find form config by webhook key."""
        for form in self.forms.values():
            if form.webhook_key == webhook_key:
                return form
        return None
