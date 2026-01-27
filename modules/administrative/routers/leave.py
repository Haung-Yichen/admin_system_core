"""
Leave Request API Router.

Endpoints for leave request initialization and submission.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session
from core.services import AuthError
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

async def get_line_user_id(
    x_line_user_id: Annotated[str | None,
                              Header(alias="X-Line-User-ID")] = None,
    line_user_id: str | None = None,  # Query param fallback
) -> str:
    """
    Extract LINE User ID from header or query parameter.

    Priority: Header > Query param

    In production, this should come from a signed LIFF token.
    For development, we accept it directly.
    """
    user_id = x_line_user_id or line_user_id
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="LINE User ID is required. Provide via X-Line-User-ID header or line_user_id query param.",
        )
    return user_id


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
    description="Get employee data for pre-filling the leave request form.",
)
async def get_leave_init(
    line_user_id: Annotated[str, Depends(get_line_user_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    leave_service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveInitResponse:
    """
    Get initialization data for leave request form.

    This endpoint is called by the LIFF app when the leave form is opened.
    It returns the authenticated user's profile for pre-filling the form.
    """
    logger.info(f"Leave init requested for LINE user: {line_user_id}")
    try:
        data = await leave_service.get_init_data(line_user_id, db)
        logger.info(
            f"Leave init success for {line_user_id}: {data.get('name', 'N/A')}")
        return LeaveInitResponse(**data)

    except AuthError as e:
        logger.warning(f"Auth error for {line_user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except EmployeeNotFoundError as e:
        logger.warning(f"Employee not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(
            f"Unexpected error in leave init for {line_user_id}: {e}")
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
    description="Submit a leave request to Ragic.",
)
async def submit_leave_request(
    request: LeaveSubmitRequest,
    line_user_id: Annotated[str, Depends(get_line_user_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    leave_service: Annotated[LeaveService, Depends(get_leave_service)],
) -> LeaveSubmitResponse:
    """
    Submit a leave request.

    The backend automatically fills in:
    - Supervisor email (from employee cache)
    - Department manager email (from department cache)
    - Source flag ("LINE_API")
    """
    try:
        result = await leave_service.submit_leave_request(
            line_user_id=line_user_id,
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

    except AuthError as e:
        logger.warning(f"Auth error during submission: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
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
