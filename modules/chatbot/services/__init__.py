"""
Chatbot Services Package.

Contains all business logic services.
"""

from modules.chatbot.services.auth_service import (
    AuthError,
    AuthService,
    EmailNotFoundError,
    EmailSendError,
    TokenAlreadyUsedError,
    UserBindingError,
    get_auth_service,
)
from modules.chatbot.services.json_import_service import (
    ImportResult,
    JsonImportError,
    JsonImportService,
    JsonParseError,
    JsonValidationError,
    SOPContentTooLongError,
    get_json_import_service,
)
from modules.chatbot.services.line_service import LineService, get_line_service
from modules.chatbot.services.ragic_service import RagicService, get_ragic_service
from modules.chatbot.services.vector_service import (
    EmbeddingError,
    SearchError,
    VectorService,
    VectorServiceError,
    get_vector_service,
)


__all__ = [
    # Auth
    "AuthError",
    "AuthService",
    "EmailNotFoundError",
    "EmailSendError",
    "TokenAlreadyUsedError",
    "UserBindingError",
    "get_auth_service",
    # JSON Import
    "ImportResult",
    "JsonImportError",
    "JsonImportService",
    "JsonParseError",
    "JsonValidationError",
    "SOPContentTooLongError",
    "get_json_import_service",
    # LINE
    "LineService",
    "get_line_service",
    # Ragic
    "RagicService",
    "get_ragic_service",
    # Vector
    "EmbeddingError",
    "SearchError",
    "VectorService",
    "VectorServiceError",
    "get_vector_service",
]
