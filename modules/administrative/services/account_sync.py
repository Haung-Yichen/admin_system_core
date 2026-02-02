"""
Account Sync Service.

Handles synchronization of Employee Account data from Ragic to local database.
Refactored to use the Core BaseRagicSyncService with RagicRegistry.
"""

import logging
from datetime import date, datetime
from typing import Any, Dict, Optional

from core.ragic.registry import get_ragic_registry
from core.ragic.sync_base import BaseRagicSyncService
from modules.administrative.models import AdministrativeAccount

logger = logging.getLogger(__name__)


# =============================================================================
# Field Mapping from RagicRegistry
# =============================================================================


class AccountFieldMapping:
    """
    Account form field ID mapping - uses RagicRegistry.
    
    Provides a clean interface to access field IDs from the central registry.
    All field IDs are loaded from ragic_registry.json at runtime.
    """
    
    _form_key = "account_form"

    @classmethod
    def _get_field(cls, name: str, default: str = "") -> str:
        """
        Get a field ID from the registry.
        
        Args:
            name: The logical field name (e.g., "ACCOUNT_ID").
            default: Default value if field not found.
            
        Returns:
            The Ragic field ID.
        """
        try:
            return get_ragic_registry().get_field_id(cls._form_key, name)
        except Exception:
            logger.warning(f"Field '{name}' not found in registry for form '{cls._form_key}'")
            return default

    # === Primary Identification ===
    @classmethod
    def RAGIC_ID(cls) -> str:
        return cls._get_field("RAGIC_ID")

    @classmethod
    def ACCOUNT_ID(cls) -> str:
        return cls._get_field("ACCOUNT_ID")

    @classmethod
    def ID_CARD_NUMBER(cls) -> str:
        return cls._get_field("ID_CARD_NUMBER")

    @classmethod
    def EMPLOYEE_ID(cls) -> str:
        return cls._get_field("EMPLOYEE_ID")

    # === Status & Basic Info ===
    @classmethod
    def STATUS(cls) -> str:
        return cls._get_field("STATUS")

    @classmethod
    def NAME(cls) -> str:
        return cls._get_field("NAME")

    @classmethod
    def GENDER(cls) -> str:
        return cls._get_field("GENDER")

    @classmethod
    def BIRTHDAY(cls) -> str:
        return cls._get_field("BIRTHDAY")

    @classmethod
    def EDUCATION(cls) -> str:
        return cls._get_field("EDUCATION")

    # === Contact Info ===
    @classmethod
    def EMAILS(cls) -> str:
        return cls._get_field("EMAILS")

    @classmethod
    def PHONES(cls) -> str:
        return cls._get_field("PHONES")

    @classmethod
    def MOBILES(cls) -> str:
        return cls._get_field("MOBILES")

    # === Organization Info ===
    @classmethod
    def ORG_CODE(cls) -> str:
        return cls._get_field("ORG_CODE")

    @classmethod
    def ORG_NAME(cls) -> str:
        return cls._get_field("ORG_NAME")

    @classmethod
    def ORG_PATH(cls) -> str:
        return cls._get_field("ORG_PATH")

    @classmethod
    def RANK_CODE(cls) -> str:
        return cls._get_field("RANK_CODE")

    @classmethod
    def RANK_NAME(cls) -> str:
        return cls._get_field("RANK_NAME")

    @classmethod
    def SALES_DEPT(cls) -> str:
        return cls._get_field("SALES_DEPT")

    @classmethod
    def SALES_DEPT_MANAGER(cls) -> str:
        return cls._get_field("SALES_DEPT_MANAGER")

    # === Referrer & Mentor ===
    @classmethod
    def REFERRER_ID_CARD(cls) -> str:
        return cls._get_field("REFERRER_ID_CARD")

    @classmethod
    def REFERRER_NAME(cls) -> str:
        return cls._get_field("REFERRER_NAME")

    @classmethod
    def MENTOR_ID_CARD(cls) -> str:
        return cls._get_field("MENTOR_ID_CARD")

    @classmethod
    def MENTOR_NAME(cls) -> str:
        return cls._get_field("MENTOR_NAME")

    @classmethod
    def SUCCESSOR_NAME(cls) -> str:
        return cls._get_field("SUCCESSOR_NAME")

    @classmethod
    def SUCCESSOR_ID_CARD(cls) -> str:
        return cls._get_field("SUCCESSOR_ID_CARD")

    # === Employment Dates ===
    @classmethod
    def APPROVAL_DATE(cls) -> str:
        return cls._get_field("APPROVAL_DATE")

    @classmethod
    def EFFECTIVE_DATE(cls) -> str:
        return cls._get_field("EFFECTIVE_DATE")

    @classmethod
    def RESIGNATION_DATE(cls) -> str:
        return cls._get_field("RESIGNATION_DATE")

    @classmethod
    def DEATH_DATE(cls) -> str:
        return cls._get_field("DEATH_DATE")

    @classmethod
    def CREATED_DATE(cls) -> str:
        return cls._get_field("CREATED_DATE")

    # === Rate & Financial ===
    @classmethod
    def ASSESSMENT_RATE(cls) -> str:
        return cls._get_field("ASSESSMENT_RATE")

    @classmethod
    def COURT_WITHHOLDING_RATE(cls) -> str:
        return cls._get_field("COURT_WITHHOLDING_RATE")

    @classmethod
    def COURT_MIN_LIVING_EXPENSE(cls) -> str:
        return cls._get_field("COURT_MIN_LIVING_EXPENSE")

    @classmethod
    def PRIOR_COMMISSION_DEBT(cls) -> str:
        return cls._get_field("PRIOR_COMMISSION_DEBT")

    @classmethod
    def PRIOR_DEBT(cls) -> str:
        return cls._get_field("PRIOR_DEBT")

    # === Bank Info ===
    @classmethod
    def BANK_NAME(cls) -> str:
        return cls._get_field("BANK_NAME")

    @classmethod
    def BANK_BRANCH_CODE(cls) -> str:
        return cls._get_field("BANK_BRANCH_CODE")

    @classmethod
    def BANK_ACCOUNT(cls) -> str:
        return cls._get_field("BANK_ACCOUNT")

    @classmethod
    def EDI_FORMAT(cls) -> str:
        return cls._get_field("EDI_FORMAT")

    # === Address - Household Registration ===
    @classmethod
    def HOUSEHOLD_POSTAL_CODE(cls) -> str:
        return cls._get_field("HOUSEHOLD_POSTAL_CODE")

    @classmethod
    def HOUSEHOLD_CITY(cls) -> str:
        return cls._get_field("HOUSEHOLD_CITY")

    @classmethod
    def HOUSEHOLD_DISTRICT(cls) -> str:
        return cls._get_field("HOUSEHOLD_DISTRICT")

    @classmethod
    def HOUSEHOLD_ADDRESS(cls) -> str:
        return cls._get_field("HOUSEHOLD_ADDRESS")

    # === Address - Mailing ===
    @classmethod
    def MAILING_POSTAL_CODE(cls) -> str:
        return cls._get_field("MAILING_POSTAL_CODE")

    @classmethod
    def MAILING_CITY(cls) -> str:
        return cls._get_field("MAILING_CITY")

    @classmethod
    def MAILING_DISTRICT(cls) -> str:
        return cls._get_field("MAILING_DISTRICT")

    @classmethod
    def MAILING_ADDRESS(cls) -> str:
        return cls._get_field("MAILING_ADDRESS")

    # === Emergency Contact ===
    @classmethod
    def EMERGENCY_CONTACT(cls) -> str:
        return cls._get_field("EMERGENCY_CONTACT")

    @classmethod
    def EMERGENCY_PHONE(cls) -> str:
        return cls._get_field("EMERGENCY_PHONE")

    # === Life Insurance License ===
    @classmethod
    def LIFE_LICENSE_NUMBER(cls) -> str:
        return cls._get_field("LIFE_LICENSE_NUMBER")

    @classmethod
    def LIFE_FIRST_REGISTRATION_DATE(cls) -> str:
        return cls._get_field("LIFE_FIRST_REGISTRATION_DATE")

    @classmethod
    def LIFE_REGISTRATION_DATE(cls) -> str:
        return cls._get_field("LIFE_REGISTRATION_DATE")

    @classmethod
    def LIFE_EXAM_NUMBER(cls) -> str:
        return cls._get_field("LIFE_EXAM_NUMBER")

    @classmethod
    def LIFE_CANCELLATION_DATE(cls) -> str:
        return cls._get_field("LIFE_CANCELLATION_DATE")

    @classmethod
    def LIFE_LICENSE_EXPIRY(cls) -> str:
        return cls._get_field("LIFE_LICENSE_EXPIRY")

    # === Property Insurance License ===
    @classmethod
    def PROPERTY_LICENSE_NUMBER(cls) -> str:
        return cls._get_field("PROPERTY_LICENSE_NUMBER")

    @classmethod
    def PROPERTY_REGISTRATION_DATE(cls) -> str:
        return cls._get_field("PROPERTY_REGISTRATION_DATE")

    @classmethod
    def PROPERTY_EXAM_NUMBER(cls) -> str:
        return cls._get_field("PROPERTY_EXAM_NUMBER")

    @classmethod
    def PROPERTY_CANCELLATION_DATE(cls) -> str:
        return cls._get_field("PROPERTY_CANCELLATION_DATE")

    @classmethod
    def PROPERTY_LICENSE_EXPIRY(cls) -> str:
        return cls._get_field("PROPERTY_LICENSE_EXPIRY")

    @classmethod
    def PROPERTY_STANDARD_DATE(cls) -> str:
        return cls._get_field("PROPERTY_STANDARD_DATE")

    # === Accident & Health Insurance License ===
    @classmethod
    def AH_LICENSE_NUMBER(cls) -> str:
        return cls._get_field("AH_LICENSE_NUMBER")

    @classmethod
    def AH_REGISTRATION_DATE(cls) -> str:
        return cls._get_field("AH_REGISTRATION_DATE")

    @classmethod
    def AH_CANCELLATION_DATE(cls) -> str:
        return cls._get_field("AH_CANCELLATION_DATE")

    @classmethod
    def AH_LICENSE_EXPIRY(cls) -> str:
        return cls._get_field("AH_LICENSE_EXPIRY")

    # === Investment-linked Insurance ===
    @classmethod
    def INVESTMENT_REGISTRATION_DATE(cls) -> str:
        return cls._get_field("INVESTMENT_REGISTRATION_DATE")

    @classmethod
    def INVESTMENT_EXAM_NUMBER(cls) -> str:
        return cls._get_field("INVESTMENT_EXAM_NUMBER")

    # === Foreign Currency Insurance ===
    @classmethod
    def FOREIGN_CURRENCY_REGISTRATION_DATE(cls) -> str:
        return cls._get_field("FOREIGN_CURRENCY_REGISTRATION_DATE")

    @classmethod
    def FOREIGN_CURRENCY_EXAM_NUMBER(cls) -> str:
        return cls._get_field("FOREIGN_CURRENCY_EXAM_NUMBER")

    # === Qualifications ===
    @classmethod
    def FUND_QUALIFICATION_DATE(cls) -> str:
        return cls._get_field("FUND_QUALIFICATION_DATE")

    @classmethod
    def TRADITIONAL_ANNUITY_QUALIFICATION(cls) -> str:
        return cls._get_field("TRADITIONAL_ANNUITY_QUALIFICATION")

    @classmethod
    def VARIABLE_ANNUITY_QUALIFICATION(cls) -> str:
        return cls._get_field("VARIABLE_ANNUITY_QUALIFICATION")

    @classmethod
    def STRUCTURED_BOND_QUALIFICATION(cls) -> str:
        return cls._get_field("STRUCTURED_BOND_QUALIFICATION")

    @classmethod
    def MOBILE_INSURANCE_EXAM_DATE(cls) -> str:
        return cls._get_field("MOBILE_INSURANCE_EXAM_DATE")

    @classmethod
    def PREFERRED_INSURANCE_EXAM_DATE(cls) -> str:
        return cls._get_field("PREFERRED_INSURANCE_EXAM_DATE")

    @classmethod
    def APP_ENABLED(cls) -> str:
        return cls._get_field("APP_ENABLED")

    # === Training Completion Dates ===
    @classmethod
    def SENIOR_TRAINING_DATE(cls) -> str:
        return cls._get_field("SENIOR_TRAINING_DATE")

    @classmethod
    def FOREIGN_CURRENCY_TRAINING_DATE(cls) -> str:
        return cls._get_field("FOREIGN_CURRENCY_TRAINING_DATE")

    @classmethod
    def FAIR_TREATMENT_TRAINING_DATE(cls) -> str:
        return cls._get_field("FAIR_TREATMENT_TRAINING_DATE")

    @classmethod
    def PROFIT_SHARING_TRAINING_DATE(cls) -> str:
        return cls._get_field("PROFIT_SHARING_TRAINING_DATE")

    # === Office Info ===
    @classmethod
    def OFFICE(cls) -> str:
        return cls._get_field("OFFICE")

    @classmethod
    def OFFICE_TAX_ID(cls) -> str:
        return cls._get_field("OFFICE_TAX_ID")

    @classmethod
    def SUBMISSION_UNIT(cls) -> str:
        return cls._get_field("SUBMISSION_UNIT")

    # === Health Insurance Withholding ===
    @classmethod
    def NHI_WITHHOLDING_STATUS(cls) -> str:
        return cls._get_field("NHI_WITHHOLDING_STATUS")

    @classmethod
    def NHI_WITHHOLDING_UPDATE_DATE(cls) -> str:
        return cls._get_field("NHI_WITHHOLDING_UPDATE_DATE")

    # === Miscellaneous ===
    @classmethod
    def REMARKS(cls) -> str:
        return cls._get_field("REMARKS")

    @classmethod
    def NOTES(cls) -> str:
        return cls._get_field("NOTES")

    @classmethod
    def ACCOUNT_ATTRIBUTES(cls) -> str:
        return cls._get_field("ACCOUNT_ATTRIBUTES")

    @classmethod
    def LAST_MODIFIED(cls) -> str:
        return cls._get_field("LAST_MODIFIED")


