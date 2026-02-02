"""
Core Ragic ORM Layer.

Provides a framework-level abstraction for Ragic API access,
similar to SQLAlchemy for databases.

Components:
    - RagicRegistry: Centralized configuration management (NEW)
    - SyncStrategy: Enum for sync strategies (NEW)
    - GenericRagicService: Form-agnostic service (NEW)
    - RagicField: Field descriptor for defining form columns
    - RagicModel: Base class for defining Ragic forms
    - RagicService: Low-level HTTP client
    - RagicRepository: High-level data access pattern
"""

# New Registry Pattern (recommended)
from core.ragic.enums import SyncStrategy
from core.ragic.exceptions import (
    RagicError,
    RagicConfigurationError,
    RagicConnectionError,
    RagicValidationError,
)
from core.ragic.registry import (
    RagicRegistry,
    get_ragic_registry,
    reset_ragic_registry,
)
from core.ragic.registry_models import (
    FormConfig,
    GlobalSettings,
    RagicRegistryConfig,
)
from core.ragic.service_factory import (
    GenericRagicService,
    RagicServiceFactory,
    BaseStrategyHandler,
    RepositoryHandler,
    get_ragic_service_factory,
    create_ragic_service,
)

# Core ORM components
from core.ragic.fields import RagicField
from core.ragic.models import RagicModel
from core.ragic.service import RagicService, get_ragic_service
from core.ragic.repository import RagicRepository

# Legacy column config (deprecated - use RagicRegistry instead)
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
    get_sop_form,
    get_user_form,
)

# Sync infrastructure
from core.ragic.sync_base import (
    BaseRagicSyncService,
    RagicSyncManager,
    SyncResult,
    SyncServiceInfo,
    get_sync_manager,
    reset_sync_manager,
)

__all__ = [
    # === New Registry Pattern (recommended) ===
    "SyncStrategy",
    "RagicRegistry",
    "get_ragic_registry",
    "reset_ragic_registry",
    "FormConfig",
    "GlobalSettings",
    "RagicRegistryConfig",
    "GenericRagicService",
    "RagicServiceFactory",
    "BaseStrategyHandler",
    "RepositoryHandler",
    "get_ragic_service_factory",
    "create_ragic_service",
    # Exceptions
    "RagicError",
    "RagicConfigurationError",
    "RagicConnectionError",
    "RagicValidationError",
    # === Core ORM ===
    "RagicField",
    "RagicModel",
    "RagicService",
    "RagicRepository",
    "get_ragic_service",
    # === Legacy column config (deprecated) ===
    "RagicFormConfig",
    "get_form_config",
    "get_form_url",
    "get_sheet_path",
    "get_field_id",
    "get_all_field_ids",
    "get_account_form",
    "get_leave_form",
    "get_leave_type_form",
    "get_sop_form",
    "get_user_form",
    # === Sync infrastructure ===
    "BaseRagicSyncService",
    "RagicSyncManager",
    "SyncResult",
    "SyncServiceInfo",
    "get_sync_manager",
    "reset_sync_manager",
]
