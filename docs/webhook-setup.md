# 外部 Webhook 設定指南

本文件說明如何設定 Ragic 與 LINE 的 Webhook，將事件同步至 HSIB Admin System。

**系統基礎資訊**
- **對外網址 (Base URL)**: `https://api.hsib.com.tw`
- **預設 Token**: `my_super_secret_123` (請參考 .env `WEBHOOK_DEFAULT_SECRET`)

---

## 1. Ragic Webhook 設定

當 Ragic 表單資料變動時，通知系統進行同步。

### 支援的同步服務 (Sync Services)

| 表單名稱 | 功能說明 | 服務代碼 (Service Key) | Webhook URL |
| :--- | :--- | :--- | :--- |
| **使用者身份表** | LINE 綁定與員工 Email 同步 | `core_user` | `/api/webhooks/ragic?source=core_user` |
| **統一帳號表** | 員工入職、離職、資料異動 | `administrative_account` | `/api/webhooks/ragic?source=administrative_account` |
| **SOP 知識庫** | 文件更新同步向量資料庫 | `chatbot_sop` | `/api/webhooks/ragic?source=chatbot_sop` |

### 完整 URL 範例

將 `<Base URL>` 替換為 `https://api.hsib.com.tw`，並加上 Token：

```
https://api.hsib.com.tw/api/webhooks/ragic?source=core_user&token=my_super_secret_123
```

### Ragic 後台設定步驟

1. **登入 Ragic** 並進入對應的表單設計模式。
2. **開啟 Webhook 設定**：工具列 > 「表單工具」 > 「Webhook」或「API Actions」。
3. **新增 Webhook**：
   - **URL**: 填入上述對應的完整 URL。
   - **Method**: `POST`
   - **Content Type**: `application/x-www-form-urlencoded`
   - **觸發時機**: 勾選 ✅新增後、✅儲存後、✅刪除後。
4. **儲存**：完成設定。

---

## 2. LINE Webhook 設定

設定 LINE Official Account (OA) 的 Webhook，讓機器人能接收訊息。

### 支援的機器人模組

本系統支援多個 LINE Bot，透過 URL 路徑區分模組。

| Bot 名稱 | 對應模組 | Webhook URL |
| :--- | :--- | :--- |
| **SOP 查詢機器人** | `chatbot` | `https://api.hsib.com.tw/webhook/line/chatbot` |
| **行政小幫手** | `administrative` | `https://api.hsib.com.tw/webhook/line/administrative` |

### LINE Developers Console 設定步驟

1. **登入 console**: [LINE Developers](https://developers.line.biz/)
2. **選擇 Channel**: 點選對應的 Channel (例如 "HSIB SOP Bot")。
3. **Messaging API 設定**:
   - 找到 **Webhook URL** 欄位。
   - 貼上完整的 URL (需為 `https://` 開頭)。
   - 點選 **Update**。
   - **務必啟用**: 將下方的 **Use webhook** 開關打開 (變綠色)。
4. **驗證**: 點選 **Verify** 按鈕，應顯示 `Success`。

### 常見錯誤排除

- **Verify 失敗？**
  - 確認 URL 是否貼對 Channel (例如：不要把 `chatbot` 的 URL 貼到 `administrative` 的 Channel)。
  - 這會導致 Channel Secret 驗證失敗 (403 Forbidden)。
- **機器人沒反應？**
  - 檢查是否開啟 **Use webhook**。
  - 檢查 Cloudflare Tunnel logs (`docker logs hsib-cloudflared`) 是否有收到請求。

---

## 3. 手動測試方式

### 測試 Ragic Webhook (cURL)

```bash
curl -X POST "https://api.hsib.com.tw/api/webhooks/ragic?source=core_user&token=my_super_secret_123" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "_ragicId=3&action=update"
```

**預期回應**:

```json
{
  "success": true,
  "message": "Synced record 3",
  "ragic_id": 3,
  "source": "core_user"
}
```

### 檢測系統狀態

您可以透過 API 檢查所有同步服務的狀態：

```bash
curl -s https://api.hsib.com.tw/api/webhooks/ragic/status
```

---

## 4. 系統架構參考

```mermaid
graph TD
    Ragic[Ragic Database] -->|Webhook (JSON/Form)| Gateway
    Line[LINE Platform] -->|Webhook (User Event)| Gateway
    
    subgraph "HSIB Admin System (Docker)"
        Gateway[Cloudflare Tunnel] -->|Reverse Proxy| FastAPI
        
        subgraph FastAPI [FastAPI Server]
            Router{Webhook Router}
            
            Router -->|source=core_user| UserSync[User Sync Service]
            Router -->|source=chatbot| SopSync[SOP Sync Service]
            Router -->|path=/webhook/line/chatbot| ChatbotMod[Chatbot Module]
            Router -->|path=/webhook/line/admin| AdminMod[Admin Module]
        end
        
        UserSync --> DB[(PostgreSQL)]
        SopSync --> DB
    end
end
```

## 相關文檔

- [Ragic Integration Guide](./ragic-integration.md)
- [Module Development Guide](./module-development.md)
- [Framework Overview](./framework.md)
