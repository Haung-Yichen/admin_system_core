# Admin System Core

HSIB 企業行政與 Chatbot 核心系統。採用 Modular Monolith 架構，基於 Python FastAPI 與 PostgreSQL 開發。

## 專案文檔

完整文檔位於 `docs/` 目錄：

*   [**框架總覽 (Framework Overview)**](docs/framework.md) - 了解核心架構、資料庫與安全性設計。
*   [**模組開發指南**](docs/module-development.md) - 如何開發新業務模組。
*   [**Administrative 模組**](docs/administrative-module.md) - 請假申請、LIFF、Rich Menu 相關說明。
*   [**Ragic 整合**](docs/ragic-integration.md) - 與 Ragic 資料庫的整合策略。

## 快速開始

### 1. 環境設定

複製範例設定檔並填入您的參數：

```bash
cp .env.example .env
```

### 2. 資料庫與服務啟動

使用 Docker Compose 啟動服務 (包含 PostgreSQL 與 API Server)：

```bash
docker-compose up -d --build
```

### 3. 初始化資料庫

首次執行需初始化資料庫結構：

```bash
# 進入容器
docker exec -it hsib-backend bash

# 執行 Alembic 生成與遷移 (若有使用 Alembic)
# 或執行初始化 SQL
```

*(註：具體初始化步驟請參考個別模組文件)*

## 專案結構

```
.
├── core/             # 框架核心 (DB, Security, Logging)
├── modules/          # 業務模組 (Administrative, Chatbot)
├── services/         # 通用服務
├── docs/             # 專案文檔
├── scripts/          # 維運腳本
└── docker-compose.yml
```

## 常見開發指令

*   **執行測試**: `pytest`
*   **重建容器**: `docker-compose up -d --build`
*   **查看 Log**: `docker-compose logs -f backend`
