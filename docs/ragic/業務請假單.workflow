/**

 * 此註解和以下的欄位 ID 都是在 2026/01/29 11:20:53 由系統自動產生。
 * 如果您需要目前資料庫裡的表單定義，請到"開始" => "帳號設定" => "資料庫維護" => "下載資料庫欄位定義文件"

 * AP_Name:HSIBAdmSys
 * Key Field: 1005578

 * 欄位名稱                            欄位編號
 * - - - - - - - - - - - --------
 * 假別                : 1005565
 * 起始日期             : 1005566
 * 結束日期             : 1005567
 * 請假日期             : 1005568
 * 請假天數             : 1005569
 * 事由                : 1005570
 * 姓名                : 1005571
 * 電子郵件信箱          : 1005579
 * 營業部               : 1005572
 * 營業部負責人          : 1005573
 * 營業部負責人電子郵件信箱 : 1005670
 * 直屬主管             : 1005574
 * 直屬主管電子郵件信箱    : 1005671
 * 審核狀態             : 1005575
 * 請假單號             : 1005576
 * 建立日期             : 1005577

 */
/**
 * @fileoverview 自動發起簽核工作流 (Post-workflow)
 * 
 * ★★★ 使用方式 ★★★
 * 1. 在 Ragic 表單設計中，右鍵點擊表單 -> JavaScript Workflow
 * 2. 從上方下拉選單選擇「Post-workflow」
 * 3. 貼上此程式碼並儲存
 */

// ============================================================
// 欄位定義
// ============================================================
var STATUS_FIELD = 1005575;           // 審核狀態
var MGR_EMAIL_FIELD = 1005671;        // 直屬主管電子郵件信箱
var DEPT_HEAD_EMAIL_FIELD = 1005670;  // 營業部負責人電子郵件信箱
var LEAVE_ID_FIELD = 1005576;         // 請假單號
var KEY_FIELD = 1005578;              // 主鍵欄位

var STATUS_INITIAL = '已上傳';
var STATUS_ACTIVE = '審核中';

// ============================================================
// Debug Log 函式 (正確的 Ragic 方式)
// ============================================================
log.setToConsole(true);

function debugLog(msg) {
    log.println("[請假單WF] " + msg);
}

// ============================================================
// 主程式 (Post-workflow)
// ============================================================

// 取得剛儲存的資料
var entry = param.getUpdatedEntry();
var recordId = param.getNewNodeId(KEY_FIELD);

debugLog("=== Post-workflow 開始 ===");
debugLog("Record ID: " + recordId);

// 取得欄位值
var currentStatus = entry.getFieldValue(STATUS_FIELD);
var mgrEmail = entry.getFieldValue(MGR_EMAIL_FIELD);
var deptHeadEmail = entry.getFieldValue(DEPT_HEAD_EMAIL_FIELD);
var leaveId = entry.getFieldValue(LEAVE_ID_FIELD);

debugLog("審核狀態: [" + currentStatus + "]");
debugLog("直屬主管 Email: " + mgrEmail);
debugLog("負責人 Email: " + deptHeadEmail);
debugLog("請假單號: " + leaveId);

// 檢查是否為新建立的資料
var isNew = param.isCreateNew();
debugLog("是否新建立: " + isNew);

// ============================================================
// 條件判斷：是否該發起簽核
// ============================================================

// 使用模糊匹配（因為 Ragic 選項可能有編號前綴）
function statusContains(status, keyword) {
    if (!status) return false;
    return status.indexOf(keyword) !== -1;
}

// 如果狀態已經是「審核中」，不要再執行（防止無限迴圈）
if (statusContains(currentStatus, STATUS_ACTIVE)) {
    debugLog("略過：狀態已經是審核中");
} else if (statusContains(currentStatus, STATUS_INITIAL) || isNew) {
    // 狀態是「已上傳」或是新建立的資料 -> 執行簽核流程
    
    debugLog("條件符合，準備發起簽核...");
    
    // 檢查 Email 是否有值（只警告，不阻擋）
    if (!mgrEmail || mgrEmail.trim() === '') {
        debugLog("警告：缺少直屬主管 Email");
    }
    if (!deptHeadEmail || deptHeadEmail.trim() === '') {
        debugLog("警告：缺少負責人 Email");
    }
    
    // ============================================================
    // 發起簽核 (使用 approval.create)
    // ============================================================
    // 注意：您需要先在「設計模式」中設定好簽核步驟
    // 這裡的 stepIndex 和 approver 必須符合您在設計模式中的設定
    
    try {
        var signers = [];
        
        // 第一步：直屬主管簽核
        if (mgrEmail && mgrEmail.trim() !== '') {
            signers.push({
                'stepIndex': '0',
                'approver': mgrEmail.trim(),
                'stepName': '直屬主管'
            });
        }
        
        // 第二步：營業部負責人簽核
        if (deptHeadEmail && deptHeadEmail.trim() !== '') {
            signers.push({
                'stepIndex': '1',
                'approver': deptHeadEmail.trim(),
                'stepName': '營業部負責人'
            });
        }
        
        if (signers.length > 0) {
            debugLog("發起簽核，簽核人數: " + signers.length);
            debugLog("簽核資料: " + JSON.stringify(signers));
            
            approval.create(JSON.stringify(signers));
            
            debugLog("簽核已發起");
        } else {
            debugLog("沒有簽核人，跳過發起簽核");
        }
        
        // 更新狀態為「審核中」
        entry.setFieldValue(STATUS_FIELD, STATUS_ACTIVE);
        entry.save();
        
        debugLog("狀態已更新為「審核中」");
        
    } catch (e) {
        debugLog("發生錯誤: " + e.message);
    }
    
} else {
    debugLog("略過：狀態不符合觸發條件 (狀態=" + currentStatus + ")");
}

debugLog("=== Post-workflow 結束 ===");
