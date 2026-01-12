"""
Encryption Module - Secure storage for tokens, keys, and sensitive data.
"""

import os
import json
import base64
import hashlib
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


# === KEY DERIVATION ===

def derive_key(password: str, salt: Optional[bytes] = None) -> tuple[bytes, bytes]:
    """
    Derive encryption key from password using PBKDF2.
    Returns (key, salt).
    """
    if salt is None:
        salt = os.urandom(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,  # OWASP recommended minimum
    )

    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt


def get_machine_key() -> str:
    """
    Generate a machine-specific key based on hardware identifiers.
    Not cryptographically strong, but adds defense in depth.
    """
    import platform
    import socket

    components = [
        platform.node(),
        platform.machine(),
        platform.processor()[:20] if platform.processor() else "",
        socket.gethostname(),
    ]

    return hashlib.sha256("|".join(components).encode()).hexdigest()


# === SECURE VAULT ===

@dataclass
class VaultConfig:
    """Configuration for secure vault."""
    vault_path: Path
    password: Optional[str] = None
    use_machine_key: bool = True


class SecureVault:
    """
    Encrypted storage for sensitive data like OAuth tokens.

    Usage:
        vault = SecureVault(Path("secrets/vault.enc"))
        vault.set("twitter_oauth", {"access_token": "xxx", "secret": "yyy"})
        tokens = vault.get("twitter_oauth")
    """

    def __init__(self, vault_path: Path, password: Optional[str] = None,
                 use_machine_key: bool = True):
        self.vault_path = vault_path
        self.salt_path = vault_path.with_suffix(".salt")

        # Build password
        if password:
            self._password = password
        elif use_machine_key:
            self._password = get_machine_key()
        else:
            self._password = os.environ.get("JARVIS_VAULT_PASSWORD", "default-insecure-password")
            if self._password == "default-insecure-password":
                logger.warning("Using default vault password - set JARVIS_VAULT_PASSWORD env var")

        self._fernet: Optional[Fernet] = None
        self._data: Dict[str, Any] = {}
        self._init_vault()

    def _init_vault(self):
        """Initialize vault encryption."""
        # Load or create salt
        if self.salt_path.exists():
            with open(self.salt_path, "rb") as f:
                salt = f.read()
        else:
            salt = None

        # Derive key
        key, salt = derive_key(self._password, salt)

        # Save salt if new
        if not self.salt_path.exists():
            self.salt_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.salt_path, "wb") as f:
                f.write(salt)

        self._fernet = Fernet(key)

        # Load existing data
        if self.vault_path.exists():
            self._load()

    def _load(self):
        """Load and decrypt vault data."""
        try:
            with open(self.vault_path, "rb") as f:
                encrypted = f.read()

            decrypted = self._fernet.decrypt(encrypted)
            self._data = json.loads(decrypted.decode())
            logger.debug(f"Loaded vault with {len(self._data)} entries")

        except Exception as e:
            logger.error(f"Failed to load vault: {e}")
            self._data = {}

    def _save(self):
        """Encrypt and save vault data."""
        try:
            json_data = json.dumps(self._data).encode()
            encrypted = self._fernet.encrypt(json_data)

            self.vault_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.vault_path, "wb") as f:
                f.write(encrypted)

            logger.debug(f"Saved vault with {len(self._data)} entries")

        except Exception as e:
            logger.error(f"Failed to save vault: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from vault."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        """Set value in vault and save."""
        self._data[key] = value
        self._save()

    def delete(self, key: str) -> bool:
        """Delete key from vault."""
        if key in self._data:
            del self._data[key]
            self._save()
            return True
        return False

    def has(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._data

    def keys(self) -> list:
        """Get all keys."""
        return list(self._data.keys())

    def clear(self):
        """Clear all data."""
        self._data = {}
        self._save()


# === TOKEN MANAGER ===

class TokenManager:
    """
    Manage encrypted OAuth and API tokens.

    Usage:
        tokens = TokenManager()
        tokens.store_oauth("twitter", "jarvis_lifeos", {
            "access_token": "xxx",
            "access_token_secret": "yyy"
        })
        creds = tokens.get_oauth("twitter", "jarvis_lifeos")
    """

    def __init__(self, vault_path: Optional[Path] = None):
        default_path = Path(__file__).parent.parent / "secrets" / "tokens.vault"
        self.vault = SecureVault(vault_path or default_path)

    def store_oauth(self, service: str, account: str, tokens: Dict[str, str]):
        """Store OAuth tokens for a service/account."""
        key = f"oauth:{service}:{account}"
        self.vault.set(key, {
            "tokens": tokens,
            "stored_at": self._now(),
        })
        logger.info(f"Stored OAuth tokens for {service}/{account}")

    def get_oauth(self, service: str, account: str) -> Optional[Dict[str, str]]:
        """Get OAuth tokens for a service/account."""
        key = f"oauth:{service}:{account}"
        data = self.vault.get(key)
        if data:
            return data.get("tokens")
        return None

    def store_api_key(self, service: str, api_key: str, metadata: Dict = None):
        """Store API key for a service."""
        key = f"api_key:{service}"
        self.vault.set(key, {
            "api_key": api_key,
            "metadata": metadata or {},
            "stored_at": self._now(),
        })
        logger.info(f"Stored API key for {service}")

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for a service."""
        key = f"api_key:{service}"
        data = self.vault.get(key)
        if data:
            return data.get("api_key")
        return None

    def rotate_token(self, service: str, account: str, new_tokens: Dict[str, str]):
        """Rotate tokens and keep old ones as backup."""
        key = f"oauth:{service}:{account}"
        old_data = self.vault.get(key)

        # Store old tokens as backup
        if old_data:
            backup_key = f"oauth_backup:{service}:{account}"
            self.vault.set(backup_key, old_data)

        # Store new tokens
        self.store_oauth(service, account, new_tokens)
        logger.info(f"Rotated OAuth tokens for {service}/{account}")

    def list_credentials(self) -> Dict[str, list]:
        """List all stored credentials by type."""
        result = {"oauth": [], "api_keys": []}

        for key in self.vault.keys():
            if key.startswith("oauth:") and not key.startswith("oauth_backup:"):
                parts = key.split(":")
                if len(parts) >= 3:
                    result["oauth"].append(f"{parts[1]}/{parts[2]}")
            elif key.startswith("api_key:"):
                result["api_keys"].append(key.replace("api_key:", ""))

        return result

    def _now(self) -> str:
        """Get current timestamp."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


# === SINGLETON INSTANCES ===

_token_manager: Optional[TokenManager] = None

def get_token_manager() -> TokenManager:
    """Get singleton token manager."""
    global _token_manager
    if _token_manager is None:
        _token_manager = TokenManager()
    return _token_manager


# === CONVENIENCE FUNCTIONS ===

def encrypt_string(plaintext: str, password: Optional[str] = None) -> str:
    """Encrypt a string and return base64-encoded result."""
    if password:
        key, salt = derive_key(password)
    else:
        key, salt = derive_key(get_machine_key())

    fernet = Fernet(key)
    encrypted = fernet.encrypt(plaintext.encode())

    # Combine salt and encrypted data
    combined = salt + encrypted
    return base64.urlsafe_b64encode(combined).decode()


def decrypt_string(encrypted: str, password: Optional[str] = None) -> str:
    """Decrypt a base64-encoded encrypted string."""
    combined = base64.urlsafe_b64decode(encrypted.encode())

    # Extract salt (first 16 bytes) and encrypted data
    salt = combined[:16]
    encrypted_data = combined[16:]

    if password:
        key, _ = derive_key(password, salt)
    else:
        key, _ = derive_key(get_machine_key(), salt)

    fernet = Fernet(key)
    decrypted = fernet.decrypt(encrypted_data)
    return decrypted.decode()


# === MIGRATION HELPER ===

def migrate_env_to_vault(env_file: Path, vault: SecureVault,
                         keys_to_migrate: list[str]):
    """
    Migrate secrets from .env file to encrypted vault.

    Usage:
        migrate_env_to_vault(
            Path(".env"),
            vault,
            ["TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET"]
        )
    """
    if not env_file.exists():
        logger.warning(f"Env file not found: {env_file}")
        return

    migrated = []

    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"\'')

            if key in keys_to_migrate:
                vault.set(f"env:{key}", value)
                migrated.append(key)

    logger.info(f"Migrated {len(migrated)} keys to vault: {migrated}")
    return migrated
