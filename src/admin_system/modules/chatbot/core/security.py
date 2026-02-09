"""
Security Module.

Handles JWT token operations for Magic Link authentication.
Follows Interface Segregation Principle - focused solely on token operations.

DEPRECATED: This module is deprecated. Use core.services.auth_token instead.
This module is kept for backward compatibility with existing chatbot code.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pydantic import BaseModel, Field

from core.app_context import ConfigLoader

import logging

logger = logging.getLogger(__name__)


class MagicLinkPayload(BaseModel):
    """Payload structure for magic link JWT tokens."""

    email: str = Field(..., description="User's verified email address")
    line_sub: str = Field(...,
                          description="LINE sub (OIDC Subject Identifier) to bind")
    exp: datetime = Field(..., description="Token expiration timestamp")
    iat: datetime = Field(..., description="Token issued at timestamp")
    purpose: str = Field(default="magic_link",
                         description="Token purpose identifier")


class TokenError(Exception):
    """Base exception for token-related errors."""
    pass


class TokenExpiredError(TokenError):
    """Raised when token has expired."""
    pass


class TokenInvalidError(TokenError):
    """Raised when token is malformed or signature is invalid."""
    pass


def _get_security_config() -> dict[str, Any]:
    """Helper to load security config."""
    loader = ConfigLoader()
    loader.load()
    return loader.get("security", {})


def create_magic_link_token(email: str, line_sub: str) -> str:
    """
    Create a signed JWT token for magic link authentication.

    DEPRECATED: Use core.services.auth_token.create_magic_link_token instead.

    Args:
        email: User's email address.
        line_sub: LINE sub (OIDC Subject Identifier) to bind upon verification.

    Returns:
        str: Signed JWT token string.
    """
    config = _get_security_config()
    secret = config.get("jwt_secret_key", "")
    algo = config.get("jwt_algorithm", "HS256")
    expire_min = int(config.get("magic_link_expire_minutes", 15))

    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=expire_min)

    payload = {
        "jti": str(uuid.uuid4()),
        "email": email,
        "line_sub": line_sub,
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp()),
        "purpose": "magic_link",
    }

    token = jwt.encode(
        payload,
        secret,
        algorithm=algo,
    )

    return token


def decode_magic_link_token(token: str) -> MagicLinkPayload:
    """
    Decode and validate a magic link JWT token.

    Args:
        token: JWT token string to decode.

    Returns:
        MagicLinkPayload: Decoded token payload.

    Raises:
        TokenExpiredError: If token has expired.
        TokenInvalidError: If token is malformed or signature is invalid.
    """
    config = _get_security_config()
    secret = config.get("jwt_secret_key", "")
    algo = config.get("jwt_algorithm", "HS256")

    try:
        logger.debug(f"Decoding magic link token (algorithm: {algo})")

        payload_dict: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[algo],
        )

        if payload_dict.get("purpose") != "magic_link":
            raise TokenInvalidError("Invalid token purpose")

        return MagicLinkPayload.model_validate(payload_dict)

    except jwt.ExpiredSignatureError as e:
        logger.warning(f"Token expired: {e}")
        raise TokenExpiredError("Magic link has expired") from e
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid token error: {str(e)}")
        raise TokenInvalidError(f"Invalid token: {e}") from e
