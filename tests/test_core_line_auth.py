"""
Unit Tests for core.line_auth.

Tests the unified LINE authentication module including:
- LineAuthMessages (Flex Message templates)
- line_auth_check (Webhook event authentication helper)
- get_verified_user (FastAPI dependency for LIFF API)
- VerifiedUser dataclass
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_auth_service():
    """Create a mock AuthService."""
    service = MagicMock()
    service.is_user_authenticated = AsyncMock(return_value=True)
    service.check_binding_status = AsyncMock(return_value={
        "sub": "U1234567890abcdef",
        "is_bound": True,
        "email": "test@company.com",
        "line_name": "Test User",
    })
    return service


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    return AsyncMock()


# =============================================================================
# Test LineAuthMessages
# =============================================================================


class TestLineAuthMessages:
    """Tests for LineAuthMessages Flex Message templates."""

    def test_get_verification_required_flex_structure(self, mock_env_vars):
        """Test that get_verification_required_flex returns correct structure."""
        from core.line_auth import LineAuthMessages

        result = LineAuthMessages.get_verification_required_flex("U123456")

        # Check overall structure
        assert result["type"] == "bubble"
        assert "hero" in result
        assert "body" in result
        assert "footer" in result

        # Check body contains required text
        body_contents = result["body"]["contents"]
        assert any(c.get("text") == "員工身份驗證" for c in body_contents)

        # Check footer has a button
        footer_contents = result["footer"]["contents"]
        assert any(c.get("type") == "button" for c in footer_contents)

    def test_get_verification_required_flex_login_url(self, mock_env_vars):
        """Test that login URL is correctly constructed."""
        from core.line_auth import LineAuthMessages

        user_id = "Utest123456"
        result = LineAuthMessages.get_verification_required_flex(user_id)

        # Find the button and check its action URI
        footer_contents = result["footer"]["contents"]
        button = next(c for c in footer_contents if c.get("type") == "button")

        assert user_id in button["action"]["uri"]
        # Updated to use template-based route
        assert "/auth/page/login" in button["action"]["uri"]

    def test_get_verification_required_messages_returns_list(self, mock_env_vars):
        """Test that get_verification_required_messages returns message list."""
        from core.line_auth import LineAuthMessages

        result = LineAuthMessages.get_verification_required_messages("U123456")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["type"] == "flex"
        assert "altText" in result[0]
        assert "contents" in result[0]

    def test_get_verification_required_flex_with_app_context(self, mock_env_vars):
        """Test that app context is correctly added to login URL."""
        from core.line_auth import LineAuthMessages

        user_id = "Utest123456"
        app_context = "administrative"
        result = LineAuthMessages.get_verification_required_flex(user_id, app_context)

        # Find the button and check its action URI
        footer_contents = result["footer"]["contents"]
        button = next(c for c in footer_contents if c.get("type") == "button")

        assert user_id in button["action"]["uri"]
        assert "/auth/page/login" in button["action"]["uri"]
        assert f"app={app_context}" in button["action"]["uri"]

    def test_get_verification_required_messages_with_app_context(self, mock_env_vars):
        """Test that messages helper passes app context correctly."""
        from core.line_auth import LineAuthMessages

        user_id = "Utest123456"
        app_context = "chatbot"
        messages = LineAuthMessages.get_verification_required_messages(user_id, app_context)

        assert len(messages) == 1
        assert messages[0]["type"] == "flex"
        
        # Check the nested flex content has the app context in URL
        flex_content = messages[0]["contents"]
        footer_contents = flex_content["footer"]["contents"]
        button = next(c for c in footer_contents if c.get("type") == "button")
        assert f"app={app_context}" in button["action"]["uri"]


# =============================================================================
# Test line_auth_check (Webhook Helper)
# =============================================================================


class TestLineAuthCheck:
    """Tests for line_auth_check helper function."""

    @pytest.mark.asyncio
    async def test_authenticated_user_returns_true(self, mock_auth_service, mock_db_session, mock_env_vars):
        """Test that authenticated user returns (True, None)."""
        from core.line_auth import line_auth_check

        mock_auth_service.is_user_authenticated = AsyncMock(return_value=True)

        is_auth, messages = await line_auth_check(
            "U123456",
            mock_db_session,
            auth_service=mock_auth_service,
        )

        assert is_auth is True
        assert messages is None
        mock_auth_service.is_user_authenticated.assert_called_once_with("U123456", mock_db_session)

    @pytest.mark.asyncio
    async def test_unauthenticated_user_returns_false_with_messages(
        self, mock_auth_service, mock_db_session, mock_env_vars
    ):
        """Test that unauthenticated user returns (False, messages)."""
        from core.line_auth import line_auth_check

        mock_auth_service.is_user_authenticated = AsyncMock(return_value=False)

        is_auth, messages = await line_auth_check(
            "U123456",
            mock_db_session,
            auth_service=mock_auth_service,
        )

        assert is_auth is False
        assert messages is not None
        assert isinstance(messages, list)
        assert len(messages) > 0
        assert messages[0]["type"] == "flex"

    @pytest.mark.asyncio
    async def test_uses_default_auth_service_if_not_provided(self, mock_db_session, mock_env_vars):
        """Test that line_auth_check uses singleton auth service if not provided."""
        from core.line_auth import line_auth_check

        with patch("core.line_auth.get_auth_service") as mock_get_service:
            mock_service = MagicMock()
            mock_service.is_user_authenticated = AsyncMock(return_value=True)
            mock_get_service.return_value = mock_service

            await line_auth_check("U123456", mock_db_session)

            mock_get_service.assert_called_once()


# =============================================================================
# Test VerifiedUser
# =============================================================================


class TestVerifiedUser:
    """Tests for VerifiedUser dataclass."""

    def test_verified_user_creation(self):
        """Test VerifiedUser can be created with required fields."""
        from core.line_auth import VerifiedUser

        user = VerifiedUser(
            line_sub="U123456",
            email="test@company.com",
        )

        assert user.line_sub == "U123456"
        assert user.email == "test@company.com"
        assert user.line_name is None

    def test_verified_user_with_line_name(self):
        """Test VerifiedUser with optional line_name."""
        from core.line_auth import VerifiedUser

        user = VerifiedUser(
            line_sub="U123456",
            email="test@company.com",
            line_name="Test User",
        )

        assert user.line_name == "Test User"


# =============================================================================
# Test AccountNotBoundResponse
# =============================================================================


class TestAccountNotBoundResponse:
    """Tests for AccountNotBoundResponse helper."""

    def test_create_returns_correct_structure(self, mock_env_vars):
        """Test AccountNotBoundResponse.create returns correct structure."""
        from core.line_auth import AccountNotBoundResponse, AUTH_ERROR_MESSAGES

        result = AccountNotBoundResponse.create(
            line_sub="U123456",
            line_name="Test User",
        )

        assert result["error"] == "account_not_bound"
        assert result["message"] == AUTH_ERROR_MESSAGES["account_not_bound"]
        assert result["line_sub"] == "U123456"
        assert result["line_name"] == "Test User"

    def test_create_without_line_name(self, mock_env_vars):
        """Test AccountNotBoundResponse.create without line_name."""
        from core.line_auth import AccountNotBoundResponse

        result = AccountNotBoundResponse.create(line_sub="U123456")

        assert result["line_sub"] == "U123456"
        assert result["line_name"] is None


# =============================================================================
# Test get_verified_user (FastAPI Dependency)
# =============================================================================


class TestGetVerifiedUser:
    """Tests for get_verified_user FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_returns_verified_user_on_success(self, mock_auth_service, mock_db_session, mock_env_vars):
        """Test that get_verified_user returns VerifiedUser on valid token."""
        from core.line_auth import get_verified_user, VerifiedUser

        result = await get_verified_user(
            x_line_id_token="valid-token",
            q_line_id_token=None,
            authorization=None,
            auth_service=mock_auth_service,
            db=mock_db_session,
        )

        assert isinstance(result, VerifiedUser)
        assert result.email == "test@company.com"
        assert result.line_sub == "U1234567890abcdef"
        assert result.line_name == "Test User"

    @pytest.mark.asyncio
    async def test_raises_401_when_no_token(self, mock_auth_service, mock_db_session, mock_env_vars):
        """Test that get_verified_user raises 401 when no token provided."""
        from core.line_auth import get_verified_user

        with pytest.raises(HTTPException) as exc_info:
            await get_verified_user(
                x_line_id_token=None,
                q_line_id_token=None,
                authorization=None,
                auth_service=mock_auth_service,
                db=mock_db_session,
            )

        assert exc_info.value.status_code == 401
        assert "LINE authentication required" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_403_when_not_bound(self, mock_auth_service, mock_db_session, mock_env_vars):
        """Test that get_verified_user raises 403 when account not bound."""
        from core.line_auth import get_verified_user

        mock_auth_service.check_binding_status = AsyncMock(return_value={
            "sub": "U123456",
            "is_bound": False,
            "email": None,
            "line_name": "Unbound User",
        })

        with pytest.raises(HTTPException) as exc_info:
            await get_verified_user(
                x_line_id_token="valid-token",
                q_line_id_token=None,
                authorization=None,
                auth_service=mock_auth_service,
                db=mock_db_session,
            )

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["error"] == "account_not_bound"

    @pytest.mark.asyncio
    async def test_uses_query_param_token(self, mock_auth_service, mock_db_session, mock_env_vars):
        """Test that get_verified_user accepts token from query parameter."""
        from core.line_auth import get_verified_user

        await get_verified_user(
            x_line_id_token=None,
            q_line_id_token="query-token",
            authorization=None,
            auth_service=mock_auth_service,
            db=mock_db_session,
        )

        mock_auth_service.check_binding_status.assert_called_once()
        call_args = mock_auth_service.check_binding_status.call_args
        assert call_args[0][0] == "query-token"

    @pytest.mark.asyncio
    async def test_uses_bearer_token(self, mock_auth_service, mock_db_session, mock_env_vars):
        """Test that get_verified_user accepts Bearer token from Authorization header."""
        from core.line_auth import get_verified_user

        await get_verified_user(
            x_line_id_token=None,
            q_line_id_token=None,
            authorization="Bearer bearer-token",
            auth_service=mock_auth_service,
            db=mock_db_session,
        )

        call_args = mock_auth_service.check_binding_status.call_args
        assert call_args[0][0] == "bearer-token"

    @pytest.mark.asyncio
    async def test_header_token_takes_priority(self, mock_auth_service, mock_db_session, mock_env_vars):
        """Test that X-Line-ID-Token header takes priority over other sources."""
        from core.line_auth import get_verified_user

        await get_verified_user(
            x_line_id_token="header-token",
            q_line_id_token="query-token",
            authorization="Bearer bearer-token",
            auth_service=mock_auth_service,
            db=mock_db_session,
        )

        call_args = mock_auth_service.check_binding_status.call_args
        assert call_args[0][0] == "header-token"

    @pytest.mark.asyncio
    async def test_raises_401_on_expired_token(self, mock_auth_service, mock_db_session, mock_env_vars):
        """Test that get_verified_user raises 401 on expired token."""
        from core.line_auth import get_verified_user, AUTH_ERROR_MESSAGES
        from core.services.auth import LineIdTokenExpiredError

        mock_auth_service.check_binding_status = AsyncMock(
            side_effect=LineIdTokenExpiredError("Token expired")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_verified_user(
                x_line_id_token="expired-token",
                q_line_id_token=None,
                authorization=None,
                auth_service=mock_auth_service,
                db=mock_db_session,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == AUTH_ERROR_MESSAGES["token_expired"]

    @pytest.mark.asyncio
    async def test_raises_401_on_invalid_token(self, mock_auth_service, mock_db_session, mock_env_vars):
        """Test that get_verified_user raises 401 on invalid token."""
        from core.line_auth import get_verified_user, AUTH_ERROR_MESSAGES
        from core.services.auth import LineIdTokenInvalidError

        mock_auth_service.check_binding_status = AsyncMock(
            side_effect=LineIdTokenInvalidError("Invalid token")
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_verified_user(
                x_line_id_token="invalid-token",
                q_line_id_token=None,
                authorization=None,
                auth_service=mock_auth_service,
                db=mock_db_session,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == AUTH_ERROR_MESSAGES["token_invalid"]


# =============================================================================
# Test AUTH_ERROR_MESSAGES Consistency
# =============================================================================


class TestAuthErrorMessages:
    """Tests for AUTH_ERROR_MESSAGES constants."""

    def test_all_required_messages_exist(self, mock_env_vars):
        """Test that all required error message keys exist."""
        from core.line_auth import AUTH_ERROR_MESSAGES

        required_keys = [
            "account_not_bound",
            "token_expired",
            "token_invalid",
            "auth_required",
        ]

        for key in required_keys:
            assert key in AUTH_ERROR_MESSAGES
            assert isinstance(AUTH_ERROR_MESSAGES[key], str)
            assert len(AUTH_ERROR_MESSAGES[key]) > 0

    def test_messages_are_in_chinese(self, mock_env_vars):
        """Test that error messages are in Chinese for user-facing display."""
        from core.line_auth import AUTH_ERROR_MESSAGES

        # Check that messages contain Chinese characters
        for key, message in AUTH_ERROR_MESSAGES.items():
            # Simple check: at least one CJK character
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in message)
            assert has_chinese, f"Message '{key}' should be in Chinese: {message}"
