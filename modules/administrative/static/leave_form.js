// leave_form.js - External JS file for LIFF Leave Request Form
// This file MUST be loaded externally to bypass CSP inline script blocks

(function () {
    'use strict';

    // Configuration
    const API_BASE_URL = window.location.origin;
    const FETCH_TIMEOUT_MS = 15000;

    // State
    let userId = null;
    let userProfile = null;
    let idToken = null;
    let lineSub = null;

    // Debug logging
    const debugLogs = [];
    const DEBUG_MODE = false;  // Set to true for debugging

    function createDebugOverlay() {
        if (document.getElementById('debug-overlay')) return;
        const overlay = document.createElement('div');
        overlay.id = 'debug-overlay';
        overlay.style.cssText = `
            position: fixed; bottom: 10px; right: 10px; width: 300px; max-height: 200px;
            background: rgba(0,0,0,0.85); color: #0f0; font-size: 11px; font-family: monospace;
            padding: 8px; border-radius: 8px; overflow-y: auto; z-index: 9999; display: ${DEBUG_MODE ? 'block' : 'none'};
        `;
        overlay.innerHTML = '<div style="margin-bottom:4px;font-weight:bold;">Debug Console <button onclick="this.parentElement.style.display=\'none\'" style="float:right;background:#333;color:#fff;border:none;padding:2px 6px;cursor:pointer;">×</button></div><div id="debug-logs"></div>';
        document.body.appendChild(overlay);
    }

    function debugLog(msg, isError = false) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = `[${timestamp}] ${msg}`;
        debugLogs.push(logEntry);
        // console.log(logEntry);

        const loadingDebug = document.getElementById('loading-debug');
        if (loadingDebug) {
            loadingDebug.textContent = msg;
        }

        const logsDiv = document.getElementById('debug-logs');
        if (logsDiv) {
            const entry = document.createElement('div');
            entry.textContent = logEntry;
            entry.style.color = isError ? '#f66' : '#0f0';
            logsDiv.appendChild(entry);
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }
    }

    // Log user agent for debugging
    debugLog('UA: ' + navigator.userAgent);

    // Make showDebugOverlay globally available
    window.showDebugOverlay = function () {
        const overlay = document.getElementById('debug-overlay');
        if (overlay) overlay.style.display = 'block';
    };

    // Fetch with timeout
    async function fetchWithTimeout(url, options = {}, timeoutMs = FETCH_TIMEOUT_MS) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
        try {
            const response = await fetch(url, { ...options, signal: controller.signal });
            clearTimeout(timeoutId);
            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            if (error.name === 'AbortError') {
                throw new Error(`請求超時 (${timeoutMs / 1000}秒)`);
            }
            throw error;
        }
    }

    /**
     * Strictly sanitize a string for use in HTTP headers.
     * For JWT tokens, only allow: A-Z, a-z, 0-9, hyphen, underscore, period, equals
     * This is the strictest possible whitelist for JWT/Base64URL.
     * @param {string} value - The value to sanitize
     * @param {boolean} isJwt - Whether this is a JWT token (stricter rules)
     * @returns {string} - Sanitized string, or empty string if invalid
     */
    function sanitizeHeaderValue(value, isJwt = false) {
        if (value === null || value === undefined) {
            return '';
        }

        try {
            // Convert to string and trim
            let str = String(value).trim();

            if (isJwt) {
                // JWT tokens ONLY allow: A-Za-z0-9-_.= (Base64URL + period for JWT segments)
                // This is the STRICTEST possible whitelist
                str = str.replace(/[^A-Za-z0-9\-_\.=]/g, '');
            } else {
                // For other headers: printable ASCII only, no whitespace
                str = str.replace(/[^\x21-\x7E]/g, '');
            }

            return str;
        } catch (e) {
            debugLog('sanitizeHeaderValue error: ' + e.message, true);
            return '';
        }
    }

    /**
     * Validate that a string is safe for HTTP header use in WebKit.
     * WebKit is extremely strict about header values.
     * @param {string} value - The value to validate
     * @returns {boolean} - True if safe
     */
    function isHeaderSafe(value) {
        if (!value || value.length === 0) return false;
        // Only allow: letters, numbers, and safe punctuation (-_,.=)
        // NO spaces, NO other special characters
        return /^[A-Za-z0-9\-_\.=]+$/.test(value);
    }

    /**
     * Safely append a header value using the Headers API.
     * Wraps in try-catch to prevent crashes on strict WebKit validation.
     * @param {Headers} headers - The Headers object
     * @param {string} name - Header name
     * @param {string} value - Header value (will be sanitized)
     * @param {boolean} isJwt - Whether this is a JWT token
     * @returns {boolean} - True if successfully appended, false otherwise
     */
    function safeAppendHeader(headers, name, value, isJwt = false) {
        try {
            const sanitized = sanitizeHeaderValue(value, isJwt);

            if (!sanitized || sanitized.length === 0) {
                debugLog(`Header "${name}" skipped: empty after sanitization`);
                return false;
            }

            // Final validation using strict whitelist
            if (!isHeaderSafe(sanitized)) {
                debugLog(`Header "${name}" skipped: failed isHeaderSafe check`);
                return false;
            }

            // Log if sanitization changed the value
            const originalLen = String(value).length;
            if (sanitized.length !== originalLen) {
                debugLog(`Header "${name}" sanitized: ${originalLen} -> ${sanitized.length} chars`);
            }

            headers.append(name, sanitized);
            debugLog(`Header "${name}" appended successfully (${sanitized.length} chars)`);
            return true;
        } catch (e) {
            // Catch DOMException or any other error from headers.append()
            debugLog(`Header "${name}" append failed: ${e.name} - ${e.message}`, true);
            return false;
        }
    }

    // Initialize LIFF
    async function initializeLiff() {
        createDebugOverlay();

        const urlParams = new URLSearchParams(window.location.search);

        // Development test mode
        if (urlParams.get('testUserId')) {
            const testUser = urlParams.get('testUserId');
            debugLog('Development mode enabled: ' + testUser);
            userId = testUser;
            userProfile = { displayName: 'Dev User' };
            idToken = 'dev_mode_token';
            document.querySelector('.loading-text').textContent = '開發模式：載入測試資料...';
            await loadUserData();
            return;
        }

        try {
            document.querySelector('.loading-text').textContent = '正在載入設定...';
            debugLog('Starting initialization...');

            // Fetch LIFF config
            let liffId = '';
            try {
                debugLog(`Fetching config from: ${API_BASE_URL}/api/administrative/liff/config`);
                const configResponse = await fetchWithTimeout(`${API_BASE_URL}/api/administrative/liff/config`);
                if (configResponse.ok) {
                    const config = await configResponse.json();
                    liffId = config.liff_id_leave;
                    debugLog('Loaded LIFF ID: ' + liffId);
                } else {
                    debugLog('Config response not OK: ' + configResponse.status, true);
                }
            } catch (e) {
                debugLog('Failed to fetch config: ' + e.message, true);
            }

            // Fallback
            if (!liffId) {
                liffId = urlParams.get('liffId') || '';
            }

            if (!liffId) {
                const isLocalhost = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
                if (isLocalhost) {
                    debugLog('No LIFF ID configured - showing setup instructions', true);
                    showError(
                        'LIFF ID 尚未設定。\n\n' +
                        '【開發測試方式】\n' +
                        '在 URL 加上 ?testUserId=test123 進入開發模式'
                    );
                } else {
                    debugLog('No LIFF ID in production environment', true);
                    showError('系統設定錯誤，請聯繫管理員（LIFF ID 未設定）');
                }
                return;
            }

            document.querySelector('.loading-text').textContent = '正在初始化 LIFF...';
            debugLog('Initializing LIFF with ID: ' + liffId);

            try {
                await liff.init({ liffId });
                debugLog('LIFF init success, isInClient: ' + liff.isInClient());
            } catch (liffError) {
                debugLog('LIFF init failed: ' + liffError.message, true);
                showError('LIFF 初始化失敗: ' + liffError.message);
                return;
            }

            const isInLineApp = liff.isInClient();
            debugLog('Is in LINE app: ' + isInLineApp);

            if (!liff.isLoggedIn()) {
                if (!isInLineApp) {
                    debugLog('Not logged in and not in LINE app', true);
                    showError('請從 LINE 應用程式開啟此頁面，或點擊下方按鈕登入');
                    const errorContainer = document.getElementById('error-container');
                    const loginBtn = document.createElement('button');
                    loginBtn.className = 'btn btn-primary';
                    loginBtn.style.marginTop = '12px';
                    loginBtn.textContent = '使用 LINE 登入';
                    loginBtn.onclick = () => liff.login();
                    errorContainer.querySelector('div').appendChild(loginBtn);
                    return;
                }
                document.querySelector('.loading-text').textContent = '正在登入...';
                debugLog('Not logged in, redirecting to login...');
                liff.login();
                return;
            }

            // Get user profile
            debugLog('Getting user profile...');
            const profile = await liff.getProfile();
            userId = profile.userId;
            userProfile = profile;
            debugLog('LIFF initialized, userId: ' + userId);

            // Get ID Token
            debugLog('Getting LINE ID Token...');
            idToken = liff.getIDToken();

            if (!idToken) {
                debugLog('ID Token is null', true);
                showError(
                    '無法取得驗證權杖。請確保您已授權 Email 存取權限。\n' +
                    '請重新登入並在登入時勾選「電子郵件」授權。'
                );
                const errorContainer = document.getElementById('error-container');
                const reloginBtn = document.createElement('button');
                reloginBtn.className = 'btn btn-primary';
                reloginBtn.style.marginTop = '12px';
                reloginBtn.textContent = '重新登入並授權';
                reloginBtn.onclick = () => {
                    liff.logout();
                    liff.login({ redirectUri: window.location.href });
                };
                errorContainer.querySelector('div').appendChild(reloginBtn);
                return;
            }

            debugLog('ID Token obtained successfully');

            document.querySelector('.loading-text').textContent = '正在載入使用者資料...';
            await loadUserData();

        } catch (error) {
            debugLog('LIFF init error: ' + error.message, true);
            showError('無法初始化 LINE 登入: ' + error.message);
        }
    }

    // Load user data from backend
    async function loadUserData() {
        try {
            debugLog('Loading user data...');

            // Use POST method with ID Token in body (to match backend endpoint)
            const targetUrl = `${API_BASE_URL}/api/administrative/leave/init`;
            debugLog('Making API request to /api/administrative/leave/init using POST');

            const requestBody = {
                line_id_token: idToken
            };

            const response = await fetchWithTimeout(
                targetUrl,
                {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(requestBody)
                }
            );

            if (!response.ok) {
                let errorDetail = `HTTP ${response.status}`;
                let errorData = null;
                try {
                    errorData = await response.json();
                    errorDetail = errorData.detail || errorDetail;
                } catch (e) {
                    // Response might not be JSON
                }

                debugLog('API Error: ' + JSON.stringify(errorDetail), true);

                // Handle 403 - Account not bound
                if (response.status === 403 && errorData && errorData.detail && errorData.detail.error === 'account_not_bound') {
                    debugLog('Account not bound, showing binding UI');
                    lineSub = errorData.detail.line_sub;
                    showBindingUI(errorData.detail.line_name);
                    return;
                }

                if (response.status === 401) {
                    let errorMsg = '身份驗證失敗。';
                    if (typeof errorDetail === 'string') {
                        if (errorDetail.includes('expired')) {
                            errorMsg = 'LINE ID Token 已過期，請重新開啟此頁面。';
                        } else {
                            errorMsg = errorDetail;
                        }
                    }
                    showError(errorMsg);
                    return;
                }

                if (response.status === 404) {
                    showError('找不到您的員工資料，請聯繫人資部門');
                    return;
                }

                throw new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
            }

            const data = await response.json();
            debugLog('User data loaded successfully');

            document.getElementById('user-name').textContent = data.name || '-';
            document.getElementById('user-email').textContent = data.email || '-';
            document.getElementById('user-sales-dept').textContent = data.sales_dept || '-';
            document.getElementById('user-sales-dept-manager').textContent = data.sales_dept_manager || '-';
            document.getElementById('user-direct-supervisor').textContent = data.direct_supervisor || '-';

            // Set default dates to tomorrow
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            const tomorrowStr = tomorrow.toISOString().split('T')[0];
            document.getElementById('start-date').value = tomorrowStr;
            document.getElementById('end-date').value = tomorrowStr;

            showForm();

        } catch (error) {
            debugLog('Load user data error: ' + error.message, true);

            // Check for DOMException or pattern-related errors (WebKit header validation)
            const errorMessage = error.message || '';
            const errorName = error.name || '';

            if (
                error instanceof DOMException ||
                errorName === 'DOMException' ||
                errorMessage.includes('pattern') ||
                errorMessage.includes('header') ||
                errorMessage.includes('Header') ||
                errorMessage.includes('SyntaxError') ||
                (error.code && error.code === 5) // DOMException.INVALID_CHARACTER_ERR
            ) {
                debugLog('Detected browser security/header format error', true);
                showError(
                    '瀏覽器安全性錯誤\n\n' +
                    '您的 LINE 應用程式版本可能需要更新。\n' +
                    '請嘗試以下步驟：\n' +
                    '1. 更新 LINE 應用程式\n' +
                    '2. 清除 LINE 的快取\n' +
                    '3. 重新開啟此頁面\n\n' +
                    '若問題持續，請聯繫系統管理員。\n' +
                    `(錯誤代碼: ${errorName || 'HEADER_FORMAT'})`
                );
            } else {
                showError(error.message);
            }
        }
    }

    // Submit form - make it globally available
    window.submitForm = async function (event) {
        event.preventDefault();

        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="width:20px;height:20px;border-width:2px;"></span><span>處理中...</span>';

        try {
            const formData = {
                start_date: document.getElementById('start-date').value,
                end_date: document.getElementById('end-date').value,
                leave_type: document.getElementById('leave-type').value,
                reason: document.getElementById('reason').value,
            };

            // Simplified: Use query parameters for auth to avoid header complexity/errors
            const params = new URLSearchParams();
            if (userId) params.append('line_user_id', userId);
            if (idToken) params.append('line_id_token', idToken);

            const targetUrl = `${API_BASE_URL}/api/administrative/leave/submit?${params.toString()}`;
            debugLog('Submitting to /api/administrative/leave/submit with query params');

            const response = await fetch(
                targetUrl,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData),
                }
            );

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Submission failed');
            }

            const result = await response.json();
            console.log('Submission result:', result);

            showSuccess();

        } catch (error) {
            console.error('Submit error:', error);
            debugLog('Submit error: ' + error.message, true);

            // Check for DOMException or pattern-related errors
            const errorMessage = error.message || '';
            const errorName = error.name || '';

            if (
                error instanceof DOMException ||
                errorName === 'DOMException' ||
                errorMessage.includes('pattern') ||
                errorMessage.includes('header') ||
                errorMessage.includes('Header') ||
                (error.code && error.code === 5)
            ) {
                alert(
                    '瀏覽器安全性錯誤\n\n' +
                    '請更新 LINE 應用程式後重試。\n' +
                    `(錯誤代碼: ${errorName || 'HEADER_FORMAT'})`
                );
            } else {
                alert('送出失敗: ' + error.message);
            }

            submitBtn.disabled = false;
            submitBtn.innerHTML = '<span>📤</span><span>送出申請</span>';
        }
    };

    // UI State functions
    function showLoading() {
        document.getElementById('loading-container').style.display = 'flex';
        document.getElementById('error-container').style.display = 'none';
        document.getElementById('binding-container').style.display = 'none';
        document.getElementById('success-container').style.display = 'none';
        document.getElementById('form-container').classList.remove('active');
        document.getElementById('submit-section').classList.add('hidden');
    }

    function showError(message) {
        document.getElementById('loading-container').style.display = 'none';
        document.getElementById('error-container').style.display = 'flex';
        document.getElementById('binding-container').style.display = 'none';

        let userMessage = message;
        if (message.includes('超時') || message.includes('timeout')) {
            userMessage = '連線逾時，請檢查網路後重試';
        } else if (message.includes('fetch') || message.includes('network')) {
            userMessage = '網路連線失敗，請稍後再試';
        }
        document.getElementById('error-message').textContent = userMessage;
        document.getElementById('success-container').style.display = 'none';
        document.getElementById('form-container').classList.remove('active');
        document.getElementById('submit-section').classList.add('hidden');
    }

    function showBindingUI(lineName) {
        document.getElementById('loading-container').style.display = 'none';
        document.getElementById('error-container').style.display = 'none';
        document.getElementById('binding-container').style.display = 'flex';
        document.getElementById('success-container').style.display = 'none';
        document.getElementById('form-container').classList.remove('active');
        document.getElementById('submit-section').classList.add('hidden');

        if (lineName) {
            document.querySelector('#binding-container .error-message').innerHTML =
                `您好 <strong>${lineName}</strong>！<br>您的 LINE 帳號尚未綁定公司信箱，<br>請輸入公司 Email 完成綁定。`;
        }
    }

    // Make sendBindingEmail globally available
    window.sendBindingEmail = async function () {
        const emailInput = document.getElementById('binding-email');
        const bindingBtn = document.getElementById('binding-btn');
        const statusEl = document.getElementById('binding-status');
        const email = emailInput.value.trim();

        if (!email) {
            alert('請輸入公司 Email');
            return;
        }

        if (!lineSub) {
            alert('無法取得 LINE 識別碼，請重新整理頁面');
            return;
        }

        bindingBtn.disabled = true;
        bindingBtn.innerHTML = '<span class="spinner" style="width:20px;height:20px;border-width:2px;"></span><span>發送中...</span>';
        statusEl.style.display = 'none';

        try {
            debugLog(`Sending binding request for email: ${email}`);

            const response = await fetchWithTimeout(
                `${API_BASE_URL}/api/auth/magic-link`,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        email: email,
                        line_sub: lineSub
                    })
                }
            );

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || error.message || '發送失敗');
            }

            const result = await response.json();
            debugLog('Binding email sent successfully');

            statusEl.style.display = 'block';
            statusEl.style.color = 'var(--accent)';
            statusEl.innerHTML = `✅ 驗證信已發送至 <strong>${email}</strong><br>請查收並點擊信中的連結完成綁定。<br>綁定完成後請重新開啟此頁面。`;

            bindingBtn.innerHTML = '<span>✅</span><span>已發送</span>';

        } catch (error) {
            debugLog('Binding error: ' + error.message, true);
            statusEl.style.display = 'block';
            statusEl.style.color = 'var(--danger)';
            statusEl.textContent = '❌ ' + error.message;

            bindingBtn.disabled = false;
            bindingBtn.innerHTML = '<span>📧</span><span>重新發送</span>';
        }
    };

    function showForm() {
        document.getElementById('loading-container').style.display = 'none';
        document.getElementById('error-container').style.display = 'none';
        document.getElementById('success-container').style.display = 'none';
        document.getElementById('form-container').classList.add('active');
        document.getElementById('submit-section').classList.remove('hidden');
    }

    function showSuccess() {
        document.getElementById('loading-container').style.display = 'none';
        document.getElementById('error-container').style.display = 'none';
        document.getElementById('success-container').style.display = 'flex';
        document.getElementById('form-container').classList.remove('active');
        document.getElementById('submit-section').classList.add('hidden');
    }

    // Make closeWindow globally available
    window.closeWindow = function () {
        if (typeof liff !== 'undefined' && liff.isInClient()) {
            liff.closeWindow();
        } else {
            window.close();
        }
    };

    // Initialize on DOM ready
    async function init() {
        console.log('[LEAVE_FORM] DOMContentLoaded');

        const loadingText = document.querySelector('.loading-text');
        if (loadingText) loadingText.textContent = '系統初始化中...';

        createDebugOverlay();
        debugLog('DOM loaded, checking LIFF SDK...');

        // Wait for LIFF SDK (max 10 seconds)
        let attempts = 0;
        while (typeof liff === 'undefined' && attempts < 100) {
            if (attempts % 10 === 0 && loadingText) {
                loadingText.textContent = `正在連接 LINE 服務... (${Math.floor(attempts / 10)})`;
            }
            await new Promise(r => setTimeout(r, 100));
            attempts++;
        }

        if (typeof liff === 'undefined') {
            debugLog('LIFF SDK load timeout!', true);
            showError('LIFF SDK 載入逾時，請重新整理頁面');
            return;
        }

        debugLog('LIFF SDK loaded OK, version: ' + liff.getVersion());
        if (loadingText) loadingText.textContent = 'LINE 服務已連接';

        // Start LIFF initialization
        initializeLiff().catch(function (err) {
            debugLog('initializeLiff error: ' + err.message, true);
            showError('初始化失敗: ' + err.message);
        });
    }

    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Global error handler
    window.onerror = function (msg, url, line, col, error) {
        console.error('[GLOBAL ERROR]', msg, url, line);
        if (typeof debugLog === 'function') {
            debugLog('JS Error: ' + msg, true);
        }
        return false;
    };

})();
