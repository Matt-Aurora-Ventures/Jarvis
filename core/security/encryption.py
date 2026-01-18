"""
Encryption at Rest Module

Provides AES-256 encryption for sensitive data.
Keys are derived from environment variables only - never hardcoded.

Features:
- AES-256-GCM encryption (authenticated encryption)
- Key derivation from environment variables
- Secure key handling
- No plaintext key storage
"""

import os
import base64
import hashlib
import logging
import secrets
from typing import Optional

logger = logging.getLogger(__name__)

# Check for cryptography library
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography library not installed. Run: pip install cryptography")


class EncryptionError(Exception):
    """Base exception for encryption errors."""
    pass


class KeyDerivationError(EncryptionError):
    """Error deriving encryption key."""
    pass


class DecryptionError(EncryptionError):
    """Error decrypting data."""
    pass


class SecureEncryption:
    """
    AES-256-GCM encryption for sensitive data.

    Security features:
    - Keys derived from environment variables only
    - AES-256-GCM provides authenticated encryption
    - Unique nonce for each encryption
    - No plaintext keys in memory longer than necessary
    """

    # Constants
    KEY_LENGTH = 32  # 256 bits
    NONCE_LENGTH = 12  # 96 bits for GCM
    SALT_LENGTH = 16

    # Algorithm identifier
    algorithm = "AES-256-GCM"
    key_length = 32

    def __init__(
        self,
        key_from_env: str = "JARVIS_ENCRYPTION_KEY",
        salt_from_env: str = "JARVIS_ENCRYPTION_SALT",
        key: str = None  # This should NOT be used - will raise error
    ):
        """
        Initialize encryption with key from environment variable.

        Args:
            key_from_env: Environment variable name containing the key/password
            salt_from_env: Environment variable name containing the salt
            key: NOT SUPPORTED - will raise error (keys must come from env)

        Raises:
            ValueError: If key is passed directly (security violation)
            KeyDerivationError: If environment variable is not set
        """
        if key is not None:
            raise ValueError(
                "Hardcoded keys are not allowed. "
                "Use environment variables via key_from_env parameter."
            )

        if not CRYPTO_AVAILABLE:
            raise EncryptionError("cryptography library not installed")

        self._key_env_var = key_from_env
        self._salt_env_var = salt_from_env

        # Derive the encryption key
        self._key = self._derive_key()

        # Create AESGCM instance
        self._cipher = AESGCM(self._key)

    def _derive_key(self) -> bytes:
        """
        Derive encryption key from environment variable.

        Returns:
            32-byte encryption key

        Raises:
            KeyDerivationError: If environment variable is not set
        """
        password = os.environ.get(self._key_env_var)
        if not password:
            raise KeyDerivationError(
                f"Environment variable {self._key_env_var} is not set. "
                f"Set it with a secure random value."
            )

        # Get or generate salt
        salt = os.environ.get(self._salt_env_var)
        if salt:
            salt_bytes = salt.encode()
        else:
            # Use a deterministic salt derived from the env var name
            # In production, use a proper random salt stored securely
            salt_bytes = hashlib.sha256(self._key_env_var.encode()).digest()[:self.SALT_LENGTH]

        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LENGTH,
            salt=salt_bytes,
            iterations=480000,  # OWASP recommended minimum
        )

        return kdf.derive(password.encode())

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string.

        Args:
            plaintext: String to encrypt

        Returns:
            Base64-encoded encrypted data (nonce + ciphertext)
        """
        if not isinstance(plaintext, str):
            raise TypeError("Plaintext must be a string")

        # Generate unique nonce
        nonce = secrets.token_bytes(self.NONCE_LENGTH)

        # Encrypt
        ciphertext = self._cipher.encrypt(nonce, plaintext.encode(), None)

        # Combine nonce + ciphertext and encode
        encrypted = nonce + ciphertext
        return base64.b64encode(encrypted).decode('ascii')

    def decrypt(self, encrypted: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            encrypted: Base64-encoded encrypted data

        Returns:
            Decrypted plaintext string

        Raises:
            DecryptionError: If decryption fails
        """
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted)

            # Split nonce and ciphertext
            if len(encrypted_bytes) < self.NONCE_LENGTH:
                raise DecryptionError("Encrypted data too short")

            nonce = encrypted_bytes[:self.NONCE_LENGTH]
            ciphertext = encrypted_bytes[self.NONCE_LENGTH:]

            # Decrypt
            plaintext = self._cipher.decrypt(nonce, ciphertext, None)
            return plaintext.decode('utf-8')

        except Exception as e:
            if isinstance(e, DecryptionError):
                raise
            raise DecryptionError(f"Decryption failed: {e}")

    def encrypt_bytes(self, data: bytes) -> bytes:
        """
        Encrypt raw bytes.

        Args:
            data: Bytes to encrypt

        Returns:
            Encrypted bytes (nonce + ciphertext)
        """
        nonce = secrets.token_bytes(self.NONCE_LENGTH)
        ciphertext = self._cipher.encrypt(nonce, data, None)
        return nonce + ciphertext

    def decrypt_bytes(self, encrypted: bytes) -> bytes:
        """
        Decrypt raw bytes.

        Args:
            encrypted: Encrypted bytes (nonce + ciphertext)

        Returns:
            Decrypted bytes
        """
        if len(encrypted) < self.NONCE_LENGTH:
            raise DecryptionError("Encrypted data too short")

        nonce = encrypted[:self.NONCE_LENGTH]
        ciphertext = encrypted[self.NONCE_LENGTH:]
        return self._cipher.decrypt(nonce, ciphertext, None)

    def rotate_key(self, new_key_env_var: str) -> None:
        """
        Rotate to a new encryption key.

        Note: This does NOT re-encrypt existing data.
        Call this after updating the environment variable.

        Args:
            new_key_env_var: New environment variable containing the key
        """
        old_key_var = self._key_env_var
        self._key_env_var = new_key_env_var
        self._key = self._derive_key()
        self._cipher = AESGCM(self._key)
        logger.info(f"Rotated encryption key from {old_key_var} to {new_key_env_var}")


