"""
Administrative Module.

Handles administrative tasks such as:
- Leave Request System
- Employee Data Sync from Ragic
- Department Management
"""

from modules.administrative.administrative_module import AdministrativeModule
from modules.administrative.core.config import get_admin_settings

__all__ = ["AdministrativeModule", "get_admin_settings"]
