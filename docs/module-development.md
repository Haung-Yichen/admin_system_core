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

若需對加密欄位進行**精確查詢**，使用 Blind Index：

```python
from core.security import generate_blind_index

email_hash = generate_blind_index(email)
result = await db.execute(
    select(Customer).where(Customer.email_hash == email_hash)
)
```

### 3. 設定管理 (Configuration)

模組應定義專屬的 `Settings` 類別，並使用前綴隔離環境變數。

> [!IMPORTANT]
> 所有模組的設定值 (與 Secret) 應統一存放於專案根目錄的 `.env` 檔案中，框架會由 `core/app_context.py` 統一載入。不建議模組建立獨立的 `.env` 檔案。

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

### 5. 身分驗證 (Authentication)

模組可透過框架 `AuthService` 使用 LINE ID Token (OIDC) 驗證並檢查帳號綁定狀態：

```python
from core.services import get_auth_service
from core.database.session import get_thread_local_session

async def check_user_binding(id_token: str):
    """檢查 LINE ID Token 對應的帳號是否已綁定公司信箱"""
    auth_service = get_auth_service()
    async with get_thread_local_session() as db:
        # 驗證 ID Token 並檢查綁定狀態
        result = await auth_service.check_binding_status(id_token, db)
        if result["is_bound"]:
            print(f"User email: {result['email']}")
        else:
            # 尚未綁定，需引導使用者進行 Magic Link 綁定
            print(f"LINE sub {result['sub']} not bound yet")
```

> [!IMPORTANT]
> 模組不應自行實作認證邏輯。所有 Magic Link 相關流程由 `/auth/*` 端點處理。
> 認證使用 LINE ID Token 的 `sub` claim 作為穩定身份識別（跨 channel 一致）。

### 6. LINE Bot 整合 (Optional)

若模組需處理 LINE Webhook，需實作兩個方法：

```python
class MyModule(IAppModule):
    def get_line_bot_config(self) -> dict | None:
        """回傳 LINE channel credentials"""
        return {
            "channel_secret": "...",
            "channel_access_token": "..."
        }
    
    async def handle_line_event(self, event: dict, context: AppContext) -> dict | None:
        """處理單一 LINE 事件 (已通過簽章驗證)"""
        event_type = event.get("type")
        # ... 處理邏輯
        return {"status": "ok"}
```

框架會自動：
- 驗證 Webhook 簽章
- 將事件分派至對應模組

---

## 常見問題 (FAQ)

**Q: 如何新增資料庫 Table？**
A: 在模組的 `models/` 目錄定義 SQLAlchemy Model。目前需手動處理 Migration。

**Q: 背景任務報錯 `Task attached to a different loop`？**
A: 這是因為在不同 Thread 共用 Session。請確保背景任務使用 `get_thread_local_session()`。

**Q: 我需要 Redis 怎麼辦？**
A: 目前框架尚未內建 Redis。若有強烈需求，請聯繫架構組評估加入 `core.services`。
