# Ragic Webhook 設定指南

## 使用者身份表 (User Identity) Webhook 設定

### Webhook URL

```
https://unministrative-consolitorily-linsey.ngrok-free.dev/api/webhooks/ragic?source=core_user
```

### 完整設定（含認證）

```
https://unministrative-consolitorily-linsey.ngrok-free.dev/api/webhooks/ragic?source=core_user&token=my_super_secret_123
```

---

## Ragic 後台設定步驟

1. **登入 Ragic**
   - 前往: https://ap13.ragic.com/HSIBAdmSys/ychn-test/13

2. **開啟 Webhook 設定**
   - 點選右上角「工具」按鈕
   - 選擇「表單工具」→「Webhook」或「API Actions」

3. **新增 Webhook**
   - **URL**: 貼上上方的 Webhook URL
   - **Method**: `POST`
   - **觸發時機**: 勾選
     - ✅ 新增資料時
     - ✅ 修改資料時  
     - ✅ 刪除資料時

4. **儲存設定**

---

## 已註冊的 Sync Services

| Service Key | Service Name | Webhook URL |
|-------------|--------------|-------------|
| `core_user` | User Identity (LINE Binding) | `/api/webhooks/ragic?source=core_user` |
| `administrative_account` | Employee Accounts | `/api/webhooks/ragic?source=administrative_account` |

> **Note**: `core_user` 是在系統啟動時自動註冊的核心服務

---

## Webhook 認證方式

### 方式 1: URL Token (簡單)

在 URL 後加上 `&token=<secret>`：

```
/api/webhooks/ragic?source=core_user&token=my_super_secret_123
```

### 方式 2: HMAC Signature (推薦)

Ragic 自動計算 HMAC-SHA256 簽章並放在 `X-Hub-Signature-256` header 中。
框架會自動驗證，無需額外設定。

---

## 測試 Webhook

### 方式 1: 在 Ragic 新增/修改資料

直接在 Ragic 表單中新增或修改一筆使用者記錄，系統會自動觸發 webhook。

### 方式 2: 使用 cURL 測試

```bash
curl -X POST "https://unministrative-consolitorily-linsey.ngrok-free.dev/api/webhooks/ragic?source=core_user&token=my_super_secret_123" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "_ragicId=3"
```

### 預期回應

成功時回應：
```json
{
  "success": true,
  "message": "Synced record 3",
  "ragic_id": 3,
  "source": "core_user"
}
```

---

## 系統架構

```
┌─────────────────────────────────────────────────────────┐
│                    Ragic (Master)                       │
│  - 使用者新增/修改 Email 或 LINE ID                      │
└────────────────────┬────────────────────────────────────┘
                     │
                     │ Webhook Trigger
                     ▼
┌─────────────────────────────────────────────────────────┐
│           /api/webhooks/ragic?source=core_user          │
│                 (Framework Endpoint)                    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              UserSyncService                            │
│  - 從 Ragic 讀取明文資料                                 │
│  - 重新產生 blind index hash                            │
│  - 加密後寫入本地 DB                                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│           PostgreSQL (Read-Replica/Cache)               │
│  - 加密儲存 email, line_user_id                         │
│  - 提供快速查詢能力                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 常見問題

### Q: Webhook 沒有被觸發？

**檢查清單：**
1. ✅ Ragic Webhook URL 是否正確
2. ✅ ngrok 是否正在運行
3. ✅ FastAPI server 是否正在運行
4. ✅ Webhook token 是否正確

**除錯方式：**
```bash
# 查看 server log
tail -f logs/app.log

# 手動觸發測試
curl -X POST "https://your-domain/api/webhooks/ragic?source=core_user&token=xxx" -d "_ragicId=3"
```

### Q: Webhook 回應 403 Forbidden？

**原因：** Token 驗證失敗

**解決方式：**
- 確認 `.env` 中的 `WEBHOOK_DEFAULT_SECRET` 與 URL 中的 `token` 參數一致
- 或使用 Ragic 自動簽章（不加 token 參數）

### Q: 如何查看同步狀態？

**方式 1: API Endpoint**
```bash
curl https://your-domain/api/webhooks/ragic/status
```

**方式 2: Dashboard**
前往: https://your-domain/static/dashboard.html

---

## 相關文檔

- [Ragic Integration Guide](./ragic-integration.md)
- [Module Development Guide](./module-development.md)
- [Framework Overview](./framework.md)
