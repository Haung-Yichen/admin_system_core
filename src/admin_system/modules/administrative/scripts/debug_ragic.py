"""Debug test with minimal records."""
import asyncio
from core.ragic import RagicService
from modules.administrative.core.config import get_admin_settings, RagicAccountFieldMapping as Fields


async def test():
    settings = get_admin_settings()
    
    print("=" * 60)
    print("Ragic Account Form Debug Test")
    print("=" * 60)
    print()
    print(f"Account URL: {settings.ragic_url_account}")
    print()
    
    # Use framework's RagicService
    service = RagicService(
        api_key=settings.ragic_api_key.get_secret_value(),
        timeout=30.0,
    )
    
    try:
        records = await service.get_records_by_url(
            full_url=settings.ragic_url_account,
            params={"naming": "EID"},
        )
    finally:
        await service.close()
    
    # Get first 7 records
    records = records[:7]
    
    print(f"Testing with {len(records)} records:")
    print("-" * 60)
    
    for r in records:
        ragic_id = r.get(Fields.RAGIC_ID, '') or r.get('_ragicId')
        account_id = (r.get(Fields.ACCOUNT_ID, '') or '').strip()
        name = (r.get(Fields.NAME, '') or '').strip()
        status = r.get(Fields.STATUS, '')
        org_code = (r.get(Fields.ORG_CODE, '') or '').strip()
        org_name = (r.get(Fields.ORG_NAME, '') or '').strip()
        emails = (r.get(Fields.EMAILS, '') or '').strip()
        
        status_str = "Active" if status == "1" else "Disabled"
        
        print(f"  [{ragic_id}] {account_id} - {name}")
        print(f"       Status: {status_str}")
        print(f"       Org: {org_code} ({org_name})")
        print(f"       Email: {emails}")
        print()


if __name__ == "__main__":
    asyncio.run(test())
