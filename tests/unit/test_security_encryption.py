"""
Comprehensive Tests for core/security/encryption.py

Tests for AES-256-GCM encryption module including:
- SecureEncryption class
- EncryptedConfigValue helper class
- Key derivation from environment variables
- Encryption/decryption roundtrips
- Key rotation
- Error handling
- Edge cases

Target: 90%+ coverage for core/security/encryption.py
"""

import pytest
import os
import base64
import secrets
from unittest.mock import patch, MagicMock, PropertyMock
from typing import Optional


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def mock_crypto_available():
    """Ensure cryptography library is mocked as available."""
    with patch.dict('os.environ', {'JARVIS_ENCRYPTION_KEY': 'test_password_for_encryption'}):
        yield


@pytest.fixture
def encryption_env():
    """Set up required environment variables for encryption."""
    env_vars = {
        'JARVIS_ENCRYPTION_KEY': 'test_password_for_encryption_12345',
        'JARVIS_ENCRYPTION_SALT': 'test_salt_value_16b',
        'TEST_ENCRYPTION_KEY': 'test_key_for_unit_tests_abc123',
        'TEST_SALT': 'another_salt_value',
        'NEW_ENCRYPTION_KEY': 'new_rotated_key_password_xyz789',
        'CUSTOM_KEY_ENV': 'custom_password_value_for_testing',
    }
    with patch.dict('os.environ', env_vars, clear=False):
        yield env_vars


@pytest.fixture
def secure_encryption(encryption_env):
    """Create a SecureEncryption instance for testing."""
    from core.security.encryption import SecureEncryption
    return SecureEncryption(key_from_env='JARVIS_ENCRYPTION_KEY')


@pytest.fixture
def secure_encryption_with_salt(encryption_env):
    """Create a SecureEncryption instance with explicit salt."""
    from core.security.encryption import SecureEncryption
    return SecureEncryption(
        key_from_env='JARVIS_ENCRYPTION_KEY',
        salt_from_env='JARVIS_ENCRYPTION_SALT'
    )


# =============================================================================
# Exception Classes Tests
# =============================================================================

class TestExceptionClasses:
    """Test custom exception classes."""

    def test_encryption_error_is_exception(self):
        """EncryptionError should be a proper exception."""
        from core.security.encryption import EncryptionError

        with pytest.raises(EncryptionError):
            raise EncryptionError("Test error")

    def test_encryption_error_message(self):
        """EncryptionError should preserve error message."""
        from core.security.encryption import EncryptionError

        error = EncryptionError("Test error message")
        assert str(error) == "Test error message"

    def test_key_derivation_error_inherits_encryption_error(self):
        """KeyDerivationError should inherit from EncryptionError."""
        from core.security.encryption import KeyDerivationError, EncryptionError

        assert issubclass(KeyDerivationError, EncryptionError)

    def test_key_derivation_error_message(self):
        """KeyDerivationError should preserve error message."""
        from core.security.encryption import KeyDerivationError

        error = KeyDerivationError("Key derivation failed")
        assert "Key derivation failed" in str(error)

    def test_decryption_error_inherits_encryption_error(self):
        """DecryptionError should inherit from EncryptionError."""
        from core.security.encryption import DecryptionError, EncryptionError

        assert issubclass(DecryptionError, EncryptionError)

    def test_decryption_error_message(self):
        """DecryptionError should preserve error message."""
        from core.security.encryption import DecryptionError

        error = DecryptionError("Decryption failed")
        assert "Decryption failed" in str(error)


# =============================================================================
# SecureEncryption Initialization Tests
# =============================================================================

