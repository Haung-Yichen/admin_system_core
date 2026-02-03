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

### 4. 身份驗證與授權 (Authentication & Identity)

採用 **Framework-First Authentication** 設計，統一全系統的登入與註冊流程。

*   **原則**: 所有模組 (Administrative, Chatbot 等) 共用同一套認證機制，模組不需各自實作登入頁面。
*   **介面層 (UI Layer)**:
    *   **模板路徑**: `core/static/auth/`
    *   **技術**: 原生 HTML5/TailwindCSS 模板，由後端直接渲染。
    *   **頁面**:
        *   `login.html`: 輸入 Email 請求 Magic Link。
        *   `verify.html`: 接收 Magic Link Token 並自動驗證。
        *   `success.html`: 驗證成功頁面。
        *   `error.html`: 錯誤處理頁面。
*   **流程 (Flow)**:
    1.  **未驗證攔截**: 當使用者觸發需授權功能時，模組拋出 `AccountNotBoundResponse`。
    2.  **引導登入**: Line Client 顯示 "身份驗證" 卡片，引導至 `/auth/login?line_sub={ID}&app={APP}`。
    3.  **動態 LIFF 注入**: 根據 URL 的 `app` 參數，自動注入對應的 LIFF ID，確保 `liff.closeWindow()` 能正常運作。
    4.  **Magic Link**: 使用者輸入 Email，系統比對 `ragic_registry` 與 DB。
    5.  **自動註冊**: 若 Email 存在於 Ragic 員工表但未在本地註冊，系統將自動完成註冊並綁定。

### 5. 核心模型 (Core Models)
*   **路徑**: `core/models/`
*   **User Model**: 系統級的使用者身份模型，包含：
    *   **Line User ID**: 用於訊息推播與身份識別。
    *   **Email**: 與 Ragic 員工表進行對應。
    *   **加密保護**: 關鍵個資 (Email, Line ID, Name) 皆自動加密。
*   **UsedToken Model**: 追蹤已使用的 Magic Link Token，防止重複使用。
*   **欄位定義 (SSOT)**: `ragic_registry.json` 作為 Ragic 欄位 ID 與表單設定的唯一真理來源，避免硬編碼。

### 6. Ragic 統一整合層 (Unified Ragic Integration)

提供標準化、型別安全的方式與 Ragic 資料庫互動。

*   **路徑**: `core/ragic/`
*   **Centralized Configuration (RagicRegistry)**: 
    *   **SSOT**: `ragic_registry.json` 為唯一真理來源。
    *   **功能**: 集中管理所有表單路徑與欄位 ID，支援熱重載 (Hot Reload)。
    *   **Registry**: `core/ragic/registry.py` 提供單例存取點。
*   **Sync Manager**:
    *   **功能**: 統一管理所有資料同步任務，支援依賴順序與啟動時自動同步。
    *   **註冊**: 透過 `core/ragic.get_sync_manager()` 進行服務註冊。
*   **Data Access Patterns**:
    *   **Repository Pattern**: 用於即時 CRUD 操作 (`RagicRepository`)。
    *   **Sync Pattern**: 用於將 Ragic 資料快取至本地資料庫 (`BaseRagicSyncService`)。

### 7. 基礎設施服務 (Infrastructure)
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

### SyncManager (`core/ragic/sync_base.py`)
負責協調與管理全系統的資料同步任務。
*   `register()`: 註冊同步服務。
*   `sync_all()`: 觸發所有已註冊服務的同步 (支援依賴排序)。
*   `get_status()`: 取得目前所有同步任務的狀態。

---

## 核心 API (Core API Endpoints)

框架自動掛載以下端點，模組**不需**自行實作：

### 1. 認證與授權 (Unified Auth)
Prefix: `/auth`
*   **Framework-First Design**: 核心統一處理所有模組的認證需求。
*   主要處理使用者 Magic Link 登入流程與 LIFF 整合。
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
| `/auth/request-magic-link` | POST | 發送驗證信 (Form Submit)         |
| `/auth/verify`         | GET  | 驗證 Token 並綁定帳號 (HTML)    |
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
3.  **Initialization (`on_entry`)**: 注入 `AppContext`，模組可在此時進行同步初始化 (如建立 Router)。
4.  **Async Startup (`async_startup`)**: 在 Event Loop 啟動後執行，用於啟動背景任務 (如資料同步、Rich Menu 設定)。
5.  **Routing**: 框架自動將模組的 `APIRouter` 掛載至主應用程式。

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
