"""
Unit Tests for Email Services.

Tests email sending functionality in:
- AuthService._send_verification_email (Magic Link emails via aiosmtplib)
- EmailNotificationService (Leave notifications via smtplib)

This test suite ensures comprehensive coverage before refactoring
to a unified email service.
"""

import pytest
import sys
import os
import smtplib
from unittest.mock import MagicMock, AsyncMock, patch
from email.mime.multipart import MIMEMultipart

# Add project root to path for direct imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_email_notification_module():
    """Load EmailNotificationService module directly to avoid chain imports."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "email_notification",
        "modules/administrative/services/email_notification.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# =============================================================================
# AuthService Email Tests (aiosmtplib)
# =============================================================================

class TestAuthServiceEmail:
    """Tests for AuthService._send_verification_email method."""

    @pytest.fixture
    def auth_service(self, mock_env_vars):
        """Create AuthService instance with mocked dependencies."""
        from core.services import auth as auth_module
        
        with patch.object(auth_module, 'get_ragic_service') as mock_ragic:
            mock_ragic.return_value = MagicMock()
            service = auth_module.AuthService()
            yield service

    @pytest.mark.asyncio
    async def test_send_verification_email_success(self, auth_service, mock_aiosmtplib):
        """Test successful magic link email sending."""
        await auth_service._send_verification_email(
            to_email="employee@example.com",
            employee_name="John Doe",
            magic_link="https://example.com/verify?token=abc123",
        )

        mock_aiosmtplib.assert_called_once()
        call_args = mock_aiosmtplib.call_args
        msg = call_args[0][0]
        
        assert "employee@example.com" in str(msg["To"])
        assert "LINE" in str(msg["Subject"])

    @pytest.mark.asyncio
    async def test_send_verification_email_contains_magic_link(
        self, auth_service, mock_aiosmtplib
    ):
        """Test that email body contains the magic link."""
        import base64
        from email import message_from_string
        
        magic_link = "https://test.example.com/api/auth/verify?token=xyz789"
        
        await auth_service._send_verification_email(
            to_email="test@example.com",
            employee_name="Test User",
            magic_link=magic_link,
        )

        call_args = mock_aiosmtplib.call_args
        msg = call_args[0][0]
        msg_str = msg.as_string()
        
        # Parse the email message to get decoded content
        parsed = message_from_string(msg_str)
        decoded_content = ""
        for part in parsed.walk():
            if part.get_content_type() in ["text/plain", "text/html"]:
                payload = part.get_payload(decode=True)
                if payload:
                    decoded_content += payload.decode('utf-8', errors='ignore')
        
        assert "xyz789" in decoded_content or "xyz789" in msg_str

    @pytest.mark.asyncio
    async def test_send_verification_email_smtp_error(self, auth_service):
        """Test handling of SMTP errors."""
        with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
            mock_send.side_effect = Exception("SMTP connection failed")
            
            from core.services.auth import EmailSendError
            
            with pytest.raises(EmailSendError) as exc_info:
                await auth_service._send_verification_email(
                    to_email="test@example.com",
                    employee_name="Test User",
                    magic_link="https://example.com/verify",
                )
            
            assert "SMTP connection failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_verification_email_uses_config(self, mock_env_vars):
        """Test that email service uses config values."""
        from core.services import auth as auth_module
        
        with patch.object(auth_module, 'get_ragic_service') as mock_ragic:
            mock_ragic.return_value = MagicMock()
            service = auth_module.AuthService()
            
            with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
                await service._send_verification_email(
                    to_email="test@example.com",
                    employee_name="Config User",
                    magic_link="https://example.com/verify",
                )
                
                call_kwargs = mock_send.call_args[1]
                assert call_kwargs.get("hostname") == "smtp.test.com"
                assert call_kwargs.get("port") == 587


# =============================================================================
# EmailNotificationService Tests (smtplib)
# =============================================================================

class TestEmailNotificationService:
    """Tests for EmailNotificationService from administrative module."""

    @pytest.fixture
    def email_module(self, mock_env_vars):
        """Load email notification module directly."""
        return load_email_notification_module()

    @pytest.fixture
    def email_service(self, email_module):
        """Create EmailNotificationService instance."""
        return email_module.EmailNotificationService()

    def test_init_loads_smtp_config(self, email_service):
        """Test that service initializes with SMTP config from env."""
        assert email_service._smtp_host == "smtp.test.com"
        assert email_service._smtp_port == 587
        assert email_service._smtp_username == "test@test.com"
        assert email_service._smtp_password == "testpass"
        assert email_service._from_email == "noreply@test.com"

    def test_is_configured_returns_true_when_configured(self, email_service):
        """Test _is_configured returns True with valid config."""
        assert email_service._is_configured() is True

    def test_is_configured_returns_false_when_missing_host(self, monkeypatch):
        """Test _is_configured returns False when host is missing."""
        monkeypatch.setenv("SMTP_HOST", "")
        
        module = load_email_notification_module()
        service = module.EmailNotificationService()
        assert service._is_configured() is False

    def test_is_configured_returns_false_when_missing_username(self, monkeypatch):
        """Test _is_configured returns False when username is missing."""
        monkeypatch.setenv("SMTP_USERNAME", "")
        monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
        monkeypatch.setenv("SMTP_PASSWORD", "pass")
        monkeypatch.setenv("SMTP_FROM_EMAIL", "from@test.com")
        
        module = load_email_notification_module()
        service = module.EmailNotificationService()
        assert service._is_configured() is False

    def test_send_leave_request_confirmation_success(
        self, email_service, mock_smtp_server
    ):
        """Test successful leave confirmation email."""
        result = email_service.send_leave_request_confirmation(
            to_email="employee@example.com",
            employee_name="王小明",
            leave_dates=["2026-02-01", "2026-02-02"],
            leave_type="特休",
            reason="家庭旅遊",
            leave_request_no="LR-2026-0001",
            direct_supervisor="李經理",
            sales_dept_manager="陳總監",
        )

        assert result is True
        mock_smtp_server.starttls.assert_called_once()
        mock_smtp_server.login.assert_called_once_with(
            "test@test.com", "testpass"
        )
        mock_smtp_server.sendmail.assert_called_once()

    def test_send_leave_request_confirmation_single_date(
        self, email_service, mock_smtp_server
    ):
        """Test leave confirmation with single date formats correctly."""
        result = email_service.send_leave_request_confirmation(
            to_email="employee@example.com",
            employee_name="王小明",
            leave_dates=["2026-02-01"],
            leave_type="事假",
            reason="個人事務",
            leave_request_no="LR-2026-0002",
            direct_supervisor="李經理",
            sales_dept_manager="陳總監",
        )

        assert result is True

    def test_send_leave_request_confirmation_not_configured(self, monkeypatch):
        """Test returns False when SMTP not configured."""
        monkeypatch.setenv("SMTP_HOST", "")
        monkeypatch.setenv("SMTP_USERNAME", "")
        monkeypatch.setenv("SMTP_PASSWORD", "")
        monkeypatch.setenv("SMTP_FROM_EMAIL", "")
        
        module = load_email_notification_module()
        service = module.EmailNotificationService()
        
        result = service.send_leave_request_confirmation(
            to_email="test@example.com",
            employee_name="Test",
            leave_dates=["2026-02-01"],
            leave_type="特休",
            reason="Test",
            leave_request_no="LR-001",
            direct_supervisor="",
            sales_dept_manager="",
        )
        
        assert result is False

    def test_send_leave_request_confirmation_no_recipient(
        self, email_service, mock_smtp_server
    ):
        """Test returns False when no recipient email provided."""
        result = email_service.send_leave_request_confirmation(
            to_email="",
            employee_name="Test",
            leave_dates=["2026-02-01"],
            leave_type="特休",
            reason="Test",
            leave_request_no="LR-001",
            direct_supervisor="",
            sales_dept_manager="",
        )
        
        assert result is False
        mock_smtp_server.sendmail.assert_not_called()

    def test_send_leave_request_confirmation_smtp_auth_error(
        self, email_service
    ):
        """Test handling of SMTP authentication errors."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            mock_server.starttls = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(
                535, b"Authentication failed"
            )
            
            result = email_service.send_leave_request_confirmation(
                to_email="employee@example.com",
                employee_name="Test",
                leave_dates=["2026-02-01"],
                leave_type="特休",
                reason="Test",
                leave_request_no="LR-001",
                direct_supervisor="",
                sales_dept_manager="",
            )
            
            assert result is False

    def test_send_leave_request_confirmation_smtp_error(self, email_service):
        """Test handling of general SMTP errors."""
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            mock_server.starttls = MagicMock()
            mock_server.login = MagicMock()
            mock_server.sendmail.side_effect = smtplib.SMTPException(
                "Connection reset"
            )
            
            result = email_service.send_leave_request_confirmation(
                to_email="employee@example.com",
                employee_name="Test",
                leave_dates=["2026-02-01"],
                leave_type="特休",
                reason="Test",
                leave_request_no="LR-001",
                direct_supervisor="",
                sales_dept_manager="",
            )
            
            assert result is False

    def test_send_email_html_content(self, email_service, mock_smtp_server):
        """Test that email contains proper HTML structure."""
        import base64
        from email import message_from_string
        
        email_service.send_leave_request_confirmation(
            to_email="employee@example.com",
            employee_name="測試員工",
            leave_dates=["2026-02-01", "2026-02-02", "2026-02-03"],
            leave_type="病假",
            reason="身體不適",
            leave_request_no="LR-2026-0003",
            direct_supervisor="主管A",
            sales_dept_manager="經理B",
        )

        call_args = mock_smtp_server.sendmail.call_args
        msg_content = call_args[0][2]
        
        # Parse MIME message to get decoded content
        parsed = message_from_string(msg_content)
        decoded_content = ""
        for part in parsed.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    decoded_content = payload.decode('utf-8', errors='ignore')
                    break
        
        assert "<!DOCTYPE html>" in decoded_content
        assert "測試員工" in decoded_content or "LR-2026-0003" in decoded_content
        assert "LR-2026-0003" in decoded_content
        assert "病假" in decoded_content


