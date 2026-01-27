"""
Ragic Sync Service.

Handles synchronization of data from Ragic (No-Code DB) to local cache tables.
Follows Single Responsibility Principle - only handles fetching and storing data.

Features:
    - Schema introspection to validate field mappings
    - Dynamic table creation if not exists
    - Full upsert sync (insert new, update existing)
    - Email fallback from core User table for records missing email in Ragic
"""

import logging
from typing import Any

import httpx
from sqlalchemy import inspect, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Base, get_thread_local_engine, get_thread_local_session
from core.models import User
from modules.administrative.core.config import AdminSettings, get_admin_settings
from modules.administrative.models import AdministrativeDepartment, AdministrativeEmployee

logger = logging.getLogger(__name__)


class RagicSyncService:
    """
    Service for synchronizing Ragic data to local PostgreSQL cache.
    
    This service is responsible for:
        1. Validating Ragic form schema matches our field mappings
        2. Ensuring local cache tables exist in the database
        3. Performing full upsert sync from Ragic to local cache
    
    Single Responsibility: Only handles data fetching and storage.
    Does NOT handle business logic, API responses, or other concerns.
    
    Example:
        service = RagicSyncService()
        await service.sync_all_data()
    """

    def __init__(self, settings: AdminSettings | None = None) -> None:
        """
        Initialize the sync service.
        
        Args:
            settings: Optional AdminSettings instance. If not provided,
                     will use get_admin_settings() to load from environment.
        """
        self._settings = settings or get_admin_settings()
        self._http_client: httpx.AsyncClient | None = None

    @property
    def _client(self) -> httpx.AsyncClient:
        """Lazy-initialized HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._settings.sync_timeout_seconds),
                headers=self._get_auth_headers(),
            )
        return self._http_client

    def _get_auth_headers(self) -> dict[str, str]:
        """Get authentication headers for Ragic API."""
        return {
            "Authorization": f"Basic {self._settings.ragic_api_key.get_secret_value()}",
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    # =========================================================================
    # Step 1: Schema Introspection & Validation
    # =========================================================================

    async def _fetch_form_schema(self, form_url: str) -> dict[str, Any]:
        """
        Fetch form schema (field definitions) from Ragic.
        
        Ragic API: Append '?info=1' to get form schema instead of data.
        
        Args:
            form_url: Full URL to the Ragic form.
            
        Returns:
            dict containing form field definitions.
        """
        schema_url = f"{form_url}?info=1"
        try:
            response = await self._client.get(schema_url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch Ragic form schema from {schema_url}: {e}")
            raise

    async def _validate_field_mappings(self) -> dict[str, list[str]]:
        """
        Validate that our configured field IDs exist in Ragic forms.
        
        Returns:
            dict with 'employee' and 'department' keys, each containing
            a list of missing field IDs (empty if all valid).
        """
        issues: dict[str, list[str]] = {"employee": [], "department": []}
        
        # Validate Employee Form
        try:
            emp_schema = await self._fetch_form_schema(self._settings.ragic_url_employee)
            fields = emp_schema.get("fields", {})
            
            required_fields = [
                self._settings.field_employee_email,
                self._settings.field_employee_name,
                self._settings.field_employee_department,
                self._settings.field_employee_supervisor_email,
            ]
            
            for field_id in required_fields:
                if field_id not in fields:
                    issues["employee"].append(field_id)
                    logger.warning(
                        f"Employee field {field_id} not found in Ragic form schema. "
                        f"Available fields: {list(fields.keys())[:10]}..."
                    )
        except Exception as e:
            logger.error(f"Could not validate Employee form schema: {e}")
            issues["employee"].append("SCHEMA_FETCH_FAILED")

        # Validate Department Form
        try:
            dept_schema = await self._fetch_form_schema(self._settings.ragic_url_dept)
            fields = dept_schema.get("fields", {})
            
            required_fields = [
                self._settings.field_department_name,
                self._settings.field_department_manager_email,
            ]
            
            for field_id in required_fields:
                if field_id not in fields:
                    issues["department"].append(field_id)
                    logger.warning(
                        f"Department field {field_id} not found in Ragic form schema. "
                        f"Available fields: {list(fields.keys())[:10]}..."
                    )
        except Exception as e:
            logger.error(f"Could not validate Department form schema: {e}")
            issues["department"].append("SCHEMA_FETCH_FAILED")

        return issues

    # =========================================================================
    # Step 2: Table Check & Dynamic Creation
    # =========================================================================

    async def _ensure_tables_exist(self) -> None:
        """
        Ensure cache tables exist in the database.
        
        Uses SQLAlchemy metadata.create_all to create missing tables.
        This is safe to call even if tables already exist.
        """
        engine = get_thread_local_engine()
        
        async with engine.begin() as conn:
            # Check if tables exist using inspector
            def check_tables(sync_conn):
                inspector = inspect(sync_conn)
                existing_tables = inspector.get_table_names()
                return (
                    AdministrativeEmployee.__tablename__ in existing_tables,
                    AdministrativeDepartment.__tablename__ in existing_tables,
                )
            
            emp_exists, dept_exists = await conn.run_sync(check_tables)
            
            if not emp_exists or not dept_exists:
                logger.info(
                    f"Creating missing tables: "
                    f"employee={not emp_exists}, department={not dept_exists}"
                )
                
                # Create only the tables we need
                await conn.run_sync(
                    lambda sync_conn: Base.metadata.create_all(
                        sync_conn,
                        tables=[
                            AdministrativeEmployee.__table__,
                            AdministrativeDepartment.__table__,
                        ],
                    )
                )
                logger.info("Cache tables created successfully.")
            else:
                logger.debug("Cache tables already exist.")

    # =========================================================================
    # Step 3: Data Sync (Upsert)
    # =========================================================================

    async def _fetch_form_data(self, form_url: str) -> list[dict[str, Any]]:
        """
        Fetch all records from a Ragic form.
        
        Uses naming=EID parameter to get field IDs as keys instead of field names.
        This ensures field mappings work even if field names are changed in Ragic.
        
        Args:
            form_url: Full URL to the Ragic form.
            
        Returns:
            List of record dicts, each with '_ragicId' added.
        """
        try:
            # Use naming=EID to get field IDs as keys (not field names)
            response = await self._client.get(form_url, params={"naming": "EID"})
            response.raise_for_status()
            data = response.json()
            
            # Ragic returns {record_id: {fields...}, ...}
            # Transform to list with _ragicId included
            records = []
            for ragic_id, record in data.items():
                if ragic_id == "_metaData":
                    continue  # Skip metadata
                record["_ragicId"] = int(ragic_id)
                records.append(record)
            
            logger.info(f"Fetched {len(records)} records from {form_url}")
            return records
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to fetch Ragic data from {form_url}: {e}")
            raise

    async def _build_name_to_email_map(
        self, session: AsyncSession
    ) -> dict[str, str]:
        """
        Build a name-to-email mapping from the core User table.
        
        This is used as a fallback when Ragic records are missing email.
        Since users authenticate through the framework (LINE + Magic Link),
        we have their verified email in the User table.
        
        Returns:
            dict: Mapping of display_name -> email for verified users.
        """
        try:
            result = await session.execute(
                select(User.display_name, User.email).where(User.is_active == True)
            )
            name_to_email = {}
            for row in result.all():
                display_name, email = row
                if display_name and email:
                    # Use decoded values (they are encrypted in DB)
                    name_to_email[display_name.strip()] = email.strip()
            
            logger.debug(f"Built name-to-email map with {len(name_to_email)} entries")
            return name_to_email
        except Exception as e:
            logger.warning(f"Failed to build name-to-email map: {e}")
            return {}

    async def _upsert_employees(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> int:
        """
        Upsert employee records into the cache table.
        
        Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE.
        Processes in batches to avoid hitting PostgreSQL limits.
        
        When Ragic records are missing email, attempts to find the email
        from the core User table using the employee's name as a lookup key.
        
        Args:
            records: List of Ragic records.
            session: Database session.
            
        Returns:
            Number of records processed.
        """
        if not records:
            return 0

        # Build fallback name-to-email map from verified users
        name_to_email = await self._build_name_to_email_map(session)
        
        values = []
        missing_email_count = 0
        recovered_email_count = 0
        
        for record in records:
            email = record.get(self._settings.field_employee_email, "").strip()
            name = record.get(self._settings.field_employee_name, "").strip() or "Unknown"
            
            # If email is missing, try to recover from User table
            if not email:
                missing_email_count += 1
                # Try to find email by name from verified users
                if name in name_to_email:
                    email = name_to_email[name]
                    recovered_email_count += 1
                    logger.info(f"Recovered email for '{name}' from User table")
                else:
                    logger.warning(
                        f"Skipping employee without email and no fallback found: "
                        f"ragic_id={record.get('_ragicId')}, name={name}"
                    )
                    continue
            
            values.append({
                "email": email,
                "name": name,
                "department_name": record.get(
                    self._settings.field_employee_department, ""
                ).strip() or None,
                "supervisor_email": record.get(
                    self._settings.field_employee_supervisor_email, ""
                ).strip() or None,
                "ragic_id": record.get("_ragicId"),
            })

        if missing_email_count > 0:
            logger.info(
                f"Email recovery: {recovered_email_count}/{missing_email_count} "
                f"records recovered from User table"
            )

        if not values:
            return 0

        # Process in batches to avoid PostgreSQL parameter limits
        batch_size = self._settings.sync_batch_size
        total_upserted = 0
        
        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]
            
            # PostgreSQL upsert
            stmt = pg_insert(AdministrativeEmployee).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["email"],
                set_={
                    "name": stmt.excluded.name,
                    "department_name": stmt.excluded.department_name,
                    "supervisor_email": stmt.excluded.supervisor_email,
                    "ragic_id": stmt.excluded.ragic_id,
                },
            )
            
            await session.execute(stmt)
            total_upserted += len(batch)
            logger.debug(f"Upserted employee batch {i//batch_size + 1}: {len(batch)} records")
        
        return total_upserted

    async def _upsert_departments(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> int:
        """
        Upsert department records into the cache table.
        
        Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE.
        
        Args:
            records: List of Ragic records.
            session: Database session.
            
        Returns:
            Number of records processed.
        """
        if not records:
            return 0

        values = []
        for record in records:
            name = record.get(self._settings.field_department_name, "").strip()
            if not name:
                logger.warning(f"Skipping department record without name: {record}")
                continue
            
            values.append({
                "name": name,
                "manager_email": record.get(
                    self._settings.field_department_manager_email, ""
                ).strip() or None,
                "ragic_id": record.get("_ragicId"),
            })

        if not values:
            return 0

        # PostgreSQL upsert
        stmt = pg_insert(AdministrativeDepartment).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["name"],
            set_={
                "manager_email": stmt.excluded.manager_email,
                "ragic_id": stmt.excluded.ragic_id,
            },
        )
        
        await session.execute(stmt)
        return len(values)

    # =========================================================================
    # Public API
    # =========================================================================

    async def sync_all_data(self) -> dict[str, Any]:
        """
        Perform full synchronization from Ragic to local cache.
        
        This is the main entry point for the sync process:
            1. Validate field mappings against Ragic schema
            2. Ensure cache tables exist
            3. Fetch and upsert all data
        
        Returns:
            dict with sync results:
                - schema_issues: Any field mapping issues found
                - employees_synced: Number of employee records synced
                - departments_synced: Number of department records synced
                
        Example:
            service = RagicSyncService()
            result = await service.sync_all_data()
            print(f"Synced {result['employees_synced']} employees")
        """
        logger.info("Starting Ragic data synchronization...")
        
        result = {
            "schema_issues": {},
            "employees_synced": 0,
            "departments_synced": 0,
        }

        try:
            # Step 1: Validate schema (non-blocking, just logs warnings)
            result["schema_issues"] = await self._validate_field_mappings()
            if any(result["schema_issues"].values()):
                logger.warning(
                    f"Schema validation issues detected: {result['schema_issues']}. "
                    "Proceeding with sync anyway - data may be incomplete."
                )

            # Step 2: Ensure tables exist
            await self._ensure_tables_exist()

            # Step 3: Fetch and sync data
            async with get_thread_local_session() as session:
                # Sync Employees
                employee_records = await self._fetch_form_data(
                    self._settings.ragic_url_employee
                )
                result["employees_synced"] = await self._upsert_employees(
                    employee_records, session
                )
                
                # Sync Departments
                department_records = await self._fetch_form_data(
                    self._settings.ragic_url_dept
                )
                result["departments_synced"] = await self._upsert_departments(
                    department_records, session
                )

            logger.info(
                f"Ragic sync completed: "
                f"{result['employees_synced']} employees, "
                f"{result['departments_synced']} departments"
            )

        except Exception as e:
            logger.exception(f"Ragic sync failed: {e}")
            raise

        finally:
            await self.close()

        return result
