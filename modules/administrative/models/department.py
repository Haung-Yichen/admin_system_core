"""
AdministrativeDepartment Model.

SQLAlchemy model for caching Department data from Ragic.
This serves as a local read-replica for performance and offline access.
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base, TimestampMixin


class AdministrativeDepartment(Base, TimestampMixin):
    """
    Department cache table synced from Ragic.
    
    This model stores a local copy of department data from the Ragic No-Code DB.
    The sync is performed by RagicSyncService on application startup.
    
    Ragic Field Mappings:
        - name (PK) -> Field 1002508
        - manager_email -> Field 1002509 (Person in Charge)
        - ragic_id -> Internal Ragic record ID (_ragicId)
    
    Attributes:
        name: Department name (Primary Key).
        manager_email: Email of the department manager/person in charge.
        ragic_id: The internal Ragic record identifier.
    """

    __tablename__ = "administrative_department"

    name: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        comment="Department name (synced from Ragic field 1002508)",
    )
    manager_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Manager email (synced from Ragic field 1002509)",
    )
    ragic_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
        comment="Internal Ragic record ID",
    )

    def __repr__(self) -> str:
        return f"<AdministrativeDepartment(name={self.name}, manager={self.manager_email})>"
