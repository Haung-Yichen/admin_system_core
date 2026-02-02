"""
Administrative Module Configuration.

Manages environment variables specific to the Administrative module.
Uses prefix ADMIN_ to avoid conflicts with other modules.

Refactored to use RagicRegistry for all Ragic configuration lookups.

IMPORTANT: Field Mapping Migration
==================================
The field mapping classes in this file (RagicAccountFieldMapping, RagicLeaveFieldMapping, 
RagicLeaveTypeFieldMapping) are kept for backward compatibility but are now powered by 
RagicRegistry through a metaclass. They dynamically load field IDs from ragic_registry.json.

For new code, prefer using the field mapping helpers directly in sync services:
- AccountSyncService uses AccountFieldMapping (in account_sync.py)
- LeaveTypeSyncService uses LeaveTypeFieldMapping (in leave_type_sync.py)

These new helpers provide better encapsulation and don't depend on module-level config.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Import registry for Ragic configuration
from core.ragic.registry import get_ragic_registry


def _get_registry():
    """Lazy-load registry to avoid circular imports."""
    return get_ragic_registry()


class RagicFieldMappingMeta(type):
    """
    Metaclass for Ragic field mappings that allows attribute access
    to return field IDs directly from the registry.
    
    Usage:
        class MyFields(metaclass=RagicFieldMappingMeta):
            _form_key = "my_form"
            FIELD_NAME = "FIELD_NAME"  # Just declare the field name
        
        # Access returns the field ID from registry:
        field_id = MyFields.FIELD_NAME  # Returns "1234567"
    """
    
    def __getattr__(cls, name: str) -> str:
        """
        Intercept attribute access to look up field IDs from registry.
        
        Args:
            name: The attribute name (should match a field name in registry)
            
        Returns:
            The field ID from the registry for this form/field combination.
        """
        # Skip private/dunder attributes
        if name.startswith("_"):
            raise AttributeError(f"'{cls.__name__}' has no attribute '{name}'")
        
        # Get the form key from the class
        form_key = getattr(cls, "_form_key", None)
        if not form_key:
            raise AttributeError(f"'{cls.__name__}' missing '_form_key' attribute")
        
        # Look up field ID from registry
        return _get_registry().get_field_id(form_key, name)


class RagicLeaveFieldMapping(metaclass=RagicFieldMappingMeta):
    """
    Ragic Field ID mappings for the Leave Request form.
    
    NOTE: This class is now powered by RagicRegistry through RagicFieldMappingMeta.
    Field IDs are loaded dynamically from ragic_registry.json at runtime.
    
    Access any attribute to get the field ID from the registry.
    Example: RagicLeaveFieldMapping.EMPLOYEE_NAME returns "1005571"
    """
    _form_key = "leave_form"
    
    # Declared fields (for IDE autocompletion and documentation)
    # Values are just documentation - actual IDs come from registry
    EMPLOYEE_NAME: str
    EMPLOYEE_EMAIL: str
    SALES_DEPT: str
    LEAVE_TYPE: str
    START_DATE: str
    END_DATE: str
    LEAVE_DATE: str
    LEAVE_DAYS: str
    LEAVE_REASON: str
    SALES_DEPT_MANAGER_NAME: str
    DIRECT_SUPERVISOR_NAME: str
    SALES_DEPT_MANAGER_EMAIL: str
    DIRECT_SUPERVISOR_EMAIL: str
    APPROVAL_STATUS: str
    LEAVE_REQUEST_NO: str
    CREATED_DATE: str


class RagicLeaveTypeFieldMapping(metaclass=RagicFieldMappingMeta):
    """
    Ragic Field ID mappings for the Leave Type master data form.
    
    NOTE: This class is now powered by RagicRegistry through RagicFieldMappingMeta.
    Field IDs are loaded dynamically from ragic_registry.json at runtime.
    
    DEPRECATED for sync services: Use LeaveTypeFieldMapping in leave_type_sync.py instead.
    This class is kept for backward compatibility with other parts of the module.
    
    Access any attribute to get the field ID from the registry.
    Example: RagicLeaveTypeFieldMapping.LEAVE_TYPE_CODE returns "3005177"
    """
    _form_key = "leave_type_form"
    
    # Declared fields
    RAGIC_ID: str
    LEAVE_TYPE_CODE: str
    LEAVE_TYPE_NAME: str
    DEDUCTION_MULTIPLIER: str


class RagicAccountFieldMapping(metaclass=RagicFieldMappingMeta):
    """
    Ragic Field ID mappings for the unified Account form.
    
    NOTE: This class is now powered by RagicRegistry through RagicFieldMappingMeta.
    Field IDs are loaded dynamically from ragic_registry.json at runtime.
    
    DEPRECATED for sync services: Use AccountFieldMapping in account_sync.py instead.
    This class is kept for backward compatibility with other parts of the module.
    
    Access any attribute to get the field ID from the registry.
    Example: RagicAccountFieldMapping.NAME returns "1000032"
    """
    _form_key = "account_form"
    
    # === Primary Identification ===
    RAGIC_ID: str
    ACCOUNT_ID: str
    ID_CARD_NUMBER: str
    EMPLOYEE_ID: str
    
    # === Status & Basic Info ===
    STATUS: str
    NAME: str
    GENDER: str
    BIRTHDAY: str
    EDUCATION: str
    
    # === Contact Info ===
    EMAILS: str
    PHONES: str
    MOBILES: str
    
    # === Organization Info ===
    ORG_CODE: str
    ORG_NAME: str
    ORG_PATH: str
    RANK_CODE: str
    RANK_NAME: str
    SALES_DEPT: str
    SALES_DEPT_MANAGER: str
    
    # === Referrer & Mentor ===
    REFERRER_ID_CARD: str
    REFERRER_NAME: str
    MENTOR_ID_CARD: str
    MENTOR_NAME: str
    SUCCESSOR_NAME: str
    SUCCESSOR_ID_CARD: str
    
    # === Employment Dates ===
    APPROVAL_DATE: str
    EFFECTIVE_DATE: str
    RESIGNATION_DATE: str
    DEATH_DATE: str
    CREATED_DATE: str
    
    # === Rate & Financial ===
    ASSESSMENT_RATE: str
    COURT_WITHHOLDING_RATE: str
    COURT_MIN_LIVING_EXPENSE: str
    PRIOR_COMMISSION_DEBT: str
    PRIOR_DEBT: str
    
    # === Bank Info ===
    BANK_NAME: str
    BANK_BRANCH_CODE: str
    BANK_ACCOUNT: str
    EDI_FORMAT: str
    
    # === Address - Household Registration ===
    HOUSEHOLD_POSTAL_CODE: str
    HOUSEHOLD_CITY: str
    HOUSEHOLD_DISTRICT: str
    HOUSEHOLD_ADDRESS: str
    
    # === Address - Mailing ===
    MAILING_POSTAL_CODE: str
    MAILING_CITY: str
    MAILING_DISTRICT: str
    MAILING_ADDRESS: str
    
    # === Emergency Contact ===
    EMERGENCY_CONTACT: str
    EMERGENCY_PHONE: str
    
    # === Life Insurance License ===
    LIFE_LICENSE_NUMBER: str
    LIFE_FIRST_REGISTRATION_DATE: str
    LIFE_REGISTRATION_DATE: str
    LIFE_EXAM_NUMBER: str
    LIFE_CANCELLATION_DATE: str
    LIFE_LICENSE_EXPIRY: str
    
    # === Property Insurance License ===
    PROPERTY_LICENSE_NUMBER: str
    PROPERTY_REGISTRATION_DATE: str
    PROPERTY_EXAM_NUMBER: str
    PROPERTY_CANCELLATION_DATE: str
    PROPERTY_LICENSE_EXPIRY: str
    PROPERTY_STANDARD_DATE: str
    
    # === Accident & Health Insurance License ===
    AH_LICENSE_NUMBER: str
    AH_REGISTRATION_DATE: str
    AH_CANCELLATION_DATE: str
    AH_LICENSE_EXPIRY: str
    
    # === Investment-linked Insurance ===
    INVESTMENT_REGISTRATION_DATE: str
    INVESTMENT_EXAM_NUMBER: str
    
    # === Foreign Currency Insurance ===
    FOREIGN_CURRENCY_REGISTRATION_DATE: str
    FOREIGN_CURRENCY_EXAM_NUMBER: str
    
    # === Qualifications ===
    FUND_QUALIFICATION_DATE: str
    TRADITIONAL_ANNUITY_QUALIFICATION: str
    VARIABLE_ANNUITY_QUALIFICATION: str
    STRUCTURED_BOND_QUALIFICATION: str
    MOBILE_INSURANCE_EXAM_DATE: str
    PREFERRED_INSURANCE_EXAM_DATE: str
    APP_ENABLED: str
    
    # === Training Completion Dates ===
    SENIOR_TRAINING_DATE: str
    FOREIGN_CURRENCY_TRAINING_DATE: str
    FAIR_TREATMENT_TRAINING_DATE: str
    PROFIT_SHARING_TRAINING_DATE: str
    
    # === Office Info ===
    OFFICE: str
    OFFICE_TAX_ID: str
    SUBMISSION_UNIT: str
    
    # === Health Insurance Withholding ===
    NHI_WITHHOLDING_STATUS: str
    NHI_WITHHOLDING_UPDATE_DATE: str
    
    # === Miscellaneous ===
    REMARKS: str
    NOTES: str
    ACCOUNT_ATTRIBUTES: str
    LAST_MODIFIED: str


class AdminSettings(BaseSettings):
    """
    Administrative module settings loaded from environment variables.
    
    All variables use the ADMIN_ prefix for module isolation.
    Sensitive values use SecretStr for security.
    
    Note: Ragic URLs are now loaded from RagicRegistry (ragic_registry.json).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ragic API Configuration (only API key from env, URLs from Registry)
    ragic_api_key: Annotated[
        SecretStr,
        Field(
            description="Ragic API key for authentication",
            validation_alias="ADMIN_RAGIC_API_KEY",
        ),
    ]

    # Sync Configuration
    sync_batch_size: Annotated[
        int,
        Field(
            default=100,
            description="Number of records to process per batch during sync",
            validation_alias="ADMIN_SYNC_BATCH_SIZE",
        ),
    ] = 100

    sync_timeout_seconds: Annotated[
        int,
        Field(
            default=60,
            description="HTTP timeout for Ragic API requests",
            validation_alias="ADMIN_SYNC_TIMEOUT_SECONDS",
        ),
    ] = 60

    # LINE Channel Configuration (獨立 Channel)
    line_channel_secret: Annotated[
        SecretStr,
        Field(
            description="LINE channel secret for webhook verification",
            validation_alias="ADMIN_LINE_CHANNEL_SECRET",
        ),
    ]

    line_channel_access_token: Annotated[
        SecretStr,
        Field(
            description="LINE channel access token for sending messages",
            validation_alias="ADMIN_LINE_CHANNEL_ACCESS_TOKEN",
        ),
    ]

    # LINE LIFF Configuration
    line_liff_id_leave: Annotated[
        str,
        Field(
            default="",
            description="LIFF ID for the leave request form",
            validation_alias="ADMIN_LINE_LIFF_ID_LEAVE",
        ),
    ] = ""

    # === Ragic URLs (loaded from RagicRegistry) ===
    @property
    def ragic_url_account(self) -> str:
        """Full URL for the Ragic Account Form API endpoint."""
        return _get_registry().get_ragic_url("account_form")

    @property
    def ragic_url_leave(self) -> str:
        """Full URL for the Ragic Leave Request Form API endpoint."""
        return _get_registry().get_ragic_url("leave_form")

    @property
    def ragic_url_leave_type(self) -> str:
        """Full URL for the Ragic Leave Type master data API endpoint."""
        return _get_registry().get_ragic_url("leave_type_form")


