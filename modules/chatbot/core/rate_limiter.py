"""
Rate Limiter for Chatbot Module.

Simple in-memory rate limiting for magic link requests.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List

from fastapi import HTTPException, Request, status


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit rule."""
    max_requests: int
    window_seconds: int


@dataclass
class RateLimiter:
    """
    Simple in-memory rate limiter.
    
    Uses sliding window approach for rate limiting.
    """
    
    rules: List[RateLimitConfig] = field(default_factory=list)
    _requests: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    _lock: Lock = field(default_factory=Lock)
    
    def _get_client_key(self, request: Request) -> str:
        """Get unique identifier for the client (IP address)."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
    
    def _cleanup_old_requests(self, key: str, current_time: float) -> None:
        """Remove expired requests from tracking."""
        max_window = max(rule.window_seconds for rule in self.rules) if self.rules else 3600
        cutoff = current_time - max_window
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]
    
    def check_rate_limit(self, request: Request) -> None:
        """
        Check if request is within rate limits.
        
        Args:
            request: FastAPI request object.
        
        Raises:
            HTTPException: If rate limit exceeded.
        """
        key = self._get_client_key(request)
        current_time = time.time()
        
        with self._lock:
            self._cleanup_old_requests(key, current_time)
            
            for rule in self.rules:
                cutoff = current_time - rule.window_seconds
                recent_requests = [t for t in self._requests[key] if t > cutoff]
                
                if len(recent_requests) >= rule.max_requests:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"請求次數過多，請稍後再試。Too many requests. Please try again later.",
                    )
            
            self._requests[key].append(current_time)


# Default rate limiter for magic link requests
magic_link_limiter = RateLimiter(
    rules=[
        RateLimitConfig(max_requests=3, window_seconds=60),   # 3 per minute
        RateLimitConfig(max_requests=10, window_seconds=3600), # 10 per hour
    ]
)
