"""
Core User Models.

Defines system-wide user identity models for authentication.
Used across all modules for user verification and session tracking.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base, TimestampMixin, UUIDPrimaryKey
from core.security import EncryptedType


class User(Base, TimestampMixin):
    """
    User model representing authenticated employees.
    
    Attributes:
        id: UUID primary key.
        line_user_id: Unique LINE user identifier for message routing.
        email: Employee email address (verified via Ragic).
        ragic_employee_id: Reference ID from Ragic database.
        display_name: User's display name from LINE profile.
        is_active: Whether the user account is active.
        last_login_at: Timestamp of last successful authentication.
    """
    
    __tablename__ = "users"
    
    id: Mapped[UUIDPrimaryKey]
    
    # Encrypted fields with blind indexes for lookups
    line_user_id: Mapped[str] = mapped_column(
        EncryptedType(512),
        nullable=False,
        comment="LINE platform user ID (Encrypted)",
    )
    line_user_id_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="HMAC-SHA256 hash of line_user_id for lookups",
    )
    
    email: Mapped[str] = mapped_column(
        EncryptedType(512),
        nullable=False,
        comment="Verified employee email (Encrypted)",
    )
    email_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="HMAC-SHA256 hash of email for lookups",
    )
    
    ragic_employee_id: Mapped[str | None] = mapped_column(
        EncryptedType(512),
        nullable=True,
        comment="Employee ID from Ragic database (Encrypted)",
    )
    display_name: Mapped[str | None] = mapped_column(
        EncryptedType(512),
        nullable=True,
        comment="User display name from LINE (Encrypted)",
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Account active status",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last successful login timestamp",
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, line_user_id={self.line_user_id})>"


class UsedToken(Base):
    """
    Model for tracking used magic link tokens (one-time use enforcement).
    
    Stores the token hash (not the token itself) to prevent reuse.
    Tokens are automatically cleaned up after expiration.
    
    Attributes:
        id: UUID primary key.
        token_hash: SHA256 hash of the JWT token.
        email: Email associated with the token.
        used_at: When the token was used.
        expires_at: When the token expires (for cleanup).
    """
    
    __tablename__ = "used_tokens"
    
    id: Mapped[UUIDPrimaryKey]
    token_hash: Mapped[str] = mapped_column(
        String(64),  # SHA256 hex = 64 chars
        unique=True,
        index=True,
        nullable=False,
        comment="SHA256 hash of the used token",
    )
    email: Mapped[str] = mapped_column(
        EncryptedType(512),
        nullable=False,
        comment="Email associated with this token (Encrypted)",
    )
    used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the token was used",
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Token expiration time (for cleanup)",
    )
    
    def __repr__(self) -> str:
        return f"<UsedToken(hash={self.token_hash[:8]}..., email={self.email})>"