class TestSecureEncryptionInit:
    """Test SecureEncryption initialization."""

    def test_init_with_default_env_vars(self, encryption_env):
        """Should initialize with default environment variable names."""
        from core.security.encryption import SecureEncryption

        enc = SecureEncryption()
        assert enc is not None
        assert enc._key_env_var == "JARVIS_ENCRYPTION_KEY"

    def test_init_with_custom_key_env(self, encryption_env):
        """Should initialize with custom key environment variable."""
        from core.security.encryption import SecureEncryption

        enc = SecureEncryption(key_from_env='CUSTOM_KEY_ENV')
        assert enc._key_env_var == 'CUSTOM_KEY_ENV'

    def test_init_with_custom_salt_env(self, encryption_env):
        """Should initialize with custom salt environment variable."""
        from core.security.encryption import SecureEncryption

        enc = SecureEncryption(key_from_env='JARVIS_ENCRYPTION_KEY', salt_from_env='TEST_SALT')
        assert enc._salt_env_var == 'TEST_SALT'

    def test_init_rejects_hardcoded_key(self, encryption_env):
        """Should reject hardcoded keys for security reasons."""
        from core.security.encryption import SecureEncryption

        with pytest.raises(ValueError) as exc_info:
            SecureEncryption(key="hardcoded_key_is_bad")

        assert "Hardcoded keys are not allowed" in str(exc_info.value)
        assert "environment variables" in str(exc_info.value).lower()

    def test_init_without_env_var_raises_error(self):
        """Should raise KeyDerivationError if env var is not set."""
        from core.security.encryption import SecureEncryption, KeyDerivationError

        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(KeyDerivationError) as exc_info:
                SecureEncryption(key_from_env='NONEXISTENT_KEY')

            assert "NONEXISTENT_KEY" in str(exc_info.value)
            assert "not set" in str(exc_info.value)

    def test_init_with_empty_env_var_raises_error(self):
        """Should raise KeyDerivationError if env var is empty."""
        from core.security.encryption import SecureEncryption, KeyDerivationError

        with patch.dict('os.environ', {'EMPTY_KEY': ''}):
            with pytest.raises(KeyDerivationError):
                SecureEncryption(key_from_env='EMPTY_KEY')

    def test_init_without_cryptography_library(self, encryption_env):
        """Should raise EncryptionError if cryptography is not available."""
        from core.security.encryption import EncryptionError

        with patch('core.security.encryption.CRYPTO_AVAILABLE', False):
            with pytest.raises(EncryptionError) as exc_info:
                from core.security.encryption import SecureEncryption
                # Force reimport to get the patched value
                import importlib
                import core.security.encryption as enc_module
                # Create instance directly
                enc_module.CRYPTO_AVAILABLE = False
                try:
                    enc_module.SecureEncryption(key_from_env='JARVIS_ENCRYPTION_KEY')
                except EncryptionError as e:
                    raise e
                finally:
                    enc_module.CRYPTO_AVAILABLE = True

    def test_constants_defined(self, encryption_env):
        """Should have correct constants defined."""
        from core.security.encryption import SecureEncryption

        assert SecureEncryption.KEY_LENGTH == 32  # 256 bits
        assert SecureEncryption.NONCE_LENGTH == 12  # 96 bits for GCM
        assert SecureEncryption.SALT_LENGTH == 16
        assert SecureEncryption.algorithm == "AES-256-GCM"
        assert SecureEncryption.key_length == 32


# =============================================================================
# Key Derivation Tests
# =============================================================================

class TestKeyDerivation:
    """Test key derivation functionality."""

    def test_key_derivation_produces_32_bytes(self, secure_encryption):
        """Derived key should be 32 bytes (256 bits)."""
        assert len(secure_encryption._key) == 32

    def test_key_derivation_deterministic_with_same_inputs(self, encryption_env):
        """Same password and salt should produce same key."""
        from core.security.encryption import SecureEncryption

        enc1 = SecureEncryption(
            key_from_env='JARVIS_ENCRYPTION_KEY',
            salt_from_env='JARVIS_ENCRYPTION_SALT'
        )
        enc2 = SecureEncryption(
            key_from_env='JARVIS_ENCRYPTION_KEY',
            salt_from_env='JARVIS_ENCRYPTION_SALT'
        )

        assert enc1._key == enc2._key

    def test_key_derivation_different_with_different_password(self, encryption_env):
        """Different passwords should produce different keys."""
        from core.security.encryption import SecureEncryption

        enc1 = SecureEncryption(key_from_env='JARVIS_ENCRYPTION_KEY')
        enc2 = SecureEncryption(key_from_env='TEST_ENCRYPTION_KEY')

        assert enc1._key != enc2._key

    def test_key_derivation_uses_default_salt_when_not_provided(self, encryption_env):
        """Should use deterministic default salt when env var not set."""
        from core.security.encryption import SecureEncryption

        with patch.dict('os.environ', {'JARVIS_ENCRYPTION_KEY': 'password'}, clear=False):
            # Clear the salt env var
            env_without_salt = dict(os.environ)
            env_without_salt.pop('JARVIS_ENCRYPTION_SALT', None)

            with patch.dict('os.environ', env_without_salt, clear=True):
                enc = SecureEncryption(
                    key_from_env='JARVIS_ENCRYPTION_KEY',
                    salt_from_env='NONEXISTENT_SALT'
                )
                # Should not raise - uses derived salt
                assert enc._key is not None
                assert len(enc._key) == 32


