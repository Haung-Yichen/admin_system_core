#!/usr/bin/env python
"""Quick script to check users table."""
import asyncio
from sqlalchemy import text
from core.database.session import get_standalone_session

async def main():
    async with get_standalone_session() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        count = result.scalar()
        print(f"Users count: {count}")
        
        if count > 0:
            result = await session.execute(text("SELECT id, display_name, is_active, created_at FROM users"))
            rows = result.fetchall()
            for row in rows:
                print(f"  - {row}")

if __name__ == "__main__":
    asyncio.run(main())
