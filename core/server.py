"""
FastAPI Application Factory.

Creates and configures the FastAPI application with webhook routing,
middleware, and core API endpoints.
"""

from typing import Any, Callable, TYPE_CHECKING
import base64
import hashlib
import hmac
import logging

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

from core.app_context import AppContext

if TYPE_CHECKING:
    from core.registry import ModuleRegistry

_logger = logging.getLogger(__name__)


def create_base_app(
    context: AppContext,
    registry: "ModuleRegistry | None" = None,
    title: str = "Admin System Core API",
    description: str = "Webhook receiver and system status API",
    version: str = "1.0.0",
) -> FastAPI:
    """
    Create and configure the base FastAPI application with webhook routes.

    Args:
        context: Application context for logging and configuration.
        registry: Optional module registry for dynamic webhook routing.
        title: API title for OpenAPI documentation.
        description: API description for OpenAPI documentation.
        version: API version string.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(title=title, description=description, version=version)

    # Store references in app state for access in route handlers
    app.state.context = context
    app.state.registry = registry

    # Add CORS middleware
    # Get allowed origins from configuration (defaults to BASE_URL only)
    config = context.config
    base_url = config.get("server.base_url", "")
    is_debug = config.get("app.debug", False)
    
    allowed_origins: list[str] = []
    
    if base_url:
        allowed_origins.append(base_url)
    
    # In debug mode, also allow localhost for development
    if is_debug:
        allowed_origins.extend([
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "https://localhost:8000",
        ])
    
    # Security: Never fallback to ["*"] in production
    # If no origins configured in non-debug mode, log warning and use empty list
    if not allowed_origins:
        if is_debug:
            # In debug mode, allow common dev origins as fallback
            _logger.warning(
                "BASE_URL not configured. Using localhost origins for CORS in debug mode."
            )
            allowed_origins = [
                "http://localhost:8000",
                "http://127.0.0.1:8000",
            ]
        else:
            # In production, do NOT allow any origins if not explicitly configured
            _logger.error(
                "CRITICAL: BASE_URL not configured and not in debug mode. "
                "CORS will reject all cross-origin requests. "
                "Please set BASE_URL environment variable."
            )
            # Use empty list - this blocks all cross-origin requests
            allowed_origins = []
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Line-ID-Token", "X-Hub-Signature-256"],
    )
    
    # Log CORS configuration
    if allowed_origins:
        _logger.info(f"CORS configured with {len(allowed_origins)} origin(s): {allowed_origins}")
    else:
        _logger.warning("CORS configured with no allowed origins (all cross-origin requests will be blocked)")

    # Add security headers middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Enable XSS filter (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Permissions policy (disable unnecessary features)
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS (via Cloudflare, but add as backup)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Register core routes
    _register_core_routes(app)

    # Register LINE webhook routes
    _register_line_webhook_routes(app)

    return app


def _register_core_routes(app: FastAPI) -> None:
    """Register core API routes (health check, root redirect)."""
    from core.api.auth import router as auth_router

    # Include authentication router
    app.include_router(auth_router)

    @app.get("/")
    async def root() -> dict[str, str]:
        """Root endpoint - redirects to login page."""
        from fastapi.responses import RedirectResponse

        return RedirectResponse(url="/static/login.html")

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok", "service": "Admin System Core"}


def _register_line_webhook_routes(app: FastAPI) -> None:
    """Register LINE webhook routes with signature verification."""

    @app.post("/webhook/line/{module_name}")
    async def line_webhook_dynamic(
        module_name: str,
        request: Request,
        x_line_signature: str = Header(..., alias="x-line-signature"),
    ) -> dict[str, Any]:
        """
        Dynamic LINE webhook endpoint for multi-module support.

        Each module registers its own LINE channel credentials.
        The framework handles signature verification and event dispatching.
        """
        context: AppContext = request.app.state.context
        registry: "ModuleRegistry | None" = request.app.state.registry

        # 1. Validate registry is configured
        if registry is None:
            _logger.error("ModuleRegistry not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server configuration error",
            )

        # 2. Find the target module
        module = registry.get_module(module_name)
        if module is None:
            _logger.warning(f"LINE webhook: Module '{module_name}' not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module '{module_name}' not found",
            )

        # 3. Get module's LINE Bot configuration
        line_config = module.get_line_bot_config()
        if line_config is None:
            _logger.warning(f"Module '{module_name}' does not support LINE webhook")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Module '{module_name}' does not handle LINE webhooks",
            )

        channel_secret = line_config.get("channel_secret", "")
        if not channel_secret:
            _logger.error(f"Module '{module_name}' has no LINE channel secret configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LINE channel secret not configured",
            )

        # 4. Read raw body and verify signature
        body = await request.body()

        if not _verify_line_signature(body, x_line_signature, channel_secret):
            _logger.warning(f"Invalid LINE signature for module '{module_name}'")
            context.log_event(f"LINE webhook: Invalid signature for {module_name}", "SECURITY")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid signature",
            )

        # 5. Parse JSON payload
        try:
            payload = await request.json()
        except Exception as e:
            _logger.error(f"Failed to parse LINE webhook JSON: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON payload",
            )

        events = payload.get("events", [])
        context.log_event(f"LINE webhook: {len(events)} event(s) for {module_name}", "WEBHOOK")

        # 6. Process events
        responses: list[dict[str, Any]] = []
        for event in events:
            try:
                response = await module.handle_line_event(event, context)
                responses.append({"status": "ok", "response": response})
            except Exception as e:
                _logger.error(f"Error handling LINE event in '{module_name}': {e}")
                responses.append({"status": "error", "error": str(e)})

        return {"processed": len(responses), "results": responses}


def _verify_line_signature(body: bytes, signature: str, channel_secret: str) -> bool:
    """
    Verify LINE webhook signature using HMAC-SHA256.

    Args:
        body: Raw request body bytes.
        signature: X-Line-Signature header value.
        channel_secret: Module's LINE channel secret.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not channel_secret or not signature:
        return False

    try:
        expected = base64.b64encode(
            hmac.new(
                channel_secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        return hmac.compare_digest(signature, expected)
    except Exception as e:
        _logger.error(f"Signature verification error: {e}")
        return False


def set_registry(app: FastAPI, registry: "ModuleRegistry") -> None:
    """
    Set the module registry on the app for dynamic webhook routing.

    Args:
        app: FastAPI application instance.
        registry: Module registry instance.
    """
    app.state.registry = registry
