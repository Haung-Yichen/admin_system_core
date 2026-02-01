"""
Database Migration: Add ragic_id to users table.

This script adds the ragic_id column to the users table to support
the Ragic-backed User Identity system.

Run this script once to update existing databases.

Usage:
    python scripts/add_user_ragic_id.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_standalone_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    """Add ragic_id column to users table if it doesn't exist."""
    
    async with get_standalone_session() as session:
        # Check if column already exists
        check_sql = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'ragic_id'
        """)
        
        result = await session.execute(check_sql)
        exists = result.scalar_one_or_none()
        
        if exists:
            logger.info("Column 'ragic_id' already exists in 'users' table")
            return
        
        # Add the column
        logger.info("Adding 'ragic_id' column to 'users' table...")
        
        alter_sql = text("""
            ALTER TABLE users 
            ADD COLUMN ragic_id INTEGER UNIQUE
        """)
        
        await session.execute(alter_sql)
        
        # Create index
        index_sql = text("""
            CREATE INDEX IF NOT EXISTS ix_users_ragic_id 
            ON users (ragic_id)
        """)
        
        await session.execute(index_sql)
        
        # Add comment
        comment_sql = text("""
            COMMENT ON COLUMN users.ragic_id IS 
            'Ragic internal record ID (_ragicId) for sync'
        """)
        
        await session.execute(comment_sql)
        
        await session.commit()
        logger.info("Migration completed successfully!")


def main():
    """Run the migration."""
    asyncio.run(migrate())


if __name__ == "__main__":
    main()
