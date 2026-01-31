"""
Database Migration Script for Encryption Key Derivation Upgrade.

This script handles migration from the legacy encryption scheme (direct master key usage)
to the new HKDF-based key derivation scheme.

MIGRATION SCENARIOS:
====================

1. Fresh Installation (No existing data):
   - No migration needed
   - New data will use HKDF-derived keys automatically

2. Existing Data with Legacy Encryption:
   - Set ENCRYPTION_LEGACY_MODE=true temporarily
   - Export all encrypted data using this script
   - Remove ENCRYPTION_LEGACY_MODE (or set to false)
   - Re-import data with new encryption

3. In-Place Migration (Advanced):
   - This script can decrypt with legacy keys and re-encrypt with new keys
   - Requires database downtime

WARNING: This script is destructive. Always backup your database first!

BACKWARD COMPATIBILITY:
======================
If you cannot migrate immediately, set ENCRYPTION_LEGACY_MODE=true in your
environment. This will use the master key directly (legacy behavior).
This is NOT recommended for new deployments.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session, get_engine
from core.security import EncryptionService
from core.security.encryption import KeyDerivationService, _load_master_key


class MigrationService:
    """
    Service to migrate encrypted data from legacy to HKDF key derivation.
    """

    def __init__(self) -> None:
        """Initialize with both legacy and new encryption services."""
        self.master_key = _load_master_key()

        # Legacy service (uses master key directly)
        self.legacy_service = EncryptionService(
            master_key=self.master_key,
            legacy_mode=True,
        )

        # New service (uses HKDF-derived keys)
        self.new_service = EncryptionService(
            master_key=self.master_key,
            legacy_mode=False,
        )

    def migrate_encrypted_value(self, encrypted_hex: str | None) -> tuple[str | None, str | None]:
        """
        Migrate a single encrypted value from legacy to new encryption.

        Args:
            encrypted_hex: Hex-encoded encrypted data from database.

        Returns:
            Tuple of (new_encrypted_hex, plaintext) or (None, None).
        """
        if not encrypted_hex:
            return None, None

        try:
            # Decrypt with legacy key
            encrypted_bytes = bytes.fromhex(encrypted_hex)
            plaintext = self.legacy_service.decrypt(encrypted_bytes)

            # Re-encrypt with new derived key
            new_encrypted = self.new_service.encrypt(plaintext)
            return new_encrypted.hex(), plaintext
        except Exception as e:
            print(f"    ⚠️  Failed to migrate value: {e}")
            return None, None

    def generate_new_blind_index(self, plaintext: str | None) -> str | None:
        """
        Generate blind index with new derived key.

        Args:
            plaintext: The original plaintext value.

        Returns:
            New HMAC-SHA256 blind index.
        """
        if not plaintext:
            return None

        return self.new_service.generate_blind_index(plaintext)


async def migrate_users_table(session: AsyncSession, migration_service: MigrationService) -> int:
    """
    Migrate User table to new encryption scheme.

    Returns:
        Number of users migrated.
    """
    print("🔄 Migrating users table...")

    # Get all users with raw encrypted values
    result = await session.execute(
        text("""
            SELECT id, line_user_id, email, ragic_employee_id, display_name
            FROM users
        """)
    )
    rows = result.fetchall()

    if not rows:
        print("   No users found to migrate.")
        return 0

    migrated_count = 0
    for row in rows:
        user_id = row[0]
        line_user_id_enc = row[1]
        email_enc = row[2]
        ragic_employee_id_enc = row[3]
        display_name_enc = row[4]

        print(f"   Processing user {user_id}...")

        # Migrate each encrypted field
        new_line_user_id, line_user_id_plain = migration_service.migrate_encrypted_value(line_user_id_enc)
        new_email, email_plain = migration_service.migrate_encrypted_value(email_enc)
        new_ragic_id, _ = migration_service.migrate_encrypted_value(ragic_employee_id_enc)
        new_display_name, _ = migration_service.migrate_encrypted_value(display_name_enc)

        # Generate new blind indexes
        new_line_user_id_hash = migration_service.generate_new_blind_index(line_user_id_plain)
        new_email_hash = migration_service.generate_new_blind_index(email_plain)

        if new_line_user_id and new_email:
            # Update the user record
            await session.execute(
                text("""
                    UPDATE users
                    SET line_user_id = :line_user_id,
                        line_user_id_hash = :line_user_id_hash,
                        email = :email,
                        email_hash = :email_hash,
                        ragic_employee_id = :ragic_employee_id,
                        display_name = :display_name
                    WHERE id = :id
                """),
                {
                    "id": user_id,
                    "line_user_id": new_line_user_id,
                    "line_user_id_hash": new_line_user_id_hash,
                    "email": new_email,
                    "email_hash": new_email_hash,
                    "ragic_employee_id": new_ragic_id,
                    "display_name": new_display_name,
                },
            )
            migrated_count += 1
            print(f"      ✅ User {user_id} migrated")
        else:
            print(f"      ❌ User {user_id} migration failed")

    return migrated_count


async def migrate_sop_documents_table(session: AsyncSession, migration_service: MigrationService) -> int:
    """
    Migrate SOPDocument table to new encryption scheme.

    Returns:
        Number of documents migrated.
    """
    print("🔄 Migrating sop_documents table...")

    # Get all SOP documents with raw encrypted values
    result = await session.execute(
        text("""
            SELECT id, content
            FROM sop_documents
        """)
    )
    rows = result.fetchall()

    if not rows:
        print("   No SOP documents found to migrate.")
        return 0

    migrated_count = 0
    for row in rows:
        doc_id = row[0]
        content_enc = row[1]

        print(f"   Processing document {doc_id}...")

        # Migrate content
        new_content, _ = migration_service.migrate_encrypted_value(content_enc)

        if new_content:
            await session.execute(
                text("""
                    UPDATE sop_documents
                    SET content = :content
                    WHERE id = :id
                """),
                {
                    "id": doc_id,
                    "content": new_content,
                },
            )
            migrated_count += 1
            print(f"      ✅ Document {doc_id} migrated")
        else:
            print(f"      ❌ Document {doc_id} migration failed")

    return migrated_count


async def migrate_admin_users_table(session: AsyncSession, migration_service: MigrationService) -> int:
    """
    Migrate AdminUser table if it has encrypted fields.

    Returns:
        Number of admin users migrated.
    """
    print("🔄 Checking admin_users table...")

    # Check if table exists and has data
    try:
        result = await session.execute(
            text("SELECT COUNT(*) FROM admin_users")
        )
        count = result.scalar()
        if count == 0:
            print("   No admin users found.")
            return 0

        # AdminUser typically doesn't have encrypted fields based on the model
        # but check anyway
        print(f"   Found {count} admin users (no encrypted fields to migrate).")
        return 0
    except Exception as e:
        print(f"   Table may not exist or error: {e}")
        return 0


async def run_migration() -> None:
    """Run the complete migration."""
    print("=" * 80)
    print("🔐 Encryption Key Derivation Migration (Legacy → HKDF)")
    print("=" * 80)
    print()

    migration_service = MigrationService()

    print("📊 Migration Summary:")
    print(f"   Legacy mode key (first 8 hex): {migration_service.master_key[:4].hex()}...")
    print(f"   New encryption key (first 8 hex): {migration_service.new_service._encryption_key[:4].hex()}...")
    print(f"   New index key (first 8 hex): {migration_service.new_service._index_key[:4].hex()}...")
    print()

    async for session in get_db_session():
        try:
            # Migrate all tables
            users_count = await migrate_users_table(session, migration_service)
            sop_count = await migrate_sop_documents_table(session, migration_service)
            admin_count = await migrate_admin_users_table(session, migration_service)

            # Commit all changes
            await session.commit()

            print()
            print("=" * 80)
            print("✅ Migration Complete!")
            print("=" * 80)
            print(f"   Users migrated: {users_count}")
            print(f"   SOP Documents migrated: {sop_count}")
            print(f"   Admin Users migrated: {admin_count}")
            print()
            print("⚠️  IMPORTANT: Make sure ENCRYPTION_LEGACY_MODE is NOT set")
            print("   in your environment before restarting the application.")
            print()

        except Exception as e:
            await session.rollback()
            print(f"❌ Migration failed: {e}")
            raise


async def check_encryption_compatibility() -> None:
    """Check if current data is compatible with new encryption."""
    print("🔍 Checking encryption compatibility...")

    try:
        service = EncryptionService()
        mode = "LEGACY" if service.is_legacy_mode else "HKDF"
        print(f"   Current mode: {mode}")

        # Test encryption/decryption
        test_value = "test_migration_value_12345"
        encrypted = service.encrypt(test_value)
        decrypted = service.decrypt(encrypted)

        if decrypted == test_value:
            print("   ✅ Encryption/decryption working correctly")
        else:
            print("   ❌ Encryption/decryption mismatch!")

        # Test blind index
        index = service.generate_blind_index(test_value)
        print(f"   Blind index length: {len(index)} chars")

    except Exception as e:
        print(f"   ❌ Error: {e}")


async def main() -> None:
    print("=" * 80)
    print("Database Encryption Migration (HKDF Key Derivation Upgrade)")
    print("=" * 80)
    print()
    print("⚠️  WARNING: This operation will modify encrypted data!")
    print("   Make sure you have backed up your database.")
    print()

    # Check current state
    await check_encryption_compatibility()
    print()

    print("MIGRATION OPTIONS:")
    print("-" * 40)
    print("1. Check compatibility only (already done above)")
    print("2. Run full migration (Legacy → HKDF)")
    print("3. Fresh database setup instructions")
    print("4. Exit")
    print()

    response = input("Select option (1-4): ").strip()

    if response == "1":
        print("✅ Compatibility check completed above.")

    elif response == "2":
        print()
        confirm = input("Are you sure? This will modify database. (yes/no): ").strip()
        if confirm.lower() == "yes":
            await run_migration()
        else:
            print("❌ Migration cancelled.")

    elif response == "3":
        print()
        print("✅ Steps for fresh database setup with new encryption:")
        print("   1. Export any critical data you need to preserve")
        print("   2. Stop services: docker-compose down")
        print("   3. Remove volume: docker volume rm admin_system_core_postgres_data")
        print("   4. Ensure SECURITY_KEY is in .env")
        print("   5. Ensure ENCRYPTION_LEGACY_MODE is NOT set (or set to false)")
        print("   6. Start services: docker-compose up -d")
        print("   7. Re-import your data (it will use HKDF-derived keys)")
        print()

    else:
        print("❌ Exited.")


if __name__ == "__main__":
    asyncio.run(main())
    asyncio.run(main())
