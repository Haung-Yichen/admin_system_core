"""
Force Encrypt Data Migration Script.

This script scans all tables with EncryptedType columns and converts any
plaintext data to properly encrypted format.

After running this script, the EncryptedType can use strict decryption
without fallback to plaintext handling.

TABLES & COLUMNS AFFECTED:
==========================
1. administrative_accounts:
   - id_card_number, emails, phones, mobiles
   - household_postal_code, household_city, household_district, household_address
   - mailing_postal_code, mailing_city, mailing_district, mailing_address
   - emergency_contact, emergency_phone

2. users:
   - line_user_id, email, ragic_employee_id

WARNING: Always backup your database before running this script!
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from core.database import get_engine
from core.security.encryption import get_encryption_service


# Define tables and their encrypted columns
ENCRYPTED_TABLES = {
    "administrative_accounts": {
        "pk": "ragic_id",
        "columns": [
            "id_card_number",
            "emails",
            "phones",
            "mobiles",
            "household_postal_code",
            "household_city",
            "household_district",
            "household_address",
            "mailing_postal_code",
            "mailing_city",
            "mailing_district",
            "mailing_address",
            "emergency_contact",
            "emergency_phone",
        ],
    },
    "users": {
        "pk": "id",
        "columns": [
            "line_user_id",
            "email",
            "ragic_employee_id",
        ],
    },
}


def is_encrypted_hex(value: str) -> bool:
    """
    Check if a value looks like encrypted hex data.
    
    Encrypted data characteristics:
    - All characters are hex (0-9, a-f, A-F)
    - Length is typically > 32 characters (IV + ciphertext + tag)
    """
    if not value or len(value) < 32:
        return False
    return all(c in '0123456789abcdefABCDEF' for c in value)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext value and return hex-encoded ciphertext."""
    service = get_encryption_service()
    encrypted_bytes = service.encrypt(plaintext)
    return encrypted_bytes.hex()


async def migrate_table(table_name: str, pk_column: str, encrypted_columns: list[str]) -> dict:
    """
    Migrate a single table's encrypted columns.
    
    Returns:
        Dict with migration statistics.
    """
    engine = get_engine()
    stats = {
        "table": table_name,
        "total_rows": 0,
        "columns_migrated": {},
        "errors": [],
    }
    
    for column in encrypted_columns:
        stats["columns_migrated"][column] = {"encrypted": 0, "skipped": 0, "null": 0}
    
    # First, read all data
    async with engine.connect() as conn:
        columns_str = ", ".join([pk_column] + encrypted_columns)
        result = await conn.execute(text(f"SELECT {columns_str} FROM {table_name}"))
        rows = result.fetchall()
    
    stats["total_rows"] = len(rows)
    print(f"\n📋 Table: {table_name} ({len(rows)} rows)")
    
    for row in rows:
        pk_value = row[0]
        
        for i, column in enumerate(encrypted_columns):
            value = row[i + 1]
            col_stats = stats["columns_migrated"][column]
            
            if value is None:
                col_stats["null"] += 1
                continue
            
            if is_encrypted_hex(value):
                # Already encrypted
                col_stats["skipped"] += 1
                continue
            
            # Need to encrypt this plaintext value - use separate transaction
            try:
                encrypted_value = encrypt_value(value)
                async with engine.begin() as conn:
                    await conn.execute(
                        text(f"UPDATE {table_name} SET {column} = :value WHERE {pk_column} = :pk"),
                        {"value": encrypted_value, "pk": pk_value}
                    )
                col_stats["encrypted"] += 1
            except Exception as e:
                error_msg = f"Error encrypting {table_name}.{column} (pk={pk_value}): {e}"
                stats["errors"].append(error_msg)
                print(f"  ❌ {error_msg}")
    
    # Print column summary
    for column, col_stats in stats["columns_migrated"].items():
        encrypted = col_stats["encrypted"]
        skipped = col_stats["skipped"]
        null = col_stats["null"]
        if encrypted > 0:
            print(f"  ✓ {column}: {encrypted} encrypted, {skipped} already OK, {null} NULL")
        elif skipped > 0 or null > 0:
            print(f"  ○ {column}: {skipped} already OK, {null} NULL")
    
    return stats


async def main():
    """Run the full migration."""
    print("=" * 60)
    print("Force Encrypt Data Migration")
    print("=" * 60)
    print("\nThis script will encrypt all plaintext data in EncryptedType columns.")
    print("Tables to process:", ", ".join(ENCRYPTED_TABLES.keys()))
    
    all_stats = []
    
    for table_name, config in ENCRYPTED_TABLES.items():
        try:
            stats = await migrate_table(
                table_name=table_name,
                pk_column=config["pk"],
                encrypted_columns=config["columns"],
            )
            all_stats.append(stats)
        except Exception as e:
            print(f"\n❌ Failed to process {table_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    
    total_encrypted = 0
    total_errors = 0
    
    for stats in all_stats:
        table_encrypted = sum(c["encrypted"] for c in stats["columns_migrated"].values())
        total_encrypted += table_encrypted
        total_errors += len(stats["errors"])
        print(f"\n{stats['table']}:")
        print(f"  - Rows processed: {stats['total_rows']}")
        print(f"  - Values encrypted: {table_encrypted}")
        print(f"  - Errors: {len(stats['errors'])}")
    
    print(f"\n{'=' * 60}")
    print(f"Total values encrypted: {total_encrypted}")
    print(f"Total errors: {total_errors}")
    
    if total_errors == 0:
        print("\n✅ Migration completed successfully!")
        print("You can now restore strict encryption checking in EncryptedType.")
    else:
        print("\n⚠️  Migration completed with errors. Review the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
