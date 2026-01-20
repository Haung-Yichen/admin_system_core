"""
Core Schemas Package.

Provides framework-level Pydantic models used by all modules.
"""

from core.schemas.auth import (
    MagicLinkRequest,
    MagicLinkResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
    UserResponse,
    RagicEmployeeData,
    ErrorResponse,
)

__all__ = [
    "MagicLinkRequest",
    "MagicLinkResponse",
    "VerifyTokenRequest",
    "VerifyTokenResponse",
    "UserResponse",
    "RagicEmployeeData",
    "ErrorResponse",
]
