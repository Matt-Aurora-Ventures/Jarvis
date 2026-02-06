"""
Secure Key Vault

Centralized secure storage for API keys, private keys, and secrets.
Uses encryption at rest with key derivation.

Prompts #171-180: Security
"""

import asyncio
import logging
import os
import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SecretMetadata:
    """Metadata for a stored secret"""
    key_id: str
    created_at: datetime
    last_accessed: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    rotation_count: int = 0
    description: str = ""


class SecureStorage:
    """
    Secure encrypted storage for secrets

    Uses AES-256 encryption with PBKDF2 key derivation.
    """

    def __init__(self, storage_path: str = "secrets/vault.enc"):
        self.storage_path = Path(storage_path)
        self.master_key = self._derive_master_key()
        self._data: Dict[str, bytes] = {}
        self._metadata: Dict[str, SecretMetadata] = {}
        self._load()

    def _derive_master_key(self) -> bytes:
        """Derive master key from environment"""
        try:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            from cryptography.hazmat.primitives import hashes

            password = os.environ.get("JARVIS_MASTER_KEY", "")
            if not password:
                # SECURITY: Never use fallback in production
                # Require explicit JARVIS_MASTER_KEY environment variable
                raise ValueError(
                    "JARVIS_MASTER_KEY environment variable must be set. "
                    "Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )

            # Validate minimum key length (32 characters = ~192 bits of entropy)
            if len(password) < 32:
                logger.warning(
                    f"JARVIS_MASTER_KEY is only {len(password)} characters. "
                    "Recommended minimum: 32 characters for production security."
                )

            salt = os.environ.get("JARVIS_KEY_SALT", "jarvis_vault_salt").encode()

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )

            return kdf.derive(password.encode())

        except ImportError:
            logger.error("cryptography package required for secure key derivation")
            raise RuntimeError(
                "Missing required package 'cryptography'. "
                "Install with: pip install cryptography"
            )

    def _encrypt(self, data: bytes) -> bytes:
        """Encrypt data"""
        try:
            from cryptography.fernet import Fernet
            import base64

            fernet = Fernet(base64.urlsafe_b64encode(self.master_key))
            return fernet.encrypt(data)
        except ImportError:
            logger.error("cryptography not installed")
            raise RuntimeError("Encryption not available")

    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt data"""
        try:
            from cryptography.fernet import Fernet
            import base64

            fernet = Fernet(base64.urlsafe_b64encode(self.master_key))
            return fernet.decrypt(data)
        except ImportError:
            logger.error("cryptography not installed")
            raise RuntimeError("Decryption not available")

    def _load(self):
        """Load encrypted vault from disk"""
        if not self.storage_path.exists():
            return

        try:
            with open(self.storage_path, "rb") as f:
                encrypted_data = f.read()

            if not encrypted_data:
                return

            decrypted = self._decrypt(encrypted_data)
            vault_data = json.loads(decrypted.decode())

            self._data = {
                k: bytes.fromhex(v) for k, v in vault_data.get("secrets", {}).items()
            }

            for k, v in vault_data.get("metadata", {}).items():
                self._metadata[k] = SecretMetadata(
                    key_id=k,
                    created_at=datetime.fromisoformat(v["created_at"]),
                    last_accessed=datetime.fromisoformat(v["last_accessed"]) if v.get("last_accessed") else None,
                    expires_at=datetime.fromisoformat(v["expires_at"]) if v.get("expires_at") else None,
                    rotation_count=v.get("rotation_count", 0),
                    description=v.get("description", "")
                )

            logger.info(f"Loaded {len(self._data)} secrets from vault")

        except Exception as e:
            logger.error(f"Failed to load vault: {e}")

    def _save(self):
        """Save encrypted vault to disk"""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            vault_data = {
                "secrets": {k: v.hex() for k, v in self._data.items()},
                "metadata": {
                    k: {
                        "created_at": v.created_at.isoformat(),
                        "last_accessed": v.last_accessed.isoformat() if v.last_accessed else None,
                        "expires_at": v.expires_at.isoformat() if v.expires_at else None,
                        "rotation_count": v.rotation_count,
                        "description": v.description
                    }
                    for k, v in self._metadata.items()
                }
            }

            encrypted = self._encrypt(json.dumps(vault_data).encode())

            with open(self.storage_path, "wb") as f:
                f.write(encrypted)

            logger.debug("Vault saved successfully")

        except Exception as e:
            logger.error(f"Failed to save vault: {e}")
            raise

    def store(
        self,
        key_id: str,
        secret: bytes,
        description: str = "",
        expires_at: Optional[datetime] = None
    ):
        """Store a secret"""
        self._data[key_id] = secret
        self._metadata[key_id] = SecretMetadata(
            key_id=key_id,
            created_at=datetime.now(),
            expires_at=expires_at,
            description=description
        )
        self._save()
        logger.info(f"Stored secret: {key_id}")

    def retrieve(self, key_id: str) -> Optional[bytes]:
        """Retrieve a secret"""
        if key_id not in self._data:
            return None

        # Check expiration
        metadata = self._metadata.get(key_id)
        if metadata and metadata.expires_at and datetime.now() > metadata.expires_at:
            logger.warning(f"Secret {key_id} has expired")
            return None

        # Update last accessed
        if metadata:
            metadata.last_accessed = datetime.now()
            self._save()

        return self._data[key_id]

    def delete(self, key_id: str) -> bool:
        """Delete a secret"""
        if key_id in self._data:
            del self._data[key_id]
            if key_id in self._metadata:
                del self._metadata[key_id]
            self._save()
            logger.info(f"Deleted secret: {key_id}")
            return True
        return False

    def rotate(self, key_id: str, new_secret: bytes) -> bool:
        """Rotate a secret"""
        if key_id not in self._data:
            return False

        metadata = self._metadata.get(key_id)
        if metadata:
            metadata.rotation_count += 1

        self._data[key_id] = new_secret
        self._save()
        logger.info(f"Rotated secret: {key_id}")
        return True

    def list_keys(self) -> Dict[str, SecretMetadata]:
        """List all stored key IDs with metadata"""
        return self._metadata.copy()


class KeyVault:
    """
    High-level key vault for managing secrets

    Provides typed access to common secret types.
    """

    def __init__(self, storage_path: str = "secrets/vault.enc"):
        self.storage = SecureStorage(storage_path)

    def store_api_key(
        self,
        service: str,
        api_key: str,
        description: str = ""
    ):
        """Store an API key"""
        key_id = f"api_key:{service}"
        self.storage.store(
            key_id=key_id,
            secret=api_key.encode(),
            description=description or f"API key for {service}"
        )

    def get_api_key(self, service: str) -> Optional[str]:
        """Get an API key"""
        key_id = f"api_key:{service}"
        data = self.storage.retrieve(key_id)
        return data.decode() if data else None

    def store_private_key(
        self,
        wallet_id: str,
        private_key: bytes,
        description: str = ""
    ):
        """Store a wallet private key"""
        key_id = f"wallet:{wallet_id}"
        self.storage.store(
            key_id=key_id,
            secret=private_key,
            description=description or f"Private key for wallet {wallet_id}"
        )

    def get_private_key(self, wallet_id: str) -> Optional[bytes]:
        """Get a wallet private key"""
        key_id = f"wallet:{wallet_id}"
        return self.storage.retrieve(key_id)

    def store_secret(
        self,
        name: str,
        value: str,
        description: str = ""
    ):
        """Store a generic secret"""
        key_id = f"secret:{name}"
        self.storage.store(
            key_id=key_id,
            secret=value.encode(),
            description=description
        )

    def get_secret(self, name: str) -> Optional[str]:
        """Get a generic secret"""
        key_id = f"secret:{name}"
        data = self.storage.retrieve(key_id)
        return data.decode() if data else None

    def rotate_api_key(self, service: str, new_key: str) -> bool:
        """Rotate an API key"""
        key_id = f"api_key:{service}"
        return self.storage.rotate(key_id, new_key.encode())

    def delete_key(self, key_id: str) -> bool:
        """Delete a key"""
        return self.storage.delete(key_id)

    def list_all(self) -> Dict[str, SecretMetadata]:
        """List all stored secrets"""
        return self.storage.list_keys()

    def get_stats(self) -> Dict[str, Any]:
        """Get vault statistics"""
        all_keys = self.list_all()

        api_keys = [k for k in all_keys if k.startswith("api_key:")]
        wallets = [k for k in all_keys if k.startswith("wallet:")]
        secrets = [k for k in all_keys if k.startswith("secret:")]

        return {
            "total_secrets": len(all_keys),
            "api_keys": len(api_keys),
            "wallets": len(wallets),
            "other_secrets": len(secrets)
        }


# Singleton instance
_vault_instance: Optional[KeyVault] = None


def get_key_vault() -> KeyVault:
    """Get key vault singleton"""
    global _vault_instance

    if _vault_instance is None:
        _vault_instance = KeyVault()

    return _vault_instance


# Testing
if __name__ == "__main__":
    # Generate a secure test key for demonstration
    import secrets
    test_master_key = secrets.token_urlsafe(32)
    os.environ["JARVIS_MASTER_KEY"] = test_master_key

    vault = KeyVault("test_vault.enc")

    # Store some test secrets
    vault.store_api_key("twitter", "test_twitter_key_12345")
    vault.store_api_key("telegram", "test_telegram_token")
    vault.store_secret("database_url", "postgresql://localhost/jarvis")

    # Retrieve
    twitter_key = vault.get_api_key("twitter")
    print(f"Twitter API key: {twitter_key}")

    # List all
    print(f"\nAll secrets: {vault.list_all()}")
    print(f"\nStats: {vault.get_stats()}")

    # Clean up
    os.remove("test_vault.enc")
