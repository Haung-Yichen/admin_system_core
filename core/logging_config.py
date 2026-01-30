"""
Logging Configuration Module.

Provides centralized logging setup with rotating file handler.
Logs are saved to the project's logs directory (headless mode).
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


# --- Constants ---
LOG_FILENAME = "admin_system.log"
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


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

    # Formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

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
