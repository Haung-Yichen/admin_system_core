"""
Logging Configuration Module.

Provides centralized logging setup with rotating file handler.
Logs are saved to the project's logs directory (headless mode).
Includes automatic masking of sensitive data (passwords, tokens, secrets, emails).
"""

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


# --- Constants ---
LOG_FILENAME = "admin_system.log"
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# --- Sensitive Data Patterns ---
# Patterns for data that should be masked in logs
SENSITIVE_PATTERNS = [
    # Database URLs with credentials (postgresql://user:password@host/db)
    (
        re.compile(
            r"(postgresql(?:\+asyncpg)?|mysql|mongodb|redis)://"
            r"([^:]+):([^@]+)@",
            re.IGNORECASE
        ),
        r"\1://\2:***@"
    ),
    # Key-value pairs with sensitive keys (password=xxx, token: xxx, etc.)
    (
        re.compile(
            r"(password|secret|token|access_token|refresh_token|api_key|apikey|"
            r"authorization|cookie|credential|private_key|channel_secret|"
            r"channel_access_token|id_token|line_user_id|line_sub)\s*[:=]\s*['\"]?([^'\"\s&]+)['\"]?",
            re.IGNORECASE
        ),
        r"\1=***"
    ),
    # Bearer tokens in headers (including full JWT with dots)
    (
        re.compile(r"(Bearer\s+)([A-Za-z0-9\-_\.]+)", re.IGNORECASE),
        r"\1***"
    ),
    # JWT tokens standalone (eyJ...)
    (
        re.compile(r"\b(eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+)\b"),
        r"[JWT:***]"
    ),
    # URL query parameters with sensitive names
    (
        re.compile(
            r"([?&])(token|key|secret|password|api_key|apikey|access_token|APIKey)=([^&\s]+)",
            re.IGNORECASE
        ),
        r"\1\2=***"
    ),
    # Ragic API key in URL path (/api.php?key=xxx or similar)
    (
        re.compile(r"(ragic\.com/[^?]+\?)(APIKey|key)=([^&\s]+)", re.IGNORECASE),
        r"\1\2=***"
    ),
    # LINE User ID (U followed by 32 hex chars) - partial mask
    (
        re.compile(r"\b(U[a-f0-9]{8})([a-f0-9]{24})\b"),
        r"\1***"
    ),
    # Email addresses (partial mask: first 2 chars + *** + @domain)
    (
        re.compile(r"\b([a-zA-Z0-9._%+-]{2})([a-zA-Z0-9._%+-]*)(@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b"),
        r"\1***\3"
    ),
]


class SensitiveDataFormatter(logging.Formatter):
    """
    Custom log formatter that masks sensitive data.
    
    Automatically detects and masks:
    - Passwords, tokens, secrets, API keys
    - Authorization headers (Bearer tokens)
    - Sensitive URL query parameters
    - Email addresses (partial masking)
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record, masking any sensitive data."""
        # Get the original formatted message
        original_msg = super().format(record)
        
        # Apply all masking patterns
        masked_msg = original_msg
        for pattern, replacement in SENSITIVE_PATTERNS:
            masked_msg = pattern.sub(replacement, masked_msg)
        
        return masked_msg


def get_log_path() -> Path:
    """
    Get the path for log files.

    In headless mode, logs are stored in the project's logs directory.
    """
    project_root = Path(__file__).resolve().parent.parent
    logs_dir = project_root / "logs"

    # Create logs directory if it doesn't exist
    logs_dir.mkdir(exist_ok=True)

    return logs_dir / LOG_FILENAME


def setup_logging(log_level: int = logging.INFO) -> None:
    """
    Configure application logging with rotation.

    Args:
        log_level: The logging level (default: logging.INFO).
    """
    log_file_path = get_log_path()

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Formatter with sensitive data masking
    formatter = SensitiveDataFormatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # --- File Handler (Rotating) ---
    file_handler = RotatingFileHandler(
        filename=str(log_file_path),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Log initialization
    root_logger.info(f"Logging initialized. Log file: {log_file_path}")

    # Suppress noisy loggers
    logging.getLogger("watchfiles.main").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # Ensure uvicorn logs are suppressed, though they are usually handled by uvicorn config
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
