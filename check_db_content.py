
import asyncio
import os
import sys
from sqlalchemy import select

# Add the project root to sys.path
sys.path.append(os.getcwd())
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from core.database.session import get_standalone_session
from core.models import User

async def main():
    async with get_standalone_session() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        print(f"Total Users: {len(users)}")
        print("-" * 30)
        
        for user in users:
            print(f"Name: {user.display_name}")
            print(f"Line ID: {user.line_user_id}")
            print(f"Emp ID: {user.ragic_employee_id}")
            print("-" * 30)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError:
        pass
