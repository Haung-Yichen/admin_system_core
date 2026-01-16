"""
Echo Module - 範例插件，展示如何實作 IAppModule。
"""
from typing import Optional, Dict, Any
from core.interface import IAppModule
from core.app_context import AppContext


class EchoModule(IAppModule):
    """
    簡單的 Echo 模組範例。
    發送 "echo:你好世界" → 回傳 {"received": "你好世界"}
    """
    
    def get_module_name(self) -> str:
        return "echo"
    
    def on_entry(self, context: AppContext) -> None:
        context.log_event("Echo 模組已載入", "MODULE")
    
    def handle_event(self, context: AppContext, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        payload = event.get("parsed_payload", event.get("message", ""))
        context.log_event(f"Echo 收到: {payload}", "MODULE")
        return {"module": "echo", "received": payload, "status": "ok"}
    
    def get_menu_config(self) -> Dict[str, Any]:
        return {"label": "Echo 測試", "icon": "echo", "actions": []}
