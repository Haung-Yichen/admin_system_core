"""
Unit Tests for core.schemas validation.

Tests Pydantic schema models for authentication.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from pydantic import ValidationError


class TestRagicEmployeeData:
    """Tests for RagicEmployeeData schema."""
    
    def test_valid_employee_data(self):
        """Test RagicEmployeeData validates correct data."""
        from core.schemas.auth import RagicEmployeeData
        
        data = RagicEmployeeData(
            employee_id="EMP001",
            email="test@example.com",
            name="Test User",
            is_active=True,
            raw_data={"key": "value"}
        )
        
        assert data.employee_id == "EMP001"
        assert data.email == "test@example.com"
        assert data.name == "Test User"
        assert data.is_active is True
    
    def test_employee_data_defaults(self):
        """Test RagicEmployeeData default values."""
        from core.schemas.auth import RagicEmployeeData
        
        data = RagicEmployeeData(
            employee_id="EMP001",
            email="test@example.com",
            name="Test User"
        )
        
        assert data.is_active is True
        assert data.raw_data == {}


class TestMagicLinkRequest:
    """Tests for MagicLinkRequest schema."""
    
    def test_valid_magic_link_request(self):
        """Test MagicLinkRequest validates correct data."""
        from core.schemas.auth import MagicLinkRequest
        
        data = MagicLinkRequest(
            email="test@example.com",
            line_user_id="U1234567890"
        )
        
        assert data.email == "test@example.com"
        assert data.line_user_id == "U1234567890"
    
    def test_invalid_email(self):
        """Test MagicLinkRequest rejects invalid email."""
        from core.schemas.auth import MagicLinkRequest
        
        with pytest.raises(ValidationError):
            MagicLinkRequest(
                email="not-an-email",
                line_user_id="U1234567890"
            )
    
    def test_empty_line_user_id(self):
        """Test MagicLinkRequest rejects empty line_user_id."""
        from core.schemas.auth import MagicLinkRequest
        
        with pytest.raises(ValidationError):
            MagicLinkRequest(
                email="test@example.com",
                line_user_id=""
            )


class TestMagicLinkResponse:
    """Tests for MagicLinkResponse schema."""
    
    def test_valid_magic_link_response(self):
        """Test MagicLinkResponse validates correct data."""
        from core.schemas.auth import MagicLinkResponse
        
        data = MagicLinkResponse(
            message="Email sent successfully",
            email_sent_to="test@example.com"
        )
        
        assert data.message == "Email sent successfully"
        assert data.email_sent_to == "test@example.com"


class TestVerifyTokenRequest:
    """Tests for VerifyTokenRequest schema."""
    
    def test_valid_verify_token_request(self):
        """Test VerifyTokenRequest validates correct data."""
        from core.schemas.auth import VerifyTokenRequest
        
        data = VerifyTokenRequest(token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        
        assert data.token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    
    def test_empty_token(self):
        """Test VerifyTokenRequest rejects empty token."""
        from core.schemas.auth import VerifyTokenRequest
        
        with pytest.raises(ValidationError):
            VerifyTokenRequest(token="")


class TestUserResponse:
    """Tests for UserResponse schema."""
    
    def test_valid_user_response(self):
        """Test UserResponse validates correct data."""
        from core.schemas.auth import UserResponse
        
        user_id = uuid4()
        now = datetime.now(timezone.utc)
        
        data = UserResponse(
            id=user_id,
            email="test@example.com",
            line_user_id="U1234567890",
            display_name="Test User",
            ragic_employee_id="EMP001",
            is_active=True,
            created_at=now,
            last_login_at=now
        )
        
        assert data.id == user_id
        assert data.email == "test@example.com"
        assert data.is_active is True
    
    def test_user_response_from_attributes(self):
        """Test UserResponse can be created from ORM model."""
        from core.schemas.auth import UserResponse
        
        class MockUser:
            id = uuid4()
            email = "test@example.com"
            line_user_id = "U1234567890"
            display_name = "Test User"
            ragic_employee_id = None
            is_active = True
            created_at = datetime.now(timezone.utc)
            last_login_at = None
        
        data = UserResponse.model_validate(MockUser())
        
        assert data.email == "test@example.com"


class TestVerifyTokenResponse:
    """Tests for VerifyTokenResponse schema."""
    
    def test_successful_verification_response(self):
        """Test VerifyTokenResponse for successful verification."""
        from core.schemas.auth import VerifyTokenResponse, UserResponse
        
        user_data = UserResponse(
            id=uuid4(),
            email="test@example.com",
            line_user_id="U1234567890",
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        
        data = VerifyTokenResponse(
            success=True,
            message="Verification successful",
            user=user_data
        )
        
        assert data.success is True
        assert data.user is not None
    
    def test_failed_verification_response(self):
        """Test VerifyTokenResponse for failed verification."""
        from core.schemas.auth import VerifyTokenResponse
        
        data = VerifyTokenResponse(
            success=False,
            message="Token expired",
            user=None
        )
        
        assert data.success is False
        assert data.user is None


class TestErrorResponse:
    """Tests for ErrorResponse schema."""
    
    def test_valid_error_response(self):
        """Test ErrorResponse validates correct data."""
        from core.schemas.auth import ErrorResponse
        
        data = ErrorResponse(
            error="validation_error",
            message="Invalid email format",
            details={"field": "email"}
        )
        
        assert data.error == "validation_error"
        assert data.message == "Invalid email format"
        assert data.details == {"field": "email"}
    
    def test_error_response_without_details(self):
        """Test ErrorResponse without details."""
        from core.schemas.auth import ErrorResponse
        
        data = ErrorResponse(
            error="not_found",
            message="Resource not found"
        )
        
        assert data.error == "not_found"
        assert data.details is None
