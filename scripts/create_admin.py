#!/usr/bin/env python3
"""
Create Admin User Script.

CLI tool for creating initial administrator accounts.
Usage: python scripts/create_admin.py <username> <password>
"""

import asyncio
import sys
from pathlib import Path
from getpass import getpass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_standalone_session, init_database
from core.models.admin_user import AdminUser


def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


async def create_admin(username: str, password: str) -> bool:
    """
    Create an admin user in the database.

    Args:
        username: Admin username
        password: Plain text password (will be hashed)

    Returns:
        bool: True if created successfully
    """
    await init_database()

    async with get_standalone_session() as session:
        # Check if username exists
        stmt = select(AdminUser).where(AdminUser.username == username)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            print(f"❌ Error: Username '{username}' already exists.")
            return False

        # Create new admin
        admin = AdminUser(
            username=username,
            password_hash=hash_password(password),
            is_active=True,
        )
        session.add(admin)
        await session.commit()

        print(f"✅ Admin user '{username}' created successfully.")
        return True


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) == 3:
        # Non-interactive mode: python create_admin.py <username> <password>
        username = sys.argv[1]
        password = sys.argv[2]
    elif len(sys.argv) == 2:
        # Semi-interactive: python create_admin.py <username>
        username = sys.argv[1]
        password = getpass("Enter password: ")
        password_confirm = getpass("Confirm password: ")
        if password != password_confirm:
            print("❌ Error: Passwords do not match.")
            sys.exit(1)
    else:
        # Fully interactive
        print("=== Create Admin User ===")
        username = input("Username: ").strip()
        if not username:
            print("❌ Error: Username cannot be empty.")
            sys.exit(1)

        password = getpass("Password: ")
        password_confirm = getpass("Confirm password: ")
        if password != password_confirm:
            print("❌ Error: Passwords do not match.")
            sys.exit(1)

    if len(password) < 8:
        print("❌ Error: Password must be at least 8 characters.")
        sys.exit(1)

    success = asyncio.run(create_admin(username, password))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
