"""
Email Notification Service.

Handles sending email notifications for administrative workflows.
Delegates to core.services.email.EmailService for actual sending.
"""

import logging
import os
from typing import Optional
from urllib.parse import urlencode

from core.services.email import get_email_service, EmailTemplates

logger = logging.getLogger(__name__)


class LiffDeepLinkGenerator:
    """
    Generator for LINE LIFF Deep Links.
    
    Follows the Single Responsibility Principle - handles only deep link generation.
    LIFF URL Scheme: https://liff.line.me/{liff_id}?{query_params}
    """
    
    LIFF_BASE_URL = "https://liff.line.me"
    
    def __init__(self, liff_id: str) -> None:
        """
        Initialize deep link generator.
        
        Args:
            liff_id: The LINE LIFF App ID for verification redirects.
        """
        self._liff_id = liff_id
    
    def generate_magic_link(self, token: str) -> str:
        """
        Generate a LIFF magic link for email verification.
        
        The generated URL opens LINE app directly on mobile devices,
        providing a native app experience.
        
        Args:
            token: The verification token to include in the link.
            
        Returns:
            str: Full LIFF deep link URL with token parameter.
        """
        if not self._liff_id:
            raise ValueError("LIFF ID is not configured")
        
        query_params = urlencode({"token": token})
        return f"{self.LIFF_BASE_URL}/{self._liff_id}?{query_params}"
    
    @property
    def is_configured(self) -> bool:
        """Check if LIFF ID is properly configured."""
        return bool(self._liff_id)


