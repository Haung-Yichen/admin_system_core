"""
Unit Tests for Leave Router.

Tests the API endpoints for leave request initialization and submission.
Updated to match current architecture (2026-01).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI

from modules.administrative.routers.leave import (
    router,
    LeaveInitResponse,
    LeaveSubmitRequest,
    LeaveSubmitResponse,
    get_current_user_email,
)
from modules.administrative.services.leave import (
    EmployeeNotFoundError,
    SubmissionError,
)


@pytest.fixture
def app():
    """Create FastAPI app with leave router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/administrative")
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_leave_service():
    """Create mock leave service."""
    service = MagicMock()
    service.get_init_data = AsyncMock()
    service.submit_leave_request = AsyncMock()
    return service


@pytest.fixture
def mock_auth_service():
    """Create mock auth service."""
    service = MagicMock()
    service.check_binding_status = AsyncMock()
    return service


@pytest.fixture
def mock_db_session():
    """Create mock database session."""
    return AsyncMock()


class TestLeaveInitEndpoint:
    """Tests for GET /leave/init endpoint."""

    @pytest.mark.asyncio
    async def test_init_success(self, app, mock_leave_service, mock_auth_service, mock_db_session):
        """Test successful leave initialization."""
        # Mock auth - return bound status with email
        mock_auth_service.check_binding_status.return_value = {
            "is_bound": True,
            "email": "test@company.com",
            "sub": "U12345",
            "line_name": "Test User",
        }

        # Mock leave service - match current schema (no department field)
        mock_leave_service.get_init_data.return_value = {
            "name": "Test User",
            "email": "test@company.com",
            "sales_dept": "Sales Dept",
            "sales_dept_manager": "Manager Name",
            "direct_supervisor": "Supervisor Name",
        }

        # Override dependencies
        from modules.administrative.services.leave import get_leave_service
        from core.services import get_auth_service
        from core.database import get_db_session

        app.dependency_overrides[get_leave_service] = lambda: mock_leave_service
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get(
            "/api/administrative/leave/init",
            headers={"X-Line-ID-Token": "test-token"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test User"
        assert data["email"] == "test@company.com"
        assert "sales_dept" in data
        assert "direct_supervisor" in data

        # Cleanup
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_init_missing_token(self, app):
        """Test returns 401 when no token provided."""
        client = TestClient(app)
        response = client.get("/api/administrative/leave/init")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_init_account_not_bound(self, app, mock_auth_service, mock_db_session):
        """Test returns 403 when account not bound."""
        mock_auth_service.check_binding_status.return_value = {
            "is_bound": False,
            "email": None,
            "sub": "U12345",
            "line_name": "Test User",
        }

        from core.services import get_auth_service
        from core.database import get_db_session

        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get(
            "/api/administrative/leave/init",
            headers={"X-Line-ID-Token": "test-token"}
        )

        assert response.status_code == 403
        data = response.json()
        assert data["detail"]["error"] == "account_not_bound"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_init_employee_not_found(
        self, app, mock_leave_service, mock_auth_service, mock_db_session
    ):
        """Test returns 404 when employee not in cache."""
        mock_auth_service.check_binding_status.return_value = {
            "is_bound": True,
            "email": "test@company.com",
            "sub": "U12345",
        }
        mock_leave_service.get_init_data.side_effect = EmployeeNotFoundError(
            "Not found")

        from modules.administrative.services.leave import get_leave_service
        from core.services import get_auth_service
        from core.database import get_db_session

        app.dependency_overrides[get_leave_service] = lambda: mock_leave_service
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.get(
            "/api/administrative/leave/init",
            headers={"X-Line-ID-Token": "test-token"}
        )

        assert response.status_code == 404

        app.dependency_overrides.clear()


class TestLeaveSubmitEndpoint:
    """Tests for POST /leave/submit endpoint."""

    @pytest.mark.asyncio
    async def test_submit_success(
        self, app, mock_leave_service, mock_auth_service, mock_db_session
    ):
        """Test successful leave submission."""
        mock_auth_service.check_binding_status.return_value = {
            "is_bound": True,
            "email": "test@company.com",
            "sub": "U12345",
        }
        mock_leave_service.submit_leave_request.return_value = {
            "success": True,
            "message": "Leave request submitted",
            "ragic_ids": [123, 124],
            "employee": "Test User",
            "dates": ["2024-03-15", "2024-03-16"],
            "total_days": 2,
        }

        from modules.administrative.services.leave import get_leave_service
        from core.services import get_auth_service
        from core.database import get_db_session

        app.dependency_overrides[get_leave_service] = lambda: mock_leave_service
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/administrative/leave/submit",
            headers={"X-Line-ID-Token": "test-token"},
            json={
                "leave_dates": ["2024-03-15", "2024-03-16"],
                "reason": "Personal matters",
                "leave_type": "事假",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_days"] == 2
        assert len(data["ragic_ids"]) == 2

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_submit_missing_token(self, app):
        """Test returns 401 when no token provided."""
        client = TestClient(app)
        response = client.post(
            "/api/administrative/leave/submit",
            json={
                "leave_dates": ["2024-03-15"],
                "reason": "Test",
            }
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_submit_employee_not_found(
        self, app, mock_leave_service, mock_auth_service, mock_db_session
    ):
        """Test returns 404 when employee not found."""
        mock_auth_service.check_binding_status.return_value = {
            "is_bound": True,
            "email": "test@company.com",
            "sub": "U12345",
        }
        mock_leave_service.submit_leave_request.side_effect = EmployeeNotFoundError(
            "Not found")

        from modules.administrative.services.leave import get_leave_service
        from core.services import get_auth_service
        from core.database import get_db_session

        app.dependency_overrides[get_leave_service] = lambda: mock_leave_service
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/administrative/leave/submit",
            headers={"X-Line-ID-Token": "test-token"},
            json={
                "leave_dates": ["2024-03-15"],
                "reason": "Test",
            }
        )

        assert response.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_submit_ragic_error(
        self, app, mock_leave_service, mock_auth_service, mock_db_session
    ):
        """Test returns 502 when Ragic submission fails."""
        mock_auth_service.check_binding_status.return_value = {
            "is_bound": True,
            "email": "test@company.com",
            "sub": "U12345",
        }
        mock_leave_service.submit_leave_request.side_effect = SubmissionError(
            "Ragic API error")

        from modules.administrative.services.leave import get_leave_service
        from core.services import get_auth_service
        from core.database import get_db_session

        app.dependency_overrides[get_leave_service] = lambda: mock_leave_service
        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/administrative/leave/submit",
            headers={"X-Line-ID-Token": "test-token"},
            json={
                "leave_dates": ["2024-03-15"],
                "reason": "Test",
            }
        )

        assert response.status_code == 502

        app.dependency_overrides.clear()


class TestRequestSchemas:
    """Tests for request/response schema validation."""

    def test_leave_init_response_schema(self):
        """Test LeaveInitResponse schema (current architecture)."""
        response = LeaveInitResponse(
            name="Test User",
            email="test@company.com",
            sales_dept="Sales Dept",
            sales_dept_manager="Manager",
            direct_supervisor="Supervisor",
        )
        assert response.name == "Test User"
        assert response.email == "test@company.com"
        assert response.sales_dept == "Sales Dept"

    def test_leave_submit_request_schema(self):
        """Test LeaveSubmitRequest schema (current architecture - uses leave_dates list)."""
        request = LeaveSubmitRequest(
            leave_dates=["2024-03-15", "2024-03-16"],
            reason="Personal matters",
            leave_type="事假",
        )
        assert request.leave_dates == ["2024-03-15", "2024-03-16"]
        assert request.reason == "Personal matters"
        assert request.leave_type == "事假"

    def test_leave_submit_request_defaults(self):
        """Test LeaveSubmitRequest default values."""
        request = LeaveSubmitRequest(
            leave_dates=["2024-03-15"],
            reason="Test",
        )
        assert request.leave_type == "特休"  # default

    def test_leave_submit_response_schema(self):
        """Test LeaveSubmitResponse schema (current architecture - uses ragic_ids list)."""
        response = LeaveSubmitResponse(
            success=True,
            message="Submitted",
            ragic_ids=[123, 124],
            employee="Test User",
            dates=["2024-03-15", "2024-03-16"],
            total_days=2,
        )
        assert response.success is True
        assert response.ragic_ids == [123, 124]
        assert response.total_days == 2


class TestWorkdaysEndpoint:
    """Tests for workdays query endpoint."""

    @pytest.mark.asyncio
    async def test_workdays_success(self, app):
        """Test successful workdays query."""
        client = TestClient(app)
        response = client.post(
            "/api/administrative/leave/workdays",
            json={
                "start_date": "2024-03-01",
                "end_date": "2024-03-31",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "workdays" in data
        assert "total_days" in data
