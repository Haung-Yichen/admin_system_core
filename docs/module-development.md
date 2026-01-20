# 模組開發指南 (Module Development Guide)

本文檔說明如何在 Admin System Core 框架上開發業務模組。

## 前置準備

開發前請先閱讀 [框架總覽 (Framework Overview)](framework.md) 以了解系統架構。

---

## 開發規範

### 1. 核心開發哲學

*   **框架負責基礎建設，模組負責業務邏輯**
    *   **Core**: DB 連線、安全性、Config、Log。
    *   **Module**: Chatbot 邏輯、訂單處理、使用者管理。

*   **不要重複造輪子**
    *   若需通用功能 (如 Redis, Email)，請使用框架提供的服務，或請求核心團隊支援。

*   **依賴注入 (Dependency Injection)**
    *   多加利用 FastAPI 的 `Depends` 與框架提供的 Service Provider。

### 2. 目錄結構

標準模組結構如下 (以 `chatbot` 為例)：

```
modules/chatbot/
├── __init__.py             # 匯出模組類別
├── chatbot_module.py       # 實作 IAppModule (模組入口)
├── core/
│   └── config.py           # 模組專屬設定 (SOP_BOT_*)
├── routers/
│   ├── __init__.py         # Router 聚合
│   └── bot.py              # API Endpoints
├── services/               # 業務邏輯 Service
├── models/                 # SQLAlchemy Models
└── schemas/                # Pydantic Schemas
```

---

## 使用框架服務 (Using Framework Services)

### 1. 資料庫 (Database)

框架已全面接管資料庫連線。**禁止** 模組自行建立 Engine。

#### 一般 API 開發 (FastAPI Dependency)
```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database.session import get_db_session

@router.get("/items")
async def get_items(db: AsyncSession = Depends(get_db_session)):
    # db 會在 request 結束後自動 commit/close
    result = await db.execute(...)
    return result.all()
```

#### 背景任務開發 (Background Tasks)
若在獨立 Thread 或背景任務中，請使用 `get_thread_local_session`：

```python
from core.database.session import get_thread_local_session

async def background_job():
    # 建立專屬 Session，避免跨 Thread 問題
    async with get_thread_local_session() as session:
        await session.execute(...)
```

### 2. 資料安全性 (Data Security)

對於敏感個資 (Email, 手機, ID)，**必須** 使用框架提供的加密欄位。

```python
from sqlalchemy.orm import Mapped, mapped_column
from core.database.base import Base
from core.security import EncryptedType

> [!TIP]
> 系統已內建 `User` 模型 (`core.models.User`) 處理員工身份與 LINE 綁定。除非您需要建立額外的會員或客戶資料，否則無需自行建立使用者表。

```python
from sqlalchemy.orm import Mapped, mapped_column
from core.database.base import Base
from core.security import EncryptedType

# 範例：建立一個包含敏感資料的客戶表
class Customer(Base):
    __tablename__ = "customers"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # 自動加密儲存，讀取時自動解密
    email: Mapped[str] = mapped_column(EncryptedType(512), nullable=False)
    phone: Mapped[str] = mapped_column(EncryptedType(256), nullable=True)
```
```

### 3. 設定管理 (Configuration)

模組應定義專屬的 `Settings` 類別，並使用前綴隔離環境變數。

```python
# modules/chatbot/core/config.py
from pydantic_settings import BaseSettings
from pydantic import Field

class ChatbotSettings(BaseSettings):
    # 對應環境變數 SOP_BOT_APP_NAME
    app_name: str = Field(validation_alias="SOP_BOT_APP_NAME") 
```

### 4. 模組入口 (Module Entry)

實作 `IAppModule` 以整合進系統：

```python
# modules/chatbot/chatbot_module.py
from core.interface import IAppModule
from core.app_context import AppContext

class ChatbotModule(IAppModule):
    def on_entry(self, context: AppContext):
        # 取得全域服務
        self.config = context.config
        
        # 啟動初始化邏輯...
        context.log_event("Chatbot module loaded", "INFO")
```

---

## 常見問題 (FAQ)

**Q: 如何新增資料庫 Table？**
A: 在模組的 `models/` 目錄定義 SQLAlchemy Model。目前需手動處理 Migration。

**Q: 背景任務報錯 `Task attached to a different loop`？**
A: 這是因為在不同 Thread 共用 Session。請確保背景任務使用 `get_thread_local_session()`。

**Q: 我需要 Redis 怎麼辦？**
A: 目前框架尚未內建 Redis。若有強烈需求，請聯繫架構組評估加入 `core.services`。
