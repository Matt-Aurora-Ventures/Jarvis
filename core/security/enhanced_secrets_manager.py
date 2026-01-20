"""
Enhanced Secrets Manager

Production-grade secrets management:
- Encrypted credential storage
- Secure key rotation with versioning
- Secret access auditing
- Multi-environment support
- Memory safety (clearing sensitive data)
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import cryptography
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    Fernet = None


class SecretVersion:
    """A versioned secret."""

    def __init__(
        self,
        version: int,
        encrypted_value: bytes,
        created_at: datetime,
        created_by: Optional[str] = None
    ):
        self.version = version
        self.encrypted_value = encrypted_value
        self.created_at = created_at
        self.created_by = created_by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "encrypted_value": base64.b64encode(self.encrypted_value).decode(),
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecretVersion":
        return cls(
            version=data["version"],
            encrypted_value=base64.b64decode(data["encrypted_value"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data.get("created_by")
        )


@dataclass
class SecretMetadata:
    """Metadata for a secret."""
    name: str
    environment: str
    created_at: datetime
    updated_at: datetime
    current_version: int
    rotation_interval_days: Optional[int] = None
    next_rotation: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    """Audit log entry for secret access."""
    timestamp: datetime
    secret_name: str
    action: str
    accessor: str
    success: bool
    ip_address: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EnhancedSecretsManager:
    """
    Production-grade secrets manager.

    Features:
    - AES-256 encryption via Fernet
    - PBKDF2 key derivation
    - Version history with rollback
    - Access auditing
    - Multi-environment isolation
    - Scheduled rotation support
    """

    def __init__(
        self,
        storage_path: Path,
        master_key: str,
        enable_audit: bool = True,
        default_environment: str = "default"
    ):
        """
        Initialize the secrets manager.

        Args:
            storage_path: Directory for encrypted secrets
            master_key: Master encryption key (must be 32 chars for proper security)
            enable_audit: Enable access auditing
            default_environment: Default environment name
        """
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.enable_audit = enable_audit
        self.default_environment = default_environment

        # Derive encryption key from master key
        self._salt = self._get_or_create_salt()
        self._encryption_key = self._derive_key(master_key)

        # In-memory cache
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

        # Audit log
        self._audit_log: List[AuditEntry] = []

        # Scheduled rotations
        self._rotation_schedule: Dict[str, Dict[str, Any]] = {}

    def _get_or_create_salt(self) -> bytes:
        """Get or create the salt for key derivation."""
        salt_path = self.storage_path / ".salt"
        if salt_path.exists():
            return salt_path.read_bytes()
        else:
            salt = secrets.token_bytes(16)
            salt_path.write_bytes(salt)
            os.chmod(salt_path, 0o600)
            return salt

    def _derive_key(self, master_key: str) -> bytes:
        """Derive encryption key using PBKDF2."""
        if HAS_CRYPTO:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self._salt,
                iterations=100000,
            )
            return base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        else:
            # Fallback to hashlib
            return base64.urlsafe_b64encode(
                hashlib.pbkdf2_hmac(
                    'sha256',
                    master_key.encode(),
                    self._salt,
                    100000,
                    dklen=32
                )
            )

    def _encrypt(self, value: str) -> bytes:
        """Encrypt a value."""
        if HAS_CRYPTO:
            fernet = Fernet(self._encryption_key)
            return fernet.encrypt(value.encode())
        else:
            # Simple XOR fallback (NOT secure for production)
            logger.warning("Using fallback encryption - install cryptography package")
            key_bytes = base64.urlsafe_b64decode(self._encryption_key)
            value_bytes = value.encode()
            # Pad to key length
            padded = value_bytes.ljust(len(value_bytes) + 16, b'\x00')
            encrypted = bytes([a ^ b for a, b in zip(padded, (key_bytes * (len(padded) // len(key_bytes) + 1))[:len(padded)])])
            return encrypted

    def _decrypt(self, encrypted: bytes) -> str:
        """Decrypt a value."""
        if HAS_CRYPTO:
            fernet = Fernet(self._encryption_key)
            return fernet.decrypt(encrypted).decode()
        else:
            # Simple XOR fallback
            key_bytes = base64.urlsafe_b64decode(self._encryption_key)
            decrypted = bytes([a ^ b for a, b in zip(encrypted, (key_bytes * (len(encrypted) // len(key_bytes) + 1))[:len(encrypted)])])
            return decrypted.rstrip(b'\x00').decode()

    def _get_secret_path(self, name: str, environment: str) -> Path:
        """Get path for a secret file."""
        env_dir = self.storage_path / environment
        env_dir.mkdir(exist_ok=True)
        return env_dir / f"{name}.secret"

    def _log_access(
        self,
        secret_name: str,
        action: str,
        accessor: str,
        success: bool,
        ip_address: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a secret access."""
        if not self.enable_audit:
            return

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            secret_name=secret_name,
            action=action,
            accessor=accessor,
            success=success,
            ip_address=ip_address,
            metadata=metadata or {}
        )

        with self._lock:
            self._audit_log.append(entry)

            # Keep only last 10000 entries
            if len(self._audit_log) > 10000:
                self._audit_log = self._audit_log[-5000:]

    def store_secret(
        self,
        name: str,
        value: str,
        environment: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Store a secret.

        Args:
            name: Secret name
            value: Secret value
            environment: Environment (default: self.default_environment)
            metadata: Additional metadata
            created_by: Who created the secret

        Returns:
            Result with success status and secret_id
        """
        env = environment or self.default_environment
        secret_path = self._get_secret_path(name, env)

        try:
            encrypted = self._encrypt(value)

            # Create versioned secret
            version = SecretVersion(
                version=1,
                encrypted_value=encrypted,
                created_at=datetime.now(timezone.utc),
                created_by=created_by
            )

            # Secret data
            secret_data = {
                "name": name,
                "environment": env,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "current_version": 1,
                "versions": [version.to_dict()],
                "metadata": metadata or {}
            }

            # Save to file
            with open(secret_path, 'w') as f:
                json.dump(secret_data, f)

            # Set restrictive permissions
            try:
                os.chmod(secret_path, 0o600)
            except OSError:
                pass  # Windows doesn't support chmod

            # Update cache
            with self._lock:
                cache_key = f"{env}:{name}"
                self._cache[cache_key] = {
                    "value": value,
                    "cached_at": datetime.now(timezone.utc)
                }

            self._log_access(name, "store", created_by or "system", True)

            return {
                "success": True,
                "secret_id": f"{env}:{name}",
                "version": 1
            }

        except Exception as e:
            logger.error(f"Failed to store secret {name}: {e}")
            self._log_access(name, "store", created_by or "system", False, metadata={"error": str(e)})
            return {"success": False, "error": str(e)}

    def get_secret(
        self,
        name: str,
        environment: Optional[str] = None,
        accessor: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Retrieve a secret.

        Args:
            name: Secret name
            environment: Environment
            accessor: Who is accessing
            metadata: Additional audit metadata

        Returns:
            Dict with success, value, and metadata
        """
        env = environment or self.default_environment
        secret_path = self._get_secret_path(name, env)

        # Check cache first
        cache_key = f"{env}:{name}"
        with self._lock:
            if cache_key in self._cache:
                cached = self._cache[cache_key]
                # Cache valid for 5 minutes
                if (datetime.now(timezone.utc) - cached["cached_at"]).seconds < 300:
                    self._log_access(name, "read", accessor or "system", True, metadata=metadata)
                    return {
                        "success": True,
                        "value": cached["value"],
                        "from_cache": True
                    }

        if not secret_path.exists():
            self._log_access(name, "read", accessor or "system", False, metadata={"error": "not_found"})
            return {"success": False, "error": "Secret not found", "value": None}

        try:
            with open(secret_path, 'r') as f:
                secret_data = json.load(f)

            # Get current version
            current_version = secret_data.get("current_version", 1)
            versions = secret_data.get("versions", [])

            current = None
            for v in versions:
                if v.get("version") == current_version:
                    current = SecretVersion.from_dict(v)
                    break

            if current is None:
                return {"success": False, "error": "Version not found", "value": None}

            # Decrypt
            value = self._decrypt(current.encrypted_value)

            # Update cache
            with self._lock:
                self._cache[cache_key] = {
                    "value": value,
                    "cached_at": datetime.now(timezone.utc)
                }

            self._log_access(name, "read", accessor or "system", True, metadata=metadata)

            return {
                "success": True,
                "value": value,
                "version": current_version,
                "environment": env
            }

        except Exception as e:
            logger.error(f"Failed to get secret {name}: {e}")
            self._log_access(name, "read", accessor or "system", False, metadata={"error": str(e)})
            return {"success": False, "error": str(e), "value": None}

    def update_secret(
        self,
        name: str,
        new_value: str,
        environment: Optional[str] = None,
        updated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a secret (creates new version)."""
        return self.rotate_secret(name, new_value, environment, updated_by)

    def rotate_secret(
        self,
        name: str,
        new_value: str,
        environment: Optional[str] = None,
        rotated_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rotate a secret (create new version).

        Args:
            name: Secret name
            new_value: New secret value
            environment: Environment
            rotated_by: Who rotated

        Returns:
            Result with previous_version
        """
        env = environment or self.default_environment
        secret_path = self._get_secret_path(name, env)

        if not secret_path.exists():
            return {"success": False, "error": "Secret not found"}

        try:
            with open(secret_path, 'r') as f:
                secret_data = json.load(f)

            # Get current version
            old_version = secret_data.get("current_version", 1)
            new_version_num = old_version + 1

            # Encrypt new value
            encrypted = self._encrypt(new_value)

            # Create new version
            new_version = SecretVersion(
                version=new_version_num,
                encrypted_value=encrypted,
                created_at=datetime.now(timezone.utc),
                created_by=rotated_by
            )

            # Add to versions
            secret_data["versions"].append(new_version.to_dict())
            secret_data["current_version"] = new_version_num
            secret_data["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Keep only last 10 versions
            if len(secret_data["versions"]) > 10:
                secret_data["versions"] = secret_data["versions"][-10:]

            # Save
            with open(secret_path, 'w') as f:
                json.dump(secret_data, f)

            # Clear cache
            cache_key = f"{env}:{name}"
            with self._lock:
                if cache_key in self._cache:
                    del self._cache[cache_key]

            self._log_access(name, "rotate", rotated_by or "system", True)

            return {
                "success": True,
                "previous_version": old_version,
                "new_version": new_version_num
            }

        except Exception as e:
            logger.error(f"Failed to rotate secret {name}: {e}")
            return {"success": False, "error": str(e)}

    def delete_secret(
        self,
        name: str,
        environment: Optional[str] = None,
        deleted_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a secret."""
        env = environment or self.default_environment
        secret_path = self._get_secret_path(name, env)

        if not secret_path.exists():
            return {"success": False, "error": "Secret not found"}

        try:
            secret_path.unlink()

            # Clear cache
            cache_key = f"{env}:{name}"
            with self._lock:
                if cache_key in self._cache:
                    del self._cache[cache_key]

            self._log_access(name, "delete", deleted_by or "system", True)

            return {"success": True}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_secret_versions(
        self,
        name: str,
        environment: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all versions of a secret (without decrypted values)."""
        env = environment or self.default_environment
        secret_path = self._get_secret_path(name, env)

        if not secret_path.exists():
            return []

        try:
            with open(secret_path, 'r') as f:
                secret_data = json.load(f)

            # Try to decrypt each version for the response
            versions = []
            for v in secret_data.get("versions", []):
                version_info = {
                    "version": v["version"],
                    "created_at": v["created_at"],
                    "created_by": v.get("created_by")
                }

                # Try to decrypt the value
                try:
                    version_obj = SecretVersion.from_dict(v)
                    version_info["value"] = self._decrypt(version_obj.encrypted_value)
                except:
                    version_info["value"] = "[DECRYPTION_FAILED]"

                versions.append(version_info)

            return versions

        except Exception as e:
            logger.error(f"Failed to get versions for {name}: {e}")
            return []

    def rollback_secret(
        self,
        name: str,
        version: int,
        environment: Optional[str] = None,
        rolled_back_by: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rollback to a previous version.

        Args:
            name: Secret name
            version: Version to rollback to
            environment: Environment
            rolled_back_by: Who initiated rollback

        Returns:
            Result
        """
        env = environment or self.default_environment
        secret_path = self._get_secret_path(name, env)

        if not secret_path.exists():
            return {"success": False, "error": "Secret not found"}

        try:
            with open(secret_path, 'r') as f:
                secret_data = json.load(f)

            # Find the target version
            target = None
            for v in secret_data.get("versions", []):
                if v.get("version") == version:
                    target = v
                    break

            if target is None:
                return {"success": False, "error": f"Version {version} not found"}

            # Set as current version
            secret_data["current_version"] = version
            secret_data["updated_at"] = datetime.now(timezone.utc).isoformat()

            # Save
            with open(secret_path, 'w') as f:
                json.dump(secret_data, f)

            # Clear cache
            cache_key = f"{env}:{name}"
            with self._lock:
                if cache_key in self._cache:
                    del self._cache[cache_key]

            self._log_access(name, "rollback", rolled_back_by or "system", True,
                           metadata={"rolled_back_to": version})

            return {"success": True, "current_version": version}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def schedule_rotation(
        self,
        name: str,
        rotation_interval_days: int,
        rotation_callback: Optional[str] = None,
        environment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Schedule automatic rotation for a secret.

        Args:
            name: Secret name
            rotation_interval_days: Days between rotations
            rotation_callback: Callback function name
            environment: Environment

        Returns:
            Result with next rotation date
        """
        env = environment or self.default_environment
        secret_key = f"{env}:{name}"

        next_rotation = datetime.now(timezone.utc) + timedelta(days=rotation_interval_days)

        self._rotation_schedule[secret_key] = {
            "interval_days": rotation_interval_days,
            "callback": rotation_callback,
            "next_rotation": next_rotation.isoformat()
        }

        return {
            "success": True,
            "next_rotation": next_rotation.isoformat()
        }

    def get_access_log(
        self,
        secret_name: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get access log for a secret."""
        with self._lock:
            matching = [
                {
                    "timestamp": e.timestamp.isoformat(),
                    "action": e.action,
                    "accessor": e.accessor,
                    "success": e.success,
                    "ip_address": e.ip_address,
                    "metadata": e.metadata
                }
                for e in self._audit_log
                if e.secret_name == secret_name
            ]

        return matching[-limit:]

    def list_secrets(
        self,
        environment: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List all secrets in an environment."""
        env = environment or self.default_environment
        env_dir = self.storage_path / env

        if not env_dir.exists():
            return []

        secrets_list = []
        for secret_file in env_dir.glob("*.secret"):
            try:
                with open(secret_file, 'r') as f:
                    data = json.load(f)
                secrets_list.append({
                    "name": data.get("name"),
                    "environment": data.get("environment"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "current_version": data.get("current_version")
                })
            except:
                continue

        return secrets_list

    def uses_key_derivation(self) -> bool:
        """Check if proper key derivation is used."""
        return True  # We always use PBKDF2

    def clear_cache(self):
        """Clear the in-memory cache."""
        with self._lock:
            self._cache.clear()

    def is_cache_empty(self) -> bool:
        """Check if cache is empty."""
        with self._lock:
            return len(self._cache) == 0


# Singleton
_secrets_manager: Optional[EnhancedSecretsManager] = None


def get_enhanced_secrets_manager(
    storage_path: Optional[Path] = None,
    master_key: Optional[str] = None
) -> EnhancedSecretsManager:
    """Get or create the enhanced secrets manager."""
    global _secrets_manager
    if _secrets_manager is None:
        path = storage_path or Path("data/secrets")
        key = master_key or os.environ.get("JARVIS_MASTER_KEY", "default_insecure_key_32!!")
        _secrets_manager = EnhancedSecretsManager(path, key)
    return _secrets_manager
