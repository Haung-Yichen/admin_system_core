"""
AppContext - Dependency Injection Container.
Implements the Dependency Inversion Principle (DIP).
"""
from typing import Any, Dict, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from pathlib import Path
import os
import logging

from dotenv import load_dotenv

if TYPE_CHECKING:
    from services.line_client import LineClient
    from core.ragic import RagicService


@dataclass
class ConfigLoader:
    """Configuration loader from environment variables."""
    
    _config: Dict[str, Any] = field(default_factory=dict)
    
    def load(self, env_path: Optional[str] = None) -> None:
        """Load configuration from .env file."""
        if env_path:
            load_dotenv(env_path)
        else:
            # Try to find .env in project root
            project_root = Path(__file__).parent.parent
            env_file = project_root / ".env"
            if env_file.exists():
                load_dotenv(env_file)
        
        self._config = {
            "server": {
                "host": os.getenv("SERVER_HOST", "127.0.0.1"),
                "port": int(os.getenv("SERVER_PORT", "8000")),
                "base_url": os.getenv("BASE_URL", "")
            },
            "app": {
                "debug": os.getenv("APP_DEBUG", "true").lower() == "true",
                "log_level": os.getenv("APP_LOG_LEVEL", "INFO")
            },
            "database": {
                "url": os.getenv("DATABASE_URL", "")
            },
            "security": {
                "jwt_secret_key": os.getenv("JWT_SECRET_KEY", ""),
                "jwt_algorithm": os.getenv("JWT_ALGORITHM", "HS256"),
                "magic_link_expire_minutes": int(os.getenv("MAGIC_LINK_EXPIRE_MINUTES", "15"))
            },
            "email": {
                "host": os.getenv("SMTP_HOST", ""),
                "port": int(os.getenv("SMTP_PORT", "587")),
                "username": os.getenv("SMTP_USERNAME", ""),
                "password": os.getenv("SMTP_PASSWORD", ""),
                "from_email": os.getenv("SMTP_FROM_EMAIL", ""),
                "from_name": os.getenv("SMTP_FROM_NAME", "Admin System")
            },
            "vector": {
                "model_name": os.getenv("EMBEDDING_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2"),
                "dimension": int(os.getenv("EMBEDDING_DIMENSION", "384")),
                "top_k": int(os.getenv("SEARCH_TOP_K", "3")),
                "similarity_threshold": float(os.getenv("SEARCH_SIMILARITY_THRESHOLD", "0.3"))
            },
            "line": {
                "channel_id": os.getenv("LINE_CHANNEL_ID", ""),
                "channel_secret": os.getenv("LINE_CHANNEL_SECRET", ""),
                "channel_access_token": os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
            },
            "ragic": {
                "api_key": os.getenv("RAGIC_API_KEY", ""),
                "base_url": os.getenv("RAGIC_BASE_URL", "https://ap13.ragic.com"),
                "employee_sheet_path": os.getenv("RAGIC_EMPLOYEE_SHEET_PATH", "/HSIBAdmSys/ychn-test/11"),
                "field_email": os.getenv("RAGIC_FIELD_EMAIL", "1005977"),
                "field_name": os.getenv("RAGIC_FIELD_NAME", "1005975"),
                "field_door_access_id": os.getenv("RAGIC_FIELD_DOOR_ACCESS_ID", "1005983")
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation key."""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def is_line_configured(self) -> bool:
        """Check if LINE credentials are set."""
        return bool(
            self.get("line.channel_secret") and 
            self.get("line.channel_access_token")
        )
    
    def is_ragic_configured(self) -> bool:
        """Check if Ragic credentials are set."""
        return bool(
            self.get("ragic.api_key") and 
            self.get("ragic.base_url")
        )


class AppContext:
    """
    Application Context - Central Dependency Injection Container.
    """
    
    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._config_loader = ConfigLoader()
        self._config_loader.load()
        
        # Service instances (lazy initialization)
        self._line_client: Optional["LineClient"] = None
        self._ragic_service: Optional["RagicService"] = None
        
        # Event log for GUI display
        self._event_log: list[str] = []
        self._max_log_entries: int = 500
        
        # Runtime state
        self._server_running: bool = False
        self._server_port: int = self._config_loader.get("server.port", 8000)
    
    @property
    def config(self) -> ConfigLoader:
        """Access the configuration loader."""
        return self._config_loader
    
    @property
    def line_client(self) -> "LineClient":
        """Lazy initialization of LINE client."""
        if self._line_client is None:
            from services.line_client import LineClient
            self._line_client = LineClient(self._config_loader)
        return self._line_client
    
    @property
    def ragic_service(self) -> "RagicService":
        """Lazy initialization of Ragic service."""
        if self._ragic_service is None:
            from core.ragic import RagicService
            self._ragic_service = RagicService()
        return self._ragic_service
    
    def log_event(self, message: str, level: str = "INFO") -> None:
        """Log an event to both logger and event log."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}"
        
        self._event_log.append(formatted)
        if len(self._event_log) > self._max_log_entries:
            self._event_log = self._event_log[-self._max_log_entries:]
        
        self._logger.info(message)
    
    def get_event_log(self) -> list[str]:
        """Get the current event log."""
        return self._event_log.copy()
    
    def set_server_status(self, running: bool, port: int = 8000) -> None:
        """Update server status."""
        self._server_running = running
        self._server_port = port
    
    def get_server_status(self) -> tuple[bool, int]:
        """Get current server status."""
        return (self._server_running, self._server_port)
