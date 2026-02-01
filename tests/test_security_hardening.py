"""
Security Hardening Tests.

Tests for security fixes including:
- Webhook signature verification (401/403 on invalid/missing signatures)
- Encryption service (HKDF, encrypt/decrypt, blind index consistency)
- User enumeration prevention in initiate_magic_link

These tests verify that security vulnerabilities have been properly addressed.
"""

import hashlib
import hmac
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Webhook Security Tests
# =============================================================================

class TestWebhookSignatureVerification:
    """
    Tests for webhook signature verification.
    
    Verifies:
    - Valid signatures return success (200)
    - Invalid signatures return failure (401/403)
    - Missing signatures return failure (401/403)
    """

    @pytest.fixture
    def webhook_service(self):
        """Create a fresh WebhookSecurityService instance."""
        from core.security.webhook import (
            WebhookSecurityService,
            reset_webhook_security_service,
        )
        
        reset_webhook_security_service()
        return WebhookSecurityService(default_secret="test-webhook-secret")

    @pytest.fixture
    def sample_payload(self):
        """Sample webhook payload."""
        return b'{"_ragicId": "123", "employee_id": "E001", "action": "update"}'

    def test_valid_signature_returns_success(self, webhook_service, sample_payload):
        """Test: Valid HMAC-SHA256 signature -> Success (verified=True)."""
        from core.security.webhook import WebhookAuthResult
        
        secret = "test-webhook-secret"
        signature = webhook_service.generate_signature(sample_payload, secret)

        with patch.object(webhook_service, 'get_secret_for_source', return_value=secret):
            result = webhook_service.authenticate_request(
                payload=sample_payload,
                signature_header=signature,
                url_token=None,
                source="ragic",
                client_ip="192.168.1.100",
            )

        assert result.verified is True
        assert result.result == WebhookAuthResult.SUCCESS
        assert result.error_message is None

    def test_invalid_signature_returns_failure(self, webhook_service, sample_payload):
        """Test: Invalid signature -> Failure (verified=False, INVALID_SIGNATURE)."""
        from core.security.webhook import WebhookAuthResult
        
        secret = "test-webhook-secret"
        wrong_signature = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

        with patch.object(webhook_service, 'get_secret_for_source', return_value=secret):
            result = webhook_service.authenticate_request(
                payload=sample_payload,
                signature_header=wrong_signature,
                url_token=None,
                source="ragic",
                client_ip="192.168.1.100",
            )

        assert result.verified is False
        assert result.result == WebhookAuthResult.INVALID_SIGNATURE
        assert result.error_message is not None

    def test_missing_signature_returns_failure(self, webhook_service, sample_payload):
        """Test: No signature header and no token -> Failure (MISSING_SIGNATURE)."""
        from core.security.webhook import WebhookAuthResult
        
        secret = "test-webhook-secret"

        with patch.object(webhook_service, 'get_secret_for_source', return_value=secret):
            result = webhook_service.authenticate_request(
                payload=sample_payload,
                signature_header=None,
                url_token=None,
                source="ragic",
                client_ip="192.168.1.100",
            )

        assert result.verified is False
        assert result.result == WebhookAuthResult.MISSING_SIGNATURE

    def test_tampered_payload_fails_verification(self, webhook_service, sample_payload):
        """Test: Signature verification fails when payload is tampered."""
        from core.security.webhook import WebhookAuthResult
        
        secret = "test-webhook-secret"
        signature = webhook_service.generate_signature(sample_payload, secret)

        # Tamper with the payload
        tampered_payload = b'{"_ragicId": "999", "employee_id": "HACKER", "action": "delete"}'

        with patch.object(webhook_service, 'get_secret_for_source', return_value=secret):
            result = webhook_service.authenticate_request(
                payload=tampered_payload,
                signature_header=signature,
                url_token=None,
                source="ragic",
                client_ip="192.168.1.100",
            )

        assert result.verified is False
        assert result.result == WebhookAuthResult.INVALID_SIGNATURE

    def test_wrong_secret_key_fails_verification(self, webhook_service, sample_payload):
        """Test: Signature verification fails with wrong secret key."""
        from core.security.webhook import WebhookAuthResult
        
        # Sign with one secret
        signature = webhook_service.generate_signature(sample_payload, "attacker-secret")

        # But verify with different secret
        with patch.object(webhook_service, 'get_secret_for_source', return_value="actual-secret"):
            result = webhook_service.authenticate_request(
                payload=sample_payload,
                signature_header=signature,
                url_token=None,
                source="ragic",
                client_ip="192.168.1.100",
            )

        assert result.verified is False
        assert result.result == WebhookAuthResult.INVALID_SIGNATURE

    def test_empty_signature_fails(self, webhook_service, sample_payload):
        """Test: Empty signature string fails verification."""
        from core.security.webhook import WebhookAuthResult
        
        secret = "test-webhook-secret"

        with patch.object(webhook_service, 'get_secret_for_source', return_value=secret):
            result = webhook_service.authenticate_request(
                payload=sample_payload,
                signature_header="",  # Empty signature
                url_token=None,
                source="ragic",
                client_ip="192.168.1.100",
            )

        # Empty string should be treated as missing
        assert result.verified is False

    def test_signature_hex_is_case_insensitive(self, webhook_service, sample_payload):
        """Test: Signature hex comparison is case-insensitive (uppercase hex part)."""
        secret = "test-webhook-secret"
        signature = webhook_service.generate_signature(sample_payload, secret)
        
        # Keep prefix lowercase, convert only hex part to uppercase
        # signature format: "sha256=<hex>"
        prefix = "sha256="
        hex_part = signature[len(prefix):]
        uppercase_hex_signature = prefix + hex_part.upper()

        with patch.object(webhook_service, 'get_secret_for_source', return_value=secret):
            result = webhook_service.authenticate_request(
                payload=sample_payload,
                signature_header=uppercase_hex_signature,
                url_token=None,
                source="ragic",
                client_ip="192.168.1.100",
            )

        assert result.verified is True

    def test_invalid_token_returns_failure(self, webhook_service, sample_payload):
        """Test: Invalid URL token -> Failure (INVALID_TOKEN)."""
        from core.security.webhook import WebhookAuthResult
        
        secret = "correct-token"

        with patch.object(webhook_service, 'get_secret_for_source', return_value=secret):
            result = webhook_service.authenticate_request(
                payload=sample_payload,
                signature_header=None,
                url_token="wrong-token",
                source="ragic",
                client_ip="192.168.1.100",
            )

        assert result.verified is False
        assert result.result == WebhookAuthResult.INVALID_TOKEN


