# Ragic 整合層 (Unified Ragic Integration)

Admin System Core 提供了一套統一的、型別安全的 Ragic 整合層，位於 `core/ragic`。
旨在解決舊版 `RagicService` 充斥大量字串鍵值 (String Keys) 導致的維護困難與型別不安全問題。

---

## 架構設計

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
from datetime import date

class LeaveRequest(RagicModel):
    # Ragic 表單路徑 (URL path without domain)
    _sheet_path = "/HSIBAdmSys/forms/3"
    
    # 欄位定義: RagicField("RAGIC_FIELD_ID", "描述")
    employee_id: str = RagicField("1000001", "員工編號")
    leave_type: str = RagicField("1000002", "假別")
    days: int = RagicField("1000003", "天數", cast_func=int)
    start_date: date = RagicField("1000004", "開始日期")
    
    # 可選欄位
    reason: str | None = RagicField("1000005", "事由", default=None)
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

## 最佳實踐

### 1. 避免硬編碼 Field ID

建議將 Field ID 集中管理 (如 `config.py`)，或直接寫在 Model 定義中作為 Single Source of Truth。

### 2. 使用本地快取

對於頻繁存取的 master data (如員工名單、部門)，**不應** 每次都呼叫 Ragic API。
應使用 **Sync Pattern** 將資料同步至本地 PostgreSQL 資料庫。

參考實作：`modules/administrative/services/ragic_sync.py`。

### 3. Schema 驗證

`RagicRepository` 會在背後自動處理型別轉換。若 Ragic 回傳的資料格式不符 (例如預期 int 卻收到字串 "ABC")，可能會拋出 `ValidationError`。
建議在 sync service 中加入錯誤處理機制。
