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
                        "type": "postback",
                        "data": "action=coming_soon&feature=overtime",
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
                        "type": "postback",
                        "data": "action=coming_soon&feature=expense",
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
                        "type": "postback",
                        "data": "action=coming_soon&feature=approval",
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
                        "type": "postback",
                        "data": "action=coming_soon&feature=announcement",
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
                        "type": "postback",
                        "data": "action=coming_soon&feature=more",
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

    def _compress_image(
        self, 
        image_path: Path, 
        target_width: int = 2500,
        target_height: int = 1686,
        max_size_bytes: int = 1024 * 1024
    ) -> bytes:
        """
        壓縮並調整圖片尺寸以符合 LINE Rich Menu 要求。
        
        LINE 要求：
        - 圖片尺寸必須與選單定義的 size 完全一致
        - 檔案大小不超過 1MB
        - 支援 PNG 和 JPEG 格式
        
        Args:
            image_path: 原始圖片路徑
            target_width: 目標寬度（預設 2500）
            target_height: 目標高度（預設 1686）
            max_size_bytes: 最大檔案大小（預設 1MB）
            
        Returns:
            bytes: 處理後的圖片資料
        """
        from PIL import Image
        import io
        
        img = Image.open(image_path)
        logger.info(f"Original image size: {img.size}, mode: {img.mode}")
        
        # 確保是 RGB 模式（JPEG 不支援 RGBA）
        if img.mode in ('RGBA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[3] if len(img.split()) == 4 else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # 調整尺寸到目標大小（LINE 要求尺寸必須完全一致）
        if img.size != (target_width, target_height):
            logger.info(f"Resizing image from {img.size} to {target_width}x{target_height}")
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        # 從高品質開始嘗試壓縮
        quality = 95
        while quality >= 20:
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=quality, optimize=True)
            image_data = buffer.getvalue()
            
            size_kb = len(image_data) / 1024
            logger.info(f"Compressed image: quality={quality}, size={size_kb:.1f}KB")
            
            if len(image_data) <= max_size_bytes:
                return image_data
            
            quality -= 5
        
        # 如果還是太大，嘗試更低品質
        logger.warning("Image still too large at minimum quality")
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=15, optimize=True)
        return buffer.getvalue()

    async def upload_menu_image(
        self, rich_menu_id: str, image_path: str | Path
    ) -> bool:
        """
        Upload an image for the rich menu.
        
        會自動壓縮圖片以符合 LINE 的 1MB 限制。
        
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

            # 檢查檔案大小，如果超過 1MB 則壓縮
            file_size = image_path.stat().st_size
            max_size = 1024 * 1024  # 1MB
            
            if file_size > max_size:
                logger.info(f"Image size ({file_size/1024:.1f}KB) exceeds 1MB limit, compressing...")
                image_data = self._compress_image(image_path, max_size_bytes=max_size)
                content_type = "image/jpeg"  # 壓縮後都是 JPEG
            else:
                # 即使檔案小於 1MB，也需要確保尺寸正確（2500x1686）
                logger.info(f"Image size OK ({file_size/1024:.1f}KB), checking dimensions...")
                image_data = self._compress_image(image_path, max_size_bytes=max_size)
                content_type = "image/jpeg"

            logger.info(f"Uploading image: {len(image_data)/1024:.1f}KB as {content_type}")
            
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

    async def setup_and_activate_menu(
        self, image_path: str | Path | None = None
    ) -> bool:
        """
        完整設定並啟用 Rich Menu。
        
        流程：
            1. 刪除所有現有的 Rich Menu
            2. 建立新的 Rich Menu
            3. 上傳選單圖片
            4. 設為預設選單
        
        Args:
            image_path: 選單圖片路徑。若未指定則使用預設路徑。
            
        Returns:
            bool: 成功返回 True。
        """
        # 預設圖片路徑
        if image_path is None:
            image_path = Path(__file__).parent.parent / "static" / "rich_menu_final.png"
        
        image_path = Path(image_path)
        if not image_path.exists():
            logger.error(f"Rich menu image not found: {image_path}")
            return False
        
        logger.info("Starting Rich Menu setup...")
        
        try:
            # Step 1: 刪除所有現有的 Rich Menu
            existing_menus = await self.list_rich_menus()
            if existing_menus:
                logger.info(f"Deleting {len(existing_menus)} existing rich menus...")
                for menu in existing_menus:
                    menu_id = menu.get("richMenuId")
                    if menu_id:
                        await self.delete_rich_menu(menu_id)
            
            # Step 2: 建立新的 Rich Menu
            rich_menu_id = await self.create_rich_menu()
            if not rich_menu_id:
                logger.error("Failed to create rich menu")
                return False
            
            # Step 3: 上傳選單圖片
            upload_success = await self.upload_menu_image(rich_menu_id, image_path)
            if not upload_success:
                logger.error("Failed to upload rich menu image")
                await self.delete_rich_menu(rich_menu_id)
                return False
            
            # Step 4: 設為預設選單
            set_default_success = await self.set_default_menu(rich_menu_id)
            if not set_default_success:
                logger.error("Failed to set rich menu as default")
                return False
            
            logger.info(f"Rich Menu setup completed successfully! Menu ID: {rich_menu_id}")
            return True
            
        except Exception as e:
            logger.error(f"Rich Menu setup failed: {e}")
            return False


# Singleton
_rich_menu_service: RichMenuService | None = None


def get_rich_menu_service() -> RichMenuService:
    """Get singleton RichMenuService instance."""
    global _rich_menu_service
    if _rich_menu_service is None:
        _rich_menu_service = RichMenuService()
    return _rich_menu_service
