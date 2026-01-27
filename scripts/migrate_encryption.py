"""
Database Migration Script for Encryption.

WARNING: This script is for reference only. Due to schema changes adding new
columns (email_hash, line_sub_hash) and changing column types, the safest
approach for production is to:

1. Backup your database
2. Export critical data
3. Drop and recreate with new schema
4. Re-import data with encryption applied

For development: Simply delete the Docker volume and restart.

This script demonstrates the encryption logic for manual migration if needed.
"""

from modules.chatbot.models import SOPDocument
from core.models import User, UsedToken
from core.security import generate_blind_index
from core.database import get_db_session, get_engine
from sqlalchemy import select, text
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def migrate_users():
    """
    Migrate User table to encrypted fields.

    NOTE: This assumes the new schema columns already exist.
    In practice, you'll need to use Alembic migrations or manual ALTER TABLE.
    """
    print("🔄 Migrating User table...")

    engine = get_engine()
    async with engine.begin() as conn:
        # This is pseudocode - actual migration requires schema changes first
        print("⚠️  User migration requires manual schema update:")
        print("   - Add email_hash column")
        print("   - Add line_sub_hash column")
        print("   - Change column types for encrypted fields")
        print("   Easiest approach: Drop DB volume and recreate")


async def migrate_sop_documents():
    """Migrate SOPDocument table."""
    print("🔄 Migrating SOPDocument table...")
    print("   Content will be encrypted on next import")


async def migrate_used_tokens():
    """Migrate UsedToken table."""
    print("🔄 Migrating UsedToken table...")
    print("   Tokens are temporary, can be cleared and recreated")


async def main():
    print("=" * 80)
    print("Database Encryption Migration")
    print("=" * 80)
    print()
    print("⚠️  WARNING: This is a destructive operation!")
    print("   Make sure you have backed up your database.")
    print()

    response = input("Have you backed up your database? (yes/no): ")
    if response.lower() != "yes":
        print("❌ Aborted. Please backup your database first.")
        return

    print()
    print("Due to schema changes, the recommended approach is:")
    print("1. docker-compose down")
    print("2. docker volume rm admin_system_core_postgres_data")
    print("3. docker-compose up -d")
    print()
    print("This will create a fresh database with the encrypted schema.")
    print()

    response = input(
        "Do you want to proceed with fresh database instructions? (yes/no): ")
    if response.lower() == "yes":
        print()
        print("✅ Steps for fresh database setup:")
        print("   1. Stop services: docker-compose down")
        print("   2. Remove volume: docker volume rm admin_system_core_postgres_data")
        print("   3. Ensure SECURITY_KEY is in .env")
        print("   4. Start services: docker-compose up -d")
        print("   5. Re-import your data (it will be encrypted automatically)")
        print()
    else:
        print("❌ Aborted.")


if __name__ == "__main__":
    asyncio.run(main())
