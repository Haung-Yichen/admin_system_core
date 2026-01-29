"""
Test Leave Service with new Account model.

Verifies that the leave service can correctly look up employee data.

Usage:
    python scripts/test_leave_service.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from core.database import get_standalone_session
from modules.administrative.models import AdministrativeAccount
from modules.administrative.services.leave import LeaveService


async def test_account_lookup():
    """Test looking up accounts by email."""
    print("=" * 60)
    print("Test Leave Service with Account Model")
    print("=" * 60)
    print()

    async with get_standalone_session() as db:
        # Step 1: Get some accounts with emails
        print("Step 1: Finding accounts with emails...")
        result = await db.execute(
            select(AdministrativeAccount).where(
                AdministrativeAccount.emails.isnot(None),
                AdministrativeAccount.status == True,
            ).limit(3)
        )
        accounts = result.scalars().all()
        
        if not accounts:
            print("  ✗ No active accounts with emails found!")
            return False
        
        print(f"  Found {len(accounts)} active accounts with emails")
        print()

        # Step 2: Test email lookup via LeaveService
        print("Step 2: Testing email lookup via LeaveService...")
        leave_service = LeaveService()
        
        for acc in accounts:
            email = acc.primary_email
            print(f"\n  Testing: {email}")
            
            try:
                init_data = await leave_service.get_init_data(email, db)
                print(f"    ✓ Found: {init_data['name']}")
                print(f"      Department: {init_data['department']}")
                print(f"      Email: {init_data['email']}")
            except Exception as e:
                print(f"    ✗ Error: {e}")
        
        print()
        
        # Step 3: Test with partial email match
        print("Step 3: Testing partial email match (LIKE query)...")
        test_email = accounts[0].primary_email
        if test_email:
            domain = test_email.split("@")[1] if "@" in test_email else ""
            print(f"  Testing domain match: %@{domain}")
            
            result = await db.execute(
                select(AdministrativeAccount).where(
                    AdministrativeAccount.emails.like(f"%@{domain}%")
                ).limit(3)
            )
            matches = result.scalars().all()
            print(f"  Found {len(matches)} accounts with @{domain}")
        
        print()
        print("=" * 60)
        print("✓ Leave service test completed!")
        print("=" * 60)
        return True


if __name__ == "__main__":
    success = asyncio.run(test_account_lookup())
    sys.exit(0 if success else 1)
