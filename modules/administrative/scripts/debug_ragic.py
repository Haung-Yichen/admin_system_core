"""Debug test with minimal records."""
import asyncio
import httpx
from modules.administrative.core.config import get_admin_settings, RagicAccountFieldMapping as Fields


async def test():
    settings = get_admin_settings()
    
    print("=" * 60)
    print("Ragic Account Form Debug Test")
    print("=" * 60)
    print()
    print(f"Account URL: {settings.ragic_url_account}")
    print()
    
    # Fetch just a few records
    async with httpx.AsyncClient(
        timeout=30, 
        headers={'Authorization': f'Basic {settings.ragic_api_key.get_secret_value()}'}
    ) as client:
        response = await client.get(
            settings.ragic_url_account,
            params={"naming": "EID"}
        )
        data = response.json()
    
    # Get first 5 records
    records = []
    for k, v in list(data.items())[:7]:
        if k != '_metaData':
            v['_ragicId'] = int(k)
            records.append(v)
    
    print(f"Testing with {len(records)} records:")
    print("-" * 60)
    
    for r in records:
        ragic_id = r.get(Fields.RAGIC_ID, '') or r.get('_ragicId')
        account_id = r.get(Fields.ACCOUNT_ID, '').strip()
        name = r.get(Fields.NAME, '').strip()
        status = r.get(Fields.STATUS, '')
        org_code = r.get(Fields.ORG_CODE, '').strip()
        org_name = r.get(Fields.ORG_NAME, '').strip()
        emails = r.get(Fields.EMAILS, '').strip()
        
        status_str = "Active" if status == "1" else "Disabled"
        
        print(f"  [{ragic_id}] {account_id} - {name}")
        print(f"       Status: {status_str}")
        print(f"       Org: {org_code} ({org_name})")
        print(f"       Email: {emails}")
        print()


if __name__ == "__main__":
    asyncio.run(test())
