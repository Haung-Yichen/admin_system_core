"""
Administrative Module Configuration.

Manages environment variables specific to the Administrative module.
Uses prefix ADMIN_ to avoid conflicts with other modules.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RagicLeaveFieldMapping:
    """
    Ragic Field ID mappings for the Leave Request form.
    
    These constants map our payload attributes to Ragic field IDs.
    Used for constructing the POST payload to create leave request records.
    
    Field Reference:
        The Leave Request form at /HSIBAdmSys/ychn-test/3
        Key Field: 1005578
        Generated: 2026/01/28
    """
    
    # === Employee Info ===
    EMPLOYEE_NAME = "1005571"  # 姓名
    EMPLOYEE_EMAIL = "1005579"  # 電子郵件信箱
    SALES_DEPT = "1005572"  # 營業部
    
    # === Leave Details ===
    LEAVE_TYPE = "1005565"  # 假別
    START_DATE = "1005566"  # 起始日期
    END_DATE = "1005567"  # 結束日期
    LEAVE_DATE = "1005568"  # 請假日期
    LEAVE_DAYS = "1005569"  # 請假天數
    LEAVE_REASON = "1005570"  # 事由
    
    # === Approval Chain (Names - Visible) ===
    SALES_DEPT_MANAGER_NAME = "1005573"  # 營業部負責人
    DIRECT_SUPERVISOR_NAME = "1005574"  # 直屬主管
    
    # === Approval Chain (Emails - Hidden, for triggering workflow) ===
    SALES_DEPT_MANAGER_EMAIL = "1005670"  # 營業部負責人電子郵件信箱
    DIRECT_SUPERVISOR_EMAIL = "1005671"  # 直屬主管電子郵件信箱
    
    # === System Fields ===
    APPROVAL_STATUS = "1005575"  # 審核狀態
    LEAVE_REQUEST_NO = "1005576"  # 請假單號
    CREATED_DATE = "1005577"  # 建立日期


class RagicLeaveTypeFieldMapping:
    """
    Ragic Field ID mappings for the Leave Type master data form.
    
    These constants map our model attributes to Ragic field IDs.
    Used for syncing leave type options from Ragic.
    
    Field Reference:
        The Leave Type form at /HSIBAdmSys/ragicforms39/20007
        Key Field: 3005180
        Generated: 2026/01/28
    """
    
    # === Primary Key ===
    RAGIC_ID = "3005180"  # Key Field (假別系統編號)
    
    # === Leave Type Info ===
    LEAVE_TYPE_CODE = "3005177"  # 假別編號
    LEAVE_TYPE_NAME = "3005178"  # 請假類別
    DEDUCTION_MULTIPLIER = "3005179"  # 扣薪乘數


class RagicAccountFieldMapping:
    """
    Ragic Field ID mappings for the unified Account form.
    
    These constants map our model attributes to Ragic field IDs.
    Used for schema validation and data transformation.
    
    Field Reference:
        The Account form at /HSIBAdmSys/ychn-test/11
        contains all employee/account data in a single table.
    """
    
    # === Primary Identification ===
    RAGIC_ID = "1005971"  # 帳號系統編號
    ACCOUNT_ID = "1005972"  # 帳號
    ID_CARD_NUMBER = "1005973"  # 身份證字號
    EMPLOYEE_ID = "1005983"  # 員工編號
    
    # === Status & Basic Info ===
    STATUS = "1005974"  # 狀態 (0:停用, 1:正常)
    NAME = "1005975"  # 姓名
    GENDER = "1005976"  # 性別 (男/女/法)
    BIRTHDAY = "1005985"  # 生日
    EDUCATION = "1005984"  # 教育程度
    
    # === Contact Info ===
    EMAILS = "1005977"  # E-Mail (逗號分隔多值)
    PHONES = "1005986"  # 電話 (逗號分隔多值)
    MOBILES = "1005987"  # 手機 (逗號分隔多值)
    
    # === Organization Info ===
    ORG_CODE = "1005978"  # 組織代號
    ORG_NAME = "1006049"  # 組織名稱
    ORG_PATH = "1006031"  # 組織路徑
    RANK_CODE = "1005979"  # 職級代號
    RANK_NAME = "1006050"  # 職級名稱
    SALES_DEPT = "1006058"  # 營業部
    SALES_DEPT_MANAGER = "1006059"  # 營業部負責人
    
    # === Referrer & Mentor ===
    REFERRER_ID_CARD = "1005980"  # 推介者身份證
    REFERRER_NAME = "1006042"  # 推介者名稱
    MENTOR_ID_CARD = "1005981"  # 輔導者身份證
    MENTOR_NAME = "1006043"  # 輔導者名稱
    SUCCESSOR_NAME = "1006045"  # 繼承人名稱
    SUCCESSOR_ID_CARD = "1006046"  # 繼承人身分證
    
    # === Employment Dates ===
    APPROVAL_DATE = "1006016"  # 核准日期
    EFFECTIVE_DATE = "1006017"  # 生效日期
    RESIGNATION_DATE = "1006019"  # 離職日期
    DEATH_DATE = "1006024"  # 身故日期
    CREATED_DATE = "1006015"  # 建立日期
    
    # === Rate & Financial ===
    ASSESSMENT_RATE = "1005982"  # 考核率
    COURT_WITHHOLDING_RATE = "1006025"  # 法院強制執行扣押率
    COURT_MIN_LIVING_EXPENSE = "1006051"  # 法院強制執行最低生活費保障
    PRIOR_COMMISSION_DEBT = "1006026"  # 前期欠佣
    PRIOR_DEBT = "1006027"  # 前期欠款
    
    # === Bank Info ===
    BANK_NAME = "1006010"  # 銀行名稱
    BANK_BRANCH_CODE = "1006011"  # 銀行分行代碼
    BANK_ACCOUNT = "1006012"  # 銀行帳號
    EDI_FORMAT = "1006033"  # EDI格式
    
    # === Address - Household Registration ===
    HOUSEHOLD_POSTAL_CODE = "1005988"  # 戶籍郵遞區號
    HOUSEHOLD_CITY = "1005989"  # 戶籍縣市
    HOUSEHOLD_DISTRICT = "1005990"  # 戶籍鄉鎮市區
    HOUSEHOLD_ADDRESS = "1005991"  # 戶籍地址
    
    # === Address - Mailing ===
    MAILING_POSTAL_CODE = "1005992"  # 通訊郵遞區號
    MAILING_CITY = "1005993"  # 通訊縣市
    MAILING_DISTRICT = "1005994"  # 通訊鄉鎮市區
    MAILING_ADDRESS = "1005995"  # 通訊地址
    
    # === Emergency Contact ===
    EMERGENCY_CONTACT = "1005996"  # 緊急聯絡人
    EMERGENCY_PHONE = "1005997"  # 緊急聯絡電話
    
    # === Life Insurance License ===
    LIFE_LICENSE_NUMBER = "1005998"  # 壽險證照號碼
    LIFE_FIRST_REGISTRATION_DATE = "1006018"  # 壽險初次登錄日期
    LIFE_REGISTRATION_DATE = "1005999"  # 壽險登錄日期
    LIFE_EXAM_NUMBER = "1006000"  # 壽險考試號碼
    LIFE_CANCELLATION_DATE = "1006001"  # 壽險註銷日期
    LIFE_LICENSE_EXPIRY = "1006028"  # 壽險證照有效期限
    
    # === Property Insurance License ===
    PROPERTY_LICENSE_NUMBER = "1006002"  # 產險證照號碼
    PROPERTY_REGISTRATION_DATE = "1006003"  # 產險登錄日期
    PROPERTY_EXAM_NUMBER = "1006004"  # 產險考試號碼
    PROPERTY_CANCELLATION_DATE = "1006005"  # 產險註銷日期
    PROPERTY_LICENSE_EXPIRY = "1006029"  # 產險證照有效期限
    PROPERTY_STANDARD_DATE = "1006041"  # 產險標準日
    
    # === Accident & Health Insurance License ===
    AH_LICENSE_NUMBER = "1006021"  # 傷健險證照號碼
    AH_REGISTRATION_DATE = "1006022"  # 傷健險登錄日期
    AH_CANCELLATION_DATE = "1006023"  # 傷健險註銷日期
    AH_LICENSE_EXPIRY = "1006030"  # 傷健險證照有效期限
    
    # === Investment-linked Insurance ===
    INVESTMENT_REGISTRATION_DATE = "1006006"  # 投資型登錄日期
    INVESTMENT_EXAM_NUMBER = "1006007"  # 投資型考試號碼
    
    # === Foreign Currency Insurance ===
    FOREIGN_CURRENCY_REGISTRATION_DATE = "1006008"  # 外幣型登錄日期
    FOREIGN_CURRENCY_EXAM_NUMBER = "1006009"  # 外幣型考試號碼
    
    # === Qualifications ===
    FUND_QUALIFICATION_DATE = "1006034"  # 基金資格通報日期
    TRADITIONAL_ANNUITY_QUALIFICATION = "1006035"  # 傳統年金資格
    VARIABLE_ANNUITY_QUALIFICATION = "1006036"  # 利率變動型年金資格
    STRUCTURED_BOND_QUALIFICATION = "1006037"  # 結構債資格
    MOBILE_INSURANCE_EXAM_DATE = "1006038"  # 行動投保考試合格日期
    PREFERRED_INSURANCE_EXAM_DATE = "1006039"  # 優體保險考試合格日期
    APP_ENABLED = "1006040"  # 啟用APP
    
    # === Training Completion Dates ===
    SENIOR_TRAINING_DATE = "1006054"  # 高齡訓練完成日
    FOREIGN_CURRENCY_TRAINING_DATE = "1006055"  # 外幣訓練完成日
    FAIR_TREATMENT_TRAINING_DATE = "1006056"  # 公平待客訓練完成日
    PROFIT_SHARING_TRAINING_DATE = "1006057"  # 分紅訓練完成日
    
    # === Office Info ===
    OFFICE = "1006013"  # 事務所
    OFFICE_TAX_ID = "1006014"  # 事務所統一編號
    SUBMISSION_UNIT = "1006032"  # 送件單位
    
    # === Health Insurance Withholding ===
    NHI_WITHHOLDING_STATUS = "1006047"  # 二代健保代扣狀態
    NHI_WITHHOLDING_UPDATE_DATE = "1006048"  # 二代健保代扣狀態更新日期
    
    # === Miscellaneous ===
    REMARKS = "1006020"  # 備註
    NOTES = "1006053"  # 注意事項
    ACCOUNT_ATTRIBUTES = "1006052"  # 帳號屬性
    LAST_MODIFIED = "1006044"  # 最後修改


class AdminSettings(BaseSettings):
    """
    Administrative module settings loaded from environment variables.
    
    All variables use the ADMIN_ prefix for module isolation.
    Sensitive values use SecretStr for security.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Ragic API Configuration
    ragic_api_key: Annotated[
        SecretStr,
        Field(
            description="Ragic API key for authentication",
            validation_alias="ADMIN_RAGIC_API_KEY",
        ),
    ]

    ragic_url_account: Annotated[
        str,
        Field(
            description="Full URL for the Ragic Account Form API endpoint",
            validation_alias="ADMIN_RAGIC_URL_ACCOUNT",
        ),
    ]

    ragic_url_leave: Annotated[
        str,
        Field(
            default="",
            description="Full URL for the Ragic Leave Request Form API endpoint",
            validation_alias="ADMIN_RAGIC_URL_LEAVE",
        ),
    ] = ""

    ragic_url_leave_type: Annotated[
        str,
        Field(
            default="",
            description="Full URL for the Ragic Leave Type master data API endpoint",
            validation_alias="ADMIN_RAGIC_URL_LEAVE_TYPE",
        ),
    ] = ""

    # Sync Configuration
    sync_batch_size: Annotated[
        int,
        Field(
            default=100,
            description="Number of records to process per batch during sync",
            validation_alias="ADMIN_SYNC_BATCH_SIZE",
        ),
    ] = 100

    sync_timeout_seconds: Annotated[
        int,
        Field(
            default=60,
            description="HTTP timeout for Ragic API requests",
            validation_alias="ADMIN_SYNC_TIMEOUT_SECONDS",
        ),
    ] = 60

    # LINE Channel Configuration (獨立 Channel)
    line_channel_secret: Annotated[
        SecretStr,
        Field(
            description="LINE channel secret for webhook verification",
            validation_alias="ADMIN_LINE_CHANNEL_SECRET",
        ),
    ]

    line_channel_access_token: Annotated[
        SecretStr,
        Field(
            description="LINE channel access token for sending messages",
            validation_alias="ADMIN_LINE_CHANNEL_ACCESS_TOKEN",
        ),
    ]

    # LINE LIFF Configuration
    line_liff_id_leave: Annotated[
        str,
        Field(
            default="",
            description="LIFF ID for the leave request form",
            validation_alias="ADMIN_LINE_LIFF_ID_LEAVE",
        ),
    ] = ""


@lru_cache
def get_admin_settings() -> AdminSettings:
    """
    Get cached administrative module settings.

    Uses LRU cache to ensure settings are loaded only once.

    Returns:
        AdminSettings: Administrative settings instance.
    """
    return AdminSettings()
