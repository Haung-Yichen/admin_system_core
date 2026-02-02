# 框架總覽 (Framework Overview)

Admin System Core 採用 **Modular Monolith (模組化單體)** 架構。

此架構的核心目標是：
1.  **分離關注點**：核心框架 (Core) 負責基礎建設，模組 (Modules) 負責業務邏輯。
2.  **統一管理**：資料庫連線、安全性、設定檔由框架統一處理，避免重複造輪子。
3.  **可插拔設計**：新增業務模組不應影響核心運作，且模組間應維持低耦合。

---

## 核心組件 (Core Components)

### 1. 應用程式上下文 (AppContext)

系統的骨幹，負責依賴注入 (Dependency Injection) 與全域服務管理。

*   **路徑**: `core/app_context.py`
*   **功能**:
    *   **設定載入 (`ConfigLoader`)**: 自動讀取與解析 `.env`。
    *   **服務實例化**: 懶加載 (Lazy Loading) 外部服務 client（如 LineClient, RagicService）。
    *   **事件日誌**: 提供簡單的內部事件紀錄。

### 2. 資料庫層 (Database Layer)

基於 SQLAlchemy 2.0+ 實作的非同步 ORM 層。

*   **路徑**: `core/database/`
*   **Engine 管理**:
    *   單例模式 (`Singleton`)：主應用程式共用一個 AsyncEngine。
    *   執行緒局域 (`Thread-Local`)：為背景執行緒提供獨立的 Engine，避免 Event Loop 衝突。
*   **Session 管理**: 提供 FastAPI Dependency (`get_db_session`) 與 Context Manager (`get_standalone_session`)。

### 3. 安全性層 (Security Layer)

企業級的安全防護機制，對開發者透明。

*   **路徑**: `core/security/`
*   **功能**:
    *   **傳輸加密**: 資料庫連線強制使用 SSL/TLS。
    *   **靜態資料加密 (Encryption At Rest)**: 
        *   使用 AES-256-GCM 演算法。
        *   透過 `EncryptedType` 在 ORM 層自動加解密。
        *   支援 `Blind Index` 機制，讓加密欄位仍可進行精確搜尋 (Exact Match)。

### 4. 核心模型 (Core Models)
*   **路徑**: `core/models/`
*   **User Model**: 系統級的使用者身份模型，包含：
    *   **Line User ID**: 用於訊息推播與身份識別。
    *   **Email**: 與 Ragic 員工表進行對應。
    *   **加密保護**: 關鍵個資 (Email, Line ID, Name) 皆自動加密。
*   **UsedToken Model**: 追蹤已使用的 Magic Link Token，防止重複使用。
*   **欄位定義 (SSOT)**: `ragic_registry.json` 作為 Ragic 欄位 ID 與表單設定的唯一真理來源，避免硬編碼。

### 5. Ragic 統一整合層 (Unified Ragic Integration)

提供標準化、型別安全的方式與 Ragic 資料庫互動。

*   **路徑**: `core/ragic/`
*   **Service**: 標準化 HTTP Client，處理重試、錯誤處理。
*   **Repository Pattern**: 封裝資料存取邏輯，提供高階 CRUD 操作。
*   **Models**: 定義 Ragic 表單結構，支援欄位映射。
*   **Registry**: 透過 `core/ragic/registry.py` 讀取 `ragic_registry.json`。

### 6. 基礎設施服務 (Infrastructure)
*   **LineClient** (`services/line_client.py`): 底層 LINE API 用戶端，負責 HTTP 通訊與簽章驗證。

---

## 核心服務 (Core Services)

框架提供以下可供模組直接調用的服務：

*   **路徑**: `core/services/` (主要業務服務)

### AuthService (`core/services/auth.py`)
負責 LINE ID Token 驗證與 Magic Link 帳號綁定。
*   `get_auth_service()`: 取得 singleton 實例
*   `verify_line_id_token(id_token)`: 驗證 LINE ID Token
*   `check_binding_status`: 檢查帳號綁定狀態（查詢本地加密 `users` 表）
*   `initiate_magic_link`: 發送登入驗證信

### AuthTokenService (`core/services/auth_token.py`)
負責 Magic Link JWT Token 的生成與驗證。
*   `create_magic_link_token`: 產生包含 email, line_sub 的短期 Token
*   `verify_magic_link_token`: 驗證 Token 合法性與過期時間

### UserSyncService (`core/services/user_sync.py`)
負責將 Ragic 的使用者資料（Email, Line ID, 姓名, 部門）同步至本地 PostgreSQL `users` 表。
*   **同步策略**: Write-Through (Ragic 為主，Webhook 更新本地)
*   **欄位映射**: Ragic 明文欄位 -> 本地加密欄位 (`core.models.User`)
*   **功能**: 確保本地認證與查詢的效能與資料一致性。

