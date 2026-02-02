"""
Ragic Sync Service.

Handles synchronization of data from Ragic (No-Code DB) to local cache tables.
Follows Single Responsibility Principle - only handles fetching and storing data.

Features:
    - Schema introspection to validate field mappings (via core.ragic)
    - Dynamic table creation if not exists
    - Full upsert sync (insert new, update existing)
    - Pydantic validation before database insertion

Note:
    This service uses the framework's core.ragic.RagicService for all
    Ragic API communication instead of managing HTTP clients directly.
"""

import logging
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from sqlalchemy import inspect, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Base, get_engine, get_standalone_session
from core.ragic import RagicService
from modules.administrative.core.config import (
    AdminSettings,
    RagicAccountFieldMapping as Fields,
    RagicLeaveTypeFieldMapping as LeaveTypeFields,
    get_admin_settings,
)
from modules.administrative.models import AdministrativeAccount, LeaveType

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Schemas for Data Validation
# =============================================================================


class AccountRecordSchema(BaseModel):
    """
    Pydantic schema for validating Ragic Account records before DB insertion.
    
    Handles:
        - Type coercion (string to date, int, float, bool)
        - Empty string to None conversion
        - Date parsing (YYYY-MM-DD format)
        - Boolean conversion (0/1 to False/True)
    """
    
    model_config = ConfigDict(
        str_strip_whitespace=True,
        coerce_numbers_to_str=False,
    )
    
    # === Primary Identification ===
    ragic_id: int
    account_id: str
    id_card_number: Optional[str] = None
    employee_id: Optional[str] = None
    
    # === Status & Basic Info ===
    status: bool = True
    name: str
    gender: Optional[str] = None
    birthday: Optional[date] = None
    education: Optional[str] = None
    
    # === Contact Info ===
    emails: Optional[str] = None
    phones: Optional[str] = None
    mobiles: Optional[str] = None
    
    # === Organization Info ===
    org_code: Optional[str] = None
    org_name: Optional[str] = None
    org_path: Optional[str] = None
    rank_code: Optional[str] = None
    rank_name: Optional[str] = None
    sales_dept: Optional[str] = None
    sales_dept_manager: Optional[str] = None
    
    # === Referrer & Mentor ===
    referrer_id_card: Optional[str] = None
    referrer_name: Optional[str] = None
    mentor_id_card: Optional[str] = None
    mentor_name: Optional[str] = None
    successor_name: Optional[str] = None
    successor_id_card: Optional[str] = None
    
    # === Employment Dates ===
    approval_date: Optional[date] = None
    effective_date: Optional[date] = None
    resignation_date: Optional[date] = None
    death_date: Optional[date] = None
    created_date: Optional[date] = None
    
    # === Rate & Financial ===
    assessment_rate: Optional[float] = None
    court_withholding_rate: Optional[float] = None
    court_min_living_expense: Optional[float] = None
    prior_commission_debt: Optional[float] = None
    prior_debt: Optional[float] = None
    
    # === Bank Info ===
    bank_name: Optional[str] = None
    bank_branch_code: Optional[str] = None
    bank_account: Optional[str] = None
    edi_format: Optional[int] = None
    
    # === Address - Household Registration ===
    household_postal_code: Optional[str] = None
    household_city: Optional[str] = None
    household_district: Optional[str] = None
    household_address: Optional[str] = None
    
    # === Address - Mailing ===
    mailing_postal_code: Optional[str] = None
    mailing_city: Optional[str] = None
    mailing_district: Optional[str] = None
    mailing_address: Optional[str] = None
    
    # === Emergency Contact ===
    emergency_contact: Optional[str] = None
    emergency_phone: Optional[str] = None
    
    # === Life Insurance License ===
    life_license_number: Optional[str] = None
    life_first_registration_date: Optional[date] = None
    life_registration_date: Optional[date] = None
    life_exam_number: Optional[str] = None
    life_cancellation_date: Optional[date] = None
    life_license_expiry: Optional[str] = None
    
    # === Property Insurance License ===
    property_license_number: Optional[str] = None
    property_registration_date: Optional[date] = None
    property_exam_number: Optional[str] = None
    property_cancellation_date: Optional[date] = None
    property_license_expiry: Optional[str] = None
    property_standard_date: Optional[date] = None
    
    # === Accident & Health Insurance License ===
    ah_license_number: Optional[str] = None
    ah_registration_date: Optional[date] = None
    ah_cancellation_date: Optional[date] = None
    ah_license_expiry: Optional[str] = None
    
    # === Investment-linked Insurance ===
    investment_registration_date: Optional[date] = None
    investment_exam_number: Optional[str] = None
    
    # === Foreign Currency Insurance ===
    foreign_currency_registration_date: Optional[date] = None
    foreign_currency_exam_number: Optional[str] = None
    
    # === Qualifications ===
    fund_qualification_date: Optional[date] = None
    traditional_annuity_qualification: Optional[bool] = None
    variable_annuity_qualification: Optional[bool] = None
    structured_bond_qualification: Optional[bool] = None
    mobile_insurance_exam_date: Optional[date] = None
    preferred_insurance_exam_date: Optional[date] = None
    app_enabled: Optional[bool] = None
    
    # === Training Completion Dates ===
    senior_training_date: Optional[date] = None
    foreign_currency_training_date: Optional[date] = None
    fair_treatment_training_date: Optional[date] = None
    profit_sharing_training_date: Optional[date] = None
    
    # === Office Info ===
    office: Optional[str] = None
    office_tax_id: Optional[str] = None
    submission_unit: Optional[str] = None
    
    # === Health Insurance Withholding ===
    nhi_withholding_status: Optional[int] = None
    nhi_withholding_update_date: Optional[date] = None
    
    # === Miscellaneous ===
    remarks: Optional[str] = None
    notes: Optional[str] = None
    account_attributes: Optional[str] = None
    last_modified: Optional[datetime] = None


