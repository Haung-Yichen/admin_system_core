# 模組開發指南

本文檔說明如何在 Admin System Core 框架上開發業務模組。

---

## 快速開始

### 1. 建立模組檔案

在 `modules/` 目錄下建立新的 Python 檔案：

```
modules/
├── __init__.py
├── echo_module.py      # 範例模組
└── your_module.py      # 你的新模組
```

### 2. 實作 IAppModule 介面

```python
from typing import Optional, Dict, Any
from core.interface import IAppModule
from core.app_context import AppContext


class YourModule(IAppModule):
    """你的模組描述"""
    
    def get_module_name(self) -> str:
        """回傳模組的唯一識別名稱"""
        return "your_module"
    
    def on_entry(self, context: AppContext) -> None:
        """模組初始化時呼叫"""
        context.log_event("Your module loaded", "MODULE")
    
    def handle_event(
        self, 
        context: AppContext, 
        event: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """處理路由到此模組的事件"""
        return {"status": "ok"}
    
    def get_menu_config(self) -> Dict[str, Any]:
        """(選填) 回傳 GUI 選單配置"""
        return {
            "label": "Your Module",
            "icon": "custom_icon",
            "actions": []
        }
    
    def on_shutdown(self) -> None:
        """(選填) 模組關閉時呼叫，用於清理資源"""
        pass

    def get_status(self) -> Dict[str, Any]:
        """(選填) 回傳模組狀態供 GUI 監控顯示"""
        return {
            "status": "active", # active, warning, error, initializing
            "details": {
                "Connection": "Connected",
                "Queue Size": 0
            }
        }
```

### 3. 自動載入

將檔案放入 `modules/` 目錄後，框架會自動：

1. 掃描所有 `*.py` 檔案（排除 `_` 開頭的檔案）
2. 尋找實作 `IAppModule` 的類別
3. 實例化並註冊到 `ModuleRegistry`
4. 呼叫 `on_entry()` 進行初始化

---

## 核心概念

### AppContext (依賴注入容器)

`AppContext` 提供所有模組共用的服務：

```python
def handle_event(self, context: AppContext, event: dict):
    # 取得設定
    debug_mode = context.config.get("app.debug", False)
    
    # 記錄事件 (會顯示在 GUI 和日誌)
    context.log_event("處理事件中", "INFO")
    
    # 使用 LINE 客戶端
    line_client = context.line_client
    
    # 使用 Ragic 服務
    ragic = context.ragic_service
```

### 事件路由

事件透過兩種方式路由到模組：

#### 方式一：訊息前綴

```
"模組名稱:內容"
```

例如發送 `leave:apply` 會路由到 `leave` 模組，並設定：

```python
event = {
    "message": "leave:apply",
    "parsed_payload": "apply"  # 冒號後的內容
}
```

#### 方式二：明確指定模組

```python
event = {
    "module": "leave",
    "action": "approve",
    "data": {...}
}
```

---

## 使用內建服務

### LINE 訊息發送

```python
from utils import line_messages as msg

async def handle_event(self, context: AppContext, event: dict):
    reply_token = event.get("reply_token")
    
    if reply_token:
        # 使用工具函數建立訊息
        messages = [
            msg.text("你好！"),
            msg.confirm_template(
                alt_text="確認",
                body_text="是否確認？",
                yes_label="是", yes_data="yes",
                no_label="否", no_data="no"
            )
        ]
        
        await context.line_client.post_reply(reply_token, messages)
```

### Ragic 資料庫操作

```python
async def handle_event(self, context: AppContext, event: dict):
    ragic = context.ragic_service
    
    # 讀取記錄
    records = await ragic.get_records("forms/1", {"status": "pending"})
    
    # 建立記錄
    new_id = await ragic.create_record("forms/1", {"name": "新記錄"})
    
    # 更新記錄
    await ragic.update_record("forms/1", record_id=123, data={"status": "done"})
    
    # 刪除記錄
    await ragic.delete_record("forms/1", record_id=123)
```

---

## 完整範例：請假模組

```python
"""
Leave Module - 請假申請管理
"""
from typing import Optional, Dict, Any
from core.interface import IAppModule
from core.app_context import AppContext
from utils import line_messages as msg


class LeaveModule(IAppModule):
    """請假申請模組"""
    
    # Ragic 表單路徑
    SHEET_PATH = "forms/leave_requests"
    
    def get_module_name(self) -> str:
        return "leave"
    
    def on_entry(self, context: AppContext) -> None:
        context.log_event("請假模組已載入", "MODULE")
    
    def handle_event(
        self, 
        context: AppContext, 
        event: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        處理請假相關事件
        
        支援的指令：
        - leave:apply - 申請請假
        - leave:status - 查詢狀態
        """
        action = event.get("parsed_payload", "").strip()
        
        if action == "apply":
            return self._handle_apply(context, event)
        elif action == "status":
            return self._handle_status(context, event)
        else:
            return {"status": "error", "message": "未知指令"}
    
    def _handle_apply(self, context: AppContext, event: dict) -> dict:
        """處理請假申請"""
        context.log_event("收到請假申請", "LEAVE")
        # 實作業務邏輯...
        return {"status": "ok", "action": "apply_started"}
    
    def _handle_status(self, context: AppContext, event: dict) -> dict:
        """查詢請假狀態"""
        context.log_event("查詢請假狀態", "LEAVE")
        # 實作業務邏輯...
        return {"status": "ok", "records": []}
    
    def get_menu_config(self) -> Dict[str, Any]:
        return {
            "label": "請假管理",
            "icon": "calendar",
            "actions": [
                {"label": "申請請假", "command": "leave:apply"},
                {"label": "查詢狀態", "command": "leave:status"}
            ]
        }
```

---

## 最佳實踐

1. **模組命名**: 使用小寫英文加底線 (`leave_management`)
2. **單一職責**: 每個模組只處理一個業務領域
3. **錯誤處理**: 使用 try-except 並記錄錯誤到 `context.log_event()`
4. **非同步操作**: LINE 和 Ragic 服務使用 async/await
5. **配置管理**: 使用 `context.config.get()` 讀取設定，不要硬編碼

---

## 測試模組

### 手動測試

1. 啟動應用程式
2. 使用 API 發送測試事件：

```bash
curl -X POST http://localhost:8000/webhook/generic \
  -H "Content-Type: application/json" \
  -d '{"module": "your_module", "action": "test"}'
```

### 查看日誌

- **GUI Dashboard**: 查看 EVENT LOG 面板
- **API**: `GET http://localhost:8000/api/logs`

---

## 檔案結構建議

複雜模組可使用子目錄：

```
modules/
├── leave/
│   ├── __init__.py      # 匯出 LeaveModule
│   ├── module.py        # 主模組類別
│   ├── handlers.py      # 事件處理函數
│   └── templates.py     # LINE 訊息模板
```

在 `__init__.py` 中匯出：

```python
from .module import LeaveModule

__all__ = ["LeaveModule"]
```

---

## 相關文件

- [IAppModule 介面定義](../core/interface.py)
- [AppContext 依賴容器](../core/app_context.py)
- [LINE 訊息工具](../utils/line_messages.py)
- [Ragic 服務](../services/ragic_service.py)
