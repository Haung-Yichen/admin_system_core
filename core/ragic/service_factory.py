"""
Ragic Service Factory.

Factory pattern for creating Ragic service instances based on
form configuration and sync strategy.

This module follows the Open/Closed Principle - new strategies can be
added by creating new handler classes without modifying existing code.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from core.ragic.enums import SyncStrategy
from core.ragic.exceptions import RagicConfigurationError
from core.ragic.registry import RagicRegistry, get_ragic_registry
from core.ragic.registry_models import FormConfig
from core.ragic.service import RagicService, get_ragic_service

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Strategy Handlers (Abstract Base)
# =============================================================================


class BaseStrategyHandler(ABC, Generic[T]):
    """
    Abstract base class for sync strategy handlers.
    
    Each strategy implementation handles data operations according to
    its specific sync pattern (RAGIC_MASTER, LOCAL_MASTER, etc.).
    """
    
    def __init__(
        self,
        form_config: FormConfig,
        ragic_service: Optional[RagicService] = None,
        registry: Optional[RagicRegistry] = None,
    ) -> None:
        self._form_config = form_config
        self._ragic_service = ragic_service or get_ragic_service()
        self._registry = registry or get_ragic_registry()
    
    @property
    def form_key(self) -> str:
        """Get the form key."""
        return self._form_config.form_key
    
    @property
    def ragic_path(self) -> str:
        """Get the Ragic sheet path."""
        return self._form_config.ragic_path
    
    @property
    def ragic_url(self) -> str:
        """Get the full Ragic URL."""
        return f"{self._registry.base_url}{self.ragic_path}"
    
    def get_field_id(self, field_name: str) -> str:
        """Get field ID from the form config."""
        return self._form_config.get_field_id_strict(field_name)
    
    def get_field_id_optional(self, field_name: str) -> Optional[str]:
        """Get field ID or None if not found."""
        return self._form_config.get_field_id(field_name)
    
    @abstractmethod
    async def fetch_all(self, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch all records from the data source."""
        pass
    
    @abstractmethod
    async def fetch_one(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single record by ID."""
        pass
    
    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new record."""
        pass
    
    @abstractmethod
    async def update(self, record_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing record."""
        pass
    
    @abstractmethod
    async def delete(self, record_id: int) -> bool:
        """Delete a record."""
        pass
    
    async def close(self) -> None:
        """Cleanup resources."""
        pass


# =============================================================================
# Repository Strategy Handler
# =============================================================================


class RepositoryHandler(BaseStrategyHandler[Dict[str, Any]]):
    """
    Handler for REPOSITORY sync strategy.
    
    Direct read/write to Ragic without local database caching.
    All operations go directly to/from Ragic API.
    
    Use cases:
        - Transactional forms (leave requests, approvals)
        - Forms where real-time data is critical
        - Forms without need for local caching
    """
    
    async def fetch_all(
        self, 
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all records directly from Ragic.
        
        Args:
            params: Optional query parameters for filtering.
        
        Returns:
            List of records as dictionaries.
        """
        default_params = {"naming": "EID"}
        if params:
            default_params.update(params)
        
        records = await self._ragic_service.get_records_by_url(
            self.ragic_url,
            params=default_params,
        )
        return records or []
    
    async def fetch_one(self, record_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a single record from Ragic.
        
        Args:
            record_id: The Ragic record ID.
        
        Returns:
            Record dictionary or None if not found.
        """
        record = await self._ragic_service.get_record(
            self.ragic_path,
            record_id,
        )
        if record:
            record["_ragicId"] = record_id
        return record
    
    async def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new record in Ragic.
        
        Args:
            data: Record data with field IDs as keys.
        
        Returns:
            Created record or None on failure.
        """
        result = await self._ragic_service.create_record(
            self.ragic_path,
            data,
        )
        return result
    
    async def update(
        self, 
        record_id: int, 
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update an existing record in Ragic.
        
        Args:
            record_id: The Ragic record ID.
            data: Fields to update with field IDs as keys.
        
        Returns:
            Updated record or None on failure.
        """
        result = await self._ragic_service.update_record(
            self.ragic_path,
            record_id,
            data,
        )
        return result
    
    async def delete(self, record_id: int) -> bool:
        """
        Delete a record from Ragic.
        
        Args:
            record_id: The Ragic record ID.
        
        Returns:
            True if deleted successfully.
        """
        return await self._ragic_service.delete_record(
            self.ragic_path,
            record_id,
        )


# =============================================================================
# Generic Ragic Service (Form-agnostic)
# =============================================================================


class GenericRagicService:
    """
    Generic service for Ragic operations using registry configuration.
    
    This service accepts a form_key and automatically resolves the
    configuration from RagicRegistry. It delegates operations to
    the appropriate strategy handler.
    
    Usage:
        # Create service for a specific form
        service = GenericRagicService("leave_form")
        
        # CRUD operations
        records = await service.fetch_all()
        record = await service.fetch_one(12345)
        created = await service.create({"1005571": "John Doe"})
        updated = await service.update(12345, {"1005575": "approved"})
        deleted = await service.delete(12345)
        
        # Field ID lookups
        field_id = service.get_field_id("EMPLOYEE_NAME")
    """
    
    def __init__(
        self,
        form_key: str,
        ragic_service: Optional[RagicService] = None,
        registry: Optional[RagicRegistry] = None,
    ) -> None:
        """
        Initialize the service for a specific form.
        
        Args:
            form_key: The form key from ragic_registry.json.
            ragic_service: Optional RagicService instance.
            registry: Optional RagicRegistry instance.
        
        Raises:
            RagicConfigurationError: If form_key not found in registry.
        """
        self._registry = registry or get_ragic_registry()
        self._form_config = self._registry.get_form_config(form_key)
        self._ragic_service = ragic_service or get_ragic_service()
        self._handler = self._create_handler()
    
    def _create_handler(self) -> BaseStrategyHandler:
        """Create the appropriate strategy handler."""
        strategy = self._form_config.sync_strategy
        
        handler_map: Dict[SyncStrategy, Type[BaseStrategyHandler]] = {
            SyncStrategy.REPOSITORY: RepositoryHandler,
            # RAGIC_MASTER and LOCAL_MASTER use BaseRagicSyncService pattern
            # HYBRID requires custom implementation per form
        }
        
        handler_class = handler_map.get(strategy)
        
        if handler_class:
            return handler_class(
                form_config=self._form_config,
                ragic_service=self._ragic_service,
                registry=self._registry,
            )
        
        # For strategies that use sync services (RAGIC_MASTER, LOCAL_MASTER, HYBRID),
        # return a basic handler that can still do direct Ragic operations
        return RepositoryHandler(
            form_config=self._form_config,
            ragic_service=self._ragic_service,
            registry=self._registry,
        )
    
    @property
    def form_key(self) -> str:
        """Get the form key."""
        return self._form_config.form_key
    
    @property
    def form_config(self) -> FormConfig:
        """Get the form configuration."""
        return self._form_config
    
    @property
    def sync_strategy(self) -> SyncStrategy:
        """Get the sync strategy."""
        return self._form_config.sync_strategy
    
    @property
    def ragic_url(self) -> str:
        """Get the full Ragic URL."""
        return self._handler.ragic_url
    
    @property
    def ragic_path(self) -> str:
        """Get the Ragic sheet path."""
        return self._form_config.ragic_path
    
    def get_field_id(self, field_name: str) -> str:
        """
        Get the Ragic field ID for a logical field name.
        
        Args:
            field_name: The logical field name (e.g., "EMPLOYEE_NAME").
        
        Returns:
            The Ragic field ID.
        
        Raises:
            RagicConfigurationError: If field not found.
        """
        return self._handler.get_field_id(field_name)
    
    def get_field_id_optional(self, field_name: str) -> Optional[str]:
        """Get field ID or None if not found."""
        return self._handler.get_field_id_optional(field_name)
    
    def get_all_field_ids(self) -> Dict[str, str]:
        """Get all field mappings for this form."""
        return self._form_config.field_mapping.copy()
    
    # =========================================================================
    # CRUD Operations (delegated to handler)
    # =========================================================================
    
    async def fetch_all(
        self, 
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all records."""
        return await self._handler.fetch_all(params)
    
    async def fetch_one(self, record_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a single record by ID."""
        return await self._handler.fetch_one(record_id)
    
    async def create(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new record."""
        return await self._handler.create(data)
    
    async def update(
        self, 
        record_id: int, 
        data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update an existing record."""
        return await self._handler.update(record_id, data)
    
    async def delete(self, record_id: int) -> bool:
        """Delete a record."""
        return await self._handler.delete(record_id)
    
    async def close(self) -> None:
        """Cleanup resources."""
        await self._handler.close()


# =============================================================================
# Factory
# =============================================================================


class RagicServiceFactory:
    """
    Factory for creating Ragic service instances.
    
    Creates the appropriate service/handler based on form configuration
    and sync strategy.
    
    Usage:
        factory = RagicServiceFactory()
        
        # Create a generic service for any form
        leave_service = factory.create("leave_form")
        
        # Create service with custom dependencies
        account_service = factory.create(
            "account_form",
            ragic_service=custom_ragic_service,
        )
    """
    
    def __init__(self, registry: Optional[RagicRegistry] = None) -> None:
        """
        Initialize the factory.
        
        Args:
            registry: Optional RagicRegistry instance.
        """
        self._registry = registry or get_ragic_registry()
    
    def create(
        self,
        form_key: str,
        ragic_service: Optional[RagicService] = None,
    ) -> GenericRagicService:
        """
        Create a service instance for a form.
        
        Args:
            form_key: The form key from ragic_registry.json.
            ragic_service: Optional RagicService instance.
        
        Returns:
            Configured GenericRagicService instance.
        
        Raises:
            RagicConfigurationError: If form_key not found.
        """
        return GenericRagicService(
            form_key=form_key,
            ragic_service=ragic_service,
            registry=self._registry,
        )
    
    def create_handler(
        self,
        form_key: str,
        ragic_service: Optional[RagicService] = None,
    ) -> BaseStrategyHandler:
        """
        Create a raw strategy handler for a form.
        
        Use this when you need direct access to the strategy handler
        without the GenericRagicService wrapper.
        
        Args:
            form_key: The form key.
            ragic_service: Optional RagicService instance.
        
        Returns:
            Strategy handler instance.
        """
        form_config = self._registry.get_form_config(form_key)
        ragic_service = ragic_service or get_ragic_service()
        
        strategy = form_config.sync_strategy
        
        if strategy == SyncStrategy.REPOSITORY:
            return RepositoryHandler(
                form_config=form_config,
                ragic_service=ragic_service,
                registry=self._registry,
            )
        
        # Default to repository handler for direct operations
        return RepositoryHandler(
            form_config=form_config,
            ragic_service=ragic_service,
            registry=self._registry,
        )
    
    def list_available_forms(self) -> List[str]:
        """Get list of all available form keys."""
        return self._registry.list_forms()
    
    def get_form_info(self, form_key: str) -> Dict[str, Any]:
        """
        Get information about a form.
        
        Args:
            form_key: The form key.
        
        Returns:
            Dictionary with form information.
        """
        config = self._registry.get_form_config(form_key)
        return {
            "form_key": config.form_key,
            "description": config.description,
            "sync_strategy": config.sync_strategy.value,
            "ragic_path": config.ragic_path,
            "webhook_key": config.webhook_key,
            "field_count": len(config.field_mapping),
        }


# =============================================================================
# Module-level convenience functions
# =============================================================================


_factory: Optional[RagicServiceFactory] = None


def get_ragic_service_factory() -> RagicServiceFactory:
    """Get the singleton factory instance."""
    global _factory
    if _factory is None:
        _factory = RagicServiceFactory()
    return _factory


def create_ragic_service(form_key: str) -> GenericRagicService:
    """
    Convenience function to create a service for a form.
    
    Args:
        form_key: The form key.
    
    Returns:
        Configured GenericRagicService.
    """
    return get_ragic_service_factory().create(form_key)
