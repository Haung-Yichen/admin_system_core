"""
Unit Tests for core.security layer.

Tests encryption service and EncryptedType field encryption.
"""

import pytest
import os
from unittest.mock import patch, MagicMock


class TestEncryptionService:
    """Tests for EncryptionService class."""
    
    def test_initialization_with_custom_key(self):
        """Test EncryptionService initializes with custom key."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(key=key)
        
        assert service._key == key
    
    def test_initialization_raises_on_invalid_key_length(self):
        """Test EncryptionService raises ValueError for invalid key length."""
        from core.security.encryption import EncryptionService
        
        with pytest.raises(ValueError, match="must be exactly 32 bytes"):
            EncryptionService(key=b"short_key")
    
    def test_encrypt_decrypt_roundtrip(self):
        """Test encrypt/decrypt roundtrip preserves data."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(key=key)
        
        plaintext = "sensitive data 123"
        encrypted = service.encrypt(plaintext)
        decrypted = service.decrypt(encrypted)
        
        assert decrypted == plaintext
    
    def test_encrypt_returns_bytes(self):
        """Test encrypt() returns bytes."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(key=key)
        
        encrypted = service.encrypt("test")
        
        assert isinstance(encrypted, bytes)
        assert len(encrypted) > 0
    
    def test_encrypt_empty_string(self):
        """Test encrypt() handles empty string."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(key=key)
        
        encrypted = service.encrypt("")
        
        assert encrypted == b""
    
    def test_decrypt_empty_bytes(self):
        """Test decrypt() handles empty bytes."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(key=key)
        
        decrypted = service.decrypt(b"")
        
        assert decrypted == ""
    
    def test_encrypt_produces_different_ciphertext(self):
        """Test encrypt() produces different ciphertext each time (random nonce)."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(key=key)
        
        plaintext = "test data"
        encrypted1 = service.encrypt(plaintext)
        encrypted2 = service.encrypt(plaintext)
        
        # Should be different due to random nonce
        assert encrypted1 != encrypted2
    
    def test_generate_blind_index_deterministic(self):
        """Test generate_blind_index() produces deterministic hashes."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(key=key)
        
        value = "test@example.com"
        hash1 = service.generate_blind_index(value)
        hash2 = service.generate_blind_index(value)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex = 64 chars
    
    def test_generate_blind_index_different_for_different_values(self):
        """Test generate_blind_index() produces different hashes for different values."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(key=key)
        
        hash1 = service.generate_blind_index("test1@example.com")
        hash2 = service.generate_blind_index("test2@example.com")
        
        assert hash1 != hash2
    
    def test_generate_blind_index_empty_string(self):
        """Test generate_blind_index() handles empty string."""
        from core.security.encryption import EncryptionService
        
        key = os.urandom(32)
        service = EncryptionService(key=key)
        
        hash_result = service.generate_blind_index("")
        
        assert hash_result == ""
    
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
