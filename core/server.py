"""
FastAPI Server - Webhook entry point and API server.
Runs in a separate thread to coexist with PyQt event loop.
"""
from typing import Any, Dict, Optional, Callable, TYPE_CHECKING
from threading import Thread
import logging
import asyncio
import base64
import hashlib
import hmac

from fastapi import FastAPI, Request, HTTPException, Header, status
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.app_context import AppContext

if TYPE_CHECKING:
    from core.registry import ModuleRegistry


class FastAPIServer:
    """
    FastAPI server wrapper for running alongside PyQt.
    Manages the server lifecycle in a separate thread.
    """

    def __init__(
        self,
        context: AppContext,
        host: str = "127.0.0.1",
        port: int = 8000,
        registry: Optional["ModuleRegistry"] = None,
    ) -> None:
        self._context = context
        self._host = host
        self._port = port
        self._registry = registry
        self._logger = logging.getLogger(__name__)

        self._app: FastAPI = self._create_app()
        self._server_thread: Optional[Thread] = None
        self._server: Optional[uvicorn.Server] = None
        self._is_running: bool = False

        # Callback for webhook handling (set by main app)
        self._webhook_handler: Optional[Callable[[
            Dict[str, Any]], Dict[str, Any]]] = None

    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(
            title="Admin System Core API",
            description="Webhook receiver and system status API",
            version="1.0.0"
        )

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add request logging middleware
        @app.middleware("http")
        async def log_requests(request: Request, call_next):
            self._logger.info(f"HTTP {request.method} {request.url.path}")
            response = await call_next(request)
            self._logger.info(
                f"HTTP {request.method} {request.url.path} -> {response.status_code}")
            return response

        # Register routes
        self._register_routes(app)

        return app

    def _register_routes(self, app: FastAPI) -> None:
        """Register API routes."""

        # Register core authentication router with /api prefix
        from core.api.auth import router as auth_router
        app.include_router(auth_router, prefix="/api")

        @app.get("/")
        async def root() -> Dict[str, str]:
            """Health check endpoint."""
            return {"status": "ok", "service": "Admin System Core"}

        # =====================================================================
        # LINE Webhook 動態路由 (框架層統一處理)
        # =====================================================================
        # 路由格式: /webhook/line/{module_name}
        # 框架負責: 簽章驗證、JSON 解析、事件分派
        # 模組負責: 業務邏輯處理

        @app.post("/webhook/line/{module_name}")
        async def line_webhook_dynamic(
            module_name: str,
            request: Request,
            x_line_signature: str = Header(..., alias="x-line-signature"),
        ) -> Dict[str, Any]:
            """
            Dynamic LINE webhook endpoint for multi-module support.

            Each module registers its own LINE channel credentials.
            The framework handles signature verification and event dispatching.
            """
            # 1. 查找模組
            if self._registry is None:
                self._logger.error("ModuleRegistry not configured")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Server configuration error"
                )

            module = self._registry.get_module(module_name)
            if module is None:
                self._logger.warning(
                    f"LINE webhook: Module '{module_name}' not found")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Module '{module_name}' not found"
                )

            # 2. 獲取模組的 LINE Bot 設定
            line_config = module.get_line_bot_config()
            if line_config is None:
                self._logger.warning(
                    f"Module '{module_name}' does not support LINE webhook")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Module '{module_name}' does not handle LINE webhooks"
                )

            channel_secret = line_config.get("channel_secret", "")
            if not channel_secret:
                self._logger.error(
                    f"Module '{module_name}' has no LINE channel secret configured")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="LINE channel secret not configured"
                )

            # 3. 讀取 Raw Body 並驗證簽章
            body = await request.body()

            if not self._verify_line_signature(body, x_line_signature, channel_secret):
                self._logger.warning(
                    f"Invalid LINE signature for module '{module_name}'")
                self._context.log_event(
                    f"LINE webhook: Invalid signature for {module_name}", "SECURITY")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid signature"
                )

            # 4. 解析 JSON 並分派事件
            try:
                payload = await request.json()
            except Exception as e:
                self._logger.error(f"Failed to parse LINE webhook JSON: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid JSON payload"
                )

            events = payload.get("events", [])
            self._context.log_event(
                f"LINE webhook: {len(events)} event(s) for {module_name}", "WEBHOOK"
            )

            # 5. 逐一處理事件
            responses = []
            for event in events:
                try:
                    response = await module.handle_line_event(event, self._context)
                    responses.append({"status": "ok", "response": response})
                except Exception as e:
                    self._logger.error(
                        f"Error handling LINE event in '{module_name}': {e}")
                    responses.append({"status": "error", "error": str(e)})

            return {"processed": len(responses), "results": responses}

        # 保留舊的 /webhook/line 端點以維持向下相容（標記為已棄用）
        @app.post("/webhook/line")
        async def line_webhook(request: Request) -> Dict[str, Any]:
            """LINE webhook endpoint (DEPRECATED - use /webhook/line/{module_name})."""
            try:
                payload = await request.json()
                self._context.log_event(
                    "Received LINE webhook (deprecated endpoint)", "WEBHOOK")

                if self._webhook_handler:
                    response = self._webhook_handler(payload)
                    return response

                return {"status": "received", "message": "No handler configured"}

            except Exception as e:
                self._logger.error(f"Webhook error: {e}")
                self._context.log_event(f"Webhook error: {e}", "ERROR")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/webhook/generic")
        async def generic_webhook(request: Request) -> Dict[str, Any]:
            """Generic webhook endpoint for other integrations."""
            try:
                payload = await request.json()
                self._context.log_event("Received generic webhook", "WEBHOOK")

                if self._webhook_handler:
                    # Wrap in standard event format
                    event = {
                        "type": "generic_webhook",
                        "payload": payload
                    }
                    return self._webhook_handler(event)

                return {"status": "received"}

            except Exception as e:
                self._logger.error(f"Generic webhook error: {e}")
                raise HTTPException(status_code=500, detail=str(e))

    def _verify_line_signature(self, body: bytes, signature: str, channel_secret: str) -> bool:
        """
        Verify LINE webhook signature using HMAC-SHA256.

        This is the core signature verification logic, centralized in the framework
        to avoid duplication across modules.

        Args:
            body: Raw request body bytes
            signature: X-Line-Signature header value
            channel_secret: Module's LINE channel secret

        Returns:
            bool: True if signature is valid
        """
        if not channel_secret or not signature:
            return False

        try:
            expected = base64.b64encode(
                hmac.new(
                    channel_secret.encode("utf-8"),
                    body,
                    hashlib.sha256
                ).digest()
            ).decode("utf-8")

            return hmac.compare_digest(signature, expected)
        except Exception as e:
            self._logger.error(f"Signature verification error: {e}")
            return False

    def set_registry(self, registry: "ModuleRegistry") -> None:
        """Set the module registry for dynamic webhook routing."""
        self._registry = registry

    def set_webhook_handler(
        self,
        handler: Callable[[Dict[str, Any]], Dict[str, Any]]
    ) -> None:
        """Set the webhook event handler callback."""
        self._webhook_handler = handler

    def add_router(self, router: Any, prefix: str = "") -> None:
        """Add an API router to the application."""
        self._app.include_router(router, prefix=prefix)

    def start(self) -> None:
        """Start the server in a background thread."""
        if self._is_running:
            self._logger.warning("Server is already running.")
            return

        self._server_thread = Thread(target=self._run_server, daemon=True)
        self._server_thread.start()

        self._is_running = True
        self._context.set_server_status(True, self._port)
        self._context.log_event(
            f"Server started on {self._host}:{self._port}", "SERVER")

    def _run_server(self) -> None:
        """Run the uvicorn server (called in thread)."""
        config = uvicorn.Config(
            app=self._app,
            host=self._host,
            port=self._port,
            log_level="warning",
            access_log=False
        )
        self._server = uvicorn.Server(config)

        # Create new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Initialize database schema before starting server
            from core.database import init_database
            loop.run_until_complete(init_database())
            self._logger.info("Database schema initialized")

            loop.run_until_complete(self._server.serve())
        except Exception as e:
            self._logger.error(f"Server error: {e}")
        finally:
            # Clean up database connections before closing loop
            try:
                from core.database import close_db_connections
                loop.run_until_complete(close_db_connections())
            except Exception as e:
                self._logger.error(f"Error cleaning up database: {e}")

            loop.close()

    def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.should_exit = True

        self._is_running = False
        self._context.set_server_status(False, self._port)
        self._context.log_event("Server stopped", "SERVER")

    def join(self, timeout: float | None = None) -> None:
        """Wait for the server thread to exit."""
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout)

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._is_running

    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self._app
