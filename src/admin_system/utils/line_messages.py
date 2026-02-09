"""
LINE Message Builders - Pure utility functions for message formatting.
Stateless, no dependencies, just data transformation.
"""
from typing import Any, Dict, List, Optional


def text(content: str) -> Dict[str, str]:
    """Create a text message object."""
    return {"type": "text", "text": content}


def sticker(package_id: str, sticker_id: str) -> Dict[str, str]:
    """Create a sticker message object."""
    return {
        "type": "sticker",
        "packageId": package_id,
        "stickerId": sticker_id
    }


def image(original_url: str, preview_url: Optional[str] = None) -> Dict[str, str]:
    """Create an image message object."""
    return {
        "type": "image",
        "originalContentUrl": original_url,
        "previewImageUrl": preview_url or original_url
    }


def video(original_url: str, preview_url: str) -> Dict[str, str]:
    """Create a video message object."""
    return {
        "type": "video",
        "originalContentUrl": original_url,
        "previewImageUrl": preview_url
    }


def audio(original_url: str, duration_ms: int) -> Dict[str, Any]:
    """Create an audio message object."""
    return {
        "type": "audio",
        "originalContentUrl": original_url,
        "duration": duration_ms
    }


def location(
    title: str, 
    address: str, 
    latitude: float, 
    longitude: float
) -> Dict[str, Any]:
    """Create a location message object."""
    return {
        "type": "location",
        "title": title,
        "address": address,
        "latitude": latitude,
        "longitude": longitude
    }


# ===== Quick Reply =====

def quick_reply_action(label: str, text: str) -> Dict[str, Any]:
    """Create a quick reply action item."""
    return {
        "type": "action",
        "action": {"type": "message", "label": label, "text": text}
    }


def with_quick_reply(
    message: Dict[str, Any], 
    items: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Attach quick reply buttons to any message."""
    message["quickReply"] = {"items": items}
    return message


# ===== Templates =====

def confirm_template(
    alt_text: str,
    body_text: str,
    yes_label: str,
    yes_data: str,
    no_label: str,
    no_data: str
) -> Dict[str, Any]:
    """Create a confirm template message."""
    return {
        "type": "template",
        "altText": alt_text,
        "template": {
            "type": "confirm",
            "text": body_text,
            "actions": [
                {"type": "message", "label": yes_label, "text": yes_data},
                {"type": "message", "label": no_label, "text": no_data}
            ]
        }
    }


def buttons_template(
    alt_text: str,
    title: str,
    body_text: str,
    actions: List[Dict[str, Any]],
    thumbnail_url: Optional[str] = None
) -> Dict[str, Any]:
    """Create a buttons template message."""
    template: Dict[str, Any] = {
        "type": "buttons",
        "title": title,
        "text": body_text,
        "actions": actions[:4]  # Max 4 actions
    }
    if thumbnail_url:
        template["thumbnailImageUrl"] = thumbnail_url
    
    return {
        "type": "template",
        "altText": alt_text,
        "template": template
    }


def carousel_template(
    alt_text: str,
    columns: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Create a carousel template message."""
    return {
        "type": "template",
        "altText": alt_text,
        "template": {
            "type": "carousel",
            "columns": columns[:10]  # Max 10 columns
        }
    }


def carousel_column(
    title: str,
    body_text: str,
    actions: List[Dict[str, Any]],
    thumbnail_url: Optional[str] = None
) -> Dict[str, Any]:
    """Create a column for carousel template."""
    column: Dict[str, Any] = {
        "title": title,
        "text": body_text,
        "actions": actions[:3]  # Max 3 actions per column
    }
    if thumbnail_url:
        column["thumbnailImageUrl"] = thumbnail_url
    return column


# ===== Actions =====

def action_message(label: str, text: str) -> Dict[str, str]:
    """Create a message action."""
    return {"type": "message", "label": label, "text": text}


def action_uri(label: str, uri: str) -> Dict[str, str]:
    """Create a URI action."""
    return {"type": "uri", "label": label, "uri": uri}


def action_postback(
    label: str, 
    data: str, 
    display_text: Optional[str] = None
) -> Dict[str, Any]:
    """Create a postback action."""
    action: Dict[str, Any] = {
        "type": "postback", 
        "label": label, 
        "data": data
    }
    if display_text:
        action["displayText"] = display_text
    return action
