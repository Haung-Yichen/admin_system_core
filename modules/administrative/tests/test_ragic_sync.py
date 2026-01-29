"""
Integration Test: Ragic Account Sync.

Tests the full sync workflow:
1. Fetches data from Ragic ADMIN_RAGIC_URL_ACCOUNT
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
    from modules.administrative.services.ragic_sync import RagicSyncService
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
    sync_service = RagicSyncService(settings)

    try:
        # =====================================================================
        # Step 1: Test Ragic API Connection
        # =====================================================================
        print("🔌 Step 1: Testing Ragic API connection...")
        
        try:
            schema = await sync_service._fetch_form_schema(settings.ragic_url_account)
            fields = schema.get("fields", {})
            print(f"   ✅ Connected successfully! Found {len(fields)} fields.")
            
            # Show sample field names
            field_names = list(fields.keys())[:10]
            print(f"   Sample field IDs: {field_names}")
        except Exception as e:
            print(f"   ❌ Failed to connect: {e}")
            return False
        print()

        # =====================================================================
        # Step 2: Fetch All Account Records
        # =====================================================================
        print("📥 Step 2: Fetching account records from Ragic...")
        
        try:
            records = await sync_service._fetch_form_data(settings.ragic_url_account)
            print(f"   ✅ Fetched {len(records)} records from Ragic.")
            
            # Show sample record
            if records:
                sample = records[0]
                print(f"   Sample record:")
                print(f"     - Ragic ID: {sample.get('_ragicId')}")
                print(f"     - Account ID (1005972): {sample.get('1005972', 'N/A')}")
                print(f"     - Name (1005975): {sample.get('1005975', 'N/A')}")
                print(f"     - Status (1005974): {sample.get('1005974', 'N/A')}")
                print(f"     - Org Code (1005978): {sample.get('1005978', 'N/A')}")
        except Exception as e:
            print(f"   ❌ Failed to fetch: {e}")
            return False
        print()

        # =====================================================================
        # Step 3: Ensure Table Exists
        # =====================================================================
        print("🗄️ Step 3: Ensuring database table exists...")
        
        try:
            await sync_service._ensure_tables_exist()
            print("   ✅ Table 'administrative_accounts' is ready.")
        except Exception as e:
            print(f"   ❌ Failed to create table: {e}")
            return False
        print()

        # =====================================================================
        # Step 4: Upsert Records
        # =====================================================================
        print("💾 Step 4: Upserting records to database...")
        
        try:
            async with get_standalone_session() as session:
                # Get count before
                before_count = await session.execute(
                    select(func.count()).select_from(AdministrativeAccount)
                )
                before_count = before_count.scalar()
                print(f"   Records before sync: {before_count}")
                
                # Perform upsert
                synced, skipped = await sync_service._upsert_accounts(records, session)
                print(f"   ✅ Synced {synced} records, skipped {skipped}.")
                
                # Get count after
                after_count = await session.execute(
                    select(func.count()).select_from(AdministrativeAccount)
                )
                after_count = after_count.scalar()
                print(f"   Records after sync: {after_count}")
                
        except Exception as e:
            print(f"   ❌ Failed to upsert: {e}")
            import traceback
            traceback.print_exc()
            return False
        print()

        # =====================================================================
        # Step 5: Verify Data
        # =====================================================================
        print("🔍 Step 5: Verifying synced data...")
        
        async with get_standalone_session() as session:
            # Check total count
            total = await session.execute(
                select(func.count()).select_from(AdministrativeAccount)
            )
            total = total.scalar()
            
            # Count active accounts
            active_count = await session.execute(
                select(func.count()).select_from(AdministrativeAccount).where(
                    AdministrativeAccount.status == True
                )
            )
            active_count = active_count.scalar()
            
            # Check sample records
            samples = await session.execute(
                select(AdministrativeAccount).limit(5)
            )
            samples = samples.scalars().all()
            
            print(f"   Total accounts in DB: {total}")
            print(f"   Active accounts: {active_count}")
            print(f"   Sample records:")
            for acc in samples:
                status = "Active" if acc.status else "Disabled"
                print(f"     - {acc.name} ({acc.account_id}) - Org: {acc.org_name} [{status}]")
        
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
