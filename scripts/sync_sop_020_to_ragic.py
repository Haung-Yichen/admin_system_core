
import asyncio
import sys
import os

sys.path.insert(0, os.getcwd())

from core.database import get_standalone_session
from modules.chatbot.models import SOPDocument
from sqlalchemy import select
from core.http_client import create_standalone_http_client
from core.ragic.service import create_ragic_service

async def main():
    # 1. content from local DB
    async with get_standalone_session() as session:
        result = await session.execute(
            select(SOPDocument).where(SOPDocument.sop_id == "SOP-020")
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            print("SOP-020 not found in local DB.")
            return

        content = doc.content
        ragic_id = doc.ragic_id or (doc.metadata_ and doc.metadata_.get("ragic_record_id"))
        
        if not ragic_id:
            print("Ragic ID not found for SOP-020.")
            return
            
        print(f"Syncing SOP-020 (Ragic ID: {ragic_id}) to Ragic...")
        
        # 2. Update to Ragic
        async with create_standalone_http_client() as http_client:
            ragic_service = create_ragic_service(http_client)
            
            # Form path and field ID from ragic_registry.json
            sheet_path = "/HSIBAdmSys/ychn-test/12"
            content_field_id = "1006066"
            
            data = {
                content_field_id: content
            }
            
            success = await ragic_service.update_record(
                sheet_path=sheet_path,
                record_id=int(ragic_id),
                data=data
            )
            
            if success:
                print("Successfully synced to Ragic.")
            else:
                print("Failed to sync to Ragic.")

if __name__ == "__main__":
    asyncio.run(main())
