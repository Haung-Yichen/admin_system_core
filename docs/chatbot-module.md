# Chatbot 模組開發文檔

本文檔說明 SOP Chatbot 模組的架構設計與開發指南。

---

## 模組概述

Chatbot 模組提供 **LINE Bot SOP 搜尋功能**，具備：

- **Magic Link 認證**：透過 Email 驗證員工身份
- **向量搜尋**：使用 MiniLM 模型進行語意相似度搜尋
- **Ragic 整合**：同步員工資料庫進行身份驗證
- **PostgreSQL + pgvector**：儲存 SOP 文件與向量索引

---

## 目錄結構

```
modules/chatbot/
├── __init__.py              # 模組入口，匯出 ChatbotModule
├── chatbot_module.py        # IAppModule 實作
├── core/
│   ├── __init__.py
│   ├── config.py            # 模組配置 (SOP_BOT_ 環境變數)
│   ├── rate_limiter.py      # API 速率限制
│   └── security.py          # JWT 簽名與驗證
├── db/
│   ├── __init__.py
│   ├── base.py              # SQLAlchemy Base 與 Mixins
│   └── session.py           # 資料庫連線管理
├── models/
│   ├── __init__.py
│   └── models.py            # ORM 模型 (User, SOPDocument, UsedToken)
├── routers/
│   ├── __init__.py          # 匯出所有 routers
│   ├── auth.py              # /auth/* 認證端點
│   ├── bot.py               # /webhook LINE Bot 端點
│   └── sop.py               # /sop/* SOP 管理端點
├── schemas/
│   ├── __init__.py
│   └── schemas.py           # Pydantic DTOs
├── services/
│   ├── __init__.py          # 匯出所有 services
│   ├── auth_service.py      # Magic Link 認證邏輯
│   ├── json_import_service.py  # JSON 匯入 SOP
│   ├── line_service.py      # LINE Messaging API
│   ├── ragic_service.py     # Ragic 員工資料查詢
│   └── vector_service.py    # 向量嵌入與搜尋
├── data/
│   └── sop_samples.json     # SOP 範例資料
└── tests/
    └── ...                  # 單元測試
```

---

## 核心類別

### ChatbotModule (模組入口)

位於 `chatbot_module.py`，實作 `IAppModule` 介面：

```python
class ChatbotModule(IAppModule):
    def get_module_name(self) -> str:
        return "chatbot"

    def on_entry(self, context: Any) -> None:
        # 初始化 API routers
        self._api_router = APIRouter()
        self._api_router.include_router(auth_router)
        self._api_router.include_router(bot_router)
        self._api_router.include_router(sop_router)

    def get_api_router(self) -> Optional[APIRouter]:
        # 回傳聚合的 router 給主應用程式
        return self._api_router
```

### 配置管理

使用 Pydantic Settings，所有環境變數使用 `SOP_BOT_` 前綴：

```python
# core/config.py
class ChatbotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # LINE Bot 憑證
    line_channel_secret: SecretStr = Field(
        validation_alias="SOP_BOT_LINE_CHANNEL_SECRET"
    )
    line_channel_access_token: SecretStr = Field(
        validation_alias="SOP_BOT_LINE_CHANNEL_ACCESS_TOKEN"
    )

    # Ragic 設定
    ragic_employee_sheet_path: str = "/HSIBAdmSys/-3/4"
    ragic_field_email: str = "1000381"

    # 向量嵌入
    embedding_dimension: int = 384  # MiniLM

    # Magic Link
    magic_link_expire_minutes: int = 15
```

---

## 資料模型

### User (使用者)

```python
class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[UUID]
    line_user_id: Mapped[str]      # LINE 使用者 ID
    email: Mapped[str]             # 已驗證的 Email
    ragic_employee_id: Mapped[str] # Ragic 員工 ID
    display_name: Mapped[str]      # LINE 顯示名稱
    is_active: Mapped[bool]
    last_login_at: Mapped[datetime]
```

### SOPDocument (SOP 文件)

```python
class SOPDocument(Base, TimestampMixin):
    __tablename__ = "sop_documents"

    id: Mapped[UUID]
    title: Mapped[str]
    content: Mapped[str]
    embedding: Mapped[Vector(384)]  # pgvector
    category: Mapped[str]
    tags: Mapped[list[str]]         # JSONB
    is_published: Mapped[bool]

    # HNSW 索引加速向量搜尋
    __table_args__ = (
        Index(
            "ix_sop_documents_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
```

