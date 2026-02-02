# Ragic 整合層 (Unified Ragic Integration)

Admin System Core 提供了一套統一的、型別安全的 Ragic 整合層，位於 `core/ragic`。
旨在解決舊版 `RagicService` 充斥大量字串鍵值 (String Keys) 導致的維護困難與型別不安全問題。

---

## 整合策略選擇 (Strategy Selection)

Admin System Core 支援兩種與 Ragic 互動的模式，請依據業務場景選擇：

| 特性 | Repository Pattern (即時存取) | Sync Pattern (本地快取) |
| :--- | :--- | :--- |
| **適用情境** | 寫入資料、即時性要求高、單筆查詢 | 讀取頻率高、需要關聯查詢 (Join)、報表統計 |
| **資料來源** | 直接呼叫 Ragic API | 本地 PostgreSQL 資料庫 |
| **延遲** | 較高 (HTTP RTT) | 極低 (Local DB Query) |
| **實作位置** | Core Framework (`core/ragic`) | Core (`core/services/user_sync.py`) 或 Module (`modules/...`) |
| **範例** | 提交請假單、寫入打卡紀錄 | 員工名單 (Core 管理)、部門組織樹、假別清單 (Module 管理) |

---

## 模式一：Repository Pattern (即時存取)

整合層採用 **Repository Pattern** 設計，將資料存取與業務邏輯分離：

1.  **RagicModel**: 定義資料結構與欄位映射。
2.  **RagicRepository**: 提供高階 CRUD 操作與查詢。
3.  **RagicService**: 底層 HTTP Client，處理連線與錯誤重試。

---

## 使用指南

### 1. 定義模型 (Define Model)

繼承 `RagicModel` 並使用 `RagicField` 定義欄位映射。

```python
from core.ragic import RagicModel, RagicField
from core.ragic.registry import get_ragic_registry
from datetime import date

class LeaveRequest(RagicModel):
    # 使用 registry 取得表單路徑
    _sheet_path = get_ragic_registry().get_sheet_path("leave_form")
    
    # 使用 registry 取得欄位 ID
    employee_id: str = RagicField(
        get_ragic_registry().get_field_id("leave_form", "EMPLOYEE_ID"), 
        "員工編號"
    )
    leave_type: str = RagicField(
        get_ragic_registry().get_field_id("leave_form", "LEAVE_TYPE"), 
        "假別"
    )
    # ...
```

### 2. 使用 Repository (Using Repository)

Repository 提供如同 ORM 一般的操作體驗。

```python
from core.ragic import RagicRepository

async def manage_leave_requests():
    # 自動注入 Singleton RagicService
    repo = RagicRepository(LeaveRequest)
    
    # 1. 查詢所有資料
    all_requests = await repo.find_all()
    
    # 2. 條件查詢 (精確比對)
    my_requests = await repo.find_by(employee_id="EMP001")
    
    # 3. 新增資料
    new_request = LeaveRequest(
        employee_id="EMP001",
        leave_type="Annual",
        days=3,
        start_date=date(2023, 10, 1)
    )
    # save() 會自動判斷是 Create 或 Update (基於 _ragicId)
    saved_req = await repo.save(new_request)
    print(f"Created request ID: {saved_req.ragic_id}")
    
    # 4. 刪除資料
    await repo.delete(saved_req)
```

### 3. 底層服務 (Low-level Service)

若需執行特殊 API 呼叫，可直接使用 `RagicService`。

```python
from core.ragic import get_ragic_service

service = get_ragic_service()
data = await service.get_records_by_url(
    "/HSIBAdmSys/forms/3",
    params={"naming": "EID"}  # 強制使用 Field ID 作為 Key
)
```

---

## 模式二：Sync Pattern (本地快取)

適用於基礎資料庫 (Master Data) 的維護，如員工資料、產品清單。
此模式由具體業務模組 (Module) 實作，例如 `modules/administrative/services/ragic_sync.py`。

### 實作流程 (Implementation Workflow)

若需新增一個同步表單（例如「加班單快取」），請遵循以下標準流程：

#### 1. 定義資料庫模型 (Database Model)
在模組的 models 資料夾 (如 `modules/administrative/models/overtime.py`) 建立 SQLAlchemy 模型。

```python
class OvertimeRecord(Base):
    __tablename__ = "administrative_overtime_records"
    ragic_id = Column(Integer, primary_key=True)  # 使用 Ragic ID 作為 PK
    employee_id = Column(String, index=True)
    hours = Column(Float)
```

#### 2. 定義資料驗證 (Schema Validation)
在 Sync Service 中定義 Pydantic Schema 以處理資料清洗與轉型。

```python
class OvertimeSchema(BaseModel):
    ragic_id: int
    employee_id: str
    hours: float
    
    @field_validator("hours", mode="before")
    def parse_hours(cls, v):
        return float(v) if v else 0.0
```

#### 3. 實作同步邏輯 (Implement Sync Logic)
繼承 `BaseRagicSyncService`，實作 Fetch -> Validate -> Upsert 流程。
使用 `INSERT ... ON CONFLICT DO UPDATE` 語法確保 **Idempotency (冪等性)**。

```python
from core.ragic.sync_base import BaseRagicSyncService

class OvertimeSyncService(BaseRagicSyncService[OvertimeRecord]):
    async def sync_all_data(self) -> SyncResult:
        # 2. Transform and upsert to DB
        # Implementation details...
        pass

#### 4. 註冊服務 (Register Service)
在模組的 `on_entry` 中向 `SyncManager` 註冊：

```python
from core.ragic import get_sync_manager

# ... inside Module.on_entry ...
get_sync_manager().register(
    key="overtime_records",
    service=OvertimeSyncService(),
    module_name="administrative"
)
```
```

---

## 最佳實踐

### 1. 避免硬編碼 Field ID (Use ragic_registry.json)

Admin System Core 採用 **`ragic_registry.json`** 作為欄位 ID 與表單設定的 Single Source of Truth。
建議透過 `core.ragic.registry` 取得欄位設定，而非在程式碼中硬編碼。

```python
from core.ragic.registry import get_ragic_registry

def get_employee_email_field():
    registry = get_ragic_registry()
    return registry.get_field_id("account_form", "EMAILS")  # 回傳 "1005977"
```

### 2. 資料一致性與唯讀原則
Sync Pattern 採用 **Eventual Consistency (最終一致性)**。
本地資料庫僅作為 Ragic 的 Read-Replica，**嚴禁** 直接修改本地快取表中的資料，所有寫入必須回到 Ragic (透過 Repository Pattern)。

參考實作：`modules/administrative/services/ragic_sync.py`。

### 3. Schema 驗證

`RagicRepository` 會在背後自動處理型別轉換。若 Ragic 回傳的資料格式不符 (例如預期 int 卻收到字串 "ABC")，可能會拋出 `ValidationError`。
建議在 sync service 中加入錯誤處理機制。
