"""
Chatbot Schemas Package.

Contains Pydantic schemas for request/response validation.
"""

from modules.chatbot.schemas.schemas import (
    AuthStatus,
    BaseSchema,
    ErrorResponse,
    LineBotMessage,
    LineWebhookEvent,
    MagicLinkRequest,
    MagicLinkResponse,
    RagicEmployeeData,
    SearchQuery,
    SearchResponse,
    SearchResult,
    SOPDocumentBase,
    SOPDocumentCreate,
    SOPDocumentResponse,
    SOPDocumentUpdate,
    SuccessResponse,
    UserCreate,
    UserPublic,
    UserResponse,
    UserUpdate,
    VerifyTokenRequest,
    VerifyTokenResponse,
)

__all__ = [
    "AuthStatus",
    "BaseSchema",
    "ErrorResponse",
    "LineBotMessage",
    "LineWebhookEvent",
    "MagicLinkRequest",
    "MagicLinkResponse",
    "RagicEmployeeData",
    "SearchQuery",
    "SearchResponse",
    "SearchResult",
    "SOPDocumentBase",
    "SOPDocumentCreate",
    "SOPDocumentResponse",
    "SOPDocumentUpdate",
    "SuccessResponse",
    "UserCreate",
    "UserPublic",
    "UserResponse",
    "UserUpdate",
    "VerifyTokenRequest",
    "VerifyTokenResponse",
]
