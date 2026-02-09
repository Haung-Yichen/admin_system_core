"""
LeaveType Model.

SQLAlchemy model for caching Leave Type data from Ragic.
This serves as a local read-replica for the leave type dropdown options.

Source: https://ap13.ragic.com/HSIBAdmSys/ragicforms39/20007
"""

from typing import Optional

from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base, TimestampMixin


class LeaveType(Base, TimestampMixin):
    """
    Leave Type cache table synced from Ragic.
    
    This model stores leave type options that appear in the leave request form dropdown.
    
    Primary Key: ragic_id (Field 3005180 - Key Field)
    
    Source Form: /HSIBAdmSys/ragicforms39/20007
    """

    __tablename__ = "administrative_leave_types"

    # === Primary Identification ===
    ragic_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        comment="假別系統編號 (Ragic Key Field 3005180)",
    )
    
    # === Leave Type Info ===
    leave_type_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="假別編號 (Ragic Field 3005177)",
    )
    leave_type_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="請假類別 (Ragic Field 3005178)",
    )
    deduction_multiplier: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="扣薪乘數 (Ragic Field 3005179)",
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveType("
            f"ragic_id={self.ragic_id}, "
            f"code={self.leave_type_code}, "
            f"name={self.leave_type_name}"
            f")>"
        )
