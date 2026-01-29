"""
Admin User Model.

Defines local administrator account for web dashboard authentication.
Separate from LINE-based User model for internal system access.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base, TimestampMixin, UUIDPrimaryKey


class AdminUser(Base, TimestampMixin):
    """
    Local administrator account for web dashboard.

    Unlike the User model (LINE-based identity), this model is for
    internal admin access to the management dashboard.

    Attributes:
        id: UUID primary key.
        username: Unique login username.
        password_hash: Bcrypt hashed password.
        is_active: Whether the account is enabled.
        last_login_at: Timestamp of last successful login.
    """

    __tablename__ = "admin_users"

    id: Mapped[UUIDPrimaryKey]

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique login username",
    )

    password_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Bcrypt hashed password",
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
        return f"<AdminUser(id={self.id}, username={self.username})>"
