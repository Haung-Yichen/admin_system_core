"""
Ragic Sync Base Infrastructure.

Provides abstract base class for Ragic sync services and a centralized
SyncManager for coordinating all module syncs.

This is part of the core framework - modules should inherit from
BaseRagicSyncService and register with SyncManager.
"""

import asyncio
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Base, get_thread_local_session
from core.ragic.service import RagicService, get_ragic_service

logger = logging.getLogger(__name__)


# Type variable for SQLAlchemy model
ModelT = TypeVar("ModelT", bound=Base)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class SyncResult:
    """Result of a sync operation."""
    
    synced: int = 0
    skipped: int = 0
    errors: int = 0
    deleted: int = 0
    duration_ms: float = 0.0
    error_messages: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "synced": self.synced,
            "skipped": self.skipped,
            "errors": self.errors,
            "deleted": self.deleted,
            "duration_ms": self.duration_ms,
            "error_messages": self.error_messages[:10],  # Limit errors
        }


@dataclass
class SyncServiceInfo:
    """Metadata about a registered sync service."""
    
    key: str  # Unique identifier (e.g., "chatbot_sop", "administrative_account")
    name: str  # Human-readable name
    service: "BaseRagicSyncService"
    module_name: str
    auto_sync_on_startup: bool = True
    last_sync_time: Optional[datetime] = None
    last_sync_result: Optional[SyncResult] = None
    status: str = "idle"  # idle, syncing, error


# =============================================================================
# Abstract Base Class
# =============================================================================


