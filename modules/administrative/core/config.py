"""
Administrative Module Configuration.

Manages environment variables specific to the Administrative module.
Uses prefix ADMIN_ to avoid conflicts with other modules.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from core.ragic.columns import get_leave_form, get_leave_type_form, get_account_form


class RagicLeaveFieldMapping:
    """
    Ragic Field ID mappings for the Leave Request form.
    
    Loads field IDs from the centralized ragic_columns.json file.
    """
    
    _config = get_leave_form()
    
    # === Employee Info ===
    EMPLOYEE_NAME = _config.field("EMPLOYEE_NAME")
    EMPLOYEE_EMAIL = _config.field("EMPLOYEE_EMAIL")
    SALES_DEPT = _config.field("SALES_DEPT")
    
    # === Leave Details ===
    LEAVE_TYPE = _config.field("LEAVE_TYPE")
    START_DATE = _config.field("START_DATE")
    END_DATE = _config.field("END_DATE")
    LEAVE_DATE = _config.field("LEAVE_DATE")
    LEAVE_DAYS = _config.field("LEAVE_DAYS")
    LEAVE_REASON = _config.field("LEAVE_REASON")
    
    # === Approval Chain (Names - Visible) ===
    SALES_DEPT_MANAGER_NAME = _config.field("SALES_DEPT_MANAGER_NAME")
    DIRECT_SUPERVISOR_NAME = _config.field("DIRECT_SUPERVISOR_NAME")
    
    # === Approval Chain (Emails - Hidden, for triggering workflow) ===
    SALES_DEPT_MANAGER_EMAIL = _config.field("SALES_DEPT_MANAGER_EMAIL")
    DIRECT_SUPERVISOR_EMAIL = _config.field("DIRECT_SUPERVISOR_EMAIL")
    
    # === System Fields ===
    APPROVAL_STATUS = _config.field("APPROVAL_STATUS")
    LEAVE_REQUEST_NO = _config.field("LEAVE_REQUEST_NO")
    CREATED_DATE = _config.field("CREATED_DATE")


class RagicLeaveTypeFieldMapping:
    """
    Ragic Field ID mappings for the Leave Type master data form.
    
    Loads field IDs from the centralized ragic_columns.json file.
    """
    
    _config = get_leave_type_form()
    
    # === Primary Key ===
    RAGIC_ID = _config.field("RAGIC_ID")
    
    # === Leave Type Info ===
    LEAVE_TYPE_CODE = _config.field("LEAVE_TYPE_CODE")
    LEAVE_TYPE_NAME = _config.field("LEAVE_TYPE_NAME")
    DEDUCTION_MULTIPLIER = _config.field("DEDUCTION_MULTIPLIER")


class RagicAccountFieldMapping:
    """
    Ragic Field ID mappings for the unified Account form.
    
    Loads field IDs from the centralized ragic_columns.json file.
    """
    
    _config = get_account_form()
    
    # === Primary Identification ===
    RAGIC_ID = _config.field("RAGIC_ID")
    ACCOUNT_ID = _config.field("ACCOUNT_ID")
    ID_CARD_NUMBER = _config.field("ID_CARD_NUMBER")
    EMPLOYEE_ID = _config.field("EMPLOYEE_ID")
    
    # === Status & Basic Info ===
    STATUS = _config.field("STATUS")
    NAME = _config.field("NAME")
    GENDER = _config.field("GENDER")
    BIRTHDAY = _config.field("BIRTHDAY")
    EDUCATION = _config.field("EDUCATION")
    
    # === Contact Info ===
    EMAILS = _config.field("EMAILS")
    PHONES = _config.field("PHONES")
    MOBILES = _config.field("MOBILES")
    
    # === Organization Info ===
    ORG_CODE = _config.field("ORG_CODE")
    ORG_NAME = _config.field("ORG_NAME")
    ORG_PATH = _config.field("ORG_PATH")
    RANK_CODE = _config.field("RANK_CODE")
    RANK_NAME = _config.field("RANK_NAME")
    SALES_DEPT = _config.field("SALES_DEPT")
    SALES_DEPT_MANAGER = _config.field("SALES_DEPT_MANAGER")
    
    # === Referrer & Mentor ===
    REFERRER_ID_CARD = _config.field("REFERRER_ID_CARD")
    REFERRER_NAME = _config.field("REFERRER_NAME")
    MENTOR_ID_CARD = _config.field("MENTOR_ID_CARD")
    MENTOR_NAME = _config.field("MENTOR_NAME")
    SUCCESSOR_NAME = _config.field("SUCCESSOR_NAME")
    SUCCESSOR_ID_CARD = _config.field("SUCCESSOR_ID_CARD")
    
    # === Employment Dates ===
    APPROVAL_DATE = _config.field("APPROVAL_DATE")
    EFFECTIVE_DATE = _config.field("EFFECTIVE_DATE")
    RESIGNATION_DATE = _config.field("RESIGNATION_DATE")
    DEATH_DATE = _config.field("DEATH_DATE")
    CREATED_DATE = _config.field("CREATED_DATE")
    
    # === Rate & Financial ===
    ASSESSMENT_RATE = _config.field("ASSESSMENT_RATE")
    COURT_WITHHOLDING_RATE = _config.field("COURT_WITHHOLDING_RATE")
    COURT_MIN_LIVING_EXPENSE = _config.field("COURT_MIN_LIVING_EXPENSE")
    PRIOR_COMMISSION_DEBT = _config.field("PRIOR_COMMISSION_DEBT")
    PRIOR_DEBT = _config.field("PRIOR_DEBT")
    
    # === Bank Info ===
    BANK_NAME = _config.field("BANK_NAME")
    BANK_BRANCH_CODE = _config.field("BANK_BRANCH_CODE")
    BANK_ACCOUNT = _config.field("BANK_ACCOUNT")
    EDI_FORMAT = _config.field("EDI_FORMAT")
    
    # === Address - Household Registration ===
    HOUSEHOLD_POSTAL_CODE = _config.field("HOUSEHOLD_POSTAL_CODE")
    HOUSEHOLD_CITY = _config.field("HOUSEHOLD_CITY")
    HOUSEHOLD_DISTRICT = _config.field("HOUSEHOLD_DISTRICT")
    HOUSEHOLD_ADDRESS = _config.field("HOUSEHOLD_ADDRESS")
    
    # === Address - Mailing ===
    MAILING_POSTAL_CODE = _config.field("MAILING_POSTAL_CODE")
    MAILING_CITY = _config.field("MAILING_CITY")
    MAILING_DISTRICT = _config.field("MAILING_DISTRICT")
    MAILING_ADDRESS = _config.field("MAILING_ADDRESS")
    
    # === Emergency Contact ===
    EMERGENCY_CONTACT = _config.field("EMERGENCY_CONTACT")
    EMERGENCY_PHONE = _config.field("EMERGENCY_PHONE")
    
    # === Life Insurance License ===
    LIFE_LICENSE_NUMBER = _config.field("LIFE_LICENSE_NUMBER")
    LIFE_FIRST_REGISTRATION_DATE = _config.field("LIFE_FIRST_REGISTRATION_DATE")
    LIFE_REGISTRATION_DATE = _config.field("LIFE_REGISTRATION_DATE")
    LIFE_EXAM_NUMBER = _config.field("LIFE_EXAM_NUMBER")
    LIFE_CANCELLATION_DATE = _config.field("LIFE_CANCELLATION_DATE")
    LIFE_LICENSE_EXPIRY = _config.field("LIFE_LICENSE_EXPIRY")
    
    # === Property Insurance License ===
    PROPERTY_LICENSE_NUMBER = _config.field("PROPERTY_LICENSE_NUMBER")
    PROPERTY_REGISTRATION_DATE = _config.field("PROPERTY_REGISTRATION_DATE")
    PROPERTY_EXAM_NUMBER = _config.field("PROPERTY_EXAM_NUMBER")
    PROPERTY_CANCELLATION_DATE = _config.field("PROPERTY_CANCELLATION_DATE")
    PROPERTY_LICENSE_EXPIRY = _config.field("PROPERTY_LICENSE_EXPIRY")
    PROPERTY_STANDARD_DATE = _config.field("PROPERTY_STANDARD_DATE")
    
    # === Accident & Health Insurance License ===
    AH_LICENSE_NUMBER = _config.field("AH_LICENSE_NUMBER")
    AH_REGISTRATION_DATE = _config.field("AH_REGISTRATION_DATE")
    AH_CANCELLATION_DATE = _config.field("AH_CANCELLATION_DATE")
    AH_LICENSE_EXPIRY = _config.field("AH_LICENSE_EXPIRY")
    
    # === Investment-linked Insurance ===
    INVESTMENT_REGISTRATION_DATE = _config.field("INVESTMENT_REGISTRATION_DATE")
    INVESTMENT_EXAM_NUMBER = _config.field("INVESTMENT_EXAM_NUMBER")
    
    # === Foreign Currency Insurance ===
    FOREIGN_CURRENCY_REGISTRATION_DATE = _config.field("FOREIGN_CURRENCY_REGISTRATION_DATE")
    FOREIGN_CURRENCY_EXAM_NUMBER = _config.field("FOREIGN_CURRENCY_EXAM_NUMBER")
    
    # === Qualifications ===
    FUND_QUALIFICATION_DATE = _config.field("FUND_QUALIFICATION_DATE")
    TRADITIONAL_ANNUITY_QUALIFICATION = _config.field("TRADITIONAL_ANNUITY_QUALIFICATION")
    VARIABLE_ANNUITY_QUALIFICATION = _config.field("VARIABLE_ANNUITY_QUALIFICATION")
    STRUCTURED_BOND_QUALIFICATION = _config.field("STRUCTURED_BOND_QUALIFICATION")
    MOBILE_INSURANCE_EXAM_DATE = _config.field("MOBILE_INSURANCE_EXAM_DATE")
    PREFERRED_INSURANCE_EXAM_DATE = _config.field("PREFERRED_INSURANCE_EXAM_DATE")
    APP_ENABLED = _config.field("APP_ENABLED")
    
    # === Training Completion Dates ===
    SENIOR_TRAINING_DATE = _config.field("SENIOR_TRAINING_DATE")
    FOREIGN_CURRENCY_TRAINING_DATE = _config.field("FOREIGN_CURRENCY_TRAINING_DATE")
    FAIR_TREATMENT_TRAINING_DATE = _config.field("FAIR_TREATMENT_TRAINING_DATE")
    PROFIT_SHARING_TRAINING_DATE = _config.field("PROFIT_SHARING_TRAINING_DATE")
    
    # === Office Info ===
    OFFICE = _config.field("OFFICE")
    OFFICE_TAX_ID = _config.field("OFFICE_TAX_ID")
    SUBMISSION_UNIT = _config.field("SUBMISSION_UNIT")
    
    # === Health Insurance Withholding ===
    NHI_WITHHOLDING_STATUS = _config.field("NHI_WITHHOLDING_STATUS")
    NHI_WITHHOLDING_UPDATE_DATE = _config.field("NHI_WITHHOLDING_UPDATE_DATE")
    
    # === Miscellaneous ===
    REMARKS = _config.field("REMARKS")
    NOTES = _config.field("NOTES")
    ACCOUNT_ATTRIBUTES = _config.field("ACCOUNT_ATTRIBUTES")
    LAST_MODIFIED = _config.field("LAST_MODIFIED")


class AdminSettings(BaseSettings):
    """
    Administrative module settings loaded from environment variables.
    
    All variables use the ADMIN_ prefix for module isolation.
    Sensitive values use SecretStr for security.
    
    Note: Ragic URLs are now loaded from ragic_columns.json (centralized config).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ragic API Configuration (only API key from env, URLs from JSON)
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

    # === Ragic URLs (loaded from ragic_columns.json) ===
    @property
    def ragic_url_account(self) -> str:
        """Full URL for the Ragic Account Form API endpoint."""
        return get_account_form().url

    @property
    def ragic_url_leave(self) -> str:
        """Full URL for the Ragic Leave Request Form API endpoint."""
        return get_leave_form().url

    @property
    def ragic_url_leave_type(self) -> str:
        """Full URL for the Ragic Leave Type master data API endpoint."""
        return get_leave_type_form().url


@lru_cache
def get_admin_settings() -> AdminSettings:
    """
    Get cached administrative module settings.

    Uses LRU cache to ensure settings are loaded only once.

    Returns:
        AdminSettings: Administrative settings instance.
    """
    return AdminSettings()