### EmailService (`core/services/email.py`)
統一的郵件發送服務，支援 SMTP 與非同步發送。
*   `send_email`: 發送 HTML 郵件
*   `send_verification_email`: 發送標準驗證信模板

### RagicService (Compatibility Layer) (`core/services/ragic.py`)
舊版服務介面，現已重構為封裝 `core/ragic` 的功能。
*   **重要變更**: 員工查詢功能已改為**查詢本地資料庫** (`administrative_accounts` 表)，而非直接呼叫 Ragic API，以提升效能與穩定性。

---

## 核心 API (Core API Endpoints)

框架自動掛載以下端點，模組**不需**自行實作：

### 1. 認證與授權 (Unified Auth)
Prefix: `/auth`
*   主要處理使用者 Magic Link 登入流程。
*   由 `core.api.auth` 提供。

### 2. 管理員認證 (Admin Auth)
Prefix: `/api/admin/auth`
*   提供 Dashboard 使用的 JWT 登入。
*   由 `api.admin_auth` 提供。

### 3. Webhook 接收
*   `/webhook/line/{module_name}`: LINE Bot Webhook (由 `core/server.py` 處理)
*   `/api/webhooks/ragic`: Ragic 資料變更 Webhook (由 `api/webhooks.py` 處理)

| 路徑                   | 方法 | 說明                            |
| ---------------------- | ---- | ------------------------------- |
| `/auth/login`          | GET  | Magic Link 登入頁面 (HTML)      |
| `/auth/request-magic-link` | POST | 發送驗證信 (Form)           |
| `/auth/verify`         | GET  | 驗證 Token 並綁定帳號           |
| `/auth/magic-link`     | POST | 發送驗證信 (JSON API)           |
| `/auth/api/verify`     | POST | 驗證 Token (JSON API)           |
| `/auth/stats`          | GET  | 使用者統計                      |

### 系統狀態 (System)
Prefix: `/api`

| 路徑                   | 方法 | 說明                            |
| ---------------------- | ---- | ------------------------------- |
| `/api/status`          | GET  | 系統狀態與已載入模組列表        |
| `/api/health`          | GET  | 健康檢查用                      |

---

## 模組化設計 (Modular Design)

### 模組生命週期 (Module Lifecycle)

所有業務模組皆位於 `modules/` 目錄下，並實作 `IAppModule` 介面。

1.  **Discovery**: 系統啟動時掃描 `modules/` 目錄。
2.  **Registration**: 註冊模組並建立實例。
3.  **Initialization (`on_entry`)**: 注入 `AppContext`，模組可在此時啟動背景任務或建立連線。
4.  **Routing**: 框架自動將模組的 `APIRouter` 掛載至主應用程式。

### 模組隔離原則

*   **獨立設定**: 模組應擁有自己的 `core/config.py`，並使用特定的環境變數前綴 (如 `SOP_BOT_`)。
*   **獨立模型**: 模組應自行定義 SQLAlchemy Models (`models/` 目錄)。
*   **使用框架服務**: 模組不應自行建立 DB Engine 或 Redis Client，必須請求核心提供。

### 外部資料快取規範 (External Data Caching)

當模組需要從外部資料來源 (如 Ragic) 快取資料時，**必須**遵循以下模式：

#### 啟動時自動同步 (Auto-Sync on Startup)

```
系統啟動
  ↓
Module.on_entry()
  ↓
背景執行緒啟動 sync_all_data()
  ↓
├─ _ensure_tables_exist()   ← 檢查表是否存在，不存在則自動建立
├─ sync_<data_type_1>()     ← 同步資料類型 1
├─ sync_<data_type_2>()     ← 同步資料類型 2
└─ ...
```

#### 實作要點

1.  **表自動建立**: 使用 `_ensure_tables_exist()` 方法，維護一個 `required_tables` 字典，包含所有需要的資料表。
    ```python
    required_tables = {
        Model1.__tablename__: Model1.__table__,
        Model2.__tablename__: Model2.__table__,
    }
    ```

2.  **Upsert 策略**: 使用 PostgreSQL `ON CONFLICT DO UPDATE` 確保資料可重複同步而不會產生重複。

3.  **新增資料表流程**:
    1. 建立 Model (`models/<new_form>.py`)
    2. 在 `models/__init__.py` 中匯出
    3. 在 `_ensure_tables_exist()` 的 `required_tables` 中加入
    4. 實作 `sync_<new_form>()` 方法
    5. 在 `sync_all_data()` 中呼叫

4.  **背景執行緒**: 資料同步應在背景執行緒執行，使用獨立的 Event Loop，避免阻塞主應用程式啟動。

---
