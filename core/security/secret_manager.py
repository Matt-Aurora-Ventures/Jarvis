"""
JARVIS Secret Management

Provides secure secret retrieval from multiple backends:
- Environment variables
- AWS Secrets Manager
- HashiCorp Vault
- Encrypted local files
"""
import os
import json
from typing import Optional, Dict, Any, Protocol
from abc import abstractmethod
from dataclasses import dataclass
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class SecretBackend(Protocol):
    """Protocol for secret backends."""

    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret by key."""
        ...

    @abstractmethod
    def get_secret_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a JSON secret."""
        ...


class EnvironmentBackend:
    """Backend using environment variables."""

    def get_secret(self, key: str) -> Optional[str]:
        """Get secret from environment variable."""
        return os.getenv(key)

    def get_secret_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON secret from environment variable."""
        value = os.getenv(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse {key} as JSON")
        return None


class AWSSecretsManagerBackend:
    """Backend using AWS Secrets Manager."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self._client = None

    @property
    def client(self):
        """Lazy initialize boto3 client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    'secretsmanager',
                    region_name=self.region
                )
            except ImportError:
                logger.warning("boto3 not installed, AWS Secrets Manager unavailable")
                raise
        return self._client

    def get_secret(self, key: str) -> Optional[str]:
        """Get secret from AWS Secrets Manager."""
        try:
            response = self.client.get_secret_value(SecretId=key)
            return response.get('SecretString')
        except Exception as e:
            logger.warning(f"Failed to get secret {key}: {e}")
            return None

    def get_secret_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON secret from AWS Secrets Manager."""
        secret = self.get_secret(key)
        if secret:
            try:
                return json.loads(secret)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse {key} as JSON")
        return None


class VaultBackend:
    """Backend using HashiCorp Vault."""

    def __init__(
        self,
        url: str = None,
        token: str = None,
        mount_point: str = "secret"
    ):
        self.url = url or os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.token = token or os.getenv("VAULT_TOKEN")
        self.mount_point = mount_point
        self._client = None

    @property
    def client(self):
        """Lazy initialize Vault client."""
        if self._client is None:
            try:
                import hvac
                self._client = hvac.Client(url=self.url, token=self.token)
            except ImportError:
                logger.warning("hvac not installed, Vault unavailable")
                raise
        return self._client

    def get_secret(self, key: str) -> Optional[str]:
        """Get secret from Vault."""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                mount_point=self.mount_point,
                path=key
            )
            data = response.get('data', {}).get('data', {})
            return data.get('value')
        except Exception as e:
            logger.warning(f"Failed to get secret {key}: {e}")
            return None

    def get_secret_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON secret from Vault."""
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                mount_point=self.mount_point,
                path=key
            )
            return response.get('data', {}).get('data', {})
        except Exception as e:
            logger.warning(f"Failed to get secret {key}: {e}")
            return None


class EncryptedFileBackend:
    """Backend using encrypted local files."""

    def __init__(self, path: str, encryption_key: str = None):
        from pathlib import Path
        self.path = Path(path)
        self.encryption_key = encryption_key or os.getenv("ENCRYPTION_KEY")
        self._secrets: Optional[Dict[str, str]] = None

    def _load_secrets(self) -> Dict[str, str]:
        """Load and decrypt secrets file."""
        if self._secrets is not None:
            return self._secrets

        if not self.path.exists():
            return {}

        from cryptography.fernet import Fernet

        try:
            fernet = Fernet(self.encryption_key.encode())
            encrypted = self.path.read_bytes()
            decrypted = fernet.decrypt(encrypted)
            self._secrets = json.loads(decrypted)
            return self._secrets
        except Exception as e:
            logger.error(f"Failed to load encrypted secrets: {e}")
            return {}

    def get_secret(self, key: str) -> Optional[str]:
        """Get secret from encrypted file."""
        secrets = self._load_secrets()
        return secrets.get(key)

    def get_secret_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON secret from encrypted file."""
        value = self.get_secret(key)
        if value and isinstance(value, dict):
            return value
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                pass
        return None


@dataclass
class SecretManagerConfig:
    """Configuration for secret manager."""
    backends: list  # List of backend names in priority order
    aws_region: str = "us-east-1"
    vault_url: Optional[str] = None
    encrypted_file_path: Optional[str] = None


class SecretManager:
    """
    Unified secret management with fallback backends.

    Usage:
        manager = SecretManager()

        # Get a secret
        api_key = manager.get_secret("ANTHROPIC_API_KEY")

        # Get with default
        timeout = manager.get_secret("TIMEOUT", default="30")

        # Required secret (raises if missing)
        token = manager.require_secret("TELEGRAM_BOT_TOKEN")
    """

    def __init__(self, config: SecretManagerConfig = None):
        self.config = config or SecretManagerConfig(
            backends=["environment"]  # Default to env vars only
        )
        self._backends: Dict[str, SecretBackend] = {}
        self._init_backends()

    def _init_backends(self) -> None:
        """Initialize configured backends."""
        for name in self.config.backends:
            if name == "environment":
                self._backends[name] = EnvironmentBackend()
            elif name == "aws":
                try:
                    self._backends[name] = AWSSecretsManagerBackend(
                        region=self.config.aws_region
                    )
                except ImportError:
                    logger.warning("Skipping AWS backend (boto3 not installed)")
            elif name == "vault":
                try:
                    self._backends[name] = VaultBackend(
                        url=self.config.vault_url
                    )
                except ImportError:
                    logger.warning("Skipping Vault backend (hvac not installed)")
            elif name == "encrypted_file":
                if self.config.encrypted_file_path:
                    self._backends[name] = EncryptedFileBackend(
                        path=self.config.encrypted_file_path
                    )

    def get_secret(
        self,
        key: str,
        default: Optional[str] = None
    ) -> Optional[str]:
        """
        Get a secret from configured backends.

        Tries each backend in order until a value is found.

        Args:
            key: Secret key/name
            default: Default value if not found

        Returns:
            Secret value or default
        """
        for backend in self._backends.values():
            value = backend.get_secret(key)
            if value is not None:
                return value

        return default

    def require_secret(self, key: str) -> str:
        """
        Get a required secret.

        Raises ValueError if the secret is not found.

        Args:
            key: Secret key/name

        Returns:
            Secret value

        Raises:
            ValueError: If secret is not found
        """
        value = self.get_secret(key)
        if value is None:
            raise ValueError(f"Required secret not found: {key}")
        return value

    def get_secret_json(
        self,
        key: str,
        default: Optional[Dict] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a JSON secret from configured backends."""
        for backend in self._backends.values():
            value = backend.get_secret_json(key)
            if value is not None:
                return value

        return default

    def list_backends(self) -> list:
        """List active backends."""
        return list(self._backends.keys())


# Global instance
_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """Get or create global secret manager."""
    global _secret_manager

    if _secret_manager is None:
        # Configure from environment
        backends = os.getenv("SECRET_BACKENDS", "environment").split(",")
        config = SecretManagerConfig(
            backends=[b.strip() for b in backends],
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            vault_url=os.getenv("VAULT_ADDR"),
            encrypted_file_path=os.getenv("SECRETS_FILE")
        )
        _secret_manager = SecretManager(config)

    return _secret_manager


def get_secret(key: str, default: Optional[str] = None) -> Optional[str]:
    """Convenience function to get a secret."""
    return get_secret_manager().get_secret(key, default)


def require_secret(key: str) -> str:
    """Convenience function to require a secret."""
    return get_secret_manager().require_secret(key)
