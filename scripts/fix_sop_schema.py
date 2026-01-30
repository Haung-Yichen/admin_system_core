"""
Fix SOP schema.

Adds missing columns to sop_documents table.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_engine


async def fix_sop_schema():
    """Add missing columns to sop_documents."""
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Check current columns
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sop_documents'
        """))
        existing_columns = {row[0] for row in result.fetchall()}
        print(f"Existing columns: {existing_columns}")
        
        # Check sop_id
        if 'sop_id' not in existing_columns:
            print("🔄 Adding 'sop_id' column...")
            await conn.execute(text("""
                ALTER TABLE sop_documents 
                ADD COLUMN sop_id VARCHAR(50) UNIQUE
            """))
            print("✅ Added 'sop_id' column")
            
            print("🔄 Creating index on sop_id...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_sop_documents_sop_id 
                ON sop_documents (sop_id)
            """))
        else:
            print("✅ 'sop_id' already exists")
            
        # Check category
        if 'category' not in existing_columns:
            print("🔄 Adding 'category' column...")
            await conn.execute(text("""
                ALTER TABLE sop_documents 
                ADD COLUMN category VARCHAR(128)
            """))
            print("✅ Added 'category' column")
            
            print("🔄 Creating index on category...")
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_sop_documents_category 
                ON sop_documents (category)
            """))
            
        # Check tags
        if 'tags' not in existing_columns:
            print("🔄 Adding 'tags' column...")
            await conn.execute(text("""
                ALTER TABLE sop_documents 
                ADD COLUMN tags JSONB DEFAULT '[]'::jsonb
            """))
            print("✅ Added 'tags' column")
            
        # Check is_published
        if 'is_published' not in existing_columns:
             print("🔄 Adding 'is_published' column...")
             await conn.execute(text("""
                ALTER TABLE sop_documents 
                ADD COLUMN is_published BOOLEAN DEFAULT TRUE NOT NULL
            """))
             print("✅ Added 'is_published' column")

async def main():
    try:
        await fix_sop_schema()
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
