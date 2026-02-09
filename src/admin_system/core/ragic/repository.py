"""
Ragic Repository Pattern.

Provides high-level data access for Ragic models,
similar to SQLAlchemy's Session/Repository pattern.
"""

import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

import httpx

from core.ragic.models import RagicModel
from core.ragic.service import RagicService

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=RagicModel)


class RagicRepository(Generic[T]):
    """
    Repository for accessing Ragic form data.
    
    Provides high-level operations that automatically handle:
    - Field ID translation (Python attr -> Ragic ID)
    - Model instantiation from raw API responses
    - Payload construction for create/update operations
    
    Example:
        class Account(RagicModel):
            _sheet_path = "/HSIBAdmSys/ychn-test/11"
            emails = RagicField("1005977", "Emails")
            name = RagicField("1005975", "Name")
        
        repo = RagicRepository(Account)
        accounts = await repo.find_all()
        acc = await repo.find_by(emails="test@example.com")
    """
    
    def __init__(
        self,
        model_cls: Type[T],
        service: RagicService,
    ) -> None:
        """
        Initialize repository.
        
        Args:
            model_cls: The RagicModel subclass to work with.
            service: RagicService instance (required).
        """
        self._model_cls = model_cls
        self._service = service
    
    @property
    def sheet_path(self) -> str:
        """Get the sheet path from the model class."""
        return self._model_cls.get_sheet_path()
    
    async def find_all(
        self,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[T]:
        """
        Fetch all records from the sheet.
        
        Args:
            limit: Maximum number of records.
            offset: Starting offset.
        
        Returns:
            List of model instances.
        """
        records = await self._service.get_records(
            self.sheet_path,
            limit=limit,
            offset=offset,
        )
        
        return [self._model_cls.from_ragic_record(r) for r in records]
    
    async def find_by(self, **filters: Any) -> List[T]:
        """
        Find records matching the given filters.
        
        Filters are specified using Python attribute names,
        which are automatically translated to Ragic field IDs.
        
        Args:
            **filters: Attribute name/value pairs to filter by.
        
        Returns:
            List of matching model instances.
        
        Example:
            employees = await repo.find_by(email="test@example.com")
        """
        # Translate attribute names to field IDs
        ragic_filters: Dict[str, Any] = {}
        
        for attr_name, value in filters.items():
            field_id = self._model_cls.get_field_id(attr_name)
            if field_id:
                ragic_filters[field_id] = value
            else:
                logger.warning(f"Unknown field: {attr_name}")
        
        records = await self._service.get_records(
            self.sheet_path,
            filters=ragic_filters,
        )
        
        return [self._model_cls.from_ragic_record(r) for r in records]
    
    async def find_one_by(self, **filters: Any) -> Optional[T]:
        """
        Find a single record matching the filters.
        
        Args:
            **filters: Attribute name/value pairs to filter by.
        
        Returns:
            First matching model instance or None.
        """
        results = await self.find_by(**filters)
        return results[0] if results else None
    
    async def get(self, record_id: int) -> Optional[T]:
        """
        Get a record by its Ragic ID.
        
        Args:
            record_id: The Ragic record ID.
        
        Returns:
            Model instance or None.
        """
        record = await self._service.get_record(self.sheet_path, record_id)
        
        if record:
            return self._model_cls.from_ragic_record(record)
        return None
    
    async def create(self, entity: T) -> Optional[T]:
        """
        Create a new record.
        
        Args:
            entity: Model instance to create.
        
        Returns:
            Created entity with ragic_id populated, or None on failure.
        """
        payload = entity.to_ragic_payload()
        
        record_id = await self._service.create_record(self.sheet_path, payload)
        
        if record_id:
            entity.ragic_id = record_id
            logger.info(f"Created {self._model_cls.__name__} with ID {record_id}")
            return entity
        
        return None
    
    async def update(self, entity: T) -> bool:
        """
        Update an existing record.
        
        Args:
            entity: Model instance with ragic_id set.
        
        Returns:
            True if successful.
        """
        if not entity.ragic_id:
            logger.error("Cannot update entity without ragic_id")
            return False
        
        payload = entity.to_ragic_payload()
        
        success = await self._service.update_record(
            self.sheet_path,
            entity.ragic_id,
            payload,
        )
        
        if success:
            logger.info(f"Updated {self._model_cls.__name__} ID {entity.ragic_id}")
        
        return success
    
    async def delete(self, entity: T) -> bool:
        """
        Delete a record.
        
        Args:
            entity: Model instance with ragic_id set.
        
        Returns:
            True if successful.
        """
        if not entity.ragic_id:
            logger.error("Cannot delete entity without ragic_id")
            return False
        
        success = await self._service.delete_record(
            self.sheet_path,
            entity.ragic_id,
        )
        
        if success:
            logger.info(f"Deleted {self._model_cls.__name__} ID {entity.ragic_id}")
        
        return success
    
    async def delete_by_id(self, record_id: int) -> bool:
        """
        Delete a record by ID.
        
        Args:
            record_id: The Ragic record ID.
        
        Returns:
            True if successful.
        """
        return await self._service.delete_record(self.sheet_path, record_id)
