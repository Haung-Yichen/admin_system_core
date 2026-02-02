# Administrative 模組開發文檔

本文檔說明行政作業系統模組的架構設計與開發指南。

---

## 模組概述

Administrative 模組提供 **LINE 行政作業功能**，包含：

- **請假申請**：透過 LIFF 網頁表單提交請假申請
- **Rich Menu 長駐選單**：六宮格選單介面
- **員工資料同步**：從 Ragic 同步員工與部門資料
- **自動路由**：根據組織架構自動路由簽核

---

## 目錄結構

```
modules/administrative/
├── __init__.py                     # 模組入口，匯出 AdministrativeModule
├── administrative_module.py        # IAppModule 實作
├── core/
│   ├── __init__.py
│   └── config.py                   # 模組配置 (ADMIN_ 環境變數)
├── messages/
│   ├── __init__.py
│   └── menu.py                     # Flex Message 模板
├── models/
│   ├── __init__.py
│   ├── account.py                  # AdministrativeAccount 模型 (含部門資訊)
│   └── leave_type.py               # LeaveType 模型 (假別清單)
├── routers/
│   ├── __init__.py                 # 匯出所有 routers
│   ├── leave.py                    # 請假 API 端點
│   └── liff.py                     # LIFF 頁面路由
├── services/
│   ├── __init__.py                 # 匯出所有 services
│   ├── account_sync.py             # AccountSyncService
│   ├── leave_type_sync.py          # LeaveTypeSyncService
│   ├── leave.py                    # LeaveService
│   ├── liff.py                     # LiffService (LIFF App 管理)
│   └── rich_menu.py                # RichMenuService
├── scripts/
│   ├── __init__.py
│   ├── setup_line.py               # LINE 設定腳本
│   ├── process_image.py            # Rich Menu 圖片處理
│   └── debug_ragic.py              # Ragic 除錯工具
├── static/
│   ├── leave_form.html             # LIFF 請假表單頁面
│   ├── rich_menu.png               # 生成的選單圖片
│   └── rich_menu_final.jpg         # 標準化後的選單圖片
└── tests/
    ├── __init__.py
    └── test_ragic_sync.py          # 整合測試
```

---

## 核心類別

### AdministrativeModule (模組入口)

位於 `administrative_module.py`，實作 `IAppModule` 介面：

```python
class AdministrativeModule(IAppModule):
    def get_module_name(self) -> str:
        return "administrative"

    async def async_startup(self) -> None:
        # 系統啟動後執行，避免阻塞主要流程
        self._start_ragic_sync()
        self._start_rich_menu_setup()

    def get_api_router(self) -> Optional[APIRouter]:
        return self._api_router
    
    def get_line_bot_config(self) -> dict[str, str]:
        # 返回獨立 LINE Channel 設定
        return {
            "channel_secret": self._settings.line_channel_secret,
            "channel_access_token": self._settings.line_channel_access_token,
        }
    
    def on_entry(self, context: AppContext) -> None:
        # 初始化 API routers
        self._api_router = APIRouter(prefix="/administrative")
        self._api_router.include_router(leave_router)
        self._api_router.include_router(liff_router)
        
        # 註冊 Sync 服務
        from modules.administrative.services import get_account_sync_service
        get_sync_manager().register(
             key="administrative_account",
             service=get_account_sync_service(),
             module_name=self.get_module_name()
        )
```

### 配置管理

使用 Pydantic Settings，所有環境變數使用 `ADMIN_` 前綴：

```python
# core/config.py
class AdminSettings(BaseSettings):
    # Ragic API
    ragic_api_key: SecretStr = Field(validation_alias="ADMIN_RAGIC_API_KEY")
    # Ragic URL 均由 ragic_registry.json 統一管理，不再透過環境變數設定
    
    # LINE Channel (獨立帳號)
    line_channel_secret: SecretStr = Field(validation_alias="ADMIN_LINE_CHANNEL_SECRET")
    line_channel_access_token: SecretStr = Field(validation_alias="ADMIN_LINE_CHANNEL_ACCESS_TOKEN")
    line_liff_id_leave: str = Field(validation_alias="ADMIN_LINE_LIFF_ID_LEAVE")
```

