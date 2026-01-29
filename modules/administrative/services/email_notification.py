"""
Email Notification Service.

Handles sending email notifications for administrative workflows.
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """
    Service for sending email notifications.
    
    Uses SMTP to send formatted HTML emails for leave request notifications.
    """
    
    # Company info
    COMPANY_NAME = "高成保險經紀人股份有限公司"
    RAGIC_LEAVE_STATUS_URL = "https://ap13.ragic.com/HSIBAdmSys/ychn-test/3?PAGEID=sqT"
    
    def __init__(self):
        """Initialize email service with SMTP configuration from environment."""
        self._smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self._smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self._smtp_username = os.getenv("SMTP_USERNAME", "")
        self._smtp_password = os.getenv("SMTP_PASSWORD", "")
        self._from_email = os.getenv("SMTP_FROM_EMAIL", "")
        self._from_name = os.getenv("SMTP_FROM_NAME", "高成保經行政系統")
    
    def _is_configured(self) -> bool:
        """Check if SMTP is properly configured."""
        return bool(
            self._smtp_host and 
            self._smtp_username and 
            self._smtp_password and 
            self._from_email
        )
    
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
    
    def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """
        Send an HTML email via SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML content of the email
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self._from_name} <{self._from_email}>"
            msg['To'] = to_email
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Send via SMTP
            logger.info(f"Sending leave confirmation email to {to_email}")
            
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.starttls()
                server.login(self._smtp_username, self._smtp_password)
                server.sendmail(self._from_email, [to_email], msg.as_string())
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending email: {e}")
            return False


# Singleton instance
_email_service: Optional[EmailNotificationService] = None


def get_email_notification_service() -> EmailNotificationService:
    """Get singleton EmailNotificationService instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailNotificationService()
    return _email_service
