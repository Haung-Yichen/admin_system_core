"""
Administrative Module Database Models.

Contains SQLAlchemy models for caching Ragic data locally.
"""

from modules.administrative.models.account import AdministrativeAccount
from modules.administrative.models.leave_type import LeaveType

__all__ = ["AdministrativeAccount", "LeaveType"]
