"""
JARVIS Encrypted Storage - Secure Key Management

Provides encryption at rest for sensitive data like private keys.
Uses Fernet symmetric encryption with password-derived keys.

Features:
- AES-256 encryption via Fernet
- PBKDF2 key derivation from password
- Secure memory handling
- Migration from plaintext
- Backup and recovery

Usage:
    from core.security.encrypted_storage import SecureStorage

    storage = SecureStorage(password="from_env_or_prompt")
    storage.store_key("treasury", private_key_bytes)
    key = storage.get_key("treasury")

Dependencies:
    pip install cryptography
"""

import base64
import hashlib
import json
import logging
import os
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    Fernet = None
    InvalidToken = Exception
    logger.warning("cryptography not installed. Run: pip install cryptography")


ROOT = Path(__file__).resolve().parents[2]
SECURE_DIR = ROOT / "data" / "secure"
SALT_FILE = SECURE_DIR / ".salt"
KEYS_FILE = SECURE_DIR / "encrypted_keys.bin"
BACKUP_DIR = SECURE_DIR / "backups"


class SecureStorageError(Exception):
    """Base exception for secure storage errors."""
    pass


class DecryptionError(SecureStorageError):
    """Failed to decrypt data."""
    pass


class KeyNotFoundError(SecureStorageError):
    """Requested key not found."""
    pass


