"""
Chatbot Module Configuration.

Manages environment variables specific to the SOP Chatbot.
Uses prefix SOP_BOT_ to avoid conflicts with other modules.
"""

import os
from functools import lru_cache
from typing import Annotated

from pydantic import Field, PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatbotSettings(BaseSettings):
    """
    Chatbot-specific settings loaded from environment variables.
    
    All variables use the SOP_BOT_ prefix for module isolation.
    Sensitive values use SecretStr for security.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="HSIB SOP Bot", validation_alias="SOP_BOT_APP_NAME")
    app_version: str = Field(default="1.0.0", validation_alias="SOP_BOT_APP_VERSION")
    debug: bool = Field(default=False, validation_alias="SOP_BOT_DEBUG")

    # LINE Bot (module-specific credentials)
    line_channel_secret: Annotated[
        SecretStr,
        Field(
            description="LINE channel secret for webhook verification",
            validation_alias="SOP_BOT_LINE_CHANNEL_SECRET"
        )
    ]
    line_channel_access_token: Annotated[
        SecretStr,
        Field(
            description="LINE channel access token for sending messages",
            validation_alias="SOP_BOT_LINE_CHANNEL_ACCESS_TOKEN"
        )
    ]

    # Ragic - Unified Account Table
    ragic_employee_sheet_path: Annotated[
        str,
        Field(
            default="/HSIBAdmSys/ychn-test/11",
            description="Ragic sheet path for unified Account table",
            validation_alias="SOP_BOT_RAGIC_EMPLOYEE_SHEET_PATH"
        )
    ] = "/HSIBAdmSys/ychn-test/11"

    ragic_field_email: Annotated[
        str,
        Field(default="1005977", validation_alias="SOP_BOT_RAGIC_FIELD_EMAIL")
    ] = "1005977"

    ragic_field_name: Annotated[
        str,
        Field(default="1005975", validation_alias="SOP_BOT_RAGIC_FIELD_NAME")
    ] = "1005975"

    ragic_field_door_access_id: Annotated[
        str,
        Field(default="1005983", validation_alias="SOP_BOT_RAGIC_FIELD_DOOR_ACCESS_ID")
    ] = "1005983"

    # SOP Content Validation
    sop_content_max_length: Annotated[
        int,
        Field(default=10000, validation_alias="SOP_BOT_SOP_CONTENT_MAX_LENGTH")
    ] = 10000

    # Vector Embedding
    embedding_dimension: Annotated[
        int,
        Field(default=768, description="Embedding dimension", validation_alias="SOP_BOT_EMBEDDING_DIMENSION")
    ] = 768

    # Magic Link
    magic_link_expire_minutes: Annotated[
        int,
        Field(default=15, description="Magic link expiration in minutes", validation_alias="SOP_BOT_MAGIC_LINK_EXPIRE_MINUTES")
    ] = 15


@lru_cache
def get_chatbot_settings() -> ChatbotSettings:
    """
    Get cached chatbot settings.

    Uses LRU cache to ensure settings are loaded only once.

    Returns:
        ChatbotSettings: Chatbot settings instance.
    """
    return ChatbotSettings()