class EncryptedConfigValue:
    """
    Helper for storing encrypted values in config files.

    Usage:
        # Encrypt a value
        encrypted = EncryptedConfigValue.encrypt("secret_api_key")
        # Store encrypted.value in config

        # Later, decrypt
        decrypted = EncryptedConfigValue.decrypt(stored_value)
    """

    PREFIX = "ENC:"  # Prefix to identify encrypted values

    @classmethod
    def is_encrypted(cls, value: str) -> bool:
        """Check if a value is encrypted."""
        return isinstance(value, str) and value.startswith(cls.PREFIX)

    @classmethod
    def encrypt(cls, plaintext: str, key_env: str = "JARVIS_ENCRYPTION_KEY") -> str:
        """
        Encrypt a config value.

        Args:
            plaintext: Value to encrypt
            key_env: Environment variable with encryption key

        Returns:
            Encrypted value with prefix
        """
        enc = SecureEncryption(key_from_env=key_env)
        encrypted = enc.encrypt(plaintext)
        return f"{cls.PREFIX}{encrypted}"

    @classmethod
    def decrypt(cls, encrypted: str, key_env: str = "JARVIS_ENCRYPTION_KEY") -> str:
        """
        Decrypt a config value.

        Args:
            encrypted: Encrypted value (with or without prefix)
            key_env: Environment variable with encryption key

        Returns:
            Decrypted plaintext
        """
        # Remove prefix if present
        if encrypted.startswith(cls.PREFIX):
            encrypted = encrypted[len(cls.PREFIX):]

        enc = SecureEncryption(key_from_env=key_env)
        return enc.decrypt(encrypted)

    @classmethod
    def decrypt_if_encrypted(
        cls,
        value: str,
        key_env: str = "JARVIS_ENCRYPTION_KEY"
    ) -> str:
        """
        Decrypt if encrypted, otherwise return as-is.

        Args:
            value: Potentially encrypted value
            key_env: Environment variable with encryption key

        Returns:
            Decrypted or original value
        """
        if cls.is_encrypted(value):
            return cls.decrypt(value, key_env)
        return value


# Factory function
def get_encryption(key_env: str = "JARVIS_ENCRYPTION_KEY") -> SecureEncryption:
    """
    Get an encryption instance.

    Args:
        key_env: Environment variable containing the encryption key

    Returns:
        SecureEncryption instance
    """
    return SecureEncryption(key_from_env=key_env)


# CLI for encrypting/decrypting values
if __name__ == "__main__":
    import sys

    def main():
        if len(sys.argv) < 3:
            print("Usage:")
            print("  python encryption.py encrypt <value>")
            print("  python encryption.py decrypt <encrypted_value>")
            print("")
            print("Requires JARVIS_ENCRYPTION_KEY environment variable to be set.")
            sys.exit(1)

        action = sys.argv[1]
        value = sys.argv[2]

        try:
            if action == "encrypt":
                result = EncryptedConfigValue.encrypt(value)
                print(f"Encrypted: {result}")
            elif action == "decrypt":
                result = EncryptedConfigValue.decrypt(value)
                print(f"Decrypted: {result}")
            else:
                print(f"Unknown action: {action}")
                sys.exit(1)
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)

    main()
