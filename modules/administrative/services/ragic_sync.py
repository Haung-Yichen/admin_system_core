"""
Ragic Sync Legacy Support Module.

This module contains Pydantic schemas for data validation that are used by
other parts of the Administrative module. The actual sync services have been
refactored into separate files following the Core BaseRagicSyncService pattern:

- AccountSyncService: modules/administrative/services/account_sync.py
- LeaveTypeSyncService: modules/administrative/services/leave_type_sync.py

DEPRECATED:
    The RagicSyncService class in this file is deprecated.
    New code should use AccountSyncService and LeaveTypeSyncService directly,
    or through the Core SyncManager.
"""

import logging
import warnings
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Schemas for Data Validation (Kept for Backward Compatibility)
# =============================================================================


class AccountRecordSchema(BaseModel):
    """
    Pydantic schema for validating Ragic Account records before DB insertion.
    
    Handles:
        - Type coercion (string to date, int, float, bool)
        - Empty string to None conversion
        - Date parsing (YYYY-MM-DD format)
        - Boolean conversion (0/1 to False/True)
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        coerce_numbers_to_str=False,
    )
    
    # === Primary Identification ===
    ragic_id: int
    account_id: str
    id_card_number: Optional[str] = None
    employee_id: Optional[str] = None
    
    # === Status & Basic Info ===
    status: bool = True
    name: str
    gender: Optional[str] = None
    birthday: Optional[date] = None
    education: Optional[str] = None
    
    # === Contact Info ===
    emails: Optional[str] = None
    phones: Optional[str] = None
    mobiles: Optional[str] = None
    
    # === Organization Info ===
    org_code: Optional[str] = None
    org_name: Optional[str] = None
    org_path: Optional[str] = None
    rank_code: Optional[str] = None
    rank_name: Optional[str] = None
    sales_dept: Optional[str] = None
    sales_dept_manager: Optional[str] = None
    
    # === Referrer & Mentor ===
    referrer_id_card: Optional[str] = None
    referrer_name: Optional[str] = None
    mentor_id_card: Optional[str] = None
    mentor_name: Optional[str] = None
    successor_name: Optional[str] = None
    successor_id_card: Optional[str] = None
    
    # === Employment Dates ===
    approval_date: Optional[date] = None
    effective_date: Optional[date] = None
    resignation_date: Optional[date] = None
    death_date: Optional[date] = None
    created_date: Optional[date] = None
    
    # === Rate & Financial ===
    assessment_rate: Optional[float] = None
    court_withholding_rate: Optional[float] = None
    court_min_living_expense: Optional[float] = None
    prior_commission_debt: Optional[float] = None
    prior_debt: Optional[float] = None
    
    # === Bank Info ===
    bank_name: Optional[str] = None
    bank_branch_code: Optional[str] = None
    bank_account: Optional[str] = None
    edi_format: Optional[int] = None
    
    # === Address - Household Registration ===
    household_postal_code: Optional[str] = None
    household_city: Optional[str] = None
    household_district: Optional[str] = None
    household_address: Optional[str] = None
    
    # === Address - Mailing ===
    mailing_postal_code: Optional[str] = None
    mailing_city: Optional[str] = None
    mailing_district: Optional[str] = None
    mailing_address: Optional[str] = None
    
    # === Emergency Contact ===
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    
    # === Life Insurance License ===
    life_license_number: Optional[str] = None
    life_first_registration_date: Optional[date] = None
    life_registration_date: Optional[date] = None
    life_exam_number: Optional[str] = None
    life_cancellation_date: Optional[date] = None
    life_license_expiry: Optional[str] = None
    
    # === Property Insurance License ===
    property_license_number: Optional[str] = None
    property_registration_date: Optional[date] = None
    property_exam_number: Optional[str] = None
    property_cancellation_date: Optional[date] = None
    property_license_expiry: Optional[str] = None
    property_standard_date: Optional[date] = None
    
    # === Accident & Health Insurance License ===
    ah_license_number: Optional[str] = None
    ah_registration_date: Optional[date] = None
    ah_cancellation_date: Optional[date] = None
    ah_license_expiry: Optional[str] = None
    
    # === Investment-linked Insurance ===
    investment_registration_date: Optional[date] = None
    investment_exam_number: Optional[str] = None
    
    # === Foreign Currency Insurance ===
    foreign_currency_registration_date: Optional[date] = None
    foreign_currency_exam_number: Optional[str] = None
    
    # === Qualifications ===
    fund_qualification_date: Optional[date] = None
    traditional_annuity_qualification: Optional[bool] = None
    variable_annuity_qualification: Optional[bool] = None
    structured_bond_qualification: Optional[bool] = None
    mobile_insurance_exam_date: Optional[date] = None
    preferred_insurance_exam_date: Optional[date] = None
    app_enabled: Optional[bool] = None
    
    # === Training Completion Dates ===
    senior_training_date: Optional[date] = None
    foreign_currency_training_date: Optional[date] = None
    fair_treatment_training_date: Optional[date] = None
    profit_sharing_training_date: Optional[date] = None
    
    # === Office Info ===
    office: Optional[str] = None
    office_tax_id: Optional[str] = None
    submission_unit: Optional[str] = None
    
    # === Health Insurance Withholding ===
    nhi_withholding_status: Optional[int] = None
    nhi_withholding_update_date: Optional[date] = None
    
    # === Miscellaneous ===
    remarks: Optional[str] = None
    notes: Optional[str] = None
    account_attributes: Optional[str] = None
    last_modified: Optional[datetime] = None


# =============================================================================
# Data Transformation Helpers (Kept for Backward Compatibility)
# =============================================================================


def parse_date(value: Any) -> Optional[date]:
    """
    Parse a date value from Ragic (YYYY/MM/DD or YYYY-MM-DD format).
    
    DEPRECATED: Use the internal helpers in account_sync.py or leave_type_sync.py.
    """
    if not value or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        # Handle multi-value dates (e.g., "2025-02-12, 2025-12-01") - take first
        if ", " in value:
            value = value.split(", ")[0].strip()
        # Try different date formats
        for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        logger.debug(f"Could not parse date: {value}")
        return None
    return None


def parse_datetime(value: Any) -> Optional[datetime]:
    """
    Parse a datetime value from Ragic (YYYY/MM/DD HH:ii:ss or YYYY-MM-DD HH:ii:ss format).
    
    DEPRECATED: Use the internal helpers in account_sync.py or leave_type_sync.py.
    """
    if not value or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        # Try different datetime formats
        for fmt in [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        logger.debug(f"Could not parse datetime: {value}")
        return None
    return None


def parse_bool(value: Any) -> Optional[bool]:
    """
    Parse a boolean value from Ragic (0/1 format).
    
    DEPRECATED: Use the internal helpers in account_sync.py or leave_type_sync.py.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return value in ("1", "true", "True", "TRUE", "是")
    return None


