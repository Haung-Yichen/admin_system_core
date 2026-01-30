
import logging
from typing import Any, Dict, Optional

from core.ragic.sync_base import BaseRagicSyncService
from modules.administrative.core.config import (
    RagicAccountFieldMapping as Fields,
    get_admin_settings,
    get_account_form,
)
from modules.administrative.models import AdministrativeAccount
from modules.administrative.services.ragic_sync import RagicSyncService

logger = logging.getLogger(__name__)

class AccountSyncService(BaseRagicSyncService[AdministrativeAccount]):
    """
    Ragic Sync Service for Employee Accounts.
    """
    
    def __init__(self):
        super().__init__(AdministrativeAccount)
        # Reuse logic from existing service for transformation to avoid duplication
        # In a full refactor, logic should be moved here completely
        self._legacy_service = RagicSyncService() 

    def get_ragic_config(self) -> Dict[str, Any]:
        """Return Ragic form configuration."""
        form = get_account_form()
        return {
            "url": form.url,
            "sheet_path": form.sheet_path
        }

    async def map_record_to_dict(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map a Ragic record to a dictionary suitable for model creation.
        """
        # Reuse the transformation logic from the existing service
        # We need to access the private method or move it to a utility
        # For now, accessing it is the quickest way
        return self._legacy_service._transform_account_record(record)
