"""
Logging Configuration Module.
Provides centralized logging setup with rotating file handler.
Logs are saved to the user's Desktop.
"""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from core.app_context import AppContext


# --- Constants ---
LOG_FILENAME = "admin_system.log"
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
GUI_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(message)s"
GUI_DATE_FORMAT = "%H:%M:%S"


class GUIHandler(logging.Handler):
    """
    Custom logging handler that sends log messages to AppContext for GUI display.
    """
    
    _instance: Optional["GUIHandler"] = None
    _context: Optional["AppContext"] = None
    
    def __init__(self) -> None:
        super().__init__()
        self.setFormatter(logging.Formatter(GUI_LOG_FORMAT, datefmt=GUI_DATE_FORMAT))
    
    @classmethod
    def set_context(cls, context: "AppContext") -> None:
        """Set the AppContext to receive log messages."""
        cls._context = context
    
    def emit(self, record: logging.LogRecord) -> None:
        """Send log record to AppContext._event_log."""
        if GUIHandler._context is None:
            return
        
        try:
            msg = self.format(record)
            # Append to AppContext event log directly
            log_list = GUIHandler._context._event_log
            log_list.append(msg)
            
            # Trim if exceeds max
            max_entries = GUIHandler._context._max_log_entries
            if len(log_list) > max_entries:
                del log_list[:len(log_list) - max_entries]
        except Exception:
            self.handleError(record)


def get_desktop_path() -> Path:
    """
    Get the path to the user's Desktop.
    Derives from the project root's parent directory structure.
    """
    # Project is at: c:\Users\jerem\OneDrive\桌面\admin_system_core
    # Desktop is at: c:\Users\jerem\OneDrive\桌面
    project_root = Path(__file__).resolve().parent.parent
    desktop_path = project_root.parent
    return desktop_path


def setup_logging(log_level: int = logging.INFO) -> None:
    """
    Configure application logging with rotation.
    
    Args:
        log_level: The logging level (default: logging.INFO).
    """
    desktop_path = get_desktop_path()
    log_file_path = desktop_path / LOG_FILENAME
    
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
        encoding="utf-8"
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # --- Console Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # --- GUI Handler (for UI log display) ---
    gui_handler = GUIHandler()
    gui_handler.setLevel(log_level)
    root_logger.addHandler(gui_handler)
    
    # Log initialization
    root_logger.info(f"Logging initialized. Log file: {log_file_path}")
