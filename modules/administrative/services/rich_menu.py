"""
Rich Menu Service.

Provides programmatic creation and management of LINE Rich Menus.
"""

import logging
from pathlib import Path
from typing import Any

import httpx

from modules.administrative.core.config import AdminSettings, get_admin_settings

logger = logging.getLogger(__name__)


class RichMenuService:
    """
    Service for managing LINE Rich Menus.
    
    Provides methods to:
        - Create rich menu structure
        - Upload menu image
        - Set as default menu
        - Link/unlink menus to users
    """

    LINE_API_BASE = "https://api.line.me/v2/bot"

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

    def _get_menu_definition(self) -> dict[str, Any]:
        """
        Get the Rich Menu JSON definition.
        
        Layout: 2500x1686 (full size), 2 rows x 3 columns
        
        Returns:
            dict: Rich Menu structure for LINE API.
        """
        liff_id = self._settings.line_liff_id_leave
        liff_uri = f"line://app/{liff_id}" if liff_id else "https://line.me"

        # Calculate button areas (2500x1686, 2 rows x 3 columns)
        # Header is approximately top 200px, remaining 1486px for buttons
        header_height = 200
        button_width = 2500 // 3  # ~833
        button_height = (1686 - header_height) // 2  # ~743

        return {
            "size": {"width": 2500, "height": 1686},
            "selected": True,
            "name": "HSIB Admin Menu",
            "chatBarText": "選單",
            "areas": [
                # Row 1
                {
                    "bounds": {
                        "x": 0,
                        "y": header_height,
                        "width": button_width,
                        "height": button_height,
                    },
                    "action": {"type": "uri", "uri": liff_uri, "label": "請假申請"},
                },
                {
                    "bounds": {
                        "x": button_width,
                        "y": header_height,
                        "width": button_width,
                        "height": button_height,
                    },
                    "action": {
                        "type": "message",
                        "text": "⏰ 加班申請功能開發中",
                        "label": "加班申請",
                    },
                },
                {
                    "bounds": {
                        "x": button_width * 2,
                        "y": header_height,
                        "width": button_width,
                        "height": button_height,
                    },
                    "action": {
                        "type": "message",
                        "text": "💰 費用報銷功能開發中",
                        "label": "費用報銷",
                    },
                },
                # Row 2
                {
                    "bounds": {
                        "x": 0,
                        "y": header_height + button_height,
                        "width": button_width,
                        "height": button_height,
                    },
                    "action": {
                        "type": "message",
                        "text": "✅ 簽核進度功能開發中",
                        "label": "簽核進度",
                    },
                },
                {
                    "bounds": {
                        "x": button_width,
                        "y": header_height + button_height,
                        "width": button_width,
                        "height": button_height,
                    },
                    "action": {
                        "type": "message",
                        "text": "📢 公告查詢功能開發中",
                        "label": "公告查詢",
                    },
                },
                {
                    "bounds": {
                        "x": button_width * 2,
                        "y": header_height + button_height,
                        "width": button_width,
                        "height": button_height,
                    },
                    "action": {
                        "type": "message",
                        "text": "⚙️ 更多功能開發中",
                        "label": "更多功能",
                    },
                },
            ],
        }

    async def create_rich_menu(self) -> str | None:
        """
        Create a new rich menu.
        
        Returns:
            str: Rich menu ID if successful, None otherwise.
        """
        try:
            menu_def = self._get_menu_definition()
            response = await self._client.post(
                f"{self.LINE_API_BASE}/richmenu",
                json=menu_def,
            )
            response.raise_for_status()
            result = response.json()
            rich_menu_id = result.get("richMenuId")
            logger.info(f"Rich menu created: {rich_menu_id}")
            return rich_menu_id
        except httpx.HTTPError as e:
            logger.error(f"Failed to create rich menu: {e}")
            return None

    async def upload_menu_image(
        self, rich_menu_id: str, image_path: str | Path
    ) -> bool:
        """
        Upload an image for the rich menu.
        
        Args:
            rich_menu_id: The rich menu ID from create_rich_menu().
            image_path: Path to the menu image (PNG or JPEG).
            
        Returns:
            bool: True if successful.
        """
        try:
            image_path = Path(image_path)
            if not image_path.exists():
                logger.error(f"Image not found: {image_path}")
                return False

            # Determine content type
            suffix = image_path.suffix.lower()
            content_type = "image/png" if suffix == ".png" else "image/jpeg"

            with open(image_path, "rb") as f:
                image_data = f.read()

            response = await self._client.post(
                f"https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content",
                content=image_data,
                headers={
                    "Authorization": f"Bearer {self._settings.line_channel_access_token.get_secret_value()}",
                    "Content-Type": content_type,
                },
            )
            response.raise_for_status()
            logger.info(f"Rich menu image uploaded for: {rich_menu_id}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to upload rich menu image: {e}")
            return False

    async def set_default_menu(self, rich_menu_id: str) -> bool:
        """
        Set a rich menu as the default for all users.
        
        Args:
            rich_menu_id: The rich menu ID to set as default.
            
        Returns:
            bool: True if successful.
        """
        try:
            response = await self._client.post(
                f"{self.LINE_API_BASE}/user/all/richmenu/{rich_menu_id}",
            )
            response.raise_for_status()
            logger.info(f"Rich menu set as default: {rich_menu_id}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to set default rich menu: {e}")
            return False

    async def delete_rich_menu(self, rich_menu_id: str) -> bool:
        """
        Delete a rich menu.
        
        Args:
            rich_menu_id: The rich menu ID to delete.
            
        Returns:
            bool: True if successful.
        """
        try:
            response = await self._client.delete(
                f"{self.LINE_API_BASE}/richmenu/{rich_menu_id}",
            )
            response.raise_for_status()
            logger.info(f"Rich menu deleted: {rich_menu_id}")
            return True
        except httpx.HTTPError as e:
            logger.error(f"Failed to delete rich menu: {e}")
            return False

    async def list_rich_menus(self) -> list[dict]:
        """
        List all rich menus.
        
        Returns:
            list: List of rich menu objects.
        """
        try:
            response = await self._client.get(
                f"{self.LINE_API_BASE}/richmenu/list",
            )
            response.raise_for_status()
            result = response.json()
            return result.get("richmenus", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to list rich menus: {e}")
            return []


# Singleton
_rich_menu_service: RichMenuService | None = None


def get_rich_menu_service() -> RichMenuService:
    """Get singleton RichMenuService instance."""
    global _rich_menu_service
    if _rich_menu_service is None:
        _rich_menu_service = RichMenuService()
    return _rich_menu_service
