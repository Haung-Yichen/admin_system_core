"""
Unit Tests for Leave Router.

Tests the API endpoints for leave request initialization and submission.
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

        # Mock leave service
        mock_leave_service.get_init_data.return_value = {
            "name": "Test User",
            "department": "Engineering",
            "email": "test@company.com",
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
        assert data["department"] == "Engineering"
        assert data["email"] == "test@company.com"

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
        assert "detail" in data
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
            "message": "Submitted",
            "ragic_id": 123,
            "employee": "Test User",
            "date": "2024-03-15",
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
                "leave_date": "2024-03-15",
                "reason": "Personal matters",
                "leave_type": "personal",
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["ragic_id"] == 123

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_submit_validation_error(
        self, app, mock_auth_service, mock_db_session
    ):
        """Test returns 422 on validation error."""
        mock_auth_service.check_binding_status.return_value = {
            "is_bound": True,
            "email": "test@company.com",
            "sub": "U12345",
        }

        from core.services import get_auth_service
        from core.database import get_db_session

        app.dependency_overrides[get_auth_service] = lambda: mock_auth_service
        app.dependency_overrides[get_db_session] = lambda: mock_db_session

        client = TestClient(app)
        response = client.post(
            "/api/administrative/leave/submit",
            headers={"X-Line-ID-Token": "test-token"},
            json={
                "leave_date": "2024-03-15",
                # Missing required 'reason' field
            }
        )

        assert response.status_code == 422

        app.dependency_overrides.clear()

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
                "leave_date": "2024-03-15",
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
            "Ragic error")

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
                "leave_date": "2024-03-15",
                "reason": "Test",
            }
        )

        assert response.status_code == 502

        app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Tests for GET /leave/health endpoint."""

    def test_health_check(self, app):
        """Test health check returns ok."""
        client = TestClient(app)
        response = client.get("/api/administrative/leave/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "leave"


class TestRequestSchemas:
    """Tests for request/response schema validation."""

    def test_leave_init_response_schema(self):
        """Test LeaveInitResponse schema."""
        response = LeaveInitResponse(
            name="Test User",
            department="Engineering",
            email="test@company.com"
        )
        assert response.name == "Test User"
        assert response.department == "Engineering"
        assert response.email == "test@company.com"

    def test_leave_submit_request_schema(self):
        """Test LeaveSubmitRequest schema."""
        request = LeaveSubmitRequest(
            leave_date="2024-03-15",
            reason="Personal matters",
            leave_type="personal",
            start_time="09:00",
            end_time="18:00",
        )
        assert request.leave_date == "2024-03-15"
        assert request.reason == "Personal matters"
        assert request.leave_type == "personal"

    def test_leave_submit_request_defaults(self):
        """Test LeaveSubmitRequest default values."""
        request = LeaveSubmitRequest(
            leave_date="2024-03-15",
            reason="Test",
        )
        assert request.leave_type == "annual"  # default
        assert request.start_time is None
        assert request.end_time is None

    def test_leave_submit_response_schema(self):
        """Test LeaveSubmitResponse schema."""
        response = LeaveSubmitResponse(
            success=True,
            message="Submitted",
            ragic_id=123,
            employee="Test User",
            date="2024-03-15",
        )
        assert response.success is True
        assert response.ragic_id == 123
