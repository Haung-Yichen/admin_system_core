"""
Tests for Webhook Security Module.

Tests HMAC-SHA256 signature validation and webhook authentication.
"""

import hashlib
import hmac
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from core.security.webhook import (
    WebhookAuthContext,
    WebhookAuthResult,
    WebhookSecurityService,
    get_webhook_security_service,
    reset_webhook_security_service,
)


class TestWebhookSecurityService:
    """Tests for WebhookSecurityService."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance for each test."""
        reset_webhook_security_service()
        return WebhookSecurityService(default_secret="test-secret-key")

    @pytest.fixture
    def payload(self):
        """Sample payload for testing."""
        return b'{"_ragicId": "123", "action": "update"}'

    def test_generate_signature(self, service, payload):
        """Test signature generation."""
        signature = service.generate_signature(payload, "test-secret")
        
        assert signature.startswith("sha256=")
        # Verify it's a valid hex string
        hex_part = signature[7:]
        assert len(hex_part) == 64  # SHA256 produces 64 hex chars
        int(hex_part, 16)  # Should not raise

    def test_verify_signature_valid(self, service, payload):
        """Test verification with valid signature."""
        secret = "my-secret-key"
        signature = service.generate_signature(payload, secret)
        
        assert service.verify_signature(payload, signature, secret) is True

    def test_verify_signature_with_prefix(self, service, payload):
        """Test verification accepts signature with sha256= prefix."""
        secret = "my-secret-key"
        signature = service.generate_signature(payload, secret)
        
        # Should work with prefix
        assert service.verify_signature(payload, signature, secret) is True

    def test_verify_signature_without_prefix(self, service, payload):
        """Test verification accepts signature without prefix."""
        secret = "my-secret-key"
        signature = service.generate_signature(payload, secret)
        # Remove prefix
        signature_no_prefix = signature[7:]
        
        assert service.verify_signature(payload, signature_no_prefix, secret) is True

    def test_verify_signature_invalid(self, service, payload):
        """Test verification fails with invalid signature."""
        assert service.verify_signature(payload, "sha256=invalid", "secret") is False

    def test_verify_signature_wrong_secret(self, service, payload):
        """Test verification fails with wrong secret."""
        signature = service.generate_signature(payload, "correct-secret")
        
        assert service.verify_signature(payload, signature, "wrong-secret") is False

    def test_verify_signature_modified_payload(self, service, payload):
        """Test verification fails when payload is modified."""
        secret = "my-secret-key"
        signature = service.generate_signature(payload, secret)
        
        modified_payload = b'{"_ragicId": "456", "action": "delete"}'
        assert service.verify_signature(modified_payload, signature, secret) is False

    def test_verify_signature_empty_inputs(self, service):
        """Test verification handles empty inputs safely."""
        assert service.verify_signature(b"", "sha256=abc", "secret") is False
        assert service.verify_signature(b"data", "", "secret") is False
        assert service.verify_signature(b"data", "sha256=abc", "") is False

    def test_verify_token_valid(self, service):
        """Test token verification with valid token."""
        assert service.verify_token("my-secret-token", "my-secret-token") is True

    def test_verify_token_invalid(self, service):
        """Test token verification with invalid token."""
        assert service.verify_token("wrong-token", "expected-token") is False

    def test_verify_token_empty(self, service):
        """Test token verification with empty inputs."""
        assert service.verify_token("", "expected") is False
        assert service.verify_token("provided", "") is False

    def test_authenticate_request_with_signature(self, service, payload):
        """Test authentication via signature header."""
        secret = "test-secret-key"
        signature = service.generate_signature(payload, secret)
        
        with patch.object(service, 'get_secret_for_source', return_value=secret):
            result = service.authenticate_request(
                payload=payload,
                signature_header=signature,
                url_token=None,
                source="ragic",
                client_ip="192.168.1.1",
            )
        
        assert result.verified is True
        assert result.result == WebhookAuthResult.SUCCESS
        assert result.source == "ragic"
        assert result.client_ip == "192.168.1.1"

    def test_authenticate_request_with_token(self, service, payload):
        """Test authentication via URL token."""
        secret = "test-secret-key"
        
        with patch.object(service, 'get_secret_for_source', return_value=secret):
            result = service.authenticate_request(
                payload=payload,
                signature_header=None,
                url_token=secret,
                source="ragic",
                client_ip="192.168.1.1",
            )
        
        assert result.verified is True
        assert result.result == WebhookAuthResult.SUCCESS

    def test_authenticate_request_invalid_signature(self, service, payload):
        """Test authentication fails with invalid signature."""
        secret = "test-secret-key"
        
        with patch.object(service, 'get_secret_for_source', return_value=secret):
            result = service.authenticate_request(
                payload=payload,
                signature_header="sha256=invalid",
                url_token=None,
                source="ragic",
                client_ip="192.168.1.1",
            )
        
        assert result.verified is False
        assert result.result == WebhookAuthResult.INVALID_SIGNATURE

    def test_authenticate_request_invalid_token(self, service, payload):
        """Test authentication fails with invalid token."""
        secret = "test-secret-key"
        
        with patch.object(service, 'get_secret_for_source', return_value=secret):
            result = service.authenticate_request(
                payload=payload,
                signature_header=None,
                url_token="wrong-token",
                source="ragic",
                client_ip="192.168.1.1",
            )
        
        assert result.verified is False
        assert result.result == WebhookAuthResult.INVALID_TOKEN

    def test_authenticate_request_missing_credentials(self, service, payload):
        """Test authentication fails with no credentials."""
        secret = "test-secret-key"
        
        with patch.object(service, 'get_secret_for_source', return_value=secret):
            result = service.authenticate_request(
                payload=payload,
                signature_header=None,
                url_token=None,
                source="ragic",
                client_ip="192.168.1.1",
            )
        
        assert result.verified is False
        assert result.result == WebhookAuthResult.MISSING_SIGNATURE

    def test_authenticate_request_secret_not_configured(self, service, payload):
        """Test authentication fails when secret not configured."""
        with patch.object(service, 'get_secret_for_source', return_value=None):
            result = service.authenticate_request(
                payload=payload,
                signature_header="sha256=something",
                url_token=None,
                source="unknown",
                client_ip="192.168.1.1",
            )
        
        assert result.verified is False
        assert result.result == WebhookAuthResult.SECRET_NOT_CONFIGURED

    def test_signature_prefers_over_token(self, service, payload):
        """Test that signature header is checked before URL token."""
        secret = "test-secret-key"
        valid_signature = service.generate_signature(payload, secret)
        
        with patch.object(service, 'get_secret_for_source', return_value=secret):
            # Both valid signature and invalid token provided
            result = service.authenticate_request(
                payload=payload,
                signature_header=valid_signature,
                url_token="wrong-token",  # This should be ignored
                source="ragic",
                client_ip="192.168.1.1",
            )
        
        # Should succeed because valid signature takes precedence
        assert result.verified is True

    def test_case_insensitive_signature_comparison(self, service, payload):
        """Test that signature comparison is case-insensitive."""
        secret = "test-secret-key"
        signature = service.generate_signature(payload, secret)
        
        # Convert to uppercase (after sha256= prefix)
        upper_signature = f"sha256={signature[7:].upper()}"
        
        assert service.verify_signature(payload, upper_signature, secret) is True


