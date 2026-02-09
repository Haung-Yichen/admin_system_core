"""
Ragic-specific exceptions.

Custom exception classes for Ragic configuration and operation errors.
"""


class RagicError(Exception):
    """Base exception for Ragic-related errors."""
    pass


class RagicConfigurationError(RagicError):
    """
    Raised when Ragic configuration is missing or invalid.
    
    Examples:
        - Form key not found in registry
        - Invalid field mapping
        - Missing required configuration
    """
    
    def __init__(self, message: str, form_key: str | None = None) -> None:
        self.form_key = form_key
        super().__init__(message)


class RagicConnectionError(RagicError):
    """Raised when connection to Ragic API fails."""
    pass


class RagicValidationError(RagicError):
    """Raised when data validation fails for Ragic operations."""
    pass
