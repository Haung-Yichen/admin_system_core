"""
Unified LINE Authentication Module.

Provides framework-level authentication utilities for LINE user verification.
All modules should use these functions instead of implementing their own logic.

Key Components:
    - LineAuthMessages: Unified message templates for authentication prompts
    - LineAuthDependency: FastAPI dependency for LIFF API authentication
    - line_auth_check: Helper for webhook event authentication

Usage (Webhook Events):
    from core.line_auth import line_auth_check, LineAuthMessages

    async def handle_message(user_id, reply_token, db):
        is_auth, response = await line_auth_check(user_id, db)
        if not is_auth:
            await line_service.reply(reply_token, response)
            return
        # User is authenticated, proceed...

Usage (LIFF API):
    from core.line_auth import get_verified_user

    @router.get("/endpoint")
    async def my_endpoint(user: VerifiedUser = Depends(get_verified_user)):
        # user.email contains the bound company email
        # user.line_sub contains the LINE sub
        pass
"""

import logging
from dataclasses import dataclass
from typing import Any, Annotated

from fastapi import Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.app_context import ConfigLoader
from core.database import get_db_session
from core.services.auth import (
    AuthService,
    LineIdTokenError,
    LineIdTokenExpiredError,
    LineIdTokenInvalidError,
    get_auth_service,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

# 統一的錯誤訊息 (所有模組共用)
AUTH_ERROR_MESSAGES = {
    "account_not_bound": "您的 LINE 帳號尚未綁定公司信箱，請先完成綁定。",
    "token_expired": "LINE 身份驗證已過期，請重新開啟頁面。",
    "token_invalid": "LINE 身份驗證失敗，請重新開啟頁面。",
    "auth_required": "請先驗證您的員工身份才能使用此服務。",
}


# =============================================================================
# Verified User Data Class
# =============================================================================

@dataclass
class VerifiedUser:
    """
    Represents a verified LINE user with bound company email.

    Attributes:
        line_sub: LINE OIDC subject identifier (stable across channels)
        email: Bound company email address
        line_name: LINE display name (optional)
    """
    line_sub: str
    email: str
    line_name: str | None = None


# =============================================================================
# LINE Flex Message Templates (用於 Webhook 回覆)
# =============================================================================

class LineAuthMessages:
    """
    Framework-level LINE Flex Message templates for authentication.

    All modules should use these templates to ensure consistent UX.
    """

    @staticmethod
    def get_verification_required_flex(line_user_id: str) -> dict[str, Any]:
        """
        Create a Flex Message prompting user to verify their identity.

        This is the standard message shown when an unverified user
        attempts to use any LINE Bot feature.

        Args:
            line_user_id: LINE user ID for constructing the login URL.

        Returns:
            Flex Message bubble content (not wrapped in flex message object).
        """
        config_loader = ConfigLoader()
        config_loader.load()
        base_url = config_loader.get("server.base_url", "")
        app_name = config_loader.get("server.app_name", "Admin System")
        login_url = f"{base_url}/auth/login?line_sub={line_user_id}"

        return {
            "type": "bubble",
            "hero": {
                "type": "image",
                "url": f"{base_url}/static/crown.png?v=1",
                "size": "full",
                "aspectRatio": "20:13",
                "aspectMode": "fit",
                "backgroundColor": "#FFFFFF",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "員工身份驗證",
                        "weight": "bold",
                        "size": "xl",
                        "align": "center",
                    },
                    {
                        "type": "text",
                        "text": AUTH_ERROR_MESSAGES["auth_required"],
                        "wrap": True,
                        "size": "sm",
                        "margin": "lg",
                        "align": "center",
                    },
                ],
                "paddingAll": "20px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "驗證身份",
                            "uri": login_url,
                        },
                        "style": "primary",
                        "color": "#00B900",
                    }
                ],
                "paddingAll": "15px",
            },
        }

    @staticmethod
    def get_verification_required_messages(line_user_id: str) -> list[dict[str, Any]]:
        """
        Get complete LINE message objects for verification required response.

        This returns a list of messages ready to send via LINE Messaging API.

        Args:
            line_user_id: LINE user ID for constructing the login URL.

        Returns:
            List of LINE message objects.
        """
        flex_content = LineAuthMessages.get_verification_required_flex(line_user_id)
        return [
            {
                "type": "flex",
                "altText": AUTH_ERROR_MESSAGES["auth_required"],
                "contents": flex_content,
            }
        ]