class TestWebhookSecurityServiceSingleton:
    """Tests for singleton pattern."""

    def test_singleton_returns_same_instance(self):
        """Test that get_webhook_security_service returns same instance."""
        reset_webhook_security_service()
        
        instance1 = get_webhook_security_service()
        instance2 = get_webhook_security_service()
        
        assert instance1 is instance2

    def test_reset_clears_singleton(self):
        """Test that reset creates new instance."""
        reset_webhook_security_service()
        
        instance1 = get_webhook_security_service()
        reset_webhook_security_service()
        instance2 = get_webhook_security_service()
        
        assert instance1 is not instance2


class TestTimingAttackPrevention:
    """Tests to verify timing attack prevention."""

    def test_uses_constant_time_comparison(self):
        """Verify that secrets.compare_digest is used."""
        import secrets as secrets_module
        
        service = WebhookSecurityService(default_secret="test")
        
        # This test verifies the implementation uses constant-time comparison
        # by checking that the code path exists
        with patch.object(secrets_module, 'compare_digest', return_value=True) as mock:
            service.verify_token("a", "b")
            mock.assert_called_once()


class TestWebhookAuthContext:
    """Tests for WebhookAuthContext dataclass."""

    def test_auth_context_creation(self):
        """Test creating auth context."""
        context = WebhookAuthContext(
            verified=True,
            result=WebhookAuthResult.SUCCESS,
            source="test",
            client_ip="127.0.0.1",
        )
        
        assert context.verified is True
        assert context.result == WebhookAuthResult.SUCCESS
        assert context.source == "test"
        assert context.client_ip == "127.0.0.1"
        assert context.error_message is None

    def test_auth_context_with_error(self):
        """Test creating auth context with error."""
        context = WebhookAuthContext(
            verified=False,
            result=WebhookAuthResult.INVALID_SIGNATURE,
            source="test",
            client_ip="192.168.1.100",
            error_message="Signature mismatch",
        )
        
        assert context.verified is False
        assert context.error_message == "Signature mismatch"
