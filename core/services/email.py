"""
Core Email Service.

Provides a unified email sending service for the entire application.
Supports both synchronous (smtplib) and asynchronous (aiosmtplib) sending.

This is a framework-level service that modules should use instead of
implementing their own email sending logic.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from core.app_context import ConfigLoader

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """Raised when email sending fails."""
    pass


class EmailConfig:
    """Email configuration from config.yaml."""
    
    def __init__(self, config: dict[str, Any]) -> None:
        self.host = config.get("host", "smtp.gmail.com")
        self.port = int(config.get("port", 587))
        self.username = config.get("username", "")
        self.password = config.get("password", "")
        self.from_email = config.get("from_email", "")
        self.from_name = config.get("from_name", "Admin System")
        self.use_tls = config.get("use_tls", True)
    
    @property
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return bool(
            self.host and 
            self.username and 
            self.password and 
            self.from_email
        )


class EmailService:
    """
    Unified email service for the application.
    
    Supports:
    - Synchronous sending via smtplib (for background tasks)
    - Asynchronous sending via aiosmtplib (for async handlers)
    - HTML and plain text emails
    - Multiple recipients
    
    Usage:
        # Get singleton
        email_svc = get_email_service()
        
        # Async sending
        await email_svc.send_async(
            to_email="user@example.com",
            subject="Hello",
            html_content="<h1>Hello</h1>",
            text_content="Hello"
        )
        
        # Sync sending
        email_svc.send_sync(
            to_email="user@example.com",
            subject="Hello",
            html_content="<h1>Hello</h1>"
        )
    """
    
    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        """
        Initialize email service.
        
        Args:
            config: Email configuration dict. If None, loads from config.yaml.
        """
        if config is None:
            loader = ConfigLoader()
            loader.load()
            config = loader.get("email", {})
        
        self._config = EmailConfig(config)
        self._app_name = "Admin System"
        
        # Load app name from config if available
        try:
            loader = ConfigLoader()
            loader.load()
            self._app_name = loader.get("app.name", self._app_name)
        except Exception:
            pass
    
    @property
    def is_configured(self) -> bool:
        """Check if email service is properly configured."""
        return self._config.is_configured
    
    @property
    def config(self) -> EmailConfig:
        """Get email configuration."""
        return self._config
    
    def _create_message(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> MIMEMultipart:
        """
        Create MIME message for email.
        
        Args:
            to_email: Recipient email address.
            subject: Email subject.
            html_content: HTML body content.
            text_content: Optional plain text body content.
        
        Returns:
            MIMEMultipart message ready to send.
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self._config.from_name} <{self._config.from_email}>"
        msg["To"] = to_email
        
        # Add plain text version if provided
        if text_content:
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        
        # Add HTML version
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        
        return msg
    
    def send_sync(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send email synchronously using smtplib.
        
        Best for background tasks and sync contexts.
        
        Args:
            to_email: Recipient email address.
            subject: Email subject.
            html_content: HTML body content.
            text_content: Optional plain text body content.
        
        Returns:
            bool: True if sent successfully.
        
        Raises:
            EmailSendError: If sending fails.
        """
        if not self._config.is_configured:
            logger.warning("Email service not configured, skipping send")
            return False
        
        if not to_email:
            logger.warning("No recipient email provided, skipping send")
            return False
        
        msg = self._create_message(to_email, subject, html_content, text_content)
        
        try:
            logger.info(f"Sending email to {to_email}: {subject}")
            
            with smtplib.SMTP(self._config.host, self._config.port) as server:
                if self._config.use_tls:
                    server.starttls()
                server.login(self._config.username, self._config.password)
                server.sendmail(
                    self._config.from_email,
                    [to_email],
                    msg.as_string()
                )
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            raise EmailSendError(f"SMTP authentication failed: {e}") from e
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            raise EmailSendError(f"SMTP error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            raise EmailSendError(f"Failed to send email: {e}") from e
    
    async def send_async(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send email asynchronously using aiosmtplib.
        
        Best for async request handlers.
        
        Args:
            to_email: Recipient email address.
            subject: Email subject.
            html_content: HTML body content.
            text_content: Optional plain text body content.
        
        Returns:
            bool: True if sent successfully.
        
        Raises:
            EmailSendError: If sending fails.
        """
        if not self._config.is_configured:
            logger.warning("Email service not configured, skipping send")
            return False
        
        if not to_email:
            logger.warning("No recipient email provided, skipping send")
            return False
        
        msg = self._create_message(to_email, subject, html_content, text_content)
        
        try:
            import aiosmtplib
            
            logger.info(f"Sending email (async) to {to_email}: {subject}")
            
            await aiosmtplib.send(
                msg,
                hostname=self._config.host,
                port=self._config.port,
                start_tls=self._config.use_tls,
                username=self._config.username,
                password=self._config.password,
            )
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            raise EmailSendError(f"Failed to send email: {e}") from e


# =============================================================================
# Email Templates
# =============================================================================

class EmailTemplates:
    """
    Pre-built email templates for common use cases.
    
    Modules can use these directly or as references for custom templates.
    """
    
    @staticmethod
    def magic_link_verification(
        employee_name: str,
        magic_link: str,
        expire_minutes: int = 30,
        app_name: str = "Admin System",
    ) -> tuple[str, str, str]:
        """
        Generate magic link verification email content.
        
        Args:
            employee_name: Name of the employee.
            magic_link: The verification URL.
            expire_minutes: Link expiration time in minutes.
            app_name: Application name.
        
        Returns:
            tuple: (subject, html_content, text_content)
        """
        subject = f"🔐 {app_name} - 綁定您的 LINE 帳號"
        
        text_content = f"""
您好 {employee_name}，

您正在將 LINE 帳號與 {app_name} 進行綁定。

請點擊以下連結完成驗證：
{magic_link}

此連結將在 {expire_minutes} 分鐘後失效。

如果您沒有發起此請求，請忽略此郵件。

{app_name} 團隊
""".strip()
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family: sans-serif;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #00B900;">🔐 {app_name}</h2>
        <p>您好 <strong>{employee_name}</strong>，</p>
        <p>您正在將 LINE 帳號與系統進行綁定。</p>
        <p><a href="{magic_link}" style="background: #00B900; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">✅ 完成綁定</a></p>
        <p style="color: #888; font-size: 12px;">此連結將在 {expire_minutes} 分鐘後失效。</p>
    </div>
</body>
</html>
"""
        
        return subject, html_content, text_content
    
    @staticmethod
    def leave_request_confirmation(
        employee_name: str,
        leave_request_no: str,
        leave_type: str,
        leave_dates: list[str],
        reason: str,
        direct_supervisor: str,
        dept_manager: str,
        status_url: str,
        company_name: str = "高成保險經紀人股份有限公司",
    ) -> tuple[str, str]:
        """
        Generate leave request confirmation email content.
        
        Args:
            employee_name: Name of the employee.
            leave_request_no: Leave request number.
            leave_type: Type of leave.
            leave_dates: List of leave dates.
            reason: Leave reason.
            direct_supervisor: Direct supervisor name.
            dept_manager: Department manager name.
            status_url: URL to check approval status.
            company_name: Company name.
        
        Returns:
            tuple: (subject, html_content)
        """
        # Format dates
        if len(leave_dates) == 1:
            dates_display = leave_dates[0]
        else:
            dates_display = f"{leave_dates[0]} 至 {leave_dates[-1]}"
        
        all_dates_list = "、".join(leave_dates)
        
        subject = f"【{company_name}】請假申請已送出 - {leave_request_no}"
        
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
        .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; }}
        .content {{
            background: #ffffff;
            padding: 30px;
            border: 1px solid #e0e0e0;
            border-top: none;
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
        .info-row:last-child {{ border-bottom: none; }}
        .info-label {{ font-weight: 600; color: #555; min-width: 100px; }}
        .info-value {{ color: #333; }}
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
        .company-name {{ font-weight: 600; color: #1a5f7a; }}
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
                <span class="info-value">{dept_manager or '未指定'}</span>
            </div>
            <div class="info-row">
                <span class="info-label">📊 目前狀態</span>
                <span class="info-value"><span class="status-badge">⏳ 等待簽核</span></span>
            </div>
        </div>
        
        <div class="action-section">
            <p style="margin: 0 0 10px 0; color: #555;">想確認簽核進度？</p>
            <a href="{status_url}" class="action-btn" target="_blank">
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
        <p class="company-name">{company_name}</p>
        <p>此為系統自動發送之郵件，請勿直接回覆</p>
        <p style="margin-top: 10px;">© 2026 {company_name} All Rights Reserved.</p>
    </div>
</body>
</html>
"""
        
        return subject, html_content


# =============================================================================
# Singleton
# =============================================================================

_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get singleton EmailService instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
