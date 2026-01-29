// Dynamic Loader for LIFF SDK
window.line_sdk_loaded = false;
const LIFF_DEBUG_MODE = false;  // Set to true for debugging

(function() {
    if (LIFF_DEBUG_MODE) console.log('[DEBUG] debug.js loaded');
    try {
        var statusEl = document.getElementById('status');
        if(statusEl) statusEl.innerHTML = 'JavaScript Status: <span style="color:blue">EXTERNAL JS RUNNING</span>';
    } catch(e) {
        if (LIFF_DEBUG_MODE) console.error(e);
    }
})();

function loadLiffSdk() {
    return new Promise((resolve, reject) => {
        if (LIFF_DEBUG_MODE) console.log('[DEBUG] Loading LIFF SDK...');
        var script = document.createElement('script');
        // script.src = "https://static.line-scdn.net/liff/edge/2/sdk.js";
        script.src = "https://static.line-scdn.net/liff/edge/2/sdk.js";
        script.onload = function() {
            if (LIFF_DEBUG_MODE) console.log('[DEBUG] LIFF SDK Loaded');
            window.line_sdk_loaded = true;
            resolve();
        };
        script.onerror = function(e) {
            if (LIFF_DEBUG_MODE) console.error('[DEBUG] LIFF SDK Load Error', e);
            reject(e);
        };
        document.head.appendChild(script);
    });
}
