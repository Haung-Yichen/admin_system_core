"""
Webhook Security Module.

Provides HMAC-SHA256 signature validation for incoming webhooks.
Implements secure signature verification following industry standards
(similar to GitHub webhooks, Stripe webhooks, etc.)

Security Features:
- HMAC-SHA256 signature validation
- Timing-safe comparison to prevent timing attacks
- IP logging for failed authentication attempts
- Support for both header-based and URL token-based authentication

Usage:
    from core.dependencies import WebhookAuthDep
    
    @router.post("/webhook")
    async def handle_webhook(auth: WebhookAuthDep):
        # auth.verified is True if signature is valid
        ...
"""

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol

from core.providers import get_configuration_provider

logger = logging.getLogger(__name__)


# =============================================================================
# Webhook Security Protocol
# =============================================================================

class IWebhookSecurityService(Protocol):
    """Protocol for webhook security service - follows ISP."""
    
    def verify_signature(
        self, 
        payload: bytes, 
        signature: str, 
        secret_key: str
    ) -> bool:
        """Verify HMAC-SHA256 signature."""
        ...
    
    def generate_signature(self, payload: bytes, secret_key: str) -> str:
        """Generate HMAC-SHA256 signature for payload."""
        ...


class WebhookAuthResult(Enum):
    """Result of webhook authentication."""
    SUCCESS = "success"
    INVALID_SIGNATURE = "invalid_signature"
    MISSING_SIGNATURE = "missing_signature"
    INVALID_TOKEN = "invalid_token"
    MISSING_TOKEN = "missing_token"
    SECRET_NOT_CONFIGURED = "secret_not_configured"


@dataclass
class WebhookAuthContext:
    """
    Context object containing webhook authentication result.
    
    Attributes:
        verified: Whether the webhook was successfully verified
        result: The authentication result enum
        source: The webhook source identifier (if provided)
        client_ip: The client IP address
        error_message: Optional error message for failed auth
    """
    verified: bool
    result: WebhookAuthResult
    source: Optional[str] = None
    client_ip: Optional[str] = None
    error_message: Optional[str] = None


# =============================================================================
# Webhook Security Service
# =============================================================================

