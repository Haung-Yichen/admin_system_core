"""
LINE Setup Script.

Automatically creates LIFF App and Rich Menu for the Administrative module.
Run this script after configuring LINE credentials in .env.

Usage:
    python -m modules.administrative.scripts.setup_line
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


async def setup_line():
    """Setup LIFF App and Rich Menu."""
    from core.app_context import ConfigLoader
    from modules.administrative.core.config import get_admin_settings
    from modules.administrative.services.liff import LiffService
    from modules.administrative.services.rich_menu import RichMenuService

    print("=" * 60)
    print("LINE Setup for Administrative Module")
    print("=" * 60)

    # Load config
    config_loader = ConfigLoader()
    config_loader.load()
    base_url = config_loader.get("server.base_url", "")
    
    if not base_url:
        print("❌ ERROR: BASE_URL not configured in .env")
        return

    settings = get_admin_settings()
    
    # Check credentials
    try:
        secret = settings.line_channel_secret.get_secret_value()
        token = settings.line_channel_access_token.get_secret_value()
        if secret == "your_channel_secret_here" or token == "your_access_token_here":
            print("❌ ERROR: Please configure ADMIN_LINE_CHANNEL_SECRET and ADMIN_LINE_CHANNEL_ACCESS_TOKEN in .env")
            return
    except Exception as e:
        print(f"❌ ERROR: Failed to load LINE credentials: {e}")
        return

    print(f"📍 Base URL: {base_url}")
    print()

    # =========================================================================
    # Step 1: LIFF App Configuration (Manual Step)
    # =========================================================================
    print("📱 Step 1: LIFF App Configuration")
    print("   NOTE: LIFF Apps must be created under a 'LINE Login' Channel,")
    print("   but the credentials provided are for a 'Messaging API' Channel.")
    print("   Therefore, we cannot create the LIFF App programmatically using these credentials.")
    print()
    
    endpoint_url = f"{base_url}/api/administrative/liff/leave-form"
    print(f"   👉 Please create a LIFF App manually in LINE Developers Console:")
    print(f"      1. Go to your LINE Login Channel")
    print(f"      2. Create a LIFF App")
    print(f"      3. Set Endpoint URL to: {endpoint_url}")
    print(f"      4. Set Scope to: profile, openid")
    print(f"      5. Copy the LIFF ID and paste it into .env:")
    print(f"         ADMIN_LINE_LIFF_ID_LEAVE=your_liff_id")
    print()

    # =========================================================================
    # Step 2: Create Rich Menu
    # =========================================================================
    print("📋 Step 2: Creating Rich Menu...")
    
    rich_menu_service = RichMenuService(settings)
    image_path = Path(__file__).parent.parent / "static" / "rich_menu_final.jpg"
    
    try:
        # Check if image exists
        if not image_path.exists():
            print(f"   ⚠️ Rich Menu image not found: {image_path}")
            print("   Please run 'python -m modules.administrative.scripts.process_image' first.")
        else:
            # Create rich menu
            menu_id = await rich_menu_service.create_rich_menu()
            
            if menu_id:
                print(f"   ✅ Created Rich Menu: {menu_id}")
                
                # Upload image
                success = await rich_menu_service.upload_menu_image(menu_id, image_path)
                if success:
                    print("   ✅ Uploaded menu image")
                    
                    # Set as default
                    success = await rich_menu_service.set_default_menu(menu_id)
                    if success:
                        print("   ✅ Set as default menu for all users")
                    else:
                        print("   ❌ Failed to set as default")
                else:
                    print("   ❌ Failed to upload image")
                    # Cleanup if upload fails
                    # await rich_menu_service.delete_rich_menu(menu_id)
            else:
                print("   ❌ Failed to create Rich Menu")
                
    except Exception as e:
        print(f"   ❌ Error: {e}")
    finally:
        await rich_menu_service.close()

    print()
    print("=" * 60)
    print("Setup Complete!")
    print("=" * 60)
    
    print()
    print("📋 Next Steps:")
    print("   1. Create LIFF App manually as shown above")
    print("   2. Update .env: ADMIN_LINE_LIFF_ID_LEAVE=your_liff_id")
    print("   3. Restart the server")
    print("   4. Test by clicking '請假申請' in LINE")


if __name__ == "__main__":
    asyncio.run(setup_line())