# =============================================================================
# Data Transformation Helpers
# =============================================================================


def parse_date(value: Any) -> Optional[date]:
    """Parse a date value from Ragic (YYYY/MM/DD or YYYY-MM-DD format)."""
    if not value or value == "":
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        # Handle multi-value dates (e.g., "2025-02-12, 2025-12-01") - take first
        if ", " in value:
            value = value.split(", ")[0].strip()
        # Try different date formats
        for fmt in ["%Y-%m-%d", "%Y/%m/%d"]:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        logger.debug(f"Could not parse date: {value}")
        return None
    return None


def parse_datetime(value: Any) -> Optional[datetime]:
    """Parse a datetime value from Ragic (YYYY/MM/DD HH:ii:ss or YYYY-MM-DD HH:ii:ss format)."""
    if not value or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        # Try different datetime formats
        for fmt in [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ]:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        logger.debug(f"Could not parse datetime: {value}")
        return None
    return None


def parse_bool(value: Any) -> Optional[bool]:
    """Parse a boolean value from Ragic (0/1 format)."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return value in ("1", "true", "True", "TRUE", "是")
    return None


def parse_float(value: Any) -> Optional[float]:
    """Parse a float value from Ragic."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value:
            return None
        try:
            return float(value)
        except ValueError:
            logger.warning(f"Failed to parse float: {value}")
            return None
    return None


def parse_int(value: Any) -> Optional[int]:
    """Parse an integer value from Ragic."""
    if value is None or value == "":
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        value = value.strip().replace(",", "")
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            logger.warning(f"Failed to parse int: {value}")
            return None
    return None


