"""
User Sync Service.

Handles synchronization of User identity data between Ragic (Master) and
local PostgreSQL (Read-Replica/Cache).

Data Flow Strategy:
    - WRITE-THROUGH: Write to Ragic first, then sync to local DB immediately
    - WEBHOOK SYNC: Ragic changes trigger webhook -> sync to local DB

Security Note:
    - Ragic stores data in PLAIN TEXT (for admin operations)
    - Local DB uses AES-256-GCM ENCRYPTION with blind indexes
    - This service handles the encryption/decryption transformation

Field Mapping (Ragic -> Local):
    - Ragic stores plain email, line_user_id for admin visibility
    - Local DB encrypts email, line_user_id and stores hashes for lookup

Design Principles:
    - NO global HTTP client access
    - HTTP client provided via method injection for sync operations
    - Stateless service pattern
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from uuid import UUID

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_thread_local_session
from core.models import User
from core.ragic import get_user_form
from core.ragic.service import RagicService, create_ragic_service
from core.ragic.sync_base import BaseRagicSyncService, SyncResult
from core.security import generate_blind_index

logger = logging.getLogger(__name__)


# =============================================================================
# Ragic Field Mapping
# =============================================================================


class RagicUserFieldMapping:
    """
    Ragic Field ID mappings for the User Identity form.
    
    Loads field IDs from ragic_registry.json via the backward-compatible shim.
    """
    
    _config = get_user_form()
    
    # === Primary Identification ===
    LOCAL_DB_ID = _config.field("LOCAL_DB_ID")        # 1006070
    LINE_USER_ID = _config.field("LINE_USER_ID")      # 1006071 (Key Field)
    LINE_USER_ID_HASH = _config.field("LINE_USER_ID_HASH")  # 1006072
    
    # === Contact Info ===
    EMAIL = _config.field("EMAIL")                    # 1006073
    EMAIL_HASH = _config.field("EMAIL_HASH")          # 1006074
    
    # === Employee Link ===
    RAGIC_EMPLOYEE_ID = _config.field("RAGIC_EMPLOYEE_ID")  # 1006075
    
    # === Profile ===
    DISPLAY_NAME = _config.field("DISPLAY_NAME")      # 1006076
    IS_ACTIVE = _config.field("IS_ACTIVE")            # 1006077
    
    # === Timestamps ===
    LAST_LOGIN_AT = _config.field("LAST_LOGIN_AT")    # 1006078
    CREATED_AT = _config.field("CREATED_AT")          # 1006079
    UPDATED_AT = _config.field("UPDATED_AT")          # 1006080


Fields = RagicUserFieldMapping


# =============================================================================
# Pydantic Schemas for Data Validation
# =============================================================================


class RagicUserRecordSchema(BaseModel):
    """
    Pydantic schema for validating Ragic User records.
    
    Note: All fields from Ragic are PLAIN TEXT.
    This schema validates before transformation to encrypted local storage.
    
    Important: ragic_id can be None when Ragic returns 0 (a known Ragic quirk).
    In such cases, we use local_db_id for record identification.
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
    )
    
    # Required fields
    ragic_id: Optional[int] = Field(None, description="Ragic internal record ID (may be 0/None)")
    line_user_id: str = Field(..., min_length=1, description="LINE User ID (plain text)")
    
    # Optional fields with defaults
    local_db_id: Optional[str] = Field(None, description="Local DB UUID as string")
    line_user_id_hash: Optional[str] = Field(None, description="Blind index hash")
    email: Optional[str] = Field(None, description="Email (plain text)")
    email_hash: Optional[str] = Field(None, description="Blind index hash")
    ragic_employee_id: Optional[str] = Field(None, description="Employee reference")
    display_name: Optional[str] = Field(None, description="LINE display name")
    is_active: bool = Field(True, description="Account active status")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: Optional[datetime] = Field(None, description="Created timestamp")
    updated_at: Optional[datetime] = Field(None, description="Updated timestamp")
    
    @field_validator("is_active", mode="before")
    @classmethod
    def parse_boolean(cls, v: Any) -> bool:
        """Convert Ragic boolean values (0/1, "", "1") to Python bool."""
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes", "on")
        return True  # Default to active
    
    @field_validator("last_login_at", "created_at", "updated_at", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> Optional[datetime]:
        """Parse datetime from various formats."""
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                # Try ISO format first
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except ValueError:
                try:
                    # Try Ragic format (YYYY-MM-DD HH:MM:SS)
                    return datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        # Try date only
                        return datetime.strptime(v, "%Y-%m-%d")
                    except ValueError:
                        logger.warning(f"Could not parse datetime: {v}")
                        return None
        return None


class UserRagicPayload(BaseModel):
    """
    Payload schema for writing User data TO Ragic.
    
    All values must be PLAIN TEXT (no encryption).
    """
    
    local_db_id: str = Field(..., description="Local DB UUID as string")
    line_user_id: str = Field(..., description="LINE User ID (plain)")
    line_user_id_hash: str = Field(..., description="Blind index hash")
    email: str = Field(..., description="Email (plain)")
    email_hash: str = Field(..., description="Blind index hash")
    ragic_employee_id: Optional[str] = Field(None, description="Employee reference")
    display_name: Optional[str] = Field(None, description="LINE display name")
    is_active: bool = Field(True, description="Account active status")
    last_login_at: Optional[datetime] = Field(None)
    created_at: Optional[datetime] = Field(None)
    updated_at: Optional[datetime] = Field(None)
    
    def to_ragic_dict(self) -> Dict[str, Any]:
        """
        Convert to Ragic API format (field IDs as keys).
        
        Returns:
            Dict with Ragic field IDs as keys.
        """
        data = {
            Fields.LOCAL_DB_ID: self.local_db_id,
            Fields.LINE_USER_ID: self.line_user_id,
            Fields.LINE_USER_ID_HASH: self.line_user_id_hash,
            Fields.EMAIL: self.email,
            Fields.EMAIL_HASH: self.email_hash,
            Fields.IS_ACTIVE: "1" if self.is_active else "0",
        }
        
        # Optional fields
        if self.ragic_employee_id:
            data[Fields.RAGIC_EMPLOYEE_ID] = self.ragic_employee_id
        if self.display_name:
            data[Fields.DISPLAY_NAME] = self.display_name
        if self.last_login_at:
            data[Fields.LAST_LOGIN_AT] = self.last_login_at.strftime("%Y-%m-%d %H:%M:%S")
        if self.created_at:
            data[Fields.CREATED_AT] = self.created_at.strftime("%Y-%m-%d %H:%M:%S")
        if self.updated_at:
            data[Fields.UPDATED_AT] = self.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        
        return data


# =============================================================================
# Sync Service
# =============================================================================


class UserSyncService(BaseRagicSyncService[User]):
    """
    Ragic Sync Service for User Identity records.
    
    Responsibilities:
        - Sync records FROM Ragic TO local DB (Full sync, Webhook sync)
        - Transform data: Plain text (Ragic) -> Encrypted (Local DB)
        - Handle ragic_id tracking for sync state
    
    Note:
        Writing TO Ragic is handled by AuthService (Write-Through pattern).
        This service only handles the reverse direction (Ragic -> Local).
    
    Sync Logic:
        User records may already exist locally (created via AuthService) before
        they have a ragic_id. The sync uses multi-key lookup:
        1. First try by ragic_id (normal sync scenario)
        2. Then try by UUID (local_db_id stored in Ragic)
        3. Finally try by line_user_id_hash (for records created locally)
    
    Design:
        This is a stateless service - it does NOT hold HTTP clients.
        HTTP clients are passed via method injection to sync methods.
    """
    
    def __init__(self) -> None:
        """Initialize UserSyncService (no HTTP client needed)."""
        super().__init__(User)
        self._form_config = get_user_form()
    
    def get_ragic_config(self) -> Dict[str, Any]:
        """Return Ragic form configuration."""
        return {
            "url": self._form_config.url,
            "sheet_path": self._form_config.sheet_path,
        }
    
    def get_unique_field(self) -> str:
        """Use ragic_id for upsert conflict detection."""
        return "ragic_id"
    
    async def sync_all_data(
        self,
        http_client: httpx.AsyncClient,
    ) -> SyncResult:
        """
        Override base sync to add HARD DELETE for removed records.
        
        Args:
            http_client: HTTP client for API requests (REQUIRED).
        
        Sync Strategy:
        1. Fetch all records from Ragic
        2. Upsert each Ragic record to local DB
        3. Find local records NOT in Ragic (by UUID comparison)
        4. HARD DELETE those orphaned local records
        
        This ensures Ragic is the single source of truth (Master).
        """
        import time
        from sqlalchemy import select, delete
        from uuid import UUID as UUIDType
        
        start_time = time.time()
        result = SyncResult()
        
        config = self.get_ragic_config()
        form_url = config.get("url")
        
        if not form_url:
            logger.error("Ragic URL not configured")
            result.errors = 1
            result.error_messages.append("Ragic URL not configured")
            return result
        
        logger.info(f"Starting full sync (with delete) from {form_url}")
        
        try:
            # Fetch all records from Ragic
            ragic_service = self._create_ragic_service(http_client)
            records = await ragic_service.get_records_by_url(
                form_url,
                params={"naming": "EID"}
            )
            
            if records is None:
                records = []
            
            logger.info(f"Fetched {len(records)} records from Ragic")
            
            # Pre-collect all UUIDs from Ragic records BEFORE upsert
            # This is the authoritative list of what should exist locally
            ragic_uuids: set[UUIDType] = set()
            for record in records:
                local_db_id = record.get(Fields.LOCAL_DB_ID, "").strip()
                if local_db_id:
                    try:
                        ragic_uuids.add(UUIDType(local_db_id))
                    except ValueError:
                        pass
            
            logger.debug(f"Ragic UUIDs collected: {len(ragic_uuids)} - {ragic_uuids}")
            
            async with get_thread_local_session() as session:
                # Step 1: Upsert all Ragic records
                for record in records:
                    try:
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
                
                # Commit upserts
                await session.commit()
                
                # Step 2: Find and delete orphaned local records
                if ragic_uuids:
                    # Get all local user UUIDs
                    local_query = select(User.id)
                    local_result = await session.execute(local_query)
                    # Ensure UUIDs are proper UUID objects for comparison
                    local_uuids: set[UUIDType] = set()
                    for row in local_result.fetchall():
                        uid = row[0]
                        if isinstance(uid, UUIDType):
                            local_uuids.add(uid)
                        elif isinstance(uid, str):
                            local_uuids.add(UUIDType(uid))
                        else:
                            local_uuids.add(UUIDType(str(uid)))
                    
                    logger.debug(f"Local UUIDs ({len(local_uuids)}): {local_uuids}")
                    logger.debug(f"Ragic UUIDs ({len(ragic_uuids)}): {ragic_uuids}")
                    
                    # Find orphans (in local but not in Ragic)
                    orphan_uuids = local_uuids - ragic_uuids
                    
                    logger.debug(f"Orphan UUIDs (local - ragic): {orphan_uuids}")
                    
                    if orphan_uuids:
                        logger.info(f"Found {len(orphan_uuids)} orphaned records to delete")
                        
                        # Delete orphans
                        for orphan_id in orphan_uuids:
                            try:
                                delete_query = delete(User).where(User.id == orphan_id)
                                await session.execute(delete_query)
                                result.deleted += 1
                                logger.info(f"Deleted orphaned user: {orphan_id}")
                            except Exception as e:
                                logger.error(f"Failed to delete user {orphan_id}: {e}")
                                result.errors += 1
                        
                        await session.commit()
                else:
                    # No valid UUIDs from Ragic - this might be a data issue
                    # Don't delete anything to be safe
                    logger.warning("No valid UUIDs found in Ragic records, skipping delete phase")
                    
        except Exception as e:
            result.errors += 1
            result.error_messages.append(f"Sync failed: {e}")
            logger.exception(f"Full sync failed: {e}")
        
        result.duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Sync completed: {result.synced} synced, "
            f"{result.skipped} skipped, {result.deleted} deleted, "
            f"{result.errors} errors ({result.duration_ms:.0f}ms)"
        )
        
        return result
    
    async def _upsert_record(
        self,
        session: AsyncSession,
        record: Dict[str, Any],
        result: "SyncResult",
        return_instance: bool = False,
    ) -> Optional[User] | bool:
        """
        Override base class to handle multi-key user lookup.
        
        Users may exist locally without ragic_id (created via AuthService).
        We need to find them by multiple keys to avoid duplicate inserts.
        
        Lookup priority:
        1. ragic_id - Normal sync case (record already synced before)
        2. UUID (id) - Record created locally, local_db_id stored in Ragic
        3. line_user_id_hash - Fallback for LINE binding match
        
        Returns:
            If return_instance is True: The model instance or None.
            Otherwise: True if synced, False if skipped.
        """
        from sqlalchemy import select
        from uuid import UUID as UUIDType
        from core.ragic.sync_base import SyncResult
        
        # Map record to model dict
        data = await self.map_record_to_dict(record)
        
        if data is None:
            return None if return_instance else False
        
        ragic_id = data.get("ragic_id")  # May be None if Ragic returned 0
        local_db_id = data.pop("id", None)  # Remove id from data to avoid conflicts
        line_user_id_hash = data.get("line_user_id_hash")
        
        # Remove ragic_id from data if None (don't overwrite valid ragic_id with None)
        if ragic_id is None:
            data.pop("ragic_id", None)
        
        existing_instance = None
        
        # Strategy 1: Find by ragic_id (if valid)
        if ragic_id:
            query = select(User).where(User.ragic_id == ragic_id)
            result_query = await session.execute(query)
            existing_instance = result_query.scalar_one_or_none()
        
        # Strategy 2: Find by UUID (local_db_id from Ragic)
        if not existing_instance and local_db_id:
            try:
                uuid_value = local_db_id if isinstance(local_db_id, UUIDType) else UUIDType(str(local_db_id))
                query = select(User).where(User.id == uuid_value)
                result_query = await session.execute(query)
                existing_instance = result_query.scalar_one_or_none()
                if existing_instance:
                    logger.debug(f"Found user by UUID: {uuid_value}")
            except ValueError:
                logger.warning(f"Invalid UUID format: {local_db_id}")
        
        # Strategy 3: Find by line_user_id_hash (blind index lookup)
        if not existing_instance and line_user_id_hash:
            query = select(User).where(User.line_user_id_hash == line_user_id_hash)
            result_query = await session.execute(query)
            existing_instance = result_query.scalar_one_or_none()
            if existing_instance:
                logger.debug(f"Found user by line_user_id_hash")
        
        is_created = existing_instance is None
        
        if existing_instance:
            # Update existing record
            for key, value in data.items():
                if hasattr(existing_instance, key):
                    setattr(existing_instance, key, value)
            instance = existing_instance
            logger.debug(f"Updated existing user (ragic_id={ragic_id})")
        else:
            # Create new record - use Ragic's local_db_id if available
            if local_db_id:
                try:
                    from uuid import UUID as UUIDType
                    uuid_value = local_db_id if isinstance(local_db_id, UUIDType) else UUIDType(str(local_db_id))
                    data["id"] = uuid_value
                    logger.debug(f"Creating user with Ragic-specified UUID: {uuid_value}")
                except ValueError:
                    logger.warning(f"Invalid UUID from Ragic: {local_db_id}, generating new UUID")
            instance = User(**data)
            session.add(instance)
            logger.debug(f"Created new user (ragic_id={ragic_id})")
        
        # Flush to persist changes
        await session.flush()
        
        # Post-sync hook
        await self._post_sync_hook(session, instance, is_created)
        
        if return_instance:
            return instance
        return True
    
    async def map_record_to_dict(self, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map a Ragic record to a dictionary suitable for User model.
        
        Transformation Logic:
            - Ragic stores PLAIN TEXT email and line_user_id
            - Local DB expects ENCRYPTED values (handled by EncryptedType)
            - We pass plain values; SQLAlchemy EncryptedType encrypts on save
            - We REGENERATE blind index hashes to ensure consistency
        
        Args:
            record: Raw Ragic record with field IDs as keys.
        
        Returns:
            Dictionary with User model field names, or None to skip.
        """
        try:
            # Extract ragic_id
            # Note: Ragic sometimes returns _ragicId: 0 for valid records
            # We handle this by using local_db_id (UUID) for identification
            ragic_id = record.get("_ragicId")
            local_db_id_str = record.get(Fields.LOCAL_DB_ID, "").strip()
            
            # Skip only if BOTH ragic_id is missing/0 AND no local_db_id
            if not ragic_id and not local_db_id_str:
                logger.warning("Record missing both _ragicId and local_db_id, skipping")
                return None
            
            # Extract and validate fields
            line_user_id = record.get(Fields.LINE_USER_ID, "").strip()
            if not line_user_id:
                logger.warning(f"Record {ragic_id or local_db_id_str} missing line_user_id, skipping")
                return None
            
            email = record.get(Fields.EMAIL, "").strip()
            if not email:
                logger.warning(f"Record {ragic_id or local_db_id_str} missing email, skipping")
                return None
            
            # Build validated schema
            # Use ragic_id if valid (> 0), otherwise None
            schema = RagicUserRecordSchema(
                ragic_id=int(ragic_id) if ragic_id else None,
                line_user_id=line_user_id,
                local_db_id=local_db_id_str or None,
                email=email,
                ragic_employee_id=record.get(Fields.RAGIC_EMPLOYEE_ID, "").strip() or None,
                display_name=record.get(Fields.DISPLAY_NAME, "").strip() or None,
                is_active=record.get(Fields.IS_ACTIVE, "1"),
                last_login_at=record.get(Fields.LAST_LOGIN_AT, ""),
                created_at=record.get(Fields.CREATED_AT, ""),
                updated_at=record.get(Fields.UPDATED_AT, ""),
            )
            
            # IMPORTANT: Regenerate blind index hashes from plain text values
            # This ensures consistency even if Ragic hashes are outdated
            email_hash = generate_blind_index(schema.email)
            line_user_id_hash = generate_blind_index(schema.line_user_id)
            
            # Build model dictionary
            # Note: email and line_user_id are passed as plain text
            # EncryptedType will encrypt them on database save
            model_dict: Dict[str, Any] = {
                "ragic_id": schema.ragic_id,
                "email": schema.email,
                "email_hash": email_hash,
                "line_user_id": schema.line_user_id,
                "line_user_id_hash": line_user_id_hash,
                "ragic_employee_id": schema.ragic_employee_id,
                "display_name": schema.display_name,
                "is_active": schema.is_active,
                "last_login_at": schema.last_login_at,
            }
            
            # Handle local_db_id if present (for existing records)
            if schema.local_db_id:
                try:
                    model_dict["id"] = UUID(schema.local_db_id)
                except ValueError:
                    logger.warning(f"Invalid UUID in local_db_id: {schema.local_db_id}")
            
            logger.debug(
                f"Mapped Ragic record {ragic_id} for user (email: ***@***)"
            )
            return model_dict
            
        except Exception as e:
            logger.error(f"Failed to map Ragic record: {e}")
            return None
    
    async def find_user_by_ragic_id(self, ragic_id: int) -> Optional[User]:
        """
        Find a local User by Ragic ID.
        
        Args:
            ragic_id: The Ragic record ID.
        
        Returns:
            User instance or None.
        """
        from sqlalchemy import select
        
        async with get_thread_local_session() as session:
            result = await session.execute(
                select(User).where(User.ragic_id == ragic_id)
            )
            return result.scalar_one_or_none()
    
    async def find_user_by_line_user_id(self, line_user_id: str) -> Optional[User]:
        """
        Find a local User by LINE user ID using blind index.
        
        Args:
            line_user_id: The LINE user ID (plain text).
        
        Returns:
            User instance or None.
        """
        from sqlalchemy import select
        
        line_id_hash = generate_blind_index(line_user_id)
        
        async with get_thread_local_session() as session:
            result = await session.execute(
                select(User).where(User.line_user_id_hash == line_id_hash)
            )
            return result.scalar_one_or_none()


# =============================================================================
# Ragic Write Operations (for AuthService)
# =============================================================================


class UserRagicWriter:
    """
    Handles writing User data TO Ragic (Master).
    
    This is the "Write" part of the Write-Through strategy:
    1. Prepare payload with plain text values
    2. Create/Update record in Ragic
    3. Return ragic_id for local DB sync
    
    Security Note:
        - Email and LINE ID are sent as PLAIN TEXT to Ragic
        - This is intentional for admin visibility
        - Local DB remains encrypted
    
    Design:
        HTTP client is provided via method injection, not held as instance state.
        This ensures proper event loop binding and clean resource management.
    """
    
    def __init__(self) -> None:
        """Initialize UserRagicWriter (stateless, no HTTP client)."""
        self._form_config = get_user_form()
    
    def _create_ragic_service(self, http_client: httpx.AsyncClient) -> RagicService:
        """Create a RagicService with the provided HTTP client."""
        return create_ragic_service(http_client)
    
    async def create_user_in_ragic(
        self,
        http_client: httpx.AsyncClient,
        local_db_id: UUID,
        email: str,
        line_user_id: str,
        ragic_employee_id: Optional[str] = None,
        display_name: Optional[str] = None,
    ) -> Optional[int]:
        """
        Create a new User record in Ragic.
        
        Args:
            http_client: HTTP client for API requests (REQUIRED).
            local_db_id: The local database UUID.
            email: Plain text email.
            line_user_id: Plain text LINE user ID.
            ragic_employee_id: Optional employee reference.
            display_name: Optional display name.
        
        Returns:
            Ragic record ID (_ragicId) or None on failure.
        """
        now = datetime.now(timezone.utc)
        
        payload = UserRagicPayload(
            local_db_id=str(local_db_id),
            line_user_id=line_user_id,
            line_user_id_hash=generate_blind_index(line_user_id),
            email=email,
            email_hash=generate_blind_index(email),
            ragic_employee_id=ragic_employee_id,
            display_name=display_name,
            is_active=True,
            last_login_at=now,
            created_at=now,
            updated_at=now,
        )
        
        logger.info(f"Creating user in Ragic (local_id: {local_db_id})")
        
        try:
            ragic_service = self._create_ragic_service(http_client)
            result = await ragic_service.create_record_by_url(
                self._form_config.url,
                payload.to_ragic_dict(),
            )
            
            # Ragic returns 'ragicId' (camelCase) in the response root
            # and '_ragicId' in the nested 'data' object
            ragic_id = None
            if result:
                if "ragicId" in result:
                    ragic_id = int(result["ragicId"])
                elif "_ragicId" in result:
                    ragic_id = int(result["_ragicId"])
                elif "data" in result and "_ragicId" in result["data"]:
                    ragic_id = int(result["data"]["_ragicId"])
            
            if ragic_id:
                logger.info(f"Created user in Ragic: ragic_id={ragic_id}")
                return ragic_id
            
            logger.error(f"Ragic create failed: no ragicId in response. Response: {result}")
            return None
            
        except Exception as e:
            logger.error(f"Failed to create user in Ragic: {e}")
            return None
    
    async def update_user_in_ragic(
        self,
        http_client: httpx.AsyncClient,
        ragic_id: int,
        local_db_id: UUID,
        email: str,
        line_user_id: str,
        ragic_employee_id: Optional[str] = None,
        display_name: Optional[str] = None,
        is_active: bool = True,
    ) -> bool:
        """
        Update an existing User record in Ragic.
        
        Args:
            http_client: HTTP client for API requests (REQUIRED).
            ragic_id: The Ragic record ID to update.
            local_db_id: The local database UUID.
            email: Plain text email.
            line_user_id: Plain text LINE user ID.
            ragic_employee_id: Optional employee reference.
            display_name: Optional display name.
            is_active: Account active status.
        
        Returns:
            True if successful.
        """
        now = datetime.now(timezone.utc)
        
        payload = UserRagicPayload(
            local_db_id=str(local_db_id),
            line_user_id=line_user_id,
            line_user_id_hash=generate_blind_index(line_user_id),
            email=email,
            email_hash=generate_blind_index(email),
            ragic_employee_id=ragic_employee_id,
            display_name=display_name,
            is_active=is_active,
            updated_at=now,
        )
        
        logger.info(f"Updating user in Ragic: ragic_id={ragic_id}")
        
        try:
            ragic_service = self._create_ragic_service(http_client)
            success = await ragic_service.update_record(
                self._form_config.sheet_path,
                ragic_id,
                payload.to_ragic_dict(),
            )
            
            if success:
                logger.info(f"Updated user in Ragic: ragic_id={ragic_id}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to update user in Ragic: {e}")
            return False
    
    async def find_user_in_ragic_by_line_id(
        self,
        http_client: httpx.AsyncClient,
        line_user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Find a user in Ragic by LINE user ID.
        
        Uses Ragic's where filter with the key field.
        
        Args:
            http_client: HTTP client for API requests (REQUIRED).
            line_user_id: The LINE user ID to search for.
        
        Returns:
            Ragic record dict or None.
        """
        try:
            # Ragic filter by key field (line_user_id)
            ragic_service = self._create_ragic_service(http_client)
            records = await ragic_service.get_records(
                self._form_config.sheet_path,
                filters={Fields.LINE_USER_ID: line_user_id},
                limit=1,
            )
            
            if records and len(records) > 0:
                return records[0]
            return None
            
        except Exception as e:
            logger.error(f"Failed to find user in Ragic: {e}")
            return None


# =============================================================================
# Singleton Access
# =============================================================================


_user_sync_service: Optional[UserSyncService] = None
_user_ragic_writer: Optional[UserRagicWriter] = None


def get_user_sync_service() -> UserSyncService:
    """Get singleton UserSyncService instance."""
    global _user_sync_service
    if _user_sync_service is None:
        _user_sync_service = UserSyncService()
    return _user_sync_service


def get_user_ragic_writer() -> UserRagicWriter:
    """Get singleton UserRagicWriter instance."""
    global _user_ragic_writer
    if _user_ragic_writer is None:
        _user_ragic_writer = UserRagicWriter()
    return _user_ragic_writer


def reset_user_sync_service() -> None:
    """Reset singletons (for testing)."""
    global _user_sync_service, _user_ragic_writer
    _user_sync_service = None
    _user_ragic_writer = None
