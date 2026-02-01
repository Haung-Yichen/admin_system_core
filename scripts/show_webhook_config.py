"""
Display Ragic Webhook Configuration.

Shows all registered sync services and their webhook URLs.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.ragic import get_sync_manager
from core.app_context import ConfigLoader

def main():
    # Load configuration
    config = ConfigLoader()
    config.load()
    
    base_url = config.get("server.base_url", "http://localhost:8000")
    webhook_secret = config.get("webhook.default_secret", "NOT_SET")
    
    # Get registered sync services
    sync_manager = get_sync_manager()
    services = sync_manager.list_services()
    
    print("=" * 80)
    print("RAGIC WEBHOOK CONFIGURATION")
    print("=" * 80)
    print()
    print(f"Server Base URL: {base_url}")
    print(f"Webhook Secret:  {'*' * 8 + webhook_secret[-4:] if len(webhook_secret) > 4 else 'NOT_SET'}")
    print()
    print("=" * 80)
    print("REGISTERED SYNC SERVICES")
    print("=" * 80)
    print()
    
    for service in services:
        webhook_url = f"{base_url}/api/webhooks/ragic?source={service['key']}"
        
        print(f"Service Key:    {service['key']}")
        print(f"Service Name:   {service['name']}")
        print(f"Module:         {service['module']}")
        print(f"Webhook URL:    {webhook_url}")
        print(f"Auto Sync:      {'Yes' if service.get('auto_sync_on_startup', False) else 'No'}")
        print("-" * 80)
    
    print()
    print("=" * 80)
    print("RAGIC CONFIGURATION STEPS")
    print("=" * 80)
    print()
    print("1. 登入 Ragic 後台")
    print("2. 進入對應的表單 (例如：使用者身份表 Page 13)")
    print("3. 點選「工具」→「表單工具」→「Webhook」")
    print("4. 新增 Webhook:")
    print("   - URL: 從上方列表複製對應的 Webhook URL")
    print("   - Method: POST")
    print("   - 觸發時機: 新增、修改、刪除")
    print("5. (Optional) 在 URL 後加上 &token=<secret> 進行簽章驗證")
    print()
    print("範例:")
    if services:
        example = services[0]
        example_url = f"{base_url}/api/webhooks/ragic?source={example['key']}"
        print(f"  {example_url}")
        if webhook_secret != "NOT_SET":
            print(f"  {example_url}&token={webhook_secret}")
    print()
    print("=" * 80)
    print("WEBHOOK AUTHENTICATION")
    print("=" * 80)
    print()
    print("Ragic Webhook 支援兩種認證方式:")
    print()
    print("方式 1: URL Token Parameter")
    print("  在 Webhook URL 後加上 &token=<secret>")
    print(f"  範例: /api/webhooks/ragic?source=core_user&token={webhook_secret}")
    print()
    print("方式 2: X-Hub-Signature-256 Header (推薦)")
    print("  Ragic 會自動計算 HMAC-SHA256 簽章並放在 Header 中")
    print("  框架會自動驗證簽章，無需額外設定")
    print()
    print("=" * 80)


if __name__ == "__main__":
    main()
