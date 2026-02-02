"""
Leave Request Schemas.

Pydantic models for leave request API endpoints.
Extracted from routers/leave.py for compliance with module development guidelines.
"""

from pydantic import BaseModel, Field


class LeaveTypeOption(BaseModel):
    """Leave type option for dropdown."""

    code: str = Field(..., description="假別編號")
    name: str = Field(..., description="請假類別名稱")


class LeaveTypesResponse(BaseModel):
    """Response for leave type options."""

    leave_types: list[LeaveTypeOption] = Field(default_factory=list)


class LeaveInitResponse(BaseModel):
    """Response for leave form initialization."""

    name: str = Field(..., description="Employee name")
    email: str = Field(..., description="Employee email")
    # Extended applicant info
    sales_dept: str = Field(default="", description="營業部名稱 (Sales Department)")
    sales_dept_manager: str = Field(
        default="", description="營業部負責人 (Sales Dept Manager)"
    )
    direct_supervisor: str = Field(
        default="", description="直屬主管 (Direct Supervisor)"
    )


class LeaveSubmitRequest(BaseModel):
    """Request body for leave submission."""

    leave_dates: list[str] = Field(
        ..., description="List of leave dates in YYYY-MM-DD format"
    )
    reason: str = Field(
        ..., min_length=1, max_length=500, description="Reason for leave"
    )
    leave_type: str = Field(
        default="特休", description="Type of leave (假別名稱，如：特休、事假、病假等)"
    )


class LeaveInitRequest(BaseModel):
    """Request body for leave init (POST mode to avoid WebKit URL issues)."""

    line_id_token: str = Field(..., description="LINE ID Token for authentication")


class WorkdayItem(BaseModel):
    """Single workday item."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    weekday: int = Field(..., description="Weekday (0=Monday, 6=Sunday)")


class WorkdaysResponse(BaseModel):
    """Response for workdays query."""

    workdays: list[WorkdayItem] = Field(default_factory=list)
    total_days: int = Field(0, description="Total workdays count")


class WorkdaysRequest(BaseModel):
    """Request body for workdays query (POST mode to avoid LINE Browser URL issues)."""

    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")


class LeaveSubmitResponse(BaseModel):
    """Response for leave submission."""

    success: bool
    message: str
    ragic_ids: list[int | None] = Field(
        default_factory=list, description="Ragic record IDs for each submitted date"
    )
    employee: str
    dates: list[str] = Field(default_factory=list, description="Submitted leave dates")
    total_days: int = Field(0, description="Total days submitted")


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str