def parse_float(value: Any) -> Optional[float]:
    """
    Parse a float value from Ragic.
    
    DEPRECATED: Use the internal helpers in account_sync.py or leave_type_sync.py.
    """
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


def parse_int(value: Any) -> Optional[int]:
    """
    Parse an integer value from Ragic.
    
    DEPRECATED: Use the internal helpers in account_sync.py or leave_type_sync.py.
    """
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


def parse_string(value: Any) -> Optional[str]:
    """
    Parse a string value, converting empty to None.
    
    DEPRECATED: Use the internal helpers in account_sync.py or leave_type_sync.py.
    """
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return str(value).strip() or None


def transform_ragic_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Transform a raw Ragic record into a format suitable for Pydantic validation.
    
    DEPRECATED: This function is kept for backward compatibility only.
    New code should use AccountSyncService.map_record_to_dict() directly.
    
    Args:
        record: Raw record from Ragic API with field ID keys.
        
    Returns:
        dict with model field names as keys and properly typed values.
    """
    warnings.warn(
        "transform_ragic_record() is deprecated. "
        "Use AccountSyncService.map_record_to_dict() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    
    # Import here to avoid circular imports
    from modules.administrative.services.account_sync import AccountFieldMapping as Fields
    from modules.administrative.services.account_sync import (
        _parse_date,
        _parse_datetime,
        _parse_bool,
        _parse_float,
        _parse_int,
        _parse_string,
        _get_ragic_id,
    )
    
    return {
        # === Primary Identification ===
        "ragic_id": _get_ragic_id(record),
        "account_id": _parse_string(record.get(Fields.ACCOUNT_ID())) or "",
        "id_card_number": _parse_string(record.get(Fields.ID_CARD_NUMBER())),
        "employee_id": _parse_string(record.get(Fields.EMPLOYEE_ID())),
        
        # === Status & Basic Info ===
        "status": _parse_bool(record.get(Fields.STATUS())) if record.get(Fields.STATUS()) != "" else True,
        "name": _parse_string(record.get(Fields.NAME())) or "Unknown",
        "gender": _parse_string(record.get(Fields.GENDER())),
        "birthday": _parse_date(record.get(Fields.BIRTHDAY())),
        "education": _parse_string(record.get(Fields.EDUCATION())),
        
        # === Contact Info ===
        "emails": _parse_string(record.get(Fields.EMAILS())),
        "phones": _parse_string(record.get(Fields.PHONES())),
        "mobiles": _parse_string(record.get(Fields.MOBILES())),
        
        # === Organization Info ===
        "org_code": _parse_string(record.get(Fields.ORG_CODE())),
        "org_name": _parse_string(record.get(Fields.ORG_NAME())),
        "org_path": _parse_string(record.get(Fields.ORG_PATH())),
        "rank_code": _parse_string(record.get(Fields.RANK_CODE())),
        "rank_name": _parse_string(record.get(Fields.RANK_NAME())),
        "sales_dept": _parse_string(record.get(Fields.SALES_DEPT())),
        "sales_dept_manager": _parse_string(record.get(Fields.SALES_DEPT_MANAGER())),
        
        # === Referrer & Mentor ===
        "referrer_id_card": _parse_string(record.get(Fields.REFERRER_ID_CARD())),
        "referrer_name": _parse_string(record.get(Fields.REFERRER_NAME())),
        "mentor_id_card": _parse_string(record.get(Fields.MENTOR_ID_CARD())),
        "mentor_name": _parse_string(record.get(Fields.MENTOR_NAME())),
        "successor_name": _parse_string(record.get(Fields.SUCCESSOR_NAME())),
        "successor_id_card": _parse_string(record.get(Fields.SUCCESSOR_ID_CARD())),
        
        # === Employment Dates ===
        "approval_date": _parse_date(record.get(Fields.APPROVAL_DATE())),
        "effective_date": _parse_date(record.get(Fields.EFFECTIVE_DATE())),
        "resignation_date": _parse_date(record.get(Fields.RESIGNATION_DATE())),
        "death_date": _parse_date(record.get(Fields.DEATH_DATE())),
        "created_date": _parse_date(record.get(Fields.CREATED_DATE())),
        
        # === Rate & Financial ===
        "assessment_rate": _parse_float(record.get(Fields.ASSESSMENT_RATE())),
        "court_withholding_rate": _parse_float(record.get(Fields.COURT_WITHHOLDING_RATE())),
        "court_min_living_expense": _parse_float(record.get(Fields.COURT_MIN_LIVING_EXPENSE())),
        "prior_commission_debt": _parse_float(record.get(Fields.PRIOR_COMMISSION_DEBT())),
        "prior_debt": _parse_float(record.get(Fields.PRIOR_DEBT())),
        
        # === Bank Info ===
        "bank_name": _parse_string(record.get(Fields.BANK_NAME())),
        "bank_branch_code": _parse_string(record.get(Fields.BANK_BRANCH_CODE())),
        "bank_account": _parse_string(record.get(Fields.BANK_ACCOUNT())),
        "edi_format": _parse_int(record.get(Fields.EDI_FORMAT())),
        
        # === Address - Household Registration ===
        "household_postal_code": _parse_string(record.get(Fields.HOUSEHOLD_POSTAL_CODE())),
        "household_city": _parse_string(record.get(Fields.HOUSEHOLD_CITY())),
        "household_district": _parse_string(record.get(Fields.HOUSEHOLD_DISTRICT())),
        "household_address": _parse_string(record.get(Fields.HOUSEHOLD_ADDRESS())),
        
        # === Address - Mailing ===
        "mailing_postal_code": _parse_string(record.get(Fields.MAILING_POSTAL_CODE())),
        "mailing_city": _parse_string(record.get(Fields.MAILING_CITY())),
        "mailing_district": _parse_string(record.get(Fields.MAILING_DISTRICT())),
        "mailing_address": _parse_string(record.get(Fields.MAILING_ADDRESS())),
        
        # === Emergency Contact ===
        "emergency_contact": _parse_string(record.get(Fields.EMERGENCY_CONTACT())),
        "emergency_phone": _parse_string(record.get(Fields.EMERGENCY_PHONE())),
        
        # === Life Insurance License ===
        "life_license_number": _parse_string(record.get(Fields.LIFE_LICENSE_NUMBER())),
        "life_first_registration_date": _parse_date(record.get(Fields.LIFE_FIRST_REGISTRATION_DATE())),
        "life_registration_date": _parse_date(record.get(Fields.LIFE_REGISTRATION_DATE())),
        "life_exam_number": _parse_string(record.get(Fields.LIFE_EXAM_NUMBER())),
        "life_cancellation_date": _parse_date(record.get(Fields.LIFE_CANCELLATION_DATE())),
        "life_license_expiry": _parse_string(record.get(Fields.LIFE_LICENSE_EXPIRY())),
        
        # === Property Insurance License ===
        "property_license_number": _parse_string(record.get(Fields.PROPERTY_LICENSE_NUMBER())),
        "property_registration_date": _parse_date(record.get(Fields.PROPERTY_REGISTRATION_DATE())),
        "property_exam_number": _parse_string(record.get(Fields.PROPERTY_EXAM_NUMBER())),
        "property_cancellation_date": _parse_date(record.get(Fields.PROPERTY_CANCELLATION_DATE())),
        "property_license_expiry": _parse_string(record.get(Fields.PROPERTY_LICENSE_EXPIRY())),
        "property_standard_date": _parse_date(record.get(Fields.PROPERTY_STANDARD_DATE())),
        
        # === Accident & Health Insurance License ===
        "ah_license_number": _parse_string(record.get(Fields.AH_LICENSE_NUMBER())),
        "ah_registration_date": _parse_date(record.get(Fields.AH_REGISTRATION_DATE())),
        "ah_cancellation_date": _parse_date(record.get(Fields.AH_CANCELLATION_DATE())),
        "ah_license_expiry": _parse_string(record.get(Fields.AH_LICENSE_EXPIRY())),
        
        # === Investment-linked Insurance ===
        "investment_registration_date": _parse_date(record.get(Fields.INVESTMENT_REGISTRATION_DATE())),
        "investment_exam_number": _parse_string(record.get(Fields.INVESTMENT_EXAM_NUMBER())),
        
        # === Foreign Currency Insurance ===
        "foreign_currency_registration_date": _parse_date(record.get(Fields.FOREIGN_CURRENCY_REGISTRATION_DATE())),
        "foreign_currency_exam_number": _parse_string(record.get(Fields.FOREIGN_CURRENCY_EXAM_NUMBER())),
        
        # === Qualifications ===
        "fund_qualification_date": _parse_date(record.get(Fields.FUND_QUALIFICATION_DATE())),
        "traditional_annuity_qualification": _parse_bool(record.get(Fields.TRADITIONAL_ANNUITY_QUALIFICATION())),
        "variable_annuity_qualification": _parse_bool(record.get(Fields.VARIABLE_ANNUITY_QUALIFICATION())),
        "structured_bond_qualification": _parse_bool(record.get(Fields.STRUCTURED_BOND_QUALIFICATION())),
        "mobile_insurance_exam_date": _parse_date(record.get(Fields.MOBILE_INSURANCE_EXAM_DATE())),
        "preferred_insurance_exam_date": _parse_date(record.get(Fields.PREFERRED_INSURANCE_EXAM_DATE())),
        "app_enabled": _parse_bool(record.get(Fields.APP_ENABLED())),
        
        # === Training Completion Dates ===
        "senior_training_date": _parse_date(record.get(Fields.SENIOR_TRAINING_DATE())),
        "foreign_currency_training_date": _parse_date(record.get(Fields.FOREIGN_CURRENCY_TRAINING_DATE())),
        "fair_treatment_training_date": _parse_date(record.get(Fields.FAIR_TREATMENT_TRAINING_DATE())),
        "profit_sharing_training_date": _parse_date(record.get(Fields.PROFIT_SHARING_TRAINING_DATE())),
        
        # === Office Info ===
        "office": _parse_string(record.get(Fields.OFFICE())),
        "office_tax_id": _parse_string(record.get(Fields.OFFICE_TAX_ID())),
        "submission_unit": _parse_string(record.get(Fields.SUBMISSION_UNIT())),
        
        # === Health Insurance Withholding ===
        "nhi_withholding_status": _parse_int(record.get(Fields.NHI_WITHHOLDING_STATUS())),
        "nhi_withholding_update_date": _parse_date(record.get(Fields.NHI_WITHHOLDING_UPDATE_DATE())),
        
        # === Miscellaneous ===
        "remarks": _parse_string(record.get(Fields.REMARKS())),
        "notes": _parse_string(record.get(Fields.NOTES())),
        "account_attributes": _parse_string(record.get(Fields.ACCOUNT_ATTRIBUTES())),
        "last_modified": _parse_datetime(record.get(Fields.LAST_MODIFIED())),
    }


# =============================================================================
# DEPRECATED: Legacy Sync Service Wrapper
# =============================================================================


class RagicSyncService:
    """
    DEPRECATED: Legacy sync service for backward compatibility.
    
    This class is deprecated and will be removed in a future version.
    Use the following instead:
    
    - For Account sync: AccountSyncService (modules/administrative/services/account_sync.py)
    - For Leave Type sync: LeaveTypeSyncService (modules/administrative/services/leave_type_sync.py)
    - For centralized sync: core.ragic.get_sync_manager()
    
    Example migration:
        # Old way (deprecated):
        sync_service = RagicSyncService()
        await sync_service.sync_all_data()
        
        # New way:
        from core.ragic import get_sync_manager
        sync_manager = get_sync_manager()
        await sync_manager.sync_all()
        
        # Or sync specific services:
        from modules.administrative.services.account_sync import get_account_sync_service
        account_service = get_account_sync_service()
        result = await account_service.sync_all_data()
    """

    def __init__(self) -> None:
        warnings.warn(
            "RagicSyncService is deprecated. "
            "Use AccountSyncService and LeaveTypeSyncService instead, "
            "or use core.ragic.get_sync_manager() for centralized sync.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Lazy import to avoid circular dependencies
        from modules.administrative.services.account_sync import get_account_sync_service
        from modules.administrative.services.leave_type_sync import get_leave_type_sync_service
        
        self._account_service = get_account_sync_service()
        self._leave_type_service = get_leave_type_sync_service()

    async def close(self) -> None:
        """Close all underlying services."""
        await self._account_service.close()
        await self._leave_type_service.close()

    async def sync_all_data(self) -> dict[str, Any]:
        """
        Perform full synchronization from Ragic to local cache.
        
        DEPRECATED: Use AccountSyncService and LeaveTypeSyncService directly.
        
        Returns:
            dict with sync results for backward compatibility.
        """
        warnings.warn(
            "RagicSyncService.sync_all_data() is deprecated. "
            "Use AccountSyncService.sync_all_data() and "
            "LeaveTypeSyncService.sync_all_data() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        
        result = {
            "schema_issues": [],
            "accounts_synced": 0,
            "accounts_skipped": 0,
            "leave_types_synced": 0,
            "leave_types_skipped": 0,
        }

        try:
            # Sync accounts
            account_result = await self._account_service.sync_all_data()
            result["accounts_synced"] = account_result.synced
            result["accounts_skipped"] = account_result.skipped
            if account_result.error_messages:
                result["schema_issues"].extend(account_result.error_messages)

            # Sync leave types
            leave_type_result = await self._leave_type_service.sync_all_data()
            result["leave_types_synced"] = leave_type_result.synced
            result["leave_types_skipped"] = leave_type_result.skipped
            if leave_type_result.error_messages:
                result["schema_issues"].extend(leave_type_result.error_messages)

            logger.info(
                f"Legacy sync completed: "
                f"{result['accounts_synced']} accounts, "
                f"{result['leave_types_synced']} leave types"
            )

        except Exception as e:
            logger.exception(f"Legacy sync failed: {e}")
            raise

        return result

    async def sync_leave_types(self) -> dict[str, Any]:
        """
        Synchronize leave type data from Ragic to local cache.
        
        DEPRECATED: Use LeaveTypeSyncService.sync_all_data() directly.
        
        Returns:
            dict with sync results for backward compatibility.
        """
        warnings.warn(
            "RagicSyncService.sync_leave_types() is deprecated. "
            "Use LeaveTypeSyncService.sync_all_data() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        
        sync_result = await self._leave_type_service.sync_all_data()
        
        return {
            "leave_types_synced": sync_result.synced,
            "leave_types_skipped": sync_result.skipped,
        }
