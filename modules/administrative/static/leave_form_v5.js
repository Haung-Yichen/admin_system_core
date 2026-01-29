// leave_form_v5.js - V6 SECURITY FIX (ID Token Only)
// This file MUST be loaded externally to bypass CSP inline script blocks

(function() {
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
        overlay.innerHTML = '<div style="margin-bottom:4px;font-weight:bold;">Debug Console (V6) <button onclick="this.parentElement.style.display=\'none\'" style="float:right;background:#333;color:#fff;border:none;padding:2px 6px;cursor:pointer;">×</button></div><div id="debug-logs"></div>';
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
    
    // Make showDebugOverlay globally available
    window.showDebugOverlay = function() {
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
    
    // Load leave types from backend
    async function loadLeaveTypes() {
        try {
            debugLog('Loading leave types...');
            const response = await fetchWithTimeout(`${API_BASE_URL}/api/administrative/leave/types`);
            
            if (!response.ok) {
                debugLog('Failed to load leave types: HTTP ' + response.status, true);
                // Fall back to default options
                populateDefaultLeaveTypes();
                return;
            }
            
            const data = await response.json();
            const selectEl = document.getElementById('leave-type');
            
            // Clear existing options
            selectEl.innerHTML = '<option value="">請選擇假別</option>';
            
            if (data.leave_types && data.leave_types.length > 0) {
                data.leave_types.forEach(lt => {
                    const option = document.createElement('option');
                    option.value = lt.name;  // 使用假別名稱作為 value，確保 POST 到 Ragic 時能匹配下拉選項
                    option.textContent = lt.name;
                    selectEl.appendChild(option);
                });
                debugLog('Loaded ' + data.leave_types.length + ' leave types');
            } else {
                debugLog('No leave types returned, using defaults', true);
                populateDefaultLeaveTypes();
            }
            
        } catch (error) {
            debugLog('Load leave types error: ' + error.message, true);
            populateDefaultLeaveTypes();
        }
    }
    
    // Fallback default leave types
    function populateDefaultLeaveTypes() {
        const selectEl = document.getElementById('leave-type');
        selectEl.innerHTML = `
            <option value="">請選擇假別</option>
            <option value="特休">特休</option>
            <option value="事假">事假</option>
            <option value="全薪病假">全薪病假</option>
            <option value="補休">補休</option>
            <option value="外出單">外出單</option>
            <option value="生理假">生理假</option>
            <option value="因公出差">因公出差</option>
        `;
    }
    
    // Initialize LIFF
    async function initializeLiff() {
        createDebugOverlay();
        debugLog('Initializing... V6 (ID Token Only Mode)');
        
        const urlParams = new URLSearchParams(window.location.search);
        
        // Development test mode
        if (urlParams.get('testUserId')) {
            const testUser = urlParams.get('testUserId');
            debugLog('Development mode enabled: ' + testUser);
            userId = testUser;
            userProfile = { displayName: 'Dev User' };
            idToken = 'dev_mode_token';
            document.querySelector('.loading-text').textContent = '開發模式：載入假別選項...';
            await loadLeaveTypes();
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
                    liffId = (config.liff_id_leave || '').trim();
                    debugLog('Loaded LIFF ID: ' + liffId);
                } else {
                    debugLog('Config response not OK: ' + configResponse.status, true);
                }
            } catch (e) {
                debugLog('Failed to fetch config: ' + e.message, true);
            }
            
            if (!liffId) {
                debugLog('LIFF ID missing, cannot initialize LIFF', true);
                showError('LIFF 設定缺失，請確認 ADMIN_LINE_LIFF_ID_LEAVE 已設定。');
                return;
            }

            const liffIdPattern = /^\d+-[a-zA-Z0-9]+$/;
            if (!liffIdPattern.test(liffId)) {
                debugLog('Invalid LIFF ID format: ' + liffId, true);
                showError('LIFF ID 格式錯誤，請確認設定值是否正確。');
                return;
            }

            try {
                await liff.init({ liffId: liffId });
            } catch (initError) {
                const initMessage = initError && initError.message ? initError.message : String(initError);
                debugLog('LIFF init failed: ' + initMessage, true);
                if (initMessage.toLowerCase().includes('pattern')) {
                    showError('LIFF 初始化失敗：LIFF ID 或端點設定不符，請確認 LIFF App 的 Endpoint URL 與目前網址一致。');
                    return;
                }
                throw initError;
            }

            // Check if logged in
            if (!liff.isLoggedIn()) {
                // Special handling for external browser debug
                if (!liff.isInClient()) {
                    debugLog('Running in external browser, not logged in');
                    // For debugging, maybe allow manual entry or mock? 
                    // For now, redirect to login
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
                return;
            }
            
            debugLog('ID Token obtained successfully');
            
            document.querySelector('.loading-text').textContent = '正在載入假別選項...';
            await loadLeaveTypes();
            
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
            debugLog('Loading user data (V6 - POST mode)...');
            
            // SECURITY FIX: Send ID Token in POST body to avoid WebKit URL validation issues
            if (!idToken) {
                debugLog('No ID Token available!', true);
                showError('無法取得驗證權杖，請重新登入。');
                return;
            }
            
            const targetUrl = `${API_BASE_URL}/api/administrative/leave/init`;
            debugLog('Making API request to init (POST mode)');
            
            const response = await fetchWithTimeout(
                targetUrl,
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ line_id_token: idToken })
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
                    debugLog('Token expired or invalid, re-authenticating...', true);
                    // Token expired - trigger re-login
                    if (typeof liff !== 'undefined' && liff.isLoggedIn && liff.isLoggedIn()) {
                        liff.logout();
                    }
                    if (typeof liff !== 'undefined' && liff.login) {
                        liff.login();
                    } else {
                        showError('身份驗證已過期，請重新開啟此頁面。');
                    }
                    return;
                }
                
                throw new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
            }
            
            const data = await response.json();
            debugLog('User data loaded successfully');
            
            document.getElementById('user-name').textContent = data.name || '-';
            document.getElementById('user-email').textContent = data.email || '-';
            // Extended applicant info
            document.getElementById('user-sales-dept').textContent = data.sales_dept || '-';
            document.getElementById('user-sales-dept-manager').textContent = data.sales_dept_manager || '-';
            document.getElementById('user-direct-supervisor').textContent = data.direct_supervisor || '-';
            
            // Set default dates (start: tomorrow, end: tomorrow)
            const tomorrow = new Date();
            tomorrow.setDate(tomorrow.getDate() + 1);
            const tomorrowStr = tomorrow.toISOString().split('T')[0];
            document.getElementById('start-date').value = tomorrowStr;
            document.getElementById('end-date').value = tomorrowStr;
            
            // Setup date change listeners
            document.getElementById('start-date').addEventListener('change', onDateRangeChange);
            document.getElementById('end-date').addEventListener('change', onDateRangeChange);
            
            showForm();
            
            // Trigger initial workdays load
            await onDateRangeChange();
            
        } catch (error) {
            debugLog('Load user data error: ' + error.message, true);
            showError(`載入資料失敗: ${error.message}`);
        }
    }
    
    // Handle date range change - fetch workdays from backend
    async function onDateRangeChange() {
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;
        
        debugLog(`Date range change: start=${startDate}, end=${endDate}`);
        
        if (!startDate || !endDate) {
            debugLog('Missing date, hiding workdays container');
            document.getElementById('workdays-container').style.display = 'none';
            return;
        }
        
        // Validate date range
        if (new Date(startDate) > new Date(endDate)) {
            debugLog('Invalid date range (start > end), hiding container');
            document.getElementById('workdays-container').style.display = 'none';
            return;
        }
        
        const container = document.getElementById('workdays-container');
        const listEl = document.getElementById('workdays-list');
        
        container.style.display = 'block';
        listEl.innerHTML = '<div class="workdays-loading">載入工作日...</div>';
        
        try {
            // Use POST to avoid LINE Browser URL validation issues
            const url = `${API_BASE_URL}/api/administrative/leave/workdays`;
            debugLog(`Fetching workdays (POST) for ${startDate} to ${endDate}`);
            
            const response = await fetchWithTimeout(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ start_date: startDate, end_date: endDate })
            });
            
            debugLog(`Workdays response status: ${response.status}`);
            
            if (!response.ok) {
                const errorText = await response.text();
                debugLog(`Workdays error response: ${errorText}`, true);
                throw new Error('Failed to fetch workdays');
            }
            
            const data = await response.json();
            debugLog(`Workdays received: ${data.workdays ? data.workdays.length : 0} days`);
            renderWorkdays(data.workdays);
            
        } catch (error) {
            debugLog('Fetch workdays error: ' + error.message, true);
            listEl.innerHTML = '<div class="workdays-loading" style="color: var(--danger);">無法載入工作日</div>';
        }
    }
    
    // Render workday checkboxes
    function renderWorkdays(workdays) {
        const listEl = document.getElementById('workdays-list');
        
        if (!workdays || workdays.length === 0) {
            listEl.innerHTML = '<div class="workdays-loading">此日期範圍內沒有工作日</div>';
            return;
        }
        
        const weekdayNames = ['週日', '週一', '週二', '週三', '週四', '週五', '週六'];
        
        listEl.innerHTML = workdays.map((day, index) => {
            const date = new Date(day.date);
            const weekday = weekdayNames[date.getDay()];
            const displayDate = `${date.getMonth() + 1}/${date.getDate()} (${weekday})`;
            
            return `
                <label class="workday-item" for="workday-${index}">
                    <input type="checkbox" 
                           class="workday-checkbox" 
                           id="workday-${index}" 
                           name="workdays" 
                           value="${day.date}"
                           onchange="updateWorkdayStyle(this)">
                    <span class="workday-label">${displayDate}</span>
                </label>
            `;
        }).join('');
        
        debugLog(`Rendered ${workdays.length} workday checkboxes`);
    }
    
    // Update checkbox item style
    window.updateWorkdayStyle = function(checkbox) {
        const item = checkbox.closest('.workday-item');
        if (checkbox.checked) {
            item.classList.add('selected');
        } else {
            item.classList.remove('selected');
        }
    };
    
    // Select all days
    window.selectAllDays = function() {
        document.querySelectorAll('.workday-checkbox').forEach(cb => {
            cb.checked = true;
            updateWorkdayStyle(cb);
        });
    };
    
    // Deselect all days
    window.deselectAllDays = function() {
        document.querySelectorAll('.workday-checkbox').forEach(cb => {
            cb.checked = false;
            updateWorkdayStyle(cb);
        });
    };
    
    // Submit form - make it globally available
    window.submitForm = async function(event) {
        event.preventDefault();
        
        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner" style="width:20px;height:20px;border-width:2px;"></span><span>處理中...</span>';
        
        try {
            // Collect selected workdays
            const selectedDays = Array.from(document.querySelectorAll('.workday-checkbox:checked'))
                .map(cb => cb.value);
            
            if (selectedDays.length === 0) {
                throw new Error('請至少選擇一個請假日期');
            }
            
            const formData = {
                leave_dates: selectedDays,
                leave_type: document.getElementById('leave-type').value,
                reason: document.getElementById('reason').value,
            };
            
            // SECURITY FIX: Only send ID Token for authentication
            const params = new URLSearchParams();
            if (idToken) {
                params.append('line_id_token', idToken);
            } else {
                throw new Error('驗證權杖已失效，請重新整理頁面。');
            }
            
            const targetUrl = `${API_BASE_URL}/api/administrative/leave/submit?${params.toString()}`;
            debugLog('Submitting form with query params...');
            
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
            // console.log('Submission result:', result);
            
            showSuccess();
            
        } catch (error) {
            // console.error('Submit error:', error);
            debugLog('Submit error: ' + error.message, true);
            alert('送出失敗: ' + error.message);
            
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
    window.sendBindingEmail = async function() {
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
    window.closeWindow = function() {
        if (typeof liff !== 'undefined' && liff.isInClient()) {
            liff.closeWindow();
        } else {
            window.close();
        }
    };
    
    // Initialize on DOM ready
    async function init() {
        // console.log('[LEAVE_FORM] DOMContentLoaded - V6');

        const loadingText = document.querySelector('.loading-text');
        if (loadingText) loadingText.textContent = '系統初始化中... (V6)';
        createDebugOverlay();
        debugLog('DOM loaded, checking LIFF SDK (V6)...');
        debugLog('User Agent: ' + navigator.userAgent);
        
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
        initializeLiff().catch(function(err) {
            const errMsg = err && err.message ? err.message : String(err);
            debugLog('initializeLiff error: ' + errMsg, true);
            if (errMsg.toLowerCase().includes('pattern')) {
                showError(
                    'LIFF 初始化失敗：URL/ID 格式不符。\n' +
                    '請確認：\n' +
                    '1) LINE Developers Console 的 LIFF Endpoint URL 與目前網址一致\n' +
                    '2) ADMIN_LINE_LIFF_ID_LEAVE 設定正確且無多餘空白\n' +
                    '3) LINE App 已更新到最新版'
                );
                return;
            }
            showError('初始化失敗: ' + errMsg);
        });
    }
    
    // Start
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // Global error handler
    window.onerror = function(msg, url, line, col, error) {
        // console.error('[GLOBAL ERROR]', msg, url, line);
        if (typeof debugLog === 'function') {
            debugLog('JS Error: ' + msg, true);
        }
        return false;
    };
    
})();