# =============================================================================
# Encryption Service Tests
# =============================================================================

class TestEncryptionServiceHKDF:
    """
    Tests for EncryptionService HKDF key derivation.
    
    Verifies:
    - HKDF is correctly executed during initialization
    - Encryption and decryption work properly
    - Blind index generation is consistent
    """

    @pytest.fixture
    def master_key(self):
        """Generate a random 32-byte master key for testing."""
        return os.urandom(32)

    def test_hkdf_derives_different_keys_from_master(self, master_key):
        """Test: HKDF derives keys different from the master key."""
        from core.security.encryption import EncryptionService

        service = EncryptionService(master_key=master_key, legacy_mode=False)

        # In non-legacy mode, encryption key should NOT equal master key
        assert service._encryption_key != master_key
        assert service._index_key != master_key

    def test_hkdf_encryption_and_index_keys_are_separate(self, master_key):
        """Test: Encryption key and index key are cryptographically separate."""
        from core.security.encryption import EncryptionService

        service = EncryptionService(master_key=master_key, legacy_mode=False)

        # Keys should be different (cryptographic separation)
        assert service._encryption_key != service._index_key

    def test_hkdf_deterministic_key_derivation(self, master_key):
        """Test: Same master key produces same derived keys."""
        from core.security.encryption import EncryptionService

        service1 = EncryptionService(master_key=master_key, legacy_mode=False)
        service2 = EncryptionService(master_key=master_key, legacy_mode=False)

        assert service1._encryption_key == service2._encryption_key
        assert service1._index_key == service2._index_key

    def test_different_master_keys_produce_different_derived_keys(self):
        """Test: Different master keys produce different derived keys."""
        from core.security.encryption import EncryptionService

        key1 = os.urandom(32)
        key2 = os.urandom(32)

        service1 = EncryptionService(master_key=key1, legacy_mode=False)
        service2 = EncryptionService(master_key=key2, legacy_mode=False)

        assert service1._encryption_key != service2._encryption_key
        assert service1._index_key != service2._index_key