class BaseRagicSyncService(ABC, Generic[ModelT]):
    """
    Abstract base class for Ragic sync services.
    
    Provides common functionality for:
    - Fetching records from Ragic API
    - Mapping records to SQLAlchemy models
    - Upserting records to local database
    - Single record sync (for webhooks)
    - Full table sync
    
    Subclasses can either:
    1. Pass form_key to constructor (uses RagicRegistry - recommended)
    2. Override get_ragic_config() (legacy approach)
    
    Subclasses must implement:
    - map_record_to_dict(): Transform Ragic record to model dict
    
    Optionally override:
    - get_unique_field(): Return the field name used for upsert conflict
    - _post_sync_hook(): Called after each record is synced
    """
    
    def __init__(
        self,
        model_class: Type[ModelT],
        ragic_service: Optional[RagicService] = None,
        form_key: Optional[str] = None,
    ) -> None:
        self._model_class = model_class
        self._ragic_service = ragic_service or get_ragic_service()
        self._form_key = form_key
        self._registry = None
        
        # If form_key is provided, load config from registry
        if form_key:
            from core.ragic.registry import get_ragic_registry
            self._registry = get_ragic_registry()
            self._form_config = self._registry.get_form_config(form_key)
        else:
            self._form_config = None
        
    @abstractmethod
    async def map_record_to_dict(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map a Ragic record to a dictionary suitable for model creation.
        
        Args:
            record: Raw Ragic record with field IDs as keys.
        
        Returns:
            Dictionary with model field names, or None to skip this record.
        """
        pass
    
    def get_ragic_config(self) -> Dict[str, Any]:
        """
        Return Ragic form configuration.
        
        If form_key was provided to constructor, returns config from registry.
        Otherwise, subclasses must override this method.
        
        Returns:
            dict with 'url' and 'sheet_path' keys.
        """
        if self._form_config:
            return {
                "url": f"{self._registry.base_url}{self._form_config.ragic_path}",
                "sheet_path": self._form_config.ragic_path,
            }
        
        raise NotImplementedError(
            "Subclasses must either pass form_key to constructor "
            "or override get_ragic_config()"
        )
    
    def get_field_id(self, field_name: str) -> Optional[str]:
        """
        Get the Ragic field ID for a logical field name.
        
        Only available when form_key is provided to constructor.
        
        Args:
            field_name: The logical field name (e.g., "EMPLOYEE_ID").
        
        Returns:
            The Ragic field ID or None if not configured.
        """
        if self._form_config:
            return self._form_config.get_field_id(field_name)
        return None
    
    def get_unique_field(self) -> str:
        """
        Return the field name used for upsert conflict detection.
        Default is 'ragic_id'. Override if using a different key.
        """
        return "ragic_id"
    
    async def _post_sync_hook(
        self,
        session: AsyncSession,
        instance: ModelT,
        is_created: bool,
    ) -> None:
        """
        Called after each record is synced.
        
        Override to add custom logic (e.g., generating embeddings).
        
        Args:
            session: Database session.
            instance: The synced model instance.
            is_created: True if newly created, False if updated.
        """
        pass
    
    async def close(self) -> None:
        """Cleanup resources."""
        if self._ragic_service:
            await self._ragic_service.close()
    
    # =========================================================================
    # Sync Operations
    # =========================================================================
    
    async def sync_all_data(self) -> SyncResult:
        """
        Sync all records from Ragic to local database.
        
        Returns:
            SyncResult with statistics.
        """
        start_time = time.time()
        result = SyncResult()
        
        config = self.get_ragic_config()
        form_url = config.get("url")
        
        if not form_url:
            logger.error("Ragic URL not configured")
            result.errors = 1
            result.error_messages.append("Ragic URL not configured")
            return result
        
        logger.info(f"Starting full sync from {form_url}")
        
        try:
            # Fetch all records from Ragic (with naming=EID to get field IDs)
            records = await self._ragic_service.get_records_by_url(
                form_url, 
                params={"naming": "EID"}
            )
            
            if not records:
                logger.warning("No records returned from Ragic")
                return result
            
            logger.info(f"Fetched {len(records)} records from Ragic")
            
            # Process each record
            async with get_thread_local_session() as session:
                for record in records:
                    try:
                        # 使用巢狀交易 (Savepoint)
                        # 如果這筆資料失敗，只會回滾這筆，不會讓整個 Session 壞掉導致後面的資料無法寫入
                        async with session.begin_nested():
                            sync_success = await self._upsert_record(session, record, result)
                            if sync_success:
                                result.synced += 1
                            else:
                                result.skipped += 1
                    except Exception as e:
                        result.errors += 1
                        error_msg = f"Error syncing record {record.get('_ragicId')}: {type(e).__name__}: {e}"
                        result.error_messages.append(error_msg)
                        logger.error(error_msg)
                        # Print full traceback for debugging
                        import traceback
                        logger.debug(f"Full traceback: {traceback.format_exc()}")
                
                # 最後統一提交成功的資料
                await session.commit()
            
        except Exception as e:
            result.errors += 1
            result.error_messages.append(f"Sync failed: {e}")
            logger.exception(f"Full sync failed: {e}")
        
        result.duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Sync completed: {result.synced} synced, "
            f"{result.skipped} skipped, {result.errors} errors "
            f"({result.duration_ms:.0f}ms)"
        )
        
        return result
    
    async def sync_single_record(self, ragic_id: int) -> Optional[ModelT]:
        """
        Sync a single record from Ragic by ID.
        
        Used for webhook-triggered updates.
        
        Args:
            ragic_id: The Ragic record ID.
        
        Returns:
            The synced model instance, or None on failure.
        """
        config = self.get_ragic_config()
        sheet_path = config.get("sheet_path")
        
        if not sheet_path:
            logger.error("Sheet path not configured")
            return None
        
        logger.info(f"Syncing single record: {ragic_id}")
        
        try:
            # Fetch the record
            record = await self._ragic_service.get_record(sheet_path, ragic_id)
            
            if not record:
                logger.warning(f"Record {ragic_id} not found in Ragic")
                return None
            
            # Add ragic_id to record
            record["_ragicId"] = ragic_id
            
            # Upsert to database
            async with get_thread_local_session() as session:
                result = SyncResult()
                instance = await self._upsert_record(session, record, result, return_instance=True)
                await session.commit()
                return instance
                
        except Exception as e:
            logger.exception(f"Failed to sync record {ragic_id}: {e}")
            return None
    
    async def delete_record(self, ragic_id: int) -> bool:
        """
        Delete a record from local database.
        
        Used for webhook-triggered deletions.
        
        Args:
            ragic_id: The Ragic record ID.
        
        Returns:
            True if deleted, False if not found.
        """
        unique_field = self.get_unique_field()
        
        try:
            async with get_thread_local_session() as session:
                # Find the record
                query = select(self._model_class).where(
                    getattr(self._model_class, unique_field) == ragic_id
                )
                result = await session.execute(query)
                instance = result.scalar_one_or_none()
                
                if instance:
                    await session.delete(instance)
                    await session.commit()
                    logger.info(f"Deleted record with {unique_field}={ragic_id}")
                    return True
                else:
                    logger.warning(f"Record with {unique_field}={ragic_id} not found")
                    return False
                    
        except Exception as e:
            logger.exception(f"Failed to delete record {ragic_id}: {e}")
            return False
    
    # =========================================================================
    # Internal Methods
    # =========================================================================
    
    async def _upsert_record(
        self,
        session: AsyncSession,
        record: Dict[str, Any],
        result: SyncResult,
        return_instance: bool = False,
    ) -> Optional[ModelT] | bool:
        """
        Upsert a single record to the database.
        
        Returns:
            If return_instance is True: The model instance or None.
            Otherwise: True if synced, False if skipped.
        """
        # Map record to model dict
        data = await self.map_record_to_dict(record)
        
        if data is None:
            return None if return_instance else False
        
        unique_field = self.get_unique_field()
        unique_value = data.get(unique_field)
        
        if unique_value is None:
            logger.warning(f"Record missing unique field '{unique_field}'")
            return None if return_instance else False
        
        # Check if exists
        query = select(self._model_class).where(
            getattr(self._model_class, unique_field) == unique_value
        )
        existing = await session.execute(query)
        existing_instance = existing.scalar_one_or_none()
        
        is_created = existing_instance is None
        
        if existing_instance:
            # Update existing
            for key, value in data.items():
                if hasattr(existing_instance, key):
                    setattr(existing_instance, key, value)
            instance = existing_instance
        else:
            # Create new
            instance = self._model_class(**data)
            session.add(instance)
        
        # Flush to get ID if new
        await session.flush()
        
        # Post-sync hook (e.g., generate embeddings)
        await self._post_sync_hook(session, instance, is_created)
        
        if return_instance:
            return instance
        return True


# =============================================================================
# Sync Manager (Singleton)
# =============================================================================


class RagicSyncManager:
    """
    Centralized manager for all Ragic sync services.
    
    Features:
    - Registry of all sync services across modules
    - Startup sync coordination
    - Webhook dispatch to appropriate sync service
    - Status monitoring
    
    Usage:
        # In module's on_entry:
        sync_manager = get_sync_manager()
        sync_manager.register(
            key="chatbot_sop",
            name="SOP Knowledge Base",
            service=sop_sync_service,
            module_name="chatbot",
        )
    """
    
    def __init__(self) -> None:
        self._services: Dict[str, SyncServiceInfo] = {}
        self._lock = threading.Lock()
        self._startup_complete = False
    
    def register(
        self,
        key: str,
        name: str,
        service: BaseRagicSyncService,
        module_name: str,
        auto_sync_on_startup: bool = True,
    ) -> None:
        """
        Register a sync service.
        
        Args:
            key: Unique identifier (e.g., "chatbot_sop").
            name: Human-readable name (e.g., "SOP Knowledge Base").
            service: The sync service instance.
            module_name: Owning module name.
            auto_sync_on_startup: Whether to sync on app startup.
        """
        with self._lock:
            self._services[key] = SyncServiceInfo(
                key=key,
                name=name,
                service=service,
                module_name=module_name,
                auto_sync_on_startup=auto_sync_on_startup,
            )
        logger.info(f"Registered sync service: {key} ({name})")
    
    def unregister(self, key: str) -> None:
        """Unregister a sync service."""
        with self._lock:
            if key in self._services:
                del self._services[key]
                logger.info(f"Unregistered sync service: {key}")
    
    def get_service(self, key: str) -> Optional[BaseRagicSyncService]:
        """Get a sync service by key."""
        info = self._services.get(key)
        return info.service if info else None
    
    def get_service_info(self, key: str) -> Optional[SyncServiceInfo]:
        """Get service info by key."""
        return self._services.get(key)
    
    def list_services(self) -> List[Dict[str, Any]]:
        """List all registered services with their status."""
        return [
            {
                "key": info.key,
                "name": info.name,
                "module": info.module_name,
                "status": info.status,
                "last_sync": info.last_sync_time.isoformat() if info.last_sync_time else None,
                "last_result": info.last_sync_result.to_dict() if info.last_sync_result else None,
            }
            for info in self._services.values()
        ]
    
    # =========================================================================
    # Sync Operations
    # =========================================================================
    
    async def sync_service(self, key: str) -> Optional[SyncResult]:
        """
        Trigger sync for a specific service.
        
        Args:
            key: Service key.
        
        Returns:
            SyncResult or None if service not found.
        """
        info = self._services.get(key)
        if not info:
            logger.warning(f"Sync service not found: {key}")
            return None
        
        info.status = "syncing"
        
        try:
            result = await info.service.sync_all_data()
            info.last_sync_time = datetime.now()
            info.last_sync_result = result
            info.status = "idle" if result.errors == 0 else "error"
            return result
            
        except Exception as e:
            logger.exception(f"Sync failed for {key}: {e}")
            info.status = "error"
            error_result = SyncResult(errors=1, error_messages=[str(e)])
            info.last_sync_result = error_result
            return error_result
    
    async def sync_all(self, auto_only: bool = True) -> Dict[str, SyncResult]:
        """
        Sync all registered services.
        
        Args:
            auto_only: If True, only sync services with auto_sync_on_startup=True.
        
        Returns:
            Dict mapping service key to SyncResult.
        """
        results = {}
        
        for key, info in self._services.items():
            if auto_only and not info.auto_sync_on_startup:
                continue
            
            logger.info(f"Running sync for: {key}")
            result = await self.sync_service(key)
            if result:
                results[key] = result
        
        return results
    
    def start_background_sync(self) -> None:
        """
        Start background sync for all registered services.
        
        Runs in a separate thread to avoid blocking app startup.
        """
        if self._startup_complete:
            return
        
        def sync_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                logger.info("Starting background sync for all services...")
                results = loop.run_until_complete(self.sync_all(auto_only=True))
                
                for key, result in results.items():
                    logger.info(
                        f"[{key}] Sync complete: "
                        f"{result.synced} synced, {result.errors} errors"
                    )
                    
            except Exception as e:
                logger.exception(f"Background sync failed: {e}")
                
            finally:
                # Cleanup thread-local database engine
                from core.database import dispose_thread_local_engine
                try:
                    loop.run_until_complete(dispose_thread_local_engine())
                except Exception as e:
                    logger.warning(f"Error disposing thread local engine: {e}")
                
                loop.close()
                self._startup_complete = True
        
        thread = threading.Thread(target=sync_worker, daemon=True, name="RagicSyncWorker")
        thread.start()
        logger.info("Background sync thread started")
    
    # =========================================================================
    # Webhook Operations
    # =========================================================================
    
    async def handle_webhook(
        self,
        key: str,
        ragic_id: int,
        action: str = "update",
    ) -> Optional[SyncResult]:
        """
        Handle a Ragic webhook for a specific service.
        
        Args:
            key: Service key (e.g., "chatbot_sop").
            ragic_id: The Ragic record ID.
            action: "create", "update", or "delete".
        
        Returns:
            SyncResult with single record stats.
        """
        info = self._services.get(key)
        if not info:
            logger.warning(f"Webhook received for unknown service: {key}")
            return None
        
        result = SyncResult()
        
        try:
            if action == "delete":
                success = await info.service.delete_record(ragic_id)
                if success:
                    result.deleted = 1
                else:
                    result.skipped = 1
            else:
                instance = await info.service.sync_single_record(ragic_id)
                if instance:
                    result.synced = 1
                else:
                    result.errors = 1
                    result.error_messages.append(f"Failed to sync record {ragic_id}")
                    
        except Exception as e:
            result.errors = 1
            result.error_messages.append(str(e))
            logger.exception(f"Webhook handling failed for {key}: {e}")
        
        return result


# =============================================================================
# Singleton Access
# =============================================================================


_sync_manager: Optional[RagicSyncManager] = None


def get_sync_manager() -> RagicSyncManager:
    """Get the singleton SyncManager instance."""
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = RagicSyncManager()
    return _sync_manager


def reset_sync_manager() -> None:
    """Reset the singleton (for testing)."""
    global _sync_manager
    _sync_manager = None
