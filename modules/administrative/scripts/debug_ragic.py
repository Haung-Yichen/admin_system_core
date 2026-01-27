"""Debug test with minimal records."""
import asyncio
import httpx
from modules.administrative.core.config import get_admin_settings

async def test():
    settings = get_admin_settings()
    
    print(f"Email field: {settings.field_employee_email}")
    print(f"Name field: {settings.field_employee_name}")
    print(f"Dept field: {settings.field_employee_department}")
    print(f"Sup field: {settings.field_employee_supervisor_email}")
    print()
    
    # Fetch just a few records
    async with httpx.AsyncClient(
        timeout=30, 
        headers={'Authorization': f'Basic {settings.ragic_api_key.get_secret_value()}'}
    ) as client:
        response = await client.get(settings.ragic_url_employee)
        data = response.json()
    
    # Get first 3 records
    records = []
    for k, v in list(data.items())[:5]:
        if k != '_metaData':
            v['_ragicId'] = int(k)
            records.append(v)
    
    print(f"Testing with {len(records)} records:")
    for r in records:
        email = r.get(settings.field_employee_email, '').strip()
        name = r.get(settings.field_employee_name, '').strip()
        dept = r.get(settings.field_employee_department, '').strip()
        sup = r.get(settings.field_employee_supervisor_email, '').strip()
        rid = r.get('_ragicId')
        print(f"  [{rid}] {name} - {email} - Dept: {dept} - Sup: {sup}")

if __name__ == "__main__":
    asyncio.run(test())
