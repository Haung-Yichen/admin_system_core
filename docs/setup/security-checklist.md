# 🔒 Cloudflare 公網部署安全檢查清單

## ✅ 已完成的安全強化

### 1. CORS 配置 (core/server.py)
- [x] 限制 `allow_origins` 只允許 BASE_URL
- [x] 限制 `allow_methods` 為必要的 HTTP 方法
- [x] 限制 `allow_headers` 為必要的標頭

### 2. HTTP 安全標頭 (core/server.py)
- [x] X-Frame-Options: DENY (防止點擊劫持)
- [x] X-Content-Type-Options: nosniff (防止 MIME 類型混淆)
- [x] X-XSS-Protection: 1; mode=block (XSS 過濾)
- [x] Referrer-Policy: strict-origin-when-cross-origin
- [x] Permissions-Policy: 禁用不必要的瀏覽器功能
- [x] Strict-Transport-Security (HSTS)

### 3. Debug 模式
- [x] 生產環境 APP_DEBUG=false
- [x] DEBUG_SKIP_AUTH 只在 localhost 生效

### 5. 輸入驗證
- [x] Vector 搜索 embedding 值類型驗證

---

## ⚠️ 需要手動確認的項目

### Cloudflare 設定
- [ ] 啟用 Cloudflare SSL/TLS (Full Strict 模式)
- [ ] 啟用 Cloudflare WAF (Web Application Firewall)
- [ ] 啟用 Cloudflare Bot Management 或 Browser Integrity Check
- [ ] 設定 Cloudflare Rate Limiting Rules (備份防護)
- [ ] 只允許 Cloudflare IP 連接到原始伺服器

### 環境變數安全
- [ ] 確保 .env 不會被提交到版本控制 (.gitignore 已配置)
- [ ] 定期輪換以下密鑰:
  - JWT_SECRET_KEY
  - SECURITY_KEY
  - WEBHOOK_DEFAULT_SECRET
  - LINE_CHANNEL_SECRET (各模組)
  - RAGIC_API_KEY (各模組)
  - SMTP_PASSWORD

### 資料庫安全
- [ ] 確保 PostgreSQL 不直接暴露在公網
- [ ] 使用強密碼 (目前 docker-compose 使用 postgres/postgres)
- [ ] 啟用 SSL 連接 (docker-compose 已配置)

### 監控和告警
- [ ] 設定日誌監控 (失敗登入嘗試)
- [ ] 設定異常流量告警
- [ ] 定期審查存取日誌

---

## 📋 Cloudflare Tunnel 特定建議

### 推薦的 Cloudflare 安全設定

```
# Access Policy (Cloudflare Zero Trust)
# 限制管理端點只允許特定 IP 或驗證用戶
/admin/* -> 需要 Cloudflare Access 驗證
/webhooks/* -> 允許 (但需要 HMAC 簽名)

# Rate Limiting (Cloudflare Dashboard)
# /auth/request-magic-link: 5 requests/minute per IP
# /admin/auth/login: 5 requests/minute per IP

# WAF Rules
# 啟用 Cloudflare Managed Ruleset
# 啟用 OWASP Core Ruleset
```

### 防火牆規則建議 (在原始伺服器)

```bash
# 只允許 Cloudflare IP 連接
# https://www.cloudflare.com/ips/

# 或使用 Cloudflare Tunnel (推薦)
# Tunnel 不需要開放任何入站端口
```

---

## 🚨 緊急聯絡

如果發現安全漏洞:
1. 立即在 Cloudflare Dashboard 啟用 "Under Attack Mode"
2. 檢查日誌中的異常存取
3. 如有需要，輪換所有密鑰

---

最後更新: 2026-02-03
