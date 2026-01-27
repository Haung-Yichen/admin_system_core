"""
LINE Bot Flex Message Templates.

This module provides Flex Message templates for LINE Bot responses.
The actual webhook handling is now done by the framework at /webhook/line/{module_name}.

Note: The webhook endpoint has been moved to the framework layer (core/server.py).
      This file now only contains reusable message templates.
"""

from typing import Any


def create_auth_required_flex(line_user_id: str) -> dict[str, Any]:
    """
    Create a Flex Message bubble prompting user to authenticate.

    Args:
        line_user_id: LINE user ID for constructing the login URL.

    Returns:
        Flex Message bubble content.

    Note:
        This function creates a legacy login URL using the Messaging API userId.
        For LIFF-based auth, the frontend should use LINE ID Token's `sub` claim instead.
    """
    from core.app_context import ConfigLoader
    config_loader = ConfigLoader()
    config_loader.load()
    base_url = config_loader.get("server.base_url", "")
    login_url = f"{base_url}/auth/login?line_sub={line_user_id}"

    return {
        "type": "bubble",
        "hero": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "🔐", "size": "4xl", "align": "center"}
        ], "backgroundColor": "#00B900", "paddingAll": "20px"},
        "body": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "身份驗證", "weight": "bold",
                "size": "xl", "align": "center"},
            {"type": "text", "text": "請先驗證您的員工身份才能使用 SOP 查詢服務。",
                "wrap": True, "size": "sm", "margin": "lg"}
        ], "paddingAll": "20px"},
        "footer": {"type": "box", "layout": "vertical", "contents": [
            {"type": "button", "action": {"type": "uri", "label": "📧 驗證身份",
                                          "uri": login_url}, "style": "primary", "color": "#00B900"}
        ], "paddingAll": "15px"},
    }


def create_sop_result_flex(
    title: str,
    content: str,
    similarity: float,
    category: str | None = None,
) -> dict[str, Any]:
    """
    Create a Flex Message bubble displaying SOP search result.

    Args:
        title: SOP document title.
        content: SOP document content.
        similarity: Search similarity score (0.0 - 1.0).
        category: Optional document category.

    Returns:
        Flex Message bubble content.
    """
    max_len = 500
    display_content = content[:max_len] + \
        "..." if len(content) > max_len else content
    match_percent = round(similarity * 100)
    match_color = "#00B900" if similarity >= 0.8 else (
        "#FFA500" if similarity >= 0.6 else "#888888")

    contents: list[dict] = [
        {"type": "text", "text": title, "weight": "bold", "size": "lg", "wrap": True}]
    if category:
        contents.append({"type": "text", "text": f"📁 {category}",
                        "size": "xs", "color": "#888888", "margin": "sm"})
    contents.extend([
        {"type": "box", "layout": "baseline", "contents": [
            {"type": "text", "text": f"相符度 {match_percent}%",
                "size": "sm", "color": match_color, "weight": "bold"}
        ], "margin": "md"},
        {"type": "separator", "margin": "lg"},
        {"type": "text", "text": display_content,
            "wrap": True, "size": "sm", "margin": "lg"}
    ])

    return {
        "type": "bubble",
        "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "📋 SOP 查詢結果",
                "color": "#FFFFFF", "size": "md", "weight": "bold"}
        ], "backgroundColor": "#00B900", "paddingAll": "15px"},
        "body": {"type": "box", "layout": "vertical", "contents": contents, "paddingAll": "20px"},
    }


def create_no_result_flex(query: str) -> dict[str, Any]:
    """
    Create a Flex Message bubble when no SOP results are found.

    Args:
        query: The user's search query.

    Returns:
        Flex Message bubble content.
    """
    return {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "🔍", "size": "3xl", "align": "center"},
            {"type": "text", "text": "找不到相關 SOP", "weight": "bold",
                "size": "lg", "align": "center", "margin": "lg"},
            {"type": "separator", "margin": "lg"},
            {"type": "text", "text": f"您的查詢: {query}",
                "wrap": True, "size": "sm", "margin": "lg"},
            {"type": "text", "text": "請嘗試不同關鍵字", "wrap": True,
                "size": "sm", "color": "#888888", "margin": "md"}
        ], "paddingAll": "20px"},
    }


# =============================================================================
# DEPRECATED: The following code has been moved to the framework layer.
# =============================================================================
# The LINE webhook endpoint is now handled by:
#   - core/server.py: /webhook/line/{module_name}
#   - modules/chatbot/chatbot_module.py: handle_line_event()
#
# This allows the framework to handle signature verification and event
# dispatching, while modules focus on business logic only.
# =============================================================================
