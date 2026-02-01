"""
Core Authentication Service.

Handles LINE ID Token (OIDC) verification and Magic Link binding flow.
This is a framework-level service used by all modules requiring user authentication.

Identity Strategy:
    - LINE `sub` (OIDC Subject Identifier) is used as the stable LINE identity
    - `sub` is consistent across all LINE Channels for the same user
    - Company email is bound via Magic Link verification
"""

import hashlib
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.app_context import ConfigLoader
from core.models import User, UsedToken
from core.schemas.auth import UserResponse
from core.security import generate_blind_index
from core.services.ragic import RagicService, get_ragic_service

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================

class AuthError(Exception):
    """Base exception for authentication errors."""
    pass


class EmailNotFoundError(AuthError):
    """Raised when email is not found in Ragic database."""
    pass


# Import EmailSendError from email module for consistency
from core.services.email import EmailSendError


class UserBindingError(AuthError):
    """Raised when user binding fails."""
    pass


class TokenAlreadyUsedError(AuthError):
    """Raised when magic link token has already been used."""
    pass


class TokenExpiredError(AuthError):
    """Raised when magic link token has expired."""
    pass


class TokenInvalidError(AuthError):
    """Raised when magic link token is invalid."""
    pass


class LineIdTokenError(AuthError):
    """Raised when LINE ID Token verification fails."""
    pass


class LineIdTokenExpiredError(LineIdTokenError):
    """Raised when LINE ID Token has expired."""
    pass


class LineIdTokenInvalidError(LineIdTokenError):
    """Raised when LINE ID Token is invalid (signature, issuer, or audience mismatch)."""
    pass


class AccountNotBoundError(AuthError):
    """Raised when LINE account is not bound to a company email."""
    pass


# =============================================================================
# Auth Service
# =============================================================================

