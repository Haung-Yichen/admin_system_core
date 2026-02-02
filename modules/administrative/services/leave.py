"""
Leave Service.

Handles leave request business logic.
Follows Single Responsibility Principle - only handles leave-related operations.

Authentication is handled by the Router layer via LINE ID Token (OIDC).
This service receives the verified email directly and uses it to look up
the employee profile from the local cache.

Note:
    This service uses the framework's core.ragic.RagicService for all
    Ragic API communication instead of managing HTTP clients directly.
"""

import logging
import os
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_standalone_session
from core.ragic import RagicService
from core.security import generate_blind_index
from modules.administrative.core.config import (
    AdminSettings,
    RagicLeaveFieldMapping,
    get_admin_settings,
)
from modules.administrative.models import AdministrativeAccount, LeaveType
from modules.administrative.services.email_notification import get_email_notification_service

logger = logging.getLogger(__name__)

# Environment flag to skip authentication for development/testing
DEBUG_SKIP_AUTH = os.environ.get(
    "DEBUG_SKIP_AUTH", "").lower() in ("true", "1", "yes")

class LeaveError(Exception):
    """Base exception for leave-related errors."""
    pass


class EmployeeNotFoundError(LeaveError):
    """Raised when employee profile not found in cache."""
    pass


class SubmissionError(LeaveError):
    """Raised when leave request submission to Ragic fails."""
    pass


