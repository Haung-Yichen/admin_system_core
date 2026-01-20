"""
Core Services Package.

Provides framework-level services used by all modules.
"""

from core.services.ragic import RagicService, get_ragic_service
from core.services.auth import (
    AuthService,
    AuthError,
    EmailNotFoundError,
    EmailSendError,
    UserBindingError,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenInvalidError,
    get_auth_service,
)
from core.services.auth_token import (
    MagicLinkPayload,
    create_magic_link_token,
    decode_magic_link_token,
)

__all__ = [
    # Ragic
    "RagicService",
    "get_ragic_service",
    # Auth
    "AuthService",
    "AuthError",
    "EmailNotFoundError",
    "EmailSendError",
    "UserBindingError",
    "TokenAlreadyUsedError",
    "TokenExpiredError",
    "TokenInvalidError",
    "get_auth_service",
    # Token
    "MagicLinkPayload",
    "create_magic_link_token",
    "decode_magic_link_token",
]
