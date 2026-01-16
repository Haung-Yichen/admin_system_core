"""
SQLAlchemy Database Models.

Defines the core database entities: User and SOPDocument.
Uses pgvector for vector similarity search on embeddings.
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modules.chatbot.core.config import get_chatbot_settings
from modules.chatbot.db.base import Base, TimestampMixin, UUIDPrimaryKey


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
    line_user_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="LINE platform user ID",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Verified employee email",
    )
    ragic_employee_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="Employee ID from Ragic database",
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="User display name from LINE",
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


def _get_embedding_dimension() -> int:
    """Get embedding dimension from settings, with fallback."""
    try:
        return get_chatbot_settings().embedding_dimension
    except Exception:
        return 384


class SOPDocument(Base, TimestampMixin):
    """
    SOP Document model for storing searchable SOP content with vector embeddings.
    
    Attributes:
        id: UUID primary key.
        title: Document title for display.
        content: Full text content of the SOP.
        embedding: Vector embedding for similarity search (384 dimensions for MiniLM).
        category: Optional category for filtering.
        tags: Optional tags as JSON array.
        metadata: Additional metadata as JSON.
        is_published: Whether document is visible in search.
    """
    
    __tablename__ = "sop_documents"
    
    id: Mapped[UUIDPrimaryKey]
    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="SOP document title",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full text content of the SOP",
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(_get_embedding_dimension()),  # Dynamic dimension from config
        nullable=True,
        comment="Vector embedding for similarity search",
    )
    category: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        comment="Document category",
    )
    tags: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
        comment="Document tags as JSON array",
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",  # Column name in DB
        JSONB,
        nullable=True,
        default=dict,
        comment="Additional metadata",
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="Whether document is searchable",
    )
    
    # Add indexes for efficient vector search
    __table_args__ = (
        Index(
            "ix_sop_documents_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
    
    def __repr__(self) -> str:
        return f"<SOPDocument(id={self.id}, title={self.title[:50]}...)>"


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
        String(255),
        nullable=False,
        comment="Email associated with this token",
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