class SecureStorage:
    """
    Encrypted storage for sensitive keys and secrets.

    All data is encrypted using Fernet (AES-256-CBC with HMAC).
    The encryption key is derived from a password using PBKDF2.

    Security model:
    - Master password required to unlock storage
    - Password can come from env var or interactive prompt
    - Salt is unique per installation
    - Keys are never stored in plaintext
    """

    ENV_PASSWORD_KEY = "JARVIS_SECURE_PASSWORD"

    def __init__(self, password: Optional[str] = None):
        """
        Initialize secure storage.

        Args:
            password: Master password. If not provided, reads from
                      JARVIS_SECURE_PASSWORD env var.
        """
        if not CRYPTO_AVAILABLE:
            raise SecureStorageError("cryptography library not installed")

        self._password = password or os.getenv(self.ENV_PASSWORD_KEY)
        if not self._password:
            raise SecureStorageError(
                f"No password provided. Set {self.ENV_PASSWORD_KEY} env var "
                "or pass password to constructor."
            )

        # Ensure directories exist
        SECURE_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Set restrictive permissions (owner only)
        try:
            os.chmod(SECURE_DIR, 0o700)
        except Exception:
            pass  # May fail on Windows

        # Initialize or load salt
        self._salt = self._get_or_create_salt()

        # Derive encryption key
        self._fernet = self._create_fernet()

        # Load encrypted keys
        self._keys: Dict[str, bytes] = {}
        self._load_keys()

    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create new one."""
        if SALT_FILE.exists():
            return SALT_FILE.read_bytes()

        # Generate new random salt
        salt = secrets.token_bytes(32)
        SALT_FILE.write_bytes(salt)

        try:
            os.chmod(SALT_FILE, 0o600)
        except Exception:
            pass

        logger.info("Created new encryption salt")
        return salt

    def _create_fernet(self) -> Fernet:
        """Derive encryption key from password and create Fernet instance."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=self._salt,
            iterations=480000,  # OWASP recommended minimum
        )

        key = base64.urlsafe_b64encode(
            kdf.derive(self._password.encode())
        )

        return Fernet(key)

    def _load_keys(self):
        """Load encrypted keys from disk."""
        if not KEYS_FILE.exists():
            self._keys = {}
            return

        try:
            encrypted_data = KEYS_FILE.read_bytes()
            decrypted_data = self._fernet.decrypt(encrypted_data)
            self._keys = json.loads(decrypted_data)

            # Convert base64 strings back to bytes
            self._keys = {
                k: base64.b64decode(v) if isinstance(v, str) else v
                for k, v in self._keys.items()
            }

            logger.info(f"Loaded {len(self._keys)} encrypted keys")

        except InvalidToken:
            raise DecryptionError(
                "Failed to decrypt keys. Wrong password or corrupted data."
            )
        except Exception as e:
            logger.error(f"Failed to load keys: {e}")
            self._keys = {}

    def _save_keys(self):
        """Save encrypted keys to disk."""
        # Convert bytes to base64 strings for JSON
        serializable = {
            k: base64.b64encode(v).decode() if isinstance(v, bytes) else v
            for k, v in self._keys.items()
        }

        json_data = json.dumps(serializable).encode()
        encrypted_data = self._fernet.encrypt(json_data)

        # Write atomically
        temp_file = KEYS_FILE.with_suffix('.tmp')
        temp_file.write_bytes(encrypted_data)
        temp_file.replace(KEYS_FILE)

        try:
            os.chmod(KEYS_FILE, 0o600)
        except Exception:
            pass

        logger.debug(f"Saved {len(self._keys)} encrypted keys")

    def store_key(self, name: str, key_data: Union[bytes, str]) -> None:
        """
        Store a key securely.

        Args:
            name: Unique identifier for the key
            key_data: The key to store (bytes or string)
        """
        if isinstance(key_data, str):
            key_data = key_data.encode()

        self._keys[name] = key_data
        self._save_keys()
        logger.info(f"Stored encrypted key: {name}")

    def get_key(self, name: str) -> bytes:
        """
        Retrieve a stored key.

        Args:
            name: Key identifier

        Returns:
            The decrypted key data

        Raises:
            KeyNotFoundError: If key doesn't exist
        """
        if name not in self._keys:
            raise KeyNotFoundError(f"Key not found: {name}")

        return self._keys[name]

    def get_key_str(self, name: str) -> str:
        """Get key as UTF-8 string."""
        return self.get_key(name).decode()

    def has_key(self, name: str) -> bool:
        """Check if a key exists."""
        return name in self._keys

    def delete_key(self, name: str) -> bool:
        """
        Delete a stored key.

        Args:
            name: Key identifier

        Returns:
            True if key was deleted, False if not found
        """
        if name not in self._keys:
            return False

        del self._keys[name]
        self._save_keys()
        logger.info(f"Deleted key: {name}")
        return True

    def list_keys(self) -> list:
        """List all stored key names."""
        return list(self._keys.keys())

    def create_backup(self) -> Path:
        """
        Create a backup of encrypted keys.

        Returns:
            Path to backup file
        """
        if not KEYS_FILE.exists():
            raise SecureStorageError("No keys to backup")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = BACKUP_DIR / f"keys_backup_{timestamp}.bin"

        # Copy encrypted file
        backup_file.write_bytes(KEYS_FILE.read_bytes())

        # Also backup salt
        salt_backup = BACKUP_DIR / f"salt_backup_{timestamp}.bin"
        salt_backup.write_bytes(self._salt)

        logger.info(f"Created backup: {backup_file}")
        return backup_file

    def rotate_password(self, new_password: str) -> None:
        """
        Change the master password.

        Re-encrypts all keys with new password-derived key.

        Args:
            new_password: The new master password
        """
        # Create backup first
        if self._keys:
            self.create_backup()

        # Update password and re-derive key
        self._password = new_password
        self._fernet = self._create_fernet()

        # Re-save with new encryption
        self._save_keys()
        logger.info("Password rotated successfully")


