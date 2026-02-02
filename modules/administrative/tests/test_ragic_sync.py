"""
Integration Test: Ragic Account Sync.

Tests the full sync workflow using AccountSyncService:
1. Fetches data from Ragic
2. Creates/updates records in the local administrative_accounts table
3. Verifies record count and data integrity

Usage:
    python -m modules.administrative.tests.test_ragic_sync
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_account_sync():
    """Test account sync from Ragic to local DB."""
    from sqlalchemy import select, func

    from core.database import get_standalone_session
    from modules.administrative.services import get_account_sync_service
    from modules.administrative.models import AdministrativeAccount
    from modules.administrative.core.config import get_admin_settings

    print("=" * 70)
    print("Integration Test: Ragic Account Sync")
    print("=" * 70)
    print()

    settings = get_admin_settings()

    # Display config
    print("📋 Configuration:")
    print(f"   Ragic Account URL: {settings.ragic_url_account}")
    print()

    # Initialize service
    sync_service = get_account_sync_service()

    try:
        # =====================================================================
        # Step 1: Get Initial Count
        # =====================================================================
        print("🗄️ Step 1: Checking database state before sync...")

        async with get_standalone_session() as session:
            before_count = await session.execute(
                select(func.count()).select_from(AdministrativeAccount)
            )
            before_count = before_count.scalar()
            print(f"   Records before sync: {before_count}")
        print()

        # =====================================================================
        # Step 2: Perform Sync
        # =====================================================================
        print("💾 Step 2: Syncing records from Ragic...")

        try:
            result = await sync_service.sync_all_data()
            print(f"   ✅ Synced {result.synced} records, skipped {result.skipped}.")
            
            if result.error_messages:
                print(f"   ⚠ Errors: {result.error_messages}")

        except Exception as e:
            print(f"   ❌ Failed to sync: {e}")
            import traceback
            traceback.print_exc()
            return False
        print()

        # =====================================================================
        # Step 3: Verify Data
        # =====================================================================
        print("🔍 Step 3: Verifying synced data...")

        async with get_standalone_session() as session:
            # Check total count
            total = await session.execute(
                select(func.count()).select_from(AdministrativeAccount)
            )
            total = total.scalar()

            # Count active accounts
            active_count = await session.execute(
                select(func.count())
                .select_from(AdministrativeAccount)
                .where(AdministrativeAccount.status == True)
            )
            active_count = active_count.scalar()

            # Check sample records
            samples = await session.execute(select(AdministrativeAccount).limit(5))
            samples = samples.scalars().all()

            print(f"   Total accounts in DB: {total}")
            print(f"   Active accounts: {active_count}")
            print(f"   Sample records:")
            for acc in samples:
                status = "Active" if acc.status else "Disabled"
                print(
                    f"     - {acc.name} ({acc.account_id}) - Org: {acc.org_name} [{status}]"
                )

        print()
        print("=" * 70)
        print("✅ Integration Test PASSED")
        print("=" * 70)
        return True

    except Exception as e:
        logger.exception(f"Test failed with error: {e}")
        print()
        print("=" * 70)
        print("❌ Integration Test FAILED")
        print("=" * 70)
        return False

    finally:
        await sync_service.close()


if __name__ == "__main__":
    success = asyncio.run(test_account_sync())
    sys.exit(0 if success else 1)
