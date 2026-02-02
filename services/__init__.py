"""
Services module - DEPRECATED.

This module is deprecated. Use core module instead:

    from core.line_client import LineClient
    from core.ragic import RagicService

These shims are provided for backward compatibility only.
"""
import warnings

# Re-export from new locations for backward compatibility
from core.line_client import LineClient

# Emit deprecation warning on import
warnings.warn(
    "The 'services' module is deprecated. "
    "Use 'core.line_client.LineClient' instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["LineClient"]