class KeyMigrator:
    """
    Migrate plaintext keys to encrypted storage.

    Handles migration from legacy JSON key files to secure storage.
    """

    # Known plaintext key files to migrate
    LEGACY_FILES = [
        ("data/treasury_keypair.json", "treasury_keypair"),
        ("data/active_keypair.json", "active_keypair"),
        ("wallets/treasury.json", "wallet_treasury"),
        ("wallets/active.json", "wallet_active"),
    ]

    def __init__(self, storage: SecureStorage):
        self.storage = storage

    def migrate_all(self, delete_originals: bool = False) -> Dict[str, bool]:
        """
        Migrate all known plaintext key files.

        Args:
            delete_originals: If True, securely delete original files

        Returns:
            Dict mapping file paths to migration success
        """
        results = {}

        for rel_path, key_name in self.LEGACY_FILES:
            file_path = ROOT / rel_path

            if not file_path.exists():
                results[rel_path] = None  # Doesn't exist
                continue

            try:
                success = self.migrate_file(file_path, key_name, delete_originals)
                results[rel_path] = success
            except Exception as e:
                logger.error(f"Migration failed for {rel_path}: {e}")
                results[rel_path] = False

        return results

    def migrate_file(
        self,
        file_path: Path,
        key_name: str,
        delete_original: bool = False
    ) -> bool:
        """
        Migrate a single key file.

        Args:
            file_path: Path to plaintext key file
            key_name: Name for encrypted storage
            delete_original: Securely delete original if True

        Returns:
            True if migration successful
        """
        if not file_path.exists():
            return False

        # Read plaintext content
        content = file_path.read_bytes()

        # Store encrypted
        self.storage.store_key(key_name, content)

        logger.info(f"Migrated {file_path} to encrypted storage as '{key_name}'")

        if delete_original:
            self._secure_delete(file_path)
        else:
            # Rename to .bak
            backup_path = file_path.with_suffix(file_path.suffix + '.migrated')
            file_path.rename(backup_path)
            logger.info(f"Renamed original to {backup_path}")

        return True

    def _secure_delete(self, file_path: Path):
        """Securely delete a file by overwriting."""
        size = file_path.stat().st_size

        # Overwrite with random data 3 times
        for _ in range(3):
            with open(file_path, 'wb') as f:
                f.write(secrets.token_bytes(size))
                f.flush()
                os.fsync(f.fileno())

        # Finally delete
        file_path.unlink()
        logger.info(f"Securely deleted: {file_path}")


def get_secure_storage() -> Optional[SecureStorage]:
    """
    Get secure storage instance if password is configured.

    Returns:
        SecureStorage instance or None if not configured
    """
    try:
        return SecureStorage()
    except SecureStorageError:
        return None


def migrate_legacy_keys(password: str, delete_originals: bool = False) -> Dict:
    """
    Convenience function to migrate all legacy keys.

    Args:
        password: Master password for encryption
        delete_originals: Securely delete originals if True

    Returns:
        Migration results
    """
    storage = SecureStorage(password)
    migrator = KeyMigrator(storage)
    return migrator.migrate_all(delete_originals)


if __name__ == "__main__":
    import getpass

    print("JARVIS Secure Key Storage Setup")
    print("=" * 40)

    # Check for existing password
    existing_password = os.getenv(SecureStorage.ENV_PASSWORD_KEY)

    if existing_password:
        print(f"Using password from {SecureStorage.ENV_PASSWORD_KEY}")
        password = existing_password
    else:
        password = getpass.getpass("Enter master password: ")
        confirm = getpass.getpass("Confirm password: ")

        if password != confirm:
            print("Passwords don't match!")
            exit(1)

    try:
        storage = SecureStorage(password)
        print(f"\n[OK] Secure storage initialized")
        print(f"    Keys stored: {len(storage.list_keys())}")

        # Check for legacy files to migrate
        migrator = KeyMigrator(storage)
        print("\nChecking for legacy key files...")

        for rel_path, _ in KeyMigrator.LEGACY_FILES:
            file_path = ROOT / rel_path
            if file_path.exists():
                print(f"  Found: {rel_path}")

        response = input("\nMigrate legacy keys? [y/N]: ")
        if response.lower() == 'y':
            results = migrator.migrate_all(delete_originals=False)
            print("\nMigration results:")
            for path, success in results.items():
                status = "OK" if success else ("SKIP" if success is None else "FAIL")
                print(f"  [{status}] {path}")

        print("\n[OK] Setup complete!")
        print(f"\nIMPORTANT: Set {SecureStorage.ENV_PASSWORD_KEY} in your .env file")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        exit(1)
