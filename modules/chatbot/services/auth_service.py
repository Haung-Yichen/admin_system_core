"""
Authentication Service Module.

Handles Magic Link authentication flow.
"""

import hashlib
import logging
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.app_context import ConfigLoader
from modules.chatbot.core.config import ChatbotSettings, get_chatbot_settings
from modules.chatbot.core.security import (
    TokenExpiredError,
    TokenInvalidError,
    create_magic_link_token,
    decode_magic_link_token,
)
from modules.chatbot.models import User
from modules.chatbot.models.models import UsedToken
from modules.chatbot.schemas import RagicEmployeeData, UserResponse
from modules.chatbot.services.ragic_service import RagicService, get_ragic_service


logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Base exception for authentication errors."""
    pass


class EmailNotFoundError(AuthError):
    """Raised when email is not found in Ragic database."""
    pass


class EmailSendError(AuthError):
    """Raised when email sending fails."""
    pass


class UserBindingError(AuthError):
    """Raised when user binding fails."""
    pass


class TokenAlreadyUsedError(AuthError):
    """Raised when magic link token has already been used."""
    pass


class AuthService:
    """Service for handling Magic Link authentication flow."""
    
    def __init__(
        self,
        settings: ChatbotSettings | None = None,
        ragic_service: RagicService | None = None,
    ) -> None:
        self._settings = settings or get_chatbot_settings()
        self._ragic_service = ragic_service or get_ragic_service()
        
        # Load global config
        self._config_loader = ConfigLoader()
        self._config_loader.load()
        self._security_config = self._config_loader.get("security", {})
        self._email_config = self._config_loader.get("email", {})
    
    async def initiate_magic_link(
        self,
        email: str,
        line_user_id: str,
    ) -> str:
        logger.info(f"Initiating magic link for: {email}, line_id: {line_user_id}")
        
        employee = await self._ragic_service.verify_email_exists(email)
        
        if employee is None:
            logger.warning(f"Email not found in Ragic: {email}")
            raise EmailNotFoundError(
                f"Email '{email}' is not registered as an employee."
            )
        
        if not employee.is_active:
            raise EmailNotFoundError("Your employee account is currently inactive.")
        
        magic_link = self.generate_magic_link(email, line_user_id)
        
        await self._send_verification_email(
            to_email=email,
            employee_name=employee.name,
            magic_link=magic_link,
        )
        
        logger.info(f"Magic link sent to: {email}")
        return f"Verification email sent to {email}"
    
    def generate_magic_link(self, email: str, line_user_id: str) -> str:
        token = create_magic_link_token(email, line_user_id)
        base_url = self._config_loader.get("server.base_url", "")
        return f"{base_url}/auth/verify?token={token}"
    
    async def verify_magic_token(
        self,
        token: str,
        db: AsyncSession,
    ) -> UserResponse:
        logger.info("Verifying magic link token")
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        try:
            existing_usage = await db.execute(
                select(UsedToken).where(UsedToken.token_hash == token_hash)
            )
            if existing_usage.scalar_one_or_none():
                raise TokenAlreadyUsedError("This verification link has already been used.")
            
            payload = decode_magic_link_token(token)
            
            used_token = UsedToken(
                token_hash=token_hash,
                email=payload.email,
                used_at=datetime.now(timezone.utc),
                expires_at=payload.exp,
            )
            db.add(used_token)
            await db.flush()
            
            existing_user = await self._find_existing_user(
                db, email=payload.email, line_user_id=payload.line_user_id
            )
            
            if existing_user:
                user = await self._update_user_binding(
                    db, user=existing_user, email=payload.email, line_user_id=payload.line_user_id
                )
            else:
                user = await self._create_bound_user(
                    db, email=payload.email, line_user_id=payload.line_user_id
                )
            
            await db.commit()
            await db.refresh(user)
            
            logger.info(f"User binding successful: {user.email} <-> {user.line_user_id}")
            return UserResponse.model_validate(user)
            
        except (TokenExpiredError, TokenInvalidError, TokenAlreadyUsedError):
            raise
        except Exception as e:
            logger.error(f"User binding failed: {e}")
            raise UserBindingError(f"Failed to bind user account: {e}") from e
    
    async def _find_existing_user(
        self, db: AsyncSession, email: str, line_user_id: str
    ) -> User | None:
        result = await db.execute(
            select(User).where(
                (User.email == email) | (User.line_user_id == line_user_id)
            )
        )
        return result.scalar_one_or_none()
    
    async def _create_bound_user(
        self, db: AsyncSession, email: str, line_user_id: str
    ) -> User:
        employee = await self._ragic_service.verify_email_exists(email)
        
        user = User(
            email=email,
            line_user_id=line_user_id,
            ragic_employee_id=employee.employee_id if employee else None,
            display_name=employee.name if employee else None,
            is_active=True,
            last_login_at=datetime.now(timezone.utc),
        )
        db.add(user)
        logger.info(f"Created new user: {email}")
        return user
    
    async def _update_user_binding(
        self, db: AsyncSession, user: User, email: str, line_user_id: str
    ) -> User:
        user.email = email
        user.line_user_id = line_user_id
        user.is_active = True
        user.last_login_at = datetime.now(timezone.utc)
        logger.info(f"Updated user binding: {email} <-> {line_user_id}")
        return user
    
    async def _send_verification_email(
        self, to_email: str, employee_name: str, magic_link: str
    ) -> None:
        logger.info(f"Sending verification email to: {to_email}")
        
        # Get config values
        expire_minutes = int(self._security_config.get("magic_link_expire_minutes", 15))
        smtp_from_name = self._email_config.get("from_name", "Admin System")
        smtp_from_email = self._email_config.get("from_email", "")
        smtp_host = self._email_config.get("host", "")
        smtp_port = int(self._email_config.get("port", 587))
        smtp_user = self._email_config.get("username", "")
        smtp_pass = self._email_config.get("password", "")
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"🔐 {self._settings.app_name} - Verify Your Identity"
            msg["From"] = f"{smtp_from_name} <{smtp_from_email}>"
            msg["To"] = to_email
            
            text_content = f"""
Hello {employee_name},

You requested to link your LINE account with {self._settings.app_name}.

Click the link below to verify your identity:
{magic_link}

This link will expire in {expire_minutes} minutes.

If you did not request this, please ignore this email.

Best regards,
{self._settings.app_name} Team
""".strip()
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #00B900;">🔐 {self._settings.app_name}</h2>
        <p>Hello <strong>{employee_name}</strong>,</p>
        <p>You requested to link your LINE account.</p>
        <p><a href="{magic_link}" style="background: #00B900; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">✅ Verify My Identity</a></p>
        <p style="color: #888; font-size: 12px;">This link expires in {expire_minutes} minutes.</p>
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
    
    async def get_user_by_line_id(self, line_user_id: str, db: AsyncSession) -> User | None:
        result = await db.execute(
            select(User).where(User.line_user_id == line_user_id, User.is_active == True)
        )
        return result.scalar_one_or_none()
    
    async def is_user_authenticated(self, line_user_id: str, db: AsyncSession) -> bool:
        user = await self.get_user_by_line_id(line_user_id, db)
        return user is not None


# Singleton
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