def parse_string(value: Any) -> Optional[str]:
    """Parse a string value, converting empty to None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return str(value).strip() or None


def _get_ragic_id(record: dict[str, Any], field_key: str) -> int | None:
    """
    Get Ragic ID from record, handling the case where ragic_id might be 0.
    
    Args:
        record: Raw record from Ragic API.
        field_key: The field key to look up (e.g., Fields.RAGIC_ID).
        
    Returns:
        The Ragic ID as int, or None if not found.
    """
    ragic_id = parse_int(record.get(field_key))
    if ragic_id is None:
        ragic_id = record.get("_ragicId")
    return ragic_id


def transform_ragic_record(record: dict[str, Any]) -> dict[str, Any]:
    """
    Transform a raw Ragic record into a format suitable for Pydantic validation.
    
    Args:
        record: Raw record from Ragic API with field ID keys.
        
    Returns:
        dict with model field names as keys and properly typed values.
    """
    return {
        # === Primary Identification ===
        "ragic_id": _get_ragic_id(record, Fields.RAGIC_ID),
        "account_id": parse_string(record.get(Fields.ACCOUNT_ID)) or "",
        "id_card_number": parse_string(record.get(Fields.ID_CARD_NUMBER)),
        "employee_id": parse_string(record.get(Fields.EMPLOYEE_ID)),
        
        # === Status & Basic Info ===
        "status": parse_bool(record.get(Fields.STATUS)) if record.get(Fields.STATUS) != "" else True,
        "name": parse_string(record.get(Fields.NAME)) or "Unknown",
        "gender": parse_string(record.get(Fields.GENDER)),
        "birthday": parse_date(record.get(Fields.BIRTHDAY)),
        "education": parse_string(record.get(Fields.EDUCATION)),
        
        # === Contact Info ===
        "emails": parse_string(record.get(Fields.EMAILS)),
        "phones": parse_string(record.get(Fields.PHONES)),
        "mobiles": parse_string(record.get(Fields.MOBILES)),
        
        # === Organization Info ===
        "org_code": parse_string(record.get(Fields.ORG_CODE)),
        "org_name": parse_string(record.get(Fields.ORG_NAME)),
        "org_path": parse_string(record.get(Fields.ORG_PATH)),
        "rank_code": parse_string(record.get(Fields.RANK_CODE)),
        "rank_name": parse_string(record.get(Fields.RANK_NAME)),
        "sales_dept": parse_string(record.get(Fields.SALES_DEPT)),
        "sales_dept_manager": parse_string(record.get(Fields.SALES_DEPT_MANAGER)),
        
        # === Referrer & Mentor ===
        "referrer_id_card": parse_string(record.get(Fields.REFERRER_ID_CARD)),
        "referrer_name": parse_string(record.get(Fields.REFERRER_NAME)),
        "mentor_id_card": parse_string(record.get(Fields.MENTOR_ID_CARD)),
        "mentor_name": parse_string(record.get(Fields.MENTOR_NAME)),
        "successor_name": parse_string(record.get(Fields.SUCCESSOR_NAME)),
        "successor_id_card": parse_string(record.get(Fields.SUCCESSOR_ID_CARD)),
        
        # === Employment Dates ===
        "approval_date": parse_date(record.get(Fields.APPROVAL_DATE)),
        "effective_date": parse_date(record.get(Fields.EFFECTIVE_DATE)),
        "resignation_date": parse_date(record.get(Fields.RESIGNATION_DATE)),
        "death_date": parse_date(record.get(Fields.DEATH_DATE)),
        "created_date": parse_date(record.get(Fields.CREATED_DATE)),
        
        # === Rate & Financial ===
        "assessment_rate": parse_float(record.get(Fields.ASSESSMENT_RATE)),
        "court_withholding_rate": parse_float(record.get(Fields.COURT_WITHHOLDING_RATE)),
        "court_min_living_expense": parse_float(record.get(Fields.COURT_MIN_LIVING_EXPENSE)),
        "prior_commission_debt": parse_float(record.get(Fields.PRIOR_COMMISSION_DEBT)),
        "prior_debt": parse_float(record.get(Fields.PRIOR_DEBT)),
        
        # === Bank Info ===
        "bank_name": parse_string(record.get(Fields.BANK_NAME)),
        "bank_branch_code": parse_string(record.get(Fields.BANK_BRANCH_CODE)),
        "bank_account": parse_string(record.get(Fields.BANK_ACCOUNT)),
        "edi_format": parse_int(record.get(Fields.EDI_FORMAT)),
        
        # === Address - Household Registration ===
        "household_postal_code": parse_string(record.get(Fields.HOUSEHOLD_POSTAL_CODE)),
        "household_city": parse_string(record.get(Fields.HOUSEHOLD_CITY)),
        "household_district": parse_string(record.get(Fields.HOUSEHOLD_DISTRICT)),
        "household_address": parse_string(record.get(Fields.HOUSEHOLD_ADDRESS)),
        
        # === Address - Mailing ===
        "mailing_postal_code": parse_string(record.get(Fields.MAILING_POSTAL_CODE)),
        "mailing_city": parse_string(record.get(Fields.MAILING_CITY)),
        "mailing_district": parse_string(record.get(Fields.MAILING_DISTRICT)),
        "mailing_address": parse_string(record.get(Fields.MAILING_ADDRESS)),
        
        # === Emergency Contact ===
        "emergency_contact": parse_string(record.get(Fields.EMERGENCY_CONTACT)),
        "emergency_phone": parse_string(record.get(Fields.EMERGENCY_PHONE)),
        
        # === Life Insurance License ===
        "life_license_number": parse_string(record.get(Fields.LIFE_LICENSE_NUMBER)),
        "life_first_registration_date": parse_date(record.get(Fields.LIFE_FIRST_REGISTRATION_DATE)),
        "life_registration_date": parse_date(record.get(Fields.LIFE_REGISTRATION_DATE)),
        "life_exam_number": parse_string(record.get(Fields.LIFE_EXAM_NUMBER)),
        "life_cancellation_date": parse_date(record.get(Fields.LIFE_CANCELLATION_DATE)),
        "life_license_expiry": parse_string(record.get(Fields.LIFE_LICENSE_EXPIRY)),
        
        # === Property Insurance License ===
        "property_license_number": parse_string(record.get(Fields.PROPERTY_LICENSE_NUMBER)),
        "property_registration_date": parse_date(record.get(Fields.PROPERTY_REGISTRATION_DATE)),
        "property_exam_number": parse_string(record.get(Fields.PROPERTY_EXAM_NUMBER)),
        "property_cancellation_date": parse_date(record.get(Fields.PROPERTY_CANCELLATION_DATE)),
        "property_license_expiry": parse_string(record.get(Fields.PROPERTY_LICENSE_EXPIRY)),
        "property_standard_date": parse_date(record.get(Fields.PROPERTY_STANDARD_DATE)),
        
        # === Accident & Health Insurance License ===
        "ah_license_number": parse_string(record.get(Fields.AH_LICENSE_NUMBER)),
        "ah_registration_date": parse_date(record.get(Fields.AH_REGISTRATION_DATE)),
        "ah_cancellation_date": parse_date(record.get(Fields.AH_CANCELLATION_DATE)),
        "ah_license_expiry": parse_string(record.get(Fields.AH_LICENSE_EXPIRY)),
        
        # === Investment-linked Insurance ===
        "investment_registration_date": parse_date(record.get(Fields.INVESTMENT_REGISTRATION_DATE)),
        "investment_exam_number": parse_string(record.get(Fields.INVESTMENT_EXAM_NUMBER)),
        
        # === Foreign Currency Insurance ===
        "foreign_currency_registration_date": parse_date(record.get(Fields.FOREIGN_CURRENCY_REGISTRATION_DATE)),
        "foreign_currency_exam_number": parse_string(record.get(Fields.FOREIGN_CURRENCY_EXAM_NUMBER)),
        
        # === Qualifications ===
        "fund_qualification_date": parse_date(record.get(Fields.FUND_QUALIFICATION_DATE)),
        "traditional_annuity_qualification": parse_bool(record.get(Fields.TRADITIONAL_ANNUITY_QUALIFICATION)),
        "variable_annuity_qualification": parse_bool(record.get(Fields.VARIABLE_ANNUITY_QUALIFICATION)),
        "structured_bond_qualification": parse_bool(record.get(Fields.STRUCTURED_BOND_QUALIFICATION)),
        "mobile_insurance_exam_date": parse_date(record.get(Fields.MOBILE_INSURANCE_EXAM_DATE)),
        "preferred_insurance_exam_date": parse_date(record.get(Fields.PREFERRED_INSURANCE_EXAM_DATE)),
        "app_enabled": parse_bool(record.get(Fields.APP_ENABLED)),
        
        # === Training Completion Dates ===
        "senior_training_date": parse_date(record.get(Fields.SENIOR_TRAINING_DATE)),
        "foreign_currency_training_date": parse_date(record.get(Fields.FOREIGN_CURRENCY_TRAINING_DATE)),
        "fair_treatment_training_date": parse_date(record.get(Fields.FAIR_TREATMENT_TRAINING_DATE)),
        "profit_sharing_training_date": parse_date(record.get(Fields.PROFIT_SHARING_TRAINING_DATE)),
        
        # === Office Info ===
        "office": parse_string(record.get(Fields.OFFICE)),
        "office_tax_id": parse_string(record.get(Fields.OFFICE_TAX_ID)),
        "submission_unit": parse_string(record.get(Fields.SUBMISSION_UNIT)),
        
        # === Health Insurance Withholding ===
        "nhi_withholding_status": parse_int(record.get(Fields.NHI_WITHHOLDING_STATUS)),
        "nhi_withholding_update_date": parse_date(record.get(Fields.NHI_WITHHOLDING_UPDATE_DATE)),
        
        # === Miscellaneous ===
        "remarks": parse_string(record.get(Fields.REMARKS)),
        "notes": parse_string(record.get(Fields.NOTES)),
        "account_attributes": parse_string(record.get(Fields.ACCOUNT_ATTRIBUTES)),
        "last_modified": parse_datetime(record.get(Fields.LAST_MODIFIED)),
    }


# =============================================================================
# Sync Service
# =============================================================================


class RagicSyncService:
    """
    Service for synchronizing Ragic Account data to local PostgreSQL cache.
    
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

    def __init__(
        self,
        settings: AdminSettings | None = None,
        ragic_service: RagicService | None = None,
    ) -> None:
        """
        Initialize the sync service.
        
        Args:
            settings: Optional AdminSettings instance. If not provided,
                     will use get_admin_settings() to load from environment.
            ragic_service: Optional RagicService instance. If not provided,
                          will create one using settings.
        """
        self._settings = settings or get_admin_settings()
        
        # Use injected service or create one with module-specific settings
        if ragic_service:
            self._ragic_service = ragic_service
        else:
            self._ragic_service = RagicService(
                api_key=self._settings.ragic_api_key.get_secret_value(),
                timeout=float(self._settings.sync_timeout_seconds),
            )

    async def close(self) -> None:
        """Close the Ragic service HTTP client."""
        await self._ragic_service.close()

    # =========================================================================
    # Step 1: Schema Introspection & Validation
    # =========================================================================

    async def _fetch_form_schema(self, form_url: str) -> dict[str, Any]:
        """
        Fetch form schema (field definitions) from Ragic.
        
        Uses framework's RagicService.get_form_schema() method.
        
        Args:
            form_url: Full URL to the Ragic form.
            
        Returns:
            dict containing form field definitions.
        """
        try:
            return await self._ragic_service.get_form_schema(full_url=form_url)
        except Exception as e:
            logger.error(f"Failed to fetch Ragic form schema from {form_url}: {e}")
            raise

    async def _validate_field_mappings(self) -> list[str]:
        """
        Validate that critical field IDs exist in Ragic form.
        
        Returns:
            list of missing field IDs (empty if all valid).
        """
        issues: list[str] = []
        
        try:
            schema = await self._fetch_form_schema(self._settings.ragic_url_account)
            fields = schema.get("fields", {})
            
            # Only validate critical fields
            critical_fields = [
                Fields.RAGIC_ID,
                Fields.ACCOUNT_ID,
                Fields.NAME,
                Fields.STATUS,
            ]
            
            for field_id in critical_fields:
                if field_id not in fields:
                    issues.append(field_id)
                    logger.warning(
                        f"Account field {field_id} not found in Ragic form schema. "
                        f"Available fields: {list(fields.keys())[:10]}..."
                    )
        except Exception as e:
            logger.error(f"Could not validate Account form schema: {e}")
            issues.append("SCHEMA_FETCH_FAILED")

        return issues

    # =========================================================================
    # Step 2: Table Check & Dynamic Creation
    # =========================================================================

    async def _ensure_tables_exist(self) -> None:
        """
        Ensure cache tables exist in the database.
        
        Uses SQLAlchemy metadata.create_all to create missing tables.
        This is safe to call even if tables already exist.
        
        Checks for:
            - AdministrativeAccount table (accounts cache)
            - LeaveType table (leave types cache)
        """
        engine = get_engine()
        
        # Define all tables that need to exist
        required_tables = {
            AdministrativeAccount.__tablename__: AdministrativeAccount.__table__,
            LeaveType.__tablename__: LeaveType.__table__,
        }
        
        async with engine.begin() as conn:
            # Check which tables exist
            def check_tables(sync_conn):
                inspector = inspect(sync_conn)
                existing_tables = set(inspector.get_table_names())
                return existing_tables
            
            existing_tables = await conn.run_sync(check_tables)
            
            # Find missing tables
            missing_tables = []
            for table_name, table_obj in required_tables.items():
                if table_name not in existing_tables:
                    missing_tables.append(table_obj)
                    logger.info(f"Table '{table_name}' not found, will create.")
            
            if missing_tables:
                logger.info(f"Creating {len(missing_tables)} missing table(s)...")
                
                # Create only the missing tables
                await conn.run_sync(
                    lambda sync_conn: Base.metadata.create_all(
                        sync_conn,
                        tables=missing_tables,
                    )
                )
                logger.info("Cache tables created successfully.")
            else:
                logger.debug("All cache tables already exist.")

    # =========================================================================
    # Step 3: Data Sync (Upsert)
    # =========================================================================

    async def _fetch_form_data(self, form_url: str) -> list[dict[str, Any]]:
        """
        Fetch all records from a Ragic form.
        
        Uses framework's RagicService.get_records_by_url() method.
        Uses naming=EID parameter to get field IDs as keys instead of field names.
        This ensures field mappings work even if field names are changed in Ragic.
        
        Args:
            form_url: Full URL to the Ragic form.
            
        Returns:
            List of record dicts, each with '_ragicId' added.
        """
        try:
            # Use naming=EID to get field IDs as keys (not field names)
            records = await self._ragic_service.get_records_by_url(
                full_url=form_url,
                params={"naming": "EID"},
            )
            
            logger.info(f"Fetched {len(records)} records from {form_url}")
            return records
            
        except Exception as e:
            logger.error(f"Failed to fetch Ragic data from {form_url}: {e}")
            raise

    async def _upsert_accounts(
        self, records: list[dict[str, Any]], session: AsyncSession
    ) -> tuple[int, int]:
        """
        Upsert account records into the cache table using Pydantic validation.
        
        Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE.
        Processes in batches to avoid hitting PostgreSQL limits.
        
        Args:
            records: List of Ragic records.
            session: Database session.
            
        Returns:
            Tuple of (records_processed, records_skipped).
        """
        if not records:
            return 0, 0

        values = []
        skipped = 0
        
        for record in records:
            try:
                # Transform and validate using Pydantic
                transformed = transform_ragic_record(record)
                
                # Skip records without required fields
                if not transformed.get("account_id"):
                    logger.warning(
                        f"Skipping record without account_id: "
                        f"ragic_id={record.get('_ragicId')}, name={transformed.get('name')}"
                    )
                    skipped += 1
                    continue
                
                # Validate through Pydantic schema
                validated = AccountRecordSchema(**transformed)
                values.append(validated.model_dump())
                
            except Exception as e:
                logger.warning(
                    f"Validation failed for record ragic_id={record.get('_ragicId')}: {e}"
                )
                skipped += 1
                continue

        if not values:
            return 0, skipped

        # Process in batches to avoid PostgreSQL parameter limits
        batch_size = self._settings.sync_batch_size
        total_upserted = 0
        
        for i in range(0, len(values), batch_size):
            batch = values[i:i + batch_size]
            
            # PostgreSQL upsert - use ragic_id as the conflict key (primary key)
            stmt = pg_insert(AdministrativeAccount).values(batch)
            
            # Build update dict for all non-primary-key columns
            update_dict = {
                col.name: getattr(stmt.excluded, col.name)
                for col in AdministrativeAccount.__table__.columns
                if col.name != "ragic_id"
            }
            
            stmt = stmt.on_conflict_do_update(
                index_elements=["ragic_id"],
                set_=update_dict,
            )
            
            await session.execute(stmt)
            total_upserted += len(batch)
            logger.debug(f"Upserted account batch {i//batch_size + 1}: {len(batch)} records")
        
        return total_upserted, skipped

    # =========================================================================
    # Step 4b: Leave Type Sync
    # =========================================================================

    def _transform_leave_type_record(self, record: dict[str, Any]) -> dict[str, Any] | None:
        """
        Transform a raw Ragic leave type record into a format for database insertion.
        
        Args:
            record: Raw record from Ragic API with field ID keys.
            
        Returns:
            dict with model field names and typed values, or None if invalid.
        """
        try:
            ragic_id = parse_int(record.get(LeaveTypeFields.RAGIC_ID))
            if ragic_id is None:
                ragic_id = record.get("_ragicId")
            leave_type_code = parse_string(record.get(LeaveTypeFields.LEAVE_TYPE_CODE))
            leave_type_name = parse_string(record.get(LeaveTypeFields.LEAVE_TYPE_NAME))
            
            if ragic_id is None or not leave_type_code or not leave_type_name:
                logger.warning(f"Skipping leave type record with missing required fields: {record}")
                return None
            
            return {
                "ragic_id": ragic_id,
                "leave_type_code": leave_type_code,
                "leave_type_name": leave_type_name,
                "deduction_multiplier": parse_float(record.get(LeaveTypeFields.DEDUCTION_MULTIPLIER)),
            }
        except Exception as e:
            logger.warning(f"Failed to transform leave type record: {e}")
            return None

    async def _upsert_leave_types(
        self,
        records: list[dict[str, Any]],
        session: AsyncSession,
    ) -> tuple[int, int]:
        """
        Upsert leave type records into the database.
        
        Args:
            records: List of raw Ragic records.
            session: Database session.
            
        Returns:
            tuple of (upserted_count, skipped_count).
        """
        if not records:
            logger.info("No leave type records to sync")
            return 0, 0

        transformed = []
        skipped = 0

        for record in records:
            data = self._transform_leave_type_record(record)
            if data:
                transformed.append(data)
            else:
                skipped += 1

        if not transformed:
            logger.warning("All leave type records were invalid, nothing to sync")
            return 0, skipped

        # PostgreSQL upsert - use ragic_id as the conflict key
        stmt = pg_insert(LeaveType).values(transformed)
        
        update_dict = {
            col.name: getattr(stmt.excluded, col.name)
            for col in LeaveType.__table__.columns
            if col.name != "ragic_id"
        }
        
        stmt = stmt.on_conflict_do_update(
            index_elements=["ragic_id"],
            set_=update_dict,
        )
        
        await session.execute(stmt)
        logger.info(f"Upserted {len(transformed)} leave type records")
        
        return len(transformed), skipped

    async def sync_leave_types(self) -> dict[str, Any]:
        """
        Synchronize leave type data from Ragic to local cache.
        
        Returns:
            dict with sync results.
        """
        logger.info("Starting leave type synchronization...")
        
        result = {
            "leave_types_synced": 0,
            "leave_types_skipped": 0,
        }

        try:
            if not self._settings.ragic_url_leave_type:
                logger.warning("Leave type URL not configured, skipping sync")
                return result

            # Ensure tables exist
            await self._ensure_tables_exist()

            # Fetch and sync data
            async with get_standalone_session() as session:
                leave_type_records = await self._fetch_form_data(
                    self._settings.ragic_url_leave_type
                )
                synced, skipped = await self._upsert_leave_types(
                    leave_type_records, session
                )
                result["leave_types_synced"] = synced
                result["leave_types_skipped"] = skipped

            logger.info(
                f"Leave type sync completed: "
                f"{result['leave_types_synced']} types synced, "
                f"{result['leave_types_skipped']} skipped"
            )

        except Exception as e:
            logger.exception(f"Leave type sync failed: {e}")
            raise

        return result

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
                - accounts_synced: Number of account records synced
                - accounts_skipped: Number of records skipped due to validation
                
        Example:
            service = RagicSyncService()
            result = await service.sync_all_data()
            print(f"Synced {result['accounts_synced']} accounts")
        """
        logger.info("Starting Ragic Account data synchronization...")
        
        result = {
            "schema_issues": [],
            "accounts_synced": 0,
            "accounts_skipped": 0,
        }

        try:
            # Step 1: Validate schema (non-blocking, just logs warnings)
            result["schema_issues"] = await self._validate_field_mappings()
            if result["schema_issues"]:
                logger.warning(
                    f"Schema validation issues detected: {result['schema_issues']}. "
                    "Proceeding with sync anyway - data may be incomplete."
                )

            # Step 2: Ensure tables exist
            await self._ensure_tables_exist()

            # Step 3: Fetch and sync account data
            async with get_standalone_session() as session:
                account_records = await self._fetch_form_data(
                    self._settings.ragic_url_account
                )
                synced, skipped = await self._upsert_accounts(
                    account_records, session
                )
                result["accounts_synced"] = synced
                result["accounts_skipped"] = skipped

            # Step 4: Sync leave types
            leave_type_result = await self.sync_leave_types()
            result["leave_types_synced"] = leave_type_result.get("leave_types_synced", 0)
            result["leave_types_skipped"] = leave_type_result.get("leave_types_skipped", 0)

            logger.info(
                f"Ragic sync completed: "
                f"{result['accounts_synced']} accounts synced, "
                f"{result['accounts_skipped']} skipped, "
                f"{result['leave_types_synced']} leave types synced"
            )

        except Exception as e:
            logger.exception(f"Ragic sync failed: {e}")
            raise

        finally:
            await self.close()

        return result