class LeaveService:
    """
    Service for handling leave request operations.

    This service receives verified email addresses from the Router layer
    (authenticated via LINE ID Token) and uses them to look up employee
    profiles from the local cache (AdministrativeAccount).

    Flow:
        1. Router verifies LINE ID Token -> Email
        2. Email -> Module Cache -> Account Profile (includes org info)
        3. Construct payload and submit to Ragic
    """

    def __init__(
        self,
        settings: AdminSettings | None = None,
    ) -> None:
        """
        Initialize leave service with dependencies.

        Args:
            settings: Admin module settings. Uses singleton if not provided.
        """
        self._settings = settings or get_admin_settings()
        
        # Use framework's RagicService for all Ragic API operations
        self._ragic_service = RagicService(
            api_key=self._settings.ragic_api_key.get_secret_value(),
            timeout=float(self._settings.sync_timeout_seconds),
        )
        
        # Schema cache for form validation
        self._form_schema_cache: dict[str, Any] | None = None
        self._schema_cache_time: float = 0
        self._schema_cache_ttl: int = 300  # 5 minutes cache

    async def close(self) -> None:
        """Close the Ragic service HTTP client."""
        await self._ragic_service.close()

    # =========================================================================
    # Account Profile Lookup
    # =========================================================================

    async def _get_account_by_email(
        self, email: str, db: AsyncSession
    ) -> AdministrativeAccount:
        """
        Get account profile from local cache by email.

        Uses blind index (primary_email_hash) for exact match lookup on the
        primary (first) email address. This replaces the previous LIKE-based
        search to support encrypted email storage.
        
        Args:
            email: Employee email address.
            db: Database session.

        Returns:
            AdministrativeAccount record.

        Raises:
            EmployeeNotFoundError: If not found in cache.
        """
        # Compute the blind index hash for the input email
        email_hash = generate_blind_index(email.strip().lower())
        
        # Use exact match on the hash index
        result = await db.execute(
            select(AdministrativeAccount).where(
                AdministrativeAccount.primary_email_hash == email_hash
            )
        )
        account = result.scalar_one_or_none()

        if account is None:
            logger.warning(f"Account not found in cache for email: {email}")
            raise EmployeeNotFoundError(
                f"Account profile not found for {email}. "
                "Please ensure Ragic data has been synced."
            )

        return account

    async def _get_account_by_id(
        self, account_id: str, db: AsyncSession
    ) -> AdministrativeAccount | None:
        """
        Get account profile from local cache by account_id.
        
        Args:
            account_id: Account ID (帳號).
            db: Database session.

        Returns:
            AdministrativeAccount or None if not found.
        """
        if not account_id:
            return None

        result = await db.execute(
            select(AdministrativeAccount).where(
                AdministrativeAccount.account_id == account_id
            )
        )
        return result.scalar_one_or_none()

    async def _get_mentor_account(
        self, mentor_id_card: str, db: AsyncSession
    ) -> AdministrativeAccount | None:
        """
        Get mentor's account from local cache by ID card number.
        
        Args:
            mentor_id_card: Mentor's ID card number (身份證字號).
            db: Database session.

        Returns:
            AdministrativeAccount or None if not found.
        """
        if not mentor_id_card:
            return None

        result = await db.execute(
            select(AdministrativeAccount).where(
                AdministrativeAccount.id_card_number == mentor_id_card
            )
        )
        return result.scalar_one_or_none()

    async def _get_account_by_name(
        self, name: str, db: AsyncSession
    ) -> AdministrativeAccount | None:
        """
        Get account profile from local cache by name.
        
        Used to find manager emails when we only have their name.
        
        Args:
            name: Person's name (姓名).
            db: Database session.

        Returns:
            AdministrativeAccount or None if not found.
        """
        if not name:
            return None

        result = await db.execute(
            select(AdministrativeAccount).where(
                AdministrativeAccount.name == name,
                AdministrativeAccount.status == True  # Only active accounts
            )
        )
        return result.scalar_one_or_none()

    async def _get_manager_email(
        self, manager_name: str, db: AsyncSession
    ) -> str | None:
        """
        Get manager's email by looking up their name in the account table.
        
        This is used to find the email for sales_dept_manager and direct_supervisor
        when we only have their names stored in the applicant's record.
        
        Args:
            manager_name: Manager's name (姓名).
            db: Database session.

        Returns:
            Manager's primary email or None if not found.
        """
        if not manager_name:
            return None

        account = await self._get_account_by_name(manager_name, db)
        if account:
            return account.primary_email
        
        logger.warning(f"Manager account not found for name: {manager_name}")
        return None

    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    async def _get_leave_form_schema(self) -> dict[str, Any]:
        """
        Fetch leave form schema from Ragic to validate options.
        Uses simple caching to reduce API calls.
        """
        current_time = time.time()
        if (self._form_schema_cache and 
            current_time - self._schema_cache_time < self._schema_cache_ttl):
            return self._form_schema_cache
            
        try:
            logger.info(f"Fetching Ragic form schema from {self._settings.ragic_url_leave}")
            self._form_schema_cache = await self._ragic_service.get_form_schema(
                full_url=self._settings.ragic_url_leave
            )
            self._schema_cache_time = current_time
            return self._form_schema_cache
        except Exception as e:
            logger.error(f"Failed to fetch Ragic form schema: {e}")
            # Return empty schema or previous cache on failure
            return self._form_schema_cache or {}

    async def _resolve_selection_option(
        self, 
        field_id: str, 
        target_value: str,
        default_value: str | None = None
    ) -> str:
        """
        Check if target_value is valid for the given field in Ragic.
        Return the exact string from Ragic if found, to avoid substring/case issues.
        """
        schema = await self._get_leave_form_schema()
        
        # Schema structure in Ragic ?info=1:
        # It returns a dictionary where keys are field IDs (sometimes) or indices.
        # But commonly the response provided by Ragic for ?info=1 is keyed by field ID.
        # However, to be safe, we iterate.
        
        field_def = None
        
        # Try direct lookup if possible
        if field_id in schema:
             field_def = schema[field_id]
        else:
            # Fallback iteration
            for key, val in schema.items():
                if isinstance(val, dict) and str(val.get("id", "")) == field_id:
                    field_def = val
                    break
        
        if not field_def:
            logger.warning(f"Field {field_id} not found in Ragic schema, using target '{target_value}' blindly")
            return target_value

        # Check choices
        choices = field_def.get("choices")
        if not choices and "selection" in field_def:
             choices = field_def.get("selection")
             
        if not choices:
            # Maybe not a selection field or no choices defined
            return target_value
            
        if isinstance(choices, str):
            choice_list = [c.strip() for c in choices.split(",")]
        elif isinstance(choices, list):
            choice_list = choices
        else:
            choice_list = []

        # Try exact match first
        if target_value in choice_list:
            return target_value
            
        # Try case-insensitive specific match
        for choice in choice_list:
            if choice.lower() == target_value.lower():
                return choice
                
        # Try substring match (e.g. "審核中" matching "審核中(Processing)")
        for choice in choice_list:
            if target_value in choice:
                return choice
        
        logger.warning(
            f"Value '{target_value}' not found in choices for field {field_id}. "
            f"Available: {choice_list[:5]}..."
        )
        # Fallback to default if provided, else target
        return default_value if default_value else target_value

    def _extract_chinese_name(self, name: str) -> str:
        """
        Extract Chinese name by removing English suffix.
        
        Examples:
            "林文中VP" -> "林文中"
            "王小明Manager" -> "王小明"
            "張三" -> "張三"
        
        Args:
            name: Name that may contain English suffix.
            
        Returns:
            Name with English suffix removed.
        """
        if not name:
            return ""
        
        import re
        # Remove English letters and common suffixes at the end
        # Keep only Chinese characters and numbers at the start
        result = re.sub(r'[A-Za-z]+$', '', name).strip()
        return result if result else name

    async def _resolve_leave_type_name(
        self, leave_type_input: str, db: AsyncSession
    ) -> str:
        """
        Resolve leave type input to exact Ragic option name.
        
        Ragic dropdown fields require exact match with option names.
        This method looks up the leave type from cache and returns
        the exact name that Ragic expects.
        
        Matching logic:
        1. Exact match on leave_type_code (假別編號)
        2. Exact match on leave_type_name (請假類別)
        3. Partial match (contains) on leave_type_name
        4. If no match, return the original input
        
        Args:
            leave_type_input: User input for leave type (code or name).
            db: Database session.
            
        Returns:
            Exact leave type name from Ragic, or original input if no match.
        """
        if not leave_type_input:
            return ""
        
        # Try exact match by code
        result = await db.execute(
            select(LeaveType).where(LeaveType.leave_type_code == leave_type_input)
        )
        leave_type = result.scalar_one_or_none()
        if leave_type:
            logger.info(f"Leave type resolved by code: {leave_type_input} -> {leave_type.leave_type_name}")
            return leave_type.leave_type_name
        
        # Try exact match by name
        result = await db.execute(
            select(LeaveType).where(LeaveType.leave_type_name == leave_type_input)
        )
        leave_type = result.scalar_one_or_none()
        if leave_type:
            logger.info(f"Leave type exact match: {leave_type_input}")
            return leave_type.leave_type_name
        
        # Try partial match (contains)
        result = await db.execute(
            select(LeaveType).where(LeaveType.leave_type_name.like(f"%{leave_type_input}%"))
        )
        leave_type = result.scalar_one_or_none()
        if leave_type:
            logger.info(f"Leave type partial match: {leave_type_input} -> {leave_type.leave_type_name}")
            return leave_type.leave_type_name
        
        # No match found, return original (may cause Ragic to show empty)
        logger.warning(f"Leave type not found in cache: {leave_type_input}, using as-is")
        return leave_type_input

    # =========================================================================
    # Public API
    # =========================================================================

    async def get_init_data(
        self, email: str, db: AsyncSession
    ) -> dict[str, Any]:
        """
        Get initialization data for leave request form.

        This provides the frontend with:
            - Employee name
            - Organization (org_name)
            - Email

        NOTE: Supervisor info is NOT exposed to frontend for security.

        Args:
            email: Verified user email (from LINE ID Token authentication).
            db: Database session.

        Returns:
            dict with employee profile data.

        Raises:
            EmployeeNotFoundError: If employee not in cache.
        """
        logger.info(f"Leave init for authenticated user: {email}")

        # Development mode bypass - return mock data if flag is set
        if DEBUG_SKIP_AUTH:
            logger.warning(
                f"[DEV MODE] Using development bypass for email: {email}")
            # Try to find any account in cache for testing
            try:
                result = await db.execute(
                    select(AdministrativeAccount).where(
                        AdministrativeAccount.status == True
                    ).limit(1)
                )
                account = result.scalar_one_or_none()
                if account:
                    logger.info(
                        f"[DEV MODE] Using account from cache: {account.name}")
                    # org_name 實際上是直屬主管名稱，需去除英文後綴
                    direct_supervisor = self._extract_chinese_name(account.org_name or "")
                    return {
                        "name": account.name,
                        "email": account.primary_email or email,
                        "sales_dept": account.sales_dept or "",
                        "sales_dept_manager": account.sales_dept_manager or "",
                        "direct_supervisor": direct_supervisor,
                    }
            except Exception as e:
                logger.warning(f"[DEV MODE] Failed to fetch account: {e}")

            # Return mock test data
            logger.info("[DEV MODE] Using mock test data")
            return {
                "name": "測試使用者",
                "email": email,
                "sales_dept": "測試營業部",
                "sales_dept_manager": "測試負責人",
                "direct_supervisor": "測試主管",
            }

        # Production mode - look up account by email
        account = await self._get_account_by_email(email, db)

        # org_name 實際上是直屬主管名稱，需去除英文後綴
        direct_supervisor = self._extract_chinese_name(account.org_name or "")

        # Return safe data (NO supervisor email exposed to frontend, only names)
        return {
            "name": account.name,
            "email": account.primary_email or email,
            # Extended applicant info
            "sales_dept": account.sales_dept or "",
            "sales_dept_manager": account.sales_dept_manager or "",
            "direct_supervisor": direct_supervisor,
        }

    async def submit_leave_request(
        self,
        email: str,
        leave_dates: list[str],
        reason: str,
        db: AsyncSession,
        # Additional fields can be added as needed
        leave_type: str = "特休",  # 假別 (預設為特休)
    ) -> dict[str, Any]:
        """
        Submit leave requests to Ragic for multiple dates.

        This is the core workflow:
            1. Receive verified email from Router (authenticated via LINE ID Token)
            2. Fetch account profile from cache
            3. Fetch mentor info from cache (using mentor_id_card)
            4. Construct Ragic payload with supervisor info
            5. POST to Ragic Leave Request form for each date

        Args:
            email: Verified user email (from LINE ID Token authentication).
            leave_dates: List of leave dates (YYYY-MM-DD format).
            reason: Reason for leave.
            db: Database session.
            leave_type: Type of leave (annual, sick, personal, etc.).

        Returns:
            dict with submission result including Ragic record IDs.

        Raises:
            EmployeeNotFoundError: If employee not in cache.
            SubmissionError: If Ragic API call fails.
        """
        logger.info(f"Leave submission from: {email}, dates: {leave_dates}")

        # Development mode bypass - use mock data if flag is set
        if DEBUG_SKIP_AUTH:
            logger.warning(
                f"[DEV MODE] Using development bypass for submission, email: {email}")
            # Try to find any account in cache for testing
            account = None
            try:
                result = await db.execute(
                    select(AdministrativeAccount).where(
                        AdministrativeAccount.status == True
                    ).limit(1)
                )
                account = result.scalar_one_or_none()
            except Exception as e:
                logger.warning(f"[DEV MODE] Failed to fetch account: {e}")

            if not account:
                # Use mock data for testing
                logger.info(
                    "[DEV MODE] Using mock account data for submission")
                return {
                    "success": True,
                    "message": f"[DEV MODE] 請假申請已模擬送出（{len(leave_dates)} 天，尚未實際提交到 Ragic）",
                    "ragic_ids": [],
                    "employee": "測試使用者",
                    "dates": leave_dates,
                    "total_days": len(leave_dates),
                }

            logger.info(
                f"[DEV MODE] Leave submission using account: {account.name}")
        else:
            # Production mode - look up account by verified email
            account = await self._get_account_by_email(email, db)

        # org_name 實際上是直屬主管名稱，需去除英文後綴
        direct_supervisor_name = self._extract_chinese_name(account.org_name or "")
        
        # 查找直屬主管的 email（用去除英文後綴的名稱查找）
        direct_supervisor_email = None
        if direct_supervisor_name:
            direct_supervisor_email = await self._get_manager_email(direct_supervisor_name, db)

        # Get sales department manager info
        # sales_dept_manager field contains the manager's name, need to look up email
        sales_dept_manager_name = account.sales_dept_manager
        sales_dept_manager_email = None
        if sales_dept_manager_name:
            sales_dept_manager_email = await self._get_manager_email(sales_dept_manager_name, db)

        # Resolve leave type to exact Ragic option name
        resolved_leave_type = await self._resolve_leave_type_name(leave_type, db)
        
        # Resolve approval status (validate against Ragic schema)
        # This prevents "Selection value invalid" errors by ensuring we send the exact string
        # Changed from "審核中" to "已上傳" per user request
        resolved_approval_status = await self._resolve_selection_option(
            RagicLeaveFieldMapping.APPROVAL_STATUS, 
            "已上傳"
        )
        
        # Resolve Sales Dept if possible (to ensure exact match with options)
        resolved_sales_dept = account.sales_dept or ""
        if resolved_sales_dept:
            resolved_sales_dept = await self._resolve_selection_option(
                RagicLeaveFieldMapping.SALES_DEPT,
                resolved_sales_dept
            )

        # Log payload (without sensitive data)
        logger.info(
            f"Submitting leave request for {account.name}: dates={leave_dates}, leave_type={resolved_leave_type}")

        # Submit to Ragic - one record per date
        ragic_ids = []
        submitted_dates = []
        
        try:
            # Check if Ragic leave form URL is configured
            if not self._settings.ragic_url_leave:
                logger.warning("Ragic leave form URL not configured, skipping submission")
                return {
                    "success": True,
                    "message": f"請假申請已記錄（{len(leave_dates)} 天，Ragic URL 尚未設定）",
                    "ragic_ids": [],
                    "employee": account.name,
                    "dates": leave_dates,
                    "total_days": len(leave_dates),
                    "direct_supervisor": direct_supervisor_name,
                    "sales_dept_manager": sales_dept_manager_name,
                }

            # Generate leave request number using timestamp (shared across all dates in this submission)
            leave_request_no = f"LV{int(time.time() * 1000)}"
            total_leave_days = len(leave_dates)
            
            # Get current date for creation date field
            from datetime import datetime
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Combine multiple leave dates with comma separator
            leave_dates_str = ",".join(leave_dates)
            
            # Get start and end dates
            start_date = leave_dates[0]
            end_date = leave_dates[-1]
            
            # Submit as a single record with comma-separated dates
            # Construct Ragic payload with actual field IDs
            # Field IDs from Ragic leave request form at /HSIBAdmSys/ychn-test/3
            ragic_payload = {
                # Employee Info
                RagicLeaveFieldMapping.EMPLOYEE_NAME: account.name,
                RagicLeaveFieldMapping.EMPLOYEE_EMAIL: account.primary_email or email,
                RagicLeaveFieldMapping.SALES_DEPT: resolved_sales_dept,
                
                # Leave Details
                RagicLeaveFieldMapping.LEAVE_TYPE: resolved_leave_type,
                RagicLeaveFieldMapping.LEAVE_DATE: leave_dates_str,  # 請假日期（逗號隔開）
                RagicLeaveFieldMapping.START_DATE: start_date,  # 起始日期
                RagicLeaveFieldMapping.END_DATE: end_date,      # 結束日期
                RagicLeaveFieldMapping.LEAVE_REASON: reason,
                RagicLeaveFieldMapping.LEAVE_DAYS: total_leave_days,  # 請假天數
                RagicLeaveFieldMapping.LEAVE_REQUEST_NO: leave_request_no,  # 請假單號
                RagicLeaveFieldMapping.CREATED_DATE: current_date,  # 建立日期
                RagicLeaveFieldMapping.APPROVAL_STATUS: resolved_approval_status,  # 審核狀態 (Validated)
                
                # Approval Chain - Names (visible fields)
                RagicLeaveFieldMapping.SALES_DEPT_MANAGER_NAME: sales_dept_manager_name or "",
                RagicLeaveFieldMapping.DIRECT_SUPERVISOR_NAME: direct_supervisor_name or "",
                
                # Approval Chain - Emails (hidden fields for triggering approval workflow)
                RagicLeaveFieldMapping.SALES_DEPT_MANAGER_EMAIL: sales_dept_manager_email or "",
                RagicLeaveFieldMapping.DIRECT_SUPERVISOR_EMAIL: direct_supervisor_email or "",
            }
            
            # Log full payload for debugging
            logger.info(f"Submitting leave request to Ragic: {self._settings.ragic_url_leave}")
            logger.debug(f"Ragic payload: {ragic_payload}")
            
            # Log key fields specifically
            logger.info(
                f"Key fields - leave_type: {ragic_payload.get(RagicLeaveFieldMapping.LEAVE_TYPE)}, "
                f"leave_dates: {leave_dates_str}, "
                f"sales_dept: {ragic_payload.get(RagicLeaveFieldMapping.SALES_DEPT)}, "
                f"name: {ragic_payload.get(RagicLeaveFieldMapping.EMPLOYEE_NAME)}"
            )
            
            # Use framework's RagicService for submission
            result = await self._ragic_service.create_record_by_url(
                full_url=self._settings.ragic_url_leave,
                data=ragic_payload,
            )
            
            if not result:
                raise SubmissionError("Failed to submit leave request to Ragic")
            
            ragic_id = result.get("_ragicId")
            ragic_ids.append(ragic_id)
            submitted_dates = leave_dates
            
            logger.info(f"Leave request submitted successfully, Ragic ID: {ragic_id}")

            logger.info(f"Leave request with {len(submitted_dates)} days submitted successfully")
            
            # Send confirmation email to the applicant
            try:
                email_service = get_email_notification_service()
                email_sent = email_service.send_leave_request_confirmation(
                    to_email=account.primary_email or email,
                    employee_name=account.name,
                    leave_dates=submitted_dates,
                    leave_type=resolved_leave_type,
                    reason=reason,
                    leave_request_no=leave_request_no,
                    direct_supervisor=direct_supervisor_name,
                    sales_dept_manager=sales_dept_manager_name,
                )
                if email_sent:
                    logger.info(f"Confirmation email sent to {account.primary_email or email}")
                else:
                    logger.warning(f"Failed to send confirmation email to {account.primary_email or email}")
            except Exception as email_error:
                # Don't fail the submission if email fails
                logger.error(f"Error sending confirmation email: {email_error}")
            
            return {
                "success": True,
                "message": f"請假申請已成功送出（共 {len(submitted_dates)} 天，請假單號：{leave_request_no}）",
                "ragic_ids": ragic_ids,
                "employee": account.name,
                "dates": submitted_dates,
                "total_days": len(submitted_dates),
                "direct_supervisor": direct_supervisor_name,
                "sales_dept_manager": sales_dept_manager_name,
            }

        except httpx.HTTPError as e:
            logger.error(f"Ragic API error: {e}")
            raise SubmissionError(f"提交請假申請失敗: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error submitting leave: {e}")
            raise SubmissionError(f"請假申請提交失敗: {e}") from e


# Singleton
_leave_service: LeaveService | None = None


def get_leave_service() -> LeaveService:
    """Get singleton LeaveService instance."""
    global _leave_service
    if _leave_service is None:
        _leave_service = LeaveService()
    return _leave_service
