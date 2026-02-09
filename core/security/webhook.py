"""
Webhook Security Module.

Provides signature validation for incoming webhooks using Strategy Pattern.
Supports multiple verification strategies:
- HMAC-SHA256 (GitHub/Stripe style - header-based)
- RSA-SHA256 (Ragic style - body-embedded signature)

Security Features:
- HMAC-SHA256 signature validation with timing-safe comparison
- RSA-SHA256 signature validation with public key verification
- IP logging for failed authentication attempts
- Support for both header-based and body-embedded authentication

Design Patterns:
- Strategy Pattern for verification algorithms (OCP compliance)
- Factory Pattern for verifier selection
- Single Responsibility Principle for each component

Usage:
    from core.security.webhook import get_verifier_factory, VerifierType
    
    factory = get_verifier_factory()
    verifier = factory.get_verifier(VerifierType.RAGIC_RSA)
    is_valid = await verifier.verify(request)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol

from fastapi import Request

from core.providers import get_configuration_provider

logger = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_RAGIC_PUBLIC_KEY_PATH = Path("resources/certs/ragic_public_key.pem")


# =============================================================================
# Enums & Data Classes
# =============================================================================

class VerifierType(str, Enum):
    """Supported webhook verification strategies."""
    HMAC_SHA256 = "hmac_sha256"
    RAGIC_RSA = "ragic_rsa"


class WebhookAuthResult(Enum):
    """Result of webhook authentication."""
    SUCCESS = "success"
    INVALID_SIGNATURE = "invalid_signature"
    MISSING_SIGNATURE = "missing_signature"
    INVALID_TOKEN = "invalid_token"
    MISSING_TOKEN = "missing_token"
    SECRET_NOT_CONFIGURED = "secret_not_configured"
    PUBLIC_KEY_NOT_FOUND = "public_key_not_found"
    INVALID_PAYLOAD = "invalid_payload"


@dataclass
class WebhookAuthContext:
    """
    Context object containing webhook authentication result.
    
    Attributes:
        verified: Whether the webhook was successfully verified.
        result: The authentication result enum.
        source: The webhook source identifier (if provided).
        client_ip: The client IP address.
        error_message: Optional error message for failed auth.
        payload_data: Optional parsed payload data (for successful verification).
    """
    verified: bool
    result: WebhookAuthResult
    source: Optional[str] = None
    client_ip: Optional[str] = None
    error_message: Optional[str] = None
    payload_data: Optional[dict[str, Any]] = None


# =============================================================================
# Webhook Security Protocol (Interface)
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


# =============================================================================
# Abstract Webhook Verifier Interface (Strategy Pattern)
# =============================================================================

class IWebhookVerifier(ABC):
    """
    Abstract interface for webhook verification strategies.
    
    Implements the Strategy Pattern to allow different verification
    algorithms to be used interchangeably (OCP compliance).
    
    Each concrete implementation handles a specific verification method:
    - HmacVerifier: Header-based HMAC-SHA256 (GitHub, Stripe style)
    - RagicRSAVerifier: Body-embedded RSA-SHA256 (Ragic style)
    """
    
    @abstractmethod
    async def verify(
        self,
        request: Request,
        secret: Optional[str] = None,
    ) -> WebhookAuthContext:
        """
        Verify the webhook request signature.
        
        Args:
            request: The FastAPI Request object containing headers and body.
            secret: Optional shared secret or identifier for verification.
                   For HMAC, this is the shared secret key.
                   For RSA, this parameter is typically unused (uses public key).
        
        Returns:
            WebhookAuthContext: Authentication context with verification result.
        
        Raises:
            This method should NOT raise exceptions. All errors should be
            captured in the WebhookAuthContext.error_message field.
        """
        ...
    
    @abstractmethod
    def get_verifier_type(self) -> VerifierType:
        """
        Get the verifier type identifier.
        
        Returns:
            VerifierType: The type of this verifier.
        """
        ...


# =============================================================================
# HMAC-SHA256 Verifier Implementation
# =============================================================================

class HmacVerifier(IWebhookVerifier):
    """
    HMAC-SHA256 webhook signature verifier.
    
    Validates webhooks using the X-Hub-Signature-256 header pattern,
    commonly used by GitHub, Stripe, and other services.
    
    Security Features:
        - Constant-time comparison to prevent timing attacks
        - Supports both prefixed (sha256=...) and raw signatures
    
    Attributes:
        SIGNATURE_HEADER: The HTTP header containing the signature.
        SIGNATURE_PREFIX: The prefix for signature values.
    """
    
    SIGNATURE_HEADER = "X-Hub-Signature-256"
    SIGNATURE_PREFIX = "sha256="
    
    def __init__(self, default_secret: Optional[str] = None) -> None:
        """
        Initialize the HMAC verifier.
        
        Args:
            default_secret: Default secret key for verification.
                           If not provided, must be passed to verify().
        """
        self._default_secret = default_secret
        self._config = get_configuration_provider()
    
    def get_verifier_type(self) -> VerifierType:
        """Get the verifier type identifier."""
        return VerifierType.HMAC_SHA256
    
    async def verify(
        self,
        request: Request,
        secret: Optional[str] = None,
    ) -> WebhookAuthContext:
        """
        Verify HMAC-SHA256 signature from request header.
        
        Args:
            request: The FastAPI Request object.
            secret: The shared secret key. Falls back to default if not provided.
        
        Returns:
            WebhookAuthContext: Authentication result with verification status.
        """
        client_ip = self._get_client_ip(request)
        source = request.query_params.get("source", "unknown")
        
        # Determine secret to use
        secret_key = secret or self._default_secret
        if not secret_key:
            secret_key = self._get_secret_for_source(source)
        
        if not secret_key:
            logger.warning(
                f"HMAC verification failed: No secret configured. "
                f"source={source}, ip={client_ip}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.SECRET_NOT_CONFIGURED,
                source=source,
                client_ip=client_ip,
                error_message="Webhook secret not configured",
            )
        
        # Get signature from header
        signature_header = request.headers.get(self.SIGNATURE_HEADER)
        if not signature_header:
            logger.warning(
                f"HMAC verification failed: Missing signature header. "
                f"source={source}, ip={client_ip}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.MISSING_SIGNATURE,
                source=source,
                client_ip=client_ip,
                error_message=f"Missing {self.SIGNATURE_HEADER} header",
            )
        
        # Get request body
        try:
            payload = await request.body()
        except Exception as e:
            logger.error(
                f"HMAC verification failed: Could not read request body. "
                f"source={source}, ip={client_ip}, error={e}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.INVALID_PAYLOAD,
                source=source,
                client_ip=client_ip,
                error_message="Failed to read request body",
            )
        
        # Verify signature
        if self._verify_signature(payload, signature_header, secret_key):
            logger.debug(
                f"HMAC verification successful. source={source}, ip={client_ip}"
            )
            return WebhookAuthContext(
                verified=True,
                result=WebhookAuthResult.SUCCESS,
                source=source,
                client_ip=client_ip,
            )
        else:
            logger.warning(
                f"HMAC verification failed: Invalid signature. "
                f"source={source}, ip={client_ip}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.INVALID_SIGNATURE,
                source=source,
                client_ip=client_ip,
                error_message="Invalid HMAC signature",
            )
    
    def _verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret_key: str,
    ) -> bool:
        """
        Verify HMAC-SHA256 signature using constant-time comparison.
        
        Args:
            payload: The raw request body bytes.
            signature: The signature from header (with or without prefix).
            secret_key: The secret key to verify against.
        
        Returns:
            bool: True if signature is valid, False otherwise.
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
            payload: The request body bytes.
            secret_key: The secret key to sign with.
        
        Returns:
            str: The signature with "sha256=" prefix.
        """
        signature = hmac.new(
            key=secret_key.encode("utf-8"),
            msg=payload,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return f"{self.SIGNATURE_PREFIX}{signature}"
    
    def _get_secret_for_source(self, source: str) -> Optional[str]:
        """
        Get the secret key for a specific webhook source.
        
        Args:
            source: The webhook source identifier.
        
        Returns:
            Optional[str]: The secret key or None if not configured.
        """
        # Try source-specific secret first
        source_secret = self._config.get(f"webhook.secrets.{source}")
        if source_secret:
            return source_secret
        
        # Fall back to default
        return self._config.get("webhook.default_secret")
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request.
        
        Args:
            request: The FastAPI Request object.
        
        Returns:
            str: The client IP address.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# =============================================================================
# RSA-SHA256 Verifier Implementation (Ragic)
# =============================================================================

class RagicRSAVerifier(IWebhookVerifier):
    """
    RSA-SHA256 webhook signature verifier for Ragic webhooks.
    
    Ragic sends webhooks with the signature embedded in the JSON body:
    {
        "data": [...],
        "signature": "<base64-encoded-signature>"
    }
    
    Verification Process:
        1. Parse JSON body and extract 'data' and 'signature' fields.
        2. Serialize 'data' to normalized JSON (sorted keys, no spaces).
        3. Decode base64 signature.
        4. Verify signature using RSA public key (PKCS1v15, SHA256).
    
    Attributes:
        public_key_path: Path to the Ragic public key PEM file.
    """
    
    def __init__(
        self,
        public_key_path: Optional[Path] = None,
    ) -> None:
        """
        Initialize the Ragic RSA verifier.
        
        Args:
            public_key_path: Path to the public key PEM file.
                            Defaults to resources/certs/ragic_public_key.pem.
        """
        self._public_key_path = public_key_path or DEFAULT_RAGIC_PUBLIC_KEY_PATH
        self._public_key: Optional[Any] = None
        self._key_load_error: Optional[str] = None
        self._load_public_key()
    
    def get_verifier_type(self) -> VerifierType:
        """Get the verifier type identifier."""
        return VerifierType.RAGIC_RSA
    
    def _load_public_key(self) -> None:
        """
        Load the RSA public key from PEM file.
        
        This is called during initialization and caches the key.
        Errors are stored for later reporting in verify().
        """
        try:
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            
            if not self._public_key_path.exists():
                self._key_load_error = (
                    f"Ragic public key file not found: {self._public_key_path}"
                )
                logger.error(self._key_load_error)
                return
            
            with open(self._public_key_path, "rb") as f:
                pem_data = f.read()
            
            self._public_key = serialization.load_pem_public_key(
                pem_data,
                backend=default_backend(),
            )
            logger.info(
                f"Loaded Ragic RSA public key from: {self._public_key_path}"
            )
            
        except ImportError as e:
            self._key_load_error = (
                f"cryptography library not installed: {e}"
            )
            logger.error(self._key_load_error)
        except Exception as e:
            self._key_load_error = (
                f"Failed to load Ragic public key: {e}"
            )
            logger.error(self._key_load_error)
    
    async def verify(
        self,
        request: Request,
        secret: Optional[str] = None,
    ) -> WebhookAuthContext:
        """
        Verify RSA-SHA256 signature from Ragic webhook.
        
        Args:
            request: The FastAPI Request object.
            secret: Unused for RSA verification (uses public key instead).
        
        Returns:
            WebhookAuthContext: Authentication result with verification status
                               and parsed payload data on success.
        """
        client_ip = self._get_client_ip(request)
        source = request.query_params.get("source", "ragic")
        
        # Check if public key was loaded successfully
        if self._public_key is None:
            logger.error(
                f"Ragic RSA verification failed: Public key not loaded. "
                f"source={source}, ip={client_ip}, error={self._key_load_error}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.PUBLIC_KEY_NOT_FOUND,
                source=source,
                client_ip=client_ip,
                error_message=self._key_load_error or "Public key not loaded",
            )
        
        # Parse JSON body
        try:
            body = await request.body()
            payload = json.loads(body)
        except json.JSONDecodeError as e:
            logger.warning(
                f"Ragic RSA verification failed: Invalid JSON payload. "
                f"source={source}, ip={client_ip}, error={e}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.INVALID_PAYLOAD,
                source=source,
                client_ip=client_ip,
                error_message=f"Invalid JSON payload: {e}",
            )
        except Exception as e:
            logger.error(
                f"Ragic RSA verification failed: Could not read body. "
                f"source={source}, ip={client_ip}, error={e}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.INVALID_PAYLOAD,
                source=source,
                client_ip=client_ip,
                error_message=f"Failed to read request body: {e}",
            )
        
        # Extract data and signature
        data = payload.get("data")
        signature_b64 = payload.get("signature")
        
        if data is None:
            logger.warning(
                f"Ragic RSA verification failed: Missing 'data' field. "
                f"source={source}, ip={client_ip}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.INVALID_PAYLOAD,
                source=source,
                client_ip=client_ip,
                error_message="Payload missing 'data' field",
            )
        
        if not signature_b64:
            logger.warning(
                f"Ragic RSA verification failed: Missing 'signature' field. "
                f"source={source}, ip={client_ip}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.MISSING_SIGNATURE,
                source=source,
                client_ip=client_ip,
                error_message="Payload missing 'signature' field",
            )
        
        # Normalize data for verification
        normalized_message = self._normalize_data(data)
        
        # Decode signature
        try:
            signature_bytes = base64.b64decode(signature_b64)
        except Exception as e:
            logger.warning(
                f"Ragic RSA verification failed: Invalid base64 signature. "
                f"source={source}, ip={client_ip}, error={e}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.INVALID_SIGNATURE,
                source=source,
                client_ip=client_ip,
                error_message=f"Invalid base64 signature: {e}",
            )
        
        # Verify signature
        if self._verify_rsa_signature(normalized_message, signature_bytes):
            logger.debug(
                f"Ragic RSA verification successful. source={source}, ip={client_ip}"
            )
            return WebhookAuthContext(
                verified=True,
                result=WebhookAuthResult.SUCCESS,
                source=source,
                client_ip=client_ip,
                payload_data={"data": data},
            )
        else:
            logger.warning(
                f"Ragic RSA verification failed: Invalid signature. "
                f"source={source}, ip={client_ip}"
            )
            return WebhookAuthContext(
                verified=False,
                result=WebhookAuthResult.INVALID_SIGNATURE,
                source=source,
                client_ip=client_ip,
                error_message="Invalid RSA signature",
            )
    
    def _normalize_data(self, data: Any) -> bytes:
        """
        Normalize data for signature verification.
        
        Serializes data to JSON with keys sorted alphabetically
        and no whitespace (separators=(',', ':')).
        
        Args:
            data: The data to normalize (typically a list of dicts).
        
        Returns:
            bytes: The normalized JSON string as bytes.
        """
        normalized = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return normalized.encode("utf-8")
    
    def _verify_rsa_signature(
        self,
        message: bytes,
        signature: bytes,
    ) -> bool:
        """
        Verify RSA-SHA256 signature using the public key.
        
        Args:
            message: The normalized message bytes.
            signature: The decoded signature bytes.
        
        Returns:
            bool: True if signature is valid, False otherwise.
        """
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.exceptions import InvalidSignature
            
            self._public_key.verify(
                signature,
                message,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
            
        except InvalidSignature:
            logger.debug("RSA signature verification failed: InvalidSignature")
            return False
        except Exception as e:
            logger.error(f"RSA signature verification error: {e}")
            return False
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP from request.
        
        Args:
            request: The FastAPI Request object.
        
        Returns:
            str: The client IP address.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "unknown"


# =============================================================================
# Verifier Factory
# =============================================================================

class WebhookVerifierFactory:
    """
    Factory for creating webhook verifier instances.
    
    Follows the Factory Pattern to decouple verifier creation from usage.
    Supports registration of custom verifiers for extensibility.
    
    Example:
        factory = WebhookVerifierFactory()
        hmac_verifier = factory.get_verifier(VerifierType.HMAC_SHA256)
        ragic_verifier = factory.get_verifier(VerifierType.RAGIC_RSA)
    """
    
    def __init__(self) -> None:
        """Initialize the factory with default verifiers."""
        self._verifiers: dict[VerifierType, IWebhookVerifier] = {}
        self._register_default_verifiers()
    
    def _register_default_verifiers(self) -> None:
        """Register the default verifier implementations."""
        self._verifiers[VerifierType.HMAC_SHA256] = HmacVerifier()
        self._verifiers[VerifierType.RAGIC_RSA] = RagicRSAVerifier()
    
    def get_verifier(self, verifier_type: VerifierType) -> IWebhookVerifier:
        """
        Get a verifier instance by type.
        
        Args:
            verifier_type: The type of verifier to retrieve.
        
        Returns:
            IWebhookVerifier: The verifier instance.
        
        Raises:
            ValueError: If the verifier type is not registered.
        """
        verifier = self._verifiers.get(verifier_type)
        if verifier is None:
            raise ValueError(f"Unknown verifier type: {verifier_type}")
        return verifier
    
    def register_verifier(
        self,
        verifier_type: VerifierType,
        verifier: IWebhookVerifier,
    ) -> None:
        """
        Register a custom verifier implementation.
        
        Args:
            verifier_type: The type identifier for the verifier.
            verifier: The verifier instance to register.
        """
        self._verifiers[verifier_type] = verifier
        logger.info(f"Registered custom verifier: {verifier_type.value}")
    
    def get_available_types(self) -> list[VerifierType]:
        """
        Get list of available verifier types.
        
        Returns:
            list[VerifierType]: List of registered verifier types.
        """
        return list(self._verifiers.keys())


# =============================================================================
# Legacy Webhook Security Service (Backward Compatibility)
# =============================================================================

class WebhookSecurityService:
    """
    Service for validating webhook signatures using HMAC-SHA256.
    
    This class is maintained for backward compatibility with existing code.
    New code should use the IWebhookVerifier interface via the factory.
    
    Supports multiple authentication methods:
    1. X-Hub-Signature-256 header (GitHub/Ragic style)
    2. URL token parameter
    """
    
    SIGNATURE_PREFIX = "sha256="
    
    def __init__(self, default_secret: Optional[str] = None) -> None:
        """
        Initialize the webhook security service.
        
        Args:
            default_secret: Optional default secret key.
        """
        self._default_secret = default_secret
        self._config = get_configuration_provider()
        self._hmac_verifier = HmacVerifier(default_secret)
    
    def get_secret_for_source(self, source: str) -> Optional[str]:
        """
        Get the secret key for a specific webhook source.
        
        Args:
            source: The webhook source identifier.
        
        Returns:
            Optional[str]: The secret key or None.
        """
        source_secret = self._config.get(f"webhook.secrets.{source}")
        if source_secret:
            return source_secret
        return self._default_secret or self._config.get("webhook.default_secret")
    
    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret_key: str,
    ) -> bool:
        """
        Verify HMAC-SHA256 signature.
        
        Args:
            payload: The raw request body bytes.
            signature: The signature from header.
            secret_key: The secret key to verify against.
        
        Returns:
            bool: True if signature is valid.
        """
        return self._hmac_verifier._verify_signature(payload, signature, secret_key)
    
    def generate_signature(self, payload: bytes, secret_key: str) -> str:
        """
        Generate HMAC-SHA256 signature for payload.
        
        Args:
            payload: The request body bytes.
            secret_key: The secret key to sign with.
        
        Returns:
            str: The signature with prefix.
        """
        return self._hmac_verifier.generate_signature(payload, secret_key)
    
    def verify_token(self, provided_token: str, expected_token: str) -> bool:
        """
        Verify a URL-based token.
        
        Args:
            provided_token: The token from URL parameter.
            expected_token: The expected token.
        
        Returns:
            bool: True if tokens match.
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
        
        Args:
            payload: Raw request body.
            signature_header: X-Hub-Signature-256 header value.
            url_token: Token from URL parameter.
            source: Webhook source identifier.
            client_ip: Client IP address.
        
        Returns:
            WebhookAuthContext: Authentication result.
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
# Singleton Instances
# =============================================================================

_webhook_security_service: Optional[WebhookSecurityService] = None
_verifier_factory: Optional[WebhookVerifierFactory] = None


def get_webhook_security_service() -> WebhookSecurityService:
    """
    Get the singleton WebhookSecurityService instance.
    
    Returns:
        WebhookSecurityService: The webhook security service.
    """
    global _webhook_security_service
    if _webhook_security_service is None:
        _webhook_security_service = WebhookSecurityService()
    return _webhook_security_service


def get_verifier_factory() -> WebhookVerifierFactory:
    """
    Get the singleton WebhookVerifierFactory instance.
    
    Returns:
        WebhookVerifierFactory: The verifier factory.
    """
    global _verifier_factory
    if _verifier_factory is None:
        _verifier_factory = WebhookVerifierFactory()
    return _verifier_factory


def reset_webhook_security_service() -> None:
    """Reset singleton instances (for testing)."""
    global _webhook_security_service, _verifier_factory
    _webhook_security_service = None
    _verifier_factory = None
