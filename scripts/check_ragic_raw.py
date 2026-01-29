"""Check raw Ragic data for a specific email."""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from modules.administrative.core.config import get_admin_settings, RagicAccountFieldMapping as F


async def main():
    email_to_find = sys.argv[1] if len(sys.argv) > 1 else "macmaxlin0428@gmail.com"
    
    settings = get_admin_settings()
    
    print(f"Fetching raw data from Ragic: {settings.ragic_url_account}")
    print(f"Looking for email: {email_to_find}")
    print("=" * 60)
    
    async with httpx.AsyncClient(
        timeout=30,
        headers={"Authorization": f"Basic {settings.ragic_api_key.get_secret_value()}"}
    ) as client:
        response = await client.get(
            settings.ragic_url_account,
            params={"naming": "EID"}
        )
        data = response.json()
    
    found = False
    for ragic_id, record in data.items():
        if ragic_id == "_metaData":
            continue
            
        emails = record.get(F.EMAILS, "") or ""
        name = record.get(F.NAME, "") or ""
        account_id = record.get(F.ACCOUNT_ID, "") or ""
        
        if email_to_find.lower() in emails.lower():
            found = True
            print(f"✓ FOUND in Ragic raw data!")
            print(f"  Ragic ID: {ragic_id}")
            print(f"  Name: {name}")
            print(f"  Account ID: {account_id}")
            print(f"  Emails: {emails}")
            print(f"  Status: {record.get(F.STATUS, 'N/A')}")
            
            if not account_id.strip():
                print()
                print("  ⚠️ WARNING: This record has NO account_id!")
                print("     It will be SKIPPED during sync.")
                print("     Please fill in the '帳號' field in Ragic.")
    
    if not found:
        print(f"✗ Email '{email_to_find}' NOT FOUND in Ragic raw data")
        print()
        print("Recent records in Ragic:")
        count = 0
        for ragic_id, record in list(data.items())[-5:]:
            if ragic_id == "_metaData":
                continue
            name = record.get(F.NAME, "")
            emails = record.get(F.EMAILS, "")
            account_id = record.get(F.ACCOUNT_ID, "")
            print(f"  [{ragic_id}] {name} - {emails or '(no email)'} - account_id: {account_id or '(empty)'}")


if __name__ == "__main__":
    asyncio.run(main())
