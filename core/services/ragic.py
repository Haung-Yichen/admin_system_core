"""
Core Ragic Service (Legacy Compatibility Layer).

This module now wraps the unified core/ragic package.
For new code, prefer using core.ragic directly:

    from core.ragic import RagicService, RagicRepository, RagicModel, RagicField

This file is kept for backward compatibility with existing code that imports:
    from core.services.ragic import RagicService, get_ragic_service

IMPORTANT: Employee lookup methods (verify_email_exists, get_employee_by_id)
now use the local database cache (administrative_accounts table) instead of
hitting the Ragic API directly. This improves performance and consistency.
The cache is synced from Ragic on application startup by RagicSyncService.
"""

import logging
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.app_context import ConfigLoader
from core.database.session import get_standalone_session
from core.schemas.auth import RagicEmployeeData

# Re-export from new location for compatibility
from core.ragic.service import RagicService as BaseRagicService
from core.ragic.service import get_ragic_service as _get_ragic_service_base

logger = logging.getLogger(__name__)


class RagicFieldConfig:
    """Configuration for Ragic field mapping (unified Account table)."""
    
    def __init__(self, config: dict[str, Any]) -> None:
        ragic_config = config.get("ragic", {})
        
        # Field IDs from config (unified Account table /HSIBAdmSys/ychn-test/11)
        self.email_id = ragic_config.get("field_email", "1005977")  # EMAILS (多值，逗號分隔)
        self.name_id = ragic_config.get("field_name", "1005975")  # NAME
        self.door_access_id = ragic_config.get("field_door_access_id", "1005983")  # EMPLOYEE_ID
        
        # Chinese name mappings for fuzzy matching
        self.email_names = ["E-mail", "電子郵件", "email", "Email", "郵件", "E-Mail"]
        self.name_names = ["申請人", "姓名", "name", "Name", "員工姓名"]
        self.door_access_names = ["員工編號", "employee_id", "EmployeeId", "門禁編號"]


class RagicService(BaseRagicService):
    """
    Employee verification service (extends unified RagicService).
    
    This class adds employee-specific methods on top of the base CRUD service.
    Uses fuzzy field name matching to handle Chinese field names.
    """
    
    def __init__(self) -> None:
        # Initialize base service
        super().__init__()
        
        # Load additional config for employee verification
        self._config_loader = ConfigLoader()
        self._config_loader.load()
        
        ragic_config = self._config_loader.get("ragic", {})
        self._sheet_path = ragic_config.get("employee_sheet_path", "/HSIBAdmSys/ychn-test/11")
        
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
        Fetch all employee records from local database cache.
        
        Returns:
            List of employee records as dictionaries.
        """
        # Import here to avoid circular imports
        from modules.administrative.models.account import AdministrativeAccount
        
        async with get_standalone_session() as session:
            result = await session.execute(
                select(AdministrativeAccount).where(
                    AdministrativeAccount.status == True
                )
            )
            accounts = result.scalars().all()
            
            # Convert to dict format for compatibility
            return [
                {
                    "ragic_id": acc.ragic_id,
                    "account_id": acc.account_id,
                    "name": acc.name,
                    "emails": acc.emails,
                    "employee_id": acc.employee_id,
                    "status": acc.status,
                }
                for acc in accounts
            ]
    
    async def verify_email_exists(self, email: str) -> RagicEmployeeData | None:
        """
        Verify if an email exists in the local database cache.
        
        Uses administrative_accounts table which is synced from Ragic.
        Supports multi-value email field (comma-separated).
        
        Args:
            email: Email address to verify.
        
        Returns:
            RagicEmployeeData if found, None otherwise.
        """
        # Import here to avoid circular imports
        from modules.administrative.models.account import AdministrativeAccount
        
        email_lower = email.lower().strip()
        logger.debug(f"Looking up email in local DB: {email_lower}")
        
        async with get_standalone_session() as session:
            # Get all active accounts (we need to check multi-value emails)
            result = await session.execute(
                select(AdministrativeAccount).where(
                    AdministrativeAccount.status == True
                )
            )
            accounts = result.scalars().all()
            
            for account in accounts:
                if account.emails:
                    # Support multi-value email field (comma-separated)
                    emails_in_record = [
                        e.lower().strip() 
                        for e in account.emails.split(",")
                    ]
                    if email_lower in emails_in_record:
                        logger.info(f"Email found in local DB: {email} -> {account.name}")
                        return self._account_to_employee_data(account)
            
            logger.warning(f"Email not found in local DB: {email}")
            return None
    
    async def get_employee_by_id(self, employee_id: str) -> RagicEmployeeData | None:
        """
        Get employee by their employee ID from local database cache.
        
        Args:
            employee_id: Employee ID to look up.
        
        Returns:
            RagicEmployeeData if found, None otherwise.
        """
        # Import here to avoid circular imports
        from modules.administrative.models.account import AdministrativeAccount
        
        async with get_standalone_session() as session:
            result = await session.execute(
                select(AdministrativeAccount).where(
                    AdministrativeAccount.employee_id == employee_id.strip(),
                    AdministrativeAccount.status == True
                )
            )
            account = result.scalar_one_or_none()
            
            if account:
                return self._account_to_employee_data(account)
            
            return None
    
    def _account_to_employee_data(self, account: Any) -> RagicEmployeeData:
        """Convert AdministrativeAccount to RagicEmployeeData."""
        # Handle multi-value email - use the first one
        email = ""
        if account.emails:
            email = account.emails.split(",")[0].strip()
        
        return RagicEmployeeData(
            employee_id=account.employee_id or str(account.ragic_id),
            email=email,
            name=account.name,
            is_active=account.status,
            raw_data={
                "ragic_id": account.ragic_id,
                "account_id": account.account_id,
                "name": account.name,
                "emails": account.emails,
            },
        )


# Singleton instance
_ragic_service: RagicService | None = None


def get_ragic_service() -> RagicService:
    """Get singleton instance of RagicService."""
    global _ragic_service
    if _ragic_service is None:
        _ragic_service = RagicService()
    return _ragic_service
