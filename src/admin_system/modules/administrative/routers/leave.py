"""
Leave Request API Router.

Endpoints for leave request initialization and submission.
Uses LINE ID Token (OIDC) with sub-based authentication and Magic Link binding.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from core.database import get_db_session
from core.dependencies import HttpClientDep
from core.line_auth import (
    get_verified_user,
    VerifiedUser,
    AUTH_ERROR_MESSAGES,
)
from core.services import (
    AuthService,
    AuthError,
    LineIdTokenError,
    LineIdTokenExpiredError,
    LineIdTokenInvalidError,
    AccountNotBoundError,
    get_auth_service,
)
from modules.administrative.models import LeaveType
from modules.administrative.schemas.leave import (
    ErrorResponse,
    LeaveInitRequest,
    LeaveInitResponse,
    LeaveSubmitRequest,
    LeaveSubmitResponse,
    LeaveTypeOption,
    LeaveTypesResponse,
    WorkdayItem,
    WorkdaysRequest,
    WorkdaysResponse,
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
# Configuration
# =============================================================================

# 可工作日設定 (0=週一, 1=週二, 2=週三, 3=週四, 4=週五, 5=週六, 6=週日)
# 預設排除週末、週二、週四，只保留週一、週三、週五
ALLOWED_WORKDAYS = [0, 2, 4]  # 0=Monday, 2=Wednesday, 4=Friday


# =============================================================================
# Dependencies
# =============================================================================

# Environment flag to skip authentication for LOCAL development only
# SECURITY: This should NEVER be enabled in production (Cloudflare/public network)
_debug_skip_raw = os.environ.get("DEBUG_SKIP_AUTH", "").lower() in ("true", "1", "yes")
_server_host = os.environ.get("SERVER_HOST", "127.0.0.1")
_is_local = _server_host in ("127.0.0.1", "localhost")
DEBUG_SKIP_AUTH = _debug_skip_raw and _is_local  # Only works on localhost


async def get_current_user_email(
    x_line_id_token: Annotated[str | None,
                               Header(alias="X-Line-ID-Token")] = None,
    q_line_id_token: Annotated[str | None,
                               Query(alias="line_id_token")] = None,
    authorization: Annotated[str | None, Header()] = None,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> str:
    """
    Extract and verify LINE identity to get user's bound company email.

    This is a wrapper around the framework's get_verified_user for backward
    compatibility. New endpoints should use get_verified_user directly.

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
    id_token = x_line_id_token or q_line_id_token

    # Fallback: Authorization Bearer header
    if not id_token and authorization:
        if authorization.startswith("Bearer "):
            id_token = authorization[7:]

    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="LINE authentication required. Provide X-Line-ID-Token header or line_id_token query parameter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify LINE ID Token with LINE's API and extract user identity
    logger.info("Authenticating via LINE ID Token verification...")

    try:
        binding_status = await auth_service.check_binding_status(id_token, db)

        if not binding_status["is_bound"]:
            # 帳號未綁定 - 回傳 403 並指示前端導向 Core 登入頁
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ACCOUNT_NOT_BOUND",
                    "message": "您的 LINE 帳號尚未綁定公司信箱，請先完成綁定。",
                    "redirect_url": "/auth/page/login?app=administrative"
                },
            )

        return binding_status["email"]

    except LineIdTokenExpiredError as e:
        logger.warning(f"LINE ID Token expired: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_ERROR_MESSAGES["token_expired"],
            headers={"WWW-Authenticate": "Bearer"},
        )
    except LineIdTokenInvalidError as e:
        logger.warning(f"LINE ID Token invalid: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AUTH_ERROR_MESSAGES["token_invalid"],
            headers={"WWW-Authenticate": "Bearer"},
        )
    except LineIdTokenError as e:
        logger.error(f"LINE ID Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"LINE authentication failed: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# =============================================================================
# Endpoints
# =============================================================================

@router.get(
    "/types",
    response_model=LeaveTypesResponse,
    summary="Get leave type options",
    description="Get available leave types for the dropdown. Data is synced from Ragic master data.",
)
async def get_leave_types(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LeaveTypesResponse:
    """
    Get available leave type options for the leave request form.
    
    This endpoint returns leave types synced from Ragic master data table.
    No authentication required as this is reference data.
    """
    try:
        result = await db.execute(
            select(LeaveType).order_by(LeaveType.leave_type_code)
        )
        leave_types = result.scalars().all()
        
        options = [
            LeaveTypeOption(code=lt.leave_type_code, name=lt.leave_type_name)
            for lt in leave_types
        ]
        
        logger.info(f"Returning {len(options)} leave type options")
        return LeaveTypesResponse(leave_types=options)
        
    except Exception as e:
        logger.exception(f"Error fetching leave types: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch leave types: {str(e)}",
        )


@router.get(
    "/workdays",
    response_model=WorkdaysResponse,
    summary="Get workdays in date range",
    description="Get workdays (excluding weekends) between start and end date.",
)
async def get_workdays(
    start_date: Annotated[str, Query(description="Start date in YYYY-MM-DD format")],
    end_date: Annotated[str, Query(description="End date in YYYY-MM-DD format")],
) -> WorkdaysResponse:
    """
    Get workdays (excluding weekends) between start and end date.
    
    No authentication required as this is utility endpoint.
    
    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        List of workdays with date and weekday info
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Use YYYY-MM-DD. Error: {e}",
        )
    
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before or equal to end date.",
        )
    
    # Limit range to prevent abuse (max 60 days)
    if (end - start).days > 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 60 days.",
        )
    
    workdays = []
    current = start
    
    while current <= end:
        # 檢查是否為允許的工作日 (根據 ALLOWED_WORKDAYS 設定)
        # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
        if current.weekday() in ALLOWED_WORKDAYS:
            workdays.append(WorkdayItem(
                date=current.strftime("%Y-%m-%d"),
                weekday=current.weekday(),
            ))
        current += timedelta(days=1)
    
    logger.info(f"Returning {len(workdays)} workdays for {start_date} to {end_date}")
    return WorkdaysResponse(workdays=workdays, total_days=len(workdays))


@router.post(
    "/workdays",
    response_model=WorkdaysResponse,
    summary="Get workdays in date range (POST)",
    description="Get workdays (excluding weekends) between start and end date. Uses POST to avoid LINE Browser URL validation issues.",
)
async def post_workdays(
    request: WorkdaysRequest,
) -> WorkdaysResponse:
    """
    Get workdays (excluding weekends) between start and end date (POST version).
    
    This endpoint uses POST instead of GET to avoid LINE Browser's
    strict URL pattern validation that rejects query parameters.
    
    No authentication required as this is utility endpoint.
    """
    try:
        start = datetime.strptime(request.start_date, "%Y-%m-%d")
        end = datetime.strptime(request.end_date, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format. Use YYYY-MM-DD. Error: {e}",
        )
    
    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must be before or equal to end date.",
        )
    
    # Limit range to prevent abuse (max 60 days)
    if (end - start).days > 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 60 days.",
        )
    
    workdays = []
    current = start
    
    while current <= end:
        # 檢查是否為允許的工作日 (根據 ALLOWED_WORKDAYS 設定)
        # 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday
        if current.weekday() in ALLOWED_WORKDAYS:
            workdays.append(WorkdayItem(
                date=current.strftime("%Y-%m-%d"),
                weekday=current.weekday(),
            ))
        current += timedelta(days=1)
    
    logger.info(f"Returning {len(workdays)} workdays for {request.start_date} to {request.end_date}")
    return WorkdaysResponse(workdays=workdays, total_days=len(workdays))


@router.post(
    "/init",
    response_model=LeaveInitResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Employee not found"},
    },
    summary="Initialize leave request form (POST)",
    description="Get employee data for pre-filling the leave request form. Uses POST to avoid WebKit URL validation issues with long tokens.",
)
async def post_leave_init(
    request: LeaveInitRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    leave_service: Annotated[LeaveService, Depends(get_leave_service)],
    auth_service: AuthService = Depends(get_auth_service),
) -> LeaveInitResponse:
    """
    Get initialization data for leave request form (POST version).
    
    This endpoint accepts the LINE ID Token in the request body instead of
    URL parameters, which avoids WebKit browser validation issues.
    """
    # TEMPORARY: Skip auth for testing
    if DEBUG_SKIP_AUTH:
        logger.warning("[DEV MODE] Skipping LINE authentication in POST /init")
        email = "test@example.com"
    else:
        # Verify token and get email
        id_token = request.line_id_token
    
        try:
            binding_status = await auth_service.check_binding_status(id_token, db)
            
            if not binding_status["is_bound"]:
                # 帳號未綁定 - 回傳 403 並指示前端導向 Core 登入頁
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "ACCOUNT_NOT_BOUND",
                        "message": "您的 LINE 帳號尚未綁定公司信箱，請先完成綁定。",
                        "redirect_url": "/auth/page/login?app=administrative"
                    },
                )
            
            email = binding_status["email"]
            
        except LineIdTokenExpiredError as e:
            logger.warning(f"LINE ID Token expired: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=AUTH_ERROR_MESSAGES["token_expired"],
            )
        except (LineIdTokenInvalidError, LineIdTokenError) as e:
            logger.warning(f"LINE ID Token error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=AUTH_ERROR_MESSAGES["token_invalid"],
            )
    
    logger.info(f"Leave init (POST) requested for email: {email}")
    try:
        data = await leave_service.get_init_data(email, db)
        logger.info(f"Leave init success for {email}: {data.get('name', 'N/A')}")
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


@router.get(
    "/init",
    response_model=LeaveInitResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
        404: {"model": ErrorResponse, "description": "Employee not found"},
    },
    summary="Initialize leave request form (GET - deprecated)",
    description="Get employee data for pre-filling the leave request form. Requires LINE ID Token authentication.",
    deprecated=True,
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
    http_client: HttpClientDep,
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
    logger.info(f"Leave submission requested for email: {email}, dates: {request.leave_dates}")
    
    if not request.leave_dates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="至少需要選擇一個請假日期",
        )
    
    try:
        result = await leave_service.submit_leave_request(
            http_client=http_client,
            email=email,
            leave_dates=request.leave_dates,
            reason=request.reason,
            leave_type=request.leave_type,
            db=db,
        )
        return LeaveSubmitResponse(
            success=result["success"],
            message=result["message"],
            ragic_ids=result.get("ragic_ids", []),
            employee=result["employee"],
            dates=result.get("dates", []),
            total_days=result.get("total_days", 0),
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
