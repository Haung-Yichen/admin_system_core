"""
Ragic SOP Sync Service.

Handles synchronization of SOP Knowledge Base from Ragic to local database.
Refactored to use the Core BaseRagicSyncService.
"""

import logging
import time
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.ragic.columns import get_sop_form
from core.ragic.sync_base import BaseRagicSyncService
from modules.chatbot.models import SOPDocument
from modules.chatbot.services.vector_service import get_vector_service

logger = logging.getLogger(__name__)


# =============================================================================
# Field Mapping from ragic_columns.json
# =============================================================================

class SOPFieldMapping:
    """SOP form field ID mapping - cached for performance."""
    _cache: dict = {}
    
    @classmethod
    def _get_field(cls, name: str, default: str = "") -> str:
        if name not in cls._cache:
            try:
                cls._cache[name] = get_sop_form().field(name)
            except KeyError:
                cls._cache[name] = default
        return cls._cache[name]
    
    @classmethod
    def SOP_ID(cls) -> str:
        return cls._get_field("SOP_ID")
    
    @classmethod
    def TITLE(cls) -> str:
        return cls._get_field("TITLE")

    @classmethod
    def CONTENT(cls) -> str:
        return cls._get_field("CONTENT")

    @classmethod
    def CATEGORY(cls) -> str:
        return cls._get_field("CATEGORY")

    @classmethod
    def KEYWORDS(cls) -> str:
        return cls._get_field("KEYWORDS")
    
    @classmethod
    def IS_PUBLISHED(cls) -> str:
        return cls._get_field("IS_PUBLISHED", "_is_published_not_defined_")


class SOPSyncService(BaseRagicSyncService[SOPDocument]):
    """
    SOP Sync Service implementation using Core Base Class.
    """

    def __init__(self):
        super().__init__(model_class=SOPDocument)
        self.vector_service = get_vector_service()

    def get_ragic_config(self) -> Dict[str, Any]:
        """Get SOP form config."""
        form = get_sop_form()
        return {
            "url": form.url,
            "sheet_path": form.sheet_path
        }

    async def map_record_to_dict(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map Ragic SOP record to SOPDocument model.
        """
        try:
            sop_id = record.get(SOPFieldMapping.SOP_ID())
            title = record.get(SOPFieldMapping.TITLE())
            content = record.get(SOPFieldMapping.CONTENT())
            
            # Validation
            if not sop_id or not title:
                # logger.warning(f"Skipping invalid record: Missing ID or Title. ID: {sop_id}")
                return None

            # Process fields
            category = record.get(SOPFieldMapping.CATEGORY())
            
            keywords_raw = record.get(SOPFieldMapping.KEYWORDS(), "")
            tags = [k.strip() for k in keywords_raw.split(",")] if keywords_raw else []

            # IS_PUBLISHED may not exist in Ragic, default to True
            is_published_field = SOPFieldMapping.IS_PUBLISHED()
            is_published_raw = record.get(is_published_field) if is_published_field else None
            if is_published_raw is None:
                is_published = True  # Default to published
            else:
                is_published = str(is_published_raw).lower() in ("true", "1", "yes", "y")

            ragic_id = int(record.get("_ragicId", 0))

            return {
                "ragic_id": ragic_id,
                "sop_id": sop_id,
                "title": title,
                "content": content or "",
                "category": category,
                "tags": tags,
                "is_published": is_published,
                "metadata_": {
                    "ragic_record_id": ragic_id, # Keep for backward compat if needed
                    "source": "ragic_sync",
                    "synced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
            }
        except Exception as e:
            logger.error(f"Error mapping record: {e}")
            return None

    async def _post_sync_hook(self, session: AsyncSession, instance: SOPDocument, is_created: bool) -> None:
        """
        Generate vector embedding after sync.
        """
        try:
            await self.vector_service.index_document(instance, session)
        except Exception as e:
            logger.error(f"Failed to index document {instance.id}: {e}")

# Helper singleton
_sop_sync_service: Optional[SOPSyncService] = None

def get_sop_sync_service() -> SOPSyncService:
    global _sop_sync_service
    if _sop_sync_service is None:
        _sop_sync_service = SOPSyncService()
    return _sop_sync_service