# =============================================================================
# Data Transformation Helpers
# =============================================================================


def _parse_date(value: Any) -> Optional[date]:
    """Parse a date value from Ragic (YYYY/MM/DD or YYYY-MM-DD format)."""
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


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a datetime value from Ragic (YYYY/MM/DD HH:ii:ss or YYYY-MM-DD HH:ii:ss format)."""
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


def _parse_bool(value: Any) -> Optional[bool]:
    """Parse a boolean value from Ragic (0/1 format)."""
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


def _parse_string(value: Any) -> Optional[str]:
    """Parse a string value, converting empty to None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return str(value).strip() or None


def _get_ragic_id(record: Dict[str, Any]) -> Optional[int]:
    """
    Get Ragic ID from record.
    
    Args:
        record: Raw record from Ragic API.
        
    Returns:
        The Ragic ID as int, or None if not found.
    """
    ragic_id = _parse_int(record.get(AccountFieldMapping.RAGIC_ID()))
    if ragic_id is None:
        ragic_id = record.get("_ragicId")
    return ragic_id


# =============================================================================
# Sync Service
# =============================================================================


class AccountSyncService(BaseRagicSyncService[AdministrativeAccount]):
    """
    Account Sync Service implementation using Core Base Class.
    
    Uses RagicRegistry for configuration (form_key="account_form").
    This service handles synchronization of employee account data from
    Ragic to the local database.
    """

    def __init__(self) -> None:
        super().__init__(
            model_class=AdministrativeAccount,
            form_key="account_form",
        )

    async def map_record_to_dict(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map a Ragic account record to a dictionary suitable for AdministrativeAccount model.
        
        Args:
            record: Raw Ragic record with field IDs as keys.
            
        Returns:
            Dictionary with model field names, or None to skip this record.
        """
        try:
            # Get ragic_id
            ragic_id = _get_ragic_id(record)
            if ragic_id is None:
                logger.warning(f"Skipping record: missing ragic_id. Record keys: {list(record.keys())[:5]}")
                return None

            # Get required field: account_id
            account_id = _parse_string(record.get(AccountFieldMapping.ACCOUNT_ID()))
            if not account_id:
                logger.warning(
                    f"Skipping record: missing account_id. "
                    f"ragic_id={ragic_id}, name={record.get(AccountFieldMapping.NAME())}"
                )
                return None

            # Get required field: name
            name = _parse_string(record.get(AccountFieldMapping.NAME())) or "Unknown"

            # Build the complete mapping using AccountFieldMapping
            Fields = AccountFieldMapping

            return {
                # === Primary Identification ===
                "ragic_id": ragic_id,
                "account_id": account_id,
                "id_card_number": _parse_string(record.get(Fields.ID_CARD_NUMBER())),
                "employee_id": _parse_string(record.get(Fields.EMPLOYEE_ID())),
                
                # === Status & Basic Info ===
                "status": _parse_bool(record.get(Fields.STATUS())) if record.get(Fields.STATUS()) != "" else True,
                "name": name,
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

        except Exception as e:
            logger.error(f"Error mapping account record: {e}")
            return None


# =============================================================================
# Singleton Helper
# =============================================================================


_account_sync_service: Optional[AccountSyncService] = None


def get_account_sync_service() -> AccountSyncService:
    """
    Get the singleton AccountSyncService instance.
    
    Returns:
        AccountSyncService instance.
    """
    global _account_sync_service
    if _account_sync_service is None:
        _account_sync_service = AccountSyncService()
    return _account_sync_service
