"""
Global Rate Limiting Middleware.

Provides IP-based rate limiting for all API endpoints.
Works with Cloudflare by respecting CF-Connecting-IP header.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

import logging

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    
    # Requests per window
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    
    # Stricter limits for sensitive endpoints
    auth_requests_per_minute: int = 10
    auth_requests_per_hour: int = 50
    
    # Endpoints that should have stricter limits
    sensitive_paths: tuple[str, ...] = (
        "/auth/",
        "/admin/auth/",
        "/webhook/",
    )


@dataclass
class RateLimitState:
    """Per-IP rate limit state."""
    
    minute_requests: list[float] = field(default_factory=list)
    hour_requests: list[float] = field(default_factory=list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    IP-based rate limiting middleware.
    
    Features:
    - Respects Cloudflare CF-Connecting-IP header
    - Sliding window rate limiting
    - Stricter limits for authentication endpoints
    - Automatic cleanup of old entries
    """
    
    def __init__(self, app, config: RateLimitConfig | None = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self._states: dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 minutes
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Get real client IP, respecting Cloudflare headers.
        
        Priority:
        1. CF-Connecting-IP (Cloudflare)
        2. X-Forwarded-For (first IP)
        3. X-Real-IP
        4. Direct client host
        """
        # Cloudflare header
        cf_ip = request.headers.get("CF-Connecting-IP")
        if cf_ip:
            return cf_ip
        
        # X-Forwarded-For (take first IP)
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        
        # X-Real-IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        return request.client.host if request.client else "unknown"
    
    def _is_sensitive_path(self, path: str) -> bool:
        """Check if path requires stricter rate limits."""
        return any(path.startswith(p) for p in self.config.sensitive_paths)
    
    def _cleanup_old_entries(self, now: float) -> None:
        """Remove expired entries from all states."""
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        self._last_cleanup = now
        hour_ago = now - 3600
        
        # Clean up old entries
        to_delete = []
        for ip, state in self._states.items():
            state.minute_requests = [t for t in state.minute_requests if t > now - 60]
            state.hour_requests = [t for t in state.hour_requests if t > hour_ago]
            
            # Mark for deletion if empty
            if not state.minute_requests and not state.hour_requests:
                to_delete.append(ip)
        
        for ip in to_delete:
            del self._states[ip]
    
    def _check_rate_limit(self, ip: str, is_sensitive: bool, now: float) -> None:
        """
        Check if request is within rate limits.
        
        Raises:
            HTTPException: If rate limit exceeded.
        """
        state = self._states[ip]
        
        # Clean old requests from this IP's state
        state.minute_requests = [t for t in state.minute_requests if t > now - 60]
        state.hour_requests = [t for t in state.hour_requests if t > now - 3600]
        
        # Get limits based on path sensitivity
        if is_sensitive:
            minute_limit = self.config.auth_requests_per_minute
            hour_limit = self.config.auth_requests_per_hour
        else:
            minute_limit = self.config.requests_per_minute
            hour_limit = self.config.requests_per_hour
        
        # Check minute limit
        if len(state.minute_requests) >= minute_limit:
            logger.warning(f"Rate limit exceeded (minute) for IP: {ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down.",
                headers={"Retry-After": "60"},
            )
        
        # Check hour limit
        if len(state.hour_requests) >= hour_limit:
            logger.warning(f"Rate limit exceeded (hour) for IP: {ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": "3600"},
            )
        
        # Record this request
        state.minute_requests.append(now)
        state.hour_requests.append(now)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through rate limiting."""
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        now = time.time()
        
        # Periodic cleanup
        self._cleanup_old_entries(now)
        
        # Get client IP and check limits
        client_ip = self._get_client_ip(request)
        is_sensitive = self._is_sensitive_path(request.url.path)
        
        self._check_rate_limit(client_ip, is_sensitive, now)
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        state = self._states[client_ip]
        if is_sensitive:
            remaining = self.config.auth_requests_per_minute - len(state.minute_requests)
        else:
            remaining = self.config.requests_per_minute - len(state.minute_requests)
        
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        
        return response