class TestEncryptionServiceEncryptDecrypt:
    """Tests for encrypt/decrypt operations."""

    @pytest.fixture
    def encryption_service(self):
        """Create an EncryptionService with random key."""
        from core.security.encryption import EncryptionService
        
        return EncryptionService(master_key=os.urandom(32))

    def test_encrypt_decrypt_roundtrip(self, encryption_service):
        """Test: Encrypt then decrypt returns original plaintext."""
        plaintext = "sensitive-user-data@example.com"
        
        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_encrypt_decrypt_unicode(self, encryption_service):
        """Test: Encrypt/decrypt works with Unicode characters."""
        plaintext = "敏感資料：使用者@公司.com 🔐"
        
        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)
        
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext_each_time(self, encryption_service):
        """Test: Same plaintext encrypts to different ciphertext (random nonce)."""
        plaintext = "same-plaintext"
        
        encrypted1 = encryption_service.encrypt(plaintext)
        encrypted2 = encryption_service.encrypt(plaintext)
        
        # Ciphertext should differ due to random nonce
        assert encrypted1 != encrypted2
        
        # But both should decrypt to same plaintext
        assert encryption_service.decrypt(encrypted1) == plaintext
        assert encryption_service.decrypt(encrypted2) == plaintext

    def test_decrypt_with_wrong_key_fails(self):
        """Test: Decrypting with wrong key raises error."""
        from core.security.encryption import EncryptionService
        from cryptography.exceptions import InvalidTag
        
        service1 = EncryptionService(master_key=os.urandom(32))
        service2 = EncryptionService(master_key=os.urandom(32))
        
        encrypted = service1.encrypt("secret data")
        
        # Should fail with InvalidTag (AES-GCM authentication failure)
        with pytest.raises(InvalidTag):
            service2.decrypt(encrypted)

    def test_encrypt_empty_string_returns_empty_bytes(self, encryption_service):
        """Test: Encrypting empty string returns empty bytes."""
        encrypted = encryption_service.encrypt("")
        assert encrypted == b""

    def test_decrypt_empty_bytes_returns_empty_string(self, encryption_service):
        """Test: Decrypting empty bytes returns empty string."""
        decrypted = encryption_service.decrypt(b"")
        assert decrypted == ""


class TestBlindIndexGeneration:
    """Tests for blind index (HMAC-SHA256) generation."""

    @pytest.fixture
    def encryption_service(self):
        """Create an EncryptionService with random key."""
        from core.security.encryption import EncryptionService
        
        return EncryptionService(master_key=os.urandom(32))

    def test_blind_index_is_deterministic(self, encryption_service):
        """Test: Same value produces same blind index."""
        value = "user@example.com"
        
        index1 = encryption_service.generate_blind_index(value)
        index2 = encryption_service.generate_blind_index(value)
        
        assert index1 == index2

    def test_blind_index_different_for_different_values(self, encryption_service):
        """Test: Different values produce different blind indexes."""
        index1 = encryption_service.generate_blind_index("user1@example.com")
        index2 = encryption_service.generate_blind_index("user2@example.com")
        
        assert index1 != index2

    def test_blind_index_is_hex_string(self, encryption_service):
        """Test: Blind index is a valid hex string (SHA-256 = 64 chars)."""
        index = encryption_service.generate_blind_index("test@example.com")
        
        assert isinstance(index, str)
        assert len(index) == 64  # SHA-256 hex = 64 characters
        # Should be valid hex
        int(index, 16)  # No exception means valid hex

    def test_blind_index_empty_value_returns_empty_string(self, encryption_service):
        """Test: Empty value returns empty string for blind index."""
        index = encryption_service.generate_blind_index("")
        assert index == ""

    def test_blind_index_uses_separate_key(self):
        """Test: Blind index uses dedicated key (not encryption key)."""
        from core.security.encryption import EncryptionService
        
        master_key = os.urandom(32)
        service = EncryptionService(master_key=master_key, legacy_mode=False)
        
        # In non-legacy mode, index key is different from encryption key
        assert service._index_key != service._encryption_key

    def test_global_generate_blind_index_function(self, mock_env_vars):
        """Test: Global generate_blind_index() function works correctly."""
        from core.security.encryption import generate_blind_index
        import core.security.encryption as enc_module
        
        # Reset singleton
        enc_module._encryption_service = None
        
        value = "test-email@example.com"
        
        index1 = generate_blind_index(value)
        index2 = generate_blind_index(value)
        
        # Should be deterministic
        assert index1 == index2
        assert len(index1) == 64


