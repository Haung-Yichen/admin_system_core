"""
LINE Client - Pure HTTP communication with LINE API.
Only responsible for sending/receiving data, no message formatting.
"""
from typing import Any, Dict, List, Optional
import logging
import hmac
import hashlib
import base64

import httpx

from core.app_context import ConfigLoader


class LineClient:
    """
    Low-level LINE API client.
    Only handles HTTP communication and signature verification.
    
    Supports multi-account usage by allowing credentials to be passed
    directly on initialization (for module-specific bots) or loaded
    from ConfigLoader (for backward compatibility).
    """
    
    API_BASE = "https://api.line.me/v2/bot"
    
    def __init__(
        self, 
        config: ConfigLoader | None = None,
        *,
        channel_secret: str | None = None,
        access_token: str | None = None,
    ) -> None:
        """
        Initialize LINE client.
        
        Args:
            config: Optional ConfigLoader for loading credentials from global config.
            channel_secret: Direct channel secret (takes precedence over config).
            access_token: Direct access token (takes precedence over config).
        """
        self._logger = logging.getLogger(__name__)
        
        # Priority: direct params > config > empty
        if channel_secret is not None:
            self._channel_secret = channel_secret
        elif config is not None:
            self._channel_secret = config.get("line.channel_secret", "")
        else:
            self._channel_secret = ""
        
        if access_token is not None:
            self._access_token = access_token
        elif config is not None:
            self._access_token = config.get("line.channel_access_token", "")
        else:
            self._access_token = ""
        
        self._client = httpx.AsyncClient(timeout=30.0)
    
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json"
        }
    
    def is_configured(self) -> bool:
        """Check if credentials are set."""
        return bool(self._channel_secret and self._access_token)
    
    def verify_signature(self, body: bytes, signature: str) -> bool:
        """Verify LINE webhook signature."""
        if not self._channel_secret:
            return False
        
        expected = base64.b64encode(
            hmac.new(
                self._channel_secret.encode(),
                body,
                hashlib.sha256
            ).digest()
        ).decode()
        
        return hmac.compare_digest(signature, expected)
    
    async def post_reply(
        self, 
        reply_token: str, 
        messages: List[Dict[str, Any]]
    ) -> bool:
        """
        POST to /message/reply endpoint.
        
        Args:
            reply_token: Token from webhook event
            messages: Pre-formatted message objects
        """
        if not self.is_configured():
            self._logger.warning("LINE client not configured")
            return False
        
        try:
            resp = await self._client.post(
                f"{self.API_BASE}/message/reply",
                headers=self._headers(),
                json={"replyToken": reply_token, "messages": messages[:5]}
            )
            return resp.status_code == 200
        except Exception as e:
            self._logger.error(f"Reply failed: {e}")
            return False
    
    async def post_push(
        self, 
        to: str, 
        messages: List[Dict[str, Any]]
    ) -> bool:
        """
        POST to /message/push endpoint.
        
        Args:
            to: User/Group/Room ID
            messages: Pre-formatted message objects
        """
        if not self.is_configured():
            return False
        
        try:
            resp = await self._client.post(
                f"{self.API_BASE}/message/push",
                headers=self._headers(),
                json={"to": to, "messages": messages[:5]}
            )
            return resp.status_code == 200
        except Exception as e:
            self._logger.error(f"Push failed: {e}")
            return False
    
    async def post_multicast(
        self, 
        to: List[str], 
        messages: List[Dict[str, Any]]
    ) -> bool:
        """POST to /message/multicast endpoint."""
        if not self.is_configured():
            return False
        
        try:
            resp = await self._client.post(
                f"{self.API_BASE}/message/multicast",
                headers=self._headers(),
                json={"to": to[:500], "messages": messages[:5]}
            )
            return resp.status_code == 200
        except Exception as e:
            self._logger.error(f"Multicast failed: {e}")
            return False
    
    async def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """GET user profile from /profile/{userId}."""
        if not self.is_configured():
            return None
        
        try:
            resp = await self._client.get(
                f"{self.API_BASE}/profile/{user_id}",
                headers=self._headers()
            )
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            self._logger.error(f"Get profile failed: {e}")
            return None
    
    async def close(self) -> None:
        """Close HTTP client."""
        await self._client.aclose()
