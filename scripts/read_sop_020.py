
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

from core.database import get_standalone_session
from modules.chatbot.models import SOPDocument
from sqlalchemy import select

async def main():
    async with get_standalone_session() as session:
        result = await session.execute(
            select(SOPDocument).where(SOPDocument.sop_id == "SOP-020")
        )
        doc = result.scalar_one_or_none()
        
        if doc:
            print(f"TITLE: {doc.title}")
            print("-" * 20)
            print(doc.content)
            print("-" * 20)
        else:
            print("SOP-020 not found in database.")

if __name__ == "__main__":
    asyncio.run(main())
