"""
Core Ragic ORM Layer.

Provides a framework-level abstraction for Ragic API access,
similar to SQLAlchemy for databases.

Components:
    - RagicField: Field descriptor for defining form columns
    - RagicModel: Base class for defining Ragic forms
    - RagicService: Low-level HTTP client
    - RagicRepository: High-level data access pattern
"""

from core.ragic.fields import RagicField
from core.ragic.models import RagicModel
from core.ragic.service import RagicService, get_ragic_service
from core.ragic.repository import RagicRepository
from core.ragic.columns import (
    RagicFormConfig,
    get_form_config,
    get_form_url,
    get_sheet_path,
    get_field_id,
    get_all_field_ids,
    get_account_form,
    get_leave_form,
    get_leave_type_form,
)

__all__ = [
    "RagicField",
    "RagicModel",
    "RagicService",
    "RagicRepository",
    "get_ragic_service",
    # Column config
    "RagicFormConfig",
    "get_form_config",
    "get_form_url",
    "get_sheet_path",
    "get_field_id",
    "get_all_field_ids",
    "get_account_form",
    "get_leave_form",
    "get_leave_type_form",
]