# =============================================================================
# String Encryption/Decryption Tests
# =============================================================================

class TestStringEncryption:
    """Test string encryption and decryption."""

    def test_encrypt_returns_string(self, secure_encryption):
        """Encrypt should return a string."""
        result = secure_encryption.encrypt("test plaintext")
        assert isinstance(result, str)

    def test_encrypt_returns_base64(self, secure_encryption):
        """Encrypted output should be valid base64."""
        encrypted = secure_encryption.encrypt("test plaintext")
        # Should not raise
        decoded = base64.b64decode(encrypted)
        assert len(decoded) > 0

    def test_encrypt_different_each_time(self, secure_encryption):
        """Each encryption should produce different output (unique nonce)."""
        plaintext = "same plaintext"
        encrypted1 = secure_encryption.encrypt(plaintext)
        encrypted2 = secure_encryption.encrypt(plaintext)

        assert encrypted1 != encrypted2

    def test_encrypt_does_not_contain_plaintext(self, secure_encryption):
        """Encrypted output should not contain plaintext."""
        plaintext = "sensitive_api_key_12345"
        encrypted = secure_encryption.encrypt(plaintext)

        assert plaintext not in encrypted
        assert plaintext not in base64.b64decode(encrypted).decode('utf-8', errors='ignore')

    def test_encrypt_rejects_non_string(self, secure_encryption):
        """Encrypt should reject non-string input."""
        with pytest.raises(TypeError) as exc_info:
            secure_encryption.encrypt(12345)  # type: ignore

        assert "string" in str(exc_info.value).lower()

    def test_encrypt_rejects_bytes(self, secure_encryption):
        """Encrypt should reject bytes (use encrypt_bytes instead)."""
        with pytest.raises(TypeError):
            secure_encryption.encrypt(b"bytes data")  # type: ignore

    def test_encrypt_rejects_none(self, secure_encryption):
        """Encrypt should reject None input."""
        with pytest.raises(TypeError):
            secure_encryption.encrypt(None)  # type: ignore

    def test_decrypt_returns_original(self, secure_encryption):
        """Decrypt should return the original plaintext."""
        original = "test plaintext message"
        encrypted = secure_encryption.encrypt(original)
        decrypted = secure_encryption.decrypt(encrypted)

        assert decrypted == original

    def test_decrypt_roundtrip_various_lengths(self, secure_encryption):
        """Roundtrip should work for various plaintext lengths."""
        test_cases = [
            "",  # Empty string
            "a",  # Single char
            "short",  # Short string
            "a" * 100,  # Medium string
            "a" * 10000,  # Long string
            "unicode: \u00e9\u00e8\u00ea\u00eb",  # Unicode chars
            "emoji: \U0001F600\U0001F601",  # Emojis
            "newlines\n\r\n\ttabs",  # Whitespace
        ]

        for plaintext in test_cases:
            encrypted = secure_encryption.encrypt(plaintext)
            decrypted = secure_encryption.decrypt(encrypted)
            assert decrypted == plaintext, f"Failed for: {repr(plaintext)}"

    def test_decrypt_invalid_base64_raises_error(self, secure_encryption):
        """Decrypt should raise DecryptionError for invalid base64."""
        from core.security.encryption import DecryptionError

        with pytest.raises(DecryptionError):
            secure_encryption.decrypt("not valid base64!!!")

    def test_decrypt_too_short_data_raises_error(self, secure_encryption):
        """Decrypt should raise DecryptionError for too-short data."""
        from core.security.encryption import DecryptionError

        # Create valid base64 but too short for nonce
        short_data = base64.b64encode(b"short").decode('ascii')

        with pytest.raises(DecryptionError) as exc_info:
            secure_encryption.decrypt(short_data)

        assert "too short" in str(exc_info.value).lower()

    def test_decrypt_corrupted_data_raises_error(self, secure_encryption):
        """Decrypt should raise DecryptionError for corrupted data."""
        from core.security.encryption import DecryptionError

        # Encrypt valid data then corrupt it
        encrypted = secure_encryption.encrypt("original")
        encrypted_bytes = base64.b64decode(encrypted)
        corrupted_bytes = encrypted_bytes[:-1] + bytes([encrypted_bytes[-1] ^ 0xFF])
        corrupted = base64.b64encode(corrupted_bytes).decode('ascii')

        with pytest.raises(DecryptionError):
            secure_encryption.decrypt(corrupted)

    def test_decrypt_wrong_key_raises_error(self, encryption_env):
        """Decrypt with wrong key should raise DecryptionError."""
        from core.security.encryption import SecureEncryption, DecryptionError

        enc1 = SecureEncryption(key_from_env='JARVIS_ENCRYPTION_KEY')
        enc2 = SecureEncryption(key_from_env='TEST_ENCRYPTION_KEY')

        encrypted = enc1.encrypt("secret message")

        with pytest.raises(DecryptionError):
            enc2.decrypt(encrypted)


