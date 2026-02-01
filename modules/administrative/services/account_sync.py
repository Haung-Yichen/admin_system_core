
import logging
from typing import Any, Dict, Optional

from core.ragic.sync_base import BaseRagicSyncService
from modules.administrative.core.config import (
    RagicAccountFieldMapping as Fields,
    get_admin_settings,
    get_account_form,
)
from modules.administrative.models import AdministrativeAccount
from modules.administrative.services.ragic_sync import transform_ragic_record

logger = logging.getLogger(__name__)

class AccountSyncService(BaseRagicSyncService[AdministrativeAccount]):
    """
    Ragic Sync Service for Employee Accounts.
    """
    
    def __init__(self):
        super().__init__(AdministrativeAccount)

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
        # Use the module-level transform function
        return transform_ragic_record(record)
