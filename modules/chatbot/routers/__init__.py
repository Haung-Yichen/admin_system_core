"""
Chatbot Routers Package.

Note: LINE webhook handling has been moved to the framework layer.
      The bot.py file now only contains Flex Message templates.
"""

from modules.chatbot.routers.bot import (
    create_auth_required_flex,
    create_sop_result_flex,
    create_no_result_flex,
)
from modules.chatbot.routers.sop import router as sop_router

__all__ = [
    "sop_router",
    "create_auth_required_flex",
    "create_sop_result_flex",
    "create_no_result_flex",
]
