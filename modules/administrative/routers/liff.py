"""
LIFF Page Router.

Serves LIFF HTML pages for LINE integration.
"""

import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

from modules.administrative.core.config import get_admin_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/liff", tags=["LIFF"])

# Path to static files
STATIC_DIR = Path(__file__).parent.parent / "static"


@router.get(
    "/leave-form",
    response_class=HTMLResponse,
    summary="Leave Request Form",
    description="Serve the LIFF leave request form page.",
)
async def serve_leave_form() -> FileResponse:
    """
    Serve the LIFF leave request form.

    LIFF Endpoint should be set to:
    https://your-domain.com/api/administrative/liff/leave-form
    """
    html_path = STATIC_DIR / "leave_form.html"

    if not html_path.exists():
        logger.error(f"Leave form not found: {html_path}")
        return HTMLResponse(
            content="<html><body><h1>Page Not Found</h1></body></html>",
            status_code=404,
        )

    # Add no-store headers to prevent caching issues during dev
    response = FileResponse(
        path=html_path,
        media_type="text/html",
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@router.get(
    "/leave_form.js",
    response_class=FileResponse,
    summary="Leave Form Script",
    description="Serve the JS for leave form."
)
async def serve_leave_form_js() -> FileResponse:
    # Serve the V5 version explicitly to ensure fresh code
    js_path = STATIC_DIR / "leave_form_v5.js"
    if not js_path.exists():
        # Fallback if v5 missing
        js_path = STATIC_DIR / "leave_form.js"
        
    if not js_path.exists():
        return HTMLResponse(content="console.error('JS Not Found');", status_code=404)

    response = FileResponse(
        path=js_path,
        media_type="application/javascript",
    )
    # Prevent caching for dev
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Content-Disposition"] = "inline"
    return response


@router.get(
    "/config",
    summary="Get LIFF Configuration",
    description="Return LIFF-related configuration for frontend.",
)
async def get_liff_config() -> dict:
    """
    Return LIFF configuration for frontend initialization.

    This allows the frontend to dynamically get the LIFF ID
    without hardcoding it in the HTML.
    """
    logger.info("LIFF config requested")
    settings = get_admin_settings()

    result = {
        "liff_id_leave": settings.line_liff_id_leave,
    }
    logger.info(f"LIFF config returned: {result}")
    return result
