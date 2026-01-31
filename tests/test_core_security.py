"""
Unit Tests for core.security layer.

Tests encryption service, HKDF key derivation, and EncryptedType field encryption.
"""

import pytest
import os
from unittest.mock import patch, MagicMock


class TestKeyDerivationService:
    """Tests for KeyDerivationService class (HKDF-SHA256)."""

    def test_initialization_with_valid_master_key(self):
        """Test KeyDerivationService initializes with valid master key."""
        from core.security.encryption import KeyDerivationService

        key = os.urandom(32)
        kds = KeyDerivationService(key)

        assert kds._master_key == key

    def test_initialization_raises_on_invalid_key_length(self):
        """Test KeyDerivationService raises ValueError for invalid key length."""
        from core.security.encryption import KeyDerivationService

        with pytest.raises(ValueError, match="must be exactly 32 bytes"):
            KeyDerivationService(b"short_key")

    def test_derive_encryption_key(self):
        """Test deriving encryption key."""
        from core.security.encryption import KeyDerivationService, KeyPurpose

        key = os.urandom(32)
        kds = KeyDerivationService(key)

        encryption_key = kds.get_encryption_key()

        assert len(encryption_key) == 32
        assert encryption_key != key  # Derived key should differ from master

    def test_derive_index_key(self):
        """Test deriving blind index key."""
        from core.security.encryption import KeyDerivationService

        key = os.urandom(32)
        kds = KeyDerivationService(key)

        index_key = kds.get_index_key()

        assert len(index_key) == 32
        assert index_key != key  # Derived key should differ from master

    def test_encryption_and_index_keys_are_different(self):
        """Test that encryption and index keys are cryptographically separate."""
        from core.security.encryption import KeyDerivationService

        key = os.urandom(32)
        kds = KeyDerivationService(key)

        encryption_key = kds.get_encryption_key()
        index_key = kds.get_index_key()

        assert encryption_key != index_key

    def test_derived_keys_are_deterministic(self):
        """Test that same master key produces same derived keys."""
        from core.security.encryption import KeyDerivationService

        key = os.urandom(32)
        kds1 = KeyDerivationService(key)
        kds2 = KeyDerivationService(key)

        assert kds1.get_encryption_key() == kds2.get_encryption_key()
        assert kds1.get_index_key() == kds2.get_index_key()

    def test_different_master_keys_produce_different_derived_keys(self):
        """Test that different master keys produce different derived keys."""
        from core.security.encryption import KeyDerivationService

        kds1 = KeyDerivationService(os.urandom(32))
        kds2 = KeyDerivationService(os.urandom(32))

        assert kds1.get_encryption_key() != kds2.get_encryption_key()
        assert kds1.get_index_key() != kds2.get_index_key()

    def test_derive_key_caching(self):
        """Test that derived keys are cached."""
        from core.security.encryption import KeyDerivationService, KeyPurpose

        key = os.urandom(32)
        kds = KeyDerivationService(key)

        # First call
        key1 = kds.derive_key(KeyPurpose.ENCRYPTION)
        # Second call should return cached value
        key2 = kds.derive_key(KeyPurpose.ENCRYPTION)

        assert key1 is key2  # Same object reference (cached)


