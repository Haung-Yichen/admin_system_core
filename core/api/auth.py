"""
Core Authentication Router.

Unified authentication API endpoints for the entire system.
Handles Magic Link authentication flow.
"""

import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.app_context import ConfigLoader
from core.database import get_db_session
from core.schemas.auth import (
    ErrorResponse,
    MagicLinkRequest,
    MagicLinkResponse,
    VerifyTokenRequest,
    VerifyTokenResponse,
)
from core.services.auth import (
    AuthService,
    EmailNotFoundError,
    EmailSendError,
    TokenAlreadyUsedError,
    TokenExpiredError,
    TokenInvalidError,
    UserBindingError,
    get_auth_service,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_app_config() -> dict:
    """Get application configuration."""
    loader = ConfigLoader()
    loader.load()
    return {
        "app_name": loader.get("server.app_name", "Admin System"),
        "magic_link_expire_minutes": loader.get("security.magic_link_expire_minutes", 15),
        "liff_id": os.getenv("ADMIN_LINE_LIFF_ID_VERIFY", ""),
    }


def get_login_html(line_sub: str, error: str | None = None, success: str | None = None) -> str:
    config = _get_app_config()
    app_name = config["app_name"]
    expire_minutes = config["magic_link_expire_minutes"]

    error_html = f'<div class="alert alert-error">⚠️ {error}</div>' if error else ""
    success_html = f'<div class="alert alert-success">✅ {success}</div>' if success else ""

    return f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>身份驗證 | {app_name}</title>
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
        <div class="header"><div class="icon"><img src="/static/crown.png" alt="Crown" style="width: 80px; height: auto;"></div><h1>身份驗證</h1><p>Identity Verification</p></div>
        <div class="content">
            {error_html}{success_html}
            <form method="POST" action="/auth/request-magic-link">
                <input type="hidden" name="line_sub" value="{line_sub}">
                <div class="form-group">
                    <label for="email">電子郵件 / Email</label>
                    <input type="email" id="email" name="email" placeholder="your.name@company.com" required>
                </div>
                <button type="submit" class="submit-btn">📧 發送驗證連結</button>
            </form>
        </div>
        <div class="footer"><p>連結有效期限 {expire_minutes} 分鐘</p></div>
    </div>
</body>
</html>
"""


def get_verification_result_html(success: bool, message: str) -> str:
    config = _get_app_config()
    app_name = config["app_name"]
    liff_id = config["liff_id"]
    
    icon = '<img src="/static/crown.png" alt="Crown" style="width: 100px; height: auto;">' if success else "❌"
    title = "驗證成功！" if success else "驗證失敗"
    bg = "#00B900" if success else "#DC2626"
    
    # LIFF Close Button Logic
    close_script = f"""
    <script charset="utf-8" src="https://static.line-scdn.net/liff/edge/2/sdk.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", function() {{
            const liffId = "{liff_id}";
            if (liffId) {{
                liff.init({{ liffId: liffId }}).then(() => {{
                    console.log("LIFF initialized");
                    // Auto-close if successful? Maybe wait for user action.
                }}).catch(err => {{
                    console.error("LIFF init failed", err);
                }});
            }}
        }});
        
        function closeWindow() {{
            if (typeof liff !== 'undefined' && liff.isInClient()) {{
                liff.closeWindow();
            }} else {{
                window.close();
                // If window.close() fails (browsers block it), show message
                document.getElementById("close-msg").style.display = "block";
            }}
        }}
    </script>
    """

    return f"""
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | {app_name}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; background: linear-gradient(135deg, {bg}, {bg}dd); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }}
        .container {{ background: white; border-radius: 16px; box-shadow: 0 20px 40px rgba(0,0,0,0.2); max-width: 420px; width: 100%; text-align: center; padding: 50px 30px; }}
        .icon {{ font-size: 72px; margin-bottom: 20px; }}
        h1 {{ font-size: 28px; color: #1F2937; margin-bottom: 8px; }}
        .description {{ color: #374151; line-height: 1.6; margin-bottom: 20px; font-size: 18px; }}
        .btn {{
            display: inline-block;
            background-color: #06C755;
            color: white;
            padding: 12px 30px;
            border-radius: 30px;
            text-decoration: none;
            font-weight: bold;
            margin-top: 20px;
            cursor: pointer;
            border: none;
            font-size: 16px;
        }}
        .btn:hover {{ background-color: #05B34C; }}
        .btn-secondary {{ background-color: #6B7280; }}
        .btn-secondary:hover {{ background-color: #4B5563; }}
    </style>
    {close_script}
</head>
<body>
    <div class="container">
        <div class="icon">{icon}</div>
        <h1>{title}</h1>
        <p class="description">{message}</p>
        
        <button onclick="closeWindow()" class="btn">關閉視窗</button>
        
        <p id="close-msg" style="display:none; color: #DC2626; font-size: 12px; margin-top: 10px;">
            瀏覽器阻止了自動關閉，請手動關閉此分頁。
        </p>
        <p style="color: #9CA3AF; font-size: 12px; margin-top: 30px;">{app_name}</p>
    </div>
</body>
</html>
"""


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    line_sub: Annotated[str, Query(description="LINE sub (OIDC Subject Identifier)")],
    error: Annotated[str | None, Query()] = None,
    success: Annotated[str | None, Query()] = None,
) -> HTMLResponse:
    return HTMLResponse(content=get_login_html(line_sub, error, success))


@router.post("/request-magic-link", response_class=HTMLResponse)
async def request_magic_link(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> HTMLResponse:
    form_data = await request.form()
    email = str(form_data.get("email", "")).strip().lower()
    line_sub = str(form_data.get("line_sub", "")).strip()

    if not email or not line_sub:
        return HTMLResponse(content=get_login_html(line_sub, error="請填寫電子郵件"), status_code=400)

    try:
        await auth_service.initiate_magic_link(email, line_sub)
        return HTMLResponse(content=get_login_html(line_sub, success=f"驗證連結已發送至 {email}"))
    except EmailNotFoundError as e:
        return HTMLResponse(content=get_login_html(line_sub, error=str(e)), status_code=400)
    except EmailSendError:
        return HTMLResponse(content=get_login_html(line_sub, error="發送郵件失敗"), status_code=500)
    except Exception:
        return HTMLResponse(content=get_login_html(line_sub, error="發生錯誤"), status_code=500)


@router.get("/verify", response_class=HTMLResponse)
async def verify_magic_link(
    token: Annotated[str | None, Query(description="Magic link token")] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,
) -> HTMLResponse:
    if not token:
        # Handle missing token (e.g. if LIFF doesn't pass query params correctly)
        return HTMLResponse(
            content=get_verification_result_html(False, "無效的連結：缺少驗證代碼。請確認您的 LINE 設定。"),
            status_code=400
        )

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


@router.post("/magic-link", response_model=MagicLinkResponse)
async def api_request_magic_link(
    request_data: MagicLinkRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MagicLinkResponse:
    try:
        await auth_service.initiate_magic_link(request_data.email, request_data.line_sub)
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
    from core.models import User

    total_result = await db.execute(select(func.count(User.id)))
    total = total_result.scalar() or 0

    active_result = await db.execute(select(func.count(User.id)).where(User.is_active == True))
    active = active_result.scalar() or 0

    return {"total_users": total, "active_users": active}
