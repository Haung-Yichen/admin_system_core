"""
Admin Authentication API.

Provides JWT-based authentication for web dashboard access.
Separate from LINE Magic Link authentication.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.app_context import ConfigLoader
from core.database import get_db_session
from core.models.admin_user import AdminUser


router = APIRouter(prefix="/admin/auth", tags=["Admin Authentication"])
security = HTTPBearer()


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Login request payload."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Login success response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminUserInfo(BaseModel):
    """Admin user information."""

    id: str
    username: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class MeResponse(BaseModel):
    """Current admin user response."""

    user: AdminUserInfo


# -----------------------------------------------------------------------------
# Config & Helpers
# -----------------------------------------------------------------------------


def _get_jwt_config() -> tuple[str, str, int]:
    """Get JWT configuration from environment."""
    loader = ConfigLoader()
    loader.load()
    return (
        loader.get("security.jwt_secret_key", ""),
        loader.get("security.jwt_algorithm", "HS256"),
        loader.get("security.admin_token_expire_minutes", 480),  # 8 hours default
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def create_access_token(admin_id: str, username: str) -> tuple[str, int]:
    """
    Create JWT access token for admin user.

    Returns:
        Tuple of (token, expires_in_seconds)
    """
    secret, algorithm, expire_minutes = _get_jwt_config()
    if not secret:
        raise ValueError("JWT_SECRET_KEY not configured")

    expires_delta = timedelta(minutes=expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": admin_id,
        "username": username,
        "type": "admin_access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, secret, algorithm=algorithm)
    return token, int(expires_delta.total_seconds())


# -----------------------------------------------------------------------------
# Dependencies
# -----------------------------------------------------------------------------


async def get_current_admin(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminUser:
    """
    FastAPI dependency: Validate JWT token and return current admin user.

    Raises:
        HTTPException 401: If token is invalid or expired
        HTTPException 403: If admin account is inactive
    """
    secret, algorithm, _ = _get_jwt_config()

    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=[algorithm])

        if payload.get("type") != "admin_access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        admin_id = payload.get("sub")
        if not admin_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # Fetch admin from database
    stmt = select(AdminUser).where(AdminUser.id == admin_id)
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin user not found",
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin account is disabled",
        )

    return admin


# Type alias for dependency injection
CurrentAdmin = Annotated[AdminUser, Depends(get_current_admin)]


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LoginResponse:
    """
    Authenticate admin user and return JWT token.

    Args:
        request: Login credentials

    Returns:
        JWT access token

    Raises:
        401: Invalid credentials
        403: Account disabled
    """
    # Find admin by username
    stmt = select(AdminUser).where(AdminUser.username == request.username)
    result = await db.execute(stmt)
    admin = result.scalar_one_or_none()

    if not admin or not verify_password(request.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    # Update last login time
    admin.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    # Generate token
    token, expires_in = create_access_token(admin.id, admin.username)

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
    )


@router.get("/me", response_model=MeResponse)
async def get_current_admin_info(
    admin: CurrentAdmin,
) -> MeResponse:
    """
    Get current authenticated admin user information.

    Requires: Valid JWT token in Authorization header
    """
    return MeResponse(
        user=AdminUserInfo(
            id=admin.id,
            username=admin.username,
            is_active=admin.is_active,
            created_at=admin.created_at,
            last_login_at=admin.last_login_at,
        )
    )