### UsedToken (已使用的 Token)

防止 Magic Link Token 重複使用：

```python
class UsedToken(Base):
    __tablename__ = "used_tokens"

    token_hash: Mapped[str]  # SHA256 hash
    email: Mapped[str]
    used_at: Mapped[datetime]
    expires_at: Mapped[datetime]
```

---

## API 端點

### 認證 (`/auth`)

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/auth/magic-link` | 發送 Magic Link Email |
| GET  | `/auth/verify` | 驗證 Token 並綁定 LINE 帳號 |
| GET  | `/auth/status/{line_user_id}` | 查詢認證狀態 |

### LINE Bot (`/webhook`)

| 方法 | 路徑 | 說明 |
|------|------|------|
| POST | `/webhook/line` | LINE Webhook 接收訊息 |

### SOP 管理 (`/sop`)

| 方法 | 路徑 | 說明 |
|------|------|------|
| GET  | `/sop/search` | 向量搜尋 SOP |
| GET  | `/sop/` | 列出所有 SOP |
| POST | `/sop/` | 建立新 SOP |
| GET  | `/sop/{id}` | 取得單一 SOP |
| PUT  | `/sop/{id}` | 更新 SOP |
| DELETE | `/sop/{id}` | 刪除 SOP |
| POST | `/sop/import` | 從 JSON 匯入 SOP |

---

## Services

### AuthService

處理 Magic Link 認證流程：

```python
from modules.chatbot.services import get_auth_service

auth_service = get_auth_service()

# 發送 Magic Link
await auth_service.send_magic_link(email, line_user_id)

# 驗證 Token
user = await auth_service.verify_token(token)
```

### VectorService

向量嵌入與語意搜尋：

```python
from modules.chatbot.services import get_vector_service

vector_service = get_vector_service()

# 搜尋相似 SOP
results = await vector_service.search(
    query="如何申請出差",
    top_k=5,
    similarity_threshold=0.3
)
```

### RagicService

員工資料驗證：

```python
from modules.chatbot.services import get_ragic_service

ragic_service = get_ragic_service()

# 查詢員工 Email
employee = await ragic_service.find_by_email("user@example.com")
```

---

## 環境變數

將以下變數加入專案根目錄的 `.env`：

```bash
# LINE Bot (SOP Chatbot)
SOP_BOT_LINE_CHANNEL_SECRET=your_channel_secret
SOP_BOT_LINE_CHANNEL_ACCESS_TOKEN=your_access_token

# Ragic 整合
SOP_BOT_RAGIC_EMPLOYEE_SHEET_PATH=/HSIBAdmSys/-3/4
SOP_BOT_RAGIC_FIELD_EMAIL=1000381
SOP_BOT_RAGIC_FIELD_NAME=1000376

# 向量嵌入
SOP_BOT_EMBEDDING_DIMENSION=384

# Magic Link
SOP_BOT_MAGIC_LINK_EXPIRE_MINUTES=15

# 除錯
SOP_BOT_DEBUG=false
```

---

## 開發指南

### 新增 Service

1. 在 `services/` 建立新檔案
2. 繼承或實作所需邏輯
3. 在 `services/__init__.py` 匯出

```python
# services/new_service.py
from functools import lru_cache

class NewService:
    async def do_something(self):
        pass

@lru_cache
def get_new_service() -> NewService:
    return NewService()
```

### 新增 Router

1. 在 `routers/` 建立新檔案
2. 使用 `APIRouter()`
3. 在 `routers/__init__.py` 匯出
4. 在 `chatbot_module.py` 的 `on_entry()` 中 include

```python
# routers/new_router.py
from fastapi import APIRouter

router = APIRouter(prefix="/new", tags=["new"])

@router.get("/")
async def get_items():
    return {"items": []}
```

### 新增 Schema

在 `schemas/schemas.py` 中定義 Pydantic 模型：

```python
class NewItemCreate(BaseSchema):
    name: str
    value: int

class NewItemResponse(BaseSchema):
    id: str
    name: str
    created_at: datetime
```

---

## 測試

執行模組測試：

```bash
# 執行所有 chatbot 測試
pytest modules/chatbot/tests/ -v

# 執行特定測試
pytest modules/chatbot/tests/test_auth.py -v
```

---

## 相關文件

- [模組開發指南](./module-development.md)
- [核心介面定義](../core/interface.py)
- [主系統 API](../api/)
