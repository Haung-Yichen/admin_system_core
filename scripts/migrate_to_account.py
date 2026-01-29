"""
Migration Script: Drop old Employee/Department tables and sync new Account data.

Usage:
    python scripts/migrate_to_account.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_standalone_session, get_thread_local_engine
from modules.administrative.services.ragic_sync import RagicSyncService


async def drop_old_tables():
    """Drop the old administrative_employee and administrative_department tables."""
    print("=" * 60)
    print("Step 1: Dropping old tables...")
    print("=" * 60)
    
    engine = get_thread_local_engine()
    
    async with engine.begin() as conn:
        # Drop old tables if they exist
        await conn.execute(text("DROP TABLE IF EXISTS administrative_employee CASCADE"))
        print("  ✓ Dropped administrative_employee")
        
        await conn.execute(text("DROP TABLE IF EXISTS administrative_department CASCADE"))
        print("  ✓ Dropped administrative_department")
    
    print()


async def sync_accounts():
    """Sync account data from Ragic."""
    print("=" * 60)
    print("Step 2: Syncing Account data from Ragic...")
    print("=" * 60)
    
    service = RagicSyncService()
    
    try:
        result = await service.sync_all_data()
        
        print(f"  ✓ Accounts synced: {result['accounts_synced']}")
        print(f"  ✓ Accounts skipped: {result['accounts_skipped']}")
        
        if result['schema_issues']:
            print(f"  ⚠ Schema issues: {result['schema_issues']}")
        
        return result
        
    except Exception as e:
        print(f"  ✗ Sync failed: {e}")
        raise


async def verify_data():
    """Verify the synced data."""
    print()
    print("=" * 60)
    print("Step 3: Verifying synced data...")
    print("=" * 60)
    
    from sqlalchemy import select, func
    from modules.administrative.models import AdministrativeAccount
    
    async with get_standalone_session() as session:
        # Total count
        total = await session.execute(
            select(func.count()).select_from(AdministrativeAccount)
        )
        total = total.scalar()
        
        # Active count
        active = await session.execute(
            select(func.count()).select_from(AdministrativeAccount).where(
                AdministrativeAccount.status == True
            )
        )
        active = active.scalar()
        
        # Sample records with email
        samples = await session.execute(
            select(AdministrativeAccount).where(
                AdministrativeAccount.emails.isnot(None)
            ).limit(5)
        )
        samples = samples.scalars().all()
        
        print(f"  Total accounts: {total}")
        print(f"  Active accounts: {active}")
        print()
        print("  Sample accounts with email:")
        for acc in samples:
            print(f"    - {acc.name} ({acc.account_id})")
            print(f"      Email: {acc.primary_email}")
            print(f"      Org: {acc.org_name}")
            print(f"      Status: {'Active' if acc.status else 'Disabled'}")
            print()
    
    return total, active


async def main():
    print()
    print("=" * 60)
    print("  MIGRATION: Employee/Department → Account")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Drop old tables
        await drop_old_tables()
        
        # Step 2: Sync new data
        await sync_accounts()
        
        # Step 3: Verify
        total, active = await verify_data()
        
        print("=" * 60)
        print(f"✓ Migration completed successfully!")
        print(f"  {total} accounts in database, {active} active")
        print("=" * 60)
        
    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ Migration failed: {e}")
        print("=" * 60)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
