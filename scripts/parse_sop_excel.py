#!/usr/bin/env python3
"""
Parse SOP Excel file and extract SOP records.
The Excel format has key:value pairs embedded in cells.
"""

import pandas as pd
import re
import json
from pathlib import Path

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
                
                # Extract id
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


if __name__ == "__main__":
    file_path = Path(__file__).parent.parent / "ru fu4bp6.xlsx"
    
    records = parse_sop_excel(str(file_path))
    
    print(f"Total records found: {len(records)}")
    print("-" * 60)
    
    for i, rec in enumerate(records, 1):
        print(f"Record {i}:")
        print(f"  id: {rec.get('id', 'N/A')}")
        print(f"  title: {rec.get('title', 'N/A')[:50]}...")
        print(f"  category: {rec.get('category', 'N/A')}")
        print(f"  tags: {rec.get('tags', 'N/A')[:50] if rec.get('tags') else 'N/A'}...")
        content = rec.get('content', 'N/A')
        print(f"  content: {content[:100] if content else 'N/A'}...")
        print()
    
    # Save as JSON
    output_file = Path(__file__).parent.parent / "modules" / "chatbot" / "data" / "sop_from_excel.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    print(f"Saved to: {output_file}")
