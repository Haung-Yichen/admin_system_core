# Dashboard 模組整合 SOP

本文件說明如何讓您的模組在 Admin Dashboard 上顯示狀態卡片。

## 概述

Dashboard 系統會自動收集所有已註冊模組的狀態資訊，並以卡片形式呈現。模組開發者只需實作 `get_status()` 方法，即可在 Dashboard 上顯示自訂的狀態資訊。

## 快速開始

### 1. 實作 `get_status()` 方法

在您的模組類別中覆寫 `get_status()` 方法：

```python
from core.interface import IAppModule

class MyModule(IAppModule):
    def get_status(self) -> dict:
        return {
            "status": "healthy",
            "message": "運作正常",
            "details": {
                "處理數量": "1,234",
                "最後同步": "2 分鐘前",
            },
            "subsystems": [
                {"name": "子系統 A", "status": "healthy"},
                {"name": "子系統 B", "status": "warning"},
            ]
        }
```

### 2. 回傳格式說明

| 欄位 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `status` | string | ✅ | 狀態燈號，決定卡片顏色 |
| `message` | string | ❌ | 狀態說明文字，顯示於標題下方 |
| `details` | dict | ❌ | 鍵值對，顯示於卡片中的詳細資訊 |
| `subsystems` | list | ❌ | 子系統狀態列表 |

### 3. Status 狀態值

| 值 | 顏色 | 使用情境 |
|----|------|----------|
| `healthy` | 🟢 綠色 | 一切正常運作 |
| `warning` | 🟡 黃色 | 功能正常但有潛在問題 |
| `error` | 🔴 紅色 | 嚴重錯誤需要處理 |
| `initializing` | 🔵 藍色 | 模組正在啟動中 |

## 完整範例

### Chatbot 模組範例

```python
class ChatbotModule(IAppModule):
    def get_status(self) -> dict:
        # 收集實際狀態
        sop_count = self._get_sop_count()
        model_ready = self._embedding_model is not None
        
        # 決定整體狀態
        if not model_ready:
            status = "initializing"
            message = "模型載入中..."
        elif sop_count == 0:
            status = "warning"
            message = "知識庫為空"
        else:
            status = "healthy"
            message = "知識庫已載入"
        
        return {
            "status": status,
            "message": message,
            "details": {
                "SOP 文件數": str(sop_count),
                "模型狀態": "Ready" if model_ready else "Loading",
                "LINE 用戶數": str(self._user_count),
            }
        }
```

### 行政作業模組範例（含子系統）

```python
class AdministrativeModule(IAppModule):
    def get_status(self) -> dict:
        # 檢查各子系統狀態
        leave_status = self._check_leave_system()
        expense_status = self._check_expense_system()
        
        # 若任一子系統有問題，整體狀態為 warning
        overall = "healthy"
        if leave_status != "healthy" or expense_status != "healthy":
            overall = "warning"
        
        return {
            "status": overall,
            "message": "行政系統運作中",
            "details": {
                "已同步帳號": str(self._synced_accounts),
                "最後同步": self._last_sync_time,
            },
            "subsystems": [
                {"name": "請假系統", "status": leave_status},
                {"name": "報銷系統", "status": expense_status},
            ]
        }
```

## Dashboard 顯示邏輯

### 卡片結構

```
┌─────────────────────────────────────┐
│  [圖示]                    [狀態徽章] │
│                                      │
│  模組名稱                            │
│  狀態訊息 (message)                  │
│                                      │
│  ─────────────────────────────────  │
│  details.key1: details.value1        │
│  details.key2: details.value2        │
│                                      │
│  ─────────────────────────────────  │
│  子系統 Subsystems                   │
│  🟢 子系統 A                         │
│  🟡 子系統 B                         │
│                                      │
│  [LINE Webhook] [API Router]         │
└─────────────────────────────────────┘
```

### 自動刷新

Dashboard 每 30 秒自動呼叫 `/api/system/dashboard` 端點，重新取得所有模組狀態。

## API 端點

### GET /api/system/dashboard

回傳完整的 Dashboard 資料，包含：

```json
{
  "server": {
    "running": true,
    "port": 8000,
    "host": "0.0.0.0",
    "uptime_seconds": 3600.5,
    "started_at": "2026-01-30T10:00:00Z"
  },
  "version": "1.0.0",
  "environment": "development",
  "services": [
    {
      "name": "Ragic",
      "status": "healthy",
      "message": "Connected",
      "details": {
        "Latency": "45ms",
        "Base URL": "https://ap13.ragic.com"
      }
    },
    {
      "name": "LINE Bot",
      "status": "healthy",
      "message": "Connected",
      "details": {
        "Bot Name": "My Bot",
        "Latency": "120ms"
      }
    }
  ],
  "modules": [
    {
      "name": "chatbot",
      "status": "healthy",
      "message": "知識庫已載入",
      "has_line_webhook": true,
      "has_api_router": true,
      "details": {
        "SOP 文件數": "42"
      },
      "subsystems": []
    }
  ]
}
```

## 最佳實踐

### 1. 效能考量

`get_status()` 會被定期呼叫，請避免在此方法中執行耗時操作：

```python
# ❌ 不建議：每次呼叫都查詢資料庫
def get_status(self):
    count = self.db.query("SELECT COUNT(*) FROM documents")  # 慢
    return {"status": "healthy", "details": {"count": count}}

# ✅ 建議：使用快取或背景更新的值
def get_status(self):
    return {"status": "healthy", "details": {"count": self._cached_count}}
```

### 2. 狀態準確性

確保狀態反映真實情況，不要永遠回傳 `healthy`：

```python
# ❌ 不建議：永遠健康
def get_status(self):
    return {"status": "healthy"}

# ✅ 建議：根據實際狀態判斷
def get_status(self):
    if self._last_error:
        return {"status": "error", "message": str(self._last_error)}
    if self._is_syncing:
        return {"status": "initializing", "message": "同步中..."}
    return {"status": "healthy"}
```

### 3. 有意義的 Details

選擇對管理員有用的指標：

```python
# ✅ 好的 details
"details": {
    "待處理請假": "5",
    "本月已核准": "23",
    "最後同步": "5 分鐘前",
}

# ❌ 不好的 details（過於技術或無意義）
"details": {
    "memory_usage": "45.2MB",
    "thread_count": "12",
    "initialized": "True",
}
```

## 核心服務健康檢查

除了模組狀態，Dashboard 也顯示核心服務（Ragic、LINE）的健康狀態。這些是透過 `check_connection()` 方法實作的：

### RagicService.check_connection()

- 測試 API 連線
- 驗證 API Key
- 回報延遲時間

### LineClient.check_connection()

- 呼叫 `/v2/bot/info` 端點
- 驗證 Access Token
- 取得 Bot 名稱與 ID

## 相關檔案

- [core/interface.py](../core/interface.py) - IAppModule 基礎類別定義
- [api/system.py](../api/system.py) - Dashboard API 端點
- [static/dashboard.html](../static/dashboard.html) - Dashboard 前端頁面
- [core/ragic/service.py](../core/ragic/service.py) - Ragic 健康檢查
- [services/line_client.py](../services/line_client.py) - LINE 健康檢查
