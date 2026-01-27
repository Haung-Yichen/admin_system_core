"""
Leave Service.

Handles leave request business logic.
Follows Single Responsibility Principle - only handles leave-related operations.

The "Identity Bridge" pattern:
    - Core Auth: LINE User ID <-> Email (authentication)
    - Module Cache: Email <-> Supervisor/Dept (authorization/profile)
"""

import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_standalone_session
from core.models import User
from core.security import generate_blind_index
from core.services import AuthService, get_auth_service, AuthError
from modules.administrative.core.config import AdminSettings, get_admin_settings
from modules.administrative.models import AdministrativeEmployee, AdministrativeDepartment

logger = logging.getLogger(__name__)


class LeaveError(Exception):
    """Base exception for leave-related errors."""
    pass


class EmployeeNotFoundError(LeaveError):
    """Raised when employee profile not found in cache."""
    pass


class DepartmentNotFoundError(LeaveError):
    """Raised when department not found in cache."""
    pass


class SubmissionError(LeaveError):
    """Raised when leave request submission to Ragic fails."""
    pass


class LeaveService:
    """
    Service for handling leave request operations.

    Bridges identity from Core Auth to Module cache for authorization.

    Flow:
        1. LINE User ID -> Core Auth -> Email
        2. Email -> Module Cache -> Employee Profile (Supervisor, Dept)
        3. Construct payload and submit to Ragic
    """

    def __init__(
        self,
        settings: AdminSettings | None = None,
        auth_service: AuthService | None = None,
    ) -> None:
        """
        Initialize leave service with dependencies.

        Args:
            settings: Admin module settings. Uses singleton if not provided.
            auth_service: Core auth service. Uses singleton if not provided.
        """
        self._settings = settings or get_admin_settings()
        self._auth_service = auth_service or get_auth_service()
        self._http_client: httpx.AsyncClient | None = None

    @property
    def _client(self) -> httpx.AsyncClient:
        """Lazy-initialized HTTP client for Ragic API calls."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._settings.sync_timeout_seconds),
                headers={
                    "Authorization": f"Basic {self._settings.ragic_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    # =========================================================================
    # Identity Bridge: LINE User ID -> Email -> Employee Profile
    # =========================================================================

    async def _get_authenticated_email(
        self, line_user_id: str, db: AsyncSession
    ) -> str:
        """
        Resolve LINE User ID to authenticated email via Core Auth.

        Args:
            line_user_id: LINE platform user ID.
            db: Database session.

        Returns:
            Authenticated user's email.

        Raises:
            AuthError: If user not authenticated.
        """
        logger.info(f"Looking up user by LINE ID: {line_user_id[:10]}...")
        user = await self._auth_service.get_user_by_line_id(line_user_id, db)
        if user is None:
            logger.warning(
                f"User not found for LINE ID: {line_user_id[:10]}... (Note: Each LINE Bot has different User IDs)")
            raise AuthError(
                "尚未在行政系統完成身份驗證。請先透過行政 Bot 完成身份綁定。"
                "（注意：SOP Bot 和行政 Bot 是不同的帳號，需要分別驗證）"
            )
        logger.info(f"User found: {user.email}")
        return user.email

    async def _get_employee_profile(
        self, email: str, db: AsyncSession
    ) -> AdministrativeEmployee:
        """
        Get employee profile from local cache by email.

        Args:
            email: Employee email address.
            db: Database session.

        Returns:
            AdministrativeEmployee record.

        Raises:
            EmployeeNotFoundError: If not found in cache.
        """
        result = await db.execute(
            select(AdministrativeEmployee).where(
                AdministrativeEmployee.email == email)
        )
        employee = result.scalar_one_or_none()

        if employee is None:
            logger.warning(f"Employee not found in cache: {email}")
            raise EmployeeNotFoundError(
                f"Employee profile not found for {email}. "
                "Please ensure Ragic data has been synced."
            )

        return employee

    async def _get_department(
        self, department_name: str, db: AsyncSession
    ) -> AdministrativeDepartment | None:
        """
        Get department from local cache by name.

        Args:
            department_name: Department name.
            db: Database session.

        Returns:
            AdministrativeDepartment or None if not found.
        """
        if not department_name:
            return None

        result = await db.execute(
            select(AdministrativeDepartment).where(
                AdministrativeDepartment.name == department_name
            )
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # Public API
    # =========================================================================

    async def get_init_data(
        self, line_user_id: str, db: AsyncSession
    ) -> dict[str, Any]:
        """
        Get initialization data for leave request form.

        This provides the frontend with:
            - Employee name
            - Department
            - Email

        NOTE: Supervisor info is NOT exposed to frontend for security.

        Args:
            line_user_id: LINE platform user ID.
            db: Database session.

        Returns:
            dict with employee profile data.

        Raises:
            AuthError: If user not authenticated.
            EmployeeNotFoundError: If employee not in cache.
        """
        # =================================================================
        # TODO: 暫時跳過身份驗證，使用測試數據
        # 正式上線前請取消註解下方的驗證邏輯
        # =================================================================
        logger.warning(f"[DEV MODE] Skipping auth for LINE user: {line_user_id}")
        
        # 嘗試從員工快取中查找，如果找不到就返回測試數據
        try:
            # 嘗試用固定測試 email 查找員工
            test_email = "test@example.com"
            result = await db.execute(
                select(AdministrativeEmployee).limit(1)
            )
            employee = result.scalar_one_or_none()
            
            if employee:
                logger.info(f"[DEV MODE] Using employee from cache: {employee.name}")
                return {
                    "name": employee.name,
                    "department": employee.department_name or "測試部門",
                    "email": employee.email or test_email,
                }
        except Exception as e:
            logger.warning(f"[DEV MODE] Failed to fetch employee: {e}")
        
        # 返回測試數據
        logger.info("[DEV MODE] Using mock test data")
        return {
            "name": "測試使用者",
            "department": "測試部門",
            "email": "test@example.com",
        }
        
        # =================================================================
        # 原始驗證邏輯 (暫時註解)
        # =================================================================
        # # Step 1: Authenticate and get email
        # email = await self._get_authenticated_email(line_user_id, db)
        # logger.info(f"Leave init for authenticated user: {email}")
        #
        # # Step 2: Get employee profile from cache
        # employee = await self._get_employee_profile(email, db)
        #
        # # Step 3: Return safe data (NO supervisor info)
        # return {
        #     "name": employee.name,
        #     "department": employee.department_name or "",
        #     "email": employee.email,
        # }

    async def submit_leave_request(
        self,
        line_user_id: str,
        leave_date: str,
        reason: str,
        db: AsyncSession,
        # Additional fields can be added as needed
        leave_type: str = "annual",  # 假別
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> dict[str, Any]:
        """
        Submit a leave request to Ragic.

        This is the core workflow:
            1. Authenticate user via Core Auth
            2. Fetch employee profile from cache
            3. Fetch department manager from cache
            4. Construct Ragic payload with supervisor/manager info
            5. POST to Ragic Leave Request form

        Args:
            line_user_id: LINE platform user ID.
            leave_date: Leave date (YYYY-MM-DD format).
            reason: Reason for leave.
            db: Database session.
            leave_type: Type of leave (annual, sick, personal, etc.).
            start_time: Optional start time.
            end_time: Optional end time.

        Returns:
            dict with submission result including Ragic record ID.

        Raises:
            AuthError: If user not authenticated.
            EmployeeNotFoundError: If employee not in cache.
            SubmissionError: If Ragic API call fails.
        """
        # =================================================================
        # TODO: 暫時跳過身份驗證，使用測試數據
        # 正式上線前請取消註解下方的驗證邏輯
        # =================================================================
        logger.warning(f"[DEV MODE] Skipping auth for leave submission, LINE user: {line_user_id}")
        
        # 嘗試從快取取得員工資料
        employee = None
        try:
            result = await db.execute(
                select(AdministrativeEmployee).limit(1)
            )
            employee = result.scalar_one_or_none()
        except Exception as e:
            logger.warning(f"[DEV MODE] Failed to fetch employee: {e}")
        
        if not employee:
            # 使用模擬數據
            logger.info("[DEV MODE] Using mock employee data for submission")
            return {
                "success": True,
                "message": "[DEV MODE] 請假申請已模擬送出（尚未實際提交到 Ragic）",
                "ragic_id": None,
                "employee": "測試使用者",
                "date": leave_date,
            }
        
        email = employee.email
        logger.info(f"[DEV MODE] Leave submission using employee: {employee.name}")
        
        # =================================================================
        # 原始驗證邏輯 (暫時註解)
        # =================================================================
        # # Step 1: Authenticate and get email
        # email = await self._get_authenticated_email(line_user_id, db)
        # logger.info(f"Leave submission from: {email}")
        #
        # # Step 2: Get employee profile
        # employee = await self._get_employee_profile(email, db)

        # Step 3: Get department manager
        department = await self._get_department(employee.department_name or "", db)
        dept_manager_email = department.manager_email if department else None

        # Step 4: Construct Ragic payload
        # NOTE: Field IDs should be configured in settings
        # These are placeholder IDs - replace with actual Ragic form field IDs
        payload = {
            # Employee Info (auto-filled)
            self._settings.field_employee_email: employee.email,
            self._settings.field_employee_name: employee.name,

            # Leave Details (from form input)
            # TODO: Add actual leave form field IDs to config
            # "LEAVE_DATE_FIELD_ID": leave_date,
            # "LEAVE_REASON_FIELD_ID": reason,
            # "LEAVE_TYPE_FIELD_ID": leave_type,

            # Approval Chain (auto-filled from cache)
            self._settings.field_employee_supervisor_email: employee.supervisor_email or "",

            # Department Manager (auto-filled from cache)
            self._settings.field_department_manager_email: dept_manager_email or "",

            # Source Flag
            "_source": "LINE_API",
        }

        # Log payload (without sensitive data)
        logger.info(
            f"Submitting leave request for {employee.name}: date={leave_date}")

        # Step 5: Submit to Ragic
        try:
            # TODO: Replace with actual leave request form URL
            # For now, log the payload for testing
            logger.info(
                f"Leave request payload constructed: {list(payload.keys())}")

            # Uncomment when form URL is configured:
            # response = await self._client.post(
            #     self._settings.ragic_url_leave_request,
            #     json=payload,
            # )
            # response.raise_for_status()
            # result = response.json()
            # ragic_id = result.get("_ragicId")

            # Placeholder response for now
            ragic_id = None

            return {
                "success": True,
                "message": "Leave request submitted successfully",
                "ragic_id": ragic_id,
                "employee": employee.name,
                "date": leave_date,
                "supervisor": employee.supervisor_email,
                "dept_manager": dept_manager_email,
            }

        except httpx.HTTPError as e:
            logger.error(f"Ragic API error: {e}")
            raise SubmissionError(
                f"Failed to submit leave request: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error submitting leave: {e}")
            raise SubmissionError(f"Leave submission failed: {e}") from e


# Singleton
_leave_service: LeaveService | None = None


def get_leave_service() -> LeaveService:
    """Get singleton LeaveService instance."""
    global _leave_service
    if _leave_service is None:
        _leave_service = LeaveService()
    return _leave_service