---

## 資料模型

### AdministrativeAccount (員工與組織快取)

```python
class AdministrativeAccount(Base, TimestampMixin):
    __tablename__ = "administrative_account"

    account_id: Mapped[str]         # Primary Identifier
    name: Mapped[str]
    emails: Mapped[str | None]      # Comma separated
    org_name: Mapped[str | None]    # 部門/組織名稱
    sales_dept: Mapped[str | None]  # 營業部
    sales_dept_manager: Mapped[str | None]
    ragic_id: Mapped[int]           # Ragic 內部記錄 ID
```

### LeaveType (假別快取)

```python
class LeaveType(Base, TimestampMixin):
    __tablename__ = "administrative_leave_type"

    leave_type_code: Mapped[str]
    leave_type_name: Mapped[str]
    deduction_multiplier: Mapped[float]
```

---

## API 端點

### 請假 (`/api/administrative/leave`)

| 方法 | 路徑            | 說明                          |
| ---- | --------------- | ----------------------------- |
| GET  | `/leave/init`   | 初始化請假表單 (取得員工資訊) |
| POST | `/leave/submit` | 提交請假申請                  |

### LIFF 頁面 (`/api/administrative/liff`)

| 方法 | 路徑               | 說明                |
| ---- | ------------------ | ------------------- |
| GET  | `/liff/leave-form` | Serve 請假表單 HTML |
| GET  | `/liff/config`     | 取得 LIFF 配置      |

---

## Services

### AccountSyncService

同步員工帳號資料從 Ragic 到本地 PostgreSQL：

```python
from modules.administrative.services import get_account_sync_service

sync_service = get_account_sync_service()
result = await sync_service.sync_all_data()
print(f"Synced {result.synced} accounts, skipped {result.skipped}")
```

### LeaveTypeSyncService

同步假別主檔資料：

```python
from modules.administrative.services import get_leave_type_sync_service

sync_service = get_leave_type_sync_service()
result = await sync_service.sync_all_data()
print(f"Synced {result.synced} leave types")
```

**特性：**
- **BaseRagicSyncService**: 繼承自 Core 的統一同步基類。
- **Batch Processing**: 分批次處理避免資料庫參數限制。
- **RagicRegistry**: 透過中央 Registry 取得欄位 ID 映射。

### RichMenuService

程式化管理 LINE Rich Menu：

```python
from modules.administrative.services import get_rich_menu_service

service = get_rich_menu_service()

# 建立選單
menu_id = await service.create_rich_menu()

# 上傳圖片
await service.upload_menu_image(menu_id, "path/to/image.jpg")

# 設為預設
await service.set_default_menu(menu_id)
```

### LiffService

程式化管理 LIFF Apps：

```python
from modules.administrative.services import get_liff_service

service = get_liff_service()
liff_id = await service.create_liff_app(
    endpoint_url="https://your-domain.com/api/administrative/liff/leave-form",
    view_type="full",
)
```

> [!NOTE]
> LIFF App 必須建立在 **LINE Login Channel** 下，而非 Messaging API Channel。

### LeaveService

請假申請業務邏輯：

```python
from modules.administrative.services import get_leave_service

service = get_leave_service()

# 取得員工資訊
employee = await service.get_employee_by_email("user@example.com", db)

# 提交請假
result = await service.submit_leave_request(request_data, db)
```

---

## 環境變數

將以下變數加入專案根目錄的 `.env`：

