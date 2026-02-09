"""
LINE Service for Chatbot Module.

Provides a module-specific LINE client using chatbot configuration.
This wraps the core LineClient with chatbot-specific credentials.
"""

import logging
from typing import Any, Dict, List

from core.line_client import LineClient
from modules.chatbot.core.config import get_chatbot_settings


logger = logging.getLogger(__name__)


class LineService:
    """
    LINE service for the chatbot module.
    
    Uses module-specific credentials from chatbot settings.
    """
    
    def __init__(self) -> None:
        settings = get_chatbot_settings()
        self._client = LineClient(
            channel_secret=settings.line_channel_secret.get_secret_value(),
            access_token=settings.line_channel_access_token.get_secret_value(),
        )
    
    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify LINE webhook signature."""
        return self._client.verify_signature(body, signature)
    
    def is_configured(self) -> bool:
        """Check if LINE credentials are configured."""
        return self._client.is_configured()
    
    async def reply(self, reply_token: str, messages: List[Dict[str, Any]]) -> bool:
        """Send reply message."""
        return await self._client.post_reply(reply_token, messages)
    
    async def push(self, to: str, messages: List[Dict[str, Any]]) -> bool:
        """Send push message."""
        return await self._client.post_push(to, messages)
    
    async def get_profile(self, user_id: str) -> Dict[str, Any] | None:
        """Get user profile."""
        return await self._client.get_profile(user_id)
    
    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.close()


# Singleton
_line_service: LineService | None = None


def get_line_service() -> LineService:
    """Get singleton instance of LineService."""
    global _line_service
    if _line_service is None:
        _line_service = LineService()
    return _line_service
