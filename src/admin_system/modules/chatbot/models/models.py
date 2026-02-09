"""
SQLAlchemy Database Models for Chatbot Module.

Defines chatbot-specific entities: SOPDocument.
Uses pgvector for vector similarity search on embeddings.
Sensitive fields are encrypted using framework-level EncryptedType.
"""

from typing import Any, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from modules.chatbot.core.config import get_chatbot_settings
from core.database.base import Base, TimestampMixin, UUIDPrimaryKey
from core.security import EncryptedType


def _get_embedding_dimension() -> int:
    """Get embedding dimension from settings, with fallback."""
    try:
        return get_chatbot_settings().embedding_dimension
    except Exception:
        return 384


class SOPDocument(Base, TimestampMixin):
    """
    SOP Document model for storing searchable SOP content with vector embeddings.
    
    Synced from Ragic SOP知識庫表單 (Form 12).
    
    Attributes:
        id: UUID primary key (local).
        ragic_id: Ragic record ID for sync (unique).
        sop_id: SOP identifier (e.g., "SOP-001").
        title: Document title for display.
        content: Full text content of the SOP.
        embedding: Vector embedding for similarity search.
        category: Optional category for filtering.
        tags: Optional tags as JSON array.
        metadata: Additional metadata as JSON.
        is_published: Whether document is visible in search.
    """
    
    __tablename__ = "sop_documents"
    
    id: Mapped[UUIDPrimaryKey]
    
    # Ragic sync fields
    ragic_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        unique=True,
        nullable=True,
        index=True,
        comment="Ragic record ID for sync",
    )
    sop_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        unique=True,
        nullable=True,
        index=True,
        comment="SOP identifier (e.g., SOP-001)",
    )
    
    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="SOP document title",
    )
    content: Mapped[str] = mapped_column(
        EncryptedType(8192),  # Larger size for encrypted SOP content
        nullable=False,
        comment="Full text content of the SOP (Encrypted)",
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
        return f"<SOPDocument(id={self.id}, sop_id={self.sop_id}, title={self.title[:50]}...)>"
