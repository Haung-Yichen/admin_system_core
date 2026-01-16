"""
Chatbot Routers Package.

Contains all API routers for the chatbot module.
"""

from modules.chatbot.routers.auth import router as auth_router
from modules.chatbot.routers.bot import router as bot_router
from modules.chatbot.routers.sop import router as sop_router

__all__ = [
    "auth_router",
    "bot_router",
    "sop_router",
]
