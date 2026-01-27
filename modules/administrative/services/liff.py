"""
LIFF Management Service.

Provides programmatic creation and management of LINE LIFF Apps.
"""

import logging
from typing import Any

import httpx

from modules.administrative.core.config import AdminSettings, get_admin_settings

logger = logging.getLogger(__name__)


class LiffService:
    """
    Service for managing LINE LIFF Apps via API.
    
    LIFF Apps are created under a LINE Login Channel.
    Once created, the LIFF ID can be used to open web pages within LINE.
    """

    LINE_API_BASE = "https://api.line.me/liff/v1"

    def __init__(self, settings: AdminSettings | None = None) -> None:
        self._settings = settings or get_admin_settings()
        self._http_client: httpx.AsyncClient | None = None

    @property
    def _client(self) -> httpx.AsyncClient:
        """Lazy-initialized HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30),
                headers={
                    "Authorization": f"Bearer {self._settings.line_channel_access_token.get_secret_value()}",
                    "Content-Type": "application/json",
                },
            )
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def create_liff_app(
        self,
        endpoint_url: str,
        view_type: str = "full",
        description: str = "Administrative Leave Request Form",
    ) -> str | None:
        """
        Create a new LIFF App.
        
        Args:
            endpoint_url: The URL to load in the LIFF browser.
                Example: https://your-domain.com/api/administrative/liff/leave-form
            view_type: LIFF view size - "compact", "tall", or "full".
            description: Description for the LIFF App.
            
        Returns:
            str: LIFF ID if successful, None otherwise.
        """
        payload = {
            "view": {
                "type": view_type,
                "url": endpoint_url,
            },
            "description": description,
            "features": {
                "ble": False,
                "qrCode": False,
            },
            "permanentLinkPattern": "concat",
        }

        try:
            response = await self._client.post(
                f"{self.LINE_API_BASE}/apps",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            liff_id = result.get("liffId")
            logger.info(f"LIFF App created: {liff_id}")
            return liff_id
        except httpx.HTTPError as e:
            logger.error(f"Failed to create LIFF App: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

    async def list_liff_apps(self) -> list[dict[str, Any]]:
        """
        List all LIFF Apps.
        
        Returns:
            list: List of LIFF App objects.
        """
        try:
            response = await self._client.get(f"{self.LINE_API_BASE}/apps")
            response.raise_for_status()
            result = response.json()
            return result.get("apps", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to list LIFF Apps: {e}")
            return []

    async def update_liff_app(
        self,
        liff_id: str,
        endpoint_url: str,
        view_type: str = "full",
    ) -> bool:
        """
        Update an existing LIFF App.
        
        Args:
            liff_id: The LIFF ID to update.
            endpoint_url: New endpoint URL.
            view_type: LIFF view size.
            
        Returns:
            bool: True if successful.
        """
        payload = {
            "view": {
                "type": view_type,
                "url": endpoint_url,
            },
        }

        try:
            response = await self._client.put(
                f"{self.LINE_API_BASE}/apps/{liff_id}",
                json=payload,
            )
            response.raise_for_status()
            logger.info(f"LIFF App updated: {liff_id}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to update LIFF App: {e}")
            return False

    async def delete_liff_app(self, liff_id: str) -> bool:
        """
        Delete a LIFF App.
        
        Args:
            liff_id: The LIFF ID to delete.
            
        Returns:
            bool: True if successful.
        """
        try:
            response = await self._client.delete(
                f"{self.LINE_API_BASE}/apps/{liff_id}",
            )
            response.raise_for_status()
            logger.info(f"LIFF App deleted: {liff_id}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete LIFF App: {e}")
            return False


# Singleton
_liff_service: LiffService | None = None


def get_liff_service() -> LiffService:
    """Get singleton LiffService instance."""
    global _liff_service
    if _liff_service is None:
        _liff_service = LiffService()
    return _liff_service