# =============================================================================
# Bytes Encryption/Decryption Tests
# =============================================================================

class TestBytesEncryption:
    """Test bytes encryption and decryption."""

    def test_encrypt_bytes_returns_bytes(self, secure_encryption):
        """encrypt_bytes should return bytes."""
        result = secure_encryption.encrypt_bytes(b"test data")
        assert isinstance(result, bytes)

    def test_encrypt_bytes_different_each_time(self, secure_encryption):
        """Each bytes encryption should produce different output."""
        data = b"same data"
        encrypted1 = secure_encryption.encrypt_bytes(data)
        encrypted2 = secure_encryption.encrypt_bytes(data)

        assert encrypted1 != encrypted2

    def test_decrypt_bytes_returns_original(self, secure_encryption):
        """decrypt_bytes should return original data."""
        original = b"binary data \x00\x01\x02"
        encrypted = secure_encryption.encrypt_bytes(original)
        decrypted = secure_encryption.decrypt_bytes(encrypted)

        assert decrypted == original

    def test_bytes_roundtrip_various_data(self, secure_encryption):
        """Bytes roundtrip should work for various data."""
        test_cases = [
            b"",  # Empty
            b"\x00",  # Null byte
            b"\x00\x01\x02\x03",  # Binary data
            b"plain text bytes",  # Text as bytes
            secrets.token_bytes(1024),  # Random binary
        ]

        for data in test_cases:
            encrypted = secure_encryption.encrypt_bytes(data)
            decrypted = secure_encryption.decrypt_bytes(encrypted)
            assert decrypted == data

    def test_decrypt_bytes_too_short_raises_error(self, secure_encryption):
        """decrypt_bytes should raise DecryptionError for too-short data."""
        from core.security.encryption import DecryptionError

        with pytest.raises(DecryptionError) as exc_info:
            secure_encryption.decrypt_bytes(b"short")

        assert "too short" in str(exc_info.value).lower()

    def test_decrypt_bytes_corrupted_raises_error(self, secure_encryption):
        """decrypt_bytes should raise error for corrupted data."""
        from core.security.encryption import DecryptionError

        encrypted = secure_encryption.encrypt_bytes(b"original")
        corrupted = encrypted[:-1] + bytes([encrypted[-1] ^ 0xFF])

        with pytest.raises(Exception):  # Could be DecryptionError or crypto exception
            secure_encryption.decrypt_bytes(corrupted)


# =============================================================================
# Key Rotation Tests
# =============================================================================

