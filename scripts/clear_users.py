#!/usr/bin/env python
"""Quick script to clear users table."""
import asyncio
from sqlalchemy import text
from core.database.session import get_standalone_session

async def main():
    async with get_standalone_session() as session:
        await session.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await session.commit()
        print("Users table cleared!")
        
        result = await session.execute(text("SELECT COUNT(*) FROM users"))
        count = result.scalar()
        print(f"Users count now: {count}")

if __name__ == "__main__":
    asyncio.run(main())
