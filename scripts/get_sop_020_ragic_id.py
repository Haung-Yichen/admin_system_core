
import asyncio
import sys
import os

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
            print(f"SOP-020 found.")
            print(f"DB ID: {doc.id}")
            print(f"Ragic ID: {doc.ragic_id}")
            if doc.metadata_:
                print(f"Metadata Ragic ID: {doc.metadata_.get('ragic_record_id')}")
        else:
            print("SOP-020 not found.")

if __name__ == "__main__":
    asyncio.run(main())
