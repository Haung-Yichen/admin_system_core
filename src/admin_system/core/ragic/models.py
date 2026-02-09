"""
Ragic Model Base Class.

Provides a declarative way to define Ragic form structures,
similar to SQLAlchemy's declarative base.
"""

from typing import Any, ClassVar, Dict, List, Optional, Type
from difflib import SequenceMatcher

from core.ragic.fields import RagicField


class RagicModelMeta(type):
    """
    Metaclass for RagicModel.
    
    Collects RagicField definitions and builds the field mapping.
    """
    
    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        # Collect fields from class definition
        fields: Dict[str, RagicField] = {}
        
        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, RagicField):
                attr_value._attr_name = attr_name
                fields[attr_name] = attr_value
        
        # Also collect from parent classes
        for base in bases:
            if hasattr(base, "_fields"):
                for attr_name, field_def in base._fields.items():
                    if attr_name not in fields:
                        fields[attr_name] = field_def
        
        namespace["_fields"] = fields
        return super().__new__(mcs, name, bases, namespace)


class RagicModel(metaclass=RagicModelMeta):
    """
    Base class for Ragic form models.
    
    Subclass this to define a Ragic form structure:
    
        class Account(RagicModel):
            _sheet_path = "/HSIBAdmSys/ychn-test/11"
            
            emails = RagicField("1005977", "Emails", fuzzy_names=["E-mail", "電子郵件"])
            name = RagicField("1005975", "Name", required=True)
            employee_id = RagicField("1005983", "Employee ID")
    """
    
    # Sheet path (must be defined in subclass)
    _sheet_path: ClassVar[str] = ""
    
    # Field definitions (populated by metaclass)
    _fields: ClassVar[Dict[str, RagicField]] = {}
    
    # Ragic record ID (always present)
    ragic_id: Optional[int] = None
    
    def __init__(self, **data: Any) -> None:
        """
        Initialize model from keyword arguments.
        
        Args:
            **data: Field values by attribute name.
        """
        self.ragic_id = data.pop("ragic_id", None) or data.pop("_ragic_id", None)
        
        for attr_name, field_def in self._fields.items():
            value = data.get(attr_name, field_def.default)
            setattr(self, attr_name, field_def.convert_value(value))
    
    @classmethod
    def from_ragic_record(cls, record: Dict[str, Any]) -> "RagicModel":
        """
        Create model instance from a raw Ragic API response record.
        
        Args:
            record: Raw record dictionary from Ragic API.
        
        Returns:
            Model instance with parsed field values.
        """
        data: Dict[str, Any] = {}
        
        # Extract ragic_id
        data["ragic_id"] = record.get("_ragic_id") or record.get("ragic_id")
        
        # Parse each field
        for attr_name, field_def in cls._fields.items():
            value = cls._get_field_value(record, field_def)
            if value is not None:
                data[attr_name] = value
        
        return cls(**data)
    
    @classmethod
    def _get_field_value(
        cls,
        record: Dict[str, Any],
        field_def: RagicField,
    ) -> Any:
        """
        Extract field value from record using ID or fuzzy matching.
        
        Args:
            record: Raw Ragic record.
            field_def: Field definition.
        
        Returns:
            Extracted value or None.
        """
        # Try exact field ID
        if field_def.field_id in record:
            return record[field_def.field_id]
        
        # Try underscore prefix (Ragic format)
        if f"_{field_def.field_id}" in record:
            return record[f"_{field_def.field_id}"]
        
        # Fuzzy name matching
        for key, value in record.items():
            for name in field_def.fuzzy_names:
                if cls._fuzzy_match(key, name, threshold=0.8):
                    return value
        
        return None
    
    @staticmethod
    def _fuzzy_match(s1: str, s2: str, threshold: float = 0.8) -> bool:
        """Check if two strings match with fuzzy threshold."""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio() >= threshold
    
    @classmethod
    def get_field_id(cls, attr_name: str) -> Optional[str]:
        """
        Get the Ragic field ID for an attribute name.
        
        Args:
            attr_name: Python attribute name (e.g., "email").
        
        Returns:
            Ragic field ID (e.g., "1000381") or None.
        """
        if attr_name in cls._fields:
            return cls._fields[attr_name].field_id
        return None
    
    @classmethod
    def get_sheet_path(cls) -> str:
        """Get the Ragic sheet path for this model."""
        return cls._sheet_path
    
    def to_ragic_payload(self) -> Dict[str, Any]:
        """
        Convert model to Ragic API payload format.
        
        Returns:
            Dictionary with field IDs as keys.
        """
        payload: Dict[str, Any] = {}
        
        for attr_name, field_def in self._fields.items():
            value = getattr(self, attr_name, None)
            if value is not None:
                payload[field_def.field_id] = value
        
        return payload
    
    def __repr__(self) -> str:
        fields_str = ", ".join(
            f"{name}={getattr(self, name, None)!r}"
            for name in list(self._fields.keys())[:3]
        )
        return f"{self.__class__.__name__}(ragic_id={self.ragic_id}, {fields_str})"
