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

# generate_blind_index 接受原始字串值
email_hash = generate_blind_index("user@example.com")

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
        
        # 建立 Router (同步操作)
        # self.api_router = ...
        
        context.log_event("Chatbot module loaded", "INFO")

    async def async_startup(self):
        # 啟動背景任務 (非同步操作)
        # 例如：資料同步、建立 DB 連線池...
        await self._start_background_tasks()
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
        # 回傳: {"sub": str, "is_bound": bool, "email": str | None, ...}
        result = await auth_service.check_binding_status(id_token, db)
        
        if result["is_bound"]:
            print(f"User email: {result['email']}")
        else:
            # 尚未綁定，需引導使用者進行 Magic Link 綁定
            # result['sub'] 為穩定的 LINE User ID
            print(f"LINE sub {result['sub']} not bound yet")
```

> [!IMPORTANT]
> 模組不應自行實作認證邏輯。所有 Magic Link 相關流程由 `/auth/*` 端點處理。
> 認證使用 LINE ID Token 的 `sub` claim 作為穩定身份識別（跨 channel 一致）。

### 6. Ragic 整合 (Ragic Integration)

模組若需讀寫 Ragic 表單，請使用統一的 `core.ragic` 套件。

### 6. Ragic 整合 (Ragic Integration)

所有與 Ragic 的互動皆透過 `core.ragic` 進行，並由 `ragic_registry.json` 統一管理設定。

#### 用法 1: 使用 Repository (簡單查詢)

適用於單次讀取或寫入操作。

```python
from core.ragic import RagicRepository, RagicModel, RagicField
from core.ragic.registry import get_ragic_registry

class LeaveRequest(RagicModel):
    # 使用 registry 取得表單路徑
    _sheet_path = get_ragic_registry().get_sheet_path("leave_form")
    
    # 使用 registry 取得欄位 ID
    employee_id: str = RagicField(
        get_ragic_registry().get_field_id("leave_form", "EMPLOYEE_ID"), 
        "工號"
    )
    # ... 其他欄位

async def sync_leave_requests():
    repo = RagicRepository(LeaveRequest)
    requests = await repo.find_all()
```

#### 用法 2: 使用 Sync Services (資料同步)

適用於需要大量快取至本地 DB 的資料 (如員工表、產品表)。

```python
from core.ragic import BaseRagicSyncService, get_sync_manager

class MySyncService(BaseRagicSyncService[MyModel]):
    def __init__(self):
        super().__init__(model_class=MyModel, form_key="my_form")
        
    async def map_record_to_dict(self, record):
        # 轉換 Ragic 資料為 DB Model 字典
        return { ... }

# 在 Module 初始化時註冊
class MyModule(IAppModule):
    def on_entry(self, context):
        service = MySyncService()
        get_sync_manager().register(
            key="my_sync",
            service=service,
            module_name="my_module"
        )
```

### 7. LINE Bot 整合 (Optional)

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

#### 7.1 Follow 事件處理 (必須實作)

> [!IMPORTANT]
> 所有 LINE 模組 **必須** 處理 `follow` 事件並發送身份驗證按鈕。
> **禁止** 發送任何歡迎訊息或問候語。

當用戶加入 LINE 官方帳號時，模組應：
1. 檢查用戶是否已綁定公司帳號
2. 若未綁定：發送框架標準的驗證按鈕
3. 若已綁定：**不發送任何訊息**（靜默處理）

```python
async def handle_line_event(self, event: dict, context: AppContext) -> dict | None:
    event_type = event.get("type")
    user_id = event.get("source", {}).get("userId")
    reply_token = event.get("replyToken")
    
    if event_type == "follow":
        await self._handle_follow_event(user_id, reply_token)
        return {"status": "ok", "action": "follow"}
    
    # ... 其他事件處理

async def _handle_follow_event(self, user_id: str, reply_token: str | None) -> None:
    """
    Handle LINE follow event.
    
    Per framework guidelines:
    - MUST send verification button for unbound users
    - MUST NOT send welcome messages
    """
    if not reply_token:
        return

    from core.database.session import get_thread_local_session
    from core.line_auth import line_auth_check
    from modules.chatbot.services import get_line_service

    line_service = get_line_service()

    async with get_thread_local_session() as db:
        # app_context 應為模組名稱，用於 LIFF ID 注入
        is_auth, auth_messages = await line_auth_check(
            user_id, db, app_context="my_module"
        )

    if is_auth:
        # 已驗證：不發送任何訊息
        pass
    else:
        # 未驗證：發送驗證按鈕
        await line_service.reply(reply_token, auth_messages)
```

> [!WARNING]
> 不要發送歡迎訊息的原因：
> 1. 避免用戶被多條訊息打擾
> 2. 保持一致的 UX（所有模組行為相同）
> 3. 驗證按鈕已包含必要的引導文字

---

### 8. 前端開發 (Front-End Development)

若模組包含前端頁面（如 LIFF 表單），請遵循以下規範以確保體驗一致性：

*   **HTML 模板**: 位於模組的 `static/` 目錄下 (建議使用 `jinja2` 渲染)。
*   **樣式規範**: 為了確保視覺一致性，**必須** 遵循 [Frontend Design Guidelines](frontend-style-guide.md)。
*   **技術限制**: 避免引入過多外部相依 (如 Bootstrap/Tailwind)，請直接使用規範中定義的 CSS Variables。
*   **LIFF 整合**:
    *   頁面載入時應初始化 `liff` SDK。
    *   使用框架提供的 `/auth/login` 進行身分驗證，不要自行實作登入頁。

---

## 常見問題 (FAQ)

**Q: 如何新增資料庫 Table？**
A: 在模組的 `models/` 目錄定義 SQLAlchemy Model。目前需手動處理 Migration。

**Q: 背景任務報錯 `Task attached to a different loop`？**
A: 這是因為在不同 Thread 共用 Session。請確保背景任務使用 `get_thread_local_session()`。

**Q: 我需要 Redis 怎麼辦？**
A: 目前框架尚未內建 Redis。若有強烈需求，請聯繫架構組評估加入 `core.services`。
