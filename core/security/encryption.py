"""
Database Field Encryption Module (Framework Layer).

Provides transparent AES-GCM encryption for sensitive database fields
using SQLAlchemy TypeDecorators and deterministic HMAC-SHA256 blind indexes
for searchable encrypted fields.

Security Features:
- AES-256-GCM encryption with random nonces (non-deterministic)
- HMAC-SHA256 blind indexes for exact-match lookups
- Key derivation from environment variable SECURITY_KEY
"""

import hashlib
import hmac
import os
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import String, TypeDecorator
from sqlalchemy.engine import Dialect

from core.app_context import ConfigLoader


class EncryptionService:
    """
    Core encryption service using AES-256-GCM.
    
    Provides encryption/decryption for sensitive data fields.
    Uses a 256-bit key derived from SECURITY_KEY environment variable.
    """
    
    def __init__(self, key: bytes | None = None) -> None:
        """
        Initialize encryption service.
        
        Args:
            key: Optional 32-byte encryption key. If None, loads from config.
        """
        if key is None:
            config_loader = ConfigLoader()
            config_loader.load()
            security_key = config_loader.get("security.key", os.getenv("SECURITY_KEY", ""))
            
            if not security_key:
                raise ValueError(
                    "SECURITY_KEY not found in config or environment. "
                    "Generate with: openssl rand -hex 32"
                )
            
            # Convert hex string to bytes
            key = bytes.fromhex(security_key)
        
        if len(key) != 32:
            raise ValueError("Encryption key must be exactly 32 bytes (256 bits)")
        
        self._cipher = AESGCM(key)
        self._key = key
    
    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt plaintext using AES-GCM with random nonce.
        
        Args:
            plaintext: String to encrypt.
            
        Returns:
            Encrypted data as bytes (nonce + ciphertext + tag).
        """
        if not plaintext:
            return b""
        
        # Generate random 12-byte nonce
        nonce = os.urandom(12)
        
        # Encrypt and authenticate
        ciphertext = self._cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
        
        # Return nonce + ciphertext (ciphertext already includes auth tag)
        return nonce + ciphertext
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """
        Decrypt AES-GCM encrypted data.
        
        Args:
            encrypted_data: Bytes containing nonce + ciphertext + tag.
            
        Returns:
            Decrypted plaintext string.
        """
        if not encrypted_data:
            return ""
        
        # Extract nonce (first 12 bytes) and ciphertext
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        # Decrypt and verify
        plaintext_bytes = self._cipher.decrypt(nonce, ciphertext, None)
        
        return plaintext_bytes.decode("utf-8")
    
    def generate_blind_index(self, value: str) -> str:
        """
        Generate deterministic HMAC-SHA256 hash for searchable index.
        
        This creates a "blind index" that allows exact-match lookups
        on encrypted fields without revealing the plaintext.
        
        Args:
            value: String to hash.
            
        Returns:
            Hex-encoded HMAC-SHA256 hash (64 characters).
        """
        if not value:
            return ""
        
        # Use HMAC-SHA256 with the encryption key as the secret
        h = hmac.new(self._key, value.encode("utf-8"), hashlib.sha256)
        return h.hexdigest()


# Global singleton
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get or create the global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


class EncryptedType(TypeDecorator):
    """
    SQLAlchemy TypeDecorator for transparent field encryption.
    
    Automatically encrypts data before storing and decrypts when reading.
    Stores encrypted data as BYTEA in PostgreSQL.
    
    Usage:
        class User(Base):
            email: Mapped[str] = mapped_column(EncryptedType(String(255)))
    """
    
    impl = String
    cache_ok = True
    
    def __init__(self, length: int = 512, *args: Any, **kwargs: Any) -> None:
        """
        Initialize encrypted type.
        
        Args:
            length: Maximum length for the underlying string column.
                   Should be larger than plaintext to account for encryption overhead.
        """
        super().__init__(*args, **kwargs)
        self.length = length
    
    def load_dialect_impl(self, dialect: Dialect) -> Any:
        """Load the appropriate dialect implementation."""
        return dialect.type_descriptor(String(self.length))
    
    def process_bind_param(self, value: str | None, dialect: Dialect) -> str | None:
        """Encrypt value before storing in database."""
        if value is None:
            return None
        
        service = get_encryption_service()
        encrypted_bytes = service.encrypt(value)
        
        # Store as hex string for compatibility
        return encrypted_bytes.hex()
    
    def process_result_value(self, value: str | None, dialect: Dialect) -> str | None:
        """Decrypt value when reading from database."""
        if value is None:
            return None
        
        service = get_encryption_service()
        encrypted_bytes = bytes.fromhex(value)
        
        return service.decrypt(encrypted_bytes)


def generate_blind_index(value: str) -> str:
    """
    Helper function to generate blind index for a value.
    
    Used when you need to populate the hash column for lookups.
    
    Args:
        value: String to hash.
        
    Returns:
        HMAC-SHA256 hash hex string.
    """
    service = get_encryption_service()
    return service.generate_blind_index(value)
