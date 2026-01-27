"""
Core Authentication Schemas.

Pydantic models for authentication request/response validation.
These are framework-level schemas used across all modules.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True)


class RagicEmployeeData(BaseModel):
    """Employee data from Ragic API."""

    employee_id: str = Field(..., description="Unique employee identifier")
    email: str = Field(..., description="Employee email address")
    name: str = Field(..., description="Employee display name")
    is_active: bool = Field(
        default=True, description="Whether employee is active")
    raw_data: dict[str, Any] = Field(
        default_factory=dict, description="Raw Ragic record")


class MagicLinkRequest(BaseModel):
    """Request to initiate magic link authentication."""

    email: EmailStr = Field(..., description="Employee email address")
    line_sub: str = Field(..., min_length=1,
                          description="LINE sub (OIDC Subject Identifier)")


class MagicLinkResponse(BaseModel):
    """Response after magic link is sent."""

    message: str = Field(..., description="Status message")
    email_sent_to: str = Field(...,
                               description="Email address the link was sent to")


class VerifyTokenRequest(BaseModel):
    """Request to verify a magic link token."""

    token: str = Field(..., min_length=1, description="Magic link token")


class UserResponse(BaseSchema):
    """User data response after successful verification."""

    id: UUID
    email: str
    line_user_id: str
    display_name: Optional[str] = None
    ragic_employee_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class VerifyTokenResponse(BaseModel):
    """Response after token verification."""

    success: bool = Field(..., description="Whether verification succeeded")
    message: str = Field(..., description="Status message")
    user: Optional[UserResponse] = Field(
        None, description="User data if verification succeeded")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[dict[str, Any]] = Field(
        None, description="Additional error details")
