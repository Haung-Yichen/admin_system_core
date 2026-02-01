"""
Core Services Package.

Provides framework-level services used by all modules.
"""

from core.services.ragic import RagicService, get_ragic_service
from core.services.auth import (
    AuthService,
    AuthError,
    EmailNotFoundError,
    UserBindingError,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenInvalidError,
    LineIdTokenError,
    LineIdTokenExpiredError,
    LineIdTokenInvalidError,
    AccountNotBoundError,
    get_auth_service,
)
from core.services.auth_token import (
    MagicLinkPayload,
    create_magic_link_token,
    decode_magic_link_token,
)
from core.services.email import (
    EmailService,
    EmailSendError,
    EmailConfig,
    EmailTemplates,
    get_email_service,
)
from core.services.user_sync import (
    UserSyncService,
    UserRagicWriter,
    RagicUserFieldMapping,
    get_user_sync_service,
    get_user_ragic_writer,
)

__all__ = [
    # Ragic
    "RagicService",
    "get_ragic_service",
    # Auth
    "AuthService",
    "AuthError",
    "EmailNotFoundError",
    "UserBindingError",
    "TokenAlreadyUsedError",
    "TokenExpiredError",
    "TokenInvalidError",
    # LINE ID Token Auth
    "LineIdTokenError",
    "LineIdTokenExpiredError",
    "LineIdTokenInvalidError",
    "AccountNotBoundError",
    "get_auth_service",
    # Token
    "MagicLinkPayload",
    "create_magic_link_token",
    "decode_magic_link_token",
    # Email
    "EmailService",
    "EmailSendError",
    "EmailConfig",
    "EmailTemplates",
    "get_email_service",
    # User Sync (Ragic Master)
    "UserSyncService",
    "UserRagicWriter",
    "RagicUserFieldMapping",
    "get_user_sync_service",
    "get_user_ragic_writer",
]
