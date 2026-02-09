"""
Employee Verification Service.

Provides employee verification against the local database cache.
The cache is synced from Ragic by AccountSyncService on application startup.

NOTE: This service does NOT make direct Ragic API calls.
All lookups are against the local administrative_accounts table.
"""

import logging
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import select

from core.database.session import get_standalone_session
from core.schemas.auth import RagicEmployeeData

logger = logging.getLogger(__name__)


class RagicFieldConfig:
    """Configuration for Ragic field mapping (unified Account table).
    
    Loads field IDs from ragic_registry.json via the backward-compatible shim.
    """
    
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        # Import here to avoid circular imports at module load time
        from core.ragic.columns import get_account_form
        
        account = get_account_form()
        
        # Field IDs from centralized config
        self.email_id = account.field("EMAILS")
        self.name_id = account.field("NAME")
        self.door_access_id = account.field("EMPLOYEE_ID")
        
        # Chinese name mappings for fuzzy matching
        self.email_names = ["E-mail", "電子郵件", "email", "Email", "郵件", "E-Mail"]
        self.name_names = ["申請人", "姓名", "name", "Name", "員工姓名"]
        self.door_access_names = ["員工編號", "employee_id", "EmployeeId", "門禁編號"]


class EmployeeVerificationService:
    """
    Employee verification service using local database cache.
    
    Uses the administrative_accounts table which is synced from Ragic
    on application startup by AccountSyncService.
    """
    
    def __init__(self) -> None:
        self._field_config = RagicFieldConfig()
    
    @staticmethod
    def _fuzzy_match(s1: str, s2: str, threshold: float = 0.8) -> bool:
        """Check if two strings match with fuzzy threshold."""
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio() >= threshold
    
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


# Alias for backward compatibility
RagicService = EmployeeVerificationService

# Singleton instance
_verification_service: EmployeeVerificationService | None = None


def get_employee_verification_service() -> EmployeeVerificationService:
    """Get singleton EmployeeVerificationService instance."""
    global _verification_service
    if _verification_service is None:
        _verification_service = EmployeeVerificationService()
    return _verification_service