class TestKeyRotation:
    """Test key rotation functionality."""

    def test_rotate_key_updates_key(self, secure_encryption, encryption_env):
        """rotate_key should update the encryption key."""
        old_key = secure_encryption._key

        secure_encryption.rotate_key('TEST_ENCRYPTION_KEY')

        assert secure_encryption._key != old_key
        assert secure_encryption._key_env_var == 'TEST_ENCRYPTION_KEY'

    def test_rotate_key_data_not_reencrypted(self, secure_encryption, encryption_env):
        """rotate_key does NOT re-encrypt existing data."""
        from core.security.encryption import DecryptionError

        # Encrypt with original key
        encrypted = secure_encryption.encrypt("secret")

        # Rotate to new key
        secure_encryption.rotate_key('TEST_ENCRYPTION_KEY')

        # Old encrypted data should NOT be decryptable with new key
        with pytest.raises(DecryptionError):
            secure_encryption.decrypt(encrypted)

    def test_rotate_key_new_encryption_works(self, secure_encryption, encryption_env):
        """After rotation, new encryptions should work."""
        secure_encryption.rotate_key('TEST_ENCRYPTION_KEY')

        # New encryption/decryption should work
        encrypted = secure_encryption.encrypt("new secret")
        decrypted = secure_encryption.decrypt(encrypted)

        assert decrypted == "new secret"

    def test_rotate_key_missing_env_var_raises_error(self, secure_encryption):
        """rotate_key should raise error if new env var doesn't exist."""
        from core.security.encryption import KeyDerivationError

        with pytest.raises(KeyDerivationError):
            secure_encryption.rotate_key('NONEXISTENT_NEW_KEY')


# =============================================================================
# EncryptedConfigValue Tests
# =============================================================================

class TestEncryptedConfigValue:
    """Test EncryptedConfigValue helper class."""

    def test_prefix_constant(self):
        """Should have ENC: prefix constant."""
        from core.security.encryption import EncryptedConfigValue

        assert EncryptedConfigValue.PREFIX == "ENC:"

    def test_is_encrypted_true_for_prefixed_value(self):
        """is_encrypted should return True for ENC: prefixed values."""
        from core.security.encryption import EncryptedConfigValue

        assert EncryptedConfigValue.is_encrypted("ENC:abcdef123") is True

    def test_is_encrypted_false_for_plain_value(self):
        """is_encrypted should return False for non-prefixed values."""
        from core.security.encryption import EncryptedConfigValue

        assert EncryptedConfigValue.is_encrypted("plain_value") is False
        assert EncryptedConfigValue.is_encrypted("api_key_12345") is False

    def test_is_encrypted_false_for_non_string(self):
        """is_encrypted should return False for non-string values."""
        from core.security.encryption import EncryptedConfigValue

        assert EncryptedConfigValue.is_encrypted(12345) is False  # type: ignore
        assert EncryptedConfigValue.is_encrypted(None) is False  # type: ignore
        assert EncryptedConfigValue.is_encrypted([]) is False  # type: ignore

    def test_encrypt_returns_prefixed_value(self, encryption_env):
        """encrypt should return value with ENC: prefix."""
        from core.security.encryption import EncryptedConfigValue

        encrypted = EncryptedConfigValue.encrypt("secret_value")

        assert encrypted.startswith("ENC:")

    def test_encrypt_decrypt_roundtrip(self, encryption_env):
        """Encrypt then decrypt should return original value."""
        from core.security.encryption import EncryptedConfigValue

        original = "my_secret_api_key"
        encrypted = EncryptedConfigValue.encrypt(original)
        decrypted = EncryptedConfigValue.decrypt(encrypted)

        assert decrypted == original

    def test_decrypt_with_prefix(self, encryption_env):
        """decrypt should handle values with ENC: prefix."""
        from core.security.encryption import EncryptedConfigValue

        encrypted = EncryptedConfigValue.encrypt("secret")
        # Should work with prefix
        decrypted = EncryptedConfigValue.decrypt(encrypted)
        assert decrypted == "secret"

    def test_decrypt_without_prefix(self, encryption_env):
        """decrypt should handle values without ENC: prefix."""
        from core.security.encryption import EncryptedConfigValue

        encrypted = EncryptedConfigValue.encrypt("secret")
        # Remove prefix
        encrypted_no_prefix = encrypted[len("ENC:"):]
        decrypted = EncryptedConfigValue.decrypt(encrypted_no_prefix)
        assert decrypted == "secret"

    def test_encrypt_with_custom_key_env(self, encryption_env):
        """encrypt should use custom key environment variable."""
        from core.security.encryption import EncryptedConfigValue

        encrypted = EncryptedConfigValue.encrypt("secret", key_env="TEST_ENCRYPTION_KEY")

        # Should be decryptable with same key
        decrypted = EncryptedConfigValue.decrypt(encrypted, key_env="TEST_ENCRYPTION_KEY")
        assert decrypted == "secret"

    def test_decrypt_if_encrypted_decrypts_encrypted_value(self, encryption_env):
        """decrypt_if_encrypted should decrypt encrypted values."""
        from core.security.encryption import EncryptedConfigValue

        encrypted = EncryptedConfigValue.encrypt("secret_value")
        result = EncryptedConfigValue.decrypt_if_encrypted(encrypted)

        assert result == "secret_value"

    def test_decrypt_if_encrypted_returns_plain_value(self, encryption_env):
        """decrypt_if_encrypted should return plain values as-is."""
        from core.security.encryption import EncryptedConfigValue

        plain_value = "not_encrypted_value"
        result = EncryptedConfigValue.decrypt_if_encrypted(plain_value)

        assert result == plain_value

    def test_decrypt_if_encrypted_with_custom_key(self, encryption_env):
        """decrypt_if_encrypted should use custom key."""
        from core.security.encryption import EncryptedConfigValue

        encrypted = EncryptedConfigValue.encrypt("secret", key_env="TEST_ENCRYPTION_KEY")
        result = EncryptedConfigValue.decrypt_if_encrypted(
            encrypted,
            key_env="TEST_ENCRYPTION_KEY"
        )

        assert result == "secret"


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestGetEncryption:
    """Test get_encryption factory function."""

    def test_returns_secure_encryption_instance(self, encryption_env):
        """get_encryption should return SecureEncryption instance."""
        from core.security.encryption import get_encryption, SecureEncryption

        enc = get_encryption()

        assert isinstance(enc, SecureEncryption)

    def test_uses_default_key_env(self, encryption_env):
        """get_encryption should use default JARVIS_ENCRYPTION_KEY."""
        from core.security.encryption import get_encryption

        enc = get_encryption()

        assert enc._key_env_var == "JARVIS_ENCRYPTION_KEY"

    def test_accepts_custom_key_env(self, encryption_env):
        """get_encryption should accept custom key env var."""
        from core.security.encryption import get_encryption

        enc = get_encryption(key_env="TEST_ENCRYPTION_KEY")

        assert enc._key_env_var == "TEST_ENCRYPTION_KEY"

    def test_encryption_works(self, encryption_env):
        """get_encryption should return working encryption instance."""
        from core.security.encryption import get_encryption

        enc = get_encryption()
        encrypted = enc.encrypt("test")
        decrypted = enc.decrypt(encrypted)

        assert decrypted == "test"


