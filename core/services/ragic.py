"""
Core Ragic Service.

Handles all Ragic API communication for employee verification.
This is a framework-level service used by all modules requiring Ragic integration.
"""

import logging
from difflib import SequenceMatcher
from typing import Any

from core.app_context import ConfigLoader
from core.schemas.auth import RagicEmployeeData

logger = logging.getLogger(__name__)


class RagicFieldConfig:
    """Configuration for Ragic field mapping."""
    
    def __init__(self, config: dict[str, Any]) -> None:
        ragic_config = config.get("ragic", {})
        
        # Field IDs from config
        self.email_id = ragic_config.get("field_email", "1000381")
        self.name_id = ragic_config.get("field_name", "1000376")
        self.door_access_id = ragic_config.get("field_door_access_id", "1000375")
        
        # Chinese name mappings for fuzzy matching
        self.email_names = ["E-mail", "電子郵件", "email", "Email", "郵件"]
        self.name_names = ["申請人", "姓名", "name", "Name", "員工姓名"]
        self.door_access_names = ["門禁編號", "door_access", "DoorAccessId", "門禁卡號"]


class RagicService:
    """
    Core Ragic API service for employee verification.
    
    Uses fuzzy field name matching to handle Chinese field names
    returned by the Ragic API.
    """
    
    def __init__(self) -> None:
        # Load global config
        self._config_loader = ConfigLoader()
        self._config_loader.load()
        
        ragic_config = self._config_loader.get("ragic", {})
        self._base_url = ragic_config.get("base_url", "https://ap13.ragic.com")
        self._api_key = ragic_config.get("api_key", "")
        self._sheet_path = ragic_config.get("employee_sheet_path", "/HSIBAdmSys/-3/4")
        
        self._field_config = RagicFieldConfig(self._config_loader._config)
    
    def _get_field_value(
        self,
        record: dict[str, Any],
        field_id: str,
        fuzzy_names: list[str] | None = None,
    ) -> str | None:
        """
        Get field value from record using ID or fuzzy name matching.
        
        Args:
            record: Ragic record dictionary.
            field_id: Field ID to look up.
            fuzzy_names: Optional list of field name variants for fuzzy matching.
        
        Returns:
            Field value or None if not found.
        """
        # Try exact field ID first
        if field_id in record:
            return str(record[field_id]).strip() or None
        
        # Try underscore prefix (Ragic format)
        if f"_{field_id}" in record:
            return str(record[f"_{field_id}"]).strip() or None
        
        # Fuzzy name matching for Chinese field names
        if fuzzy_names:
            for key, value in record.items():
                for name in fuzzy_names:
                    if self._fuzzy_match(key, name, threshold=0.8):
                        return str(value).strip() or None
        
        return None
    
    def _fuzzy_match(self, s1: str, s2: str, threshold: float = 0.8) -> bool:
        """Check if two strings match with fuzzy threshold."""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio() >= threshold
    
    async def get_all_employees(self) -> list[dict[str, Any]]:
        """
        Fetch all employee records from Ragic.
        
        Returns:
            List of raw employee records.
        """
        import httpx
        
        url = f"{self._base_url}{self._sheet_path}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Basic {self._api_key}"},
                    params={"api": ""},
                )
                resp.raise_for_status()
                data = resp.json()
                
                # Ragic returns dict with record IDs as keys
                if isinstance(data, dict):
                    return list(data.values())
                return []
                
        except Exception as e:
            logger.error(f"Failed to fetch employees from Ragic: {e}")
            return []
    
    async def verify_email_exists(self, email: str) -> RagicEmployeeData | None:
        """
        Verify if an email exists in the Ragic employee database.
        
        Args:
            email: Email address to verify.
        
        Returns:
            RagicEmployeeData if found, None otherwise.
        """
        email_lower = email.lower().strip()
        employees = await self.get_all_employees()
        
        for record in employees:
            record_email = self._get_field_value(
                record,
                self._field_config.email_id,
                self._field_config.email_names,
            )
            
            if record_email and record_email.lower().strip() == email_lower:
                return self._parse_employee_record(record)
        
        return None
    
    async def get_employee_by_id(self, employee_id: str) -> RagicEmployeeData | None:
        """
        Get employee by their door access ID.
        
        Args:
            employee_id: Door access ID to look up.
        
        Returns:
            RagicEmployeeData if found, None otherwise.
        """
        employees = await self.get_all_employees()
        
        for record in employees:
            door_id = self._get_field_value(
                record,
                self._field_config.door_access_id,
                self._field_config.door_access_names,
            )
            
            if door_id and door_id.strip() == employee_id.strip():
                return self._parse_employee_record(record)
        
        return None
    
    def _parse_employee_record(self, record: dict[str, Any]) -> RagicEmployeeData:
        """Parse a raw Ragic record into RagicEmployeeData."""
        email = self._get_field_value(
            record,
            self._field_config.email_id,
            self._field_config.email_names,
        ) or ""
        
        name = self._get_field_value(
            record,
            self._field_config.name_id,
            self._field_config.name_names,
        ) or "Unknown"
        
        door_access_id = self._get_field_value(
            record,
            self._field_config.door_access_id,
            self._field_config.door_access_names,
        )
        
        # Use door access ID if available, otherwise use Ragic record ID
        employee_id = door_access_id or str(record.get("_ragic_id", ""))
        
        return RagicEmployeeData(
            employee_id=employee_id,
            email=email,
            name=name,
            is_active=True,
            raw_data=record,
        )


# Singleton instance
_ragic_service: RagicService | None = None


def get_ragic_service() -> RagicService:
    """Get singleton instance of RagicService."""
    global _ragic_service
    if _ragic_service is None:
        _ragic_service = RagicService()
    return _ragic_service
