
import logging
from typing import Any, Dict, Optional

from core.ragic.sync_base import BaseRagicSyncService
from core.ragic.registry import get_ragic_registry
from modules.administrative.core.config import (
    RagicAccountFieldMapping as Fields,
    get_admin_settings,
)
from modules.administrative.models import AdministrativeAccount
from modules.administrative.services.ragic_sync import transform_ragic_record

logger = logging.getLogger(__name__)

class AccountSyncService(BaseRagicSyncService[AdministrativeAccount]):
    """
    Ragic Sync Service for Employee Accounts.
    
    Uses RagicRegistry for configuration (form_key="account_form").
    """
    
    def __init__(self):
        super().__init__(
            model_class=AdministrativeAccount,
            form_key="account_form",  # NEW: Use form_key instead of hardcoded config
        )

    async def map_record_to_dict(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map a Ragic record to a dictionary suitable for model creation.
        """
        # Use the module-level transform function
        return transform_ragic_record(record)
