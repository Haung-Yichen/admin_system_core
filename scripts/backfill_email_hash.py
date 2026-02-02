"""
Backfill primary_email_hash for existing administrative_accounts.

This script populates the primary_email_hash column for all existing records
that have email data but no hash value yet.

Uses standard ORM operations - EncryptedType handles decryption automatically.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from core.database import get_standalone_session
from core.security import generate_blind_index
from modules.administrative.models import AdministrativeAccount


def compute_primary_email_hash(emails: str | None) -> str | None:
    """
    Extract primary email and compute blind index hash.
    
    The primary email is the first email in the comma-separated list.
    """
    if not emails:
        return None
    
    # Extract first email, strip whitespace, lowercase for consistency
    primary_email = emails.split(",")[0].strip().lower()
    if not primary_email:
        return None
    
    return generate_blind_index(primary_email)


async def backfill_email_hashes():
    """Backfill primary_email_hash for all existing accounts."""
    async with get_standalone_session() as db:
        # Get all accounts that have no hash
        result = await db.execute(
            select(AdministrativeAccount).where(
                AdministrativeAccount.primary_email_hash.is_(None)
            )
        )
        accounts = result.scalars().all()
        
        if not accounts:
            print("✅ No accounts need backfilling - all records already have primary_email_hash")
            return
        
        print(f"🔄 Found {len(accounts)} accounts to backfill...")
        
        updated = 0
        skipped = 0
        
        for account in accounts:
            identifier = account.account_id or f"ragic:{account.ragic_id}"
            
            # emails is auto-decrypted by EncryptedType
            email_hash = compute_primary_email_hash(account.emails)
            
            if email_hash:
                account.primary_email_hash = email_hash
                updated += 1
                print(f"  ✓ Updated account {identifier}")
            else:
                skipped += 1
                print(f"  ⚠ Skipped account {identifier} (no valid email)")
        
        await db.commit()
        
        print(f"\n✅ Backfill complete:")
        print(f"   - Updated: {updated}")
        print(f"   - Skipped (no email): {skipped}")


async def main():
    try:
        await backfill_email_hashes()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(main())