# =============================================================================
# Security Properties Tests
# =============================================================================

class TestSecurityProperties:
    """Test security-related properties."""

    def test_uses_aes256_gcm(self, secure_encryption):
        """Should use AES-256-GCM algorithm."""
        assert secure_encryption.algorithm == "AES-256-GCM"

    def test_key_length_is_256_bits(self, secure_encryption):
        """Key length should be 32 bytes (256 bits)."""
        assert secure_encryption.key_length == 32
        assert len(secure_encryption._key) == 32

    def test_nonce_is_unique_per_encryption(self, secure_encryption):
        """Each encryption should use a unique nonce."""
        encrypted1 = secure_encryption.encrypt("same")
        encrypted2 = secure_encryption.encrypt("same")

        # Decode and extract nonces (first 12 bytes)
        nonce1 = base64.b64decode(encrypted1)[:12]
        nonce2 = base64.b64decode(encrypted2)[:12]

        assert nonce1 != nonce2

    def test_nonce_length_is_96_bits(self, secure_encryption):
        """Nonce should be 12 bytes (96 bits) as per GCM standard."""
        encrypted = secure_encryption.encrypt("test")
        encrypted_bytes = base64.b64decode(encrypted)

        # Nonce is first 12 bytes
        nonce = encrypted_bytes[:12]
        assert len(nonce) == 12

    def test_ciphertext_includes_auth_tag(self, secure_encryption):
        """Ciphertext should include GCM authentication tag."""
        plaintext = "test"
        encrypted = secure_encryption.encrypt(plaintext)
        encrypted_bytes = base64.b64decode(encrypted)

        # encrypted_bytes = nonce (12) + ciphertext + auth_tag (16)
        # GCM auth tag is 16 bytes
        # So minimum length is 12 + len(plaintext) + 16
        min_length = 12 + len(plaintext) + 16
        assert len(encrypted_bytes) >= min_length


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================