class TestEmailNotificationServiceSingleton:
    """Tests for singleton pattern."""

    def test_get_email_notification_service_returns_singleton(self, mock_env_vars):
        """Test that get_email_notification_service returns same instance."""
        module = load_email_notification_module()
        module._email_service = None
        
        service1 = module.get_email_notification_service()
        service2 = module.get_email_notification_service()
        
        assert service1 is service2


# =============================================================================
# Email Template Tests (Admin Module)
# =============================================================================

class TestAdminEmailTemplates:
    """Tests for email HTML template generation (admin module)."""

    @pytest.fixture
    def email_service(self, mock_env_vars):
        """Create EmailNotificationService instance."""
        module = load_email_notification_module()
        return module.EmailNotificationService()

    def test_leave_email_contains_required_fields(
        self, email_service, mock_smtp_server
    ):
        """Test leave email contains all required information fields."""
        from email import message_from_string
        
        email_service.send_leave_request_confirmation(
            to_email="test@example.com",
            employee_name="測試員工",
            leave_dates=["2026-03-01"],
            leave_type="婚假",
            reason="結婚",
            leave_request_no="LR-2026-0100",
            direct_supervisor="直屬主管",
            sales_dept_manager="部門經理",
        )

        call_args = mock_smtp_server.sendmail.call_args
        msg_content = call_args[0][2]
        
        # Parse MIME message to get decoded content
        parsed = message_from_string(msg_content)
        decoded_content = ""
        for part in parsed.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    decoded_content = payload.decode('utf-8', errors='ignore')
                    break
        
        # Verify expected fields in decoded content
        assert "婚假" in decoded_content
        assert "結婚" in decoded_content
        assert "LR-2026-0100" in decoded_content
        assert "直屬主管" in decoded_content
        assert "部門經理" in decoded_content

    def test_leave_email_handles_none_supervisors(
        self, email_service, mock_smtp_server
    ):
        """Test email handles None/empty supervisor fields gracefully."""
        from email import message_from_string
        
        result = email_service.send_leave_request_confirmation(
            to_email="test@example.com",
            employee_name="員工",
            leave_dates=["2026-03-01"],
            leave_type="特休",
            reason="休息",
            leave_request_no="LR-001",
            direct_supervisor="",
            sales_dept_manager="",
        )

        assert result is True
        call_args = mock_smtp_server.sendmail.call_args
        msg_content = call_args[0][2]
        
        # Parse MIME message to get decoded content
        parsed = message_from_string(msg_content)
        decoded_content = ""
        for part in parsed.walk():
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    decoded_content = payload.decode('utf-8', errors='ignore')
                    break
        
        # When supervisor is empty, "未指定" should appear in template
        assert "未指定" in decoded_content


