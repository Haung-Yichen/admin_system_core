#!/usr/bin/env python3
"""
Import SOP from Excel to Local DB and Ragic.

This script:
1. Parses the Excel file (ru fu4bp6.xlsx) with special format
2. Imports SOPs to local PostgreSQL database with vector embeddings
3. Uploads SOPs to Ragic form (https://ap13.ragic.com/HSIBAdmSys/ychn-test/12)

Run: python scripts/import_sop_from_excel.py
"""

import asyncio
import json
import re
import sys
from pathlib import Path

import httpx
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.app_context import ConfigLoader
from core.database.session import get_standalone_session

# Ragic configuration
RAGIC_FORM_URL = "https://ap13.ragic.com/HSIBAdmSys/ychn-test/12"
RAGIC_FIELD_MAPPING = {
    "id": "1006062",       # SOP_ID
    "title": "1006063",    # TITLE
    "category": "1006064", # CATEGORY
    "tags": "1006065",     # KEYWORDS
    "content": "1006066",  # CONTENT
}


def parse_sop_excel(file_path: str) -> list[dict]:
    """Parse the special format Excel file and extract SOP records."""
    df = pd.read_excel(file_path, header=None)
    
    sop_records = []
    
    for row_idx in range(len(df)):
        for col_idx in range(len(df.columns)):
            val = df.iloc[row_idx, col_idx]
            if pd.notna(val):
                text = str(val)
                record = {}
                
                # Extract id (but we'll generate our own)
                id_match = re.search(r'id:([^\s]+)', text)
                if id_match:
                    record['id'] = id_match.group(1)
                
                # Extract title
                title_match = re.search(r'title:([^c]*?)(?=category:)', text)
                if title_match:
                    record['title'] = title_match.group(1).strip()
                
                # Extract category
                cat_match = re.search(r'category:([^t]*?)(?=tags:)', text)
                if cat_match:
                    record['category'] = cat_match.group(1).strip()
                
                # Extract tags
                tags_match = re.search(r'tags:([^c]*?)(?=content:)', text)
                if tags_match:
                    record['tags'] = tags_match.group(1).strip()
                
                # Extract content
                content_match = re.search(r'content:(.*)', text, re.DOTALL)
                if content_match:
                    record['content'] = content_match.group(1).strip()
                
                if record and record.get('title'):
                    sop_records.append(record)
    
    return sop_records