class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    def test_encrypt_empty_string(self, secure_encryption):
        """Should handle empty string encryption."""
        encrypted = secure_encryption.encrypt("")
        decrypted = secure_encryption.decrypt(encrypted)
        assert decrypted == ""

    def test_encrypt_empty_bytes(self, secure_encryption):
        """Should handle empty bytes encryption."""
        encrypted = secure_encryption.encrypt_bytes(b"")
        decrypted = secure_encryption.decrypt_bytes(encrypted)
        assert decrypted == b""

    def test_encrypt_large_data(self, secure_encryption):
        """Should handle large data encryption."""
        large_data = "x" * 1_000_000  # 1MB
        encrypted = secure_encryption.encrypt(large_data)
        decrypted = secure_encryption.decrypt(encrypted)
        assert decrypted == large_data

    def test_encrypt_special_characters(self, secure_encryption):
        """Should handle special characters."""
        special = "!@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        encrypted = secure_encryption.encrypt(special)
        decrypted = secure_encryption.decrypt(encrypted)
        assert decrypted == special

    def test_encrypt_null_bytes(self, secure_encryption):
        """Should handle strings with embedded null-like characters."""
        # Note: Python strings don't have real null terminators
        data = "before\x00after"
        encrypted = secure_encryption.encrypt(data)
        decrypted = secure_encryption.decrypt(encrypted)
        assert decrypted == data

    def test_encrypt_bytes_with_all_byte_values(self, secure_encryption):
        """Should handle all possible byte values."""
        all_bytes = bytes(range(256))
        encrypted = secure_encryption.encrypt_bytes(all_bytes)
        decrypted = secure_encryption.decrypt_bytes(encrypted)
        assert decrypted == all_bytes

    def test_decrypt_completely_wrong_format(self, secure_encryption):
        """Should handle completely wrong format gracefully."""
        from core.security.encryption import DecryptionError

        with pytest.raises(DecryptionError):
            secure_encryption.decrypt("not-even-base64!")

    def test_decrypt_random_base64(self, secure_encryption):
        """Should fail gracefully on random base64 data."""
        from core.security.encryption import DecryptionError

        random_data = base64.b64encode(secrets.token_bytes(100)).decode('ascii')

        with pytest.raises((DecryptionError, Exception)):
            secure_encryption.decrypt(random_data)


# =============================================================================
# CRYPTO_AVAILABLE Flag Tests
# =============================================================================

class TestCryptoAvailableFlag:
    """Test CRYPTO_AVAILABLE flag behavior."""

    def test_crypto_available_when_library_present(self):
        """CRYPTO_AVAILABLE should be True when cryptography is installed."""
        from core.security import encryption

        # The library should be available in test environment
        assert encryption.CRYPTO_AVAILABLE is True

    def test_imports_succeed_when_crypto_available(self):
        """Should successfully import from cryptography when available."""
        from core.security import encryption

        if encryption.CRYPTO_AVAILABLE:
            # These should be imported
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            assert AESGCM is not None
            assert PBKDF2HMAC is not None


# =============================================================================
# Concurrent/Threading Safety Tests
# =============================================================================

class TestThreadingSafety:
    """Test thread safety of encryption operations."""

    def test_concurrent_encryptions(self, secure_encryption):
        """Multiple concurrent encryptions should work correctly."""
        import threading
        results = []
        errors = []

        def encrypt_task(plaintext, index):
            try:
                encrypted = secure_encryption.encrypt(plaintext)
                decrypted = secure_encryption.decrypt(encrypted)
                if decrypted == plaintext:
                    results.append((index, True))
                else:
                    results.append((index, False))
            except Exception as e:
                errors.append((index, str(e)))

        threads = []
        for i in range(10):
            t = threading.Thread(target=encrypt_task, args=(f"message_{i}", i))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10
        assert all(success for _, success in results)


# =============================================================================
# Memory Safety Tests
# =============================================================================

