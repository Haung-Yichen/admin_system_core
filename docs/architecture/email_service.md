# Email Service Architecture

## Overview

All email sending in this application is handled by the **core EmailService** (`core/services/email.py`).
Modules should **NOT** implement their own SMTP/email sending logic.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Modules                                  │
│  ┌─────────────────────┐    ┌──────────────────────────────┐   │
│  │ core/services/auth  │    │ modules/administrative/...   │   │
│  │   (Magic Link)      │    │   (Leave Notification)       │   │
│  └──────────┬──────────┘    └──────────────┬───────────────┘   │
│             │                              │                    │
│             └──────────────┬───────────────┘                    │
│                            ▼                                    │
│              ┌─────────────────────────────┐                    │
│              │  core/services/email.py     │                    │
│              │  - EmailService             │                    │
│              │  - EmailTemplates           │                    │
│              │  - EmailConfig              │                    │
│              └──────────────┬──────────────┘                    │
│                             │                                   │
└─────────────────────────────┼───────────────────────────────────┘
                              ▼
                    ┌────────────────┐
                    │   SMTP Server  │
                    └────────────────┘
```

## Usage Guidelines

### For Modules (Business Logic)

1. **Import from core**:
   ```python
   from core.services.email import get_email_service, EmailTemplates
   ```

2. **Use EmailTemplates for common templates**:
   ```python
   subject, html, text = EmailTemplates.magic_link_verification(...)
   subject, html = EmailTemplates.leave_request_confirmation(...)
   ```

3. **Send via EmailService**:
   ```python
   email_service = get_email_service()
   
   # Async context
   await email_service.send_async(to_email, subject, html_content, text_content)
   
   # Sync context
   email_service.send_sync(to_email, subject, html_content)
   ```

### Configuration

EmailService reads configuration from `AppContext` (typically mapped from environment variables).

Priority:
1. Passed `config` dictionary (from `AppContext`)
2. Environment variables (fallback)

| Config Key | Environment Variable | Description |
|------------|----------------------|-------------|
| `host` | `SMTP_HOST` | SMTP server hostname |
| `port` | `SMTP_PORT` | SMTP server port |
| `username` | `SMTP_USERNAME` | SMTP username |
| `password` | `SMTP_PASSWORD` | SMTP password |
| `from_email` | `SMTP_FROM_EMAIL` | Sender email address |
| `from_name` | `SMTP_FROM_NAME` | Sender display name |

### Do NOT

❌ Import `smtplib` or `aiosmtplib` directly in modules  
❌ Create `MIMEMultipart` / `MIMEText` objects in modules  
❌ Load SMTP config (`SMTP_*` env vars) in modules  
❌ Implement email sending logic outside of `core/services/email.py`

## Adding New Email Templates

1. Add a new static method to `EmailTemplates` class in `core/services/email.py`
2. Return `(subject, html_content, text_content)` tuple
3. Use the template in your module via `EmailTemplates.your_new_template(...)`

## Testing

Mock `get_email_service()` in your tests:
```python
from unittest.mock import Mock, patch

@patch('your_module.get_email_service')
def test_email_sending(mock_get_service):
    mock_service = Mock()
    mock_service.send_sync.return_value = True
    mock_get_service.return_value = mock_service
    
    # Your test code
    
    mock_service.send_sync.assert_called_once_with(...)
```