class TestEncryptionService:
    """Tests for EncryptionService class."""
    
    def test_initialization_with_custom_key(self):
        """Test EncryptionService initializes with custom master key."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key)
        
        # In non-legacy mode, _encryption_key is derived from master_key
        assert service._encryption_key != key
    
    def test_initialization_legacy_mode(self):
        """Test EncryptionService in legacy mode uses master key directly."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key, legacy_mode=True)
        
        assert service._encryption_key == key
        assert service._index_key == key
        assert service.is_legacy_mode is True
    
    def test_initialization_raises_on_invalid_key_length(self):
        """Test EncryptionService raises ValueError for invalid key length."""
        from core.security.encryption import EncryptionService
        
        with pytest.raises(ValueError, match="must be exactly 32 bytes"):
            EncryptionService(master_key=b"short_key")
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test encrypt/decrypt roundtrip preserves data."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key)
        
        plaintext = "sensitive data 123"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_encrypt_decrypt_roundtrip_legacy_mode(self):
        """Test encrypt/decrypt roundtrip in legacy mode."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key, legacy_mode=True)
        
        plaintext = "sensitive data 123"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_encrypt_returns_bytes(self):
        """Test encrypt() returns bytes."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key)
        
        encrypted = service.encrypt("test")
        
        assert isinstance(encrypted, bytes)
        assert len(encrypted) > 0
    
    def test_encrypt_empty_string(self):
        """Test encrypt() handles empty string."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key)
        
        encrypted = service.encrypt("")
        
        assert encrypted == b""
    
    def test_decrypt_empty_bytes(self):
        """Test decrypt() handles empty bytes."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key)
        
        decrypted = service.decrypt(b"")
        
        assert decrypted == ""
    
    def test_encrypt_produces_different_ciphertext(self):
        """Test encrypt() produces different ciphertext each time (random nonce)."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key)
        
        plaintext = "test data"
        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)
        
        # Should be different due to random nonce
        assert encrypted1 != encrypted2
    
    def test_generate_blind_index_deterministic(self):
        """Test generate_blind_index() produces deterministic hashes."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key)
        
        value = "test@example.com"
        hash1 = service.generate_blind_index(value)
        hash2 = service.generate_blind_index(value)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex = 64 chars
    
    def test_generate_blind_index_different_for_different_values(self):
        """Test generate_blind_index() produces different hashes for different values."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key)
        
        hash1 = service.generate_blind_index("test1@example.com")
        hash2 = service.generate_blind_index("test2@example.com")
        
        assert hash1 != hash2
    
    def test_generate_blind_index_empty_string(self):
        """Test generate_blind_index() handles empty string."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(master_key=key)
        
        hash_result = service.generate_blind_index("")
        
        assert hash_result == ""
    
    def test_legacy_mode_not_compatible_with_hkdf_mode(self):
        """Test that data encrypted in legacy mode cannot be decrypted in HKDF mode."""
        from core.security.encryption import EncryptionService
        from cryptography.exceptions import InvalidTag
        
        key = os.urandom(32)
        legacy_service = EncryptionService(master_key=key, legacy_mode=True)
        hkdf_service = EncryptionService(master_key=key, legacy_mode=False)
        
        plaintext = "test data"
        encrypted_legacy = legacy_service.encrypt(plaintext)
        
        # HKDF mode should fail to decrypt legacy data (different key)
        with pytest.raises(InvalidTag):
            hkdf_service.decrypt(encrypted_legacy)
    
    def test_blind_index_differs_between_modes(self):
        """Test that blind indexes differ between legacy and HKDF modes."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        legacy_service = EncryptionService(master_key=key, legacy_mode=True)
        hkdf_service = EncryptionService(master_key=key, legacy_mode=False)
        
        value = "test@example.com"
        legacy_index = legacy_service.generate_blind_index(value)
        hkdf_index = hkdf_service.generate_blind_index(value)
        
        # Indexes should differ due to different keys
        assert legacy_index != hkdf_index
    
    def test_get_encryption_service_singleton(self, mock_env_vars):
        """Test get_encryption_service() returns singleton."""
        from core.security.encryption import get_encryption_service
        import core.security.encryption as enc_module
        
        enc_module._encryption_service = None
        
        service1 = get_encryption_service()
        service2 = get_encryption_service()
        
        assert service1 is service2


class TestEncryptedType:
    """Tests for EncryptedType SQLAlchemy TypeDecorator."""
    
    def test_encrypted_type_initialization(self):
        """Test EncryptedType initializes with length."""
        from core.security.encryption import EncryptedType
        
        encrypted = EncryptedType(512)
        
        assert encrypted.length == 512
    
    def test_process_bind_param_encrypts_value(self, mock_env_vars):
        """Test process_bind_param() encrypts the value."""
        from core.security.encryption import EncryptedType
        
        encrypted_type = EncryptedType(512)
        plaintext = "sensitive data"
        dialect = MagicMock()
        
        result = encrypted_type.process_bind_param(plaintext, dialect)
        
        assert result is not None
        assert isinstance(result, str)
        assert result != plaintext
    
    def test_process_bind_param_handles_none(self, mock_env_vars):
        """Test process_bind_param() handles None."""
        from core.security.encryption import EncryptedType
        
        encrypted_type = EncryptedType(512)
        dialect = MagicMock()
        
        result = encrypted_type.process_bind_param(None, dialect)
        
        assert result is None
    
    def test_process_result_value_decrypts_value(self, mock_env_vars):
        """Test process_result_value() decrypts the value."""
        from core.security.encryption import EncryptedType
        
        encrypted_type = EncryptedType(512)
        plaintext = "sensitive data"
        dialect = MagicMock()
        
        encrypted = encrypted_type.process_bind_param(plaintext, dialect)
        decrypted = encrypted_type.process_result_value(encrypted, dialect)
        
        assert decrypted == plaintext
    
    def test_process_result_value_handles_none(self, mock_env_vars):
        """Test process_result_value() handles None."""
        from core.security.encryption import EncryptedType
        
        encrypted_type = EncryptedType(512)
        dialect = MagicMock()
        
        result = encrypted_type.process_result_value(None, dialect)
        
        assert result is None
    
    def test_generate_blind_index_helper_function(self, mock_env_vars):
        """Test generate_blind_index() helper function."""
        from core.security.encryption import generate_blind_index
        
        value = "test@example.com"
        hash1 = generate_blind_index(value)
        hash2 = generate_blind_index(value)
        
        assert hash1 == hash2
        assert len(hash1) == 64