# =============================================================================
# User Enumeration Prevention Tests
# =============================================================================

class TestUserEnumerationPrevention:
    """
    Tests for user enumeration attack prevention.
    
    Verifies:
    - initiate_magic_link returns SAME message regardless of email existence
    - No EmailNotFoundError is raised to the caller
    - Non-existent emails are logged but don't affect response
    """

    @pytest.fixture
    def mock_ragic_service(self):
        """Create mock RagicService."""
        service = MagicMock()
        service.verify_email_exists = AsyncMock()
        return service

    @pytest.fixture
    def mock_config_loader(self):
        """Create mock ConfigLoader."""
        config = MagicMock()
        config.get = MagicMock(side_effect=lambda key, default=None: {
            "security": {},
            "email": {
                "host": "smtp.test.com",
                "port": 587,
                "username": "test",
                "password": "test",
                "from_email": "noreply@test.com",
                "from_name": "Test System",
            },
            "server.app_name": "Test App",
            "server.base_url": "https://test.example.com",
        }.get(key, default))
        return config

    @pytest.fixture
    def auth_service(self, mock_ragic_service, mock_config_loader):
        """Create AuthService with mocked dependencies."""
        from core.services.auth import AuthService
        
        return AuthService(
            ragic_service=mock_ragic_service,
            config_loader=mock_config_loader,
        )

    @pytest.mark.asyncio
    async def test_existing_email_returns_success_message(
        self, auth_service, mock_ragic_service
    ):
        """Test: Existing email returns the standard success message."""
        from core.schemas.auth import RagicEmployeeData
        from core.services.auth import AuthService
        
        # Mock: Email exists
        mock_ragic_service.verify_email_exists.return_value = RagicEmployeeData(
            employee_id="E001",
            email="valid@company.com",
            name="Valid User",
            is_active=True,
        )
        
        with patch.object(auth_service, '_send_verification_email', new_callable=AsyncMock):
            result = await auth_service.initiate_magic_link(
                email="valid@company.com",
                line_sub="U1234567890"
            )
        
        assert result == AuthService.MAGIC_LINK_SUCCESS_MESSAGE

    @pytest.mark.asyncio
    async def test_nonexistent_email_returns_same_message(
        self, auth_service, mock_ragic_service
    ):
        """Test: Non-existent email returns the SAME success message (no enumeration)."""
        from core.services.auth import AuthService
        
        # Mock: Email does NOT exist
        mock_ragic_service.verify_email_exists.return_value = None
        
        result = await auth_service.initiate_magic_link(
            email="nonexistent@hacker.com",
            line_sub="U1234567890"
        )
        
        # Response should be IDENTICAL to the success case
        assert result == AuthService.MAGIC_LINK_SUCCESS_MESSAGE

    @pytest.mark.asyncio
    async def test_response_is_identical_regardless_of_email(
        self, auth_service, mock_ragic_service
    ):
        """Test: Response for valid and invalid emails are byte-for-byte identical."""
        from core.schemas.auth import RagicEmployeeData
        
        # Test 1: Valid email
        mock_ragic_service.verify_email_exists.return_value = RagicEmployeeData(
            employee_id="E001",
            email="valid@company.com",
            name="Valid User",
            is_active=True,
        )
        
        with patch.object(auth_service, '_send_verification_email', new_callable=AsyncMock):
            result_valid = await auth_service.initiate_magic_link(
                email="valid@company.com",
                line_sub="U1234567890"
            )
        
        # Test 2: Invalid email
        mock_ragic_service.verify_email_exists.return_value = None
        
        result_invalid = await auth_service.initiate_magic_link(
            email="invalid@hacker.com",
            line_sub="U1234567890"
        )
        
        # Both responses must be EXACTLY the same
        assert result_valid == result_invalid

    @pytest.mark.asyncio
    async def test_nonexistent_email_does_not_raise_exception(
        self, auth_service, mock_ragic_service
    ):
        """Test: No EmailNotFoundError is raised for non-existent email."""
        from core.services.auth import EmailNotFoundError
        
        # Mock: Email does NOT exist
        mock_ragic_service.verify_email_exists.return_value = None
        
        # Should NOT raise EmailNotFoundError
        try:
            await auth_service.initiate_magic_link(
                email="nonexistent@hacker.com",
                line_sub="U1234567890"
            )
        except EmailNotFoundError:
            pytest.fail("EmailNotFoundError should NOT be raised for non-existent email")

    @pytest.mark.asyncio
    async def test_inactive_employee_returns_same_message(
        self, auth_service, mock_ragic_service
    ):
        """Test: Inactive employee returns the same message (no enumeration)."""
        from core.schemas.auth import RagicEmployeeData
        from core.services.auth import AuthService
        
        # Mock: Email exists but is_active=False
        mock_ragic_service.verify_email_exists.return_value = RagicEmployeeData(
            employee_id="E001",
            email="inactive@company.com",
            name="Inactive User",
            is_active=False,  # Inactive!
        )
        
        result = await auth_service.initiate_magic_link(
            email="inactive@company.com",
            line_sub="U1234567890"
        )
        
        # Should return same message, not reveal that the user exists but is inactive
        assert result == AuthService.MAGIC_LINK_SUCCESS_MESSAGE

    @pytest.mark.asyncio
    async def test_nonexistent_email_does_not_send_email(
        self, auth_service, mock_ragic_service
    ):
        """Test: No email is sent for non-existent email addresses."""
        # Mock: Email does NOT exist
        mock_ragic_service.verify_email_exists.return_value = None
        
        with patch.object(
            auth_service, '_send_verification_email', new_callable=AsyncMock
        ) as mock_send:
            await auth_service.initiate_magic_link(
                email="nonexistent@hacker.com",
                line_sub="U1234567890"
            )
            
            # Email should NOT be sent
            mock_send.assert_not_called()

    @pytest.mark.asyncio
    async def test_nonexistent_email_is_logged(
        self, auth_service, mock_ragic_service, caplog
    ):
        """Test: Non-existent email is logged with USER_ENUM_PROTECTION tag."""
        import logging
        
        # Mock: Email does NOT exist
        mock_ragic_service.verify_email_exists.return_value = None
        
        with caplog.at_level(logging.WARNING):
            await auth_service.initiate_magic_link(
                email="nonexistent@hacker.com",
                line_sub="U1234567890"
            )
        
        # Should log the attempt with security tag
        assert any("USER_ENUM_PROTECTION" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_email_send_failure_returns_same_message(
        self, auth_service, mock_ragic_service
    ):
        """Test: Email send failure still returns success message (no enumeration)."""
        from core.schemas.auth import RagicEmployeeData
        from core.services.auth import AuthService
        from core.services.email import EmailSendError
        
        # Mock: Email exists
        mock_ragic_service.verify_email_exists.return_value = RagicEmployeeData(
            employee_id="E001",
            email="valid@company.com",
            name="Valid User",
            is_active=True,
        )
        
        # Mock: Email sending fails
        with patch.object(
            auth_service, '_send_verification_email', new_callable=AsyncMock
        ) as mock_send:
            mock_send.side_effect = EmailSendError("SMTP connection failed")
            
            result = await auth_service.initiate_magic_link(
                email="valid@company.com",
                line_sub="U1234567890"
            )
        
        # Should still return same message
        assert result == AuthService.MAGIC_LINK_SUCCESS_MESSAGE


class TestEmailMasking:
    """Tests for email masking in logs."""

    def test_mask_email_normal(self):
        """Test: Normal email is properly masked."""
        from core.services.auth import AuthService
        
        masked = AuthService._mask_email("john.doe@company.com")
        
        assert masked == "jo***@company.com"
        assert "john" not in masked

    def test_mask_email_short_local_part(self):
        """Test: Short local part email is masked."""
        from core.services.auth import AuthService
        
        masked = AuthService._mask_email("ab@test.com")
        
        assert "a***@test.com" == masked

    def test_mask_email_single_char_local_part(self):
        """Test: Single character local part is masked."""
        from core.services.auth import AuthService
        
        masked = AuthService._mask_email("a@test.com")
        
        assert masked == "a***@test.com"

    def test_mask_email_invalid_format(self):
        """Test: Invalid email format returns masked placeholder."""
        from core.services.auth import AuthService
        
        masked = AuthService._mask_email("not-an-email")
        
        assert masked == "***"


# =============================================================================
# DEBUG_SKIP_AUTH Removal Verification
# =============================================================================

class TestDebugBypassRemoved:
    """
    Tests to verify DEBUG_SKIP_AUTH backdoor has been removed.
    
    Even with DEBUG_SKIP_AUTH=true, authentication should still be required.
    """

    @pytest.mark.asyncio
    async def test_debug_skip_auth_env_has_no_effect(self, mock_env_vars, monkeypatch):
        """Test: Setting DEBUG_SKIP_AUTH=true does NOT bypass authentication."""
        from fastapi import HTTPException
        from core.line_auth import get_verified_user
        from core.services.auth import AuthService
        
        # Set the backdoor environment variable
        monkeypatch.setenv("DEBUG_SKIP_AUTH", "true")
        
        # Mock dependencies
        mock_auth_service = MagicMock(spec=AuthService)
        mock_db = AsyncMock()
        
        # Should raise 401 because no token is provided
        # (if backdoor existed, it would return a VerifiedUser)
        with pytest.raises(HTTPException) as exc_info:
            await get_verified_user(
                x_line_id_token=None,
                q_line_id_token=None,
                authorization=None,
                auth_service=mock_auth_service,
                db=mock_db,
            )
        
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_no_token_requires_authentication(self, mock_env_vars):
        """Test: No token provided results in 401 error."""
        from fastapi import HTTPException
        from core.line_auth import get_verified_user
        from core.services.auth import AuthService
        
        mock_auth_service = MagicMock(spec=AuthService)
        mock_db = AsyncMock()
        
        with pytest.raises(HTTPException) as exc_info:
            await get_verified_user(
                x_line_id_token=None,
                q_line_id_token=None,
                authorization=None,
                auth_service=mock_auth_service,
                db=mock_db,
            )
        
        assert exc_info.value.status_code == 401
        assert "LINE authentication required" in str(exc_info.value.detail)


# =============================================================================
# Dependency Injection Tests
# =============================================================================

class TestAuthServiceDependencyInjection:
    """Tests for AuthService dependency injection capability."""

    def test_constructor_accepts_ragic_service(self, mock_env_vars):
        """Test: AuthService accepts injected RagicService."""
        from core.services.auth import AuthService
        
        mock_ragic = MagicMock()
        service = AuthService(ragic_service=mock_ragic)
        
        assert service._ragic_service is mock_ragic

    def test_constructor_accepts_config_loader(self, mock_env_vars):
        """Test: AuthService accepts injected ConfigLoader."""
        from core.services.auth import AuthService
        
        mock_config = MagicMock()
        mock_config.get = MagicMock(return_value={})
        
        service = AuthService(config_loader=mock_config)
        
        assert service._config_loader is mock_config

    def test_constructor_accepts_both_dependencies(self, mock_env_vars):
        """Test: AuthService accepts both injected dependencies."""
        from core.services.auth import AuthService
        
        mock_ragic = MagicMock()
        mock_config = MagicMock()
        mock_config.get = MagicMock(return_value={})
        
        service = AuthService(
            ragic_service=mock_ragic,
            config_loader=mock_config,
        )
        
        assert service._ragic_service is mock_ragic
        assert service._config_loader is mock_config

    def test_default_dependencies_created_if_not_provided(self, mock_env_vars):
        """Test: Default dependencies are created if not injected."""
        from core.services.auth import AuthService
        from core.services.ragic import RagicService
        from core.app_context import ConfigLoader
        
        service = AuthService()
        
        assert service._ragic_service is not None
        assert service._config_loader is not None
