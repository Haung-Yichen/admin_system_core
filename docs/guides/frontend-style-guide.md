# 前端樣式設計規範 (Frontend Design Guidelines)

Admin System Core 與各模組的獨立頁面（如 LIFF 表單、登入頁）採用統一的視覺設計語言。
本規範旨在確保所有使用者介面（UI）在不同模組間保持一致的體驗。

## 設計哲學 (Design Philosophy)

1.  **一致性 (Consistency)**: 所有頁面應共用相同的配色、排版與元件風格。
2.  **原生優先 (Native First)**: 使用原生 CSS Variables 與標準 HTML 結構，減少對大型 CSS 框架 (如 Tailwind) 的依賴，以利於在受限環境 (如 LIFF 瀏覽器) 中輕量化載入。
3.  **清晰的狀態回饋**: 對於載入中、錯誤、成功等狀態，提供明確且統一的視覺回饋。

## 色彩系統 (Color System)

我們使用 CSS Variables (`:root`) 定義全域色彩，所有樣式必須引用這些變數。

```css
:root {
    /* 主色調 - 專業深藍 */
    --primary: #1A1A2E;
    --primary-light: #16213E;

    /* 強調色 - LINE Green */
    --accent: #06C755;
    --accent-hover: #05B34C;

    /* 狀態色 */
    --danger: #E74C3C;
    --warning: #F39C12;
    --success: #2e7d32;

    /* 文字色 */
    --text: #333333;
    --text-light: #666666;
    --text-muted: #999999;

    /* 背景色 */
    --bg: #F5F7FA;       /* 頁面背景 - 淺灰藍 */
    --card-bg: #FFFFFF;  /* 卡片背景 - 純白 */
    --border: #E0E0E0;   /* 邊框色 */

    /* 陰影與圓角 */
    --shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
    --radius: 16px;
    --radius-sm: 8px;
}
```

## 排版 (Typography)

*   **字體**: 優先使用 `'Noto Sans TC'`, `-apple-system`, `BlinkMacSystemFont`, `sans-serif`。
*   **載入**: 需引入 Google Fonts Noto Sans TC (Weights: 400, 500, 600, 700)。

```html
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;600;700&display=swap" rel="stylesheet">
```

## 佈局結構 (Layout Structure)

標準頁面結構包含三個主要部分：

1.  **Header**: 頂部品牌識別區。
2.  **Main Content**: 中央卡片式內容區。
3.  **Footer**: 底部版權與資訊。

```html
<body>
    <header class="header">
        <img src="/static/crown.png" alt="Logo" class="header-logo">
        <h1>頁面標題</h1>
        <p>Subtitle</p>
    </header>

    <div class="main-content">
        <div class="card">
            <!-- 內容 -->
        </div>
        <div class="footer">
            連結有效期限 10 分鐘 • Admin System
        </div>
    </div>
</body>
```

### CSS 範例

```css
body {
    background: var(--bg);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

.header {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
    color: white;
    padding: 24px 20px;
    text-align: center;
}

.main-content {
    flex: 1;
    padding: 20px;
    max-width: 480px; /* 手機優先設計，限制最大寬度 */
    width: 100%;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    justify-content: center;
}

.card {
    background: var(--card-bg);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
    padding: 32px 24px;
}
```

## 元件規範 (Component Guidelines)

### 按鈕 (Buttons)

主要行動按鈕應使用 `--accent` 色。

```css
.btn-primary {
    width: 100%;
    padding: 16px;
    background: var(--accent);
    color: white;
    border: none;
    border-radius: var(--radius-sm);
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn-primary:hover {
    background: var(--accent-hover);
    transform: translateY(-1px);
}
```

### 輸入框 (Inputs)

```css
.form-input {
    width: 100%;
    padding: 14px 16px;
    border: 2px solid var(--border);
    border-radius: var(--radius-sm);
    transition: all 0.2s ease;
}

.form-input:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(6, 199, 85, 0.1);
}
```

### 狀態提示 (Alerts)

```css
.alert {
    padding: 16px;
    border-radius: var(--radius-sm);
    margin-bottom: 20px;
    display: flex;
    gap: 12px;
}

.alert-success {
    background: #e8f5e9;
    color: #2e7d32;
    border-left: 4px solid var(--accent);
}

.alert-error {
    background: #ffebee;
    color: #c62828;
    border-left: 4px solid var(--danger);
}
```

## 頁面狀態管理 (Page States)

每個頁面應至少處理以下三種狀態：

1.  **Loading**: 顯示 Spinner。
2.  **Error**: 顯示錯誤圖示與重試按鈕。
3.  **Active (Form/Content)**: 顯示主要互動內容。

使用 `.state-hidden` class (`display: none !important`) 來切換這些區塊的顯示。