@lru_cache
def get_admin_settings() -> AdminSettings:
    """
    Get cached administrative module settings.

    Uses LRU cache to ensure settings are loaded only once.

    Returns:
        AdminSettings: Administrative settings instance.
    """
    return AdminSettings()


# === Backward Compatibility Aliases ===
# These functions are deprecated - use RagicRegistry directly

def get_account_form():
    """Deprecated: Use get_ragic_registry().get_form_config('account_form')"""
    import warnings
    warnings.warn(
        "get_account_form() is deprecated. Use get_ragic_registry().get_form_config('account_form')",
        DeprecationWarning,
        stacklevel=2
    )
    return _get_registry().get_form_config("account_form")


def get_leave_form():
    """Deprecated: Use get_ragic_registry().get_form_config('leave_form')"""
    import warnings
    warnings.warn(
        "get_leave_form() is deprecated. Use get_ragic_registry().get_form_config('leave_form')",
        DeprecationWarning,
        stacklevel=2
    )
    return _get_registry().get_form_config("leave_form")


def get_leave_type_form():
    """Deprecated: Use get_ragic_registry().get_form_config('leave_type_form')"""
    import warnings
    warnings.warn(
        "get_leave_type_form() is deprecated. Use get_ragic_registry().get_form_config('leave_type_form')",
        DeprecationWarning,
        stacklevel=2
    )
    return _get_registry().get_form_config("leave_type_form")
