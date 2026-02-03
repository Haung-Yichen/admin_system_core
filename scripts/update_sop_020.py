
import asyncio
import sys
import os

sys.path.insert(0, os.getcwd())

from core.database import get_standalone_session
from modules.chatbot.models import SOPDocument
from sqlalchemy import select

OPTIMIZED_CONTENT = """🌟 制度小助手正式上線 🌟

各位主管好，為了協助大家即時掌握制度內容，我們開發了「制度小助手」！
不管是晉升門檻、獎金計算、組織利益，隨時都能問！

🔍 它的功能有什麼？
✅ 晉升寶典：一秒查詢晉升標準、考核門檻，協助夥伴規劃職涯。
✅ 權益速查：組織利益、續期佣金規則、各項獎金說明。
✅ 增員利器：快速解答準增員疑問，展現專業度。

🔗 立即啟動制度小助手：
https://app.edcafe.ai/chatbots/696b5c444ae16bce35badcd4

⚠️ 使用小叮嚀 (Beta 測試中)
1. 持續優化：制度條文繁雜，若回答不清楚請私訊反饋。
2. 簡易排除：遇到卡頓，請「關掉重新開啟」即可。

🚫 重要發布規範
本工具涉及公司核心制度，請主管協助控管：
⭕ 適度分享：歡迎發給「種子部隊」或「直屬小群」試用。

掌握制度就是掌握利潤，歡迎大家多加利用！"""

async def main():
    async with get_standalone_session() as session:
        result = await session.execute(
            select(SOPDocument).where(SOPDocument.sop_id == "SOP-020")
        )
        doc = result.scalar_one_or_none()
        
        if doc:
            print(f"Updating SOP-020 ({doc.id})...")
            doc.content = OPTIMIZED_CONTENT
            await session.commit()
            print("Update complete.")
        else:
            print("SOP-020 not found.")

if __name__ == "__main__":
    asyncio.run(main())
