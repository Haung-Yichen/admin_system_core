"""
Database Field Encryption Module (Framework Layer).

Provides transparent AES-GCM encryption for sensitive database fields
using SQLAlchemy TypeDecorators and deterministic HMAC-SHA256 blind indexes
for searchable encrypted fields.

Security Features:
- AES-256-GCM encryption with random nonces (non-deterministic)
- HMAC-SHA256 blind indexes for exact-match lookups
- HKDF-SHA256 key derivation for cryptographic key separation
- Master key (SECURITY_KEY) derives independent sub-keys for encryption and indexing

Backward Compatibility Notice:
-----------------------------
This version uses HKDF to derive separate keys from the master key. Data encrypted
with the previous version (which used the master key directly) is NOT compatible
with this version. Before upgrading, you must:

1. Export all encrypted data using the OLD version (decrypt to plaintext)
2. Upgrade to this new version
3. Re-encrypt all data using the NEW version

See scripts/migrate_encryption.py for the migration tool.
Alternatively, set ENCRYPTION_LEGACY_MODE=true to use the old key derivation
(not recommended for new deployments).
"""

import hashlib
import hmac
import os
from enum import Enum
from typing import Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import String, TypeDecorator
from sqlalchemy.engine import Dialect

from core.app_context import ConfigLoader


class KeyPurpose(Enum):
    """Enumeration of key derivation purposes for cryptographic separation."""
    
    ENCRYPTION = b"encryption-aes-gcm-v1"
    BLIND_INDEX = b"blind-index-hmac-v1"


class KeyDerivationService:
    """
    Secure key derivation service using HKDF-SHA256.
    
    Implements cryptographic key separation by deriving purpose-specific
    sub-keys from a master key. This follows the principle of key separation
    where different cryptographic operations use different keys.
    
    Security Properties:
    - Uses HKDF (RFC 5869) for secure key derivation
    - Each derived key is cryptographically independent
    - Purpose-specific info strings prevent key misuse
    """
    
    # Salt for HKDF - should be consistent across deployments
    # This can be changed per-deployment for additional security isolation
    DEFAULT_SALT = b"admin-system-core-encryption-salt-v1"
    
    def __init__(self, master_key: bytes, salt: bytes | None = None) -> None:
        """
        Initialize key derivation service.
        
        Args:
            master_key: The master key (32 bytes) from SECURITY_KEY.
            salt: Optional salt for HKDF. Uses default if not provided.
        """
        if len(master_key) != 32:
            raise ValueError("Master key must be exactly 32 bytes (256 bits)")
        
        self._master_key = master_key
        self._salt = salt or self.DEFAULT_SALT
        self._derived_keys: dict[KeyPurpose, bytes] = {}
    
    def derive_key(self, purpose: KeyPurpose, key_length: int = 32) -> bytes:
        """
        Derive a purpose-specific key using HKDF-SHA256.
        
        Args:
            purpose: The intended use of the derived key.
            key_length: Length of derived key in bytes (default: 32 for 256-bit).
            
        Returns:
            Derived key bytes of specified length.
        """
        # Return cached key if already derived
        if purpose in self._derived_keys:
            return self._derived_keys[purpose]
        
        # Use HKDF to derive a key with purpose-specific info
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=key_length,
            salt=self._salt,
            info=purpose.value,
            backend=default_backend(),
        )
        
        derived_key = hkdf.derive(self._master_key)
        self._derived_keys[purpose] = derived_key
        
        return derived_key
    
    def get_encryption_key(self) -> bytes:
        """Get the derived key for AES-GCM encryption."""
        return self.derive_key(KeyPurpose.ENCRYPTION)
    
    def get_index_key(self) -> bytes:
        """Get the derived key for blind index HMAC."""
        return self.derive_key(KeyPurpose.BLIND_INDEX)


def _load_master_key() -> bytes:
    """
    Load the master key from configuration or environment.
    
    Returns:
        32-byte master key.
        
    Raises:
        ValueError: If key is not found or invalid.
    """
    config_loader = ConfigLoader()
    config_loader.load()
    security_key = config_loader.get("security.key", os.getenv("SECURITY_KEY", ""))
    
    if not security_key:
        raise ValueError(
            "SECURITY_KEY not found in config or environment. "
            "Generate with: openssl rand -hex 32"
        )
    
    key = bytes.fromhex(security_key)
    
    if len(key) != 32:
        raise ValueError("SECURITY_KEY must be exactly 32 bytes (256 bits) in hex format")
    
    return key


def _is_legacy_mode() -> bool:
    """Check if legacy encryption mode is enabled."""
    return os.getenv("ENCRYPTION_LEGACY_MODE", "").lower() in ("true", "1", "yes")


class EncryptionService:
    """
    Core encryption service using AES-256-GCM with HKDF key derivation.
    
    Provides encryption/decryption for sensitive data fields using
    cryptographically separated keys derived from the master SECURITY_KEY.
    
    Key Derivation Strategy:
    - Master key (SECURITY_KEY) is never used directly for cryptographic operations
    - HKDF-SHA256 derives separate keys for encryption and blind indexing
    - This ensures cryptographic independence between operations
    
    Security Properties:
    - AES-256-GCM provides authenticated encryption
    - Random 12-byte nonces ensure semantic security
    - HMAC-SHA256 blind indexes enable secure searchability
    """
    
    def __init__(
        self,
        master_key: bytes | None = None,
        key_derivation_service: KeyDerivationService | None = None,
        legacy_mode: bool | None = None,
    ) -> None:
        """
        Initialize encryption service with derived keys.
        
        Args:
            master_key: Optional 32-byte master key. If None, loads from config.
            key_derivation_service: Optional pre-configured KDS for testing.
            legacy_mode: If True, uses master key directly (for backward compatibility).
                        If None, checks ENCRYPTION_LEGACY_MODE environment variable.
        """
        if master_key is None:
            master_key = _load_master_key()
        
        if len(master_key) != 32:
            raise ValueError("Master key must be exactly 32 bytes (256 bits)")
        
        # Determine if legacy mode is enabled
        self._legacy_mode = legacy_mode if legacy_mode is not None else _is_legacy_mode()
        
        if self._legacy_mode:
            # Legacy mode: use master key directly (for backward compatibility)
            self._encryption_key = master_key
            self._index_key = master_key
        else:
            # Modern mode: derive separate keys using HKDF
            if key_derivation_service is None:
                key_derivation_service = KeyDerivationService(master_key)
            
            self._key_derivation_service = key_derivation_service
            self._encryption_key = key_derivation_service.get_encryption_key()
            self._index_key = key_derivation_service.get_index_key()
        
        self._cipher = AESGCM(self._encryption_key)
    
    def encrypt(self, plaintext: str) -> bytes:
        """
        Encrypt plaintext using AES-GCM with random nonce.
        
        Uses the derived encryption key (not the master key).
        
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
        
        Uses the derived encryption key (not the master key).
        
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
        
        Uses the derived index key (separate from encryption key).
        This creates a "blind index" that allows exact-match lookups
        on encrypted fields without revealing the plaintext.
        
        Args:
            value: String to hash.
            
        Returns:
            Hex-encoded HMAC-SHA256 hash (64 characters).
        """
        if not value:
            return ""
        
        # Use HMAC-SHA256 with the dedicated index key
        h = hmac.new(self._index_key, value.encode("utf-8"), hashlib.sha256)
        return h.hexdigest()
    
    @property
    def is_legacy_mode(self) -> bool:
        """Check if service is running in legacy compatibility mode."""
        return self._legacy_mode


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
