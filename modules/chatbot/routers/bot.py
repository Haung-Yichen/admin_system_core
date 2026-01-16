"""
LINE Bot Webhook Router.

Handles LINE webhook events and message routing.
"""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from modules.chatbot.core.config import get_chatbot_settings
from modules.chatbot.db import get_db_session
from modules.chatbot.services import (
    AuthService,
    VectorService,
    get_auth_service,
    get_line_service,
    get_vector_service,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bot", tags=["LINE Bot"])


def create_auth_required_flex(line_user_id: str) -> dict[str, Any]:
    from core.app_context import ConfigLoader
    config_loader = ConfigLoader()
    config_loader.load()
    base_url = config_loader.get("server.base_url", "")
    login_url = f"{base_url}/auth/login?line_id={line_user_id}"
    
    return {
        "type": "bubble",
        "hero": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "🔐", "size": "4xl", "align": "center"}
        ], "backgroundColor": "#00B900", "paddingAll": "20px"},
        "body": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "身份驗證", "weight": "bold", "size": "xl", "align": "center"},
            {"type": "text", "text": "請先驗證您的員工身份才能使用 SOP 查詢服務。", "wrap": True, "size": "sm", "margin": "lg"}
        ], "paddingAll": "20px"},
        "footer": {"type": "box", "layout": "vertical", "contents": [
            {"type": "button", "action": {"type": "uri", "label": "📧 驗證身份", "uri": login_url}, "style": "primary", "color": "#00B900"}
        ], "paddingAll": "15px"},
    }


def create_sop_result_flex(title: str, content: str, similarity: float, category: str | None = None) -> dict[str, Any]:
    max_len = 500
    display_content = content[:max_len] + "..." if len(content) > max_len else content
    match_percent = round(similarity * 100)
    match_color = "#00B900" if similarity >= 0.8 else ("#FFA500" if similarity >= 0.6 else "#888888")
    
    contents: list[dict] = [{"type": "text", "text": title, "weight": "bold", "size": "lg", "wrap": True}]
    if category:
        contents.append({"type": "text", "text": f"📁 {category}", "size": "xs", "color": "#888888", "margin": "sm"})
    contents.extend([
        {"type": "box", "layout": "baseline", "contents": [
            {"type": "text", "text": f"相符度 {match_percent}%", "size": "sm", "color": match_color, "weight": "bold"}
        ], "margin": "md"},
        {"type": "separator", "margin": "lg"},
        {"type": "text", "text": display_content, "wrap": True, "size": "sm", "margin": "lg"}
    ])
    
    return {
        "type": "bubble",
        "size": "mega",
        "header": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "📋 SOP 查詢結果", "color": "#FFFFFF", "size": "md", "weight": "bold"}
        ], "backgroundColor": "#00B900", "paddingAll": "15px"},
        "body": {"type": "box", "layout": "vertical", "contents": contents, "paddingAll": "20px"},
    }


def create_no_result_flex(query: str) -> dict[str, Any]:
    return {
        "type": "bubble",
        "body": {"type": "box", "layout": "vertical", "contents": [
            {"type": "text", "text": "🔍", "size": "3xl", "align": "center"},
            {"type": "text", "text": "找不到相關 SOP", "weight": "bold", "size": "lg", "align": "center", "margin": "lg"},
            {"type": "separator", "margin": "lg"},
            {"type": "text", "text": f"您的查詢: {query}", "wrap": True, "size": "sm", "margin": "lg"},
            {"type": "text", "text": "請嘗試不同關鍵字", "wrap": True, "size": "sm", "color": "#888888", "margin": "md"}
        ], "paddingAll": "20px"},
    }


@router.post("/webhook")
async def line_webhook(
    request: Request,
    x_line_signature: Annotated[str, Header()],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    vector_service: Annotated[VectorService, Depends(get_vector_service)],
) -> dict[str, str]:
    """Handle LINE webhook events."""
    body = await request.body()
    
    line_service = get_line_service()
    if not line_service.verify_signature(body, x_line_signature):
        logger.warning("Invalid LINE webhook signature")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")
    
    body_json = await request.json()
    events = body_json.get("events", [])
    
    for event_data in events:
        try:
            await process_event(event_data, db, auth_service, vector_service)
        except Exception as e:
            logger.error(f"Error processing event: {e}")
    
    return {"status": "ok"}


async def process_event(
    event_data: dict[str, Any],
    db: AsyncSession,
    auth_service: AuthService,
    vector_service: VectorService,
) -> None:
    event_type = event_data.get("type")
    reply_token = event_data.get("replyToken")
    source = event_data.get("source", {})
    user_id = source.get("userId")
    
    if not user_id:
        return
    
    logger.info(f"Processing event: {event_type} from user: {user_id}")
    
    if event_type == "follow":
        await handle_follow_event(user_id, reply_token, db, auth_service)
        return
    
    if event_type == "message":
        message_data = event_data.get("message", {})
        if message_data.get("type") == "text":
            text = message_data.get("text", "").strip()
            await handle_text_message(user_id, text, reply_token, db, auth_service, vector_service)


async def handle_follow_event(
    user_id: str,
    reply_token: str | None,
    db: AsyncSession,
    auth_service: AuthService,
) -> None:
    if not reply_token:
        return
    
    line_service = get_line_service()
    is_auth = await auth_service.is_user_authenticated(user_id, db)
    
    if is_auth:
        await line_service.reply(reply_token, [{"type": "text", "text": "👋 歡迎回來！您可以直接輸入問題查詢 SOP。"}])
    else:
        flex_content = create_auth_required_flex(user_id)
        await line_service.reply(reply_token, [
            {"type": "text", "text": "👋 歡迎使用 HSIB SOP Bot！"},
            {"type": "flex", "altText": "請驗證您的身份", "contents": flex_content}
        ])


async def handle_text_message(
    user_id: str,
    text: str,
    reply_token: str | None,
    db: AsyncSession,
    auth_service: AuthService,
    vector_service: VectorService,
) -> None:
    if not reply_token:
        return
    
    line_service = get_line_service()
    is_auth = await auth_service.is_user_authenticated(user_id, db)
    
    if not is_auth:
        flex_content = create_auth_required_flex(user_id)
        await line_service.reply(reply_token, [{"type": "flex", "altText": "請先驗證身份", "contents": flex_content}])
        return
    
    try:
        result = await vector_service.get_best_match(text, db)
        
        if result:
            doc, similarity = result
            flex_content = create_sop_result_flex(doc.title, doc.content, similarity, doc.category)
            await line_service.reply(reply_token, [{"type": "flex", "altText": f"SOP: {doc.title}", "contents": flex_content}])
        else:
            flex_content = create_no_result_flex(text)
            await line_service.reply(reply_token, [{"type": "flex", "altText": "找不到相關 SOP", "contents": flex_content}])
            
    except Exception as e:
        logger.error(f"Search error: {e}")
        await line_service.reply(reply_token, [{"type": "text", "text": "⚠️ 搜尋時發生錯誤，請稍後再試。"}])
