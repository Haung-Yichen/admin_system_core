"""
FastAPI Server - Webhook entry point and API server.
Runs in a separate thread to coexist with PyQt event loop.
"""
from typing import Any, Dict, Optional, Callable
from threading import Thread
import logging
import asyncio

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from core.app_context import AppContext


class FastAPIServer:
    """
    FastAPI server wrapper for running alongside PyQt.
    Manages the server lifecycle in a separate thread.
    """
    
    def __init__(
        self, 
        context: AppContext,
        host: str = "127.0.0.1",
        port: int = 8000
    ) -> None:
        self._context = context
        self._host = host
        self._port = port
        self._logger = logging.getLogger(__name__)
        
        self._app: FastAPI = self._create_app()
        self._server_thread: Optional[Thread] = None
        self._server: Optional[uvicorn.Server] = None
        self._is_running: bool = False
        
        # Callback for webhook handling (set by main app)
        self._webhook_handler: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None
    
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
        
        # Register routes
        self._register_routes(app)
        
        return app
    
    def _register_routes(self, app: FastAPI) -> None:
        """Register API routes."""
        
        @app.get("/")
        async def root() -> Dict[str, str]:
            """Health check endpoint."""
            return {"status": "ok", "service": "Admin System Core"}
        
        @app.post("/webhook/line")
        async def line_webhook(request: Request) -> Dict[str, Any]:
            """LINE webhook endpoint."""
            try:
                payload = await request.json()
                self._context.log_event("Received LINE webhook", "WEBHOOK")
                
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
        self._context.log_event(f"Server started on {self._host}:{self._port}", "SERVER")
    
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
            loop.run_until_complete(self._server.serve())
        except Exception as e:
            self._logger.error(f"Server error: {e}")
        finally:
            loop.close()
    
    def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.should_exit = True
        
        self._is_running = False
        self._context.set_server_status(False, self._port)
        self._context.log_event("Server stopped", "SERVER")
    
    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._is_running
    
    @property
    def app(self) -> FastAPI:
        """Get the FastAPI application instance."""
        return self._app