async def upload_to_ragic(records: list[dict], api_key: str) -> dict:
    """Upload SOP records to Ragic."""
    print("\n" + "=" * 60)
    print("正在上傳到 Ragic...")
    print("=" * 60)
    
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }
    
    success_count = 0
    failed_count = 0
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for idx, sop in enumerate(records, 1):
            # Use generated SOP ID (format: SOP-EXL-XXX)
            sop_id = f"SOP-EXL-{idx:03d}"
            
            # Map fields to Ragic field IDs
            record_data = {
                RAGIC_FIELD_MAPPING["id"]: sop_id,
                RAGIC_FIELD_MAPPING["title"]: sop.get("title", ""),
                RAGIC_FIELD_MAPPING["category"]: sop.get("category", ""),
                RAGIC_FIELD_MAPPING["tags"]: sop.get("tags", ""),
                RAGIC_FIELD_MAPPING["content"]: sop.get("content", ""),
            }
            
            print(f"  [{idx}/{len(records)}] 上傳: {sop_id} - {sop.get('title', 'N/A')[:30]}...")
            
            try:
                response = await client.post(
                    RAGIC_FORM_URL,
                    headers=headers,
                    params={"api": ""},
                    json=record_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ragic_id = result.get("_ragicId", "N/A")
                    print(f"      ✓ 成功, Ragic ID: {ragic_id}")
                    success_count += 1
                    results.append({
                        "sop_id": sop_id,
                        "ragic_id": ragic_id,
                        "success": True
                    })
                else:
                    print(f"      ✗ 失敗: {response.status_code} - {response.text[:100]}")
                    failed_count += 1
                    results.append({
                        "sop_id": sop_id,
                        "success": False,
                        "error": response.text[:100]
                    })
            except Exception as e:
                print(f"      ✗ 錯誤: {e}")
                failed_count += 1
                results.append({
                    "sop_id": sop_id,
                    "success": False,
                    "error": str(e)
                })
    
    return {
        "success": success_count,
        "failed": failed_count,
        "results": results
    }


async def import_to_local_db(records: list[dict]) -> dict:
    """Import SOP records to local PostgreSQL database."""
    print("\n" + "=" * 60)
    print("正在寫入本地資料庫...")
    print("=" * 60)
    
    # Import here to avoid circular imports
    from modules.chatbot.services.vector_service import get_vector_service
    
    vector_service = get_vector_service()
    
    success_count = 0
    failed_count = 0
    created_count = 0
    updated_count = 0
    results = []
    
    async with get_standalone_session() as db:
        for idx, sop in enumerate(records, 1):
            sop_id = f"SOP-EXL-{idx:03d}"
            title = sop.get("title", "")
            content = sop.get("content", "")
            category = sop.get("category")
            tags_str = sop.get("tags", "")
            tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else None
            
            print(f"  [{idx}/{len(records)}] 寫入: {sop_id} - {title[:30]}...")
            
            try:
                upsert_result = await vector_service.upsert_document(
                    db=db,
                    ragic_record_id=sop_id,
                    title=title,
                    content=content,
                    category=category,
                    tags=tags,
                    is_published=True,
                )
                
                action = "創建" if upsert_result.created else "更新"
                print(f"      ✓ {action}成功 (ID: {upsert_result.document.id})")
                
                success_count += 1
                if upsert_result.created:
                    created_count += 1
                else:
                    updated_count += 1
                    
                results.append({
                    "sop_id": sop_id,
                    "db_id": str(upsert_result.document.id),
                    "action": upsert_result.action,
                    "success": True
                })
                
            except Exception as e:
                print(f"      ✗ 失敗: {e}")
                failed_count += 1
                results.append({
                    "sop_id": sop_id,
                    "success": False,
                    "error": str(e)
                })
        
        await db.commit()
    
    return {
        "success": success_count,
        "failed": failed_count,
        "created": created_count,
        "updated": updated_count,
        "results": results
    }


async def main():
    """Main entry point."""
    print("=" * 60)
    print("SOP Excel 匯入工具")
    print("=" * 60)
    
    # Load config
    config = ConfigLoader()
    config.load()
    
    api_key = config.get("ragic.api_key", "")
    if not api_key:
        print("⚠️ 警告: Ragic API Key 未設定，將跳過 Ragic 上傳")
    
    # Parse Excel file
    excel_path = Path(__file__).parent.parent / "ru fu4bp6.xlsx"
    if not excel_path.exists():
        print(f"❌ 錯誤: 找不到 Excel 檔案: {excel_path}")
        return
    
    print(f"\n📂 讀取 Excel 檔案: {excel_path.name}")
    records = parse_sop_excel(str(excel_path))
    print(f"   找到 {len(records)} 筆 SOP 記錄")
    
    # Save parsed JSON for reference
    json_output = Path(__file__).parent.parent / "modules" / "chatbot" / "data" / "sop_from_excel.json"
    json_output.parent.mkdir(parents=True, exist_ok=True)
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"   已儲存 JSON: {json_output}")
    
    # Step 1: Import to local DB
    db_result = await import_to_local_db(records)
    
    print("\n" + "-" * 60)
    print("本地資料庫匯入結果:")
    print(f"  ✓ 成功: {db_result['success']} 筆")
    print(f"    - 新增: {db_result['created']} 筆")
    print(f"    - 更新: {db_result['updated']} 筆")
    print(f"  ✗ 失敗: {db_result['failed']} 筆")
    
    # Step 2: Upload to Ragic
    if api_key:
        ragic_result = await upload_to_ragic(records, api_key)
        
        print("\n" + "-" * 60)
        print("Ragic 上傳結果:")
        print(f"  ✓ 成功: {ragic_result['success']} 筆")
        print(f"  ✗ 失敗: {ragic_result['failed']} 筆")
    else:
        print("\n⚠️ 跳過 Ragic 上傳 (API Key 未設定)")
    
    print("\n" + "=" * 60)
    print("匯入完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
