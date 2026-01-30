#!/usr/bin/env python3
"""
Upload SOP Knowledge Base to Ragic Form.

This script reads the SOP samples JSON and uploads them to the Ragic form:
https://ap13.ragic.com/HSIBAdmSys/ychn-test/12

Run: python scripts/upload_sop_to_ragic.py
"""

import asyncio
import json
import sys
from pathlib import Path

import httpx

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.app_context import ConfigLoader


# Ragic form configuration
RAGIC_FORM_URL = "https://ap13.ragic.com/HSIBAdmSys/ychn-test/12"
RAGIC_SHEET_PATH = "/HSIBAdmSys/ychn-test/12"

# SOP JSON file path
SOP_FILE = Path(__file__).parent.parent / "modules" / "chatbot" / "data" / "sop_samples.json"


async def get_form_schema(api_key: str, base_url: str) -> dict:
    """Fetch and display form schema to understand field structure."""
    print("=" * 60)
    print("正在取得表單欄位結構...")
    print("=" * 60)
    
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }
    
    # Try info endpoint first
    url_info = f"{RAGIC_FORM_URL}?info=1"
    print(f"API URL (info): {url_info}")
    print(f"Using API key: {api_key[:10]}...")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get schema info
            response = await client.get(url_info, headers=headers)
            print(f"Info response status: {response.status_code}")
            
            if response.status_code == 200:
                schema = response.json()
                if schema:
                    print(f"\n表單欄位結構 (info=1):")
                    print(json.dumps(schema, ensure_ascii=False, indent=2))
                else:
                    print("info=1 回傳空物件")
            
            # Also try to get existing records to see field structure
            url_data = f"{RAGIC_FORM_URL}?api="
            print(f"\n嘗試取得現有資料以推測欄位結構...")
            response2 = await client.get(url_data, headers=headers)
            print(f"Data response status: {response2.status_code}")
            
            if response2.status_code == 200:
                data = response2.json()
                print(f"\n現有資料:")
                print(json.dumps(data, ensure_ascii=False, indent=2))
                return data
            else:
                print(f"Error response: {response2.text}")
                return schema if schema else {}
                
    except Exception as e:
        print(f"取得表單結構失敗: {e}")
        import traceback
        traceback.print_exc()
        return {}


async def upload_sop_records(api_key: str, base_url: str, field_mapping: dict):
    """Upload SOP records to Ragic."""
    # Load SOP data
    print("\n" + "=" * 60)
    print("正在讀取 SOP 資料...")
    print("=" * 60)
    
    with open(SOP_FILE, "r", encoding="utf-8-sig") as f:
        sop_data = json.load(f)
    
    print(f"共找到 {len(sop_data)} 筆 SOP 資料")
    
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }
    
    # Upload each record
    success_count = 0
    failed_count = 0
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for sop in sop_data:
            # Map SOP fields to Ragic field IDs
            record_data = {}
            
            for sop_key, ragic_field_id in field_mapping.items():
                if sop_key in sop:
                    value = sop[sop_key]
                    # Convert list to comma-separated string for tags
                    if isinstance(value, list):
                        value = ", ".join(value)
                    record_data[ragic_field_id] = value
            
            print(f"\n正在上傳: {sop.get('id', 'N/A')} - {sop.get('title', 'N/A')[:30]}...")
            
            try:
                response = await client.post(
                    RAGIC_FORM_URL,
                    headers=headers,
                    params={"api": ""},
                    json=record_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"  ✓ 成功建立記錄, Ragic ID: {result.get('_ragicId', 'N/A')}")
                    success_count += 1
                else:
                    print(f"  ✗ 建立失敗: {response.status_code} - {response.text}")
                    failed_count += 1
            except Exception as e:
                print(f"  ✗ 建立失敗: {e}")
                failed_count += 1
    
    print("\n" + "=" * 60)
    print(f"上傳完成! 成功: {success_count} 筆, 失敗: {failed_count} 筆")
    print("=" * 60)


async def main():
    """Main entry point."""
    # Load config
    config = ConfigLoader()
    config.load()
    
    api_key = config.get("ragic.api_key", "")
    base_url = config.get("ragic.base_url", "https://ap13.ragic.com")
    
    if not api_key:
        print("錯誤: Ragic API 未設定，請確認 .env 檔案中有設定 RAGIC_API_KEY")
        return
    
    print(f"Base URL: {base_url}")
    print(f"API Key configured: Yes")
    
    # Step 1: Get form schema to understand field structure
    schema = await get_form_schema(api_key, base_url)
    
    # Continue even if schema is empty (form might be new)
    print("\n開始上傳 SOP 資料到 Ragic...")
    
    # Field mapping based on Ragic form definition (2026/01/30)
    # Key Field: 1006067
    field_mapping = {
        "id": "1006062",
        "title": "1006063", 
        "category": "1006064",
        "tags": "1006065",
        "content": "1006066",
    }
    
    # Upload SOP records
    await upload_sop_records(api_key, base_url, field_mapping)


if __name__ == "__main__":
    asyncio.run(main())
