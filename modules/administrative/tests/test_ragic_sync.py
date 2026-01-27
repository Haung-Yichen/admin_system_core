"""
Integration Test: Ragic Employee Sync.

Tests the full sync workflow:
1. Fetches data from Ragic ADMIN_RAGIC_URL_EMPLOYEE
2. Creates/updates records in the local administrative_employees table
3. Verifies record count matches expected (238 records)

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


async def test_employee_sync():
    """Test employee sync from Ragic to local DB."""
    from sqlalchemy import select, func
    
    from core.database import get_standalone_session
    from modules.administrative.services.ragic_sync import RagicSyncService
    from modules.administrative.models import AdministrativeEmployee
    from modules.administrative.core.config import get_admin_settings

    print("=" * 70)
    print("Integration Test: Ragic Employee Sync")
    print("=" * 70)
    print()

    settings = get_admin_settings()
    
    # Display config
    print("📋 Configuration:")
    print(f"   Ragic Employee URL: {settings.ragic_url_employee}")
    print(f"   Field mappings:")
    print(f"     - Email:      {settings.field_employee_email}")
    print(f"     - Name:       {settings.field_employee_name}")
    print(f"     - Department: {settings.field_employee_department}")
    print(f"     - Supervisor: {settings.field_employee_supervisor_email}")
    print()

    # Initialize service
    sync_service = RagicSyncService(settings)

    try:
        # =====================================================================
        # Step 1: Test Ragic API Connection
        # =====================================================================
        print("🔌 Step 1: Testing Ragic API connection...")
        
        try:
            schema = await sync_service._fetch_form_schema(settings.ragic_url_employee)
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
        # Step 2: Fetch All Employee Records
        # =====================================================================
        print("📥 Step 2: Fetching employee records from Ragic...")
        
        try:
            records = await sync_service._fetch_form_data(settings.ragic_url_employee)
            print(f"   ✅ Fetched {len(records)} records from Ragic.")
            
            # Show sample record
            if records:
                sample = records[0]
                email_field = settings.field_employee_email
                name_field = settings.field_employee_name
                print(f"   Sample record:")
                print(f"     - Ragic ID: {sample.get('_ragicId')}")
                print(f"     - Email: {sample.get(email_field, 'N/A')}")
                print(f"     - Name: {sample.get(name_field, 'N/A')}")
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
            print("   ✅ Table 'administrative_employees' is ready.")
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
                    select(func.count()).select_from(AdministrativeEmployee)
                )
                before_count = before_count.scalar()
                print(f"   Records before sync: {before_count}")
                
                # Perform upsert
                upserted = await sync_service._upsert_employees(records, session)
                print(f"   ✅ Upserted {upserted} records.")
                
                # Get count after
                after_count = await session.execute(
                    select(func.count()).select_from(AdministrativeEmployee)
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
                select(func.count()).select_from(AdministrativeEmployee)
            )
            total = total.scalar()
            
            # Check sample records
            samples = await session.execute(
                select(AdministrativeEmployee).limit(5)
            )
            samples = samples.scalars().all()
            
            print(f"   Total employees in DB: {total}")
            print(f"   Sample records:")
            for emp in samples:
                print(f"     - {emp.name} ({emp.email}) - Dept: {emp.department_name}")
            
            # Validate expected count
            expected_count = 238
            if total == expected_count:
                print(f"   ✅ Count matches expected: {expected_count}")
            else:
                print(f"   ⚠️ Count mismatch: got {total}, expected {expected_count}")
        
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
    success = asyncio.run(test_employee_sync())
    sys.exit(0 if success else 1)
