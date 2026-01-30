
import asyncio
import sys
import re
import random
import time
from pathlib import Path
from sqlalchemy import select

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_standalone_session, init_database
from modules.chatbot.models import SOPDocument
from modules.chatbot.services.vector_service import VectorService

async def generate_questions_for_sop(sop) -> list[str]:
    """
    Generates 10 test questions based on SOP title and content.
    Uses simple heuristics to simulate user queries.
    """
    questions = []
    
    # 1. Direct Title Query
    questions.append(f"請問{sop.title}?")
    questions.append(f"{sop.title}的內容是什麼?")
    
    # 2. Content-based extraction (Heuristic)
    # Split content into meaningful chunks using common delimiters
    chunks = re.split(r'[，。：；、\n\r]+', sop.content)
    # Filter for chunks with reasonable length (e.g., 4-20 chars) to be "keywords" or "phrases"
    valid_chunks = [c.strip() for c in chunks if 4 < len(c.strip()) < 30]
    
    # Shuffle to get random samples
    if valid_chunks:
        # Create questions from chunks
        for chunk in valid_chunks:
            if len(questions) >= 10:
                break
            
            # Mix of templates
            templates = [
                f"如何{chunk}?",
                f"關於{chunk}的規定",
                f"{chunk}怎麼處理?",
                f"請說明{chunk}",
                f"{chunk}"
            ]
            questions.append(random.choice(templates))
            
    # 3. Fill remaining with variations
    while len(questions) < 10:
        if sop.category:
            questions.append(f"{sop.category}中的{sop.title}相關問題")
        elif sop.tags and len(sop.tags) > 0:
            tag = random.choice(sop.tags)
            questions.append(f"關於{tag}的{sop.title}")
        else:
            questions.append(f"{sop.title}細節")
            
    return questions[:10]

async def main():
    print("Initializing Database...")
    await init_database()
    
    # Initialize Vector Service
    print("Initializing Vector Service...")
    vector_service = VectorService()
    # Force load model
    vector_service._get_model()
    
    async with get_standalone_session() as session:
        # Fetch all SOPs
        result = await session.execute(select(SOPDocument).where(SOPDocument.is_published == True))
        sops = result.scalars().all()
        
        print(f"Found {len(sops)} SOP documents in knowledge base.")
        print("=" * 60)
        
        total_questions = 0
        total_hits = 0
        top1_hits = 0
        
        results_data = []

        for sop in sops:
            print(f"\nProcessing SOP: [{sop.sop_id}] {sop.title}")
            
            questions = await generate_questions_for_sop(sop)
            sop_hits = 0
            
            for q in questions:
                total_questions += 1
                
                # Perform Search
                start_time = time.time()
                search_res = await vector_service.search(q, session, top_k=3)
                duration = time.time() - start_time
                
                # Check results
                found_rank = -1
                for rank, res in enumerate(search_res.results):
                    # Check matching ID (Using database ID or metadata sop_id if mapped)
                    # We compare the database ID directly
                    if str(res.document.id) == str(sop.id):
                        found_rank = rank + 1
                        break
                
                is_hit = found_rank != -1
                is_top1 = found_rank == 1
                
                if is_hit:
                    sop_hits += 1
                    total_hits += 1
                if is_top1:
                    top1_hits += 1
                
                status_icon = "✅" if is_top1 else ("⚠️" if is_hit else "❌")
                print(f"  {status_icon} Q: {q:<40} -> Rank: {found_rank if is_hit else 'Not Found'} ({duration:.3f}s)")
            
            accuracy = (sop_hits / len(questions)) * 100
            print(f"  >> SOP Accuracy: {accuracy:.1f}% ({sop_hits}/{len(questions)})")
            
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"Total Documents: {len(sops)}")
        print(f"Total Questions: {total_questions}")
        print(f"Top-1 Accuracy:  {(top1_hits/total_questions)*100:.2f}% ({top1_hits}/{total_questions})")
        print(f"Top-3 Accuracy:  {(total_hits/total_questions)*100:.2f}% ({total_hits}/{total_questions})")
        print("=" * 60)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
