"""
Authentication Router.

Handles Magic Link authentication flow endpoints.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from modules.chatbot.core.config import get_chatbot_settings
from modules.chatbot.core.rate_limiter import magic_link_limiter
from modules.chatbot.core.security import TokenExpiredError, TokenInvalidError
from modules.chatbot.db import get_db_session
from modules.chatbot.schemas import (
    ErrorResponse,
    MagicLinkRequest,
    MagicLinkResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
)
from modules.chatbot.services import (
    AuthService,
    EmailNotFoundError,
    EmailSendError,
    TokenAlreadyUsedError,
    UserBindingError,
    get_auth_service,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_login_html(line_id: str, error: str | None = None, success: str | None = None) -> str:
    settings = get_chatbot_settings()
    
    error_html = f'<div class="alert alert-error">⚠️ {error}</div>' if error else ""
    success_html = f'<div class="alert alert-success">✅ {success}</div>' if success else ""
    
    return f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>身份驗證 | {settings.app_name}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, sans-serif; background: linear-gradient(135deg, #00B900, #00A000); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .container {{ background: white; border-radius: 16px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); max-width: 420px; width: 100%; }}
        .header {{ background: linear-gradient(135deg, #00B900, #00C900); color: white; padding: 40px 30px; text-align: center; border-radius: 16px 16px 0 0; }}
        .header .icon {{ font-size: 48px; }}
        .content {{ padding: 30px; }}
        .alert {{ padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
        .alert-error {{ background: #FEE2E2; color: #DC2626; }}
        .alert-success {{ background: #D1FAE5; color: #059669; }}
        .form-group {{ margin-bottom: 20px; }}
        .form-group label {{ display: block; font-weight: 600; margin-bottom: 8px; }}
        .form-group input {{ width: 100%; padding: 14px; border: 2px solid #E5E7EB; border-radius: 8px; font-size: 16px; }}
        .form-group input:focus {{ outline: none; border-color: #00B900; }}
        .submit-btn {{ width: 100%; padding: 16px; background: linear-gradient(135deg, #00B900, #00A000); color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer; }}
        .footer {{ text-align: center; padding: 20px; color: #6B7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header"><div class="icon">🔐</div><h1>身份驗證</h1><p>Identity Verification</p></div>
        <div class="content">
            {error_html}{success_html}
            <form method="POST" action="/auth/request-magic-link">
                <input type="hidden" name="line_user_id" value="{line_id}">
                <div class="form-group">
                    <label for="email">電子郵件 / Email</label>
                    <input type="email" id="email" name="email" placeholder="your.name@company.com" required>
                </div>
                <button type="submit" class="submit-btn">📧 發送驗證連結</button>
            </form>
        </div>
        <div class="footer"><p>連結有效期限 {settings.magic_link_expire_minutes} 分鐘</p></div>
    </div>
</body>
</html>
"""


def get_verification_result_html(success: bool, message: str) -> str:
    settings = get_chatbot_settings()
    icon = "✅" if success else "❌"
    title = "驗證成功！" if success else "驗證失敗"
    bg = "#00B900" if success else "#DC2626"
    
    return f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | {settings.app_name}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: linear-gradient(135deg, {bg}, {bg}dd); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .container {{ background: white; border-radius: 16px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); max-width: 420px; width: 100%; text-align: center; padding: 50px 30px; }}
        .icon {{ font-size: 72px; margin-bottom: 20px; }}
        h1 {{ font-size: 28px; color: #1F2937; margin-bottom: 8px; }}
        .description {{ color: #374151; line-height: 1.6; margin-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">{icon}</div>
        <h1>{title}</h1>
        <p class="description">{message}</p>
        <p style="color: #9CA3AF; font-size: 12px; margin-top: 30px;">您可以關閉此頁面 / You can close this page</p>
    </div>
</body>
</html>
"""


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    line_id: Annotated[str, Query(description="LINE user ID")],
    error: Annotated[str | None, Query()] = None,
    success: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    return HTMLResponse(content=get_login_html(line_id, error, success))


@router.post("/request-magic-link", response_class=HTMLResponse)
async def request_magic_link(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> HTMLResponse:
    try:
        magic_link_limiter.check_rate_limit(request)
    except HTTPException as e:
        form_data = await request.form()
        line_user_id = str(form_data.get("line_user_id", "")).strip()
        return HTMLResponse(content=get_login_html(line_user_id, error=e.detail), status_code=e.status_code)
    
    form_data = await request.form()
    email = str(form_data.get("email", "")).strip().lower()
    line_user_id = str(form_data.get("line_user_id", "")).strip()
    
    if not email or not line_user_id:
        return HTMLResponse(content=get_login_html(line_user_id, error="請填寫電子郵件"), status_code=400)
    
    try:
        await auth_service.initiate_magic_link(email, line_user_id)
        return HTMLResponse(content=get_login_html(line_user_id, success=f"驗證連結已發送至 {email}"))
    except EmailNotFoundError as e:
        return HTMLResponse(content=get_login_html(line_user_id, error=str(e)), status_code=400)
    except EmailSendError:
        return HTMLResponse(content=get_login_html(line_user_id, error="發送郵件失敗"), status_code=500)
    except Exception:
        return HTMLResponse(content=get_login_html(line_user_id, error="發生錯誤"), status_code=500)


@router.get("/verify", response_class=HTMLResponse)
async def verify_magic_link(
    token: Annotated[str, Query(description="Magic link token")],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> HTMLResponse:
    try:
        await auth_service.verify_magic_token(token, db)
        return HTMLResponse(content=get_verification_result_html(True, "您的 LINE 帳號已成功綁定！"))
    except TokenExpiredError:
        return HTMLResponse(content=get_verification_result_html(False, "驗證連結已過期"), status_code=400)
    except TokenInvalidError:
        return HTMLResponse(content=get_verification_result_html(False, "驗證連結無效"), status_code=400)
    except TokenAlreadyUsedError:
        return HTMLResponse(content=get_verification_result_html(False, "此連結已被使用"), status_code=400)
    except UserBindingError:
        return HTMLResponse(content=get_verification_result_html(False, "帳號綁定失敗"), status_code=500)
    except Exception:
        return HTMLResponse(content=get_verification_result_html(False, "發生錯誤"), status_code=500)


@router.post("/api/request-magic-link", response_model=MagicLinkResponse)
async def api_request_magic_link(
    request_data: MagicLinkRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MagicLinkResponse:
    try:
        await auth_service.initiate_magic_link(request_data.email, request_data.line_user_id)
        return MagicLinkResponse(message="Verification email sent", email_sent_to=request_data.email)
    except EmailNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except EmailSendError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/verify", response_model=VerifyTokenResponse)
async def api_verify_token(
    request_data: VerifyTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> VerifyTokenResponse:
    try:
        user = await auth_service.verify_magic_token(request_data.token, db)
        return VerifyTokenResponse(success=True, message="Verification successful", user=user)
    except TokenExpiredError:
        raise HTTPException(status_code=400, detail="Token expired")
    except TokenInvalidError:
        raise HTTPException(status_code=400, detail="Invalid token")
    except UserBindingError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_user_stats(db: Annotated[AsyncSession, Depends(get_db_session)]) -> dict:
    from sqlalchemy import func, select
    from modules.chatbot.models import User
    
    total_result = await db.execute(select(func.count(User.id)))
    total = total_result.scalar() or 0
    
    active_result = await db.execute(select(func.count(User.id)).where(User.is_active == True))
    active = active_result.scalar() or 0
    
    return {"total_users": total, "active_users": active}
