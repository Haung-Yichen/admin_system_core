"""
Administrative Module Database Models.

Contains SQLAlchemy models for caching Ragic data locally.
"""

from modules.administrative.models.employee import AdministrativeEmployee
from modules.administrative.models.department import AdministrativeDepartment

__all__ = ["AdministrativeEmployee", "AdministrativeDepartment"]
