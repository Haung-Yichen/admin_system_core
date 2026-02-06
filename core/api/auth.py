"""
Core Authentication Router.

Unified authentication API endpoints for the entire system.
Handles Magic Link authentication flow with Framework-First design.

Framework-First Authentication:
    - All modules share the same login and verify pages
    - LIFF ID is dynamically injected based on ?app= query parameter
    - No module needs to implement its own auth UI
"""

import logging
import os
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv  # 新增：確保 .env 被載入
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.app_context import ConfigLoader
from core.database import get_db_session
from core.schemas.auth import (
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

# 強制載入 .env 檔案到 os.environ，確保 os.getenv 能讀取到變數
load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# =============================================================================
# LIFF ID Configuration (Dependency Injection via Environment Variables)
# =============================================================================

def _get_liff_id_map() -> dict[str, str]:
    """
    Build LIFF ID map from environment variables.
    
    Convention: AUTH_LIFF_ID for login pages (all apps share the same login LIFF)
    
    Returns:
        dict mapping app context names to LIFF IDs
    """
    # 登入頁面使用專用的 AUTH_LIFF_ID（所有模組共用）
    auth_liff = os.getenv("AUTH_LIFF_ID", "").strip()
    
    # Fallback to legacy variables if AUTH_LIFF_ID not set
    if not auth_liff:
        auth_liff = (
            os.getenv("ADMIN_LINE_LIFF_ID_VERIFY") 
            or os.getenv("DEFAULT_LIFF_ID")
            or ""
        ).strip()

    # Debug Log: 幫助排查環境變數是否正確載入
    logger.debug(f"LIFF ID for login page: '{auth_liff}'")

    # 所有 app context 都使用同一個登入頁面 LIFF ID
    return {
        "admin": auth_liff,
        "administrative": auth_liff,
        "chatbot": auth_liff,
        "hr": auth_liff,
        "default": auth_liff,
    }


def _get_liff_id_for_app(app_context: str | None) -> str:
    """
    Get LIFF ID for a specific app context.
    
    Args:
        app_context: App name (e.g., 'admin', 'chatbot'). If None, uses 'default'.
        
    Returns:
        LIFF ID string (may be empty if not configured)
    """
    liff_map = _get_liff_id_map()
    app = (app_context or "default").lower().strip()
    
    # Try exact match first, then fallback to default
    liff_id = liff_map.get(app) or liff_map.get("default", "")
    
    if not liff_id:
        logger.warning(
            f"LIFF ID not found for app context: '{app}'. "
            f"Available keys: {list(liff_map.keys())}. "
            "Please check .env file and ADMIN_LINE_LIFF_ID_VERIFY."
        )
    else:
        logger.debug(f"Resolved LIFF ID for '{app}': {liff_id}")
        
    return liff_id


def _get_app_config() -> dict:
    """Get application configuration."""
    loader = ConfigLoader()
    loader.load()
    return {
        "app_name": loader.get("server.app_name", "Admin System"),
        "magic_link_expire_minutes": loader.get("security.magic_link_expire_minutes", 15),
    }


# =============================================================================
# Static HTML Template Engine
# =============================================================================

def _get_template_path(template_name: str) -> Path:
    """Get the path to a template file."""
    return Path(__file__).parent.parent / "static" / "auth" / template_name


def _render_template(template_name: str, variables: dict[str, str]) -> str:
    """
    Render an HTML template with variable substitution.
    
    Args:
        template_name: Name of the template file (e.g., 'login.html')
        variables: Dictionary of {{VARIABLE}} -> value mappings
        
    Returns:
        Rendered HTML string
    """
    template_path = _get_template_path(template_name)
    
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    
    content = template_path.read_text(encoding="utf-8")
    
    for key, value in variables.items():
        placeholder = "{{" + key + "}}"
        # Ensure value is not None before replacing
        safe_value = str(value) if value is not None else ""
        content = content.replace(placeholder, safe_value)
    
    return content


# =============================================================================
# Legacy HTML Generators (Kept for backward compatibility)
# =============================================================================

def get_login_html(line_sub: str, error: str | None = None, success: str | None = None) -> str:
    """
    Generate legacy login HTML (inline string version).
    
    DEPRECATED: Use GET /auth/page/login instead for the new template-based version.
    """
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
        <div class="header"><div class="icon"><img src="/static/crown.png?v=2" alt="Crown" style="width: 80px; height: auto;"></div><h1>身份驗證</h1><p>Identity Verification</p></div>
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


def get_verification_result_html(success: bool, message: str, app_context: str | None = None) -> str:
    """
    Generate legacy verification result HTML (inline string version).
    
    DEPRECATED: Use GET /auth/page/verify-result instead for the new template-based version.
    """
    config = _get_app_config()
    app_name = config["app_name"]
    liff_id = _get_liff_id_for_app(app_context)
    
    icon = '<img src="/static/crown.png?v=2" alt="Crown" style="width: 100px; height: auto;">' if success else "❌"
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


# =============================================================================
# Framework-First Page Routes (New Template-Based)
# =============================================================================

@router.get("/page/login", response_class=HTMLResponse)
async def get_login_page(
    app: Annotated[str | None, Query(description="App context for LIFF ID selection")] = None,
) -> HTMLResponse:
    """
    Serve the unified login page with LIFF ID injection.
    
    This is the Framework-First entry point for all modules.
    The page handles LIFF SDK initialization, LINE login, and form submission.
    
    Args:
        app: App context name (e.g., 'admin', 'chatbot'). Determines which LIFF ID to use.
        
    Returns:
        HTMLResponse with the rendered login page
    """
    config = _get_app_config()
    app_context = app or "default"
    liff_id = _get_liff_id_for_app(app_context)
    
    logger.info(f"Login page requested for app: {app_context}, LIFF ID: {liff_id}")
    
    # 這裡如果不寫入 load_dotenv，liff_id 很可能為空
    if not liff_id:
        logger.error(f"CRITICAL: No LIFF ID configured for app context: {app_context}. Login will fail.")
    
    try:
        html_content = _render_template("login.html", {
            "LIFF_ID": liff_id,
            "APP_CONTEXT": app_context,
            "APP_NAME": config["app_name"],
            "EXPIRE_MINUTES": str(config["magic_link_expire_minutes"]),
        })
        return HTMLResponse(content=html_content)
    except FileNotFoundError as e:
        logger.error(f"Login template not found: {e}")
        return HTMLResponse(content=get_login_html("", error="系統錯誤：找不到登入頁面模板"), status_code=500)


@router.get("/page/verify-result", response_class=HTMLResponse)
async def get_verify_result_page(
    token: Annotated[str | None, Query(description="Magic link token")] = None,
    app: Annotated[str | None, Query(description="App context for LIFF ID selection")] = None,
) -> HTMLResponse:
    """
    Serve the unified verification result page.
    """
    config = _get_app_config()
    app_context = app or "default"
    liff_id = _get_liff_id_for_app(app_context)
    
    if not liff_id:
        logger.warning(f"No LIFF ID configured for app context: {app_context}")
    
    try:
        html_content = _render_template("verify_result.html", {
            "LIFF_ID": liff_id,
            "APP_CONTEXT": app_context,
            "APP_NAME": config["app_name"],
            "TOKEN": token or "",
        })
        return HTMLResponse(content=html_content)
    except FileNotFoundError as e:
        logger.error(f"Verify result template not found: {e}")
        return HTMLResponse(
            content=get_verification_result_html(False, "系統錯誤，請稍後再試", app_context)
        )


@router.get("/liff-config")
async def get_liff_config(
    app: Annotated[str | None, Query(description="App context")] = None,
) -> dict:
    """Get LIFF configuration for a specific app context."""
    app_context = app or "default"
    return {
        "liff_id": _get_liff_id_for_app(app_context),
        "app_context": app_context,
    }


# =============================================================================
# Legacy Routes (Kept for backward compatibility)
# =============================================================================

@router.get("/login", response_class=HTMLResponse)
async def login_page(
    line_sub: Annotated[str, Query(description="LINE sub (OIDC Subject Identifier)")],
    error: Annotated[str | None, Query()] = None,
    success: Annotated[str | None, Query()] = None,
    app: Annotated[str | None, Query(description="App context")] = None,
) -> HTMLResponse:
    """Legacy login page endpoint."""
    return HTMLResponse(content=get_login_html(line_sub, error, success))


@router.post("/request-magic-link", response_class=HTMLResponse)
async def request_magic_link(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> HTMLResponse:
    """Handle magic link request from login form."""
    form_data = await request.form()
    email = str(form_data.get("email", "")).strip().lower()
    line_sub = str(form_data.get("line_sub", "")).strip()
    app_context = str(form_data.get("app_context", "")).strip() or None

    if not email or not line_sub:
        return HTMLResponse(content=get_login_html(line_sub, error="請填寫電子郵件"), status_code=400)

    try:
        await auth_service.initiate_magic_link(email, line_sub, app_context=app_context)
        return HTMLResponse(content=get_login_html(line_sub, success=f"驗證連結已發送至 {email}"))
    except EmailNotFoundError as e:
        return HTMLResponse(content=get_login_html(line_sub, error=str(e)), status_code=400)
    except EmailSendError:
        return HTMLResponse(content=get_login_html(line_sub, error="發送郵件失敗"), status_code=500)
    except Exception:
        logger.exception("Unexpected error in request_magic_link")
        return HTMLResponse(content=get_login_html(line_sub, error="發生錯誤"), status_code=500)


@router.get("/verify", response_class=HTMLResponse)
async def verify_magic_link(
    request: Request,
    token: Annotated[str | None, Query(description="Magic link token")] = None,
    app: Annotated[str | None, Query(description="App context")] = None,
    db: Annotated[AsyncSession, Depends(get_db_session)] = None,
    auth_service: Annotated[AuthService, Depends(get_auth_service)] = None,
) -> HTMLResponse:
    """Magic link verification endpoint with legacy compatibility."""
    # Check if this is an API request (JSON expected)
    accept_header = request.headers.get("accept", "")
    if "application/json" in accept_header:
        raise HTTPException(
            status_code=307,
            headers={"Location": f"/auth/api/verify?token={token}"}
        )
    
    # Browser request - render the verification result page directly
    config = _get_app_config()
    app_context = app or "default"
    liff_id = _get_liff_id_for_app(app_context)
    token_val = token or ""
    
    try:
        html_content = _render_template("verify_result.html", {
            "LIFF_ID": liff_id,
            "APP_CONTEXT": app_context,
            "APP_NAME": config["app_name"],
            "TOKEN": token_val,
        })
        return HTMLResponse(content=html_content)
    except FileNotFoundError as e:
        logger.error(f"Verify result template not found: {e}")
        return HTMLResponse(content="System Error: Template not found", status_code=500)


# =============================================================================
# API Endpoints (JSON responses)
# =============================================================================

@router.post("/magic-link", response_model=MagicLinkResponse)
async def api_request_magic_link(
    request_data: MagicLinkRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> MagicLinkResponse:
    """API endpoint for requesting magic link (JSON)."""
    try:
        app_context = getattr(request_data, 'app_context', None)
        await auth_service.initiate_magic_link(
            request_data.email, 
            request_data.line_sub,
            app_context=app_context
        )
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
    """API endpoint for token verification (JSON)."""
    try:
        user = await auth_service.verify_magic_token(request_data.token, db)
        return VerifyTokenResponse(success=True, message="Verification successful", user=user)
    except TokenExpiredError:
        raise HTTPException(status_code=400, detail="Token expired")
    except TokenInvalidError:
        raise HTTPException(status_code=400, detail="Invalid token")
    except TokenAlreadyUsedError:
        raise HTTPException(status_code=400, detail="Token already used")
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