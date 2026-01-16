"""
Chatbot Core Package.

Contains configuration, security, and logging utilities.
"""

from modules.chatbot.core.config import ChatbotSettings, get_chatbot_settings
from modules.chatbot.core.security import (
    MagicLinkPayload,
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    create_magic_link_token,
    decode_magic_link_token,
)

__all__ = [
    "ChatbotSettings",
    "get_chatbot_settings",
    "MagicLinkPayload",
    "TokenError",
    "TokenExpiredError",
    "TokenInvalidError",
    "create_magic_link_token",
    "decode_magic_link_token",
]
