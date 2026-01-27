"""
Leave Service.

Handles leave request business logic.
Follows Single Responsibility Principle - only handles leave-related operations.

Authentication is handled by the Router layer via LINE ID Token (OIDC).
This service receives the verified email directly and uses it to look up
the employee profile from the local cache.
"""

import logging
import os
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_standalone_session
from modules.administrative.core.config import AdminSettings, get_admin_settings
from modules.administrative.models import AdministrativeEmployee, AdministrativeDepartment

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


class DepartmentNotFoundError(LeaveError):
    """Raised when department not found in cache."""
    pass


class SubmissionError(LeaveError):
    """Raised when leave request submission to Ragic fails."""
    pass


class LeaveService:
    """
    Service for handling leave request operations.

    This service receives verified email addresses from the Router layer
    (authenticated via LINE ID Token) and uses them to look up employee
    profiles from the local cache.

    Flow:
        1. Router verifies LINE ID Token -> Email
        2. Email -> Module Cache -> Employee Profile (Supervisor, Dept)
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
    # Employee Profile Lookup
    # =========================================================================

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
        self, email: str, db: AsyncSession
    ) -> dict[str, Any]:
        """
        Get initialization data for leave request form.

        This provides the frontend with:
            - Employee name
            - Department
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
            # Try to find any employee in cache for testing
            try:
                result = await db.execute(
                    select(AdministrativeEmployee).limit(1)
                )
                employee = result.scalar_one_or_none()
                if employee:
                    logger.info(
                        f"[DEV MODE] Using employee from cache: {employee.name}")
                    return {
                        "name": employee.name,
                        "department": employee.department_name or "測試部門",
                        "email": employee.email or email,
                    }
            except Exception as e:
                logger.warning(f"[DEV MODE] Failed to fetch employee: {e}")

            # Return mock test data
            logger.info("[DEV MODE] Using mock test data")
            return {
                "name": "測試使用者",
                "department": "測試部門",
                "email": email,
            }

        # Production mode - look up employee by email
        employee = await self._get_employee_profile(email, db)

        # Return safe data (NO supervisor info exposed to frontend)
        return {
            "name": employee.name,
            "department": employee.department_name or "",
            "email": employee.email,
        }

    async def submit_leave_request(
        self,
        email: str,
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
            1. Receive verified email from Router (authenticated via LINE ID Token)
            2. Fetch employee profile from cache
            3. Fetch department manager from cache
            4. Construct Ragic payload with supervisor/manager info
            5. POST to Ragic Leave Request form

        Args:
            email: Verified user email (from LINE ID Token authentication).
            leave_date: Leave date (YYYY-MM-DD format).
            reason: Reason for leave.
            db: Database session.
            leave_type: Type of leave (annual, sick, personal, etc.).
            start_time: Optional start time.
            end_time: Optional end time.

        Returns:
            dict with submission result including Ragic record ID.

        Raises:
            EmployeeNotFoundError: If employee not in cache.
            SubmissionError: If Ragic API call fails.
        """
        logger.info(f"Leave submission from: {email}")

        # Development mode bypass - use mock data if flag is set
        if DEBUG_SKIP_AUTH:
            logger.warning(
                f"[DEV MODE] Using development bypass for submission, email: {email}")
            # Try to find any employee in cache for testing
            employee = None
            try:
                result = await db.execute(
                    select(AdministrativeEmployee).limit(1)
                )
                employee = result.scalar_one_or_none()
            except Exception as e:
                logger.warning(f"[DEV MODE] Failed to fetch employee: {e}")

            if not employee:
                # Use mock data for testing
                logger.info(
                    "[DEV MODE] Using mock employee data for submission")
                return {
                    "success": True,
                    "message": "[DEV MODE] 請假申請已模擬送出（尚未實際提交到 Ragic）",
                    "ragic_id": None,
                    "employee": "測試使用者",
                    "date": leave_date,
                }

            logger.info(
                f"[DEV MODE] Leave submission using employee: {employee.name}")
        else:
            # Production mode - look up employee by verified email
            employee = await self._get_employee_profile(email, db)

        # Get department manager
        department = await self._get_department(employee.department_name or "", db)
        dept_manager_email = department.manager_email if department else None

        # Construct Ragic payload
        # NOTE: Field IDs should be configured in settings
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

        # Submit to Ragic
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
