"""
Modules package - 在此放置你的自訂插件。

每個模組必須實作 IAppModule 介面：
- get_module_name() -> str
- on_entry(context: AppContext)
- handle_event(context: AppContext, event: dict)
- get_menu_config() -> dict (可選)
"""