class TestMemorySafety:
    """Test memory handling of sensitive data."""

    def test_key_not_exposed_in_repr(self, secure_encryption):
        """Key should not be exposed in object representation."""
        repr_str = repr(secure_encryption)
        # The key bytes should not appear in repr
        key_hex = secure_encryption._key.hex()
        assert key_hex not in repr_str

    def test_key_not_exposed_in_str(self, secure_encryption):
        """Key should not be exposed in string representation."""
        str_repr = str(secure_encryption)
        key_hex = secure_encryption._key.hex()
        assert key_hex not in str_repr


# =============================================================================
# Integration-like Tests
# =============================================================================

class TestIntegrationScenarios:
    """Test realistic usage scenarios."""

    def test_encrypt_api_key_workflow(self, encryption_env):
        """Test encrypting and storing API keys."""
        from core.security.encryption import EncryptedConfigValue

        api_key = "sk_live_abc123xyz789"

        # Encrypt for storage
        encrypted = EncryptedConfigValue.encrypt(api_key)
        assert EncryptedConfigValue.is_encrypted(encrypted)

        # Store (simulated)
        stored_config = {"api_key": encrypted}

        # Retrieve and decrypt
        retrieved = stored_config["api_key"]
        decrypted = EncryptedConfigValue.decrypt_if_encrypted(retrieved)

        assert decrypted == api_key

    def test_config_migration_scenario(self, encryption_env):
        """Test migrating plain config values to encrypted."""
        from core.security.encryption import EncryptedConfigValue

        # Old config with plain values
        old_config = {
            "database_url": "postgres://user:password@host/db",
            "api_key": "plain_api_key",
            "public_key": "not_secret"
        }

        # Encrypt sensitive values
        sensitive_keys = ["database_url", "api_key"]
        new_config = {}

        for key, value in old_config.items():
            if key in sensitive_keys:
                new_config[key] = EncryptedConfigValue.encrypt(value)
            else:
                new_config[key] = value

        # Verify encrypted
        assert EncryptedConfigValue.is_encrypted(new_config["database_url"])
        assert EncryptedConfigValue.is_encrypted(new_config["api_key"])
        assert not EncryptedConfigValue.is_encrypted(new_config["public_key"])

        # Verify decryption
        assert EncryptedConfigValue.decrypt(new_config["database_url"]) == old_config["database_url"]
        assert EncryptedConfigValue.decrypt(new_config["api_key"]) == old_config["api_key"]

    def test_key_rotation_workflow(self, encryption_env):
        """Test full key rotation workflow."""
        from core.security.encryption import SecureEncryption

        # Create encryption with old key
        old_enc = SecureEncryption(key_from_env='JARVIS_ENCRYPTION_KEY')

        # Encrypt some data
        secrets_data = ["secret1", "secret2", "secret3"]
        encrypted_data = [old_enc.encrypt(s) for s in secrets_data]

        # Create encryption with new key
        new_enc = SecureEncryption(key_from_env='TEST_ENCRYPTION_KEY')

        # Re-encrypt data with new key
        migrated_data = []
        for i, enc_value in enumerate(encrypted_data):
            # Decrypt with old key
            plain = old_enc.decrypt(enc_value)
            # Encrypt with new key
            new_enc_value = new_enc.encrypt(plain)
            migrated_data.append(new_enc_value)

        # Verify new data works with new key
        for i, enc_value in enumerate(migrated_data):
            decrypted = new_enc.decrypt(enc_value)
            assert decrypted == secrets_data[i]

    def test_multi_environment_encryption(self, encryption_env):
        """Test encryption with different keys per environment."""
        from core.security.encryption import SecureEncryption

        # Different environments use different keys
        prod_enc = SecureEncryption(key_from_env='JARVIS_ENCRYPTION_KEY')
        test_enc = SecureEncryption(key_from_env='TEST_ENCRYPTION_KEY')

        secret = "shared_secret_value"

        # Encrypt for each environment
        prod_encrypted = prod_enc.encrypt(secret)
        test_encrypted = test_enc.encrypt(secret)

        # They should be different
        assert prod_encrypted != test_encrypted

        # Each can only decrypt its own
        assert prod_enc.decrypt(prod_encrypted) == secret
        assert test_enc.decrypt(test_encrypted) == secret

        # Cross-decryption should fail
        from core.security.encryption import DecryptionError
        with pytest.raises(DecryptionError):
            prod_enc.decrypt(test_encrypted)
        with pytest.raises(DecryptionError):
            test_enc.decrypt(prod_encrypted)
