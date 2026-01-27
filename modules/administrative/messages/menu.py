"""
Administrative Module LINE Flex Message Templates.

Contains reusable Flex Message templates for LINE Bot integration.
"""

from typing import Any

from modules.administrative.core.config import get_admin_settings


def create_admin_menu_flex() -> dict[str, Any]:
    """
    Create the Administrative Module main menu Flex Message.
    
    Layout: 2x3 grid with 6 buttons
    - Button 1: Leave Request (active)
    - Buttons 2-6: Coming Soon (disabled/greyed)
    
    Returns:
        Flex Message bubble content.
    """
    settings = get_admin_settings()
    liff_id = settings.line_liff_id_leave
    
    # LIFF URL or fallback message
    leave_uri = f"line://app/{liff_id}" if liff_id else "https://line.me"
    
    # Button styles
    active_style = {
        "backgroundColor": "#06C755",  # LINE Green
        "color": "#FFFFFF",
    }
    disabled_style = {
        "backgroundColor": "#E0E0E0",  # Grey
        "color": "#9E9E9E",
    }
    
    def create_button(
        label: str,
        emoji: str,
        action: dict[str, Any],
        is_active: bool = True,
    ) -> dict[str, Any]:
        """Create a single menu button."""
        style = active_style if is_active else disabled_style
        
        return {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": emoji,
                    "size": "xxl",
                    "align": "center",
                },
                {
                    "type": "text",
                    "text": label,
                    "size": "sm",
                    "align": "center",
                    "margin": "sm",
                    "weight": "bold",
                    "color": style["color"],
                },
            ],
            "backgroundColor": style["backgroundColor"],
            "cornerRadius": "lg",
            "paddingAll": "15px",
            "action": action,
            "flex": 1,
        }
    
    # Row 1: Leave Request + Overtime
    row1 = {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            create_button(
                label="請假申請",
                emoji="📅",
                action={"type": "uri", "uri": leave_uri},
                is_active=True,
            ),
            {"type": "separator", "margin": "sm"},
            create_button(
                label="加班申請",
                emoji="⏰",
                action={"type": "postback", "data": "action=coming_soon&feature=overtime"},
                is_active=False,
            ),
        ],
        "spacing": "sm",
    }
    
    # Row 2: Expense + Approval
    row2 = {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            create_button(
                label="費用報銷",
                emoji="💰",
                action={"type": "postback", "data": "action=coming_soon&feature=expense"},
                is_active=False,
            ),
            {"type": "separator", "margin": "sm"},
            create_button(
                label="簽核進度",
                emoji="✅",
                action={"type": "postback", "data": "action=coming_soon&feature=approval"},
                is_active=False,
            ),
        ],
        "spacing": "sm",
    }
    
    # Row 3: Announcement + More
    row3 = {
        "type": "box",
        "layout": "horizontal",
        "contents": [
            create_button(
                label="公告查詢",
                emoji="📢",
                action={"type": "postback", "data": "action=coming_soon&feature=announcement"},
                is_active=False,
            ),
            {"type": "separator", "margin": "sm"},
            create_button(
                label="更多功能",
                emoji="⚙️",
                action={"type": "postback", "data": "action=coming_soon&feature=more"},
                is_active=False,
            ),
        ],
        "spacing": "sm",
    }
    
    return {
        "type": "bubble",
        "size": "mega",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "📋 行政作業模組",
                    "color": "#FFFFFF",
                    "size": "lg",
                    "weight": "bold",
                },
                {
                    "type": "text",
                    "text": "Administrative Module",
                    "color": "#FFFFFF99",
                    "size": "xs",
                    "margin": "xs",
                },
            ],
            "backgroundColor": "#1A1A2E",
            "paddingAll": "20px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                row1,
                {"type": "separator", "margin": "md"},
                row2,
                {"type": "separator", "margin": "md"},
                row3,
            ],
            "paddingAll": "15px",
            "spacing": "md",
            "backgroundColor": "#F5F5F5",
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "💡 點擊上方按鈕開始使用",
                    "size": "xs",
                    "color": "#888888",
                    "align": "center",
                },
            ],
            "paddingAll": "10px",
        },
    }


def create_coming_soon_flex(feature_name: str) -> dict[str, Any]:
    """
    Create a "Coming Soon" response Flex Message.
    
    Args:
        feature_name: Name of the feature that's coming soon.
        
    Returns:
        Flex Message bubble content.
    """
    feature_labels = {
        "overtime": "加班申請",
        "expense": "費用報銷",
        "approval": "簽核進度",
        "announcement": "公告查詢",
        "more": "更多功能",
    }
    
    label = feature_labels.get(feature_name, feature_name)
    
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🚧",
                    "size": "4xl",
                    "align": "center",
                },
                {
                    "type": "text",
                    "text": "功能開發中",
                    "weight": "bold",
                    "size": "xl",
                    "align": "center",
                    "margin": "lg",
                },
                {
                    "type": "separator",
                    "margin": "lg",
                },
                {
                    "type": "text",
                    "text": f"「{label}」功能即將推出",
                    "wrap": True,
                    "size": "sm",
                    "align": "center",
                    "margin": "lg",
                    "color": "#666666",
                },
                {
                    "type": "text",
                    "text": "敬請期待！",
                    "size": "sm",
                    "align": "center",
                    "margin": "md",
                    "color": "#888888",
                },
            ],
            "paddingAll": "25px",
        },
    }


def create_auth_required_flex(line_user_id: str) -> dict[str, Any]:
    """
    Create authentication required Flex Message for Administrative module.
    
    Args:
        line_user_id: LINE user ID for constructing the login URL.
        
    Returns:
        Flex Message bubble content.
    """
    from core.app_context import ConfigLoader
    
    config_loader = ConfigLoader()
    config_loader.load()
    base_url = config_loader.get("server.base_url", "")
    login_url = f"{base_url}/auth/login?line_id={line_user_id}"
    
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "🔐",
                    "size": "4xl",
                    "align": "center",
                },
            ],
            "backgroundColor": "#1A1A2E",
            "paddingAll": "25px",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "text",
                    "text": "身份驗證",
                    "weight": "bold",
                    "size": "xl",
                    "align": "center",
                },
                {
                    "type": "text",
                    "text": "請先驗證您的員工身份才能使用行政作業功能。",
                    "wrap": True,
                    "size": "sm",
                    "margin": "lg",
                    "align": "center",
                    "color": "#666666",
                },
            ],
            "paddingAll": "20px",
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "action": {
                        "type": "uri",
                        "label": "📧 驗證身份",
                        "uri": login_url,
                    },
                    "style": "primary",
                    "color": "#1A1A2E",
                },
            ],
            "paddingAll": "15px",
        },
    }
