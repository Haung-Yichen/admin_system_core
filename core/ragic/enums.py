"""
Ragic Sync Strategy Enums.

Defines the synchronization strategies for Ragic forms.
Each strategy determines how data flows between local database and Ragic.
"""

from enum import Enum


class SyncStrategy(str, Enum):
    """
    Synchronization strategy for Ragic forms.
    
    Determines the source of truth and data flow direction:
    
    - RAGIC_MASTER: Ragic is the source of truth. Local database is a read-only cache.
      Data flows: Ragic → Local DB (one-way sync)
      Use case: Reference data, lookup tables, SOP documents.
      
    - LOCAL_MASTER: Local database is the source of truth. Changes push to Ragic.
      Data flows: Local DB → Ragic (one-way push)
      Use case: System-generated data, audit logs.
      
    - REPOSITORY: Direct read/write to Ragic without local caching.
      Data flows: App ↔ Ragic (no local DB table)
      Use case: Transactional forms like leave requests, approvals.
      
    - HYBRID: Custom bidirectional sync with conflict resolution.
      Data flows: Local DB ↔ Ragic (two-way sync)
      Use case: User data that can be edited in both systems.
    """
    
    RAGIC_MASTER = "ragic_master"
    LOCAL_MASTER = "local_master"
    REPOSITORY = "repository"
    HYBRID = "hybrid"
    
    def __str__(self) -> str:
        return self.value
