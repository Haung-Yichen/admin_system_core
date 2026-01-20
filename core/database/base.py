"""
Database Base Model Module.

Defines the declarative base and common model mixins.
All modules should inherit from this Base class.
"""

from datetime import datetime, timezone
from typing import Annotated
from uuid import uuid4

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Custom type annotations for common column types
UUIDPrimaryKey = Annotated[
    str,
    mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
    ),
]

CreatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    ),
]

UpdatedAt = Annotated[
    datetime,
    mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    ),
]


class Base(DeclarativeBase):
    """
    Declarative base class for all SQLAlchemy models.

    All models across the framework should inherit from this base class.
    """
    pass


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at timestamp columns.

    Usage:
        class MyModel(Base, TimestampMixin):
            __tablename__ = "my_table"
            ...
    """

    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
