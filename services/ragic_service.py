"""
Ragic Service - DEPRECATED Compatibility Shim.

This module is deprecated. Use core.ragic instead:

    from core.ragic import RagicService, RagicRepository

This file is kept only for backward compatibility with existing code.
"""
from typing import Any, Dict, List, Optional
import logging
import warnings

from core.ragic.service import RagicService as BaseRagicService
from core.app_context import ConfigLoader


class RagicService(BaseRagicService):
    """
    DEPRECATED: Use core.ragic.RagicService instead.
    
    This class wraps the new unified RagicService for backward compatibility.
    It accepts a ConfigLoader in the constructor (legacy interface).
    """
    
    def __init__(self, config: ConfigLoader) -> None:
        warnings.warn(
            "services.ragic_service.RagicService is deprecated. "
            "Use core.ragic.RagicService instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # Extract config values and pass to base
        api_key = config.get("ragic.api_key", "")
        base_url = config.get("ragic.base_url", "")
        super().__init__(api_key=api_key, base_url=base_url)
        
        # Keep reference for legacy code that might access it
        self._config = config
        self._logger = logging.getLogger(__name__)
