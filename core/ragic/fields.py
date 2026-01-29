"""
Ragic Field Descriptors.

Defines metadata for Ragic form fields, similar to SQLAlchemy Column.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional, Type


@dataclass
class RagicField:
    """
    Represents a field (column) in a Ragic sheet.
    
    Attributes:
        field_id: The Ragic field ID (e.g., "1000381").
        name: Human-readable field name for debugging/logging.
        required: Whether the field is required for create operations.
        fuzzy_names: Alternative names for fuzzy matching (Chinese variants).
        field_type: Python type for value conversion (str, int, bool, etc.).
        default: Default value if not provided.
    
    Example:
        class Employee(RagicModel):
            email = RagicField("1000381", "Email", fuzzy_names=["E-mail", "電子郵件"])
            name = RagicField("1000376", "Name", required=True)
    """
    
    field_id: str
    name: str
    required: bool = False
    fuzzy_names: List[str] = field(default_factory=list)
    field_type: Type = str
    default: Any = None
    
    # Internal: attribute name set by RagicModel metaclass
    _attr_name: Optional[str] = field(default=None, repr=False)
    
    def __post_init__(self) -> None:
        """Ensure fuzzy_names always includes the field name."""
        if self.name and self.name not in self.fuzzy_names:
            self.fuzzy_names = [self.name] + self.fuzzy_names
    
    def convert_value(self, value: Any) -> Any:
        """Convert raw value to the appropriate Python type."""
        if value is None:
            return self.default
        
        if self.field_type == bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        
        if self.field_type == int:
            try:
                return int(value)
            except (ValueError, TypeError):
                return self.default
        
        if self.field_type == float:
            try:
                return float(value)
            except (ValueError, TypeError):
                return self.default
        
        # Default: convert to string and strip
        if isinstance(value, str):
            return value.strip() or self.default
        
        return str(value) if value else self.default