class EmailNotificationService:
    """
    Service for sending email notifications.
    
    Delegates to core.services.email.EmailService for actual SMTP sending.
    This class provides business-specific templates and convenience methods.
    """
    
    # Company info
    COMPANY_NAME = "高成保險經紀人股份有限公司"
    RAGIC_LEAVE_STATUS_URL = "https://ap13.ragic.com/HSIBAdmSys/ychn-test/3?PAGEID=sqT"
    
    def __init__(self, liff_id_verify: str = "") -> None:
        """
        Initialize email notification service.
        
        Args:
            liff_id_verify: LIFF ID for verification deep links (optional).
        """
        # LIFF deep link generator (Dependency Injection)
        self._liff_link_generator = LiffDeepLinkGenerator(
            liff_id=liff_id_verify or os.getenv("ADMIN_LINE_LIFF_ID_VERIFY", "")
        )
        
        # Get core email service (handles all SMTP config)
        self._email_service = get_email_service()
    
    def _is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return self._email_service.is_configured
    
    def generate_verification_magic_link(self, token: str) -> str:
        """
        Generate a LIFF magic link for email verification.
        
        This creates a deep link that opens LINE app directly,
        providing a seamless mobile-native experience.
        
        Args:
            token: The verification token.
            
        Returns:
            str: LIFF deep link URL.
            
        Raises:
            ValueError: If LIFF ID is not configured.
        """
        return self._liff_link_generator.generate_magic_link(token)
    
    def send_leave_request_confirmation(
        self,
        to_email: str,
        employee_name: str,
        leave_dates: list[str],
        leave_type: str,
        reason: str,
        leave_request_no: str,
        direct_supervisor: str,
        sales_dept_manager: str,
    ) -> bool:
        """
        Send leave request confirmation email to the applicant.
        
        Args:
            to_email: Recipient email address
            employee_name: Name of the employee
            leave_dates: List of leave dates
            leave_type: Type of leave (e.g., 特休, 事假)
            reason: Reason for leave
            leave_request_no: Leave request number
            direct_supervisor: Direct supervisor name
            sales_dept_manager: Sales department manager name
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self._is_configured():
            logger.warning("SMTP not configured, skipping email notification")
            return False
        
        if not to_email:
            logger.warning("No recipient email provided, skipping notification")
            return False
        
        # Format dates for display
        if len(leave_dates) == 1:
            dates_display = leave_dates[0]
        else:
            dates_display = f"{leave_dates[0]} 至 {leave_dates[-1]}"
        
        all_dates_list = "、".join(leave_dates)
        
        subject = f"【{self.COMPANY_NAME}】請假申請已送出 - {leave_request_no}"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Microsoft JhengHei', '微軟正黑體', Arial, sans-serif;
            line-height: 1.8;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #1a5f7a, #2c8fb5);
            color: white;
            padding: 25px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }}
        .header h1 {{
            margin: 0;
            font-size: 22px;
            font-weight: 600;
        }}
        .content {{
            background: #ffffff;
            padding: 30px;
            border: 1px solid #e0e0e0;
            border-top: none;
        }}
        .greeting {{
            font-size: 16px;
            margin-bottom: 20px;
        }}
        .info-box {{
            background: #f8f9fa;
            border-left: 4px solid #1a5f7a;
            padding: 20px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
        }}
        .info-row {{
            display: flex;
            margin: 10px 0;
            padding: 8px 0;
            border-bottom: 1px dashed #e0e0e0;
        }}
        .info-row:last-child {{
            border-bottom: none;
        }}
        .info-label {{
            font-weight: 600;
            color: #555;
            min-width: 100px;
        }}
        .info-value {{
            color: #333;
        }}
        .status-badge {{
            display: inline-block;
            background: #ffc107;
            color: #333;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
        }}
        .action-section {{
            background: #e8f4f8;
            padding: 20px;
            margin: 25px 0;
            border-radius: 8px;
            text-align: center;
        }}
        .action-btn {{
            display: inline-block;
            background: #1a5f7a;
            color: white !important;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 25px;
            font-weight: 600;
            margin-top: 10px;
        }}
        .action-btn:hover {{
            background: #2c8fb5;
        }}
        .note {{
            font-size: 13px;
            color: #666;
            margin-top: 20px;
            padding: 15px;
            background: #fff3cd;
            border-radius: 8px;
        }}
        .footer {{
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #888;
            border-radius: 0 0 8px 8px;
            border: 1px solid #e0e0e0;
            border-top: none;
        }}
        .company-name {{
            font-weight: 600;
            color: #1a5f7a;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 請假申請通知</h1>
    </div>
    
    <div class="content">
        <div class="greeting">
            <strong>{employee_name}</strong> 您好：
        </div>
        
        <p>您的請假申請已成功送出，目前正在等待主管簽核。</p>
        
        <div class="info-box">
            <div class="info-row">
                <span class="info-label">📌 請假單號</span>
                <span class="info-value"><strong>{leave_request_no}</strong></span>
            </div>
            <div class="info-row">
                <span class="info-label">📅 請假類型</span>
                <span class="info-value">{leave_type}</span>
            </div>
            <div class="info-row">
                <span class="info-label">📆 請假期間</span>
                <span class="info-value">{dates_display}</span>
            </div>
            <div class="info-row">
                <span class="info-label">📝 請假日期</span>
                <span class="info-value">{all_dates_list}</span>
            </div>
            <div class="info-row">
                <span class="info-label">⏱️ 請假天數</span>
                <span class="info-value"><strong>{len(leave_dates)}</strong> 天</span>
            </div>
            <div class="info-row">
                <span class="info-label">💬 請假事由</span>
                <span class="info-value">{reason}</span>
            </div>
            <div class="info-row">
                <span class="info-label">👤 直屬主管</span>
                <span class="info-value">{direct_supervisor or '未指定'}</span>
            </div>
            <div class="info-row">
                <span class="info-label">👥 部門負責人</span>
                <span class="info-value">{sales_dept_manager or '未指定'}</span>
            </div>
            <div class="info-row">
                <span class="info-label">📊 目前狀態</span>
                <span class="info-value"><span class="status-badge">⏳ 等待簽核</span></span>
            </div>
        </div>
        
        <div class="action-section">
            <p style="margin: 0 0 10px 0; color: #555;">想確認簽核進度？</p>
            <a href="{self.RAGIC_LEAVE_STATUS_URL}" class="action-btn" target="_blank">
                🔍 查看簽核狀態
            </a>
        </div>
        
        <div class="note">
            <strong>📢 提醒：</strong><br>
            • 請假申請將由您的直屬主管與部門負責人依序審核<br>
            • 審核結果將另行通知，請耐心等候<br>
            • 如有疑問，請聯繫您的直屬主管
        </div>
    </div>
    
    <div class="footer">
        <p class="company-name">{self.COMPANY_NAME}</p>
        <p>此為系統自動發送之郵件，請勿直接回覆</p>
        <p style="margin-top: 10px;">© 2026 {self.COMPANY_NAME} All Rights Reserved.</p>
    </div>
</body>
</html>
"""
        
        return self._send_email(to_email, subject, html_content)
    
    def send_email_verification(
        self,
        to_email: str,
        employee_name: str,
        verification_token: str,
        purpose: str = "帳號驗證",
        expiry_hours: int = 24,
    ) -> bool:
        """
        Send email verification notification with LIFF deep link.
        
        Uses LINE LIFF Deep Linking for a seamless mobile-native experience.
        When clicked on mobile, the link opens directly in LINE app.
        
        Args:
            to_email: Recipient email address.
            employee_name: Name of the employee.
            verification_token: Token for verification.
            purpose: Description of verification purpose.
            expiry_hours: Number of hours until link expires.
            
        Returns:
            bool: True if email sent successfully, False otherwise.
        """
        if not self._is_configured():
            logger.warning("SMTP not configured, skipping verification email")
            return False
        
        if not to_email:
            logger.warning("No recipient email provided, skipping verification email")
            return False
        
        # Generate LIFF magic link
        try:
            magic_link = self.generate_verification_magic_link(verification_token)
        except ValueError as e:
            logger.error(f"Failed to generate magic link: {e}")
            return False
        
        subject = f"【{self.COMPANY_NAME}】{purpose} - 請點擊連結完成驗證"
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: 'Microsoft JhengHei', '微軟正黑體', Arial, sans-serif;
            line-height: 1.8;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background: linear-gradient(135deg, #06C755, #05B34C);
            color: white;
            padding: 25px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }}
        .header h1 {{
            margin: 0;
            font-size: 22px;
            font-weight: 600;
        }}
        .content {{
            background: #ffffff;
            padding: 30px;
            border: 1px solid #e0e0e0;
            border-top: none;
        }}
        .greeting {{
            font-size: 16px;
            margin-bottom: 20px;
        }}
        .verify-section {{
            background: #f0faf4;
            border: 2px solid #06C755;
            padding: 25px;
            margin: 25px 0;
            border-radius: 12px;
            text-align: center;
        }}
        .verify-btn {{
            display: inline-block;
            background: #06C755;
            color: white !important;
            padding: 14px 40px;
            text-decoration: none;
            border-radius: 30px;
            font-weight: 600;
            font-size: 16px;
            margin-top: 15px;
        }}
        .verify-btn:hover {{
            background: #05B34C;
        }}
        .line-icon {{
            font-size: 24px;
            margin-right: 8px;
        }}
        .note {{
            font-size: 13px;
            color: #666;
            margin-top: 20px;
            padding: 15px;
            background: #fff3cd;
            border-radius: 8px;
        }}
        .expiry-note {{
            font-size: 12px;
            color: #888;
            margin-top: 10px;
        }}
        .footer {{
            background: #f5f5f5;
            padding: 20px;
            text-align: center;
            font-size: 12px;
            color: #888;
            border-radius: 0 0 8px 8px;
            border: 1px solid #e0e0e0;
            border-top: none;
        }}
        .company-name {{
            font-weight: 600;
            color: #1a5f7a;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔐 {purpose}</h1>
    </div>
    
    <div class="content">
        <div class="greeting">
            <strong>{employee_name}</strong> 您好：
        </div>
        
        <p>我們收到了您的{purpose}請求，請點擊下方按鈕完成驗證。</p>
        
        <div class="verify-section">
            <p style="margin: 0 0 10px 0; color: #555; font-size: 14px;">
                點擊按鈕將在 LINE 應用程式中開啟
            </p>
            <a href="{magic_link}" class="verify-btn">
                <span class="line-icon">💬</span> 在 LINE 中驗證
            </a>
            <p class="expiry-note">
                ⏰ 此連結將於 {expiry_hours} 小時後失效
            </p>
        </div>
        
        <div class="note">
            <strong>📢 安全提醒：</strong><br>
            • 如果您沒有發起此請求，請忽略此郵件<br>
            • 請勿將此連結分享給他人<br>
            • 連結僅能使用一次
        </div>
    </div>
    
    <div class="footer">
        <p class="company-name">{self.COMPANY_NAME}</p>
        <p>此為系統自動發送之郵件，請勿直接回覆</p>
        <p style="margin-top: 10px;">© 2026 {self.COMPANY_NAME} All Rights Reserved.</p>
    </div>
</body>
</html>
"""
        
        return self._send_email(to_email, subject, html_content)
    
    def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        Send an HTML email via core EmailService.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            logger.info(f"Sending email to {to_email}: {subject}")
            return self._email_service.send_sync(
                to_email=to_email,
                subject=subject,
                html_content=html_content,
            )
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False


# Singleton instance
_email_service: Optional[EmailNotificationService] = None


def get_email_notification_service() -> EmailNotificationService:
    """Get singleton EmailNotificationService instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailNotificationService()
    return _email_service
