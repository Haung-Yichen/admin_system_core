"""
AdministrativeEmployee Model.

SQLAlchemy model for caching Employee data from Ragic.
This serves as a local read-replica for performance and offline access.
"""

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base, TimestampMixin


class AdministrativeEmployee(Base, TimestampMixin):
    """
    Employee cache table synced from Ragic.
    
    This model stores a local copy of employee data from the Ragic No-Code DB.
    The sync is performed by RagicSyncService on application startup.
    
    Ragic Field Mappings:
        - email (PK) -> Field 1001132
        - name -> Field 1001129
        - department_name -> Field 1001194
        - supervisor_email -> Field 1001182 (Mentor ID/Email)
        - ragic_id -> Internal Ragic record ID (_ragicId)
    
    Attributes:
        email: Employee email address (Primary Key).
        name: Employee full name.
        department_name: Name of the employee's department.
        supervisor_email: Email of the employee's supervisor/mentor.
        ragic_id: The internal Ragic record identifier.
    """

    __tablename__ = "administrative_employee"

    email: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        comment="Employee email (synced from Ragic field 1001132)",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Employee name (synced from Ragic field 1001129)",
    )
    department_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Department name (synced from Ragic field 1001194)",
    )
    supervisor_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Supervisor/Mentor email (synced from Ragic field 1001182)",
    )
    ragic_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        index=True,
        comment="Internal Ragic record ID",
    )

    def __repr__(self) -> str:
        return f"<AdministrativeEmployee(email={self.email}, name={self.name})>"