# =============================================================================
# Webhook Event Authentication Helper
# =============================================================================

async def line_auth_check(
    line_user_id: str,
    db: AsyncSession,
    auth_service: AuthService | None = None,
) -> tuple[bool, list[dict[str, Any]] | None]:
    """
    Check if a LINE user is authenticated (bound to company email).

    This is the unified method for checking user authentication in webhook handlers.
    If the user is not authenticated, returns the standard verification message.

    Args:
        line_user_id: LINE user ID from webhook event source.
        db: Database session.
        auth_service: Optional auth service instance (uses singleton if not provided).

    Returns:
        Tuple of (is_authenticated, messages_if_not_auth).
        - If authenticated: (True, None)
        - If not authenticated: (False, [verification_messages])

    Example:
        is_auth, response = await line_auth_check(user_id, db)
        if not is_auth:
            await line_service.reply(reply_token, response)
            return
        # User is authenticated, proceed...
    """
    if auth_service is None:
        auth_service = get_auth_service()

    is_bound = await auth_service.is_user_authenticated(line_user_id, db)

    if is_bound:
        return True, None
    else:
        messages = LineAuthMessages.get_verification_required_messages(line_user_id)
        return False, messages


# =============================================================================
# LIFF API Authentication Dependency
# =============================================================================

class AccountNotBoundResponse:
    """
    Standard response structure for account not bound errors.

    This ensures all API endpoints return the same error format.
    """

    @staticmethod
    def create(line_sub: str, line_name: str | None = None) -> dict[str, Any]:
        """Create the standard error response for account not bound."""
        return {
            "error": "account_not_bound",
            "message": AUTH_ERROR_MESSAGES["account_not_bound"],
            "line_sub": line_sub,
            "line_name": line_name,
        }


async def get_verified_user(
    x_line_id_token: Annotated[str | None, Header(alias="X-Line-ID-Token")] = None,
    q_line_id_token: Annotated[str | None, Query(alias="line_id_token")] = None,
    authorization: Annotated[str | None, Header()] = None,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> VerifiedUser:
    """
    FastAPI dependency to verify LINE user and get bound company email.

    This is the unified dependency for all LIFF API endpoints.
    Use this instead of implementing custom authentication logic.

    Authentication methods (in priority order):
        1. X-Line-ID-Token header
        2. line_id_token query parameter
        3. Authorization: Bearer <token> header

    Args:
        x_line_id_token: LINE ID Token from header.
        q_line_id_token: LINE ID Token from query parameter.
        authorization: Bearer token from Authorization header.
        auth_service: Auth service instance (injected).
        db: Database session (injected).

    Returns:
        VerifiedUser: Contains line_sub, email, and line_name.

    Raises:
        HTTPException 401: If no token provided or token is invalid/expired.
        HTTPException 403: If account is not bound to a company email.
    """
    # NOTE: 開發測試請使用 FastAPI 的 dependency_overrides 或 Mock，
    # 例如: app.dependency_overrides[get_verified_user] = lambda: VerifiedUser(...)
    # 不在生產程式碼中保留任何繞過驗證的後門。

    # Consolidate token inputs (Header > Query > Bearer)
    id_token = x_line_id_token or q_line_id_token
    if not id_token and authorization and authorization.startswith("Bearer "):
        id_token = authorization[7:]

    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="LINE authentication required. Provide X-Line-ID-Token header or line_id_token query parameter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        binding_status = await auth_service.check_binding_status(id_token, db)

        if not binding_status["is_bound"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=AccountNotBoundResponse.create(
                    line_sub=binding_status["sub"],
                    line_name=binding_status.get("line_name"),
                ),
            )

        return VerifiedUser(
            line_sub=binding_status["sub"],
            email=binding_status["email"],
            line_name=binding_status.get("line_name"),
        )

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


# Alias for backward compatibility
VerifyLineUser = get_verified_user
