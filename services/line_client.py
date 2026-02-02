"""
LINE Client - DEPRECATED.

This module is deprecated. Use core.line_client instead:

    from core.line_client import LineClient

This file is kept only for backward compatibility with existing imports.
"""
import warnings

# Re-export from new location
from core.line_client import LineClient

warnings.warn(
    "services.line_client is deprecated. Use core.line_client instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["LineClient"]
