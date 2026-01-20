
import sys
import os
import asyncio
import logging
import numpy as np
from sentence_transformers import SentenceTransformer

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# Mock config to avoid loading full app context
from unittest.mock import MagicMock, patch

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def reproduce():
    print("Loading model...")
    # Use the same model as in VectorService
    model_name = "paraphrase-multilingual-MiniLM-L12-v2"
    model = SentenceTransformer(model_name)
    
    target_sop_content = "【首次綁定】\n1. 手機下載「Google Authenticator」APP。\n2. 嚴禁使用相機或 Line 掃描，必須使用 Google Authenticator 內的「掃描 QR 圖碼」功能。\n3. 掃描螢幕上的條碼，輸入產生的 6 位數驗證碼完成綁定。\n\n【日常登入】\n1. 登入時開啟手機 APP 查看 6 位數驗證碼。\n2. 於網頁輸入驗證碼即可登入。\n\n※注意：手機需開啟「自動偵測日期與時間」以免驗證碼失效。"
    target_sop_title = "創時保經平台-登入驗證(2FA)綁定與操作"
    target_text = f"{target_sop_title}\n\n{target_sop_content}"
    
    query_normal = "怎麼綁定創時登入驗證"
    query_repeated = query_normal * 20
    
    print("\nGenerating embeddings...")
    emb_target = model.encode(target_text)
    emb_normal = model.encode(query_normal)
    emb_repeated = model.encode(query_repeated)
    
    sim_normal = cosine_similarity(emb_target, emb_normal)
    sim_repeated = cosine_similarity(emb_target, emb_repeated)
    
    print(f"\nTarget SOP: {target_sop_title}")
    print(f"Query Normal: '{query_normal}'")
    print(f"Similarity Normal: {sim_normal:.4f}")
    
    print(f"\nQuery Repeated (20x): '{query_normal}...'")
    print(f"Similarity Repeated: {sim_repeated:.4f}")
    
    diff = sim_normal - sim_repeated
    print(f"\nDifference: {diff:.4f}")
    
    if diff > 0.1:
        print("\n[CONFIRMED] Repetition significantly degrades similarity score.")
    else:
        print("\n[UNCLEAR] Repetition effect is small.")

if __name__ == "__main__":
    reproduce()
