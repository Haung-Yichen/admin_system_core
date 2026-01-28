"""
Leave Request API Router.

Endpoints for leave request initialization and submission.
Uses LINE ID Token (OIDC) with sub-based authentication and Magic Link binding.
"""

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session
from core.services import (
    AuthService,
    AuthError,
    LineIdTokenError,
    LineIdTokenExpiredError,
    LineIdTokenInvalidError,
    AccountNotBoundError,
    get_auth_service,
)
from modules.administrative.services.leave import (
    LeaveService,
    get_leave_service,
    EmployeeNotFoundError,
    SubmissionError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leave", tags=["Leave"])


# =============================================================================
# Request/Response Schemas
# =============================================================================

class LeaveInitResponse(BaseModel):
    """Response for leave form initialization."""
    name: str = Field(..., description="Employee name")
    department: str = Field(..., description="Department name")
    email: str = Field(..., description="Employee email")


class LeaveSubmitRequest(BaseModel):
    """Request body for leave submission."""
    leave_date: str = Field(..., description="Leave date in YYYY-MM-DD format")
    reason: str = Field(..., min_length=1, max_length=500,
                        description="Reason for leave")
    leave_type: str = Field(default="annual", description="Type of leave")
    start_time: str | None = Field(
        default=None, description="Start time (HH:MM)")
    end_time: str | None = Field(default=None, description="End time (HH:MM)")


class LeaveSubmitResponse(BaseModel):
    """Response for leave submission."""
    success: bool
    message: str
    ragic_id: int | None = None
    employee: str
    date: str


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str


# =============================================================================
# Dependencies
# =============================================================================

# Environment flag to skip authentication for development/testing
DEBUG_SKIP_AUTH = os.environ.get(
    "DEBUG_SKIP_AUTH", "").lower() in ("true", "1", "yes")


async def get_current_user_email(
    x_line_id_token: Annotated[str | None,
                               Header(alias="X-Line-ID-Token")] = None,
    x_line_user_id: Annotated[str | None,
                              Header(alias="X-Line-User-Id")] = None,
    q_line_id_token: Annotated[str | None,
                               Query(alias="line_id_token")] = None,
    q_line_user_id: Annotated[str | None,
                              Query(alias="line_user_id")] = None,
    authorization: Annotated[str | None, Header()] = None,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> str:
    """
    Extract and verify LINE identity to get user's bound company email.

    Authentication methods (in order of preference):
    1. X-Line-User-Id header or line_user_id query param - Direct lookup by LINE userId from LIFF profile
    2. X-Line-ID-Token header or line_id_token query param - Verify LINE ID Token and extract sub
    3. Authorization: Bearer <token> header - Fallback for ID Token

    The X-Line-User-Id method is preferred for LIFF apps because:
    - The userId from liff.getProfile() matches the webhook userId
    - This ensures consistency with the binding created via webhook

    Returns:
        str: User's bound company email.

    Raises:
        HTTPException 401: If authentication fails.
        HTTPException 403: If account is not bound to a company email.
    """
    # Development mode bypass
    if DEBUG_SKIP_AUTH:
        logger.warning("[DEV MODE] Skipping LINE authentication")
        return "test@example.com"

    # Consolidate inputs (Header > Query)
    user_id = x_line_user_id or q_line_user_id
    id_token = x_line_id_token or q_line_id_token

    # Method 1: Direct lookup by LINE User ID (from LIFF profile)
    if user_id:
        logger.info(
            f"Authenticating via LINE User ID: {user_id[:8]}...")
        bound_email = await auth_service.get_bound_email_by_line_sub(user_id, db)

        if bound_email:
            logger.info(f"User authenticated via LINE User ID: {bound_email}")
            return bound_email
        else:
            # Account not bound
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "account_not_bound",
                    "message": "您的 LINE 帳號尚未綁定公司信箱，請先完成綁定。",
                    "line_sub": user_id,
                    "line_name": None,
                },
            )

    # Method 2: Verify LINE ID Token
    if not id_token and authorization:
        if authorization.startswith("Bearer "):
            id_token = authorization[7:]

    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="LINE authentication required. Provide X-Line-User-Id or X-Line-ID-Token header/query.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        binding_status = await auth_service.check_binding_status(id_token, db)

        if not binding_status["is_bound"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "account_not_bound",
                    "message": "您的 LINE 帳號尚未綁定公司信箱，請先完成綁定。",
                    "line_sub": binding_status["sub"],
                    "line_name": binding_status.get("line_name"),
                },
            )

        return binding_status["email"]

    except LineIdTokenExpiredError as e:
        logger.warning(f"LINE ID Token expired: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="LINE ID Token has expired. Please re-authenticate.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except LineIdTokenInvalidError as e:
        logger.warning(f"LINE ID Token invalid: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid LINE ID Token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except LineIdTokenError as e:
        logger.error(f"LINE ID Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"LINE ID Token verification failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/init",
    response_model=LeaveInitResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Employee not found"},
    },
    summary="Initialize leave request form",
    description="Get employee data for pre-filling the leave request form. Requires LINE ID Token authentication.",
)
async def get_leave_init(
    email: Annotated[str, Depends(get_current_user_email)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    leave_service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveInitResponse:
    """
    Get initialization data for leave request form.

    This endpoint is called by the LIFF app when the leave form is opened.
    It returns the authenticated user's profile for pre-filling the form.

    Authentication is performed via LINE ID Token (OIDC), which provides
    the user's verified email address.
    """
    logger.info(f"Leave init requested for email: {email}")
    try:
        data = await leave_service.get_init_data(email, db)
        logger.info(
            f"Leave init success for {email}: {data.get('name', 'N/A')}")
        return LeaveInitResponse(**data)

    except EmployeeNotFoundError as e:
        logger.warning(f"Employee not found for {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Unexpected error in leave init for {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error: {str(e)}",
        )


@router.post(
    "/submit",
    response_model=LeaveSubmitResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Employee not found"},
        502: {"model": ErrorResponse, "description": "Ragic API error"},
    },
    summary="Submit leave request",
    description="Submit a leave request to Ragic. Requires LINE ID Token authentication.",
)
async def submit_leave_request(
    request: LeaveSubmitRequest,
    email: Annotated[str, Depends(get_current_user_email)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    leave_service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveSubmitResponse:
    """
    Submit a leave request.

    Authentication is performed via LINE ID Token (OIDC), which provides
    the user's verified email address.

    The backend automatically fills in:
    - Supervisor email (from employee cache)
    - Department manager email (from department cache)
    - Source flag ("LINE_API")
    """
    logger.info(f"Leave submission requested for email: {email}")
    try:
        result = await leave_service.submit_leave_request(
            email=email,
            leave_date=request.leave_date,
            reason=request.reason,
            leave_type=request.leave_type,
            start_time=request.start_time,
            end_time=request.end_time,
            db=db,
        )
        return LeaveSubmitResponse(
            success=result["success"],
            message=result["message"],
            ragic_id=result.get("ragic_id"),
            employee=result["employee"],
            date=result["date"],
        )
    except EmployeeNotFoundError as e:
        logger.warning(f"Employee not found during submission: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except SubmissionError as e:
        logger.error(f"Submission error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )


@router.get(
    "/health",
    summary="Health check",
    description="Check if leave API is operational.",
)
async def health_check() -> dict:
    """Simple health check endpoint."""
    return {"status": "ok", "service": "leave"}