```bash
# =============================================================================
# Administrative 模組設定
# =============================================================================

# Ragic API Configuration
# 注意：詳細的表單 URL 與欄位 ID 對映已移至 ragic_registry.json 統一管理。
# 這裡只需設定 API Key 與同步參數。
ADMIN_RAGIC_API_KEY=your_base64_encoded_api_key

# Sync Configuration
ADMIN_SYNC_BATCH_SIZE=100
ADMIN_SYNC_TIMEOUT_SECONDS=60

# LINE Configuration (獨立 Messaging API Channel)
ADMIN_LINE_CHANNEL_SECRET=your_channel_secret
ADMIN_LINE_CHANNEL_ACCESS_TOKEN=your_access_token

# LINE LIFF Configuration (需在 LINE Login Channel 建立)
ADMIN_LINE_LIFF_ID_LEAVE=your_liff_id_from_line_developers
```

---

## LINE 設定指南

### 1. Messaging API Channel (Bot & Rich Menu)

1. 到 [LINE Developers Console](https://developers.line.biz/)
2. 建立或選擇 **Messaging API** Channel
3. 設定 Webhook URL：`https://api.hsib.com.tw/webhook/line/administrative` (或您的正式網域)
4. 取得 **Channel Secret** 和 **Channel Access Token**
5. 填入 `.env`

### 2. LINE Login Channel (LIFF)

LIFF 應用程式必須建立在 **LINE Login** Channel 下。由於無法透過 Messaging API 自動建立 LIFF，您必須**手動**在 Console 設定。

1. 在同一個 Provider 下建立 **LINE Login** Channel (或選擇現有的)。
2. 進入 **LIFF** 分頁，點選 **Add** 建立 LIFF App：
   - **LIFF App Name**: Administrative Leave Form (自訂)
   - **Size**: Full
   - **Endpoint URL**: `https://api.hsib.com.tw/api/administrative/liff/leave-form`
     > **注意**：必須使用**HTTPS**且**公開可存取**的網址。
     > 若您使用 Cloudflare Tunnel，請確保網域配置正確。
     > **切勿**填寫 `localhost` 或過期的 `ngrok` 網址。
   - **Scopes**: 勾選 `profile`, `openid`
3. 儲存後，取得 **LIFF ID** (格式如 `2008988187-xxxxxx`)。
4. 將 LIFF ID 填入 `.env` 的 `ADMIN_LINE_LIFF_ID_LEAVE`。
5. (選用) 若有修改 Endpoint URL，請務必在 LINE Developers Console 更新，LIFF 的跳轉是由 LINE 伺服器控制的，重啟容器**不會**更新此設定。

### 常見問題排除

**Q: LIFF 打開後顯示舊的網址 (如 ngrok) 或無法連線？**
A: 這通常是因為 LINE Developers Console 中的 **Endpoint URL** 尚未更新。
請登入 LINE Developers Console > LINE Login Channel > LIFF，確認 Endpoint URL 是否為最新的正式網址 (`https://api.hsib.com.tw/...`)。
LIFF 的轉導邏輯是在 LINE 端的，與本地程式碼無關。

### 3. 一鍵設定腳本

```bash
# 設定好 .env 後執行
python -m modules.administrative.scripts.setup_line
```

此腳本會自動：
- ✅ 建立 Rich Menu
- ✅ 上傳選單圖片
- ✅ 設為預設選單

---

## Email 補救機制 (Fallback Strategy)

由於 Ragic 來源資料 (`ADMIN_RAGIC_URL_EMPLOYEE`) 可能存在 Email 欄位缺失的情況，為了確保系統運作正常且不改動原始 Ragic 資料，模組實作了自動補救機制。

### 設計邏輯

1. **不改動來源**：系統僅讀取 Ragic 資料，絕不寫回或修改 Ragic 表單，確保來源資料的一致性。
2. **利用已驗證身分**：所有使用者在使用本系統前，皆需通過 LINE + Magic Link 的身分驗證流程。因此，核心框架的 `core.models.User` 表中必定存有「LINE User ID」與「驗證過的 Email」之對應關係。
3. **自動補全**：同步程式在寫入本地快取 (`AdministrativeEmployee`) 前，若發現 Ragic 資料缺少 Email，會自動從 `User` 表查找補全。

### 運作流程

1. **同步啟動**：`AccountSyncService` 開始從 Ragic 抓取員工資料。
2. **建立對照表**：同時從 `core.models.User` 表讀取所有已驗證用戶，建立 `display_name -> email` 的對照表 (`_build_name_to_email_map`)。
3. **逐筆處理**：
   - 讀取 Ragic 記錄。
   - 檢查 Email 欄位是否為空。
   - **若為空**：使用員工姓名 (`姓名` 欄位) 在對照表中查找。
     - **找到**：使用對照表中的 Email 寫入本地資料庫。
     - **未找到**：跳過此記錄並記錄 Warning log。
   - **若不為空**：直接使用 Ragic 的 Email。
4. **寫入完成**：本地資料庫 (`AdministrativeEmployee`) 獲得完整資料，即便 Ragic 來源有缺漏。

**流程圖示：**

```mermaid
graph TD
    A[開始同步] --> B[從 Ragic 抓取資料]
    A --> C[從 User 表建立 Name-Email Map]
    B --> D{Ragic 有 Email?}
    D -- Yes --> E[使用 Ragic Email]
    D -- No --> F{User 表有此姓名?}
    F -- Yes --> G[使用 User 表 Email (補救)]
    F -- No --> H[跳過記錄 (Warning)]
    E --> I[寫入本地 DB]
    G --> I
```

---

## Rich Menu 設計

**規格：**
- 尺寸：2500 x 1686 px
- 格式：JPEG (< 1MB)
- 布局：2 行 x 3 列

**按鈕配置：**

| 位置 | 圖示 | 文字     | 狀態                |
| ---- | ---- | -------- | ------------------- |
| 1,1  | 📅    | 請假申請 | ✅ Active (LIFF URI) |
| 1,2  | ⏰    | 加班申請 | 🔒 Coming Soon       |
| 1,3  | 💰    | 費用報銷 | 🔒 Coming Soon       |
| 2,1  | ✅    | 簽核進度 | 🔒 Coming Soon       |
| 2,2  | 📢    | 公告查詢 | 🔒 Coming Soon       |
| 2,3  | ⚙️    | 更多功能 | 🔒 Coming Soon       |

**生成提示詞（用於 AI 圖片生成）：**

> LINE Rich Menu design, 2500x1686px, dark navy blue (#1A1A2E), 2x3 grid.
> Row 1: Calendar (請假申請/green #06C755), Clock (加班申請/grey), Dollar (費用報銷/grey).
> Row 2: Checkmark (簽核進度/grey), Megaphone (公告查詢/grey), Gear (更多功能/grey).
> Header: "HSIB 行政作業系統". Flat design, minimalist icons, white text.

---

## 測試

### 執行整合測試

```bash
# Ragic 同步測試
python -m modules.administrative.tests.test_ragic_sync
```

### 手動測試 Ragic API

```bash
# 除錯腳本
python -m modules.administrative.scripts.debug_ragic
```

---

## 開發指南

### 新增功能按鈕

1. 更新 `messages/menu.py` 的 Flex Message
2. 更新 `services/rich_menu.py` 的按鈕區域定義
3. 建立對應的 LIFF 頁面或 API
4. 重新執行 `setup_line.py` 更新 Rich Menu

### 新增 Service

```python
# services/new_service.py
from functools import lru_cache

class NewService:
    async def do_something(self):
        pass

_service: NewService | None = None

def get_new_service() -> NewService:
    global _service
    if _service is None:
        _service = NewService()
    return _service
```

---

## 相關文件

- [模組開發指南](./module-development.md)
- [核心框架](./framework.md)
- [Chatbot 模組](./chatbot-module.md)