class WebhookSecurityService:
    """
    Service for validating webhook signatures using HMAC-SHA256.
    
    Supports multiple authentication methods:
    1. X-Hub-Signature-256 header (GitHub/Ragic style)
    2. URL token parameter
    
    The service follows Single Responsibility Principle by only handling
    signature verification logic, separate from HTTP request handling.
    """
    
    # Signature header prefix (e.g., "sha256=abc123...")
    SIGNATURE_PREFIX = "sha256="
    
    def __init__(self, default_secret: Optional[str] = None) -> None:
        """
        Initialize the webhook security service.
        
        Args:
            default_secret: Optional default secret key. If not provided,
                          will be loaded from configuration.
        """
        self._default_secret = default_secret
        self._config = get_configuration_provider()
    
    def get_secret_for_source(self, source: str) -> Optional[str]:
        """
        Get the secret key for a specific webhook source.
        
        Looks for source-specific secrets first, then falls back to default.
        
        Args:
            source: The webhook source identifier (e.g., "ragic", "chatbot_sop")
            
        Returns:
            The secret key or None if not configured
        """
        # Try source-specific secret first (e.g., WEBHOOK_SECRET_RAGIC)
        source_secret = self._config.get(f"webhook.secrets.{source}")
        if source_secret:
            return source_secret
        
        # Fall back to default webhook secret
        default_secret = self._default_secret or self._config.get("webhook.default_secret")
        return default_secret
    
    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret_key: str,
    ) -> bool:
        """
        Verify HMAC-SHA256 signature.
        
        Uses constant-time comparison to prevent timing attacks.
        
        Args:
            payload: The raw request body bytes
            signature: The signature from header (with or without "sha256=" prefix)
            secret_key: The secret key to verify against
            
        Returns:
            True if signature is valid, False otherwise
        """
        if not payload or not signature or not secret_key:
            return False
        
        # Remove prefix if present
        if signature.startswith(self.SIGNATURE_PREFIX):
            signature = signature[len(self.SIGNATURE_PREFIX):]
        
        # Compute expected signature
        expected_signature = hmac.new(
            key=secret_key.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return secrets.compare_digest(signature.lower(), expected_signature.lower())
    
    def generate_signature(self, payload: bytes, secret_key: str) -> str:
        """
        Generate HMAC-SHA256 signature for payload.
        
        Useful for testing or when sending webhooks to other services.
        
        Args:
            payload: The request body bytes
            secret_key: The secret key to sign with
            
        Returns:
            The signature with "sha256=" prefix
        """
        signature = hmac.new(
            key=secret_key.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()
        
        return f"{self.SIGNATURE_PREFIX}{signature}"
    
    def verify_token(self, provided_token: str, expected_token: str) -> bool:
        """
        Verify a URL-based token.
        
        Uses constant-time comparison to prevent timing attacks.
        
        Args:
            provided_token: The token from URL parameter
            expected_token: The expected token from configuration
            
        Returns:
            True if tokens match, False otherwise
        """
        if not provided_token or not expected_token:
            return False
        
        return secrets.compare_digest(provided_token, expected_token)
    
    def authenticate_request(
        self,
        payload: bytes,
        signature_header: Optional[str],
        url_token: Optional[str],
        source: str,
        client_ip: str,
    ) -> WebhookAuthContext:
        """
        Authenticate a webhook request using available credentials.
        
        Tries signature header first, then URL token.
        
        Args:
            payload: Raw request body
            signature_header: X-Hub-Signature-256 header value
            url_token: Token from URL parameter
            source: Webhook source identifier
            client_ip: Client IP address for logging
            
        Returns:
            WebhookAuthContext with authentication result
        """
        secret = self.get_secret_for_source(source)
        
        if not secret:
            logger.warning(
                f"Webhook secret not configured for source '{source}'. "
                f"Request from IP: {client_ip}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.SECRET_NOT_CONFIGURED,
                source=source,
                client_ip=client_ip,
                error_message=f"Webhook secret not configured for source: {source}",
            )
        
        # Try header-based authentication first
        if signature_header:
            if self.verify_signature(payload, signature_header, secret):
                logger.debug(
                    f"Webhook authenticated via signature header for '{source}' "
                    f"from IP: {client_ip}"
                )
                return WebhookAuthContext(
                    verified=True,
                    result=WebhookAuthResult.SUCCESS,
                    source=source,
                    client_ip=client_ip,
                )
            else:
                logger.warning(
                    f"Invalid webhook signature for source '{source}' "
                    f"from IP: {client_ip}"
                )
                return WebhookAuthContext(
                    verified=False,
                    result=WebhookAuthResult.INVALID_SIGNATURE,
                    source=source,
                    client_ip=client_ip,
                    error_message="Invalid webhook signature",
                )
        
        # Try URL token authentication
        if url_token:
            if self.verify_token(url_token, secret):
                logger.debug(
                    f"Webhook authenticated via URL token for '{source}' "
                    f"from IP: {client_ip}"
                )
                return WebhookAuthContext(
                    verified=True,
                    result=WebhookAuthResult.SUCCESS,
                    source=source,
                    client_ip=client_ip,
                )
            else:
                logger.warning(
                    f"Invalid webhook token for source '{source}' "
                    f"from IP: {client_ip}"
                )
                return WebhookAuthContext(
                    verified=False,
                    result=WebhookAuthResult.INVALID_TOKEN,
                    source=source,
                    client_ip=client_ip,
                    error_message="Invalid webhook token",
                )
        
        # No credentials provided
        logger.warning(
            f"Missing webhook credentials for source '{source}' "
            f"from IP: {client_ip}. "
            "Expected X-Hub-Signature-256 header or 'token' URL parameter."
        )
        return WebhookAuthContext(
            verified=False,
            result=WebhookAuthResult.MISSING_SIGNATURE,
            source=source,
            client_ip=client_ip,
            error_message="Missing webhook signature or token",
        )


# =============================================================================
# Singleton Instance
# =============================================================================

_webhook_security_service: Optional[WebhookSecurityService] = None


def get_webhook_security_service() -> WebhookSecurityService:
    """
    Get the singleton WebhookSecurityService instance.
    
    Returns:
        WebhookSecurityService: The webhook security service
    """
    global _webhook_security_service
    if _webhook_security_service is None:
        _webhook_security_service = WebhookSecurityService()
    return _webhook_security_service


def reset_webhook_security_service() -> None:
    """Reset the singleton instance (for testing)."""
    global _webhook_security_service
    _webhook_security_service = None
