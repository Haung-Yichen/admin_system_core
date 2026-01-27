"""
Administrative Module Configuration.

Manages environment variables specific to the Administrative module.
Uses prefix ADMIN_ to avoid conflicts with other modules.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RagicFieldMapping:
    """
    Ragic Field ID mappings for Employee and Department forms.
    
    These constants map our model attributes to Ragic field IDs.
    Used for schema validation and data transformation.
    """
    
    # Employee Form Fields
    EMPLOYEE_EMAIL = "1001132"
    EMPLOYEE_NAME = "1001129"
    EMPLOYEE_DEPARTMENT = "1001194"
    EMPLOYEE_SUPERVISOR_EMAIL = "1001182"  # Mentor ID/Email
    
    # Department Form Fields
    DEPARTMENT_NAME = "1002508"
    DEPARTMENT_MANAGER_EMAIL = "1002509"  # Person in Charge


class AdminSettings(BaseSettings):
    """
    Administrative module settings loaded from environment variables.
    
    All variables use the ADMIN_ prefix for module isolation.
    Sensitive values use SecretStr for security.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ragic API Configuration
    ragic_api_key: Annotated[
        SecretStr,
        Field(
            description="Ragic API key for authentication",
            validation_alias="ADMIN_RAGIC_API_KEY",
        ),
    ]

    ragic_url_employee: Annotated[
        str,
        Field(
            description="Full URL for the Ragic Employee Form API endpoint",
            validation_alias="ADMIN_RAGIC_URL_EMPLOYEE",
        ),
    ]

    ragic_url_dept: Annotated[
        str,
        Field(
            description="Full URL for the Ragic Department Form API endpoint",
            validation_alias="ADMIN_RAGIC_URL_DEPT",
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

    # Field Mappings (can be overridden via env if Ragic form changes)
    field_employee_email: Annotated[
        str,
        Field(
            default=RagicFieldMapping.EMPLOYEE_EMAIL,
            validation_alias="ADMIN_FIELD_EMPLOYEE_EMAIL",
        ),
    ] = RagicFieldMapping.EMPLOYEE_EMAIL

    field_employee_name: Annotated[
        str,
        Field(
            default=RagicFieldMapping.EMPLOYEE_NAME,
            validation_alias="ADMIN_FIELD_EMPLOYEE_NAME",
        ),
    ] = RagicFieldMapping.EMPLOYEE_NAME

    field_employee_department: Annotated[
        str,
        Field(
            default=RagicFieldMapping.EMPLOYEE_DEPARTMENT,
            validation_alias="ADMIN_FIELD_EMPLOYEE_DEPARTMENT",
        ),
    ] = RagicFieldMapping.EMPLOYEE_DEPARTMENT

    field_employee_supervisor_email: Annotated[
        str,
        Field(
            default=RagicFieldMapping.EMPLOYEE_SUPERVISOR_EMAIL,
            validation_alias="ADMIN_FIELD_EMPLOYEE_SUPERVISOR_EMAIL",
        ),
    ] = RagicFieldMapping.EMPLOYEE_SUPERVISOR_EMAIL

    field_department_name: Annotated[
        str,
        Field(
            default=RagicFieldMapping.DEPARTMENT_NAME,
            validation_alias="ADMIN_FIELD_DEPARTMENT_NAME",
        ),
    ] = RagicFieldMapping.DEPARTMENT_NAME

    field_department_manager_email: Annotated[
        str,
        Field(
            default=RagicFieldMapping.DEPARTMENT_MANAGER_EMAIL,
            validation_alias="ADMIN_FIELD_DEPARTMENT_MANAGER_EMAIL",
        ),
    ] = RagicFieldMapping.DEPARTMENT_MANAGER_EMAIL

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


@lru_cache
def get_admin_settings() -> AdminSettings:
    """
    Get cached administrative module settings.

    Uses LRU cache to ensure settings are loaded only once.

    Returns:
        AdminSettings: Administrative settings instance.
    """
    return AdminSettings()
