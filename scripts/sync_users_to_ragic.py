"""
Sync Existing Users to Ragic.

This script reads all existing User records from the local PostgreSQL database
and writes them to the Ragic User Identity form (Page 13).

This is a ONE-TIME migration script for existing data.

Usage:
    python scripts/sync_users_to_ragic.py
    
Options:
    --dry-run    Preview changes without writing to Ragic
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from core.database import get_standalone_session
from core.models import User
from core.services.user_sync import get_user_ragic_writer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def sync_users_to_ragic(dry_run: bool = False):
    """
    Sync all local users to Ragic.
    
    Args:
        dry_run: If True, only preview without writing.
    """
    logger.info("=" * 60)
    logger.info("Starting User -> Ragic Sync")
    logger.info(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE'}")
    logger.info("=" * 60)
    
    ragic_writer = get_user_ragic_writer()
    
    stats = {
        "total": 0,
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }
    
    async with get_standalone_session() as session:
        # Fetch all users
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        stats["total"] = len(users)
        logger.info(f"Found {stats['total']} user(s) in local database")
        
        for user in users:
            try:
                # Log user info (masked)
                email_masked = _mask_email(user.email) if user.email else "N/A"
                line_id_masked = f"{user.line_user_id[:8]}..." if user.line_user_id else "N/A"
                
                logger.info("-" * 40)
                logger.info(f"Processing User: {user.id}")
                logger.info(f"  Email: {email_masked}")
                logger.info(f"  LINE ID: {line_id_masked}")
                logger.info(f"  Ragic ID: {user.ragic_id or 'Not set'}")
                
                if dry_run:
                    if user.ragic_id:
                        logger.info(f"  [DRY RUN] Would UPDATE in Ragic (ragic_id={user.ragic_id})")
                        stats["updated"] += 1
                    else:
                        logger.info(f"  [DRY RUN] Would CREATE in Ragic")
                        stats["created"] += 1
                    continue
                
                # Check if user already has ragic_id
                if user.ragic_id:
                    # Update existing Ragic record
                    logger.info(f"  Updating existing Ragic record (ragic_id={user.ragic_id})...")
                    
                    success = await ragic_writer.update_user_in_ragic(
                        ragic_id=user.ragic_id,
                        local_db_id=user.id,
                        email=user.email,
                        line_user_id=user.line_user_id,
                        ragic_employee_id=user.ragic_employee_id,
                        display_name=user.display_name,
                        is_active=user.is_active,
                    )
                    
                    if success:
                        logger.info(f"  ✓ Updated successfully")
                        stats["updated"] += 1
                    else:
                        logger.error(f"  ✗ Update failed")
                        stats["errors"] += 1
                else:
                    # Create new Ragic record
                    logger.info(f"  Creating new Ragic record...")
                    
                    ragic_id = await ragic_writer.create_user_in_ragic(
                        local_db_id=user.id,
                        email=user.email,
                        line_user_id=user.line_user_id,
                        ragic_employee_id=user.ragic_employee_id,
                        display_name=user.display_name,
                    )
                    
                    if ragic_id:
                        logger.info(f"  ✓ Created with ragic_id={ragic_id}")
                        
                        # Update local record with ragic_id
                        user.ragic_id = ragic_id
                        stats["created"] += 1
                    else:
                        logger.error(f"  ✗ Creation failed")
                        stats["errors"] += 1
            
            except Exception as e:
                logger.error(f"  ✗ Error processing user {user.id}: {e}")
                stats["errors"] += 1
        
        # Commit changes (update ragic_id in local DB)
        if not dry_run:
            await session.commit()
            logger.info("Changes committed to local database")
    
    # Print summary
    logger.info("=" * 60)
    logger.info("SYNC COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total Users:     {stats['total']}")
    logger.info(f"Created:         {stats['created']}")
    logger.info(f"Updated:         {stats['updated']}")
    logger.info(f"Skipped:         {stats['skipped']}")
    logger.info(f"Errors:          {stats['errors']}")
    logger.info("=" * 60)
    
    return stats


def _mask_email(email: str) -> str:
    """Mask email for logging."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.rsplit("@", 1)
    if len(local) <= 2:
        masked = local[0] + "***" if local else "***"
    else:
        masked = local[:2] + "***"
    return f"{masked}@{domain}"


def main():
    parser = argparse.ArgumentParser(
        description="Sync existing local users to Ragic"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to Ragic"
    )
    args = parser.parse_args()
    
    asyncio.run(sync_users_to_ragic(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
