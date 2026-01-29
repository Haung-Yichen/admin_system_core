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

__all__ = [
    "RagicField",
    "RagicModel",
    "RagicService",
    "RagicRepository",
    "get_ragic_service",
]
