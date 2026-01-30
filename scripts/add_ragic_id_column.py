"""
Add ragic_id column to sop_documents table.

This migration script adds the ragic_id column that was added to the SOPDocument model
but is missing from the existing database table.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_engine


async def add_ragic_id_column():
    """Add ragic_id column to sop_documents if it doesn't exist."""
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sop_documents' AND column_name = 'ragic_id'
        """))
        exists = result.fetchone() is not None
        
        if exists:
            print("✅ Column 'ragic_id' already exists in sop_documents table")
            return
        
        # Add the column
        print("🔄 Adding 'ragic_id' column to sop_documents table...")
        await conn.execute(text("""
            ALTER TABLE sop_documents 
            ADD COLUMN ragic_id INTEGER UNIQUE
        """))
        
        # Create index for the column
        print("🔄 Creating index on ragic_id...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_sop_documents_ragic_id 
            ON sop_documents (ragic_id)
        """))
        
        print("✅ Successfully added 'ragic_id' column to sop_documents table")


async def main():
    try:
        await add_ragic_id_column()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