class AuthService:
    """
    Service for LINE ID Token verification and Magic Link binding.

    Authentication Flow:
        1. Frontend calls liff.getIDToken() to get LINE ID Token
        2. Backend verifies token and extracts 'sub' (stable LINE identifier)
        3. Backend checks if 'sub' is bound to a company email
        4. If bound: return company email for downstream use
        5. If not bound: return 403 with binding instructions

    Binding Flow:
        1. User enters company email in binding UI
        2. Backend sends Magic Link to company email
        3. User clicks link to verify ownership
        4. Backend creates binding: line_sub <-> company_email
    """

    # LINE API endpoint for ID Token verification
    LINE_TOKEN_VERIFY_URL = "https://api.line.me/oauth2/v2.1/verify"

    def __init__(
        self,
        ragic_service: RagicService | None = None,
        config_loader: ConfigLoader | None = None,
    ) -> None:
        """
        Initialize AuthService with injectable dependencies.

        Args:
            ragic_service: RagicService instance for employee verification.
                          If None, uses global singleton.
            config_loader: ConfigLoader instance for configuration.
                          If None, creates and loads a new instance.

        Note:
            For unit testing, inject mock dependencies:
            >>> mock_ragic = Mock(spec=RagicService)
            >>> mock_config = Mock(spec=ConfigLoader)
            >>> service = AuthService(ragic_service=mock_ragic, config_loader=mock_config)
        """
        self._ragic_service = ragic_service or get_ragic_service()

        # Use injected config loader or create new one
        if config_loader is not None:
            self._config_loader = config_loader
        else:
            self._config_loader = ConfigLoader()
            self._config_loader.load()

        self._security_config = self._config_loader.get("security", {})
        self._email_config = self._config_loader.get("email", {})
        self._app_name = self._config_loader.get(
            "server.app_name", "Admin System")

        # LINE Channel ID for token verification (aud check)
        self._line_channel_id = self._config_loader.get("line.channel_id", "")

        # HTTP client for LINE API calls
        self._http_client: httpx.AsyncClient | None = None

    @property
    def _client(self) -> httpx.AsyncClient:
        """Lazy-initialized HTTP client for LINE API calls."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    # =========================================================================
    # LINE ID Token (OIDC) Verification
    # =========================================================================

    async def verify_line_id_token(self, id_token: str) -> dict[str, Any]:
        """
        Verify LINE ID Token and extract user's 'sub' claim.

        The 'sub' claim is the unique LINE user identifier that is consistent
        across all channels under the same provider. This solves the problem
        of different userId per channel.

        Args:
            id_token: The LINE ID Token from LIFF frontend.

        Returns:
            dict: Token data containing:
                - sub: str - Unique LINE user identifier (REQUIRED)
                - name: str | None - User's display name
                - picture: str | None - User's profile picture URL
                - email: str | None - User's LINE email (if granted, NOT company email)

        Raises:
            LineIdTokenExpiredError: If the token has expired.
            LineIdTokenInvalidError: If the token is invalid.
            LineIdTokenError: For other verification failures.
        """
        logger.info("Verifying LINE ID Token")

        if not id_token:
            raise LineIdTokenInvalidError("ID Token is required")

        if not self._line_channel_id:
            logger.error("LINE Channel ID not configured")
            raise LineIdTokenError(
                "LINE Channel ID not configured in server settings")

        try:
            # Call LINE Verify API
            response = await self._client.post(
                self.LINE_TOKEN_VERIFY_URL,
                data={
                    "id_token": id_token,
                    "client_id": self._line_channel_id,
                },
            )

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                error_code = error_data.get("error", "unknown")
                error_description = error_data.get(
                    "error_description", "Unknown error")

                logger.warning(
                    f"LINE Token verification failed: {error_code} - {error_description}")

                # Map LINE API errors to specific exceptions
                if "expired" in error_description.lower():
                    raise LineIdTokenExpiredError("LINE ID Token has expired")
                elif error_code in ("invalid_request", "invalid_id_token"):
                    raise LineIdTokenInvalidError(
                        f"Invalid LINE ID Token: {error_description}")
                else:
                    raise LineIdTokenError(
                        f"Token verification failed: {error_description}")

            # Parse the verified token payload
            token_data = response.json()

            # Validate issuer (should be https://access.line.me)
            issuer = token_data.get("iss", "")
            if issuer != "https://access.line.me":
                logger.warning(f"Invalid token issuer: {issuer}")
                raise LineIdTokenInvalidError(
                    f"Invalid token issuer: {issuer}")

            # Validate audience (should match our channel ID)
            audience = token_data.get("aud", "")
            if audience != self._line_channel_id:
                logger.warning(
                    f"Token audience mismatch: expected {self._line_channel_id}, got {audience}")
                raise LineIdTokenInvalidError(
                    "Token audience does not match this application")

            # Extract 'sub' - this is REQUIRED and always present in valid tokens
            sub = token_data.get("sub")
            if not sub:
                logger.error("LINE ID Token does not contain 'sub' claim")
                raise LineIdTokenInvalidError(
                    "Invalid token: missing 'sub' claim")

            logger.info(
                f"LINE ID Token verified successfully for sub: {sub[:8]}...")

            return {
                "sub": sub,
                "name": token_data.get("name"),
                "picture": token_data.get("picture"),
                # LINE email, NOT company email
                "email": token_data.get("email"),
            }

        except (LineIdTokenError, LineIdTokenExpiredError, LineIdTokenInvalidError):
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during LINE token verification: {e}")
            raise LineIdTokenError(
                f"Failed to verify LINE ID Token: {e}") from e
        except Exception as e:
            logger.error(
                f"Unexpected error during LINE token verification: {e}")
            raise LineIdTokenError(f"Token verification failed: {e}") from e

    # =========================================================================
    # Binding Status Check
    # =========================================================================

    async def get_user_by_line_sub(self, line_sub: str, db: AsyncSession) -> User | None:
        """Get user by LINE ID using blind index hash."""
        line_id_hash = generate_blind_index(line_sub)
        result = await db.execute(
            select(User).where(User.line_user_id_hash ==
                               line_id_hash, User.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_bound_email_by_line_sub(
        self, line_sub: str, db: AsyncSession
    ) -> str | None:
        """
        Get the bound company email for a LINE sub.

        Args:
            line_sub: LINE ID Token 'sub' claim.
            db: Database session.

        Returns:
            str | None: Bound company email, or None if not bound.
        """
        user = await self.get_user_by_line_sub(line_sub, db)
        return user.email if user else None

    async def check_binding_status(
        self, id_token: str, db: AsyncSession
    ) -> dict[str, Any]:
        """
        Verify LINE ID Token and check if the user has bound a company email.

        This is the main entry point for LIFF authentication flow:
        1. Verify the ID Token and extract 'sub'
        2. Check if 'sub' is bound to a company email
        3. Return binding status and email if bound

        Args:
            id_token: LINE ID Token from LIFF.
            db: Database session.

        Returns:
            dict containing:
                - sub: str - LINE user identifier
                - is_bound: bool - Whether account is bound
                - email: str | None - Bound company email
                - line_name: str | None - LINE display name

        Raises:
            LineIdTokenError: If token verification fails.
        """
        # Verify token and extract sub
        token_data = await self.verify_line_id_token(id_token)
        line_sub = token_data["sub"]

        # Check if bound
        bound_email = await self.get_bound_email_by_line_sub(line_sub, db)

        # Update last login if bound
        if bound_email:
            user = await self.get_user_by_line_sub(line_sub, db)
            if user:
                user.last_login_at = datetime.now(timezone.utc)
                await db.commit()

        return {
            "sub": line_sub,
            "is_bound": bound_email is not None,
            "email": bound_email,
            "line_name": token_data.get("name"),
        }

    async def is_user_bound(self, line_sub: str, db: AsyncSession) -> bool:
        """Check if a LINE account is bound to a company email."""
        user = await self.get_user_by_line_sub(line_sub, db)
        return user is not None

    async def is_user_authenticated(self, line_id: str, db: AsyncSession) -> bool:
        """
        Check if a LINE user is authenticated (bound to a company email).

        This is an alias for is_user_bound, accepting LINE userId from webhook events.
        The userId is used as the identity key for lookup.

        Args:
            line_id: LINE user ID from webhook event or OIDC sub.
            db: Database session.

        Returns:
            True if user has bound their account, False otherwise.
        """
        return await self.is_user_bound(line_id, db)

    # =========================================================================
    # Magic Link Binding Flow
    # =========================================================================

    # 統一的成功訊息，防止使用者枚舉攻擊
    MAGIC_LINK_SUCCESS_MESSAGE = "如果此信箱已註冊為員工，驗證連結將會寄出。"

    async def initiate_magic_link(
        self,
        email: str,
        line_sub: str,
    ) -> str:
        """
        Initiate magic link authentication flow for LINE account binding.

        Security Note:
            This method is designed to prevent user enumeration attacks.
            Regardless of whether the email exists in the system, the response
            is always the same generic success message. This prevents attackers
            from discovering valid employee email addresses.

        Args:
            email: Company email address to bind.
            line_sub: LINE ID Token 'sub' claim.

        Returns:
            str: Generic status message (always the same, regardless of email validity).

        Note:
            This method no longer raises EmailNotFoundError to the caller.
            Invalid emails are logged internally but do not affect the response.
        """
        # 使用安全的 log 格式，避免洩漏完整 email
        email_masked = self._mask_email(email)
        logger.info(
            f"Magic link request for: {email_masked}, line_sub: {line_sub[:8]}...")

        try:
            employee = await self._ragic_service.verify_email_exists(email)

            if employee is None:
                # 記錄但不拋出例外，防止使用者枚舉
                logger.warning(
                    f"[USER_ENUM_PROTECTION] Magic link requested for non-existent email: {email_masked}"
                )
                # 返回與成功相同的訊息
                return self.MAGIC_LINK_SUCCESS_MESSAGE

            if not employee.is_active:
                # 記錄但不拋出例外，防止使用者枚舉
                logger.warning(
                    f"[USER_ENUM_PROTECTION] Magic link requested for inactive employee: {email_masked}"
                )
                return self.MAGIC_LINK_SUCCESS_MESSAGE

            magic_link = self.generate_magic_link(email, line_sub)

            await self._send_verification_email(
                to_email=email,
                employee_name=employee.name,
                magic_link=magic_link,
            )

            logger.info(f"Magic link sent to: {email_masked}")

        except EmailSendError as e:
            # 郵件發送失敗仍記錄，但對外返回相同訊息
            logger.error(
                f"[EMAIL_SEND_FAILURE] Failed to send magic link to {email_masked}: {e}"
            )
            # 不重新拋出，維持一致的回應

        except Exception as e:
            # 其他未預期錯誤也記錄，但不影響回應
            logger.error(
                f"[UNEXPECTED_ERROR] Magic link initiation failed for {email_masked}: {e}"
            )

        return self.MAGIC_LINK_SUCCESS_MESSAGE

    @staticmethod
    def _mask_email(email: str) -> str:
        """
        Mask email for secure logging.

        Example: "john.doe@company.com" -> "jo***@company.com"
        """
        if "@" not in email:
            return "***"
        local, domain = email.rsplit("@", 1)
        if len(local) <= 2:
            masked_local = local[0] + "***" if local else "***"
        else:
            masked_local = local[:2] + "***"
        return f"{masked_local}@{domain}"

    def generate_magic_link(self, email: str, line_sub: str) -> str:
        """Generate a magic link URL with signed JWT token."""
        from core.services.auth_token import create_magic_link_token

        token = create_magic_link_token(email, line_sub)
        base_url = self._config_loader.get("server.base_url", "")
        return f"{base_url}/auth/verify?token={token}"

    async def verify_magic_token(
        self,
        token: str,
        db: AsyncSession,
    ) -> UserResponse:
        """
        Verify magic link token and create/update user binding.

        Args:
            token: JWT token from magic link.
            db: Database session.

        Returns:
            UserResponse: User data after successful binding.

        Raises:
            TokenExpiredError: If token has expired.
            TokenInvalidError: If token is invalid.
            TokenAlreadyUsedError: If token was already used.
            UserBindingError: If binding fails.
        """
        from core.services.auth_token import decode_magic_link_token
        from core.services.auth_token import TokenExpiredError as JwtExpiredError
        from core.services.auth_token import TokenInvalidError as JwtInvalidError

        logger.info("Verifying magic link token")

        token_hash = hashlib.sha256(token.encode()).hexdigest()

        try:
            # Check if token already used
            existing_usage = await db.execute(
                select(UsedToken).where(UsedToken.token_hash == token_hash)
            )
            if existing_usage.scalar_one_or_none():
                raise TokenAlreadyUsedError(
                    "This verification link has already been used.")

            # Decode and validate token
            payload = decode_magic_link_token(token)

            # Mark token as used
            used_token = UsedToken(
                token_hash=token_hash,
                email=payload.email,
                used_at=datetime.now(timezone.utc),
                expires_at=payload.exp,
            )
            db.add(used_token)
            await db.flush()

            # Find or create user binding
            existing_user = await self._find_existing_user(
                db, email=payload.email, line_sub=payload.line_sub
            )

            if existing_user:
                user = await self._update_user_binding(
                    db, user=existing_user, email=payload.email, line_sub=payload.line_sub
                )
            else:
                user = await self._create_bound_user(
                    db, email=payload.email, line_sub=payload.line_sub
                )

            await db.commit()
            await db.refresh(user)

            logger.info(
                f"User binding successful: {user.email} <-> LINE sub: {payload.line_sub[:8]}...")
            return UserResponse.model_validate(user)

        except JwtExpiredError:
            raise TokenExpiredError("Magic link has expired")
        except JwtInvalidError as e:
            raise TokenInvalidError(str(e))
        except TokenAlreadyUsedError:
            raise
        except Exception as e:
            logger.error(f"User binding failed: {e}")
            raise UserBindingError(f"Failed to bind user account: {e}") from e

    async def _find_existing_user(
        self, db: AsyncSession, email: str, line_sub: str
    ) -> User | None:
        """Find user by email or line_user_id using blind index hashes."""
        email_hash = generate_blind_index(email)
        line_id_hash = generate_blind_index(line_sub)

        result = await db.execute(
            select(User).where(
                (User.email_hash == email_hash) | (
                    User.line_user_id_hash == line_id_hash)
            )
        )
        return result.scalar_one_or_none()

    async def _create_bound_user(
        self, db: AsyncSession, email: str, line_sub: str
    ) -> User:
        """
        Create new user with Write-Through to Ragic.
        
        Strategy:
            1. Verify employee exists in Ragic
            2. Create local User record first (to get UUID)
            3. Write to Ragic with local UUID
            4. Update local record with ragic_id
        
        This ensures immediate consistency - user can login instantly
        without waiting for webhook sync.
        """
        from core.services.user_sync import get_user_ragic_writer
        
        employee = await self._ragic_service.verify_email_exists(email)

        # Step 1: Create local user first (generates UUID)
        user = User(
            email=email,
            email_hash=generate_blind_index(email),
            line_user_id=line_sub,
            line_user_id_hash=generate_blind_index(line_sub),
            ragic_employee_id=employee.employee_id if employee else None,
            display_name=employee.name if employee else None,
            is_active=True,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        await db.flush()  # Generate UUID
        
        logger.info(
            f"Created local user: {self._mask_email(email)} bound to LINE ID: {line_sub[:8]}..."
        )
        
        # Step 2: Write-Through to Ragic (Master)
        ragic_writer = get_user_ragic_writer()
        try:
            ragic_id = await ragic_writer.create_user_in_ragic(
                local_db_id=user.id,
                email=email,  # Plain text to Ragic
                line_user_id=line_sub,  # Plain text to Ragic
                ragic_employee_id=employee.employee_id if employee else None,
                display_name=employee.name if employee else None,
            )
            
            if ragic_id:
                # Update local record with ragic_id
                user.ragic_id = ragic_id
                logger.info(f"Ragic sync successful: ragic_id={ragic_id}")
            else:
                # Log warning but don't fail - local DB is still valid
                # Webhook can sync ragic_id later
                logger.warning(
                    f"Ragic write failed for user {user.id}, "
                    "will sync via webhook later"
                )
        except Exception as e:
            # Log error but don't fail the user creation
            # The local DB record is valid, Ragic sync can be retried
            logger.error(f"Ragic write-through failed: {e}")
        
        return user

    async def _update_user_binding(
        self, db: AsyncSession, user: User, email: str, line_sub: str
    ) -> User:
        """
        Update user binding with Write-Through to Ragic.
        
        Strategy:
            1. Update local DB first
            2. Write-Through to Ragic
            3. If Ragic fails, local update still succeeds (eventual consistency)
        """
        from core.services.user_sync import get_user_ragic_writer
        
        # Step 1: Update local user
        user.email = email
        user.email_hash = generate_blind_index(email)
        user.line_user_id = line_sub
        user.line_user_id_hash = generate_blind_index(line_sub)
        user.is_active = True
        user.last_login_at = datetime.now(timezone.utc)
        
        logger.info(
            f"Updated local user binding: {self._mask_email(email)} <-> LINE ID: {line_sub[:8]}..."
        )
        
        # Step 2: Write-Through to Ragic (if ragic_id exists)
        if user.ragic_id:
            ragic_writer = get_user_ragic_writer()
            try:
                success = await ragic_writer.update_user_in_ragic(
                    ragic_id=user.ragic_id,
                    local_db_id=user.id,
                    email=email,  # Plain text to Ragic
                    line_user_id=line_sub,  # Plain text to Ragic
                    ragic_employee_id=user.ragic_employee_id,
                    display_name=user.display_name,
                    is_active=True,
                )
                
                if success:
                    logger.info(f"Ragic update successful: ragic_id={user.ragic_id}")
                else:
                    logger.warning(f"Ragic update failed for ragic_id={user.ragic_id}")
            except Exception as e:
                logger.error(f"Ragic write-through update failed: {e}")
        else:
            # No ragic_id - try to create in Ragic
            ragic_writer = get_user_ragic_writer()
            try:
                ragic_id = await ragic_writer.create_user_in_ragic(
                    local_db_id=user.id,
                    email=email,
                    line_user_id=line_sub,
                    ragic_employee_id=user.ragic_employee_id,
                    display_name=user.display_name,
                )
                
                if ragic_id:
                    user.ragic_id = ragic_id
                    logger.info(f"Created user in Ragic: ragic_id={ragic_id}")
            except Exception as e:
                logger.error(f"Ragic create failed during update: {e}")
        
        return user

    async def _send_verification_email(
        self, to_email: str, employee_name: str, magic_link: str
    ) -> None:
        """Send verification email with magic link."""
        logger.info(f"Sending verification email to: {to_email}")

        # Get config values
        expire_minutes = int(self._security_config.get(
            "magic_link_expire_minutes", 15))
        smtp_from_name = self._email_config.get("from_name", "Admin System")
        smtp_from_email = self._email_config.get("from_email", "")
        smtp_host = self._email_config.get("host", "")
        smtp_port = int(self._email_config.get("port", 587))
        smtp_user = self._email_config.get("username", "")
        smtp_pass = self._email_config.get("password", "")

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🔐 {self._app_name} - 綁定您的 LINE 帳號"
            msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
            msg["To"] = to_email

            text_content = f"""
您好 {employee_name}，

您正在將 LINE 帳號與 {self._app_name} 進行綁定。

請點擊以下連結完成驗證：
{magic_link}

此連結將在 {expire_minutes} 分鐘後失效。

如果您沒有發起此請求，請忽略此郵件。

{self._app_name} 團隊
""".strip()

            html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #00B900;">🔐 {self._app_name}</h2>
        <p>您好 <strong>{employee_name}</strong>，</p>
        <p>您正在將 LINE 帳號與系統進行綁定。</p>
        <p><a href="{magic_link}" style="background: #00B900; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">✅ 完成綁定</a></p>
        <p style="color: #888; font-size: 12px;">此連結將在 {expire_minutes} 分鐘後失效。</p>
    </div>
</body>
</html>
"""

            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            import aiosmtplib
            await aiosmtplib.send(
                msg,
                hostname=smtp_host,
                port=smtp_port,
                start_tls=True,
                username=smtp_user,
                password=smtp_pass,
            )

            logger.info(f"Email sent to: {to_email}")

        except Exception as e:
            logger.error(f"Email send error: {e}")
            raise EmailSendError(f"Failed to send email: {e}") from e


# Singleton
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Get singleton AuthService instance."""
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
