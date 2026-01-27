"""
Pydantic V2 Schemas / DTOs.

Defines request/response schemas for API endpoints.
Follows Interface Segregation Principle with focused, single-purpose schemas.
"""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# =============================================================================
# Base Configurations
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM mode
        str_strip_whitespace=True,
        validate_assignment=True,
    )


# =============================================================================
# User Schemas
# =============================================================================

class UserBase(BaseSchema):
    """Base user fields."""

    email: EmailStr
    display_name: Annotated[str | None, Field(max_length=255)] = None


class UserCreate(UserBase):
    """Schema for creating a new user."""

    line_sub: Annotated[str, Field(min_length=1, max_length=64)]
    ragic_employee_id: Annotated[str | None, Field(max_length=64)] = None


class UserUpdate(BaseSchema):
    """Schema for updating user fields."""

    display_name: Annotated[str | None, Field(max_length=255)] = None
    is_active: bool | None = None


class UserResponse(UserBase):
    """Schema for user response."""

    id: str
    line_sub: str
    ragic_employee_id: str | None
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserPublic(BaseSchema):
    """Public user info (limited fields)."""

    id: str
    display_name: str | None
    is_active: bool


# =============================================================================
# Authentication Schemas
# =============================================================================

class MagicLinkRequest(BaseSchema):
    """Request schema for initiating magic link authentication."""

    email: EmailStr
    line_sub: Annotated[str, Field(min_length=1, max_length=64)]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower()


class MagicLinkResponse(BaseSchema):
    """Response after magic link is sent."""

    message: str
    email_sent_to: str


class VerifyTokenRequest(BaseSchema):
    """Request schema for verifying magic link token."""

    token: Annotated[str, Field(min_length=1)]


class VerifyTokenResponse(BaseSchema):
    """Response after successful token verification."""

    success: bool
    message: str
    user: UserResponse | None = None


class AuthStatus(BaseSchema):
    """User authentication status."""

    is_authenticated: bool
    user: UserPublic | None = None


# =============================================================================
# Ragic / Employee Schemas
# =============================================================================

class RagicEmployeeData(BaseSchema):
    """
    Employee data from Ragic API (AC01 門禁/簽到退 系統申請單).

    Note: email accepts any domain (personal emails like Gmail are allowed).
    employee_id uses Door Access ID (門禁編號) when available, 
    otherwise falls back to Ragic Record ID.
    """

    employee_id: str  # Door Access ID or Ragic Record ID
    email: str  # Any email domain allowed (not restricted to corporate)
    name: str
    department: str | None = None
    is_active: bool = True
    raw_data: dict[str, Any] | None = None


# =============================================================================
# SOP Document Schemas
# =============================================================================

class SOPDocumentBase(BaseSchema):
    """Base SOP document fields."""

    title: Annotated[str, Field(min_length=1, max_length=512)]
    content: Annotated[str, Field(min_length=1)]
    category: Annotated[str | None, Field(max_length=128)] = None
    tags: list[str] | None = None
    metadata_: Annotated[dict[str, Any] | None, Field(
        validation_alias="metadata_", serialization_alias="metadata")] = None


class SOPDocumentCreate(SOPDocumentBase):
    """Schema for creating a new SOP document."""
    pass


class SOPDocumentUpdate(BaseSchema):
    """Schema for updating SOP document fields."""

    title: Annotated[str | None, Field(max_length=512)] = None
    content: str | None = None
    category: Annotated[str | None, Field(max_length=128)] = None
    tags: list[str] | None = None
    metadata_: Annotated[dict[str, Any] | None, Field(
        validation_alias="metadata_", serialization_alias="metadata")] = None
    is_published: bool | None = None


class SOPDocumentResponse(SOPDocumentBase):
    """Schema for SOP document response."""

    id: str
    is_published: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,  # Allow both 'metadata_' and 'metadata'
    )


# =============================================================================
# Search Schemas
# =============================================================================

class SearchQuery(BaseSchema):
    """Search query request."""

    query: Annotated[str, Field(min_length=1, max_length=1000)]
    top_k: Annotated[int, Field(ge=1, le=20)] = 3
    category: str | None = None
    similarity_threshold: Annotated[float, Field(ge=0.0, le=1.0)] = 0.3


class SearchResult(BaseSchema):
    """Single search result."""

    document: SOPDocumentResponse
    similarity_score: Annotated[float, Field(ge=0.0, le=1.0)]
    snippet: str | None = None


class SearchResponse(BaseSchema):
    """Search response with multiple results."""

    query: str
    results: list[SearchResult]
    total_count: int
    search_time_ms: float


# =============================================================================
# LINE Bot Schemas
# =============================================================================

class LineWebhookEvent(BaseSchema):
    """LINE webhook event structure."""

    type: str
    timestamp: int
    source: dict[str, Any]
    reply_token: str | None = None
    message: dict[str, Any] | None = None


class LineBotMessage(BaseSchema):
    """Message to send via LINE Bot."""

    to: str
    message_type: str = "text"
    text: str | None = None
    flex_content: dict[str, Any] | None = None


# =============================================================================
# Generic Response Schemas
# =============================================================================

class SuccessResponse(BaseSchema):
    """Generic success response."""

    success: bool = True
    message: str


class ErrorResponse(BaseSchema):
    """Generic error response."""

    success: bool = False
    error: str
    detail: str | None = None
