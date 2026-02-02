"""
Leave Type Sync Service.

Handles synchronization of Leave Type master data from Ragic to local database.
Refactored to use the Core BaseRagicSyncService with RagicRegistry.
"""

import logging
from typing import Any, Dict, Optional

from core.ragic.registry import get_ragic_registry
from core.ragic.sync_base import BaseRagicSyncService
from modules.administrative.models import LeaveType

logger = logging.getLogger(__name__)


# =============================================================================
# Field Mapping from RagicRegistry
# =============================================================================


class LeaveTypeFieldMapping:
    """
    Leave Type form field ID mapping - uses RagicRegistry.
    
    Provides a clean interface to access field IDs from the central registry.
    All field IDs are loaded from ragic_registry.json at runtime.
    """
    
    _form_key = "leave_type_form"

    @classmethod
    def _get_field(cls, name: str, default: str = "") -> str:
        """
        Get a field ID from the registry.
        
        Args:
            name: The logical field name (e.g., "LEAVE_TYPE_CODE").
            default: Default value if field not found.
            
        Returns:
            The Ragic field ID.
        """
        try:
            return get_ragic_registry().get_field_id(cls._form_key, name)
        except Exception:
            logger.warning(f"Field '{name}' not found in registry for form '{cls._form_key}'")
            return default

    @classmethod
    def RAGIC_ID(cls) -> str:
        return cls._get_field("RAGIC_ID", "_ragicId")

    @classmethod
    def LEAVE_TYPE_CODE(cls) -> str:
        return cls._get_field("LEAVE_TYPE_CODE")

    @classmethod
    def LEAVE_TYPE_NAME(cls) -> str:
        return cls._get_field("LEAVE_TYPE_NAME")

    @classmethod
    def DEDUCTION_MULTIPLIER(cls) -> str:
        return cls._get_field("DEDUCTION_MULTIPLIER")


# =============================================================================
# Data Transformation Helpers
# =============================================================================


def _parse_string(value: Any) -> Optional[str]:
    """Parse a string value, converting empty to None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return str(value).strip() or None


def _parse_float(value: Any) -> Optional[float]:
    """Parse a float value from Ragic."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            logger.warning(f"Failed to parse float: {value}")
            return None
    return None


def _parse_int(value: Any) -> Optional[int]:
    """Parse an integer value from Ragic."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            logger.warning(f"Failed to parse int: {value}")
            return None
    return None


# =============================================================================
# Sync Service
# =============================================================================


class LeaveTypeSyncService(BaseRagicSyncService[LeaveType]):
    """
    Leave Type Sync Service implementation using Core Base Class.
    
    Uses RagicRegistry for configuration (form_key="leave_type_form").
    This service handles synchronization of leave type master data from
    Ragic to the local database for use in leave request forms.
    """

    def __init__(self) -> None:
        super().__init__(
            model_class=LeaveType,
            form_key="leave_type_form",
        )

    async def map_record_to_dict(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map a Ragic leave type record to a dictionary suitable for LeaveType model.
        
        Args:
            record: Raw Ragic record with field IDs as keys.
            
        Returns:
            Dictionary with model field names, or None to skip this record.
        """
        try:
            # Extract ragic_id - use _ragicId if the field mapping returns it
            ragic_id_field = LeaveTypeFieldMapping.RAGIC_ID()
            if ragic_id_field == "_ragicId":
                ragic_id = record.get("_ragicId")
            else:
                ragic_id = _parse_int(record.get(ragic_id_field))
                if ragic_id is None:
                    ragic_id = record.get("_ragicId")

            leave_type_code = _parse_string(record.get(LeaveTypeFieldMapping.LEAVE_TYPE_CODE()))
            leave_type_name = _parse_string(record.get(LeaveTypeFieldMapping.LEAVE_TYPE_NAME()))

            # Validation - skip records with missing required fields
            if ragic_id is None:
                logger.warning(f"Skipping leave type record: missing ragic_id. Record: {record}")
                return None

            if not leave_type_code:
                logger.warning(
                    f"Skipping leave type record: missing leave_type_code. "
                    f"ragic_id={ragic_id}"
                )
                return None

            if not leave_type_name:
                logger.warning(
                    f"Skipping leave type record: missing leave_type_name. "
                    f"ragic_id={ragic_id}"
                )
                return None

            # Parse optional fields
            deduction_multiplier = _parse_float(
                record.get(LeaveTypeFieldMapping.DEDUCTION_MULTIPLIER())
            )

            return {
                "ragic_id": ragic_id,
                "leave_type_code": leave_type_code,
                "leave_type_name": leave_type_name,
                "deduction_multiplier": deduction_multiplier,
            }

        except Exception as e:
            logger.error(f"Error mapping leave type record: {e}")
            return None


# =============================================================================
# Singleton Helper
# =============================================================================


_leave_type_sync_service: Optional[LeaveTypeSyncService] = None


def get_leave_type_sync_service() -> LeaveTypeSyncService:
    """
    Get the singleton LeaveTypeSyncService instance.
    
    Returns:
        LeaveTypeSyncService instance.
    """
    global _leave_type_sync_service
    if _leave_type_sync_service is None:
        _leave_type_sync_service = LeaveTypeSyncService()
    return _leave_type_sync_service