# =============================================================================
# Core EmailService Tests (new unified service)
# =============================================================================

class TestCoreEmailService:
    """Tests for the new unified core/services/email.py EmailService."""

    @pytest.fixture
    def mock_env_vars(self):
        """Set up environment variables for testing."""
        env_vars = {
            "SMTP_HOST": "smtp.test.com",
            "SMTP_PORT": "587",
            "SMTP_USERNAME": "test_user",
            "SMTP_PASSWORD": "test_pass",
            "SMTP_FROM_EMAIL": "noreply@test.com",
            "SMTP_FROM_NAME": "Test System",
        }
        with patch.dict(os.environ, env_vars):
            yield

    @pytest.fixture
    def email_config(self):
        """Create test email config."""
        return {
            "host": "smtp.test.com",
            "port": 587,
            "username": "test_user",
            "password": "test_pass",
            "from_email": "noreply@test.com",
            "from_name": "Test System",
            "use_tls": True,
        }

    @pytest.fixture
    def email_service(self, email_config):
        """Create EmailService instance with test config."""
        from core.services.email import EmailService
        return EmailService(config=email_config)

    def test_init_with_config(self, email_service, email_config):
        """Test EmailService initializes correctly with config."""
        assert email_service.config.host == email_config["host"]
        assert email_service.config.port == email_config["port"]
        assert email_service.config.username == email_config["username"]
        assert email_service.config.from_email == email_config["from_email"]

    def test_is_configured_returns_true(self, email_service):
        """Test is_configured returns True when fully configured."""
        assert email_service.is_configured is True

    def test_is_configured_returns_false_when_missing_host(self, email_config):
        """Test is_configured returns False when host is missing."""
        from core.services.email import EmailService
        email_config["host"] = ""
        service = EmailService(config=email_config)
        assert service.is_configured is False

    def test_send_sync_success(self, email_service):
        """Test synchronous email sending."""
        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_server = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_server
            
            result = email_service.send_sync(
                to_email="test@example.com",
                subject="Test Subject",
                html_content="<h1>Test</h1>",
                text_content="Test"
            )
            
            assert result is True
            mock_server.sendmail.assert_called_once()

    def test_send_sync_not_configured(self):
        """Test send_sync returns False when not configured."""
        from core.services.email import EmailService
        service = EmailService(config={"host": "", "username": "", "password": "", "from_email": ""})
        
        result = service.send_sync(
            to_email="test@example.com",
            subject="Test",
            html_content="<h1>Test</h1>"
        )
        
        assert result is False

    def test_send_sync_no_recipient(self, email_service):
        """Test send_sync returns False when no recipient."""
        result = email_service.send_sync(
            to_email="",
            subject="Test",
            html_content="<h1>Test</h1>"
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_async_success(self, email_service):
        """Test asynchronous email sending."""
        with patch('aiosmtplib.send', new_callable=AsyncMock) as mock_send:
            result = await email_service.send_async(
                to_email="test@example.com",
                subject="Async Test",
                html_content="<h1>Async</h1>",
                text_content="Async"
            )
            
            assert result is True
            mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_async_not_configured(self):
        """Test send_async returns False when not configured."""
        from core.services.email import EmailService
        service = EmailService(config={"host": "", "username": "", "password": "", "from_email": ""})
        
        result = await service.send_async(
            to_email="test@example.com",
            subject="Test",
            html_content="<h1>Test</h1>"
        )
        
        assert result is False


class TestCoreEmailTemplates:
    """Tests for EmailTemplates class (core module)."""

    def test_magic_link_verification_template(self):
        """Test magic link verification email template."""
        from core.services.email import EmailTemplates
        
        subject, html, text = EmailTemplates.magic_link_verification(
            employee_name="Test User",
            magic_link="https://example.com/verify?token=abc123",
            expire_minutes=15,
            app_name="Test App"
        )
        
        assert "Test App" in subject
        assert "Test User" in html
        assert "Test User" in text
        assert "https://example.com/verify?token=abc123" in html
        assert "https://example.com/verify?token=abc123" in text
        assert "15" in text

    def test_leave_request_confirmation_template(self):
        """Test leave request confirmation email template."""
        from core.services.email import EmailTemplates
        
        subject, html = EmailTemplates.leave_request_confirmation(
            employee_name="測試員工",
            leave_request_no="LR-2026-0001",
            leave_type="特休",
            leave_dates=["2026-01-01", "2026-01-02"],
            reason="休息",
            direct_supervisor="主管",
            dept_manager="經理",
            status_url="https://example.com/status",
            company_name="測試公司"
        )
        
        assert "LR-2026-0001" in subject
        assert "測試公司" in subject
        assert "特休" in html
        assert "休息" in html
        assert "主管" in html
        assert "經理" in html
        assert "https://example.com/status" in html

    def test_leave_request_single_date(self):
        """Test leave request with single date displays correctly."""
        from core.services.email import EmailTemplates
        
        subject, html = EmailTemplates.leave_request_confirmation(
            employee_name="員工",
            leave_request_no="LR-001",
            leave_type="事假",
            leave_dates=["2026-03-01"],
            reason="私事",
            direct_supervisor="",
            dept_manager="",
            status_url="https://example.com",
        )
        
        assert "2026-03-01" in html
        assert "未指定" in html  # Empty supervisor shows 未指定


class TestCoreEmailServiceSingleton:
    """Tests for EmailService singleton pattern."""

    def test_get_email_service_returns_singleton(self):
        """Test that get_email_service returns the same instance."""
        from core.services.email import get_email_service
        import core.services.email as email_module
        
        # Reset singleton
        email_module._email_service = None
        
        service1 = get_email_service()
        service2 = get_email_service()
        
        assert service1 is service2
