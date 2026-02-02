"""
Quick sync and check - triggers Ragic sync and checks for email.

Usage:
    python scripts/resync.py [email]
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from core.database import get_standalone_session
from modules.administrative.models import AdministrativeAccount
from modules.administrative.services import get_account_sync_service


async def main():
    email_to_check = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("=" * 60)
    print("Re-syncing Ragic Account data...")
    print("=" * 60)
    
    # Run sync
    service = get_account_sync_service()
    try:
        result = await service.sync_all_data()
        print(f"✓ Synced: {result.synced} accounts")
        print(f"  Skipped: {result.skipped}")
    finally:
        await service.close()
    
    # Check for email if provided
    if email_to_check:
        print()
        print(f"Searching for: {email_to_check}")
        print("-" * 60)
        
        async with get_standalone_session() as db:
            # Try LIKE search
            result = await db.execute(
                select(AdministrativeAccount).where(
                    AdministrativeAccount.emails.like(f"%{email_to_check}%")
                )
            )
            account = result.scalar_one_or_none()
            
            if account:
                print(f"✓ FOUND!")
                print(f"  Name: {account.name}")
                print(f"  Account ID: {account.account_id}")
                print(f"  Emails: {account.emails}")
                print(f"  Org: {account.org_name}")
                print(f"  Status: {'Active' if account.status else 'Disabled'}")
            else:
                print(f"✗ NOT FOUND in local cache")
                print()
                print("Checking all accounts with emails...")
                all_result = await db.execute(
                    select(AdministrativeAccount).where(
                        AdministrativeAccount.emails.isnot(None)
                    ).limit(10)
                )
                all_accounts = all_result.scalars().all()
                print(f"Sample accounts with email ({len(all_accounts)} shown):")
                for acc in all_accounts:
                    print(f"  - {acc.name}: {acc.emails}")


if __name__ == "__main__":
    asyncio.run(main())
