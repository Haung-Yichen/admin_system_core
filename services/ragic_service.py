"""
Ragic Service - DEPRECATED.

This module is deprecated. Use core.ragic instead:

    from core.ragic import RagicService, RagicRepository

This file is kept only for backward compatibility with existing imports.
"""
import warnings

# Re-export from new location
from core.ragic.service import RagicService

warnings.warn(
    "services.ragic_service is deprecated. Use core.ragic.RagicService instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ["RagicService"]
        
        # Keep reference for legacy code that might access it
        self._config = config
        self._logger = logging.getLogger(__name__)
