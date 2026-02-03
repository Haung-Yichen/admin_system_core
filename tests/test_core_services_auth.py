"""
Unit Tests for core.services.auth.

Tests AuthService and authentication token operations.
"""

import pytest
import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


class TestAuthTokenOperations:
    """Tests for JWT token creation and validation."""

    def test_create_magic_link_token(self, mock_env_vars):
        """Test create_magic_link_token() generates valid JWT."""
        from core.services.auth_token import create_magic_link_token

        token = create_magic_link_token("test@example.com", "U1234567890")

        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_magic_link_token_success(self, mock_env_vars):
        """Test decode_magic_link_token() decodes valid token."""
        from core.services.auth_token import create_magic_link_token, decode_magic_link_token

        email = "test@example.com"
        line_sub = "U1234567890"

        token = create_magic_link_token(email, line_sub)
        payload = decode_magic_link_token(token)

        assert payload.email == email
        assert payload.line_sub == line_sub
        assert payload.purpose == "magic_link"

    def test_decode_magic_link_token_expired(self, mock_env_vars):
        """Test decode_magic_link_token() raises on expired token."""
        from core.services.auth_token import decode_magic_link_token, TokenExpiredError
        import jwt

        secret = "test-secret-key-12345"
        payload = {
            "email": "test@example.com",
            "line_sub": "U1234567890",
            "exp": int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "purpose": "magic_link"
        }

        token = jwt.encode(payload, secret, algorithm="HS256")

        with pytest.raises(TokenExpiredError):
            decode_magic_link_token(token)

    def test_decode_magic_link_token_malformed(self, mock_env_vars):
        """Test decode_magic_link_token() raises on malformed token."""
        from core.services.auth_token import decode_magic_link_token, TokenInvalidError

        with pytest.raises(TokenInvalidError):
            decode_magic_link_token("malformed.token.string")


class TestAuthService:
    """Tests for AuthService class."""

    @pytest.fixture
    def mock_ragic_service(self):
        """Create a mock Ragic service."""
        from core.schemas.auth import RagicEmployeeData

        service = MagicMock()
        service.verify_email_exists = AsyncMock(return_value=RagicEmployeeData(
            employee_id="EMP001",
            email="test@example.com",
            name="Test User",
            is_active=True
        ))
        return service

    @pytest.fixture
    def auth_service(self, mock_ragic_service, mock_env_vars):
        """Create AuthService with mocked dependencies."""
        from core.services.auth import AuthService

        return AuthService(ragic_service=mock_ragic_service)

    @pytest.mark.asyncio
    async def test_initiate_magic_link_success(self, auth_service, mock_ragic_service):
        """Test initiate_magic_link() sends email on valid employee."""
        with patch.object(auth_service, '_send_verification_email', new_callable=AsyncMock) as mock_send:
            result = await auth_service.initiate_magic_link(
                email="test@example.com",
                line_sub="U1234567890"
            )

            mock_send.assert_called_once()
            # Updated to use Chinese message from user enumeration protection
            assert "如果此信箱已註冊為員工" in result or "註冊為員工" in result

    @pytest.mark.asyncio
    async def test_initiate_magic_link_email_not_found(self, auth_service, mock_ragic_service):
        """Test initiate_magic_link() does NOT raise for non-existent email (user enumeration protection)."""
        mock_ragic_service.verify_email_exists = AsyncMock(return_value=None)

        # Should return success message without raising exception
        result = await auth_service.initiate_magic_link(
            email="notfound@example.com",
            line_sub="U1234567890"
        )
        
        assert "如果此信箱已註冊為員工" in result or "註冊為員工" in result

    def test_generate_magic_link(self, auth_service, mock_env_vars):
        """Test generate_magic_link() creates valid URL."""
        # By default (from conftest.py or setup), _liff_id_verify might be empty or mocked
        # Let's ensure it's empty to test the standard link
        auth_service._liff_id_verify = ""
        
        link = auth_service.generate_magic_link(
            "test@example.com", "U1234567890")

        # Updated path without /api/ prefix
        assert "https://test.example.com/auth/verify?token=" in link
        
    def test_generate_magic_link_with_app_context(self, auth_service):
        """Test generate_magic_link() includes app context."""
        auth_service._liff_id_verify = "" # Force web link
        
        link = auth_service.generate_magic_link(
            "test@example.com", "U1234567890", app_context="chatbot")
            
        assert "app=chatbot" in link
        assert "https://test.example.com/auth/verify?" in link

    def test_generate_magic_link_liff(self, auth_service):
        """Test generate_magic_link() returns LIFF URL when configured."""
        auth_service._liff_id_verify = "12345-abcde"
        
        link = auth_service.generate_magic_link(
            "test@example.com", "U1234567890", app_context="admin")
            
        assert "https://liff.line.me/12345-abcde" in link
        assert "app=admin" in link
        assert "token=" in link

    def test_get_auth_service_singleton(self, mock_env_vars):
        """Test get_auth_service() returns singleton."""
        from core.services.auth import get_auth_service
        import core.services.auth as auth_module

        auth_module._auth_service = None

        service1 = get_auth_service()
        service2 = get_auth_service()

        assert service1 is service2
