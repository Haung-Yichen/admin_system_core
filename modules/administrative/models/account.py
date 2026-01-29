"""
AdministrativeAccount Model.

SQLAlchemy model for caching Account data from Ragic.
This serves as a local read-replica for performance and offline access.

Contains comprehensive employee/account information including:
- Personal info (name, ID, gender, birthday)
- Contact info (emails, phones, addresses)
- Employment info (org, rank, status)
- License info (life insurance, property insurance, etc.)
- Financial info (bank account, withholding rates)
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base, TimestampMixin


class AdministrativeAccount(Base, TimestampMixin):
    """
    Account cache table synced from Ragic.
    
    This model stores a local copy of account data from the Ragic No-Code DB.
    The sync is performed by RagicSyncService on application startup.
    
    Primary Key: ragic_id (Field 1005971 - 帳號系統編號)
    Unique: account_id (Field 1005972 - 帳號)
    """

    __tablename__ = "administrative_accounts"

    # === Primary Identification ===
    ragic_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        comment="帳號系統編號 (Ragic Field 1005971)",
    )
    account_id: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="帳號 (Ragic Field 1005972)",
    )
    id_card_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="身份證字號 (Ragic Field 1005973)",
    )
    employee_id: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="員工編號 (Ragic Field 1005983)",
    )

    # === Status & Basic Info ===
    status: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
        comment="狀態 (0:停用, 1:正常) (Ragic Field 1005974)",
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="姓名 (Ragic Field 1005975)",
    )
    gender: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="性別 (男/女/法) (Ragic Field 1005976)",
    )
    birthday: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="生日 (Ragic Field 1005985)",
    )
    education: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="教育程度 (Ragic Field 1005984)",
    )

    # === Contact Info ===
    emails: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="E-Mail, 逗號分隔多值 (Ragic Field 1005977)",
    )
    phones: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="電話, 逗號分隔多值 (Ragic Field 1005986)",
    )
    mobiles: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="手機, 逗號分隔多值 (Ragic Field 1005987)",
    )

    # === Organization Info ===
    org_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="組織代號 (Ragic Field 1005978)",
    )
    org_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="組織名稱 (Ragic Field 1006049)",
    )
    org_path: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="組織路徑 (Ragic Field 1006031)",
    )
    rank_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="職級代號 (Ragic Field 1005979)",
    )
    rank_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="職級名稱 (Ragic Field 1006050)",
    )
    sales_dept: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="營業部 (Ragic Field 1006058)",
    )
    sales_dept_manager: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="營業部負責人 (Ragic Field 1006059)",
    )

    # === Referrer & Mentor ===
    referrer_id_card: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="推介者身份證 (Ragic Field 1005980)",
    )
    referrer_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="推介者名稱 (Ragic Field 1006042)",
    )
    mentor_id_card: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="輔導者身份證 (Ragic Field 1005981)",
    )
    mentor_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="輔導者名稱 (Ragic Field 1006043)",
    )
    successor_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="繼承人名稱 (Ragic Field 1006045)",
    )
    successor_id_card: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="繼承人身分證 (Ragic Field 1006046)",
    )

    # === Employment Dates ===
    approval_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="核准日期 (Ragic Field 1006016)",
    )
    effective_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="生效日期 (Ragic Field 1006017)",
    )
    resignation_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="離職日期 (Ragic Field 1006019)",
    )
    death_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="身故日期 (Ragic Field 1006024)",
    )
    created_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="建立日期 (Ragic Field 1006015)",
    )

    # === Rate & Financial ===
    assessment_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="考核率, 0.01=1% (Ragic Field 1005982)",
    )
    court_withholding_rate: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="法院強制執行扣押率, 0.01=1% (Ragic Field 1006025)",
    )
    court_min_living_expense: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="法院強制執行最低生活費保障 (Ragic Field 1006051)",
    )
    prior_commission_debt: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="前期欠佣 (Ragic Field 1006026)",
    )
    prior_debt: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="前期欠款 (Ragic Field 1006027)",
    )

    # === Bank Info ===
    bank_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="銀行名稱 (Ragic Field 1006010)",
    )
    bank_branch_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="銀行分行代碼 (Ragic Field 1006011)",
    )
    bank_account: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="銀行帳號 (Ragic Field 1006012)",
    )
    edi_format: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="EDI格式 (0:銀行EDI, 1:標準轉帳) (Ragic Field 1006033)",
    )

    # === Address - Household Registration ===
    household_postal_code: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="戶籍郵遞區號 (Ragic Field 1005988)",
    )
    household_city: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="戶籍縣市 (Ragic Field 1005989)",
    )
    household_district: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="戶籍鄉鎮市區 (Ragic Field 1005990)",
    )
    household_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="戶籍地址 (Ragic Field 1005991)",
    )

    # === Address - Mailing ===
    mailing_postal_code: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="通訊郵遞區號 (Ragic Field 1005992)",
    )
    mailing_city: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="通訊縣市 (Ragic Field 1005993)",
    )
    mailing_district: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="通訊鄉鎮市區 (Ragic Field 1005994)",
    )
    mailing_address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="通訊地址 (Ragic Field 1005995)",
    )

    # === Emergency Contact ===
    emergency_contact: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="緊急聯絡人 (Ragic Field 1005996)",
    )
    emergency_phone: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="緊急聯絡電話 (Ragic Field 1005997)",
    )

    # === Life Insurance License ===
    life_license_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="壽險證照號碼 (Ragic Field 1005998)",
    )
    life_first_registration_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="壽險初次登錄日期 (Ragic Field 1006018)",
    )
    life_registration_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="壽險登錄日期 (Ragic Field 1005999)",
    )
    life_exam_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="壽險考試號碼 (Ragic Field 1006000)",
    )
    life_cancellation_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="壽險註銷日期 (Ragic Field 1006001)",
    )
    life_license_expiry: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="壽險證照有效期限 (Ragic Field 1006028)",
    )

    # === Property Insurance License ===
    property_license_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="產險證照號碼 (Ragic Field 1006002)",
    )
    property_registration_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="產險登錄日期 (Ragic Field 1006003)",
    )
    property_exam_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="產險考試號碼 (Ragic Field 1006004)",
    )
    property_cancellation_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="產險註銷日期 (Ragic Field 1006005)",
    )
    property_license_expiry: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="產險證照有效期限 (Ragic Field 1006029)",
    )
    property_standard_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="產險標準日 (Ragic Field 1006041)",
    )

    # === Accident & Health Insurance License ===
    ah_license_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="傷健險證照號碼 (Ragic Field 1006021)",
    )
    ah_registration_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="傷健險登錄日期 (Ragic Field 1006022)",
    )
    ah_cancellation_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="傷健險註銷日期 (Ragic Field 1006023)",
    )
    ah_license_expiry: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="傷健險證照有效期限 (Ragic Field 1006030)",
    )

    # === Investment-linked Insurance ===
    investment_registration_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="投資型登錄日期 (Ragic Field 1006006)",
    )
    investment_exam_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="投資型考試號碼 (Ragic Field 1006007)",
    )

    # === Foreign Currency Insurance ===
    foreign_currency_registration_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="外幣型登錄日期 (Ragic Field 1006008)",
    )
    foreign_currency_exam_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="外幣型考試號碼 (Ragic Field 1006009)",
    )

    # === Qualifications ===
    fund_qualification_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="基金資格通報日期 (Ragic Field 1006034)",
    )
    traditional_annuity_qualification: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="傳統年金資格 (0:無, 1:有) (Ragic Field 1006035)",
    )
    variable_annuity_qualification: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="利率變動型年金資格 (0:無, 1:有) (Ragic Field 1006036)",
    )
    structured_bond_qualification: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="結構債資格 (0:無, 1:有) (Ragic Field 1006037)",
    )
    mobile_insurance_exam_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="行動投保考試合格日期 (Ragic Field 1006038)",
    )
    preferred_insurance_exam_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="優體保險考試合格日期 (Ragic Field 1006039)",
    )
    app_enabled: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
        comment="啟用APP (0:否, 1:是) (Ragic Field 1006040)",
    )

    # === Training Completion Dates ===
    senior_training_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="高齡訓練完成日 (Ragic Field 1006054)",
    )
    foreign_currency_training_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="外幣訓練完成日 (Ragic Field 1006055)",
    )
    fair_treatment_training_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="公平待客訓練完成日 (Ragic Field 1006056)",
    )
    profit_sharing_training_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="分紅訓練完成日 (Ragic Field 1006057)",
    )

    # === Office Info ===
    office: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="事務所 (Ragic Field 1006013)",
    )
    office_tax_id: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="事務所統一編號 (Ragic Field 1006014)",
    )
    submission_unit: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="送件單位 (Ragic Field 1006032)",
    )

    # === Health Insurance Withholding ===
    nhi_withholding_status: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="二代健保代扣狀態 (0:免代扣) (Ragic Field 1006047)",
    )
    nhi_withholding_update_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="二代健保代扣狀態更新日期 (Ragic Field 1006048)",
    )

    # === Miscellaneous ===
    remarks: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="備註 (Ragic Field 1006020)",
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="注意事項 (Ragic Field 1006053)",
    )
    account_attributes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="帳號屬性, 逗號分隔多值 (Ragic Field 1006052)",
    )
    last_modified: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="最後修改 (Ragic Field 1006044)",
    )

    def __repr__(self) -> str:
        return (
            f"<AdministrativeAccount("
            f"ragic_id={self.ragic_id}, "
            f"account_id={self.account_id}, "
            f"name={self.name}, "
            f"status={'Active' if self.status else 'Disabled'}"
            f")>"
        )

    @property
    def is_active(self) -> bool:
        """Check if the account is active (status=1 and no resignation)."""
        return self.status and self.resignation_date is None

    @property
    def primary_email(self) -> Optional[str]:
        """Get the first email from the comma-separated list."""
        if not self.emails:
            return None
        return self.emails.split(",")[0].strip()

    @property
    def primary_phone(self) -> Optional[str]:
        """Get the first phone from the comma-separated list."""
        if not self.phones:
            return None
        return self.phones.split(",")[0].strip()

    @property
    def primary_mobile(self) -> Optional[str]:
        """Get the first mobile from the comma-separated list."""
        if not self.mobiles:
            return None
        return self.mobiles.split(",")[0].strip()
