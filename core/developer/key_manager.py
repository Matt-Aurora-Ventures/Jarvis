"""
API Key Management

Manage API keys for developer access with scopes and rate limits.

Prompts #61-64: Developer API Keys
"""

import asyncio
import hashlib
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
import json

logger = logging.getLogger(__name__)


class KeyScope(str, Enum):
    """API key permission scopes"""
    READ_PORTFOLIO = "read:portfolio"
    WRITE_PORTFOLIO = "write:portfolio"
    READ_TRADES = "read:trades"
    WRITE_TRADES = "write:trades"
    READ_SIGNALS = "read:signals"
    READ_WHALES = "read:whales"
    READ_ALERTS = "read:alerts"
    WRITE_ALERTS = "write:alerts"
    READ_STAKING = "read:staking"
    ADMIN = "admin"


# Scope groups for convenience
SCOPE_GROUPS = {
    "read_only": [
        KeyScope.READ_PORTFOLIO,
        KeyScope.READ_TRADES,
        KeyScope.READ_SIGNALS,
        KeyScope.READ_WHALES,
        KeyScope.READ_ALERTS,
        KeyScope.READ_STAKING,
    ],
    "trading": [
        KeyScope.READ_PORTFOLIO,
        KeyScope.WRITE_PORTFOLIO,
        KeyScope.READ_TRADES,
        KeyScope.WRITE_TRADES,
        KeyScope.READ_SIGNALS,
    ],
    "full": list(KeyScope),
}


@dataclass
class APIKey:
    """An API key"""
    key_id: str
    user_id: str
    name: str
    key_hash: str               # Hashed API key (never store plain)
    key_prefix: str             # First 8 chars for identification
    secret_hash: Optional[str] = None  # Hashed secret for signing
    scopes: List[KeyScope] = field(default_factory=list)
    rate_limit_per_minute: int = 60
    rate_limit_per_day: int = 10000
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used_at: Optional[datetime] = None
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired

    def has_scope(self, scope: KeyScope) -> bool:
        """Check if key has a specific scope"""
        if KeyScope.ADMIN in self.scopes:
            return True
        return scope in self.scopes

    def has_any_scope(self, scopes: List[KeyScope]) -> bool:
        """Check if key has any of the specified scopes"""
        return any(self.has_scope(s) for s in scopes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scopes": [s.value for s in self.scopes],
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "rate_limit_per_day": self.rate_limit_per_day,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
            "is_valid": self.is_valid
        }


@dataclass
class KeyUsageStats:
    """Usage statistics for an API key"""
    key_id: str
    requests_today: int = 0
    requests_this_minute: int = 0
    minute_reset: datetime = field(default_factory=datetime.utcnow)
    day_reset: datetime = field(default_factory=datetime.utcnow)
    total_requests: int = 0
    total_errors: int = 0


class APIKeyManager:
    """
    Manages API keys for developer access.

    Features:
    - Key generation with secure hashing
    - Scope-based permissions
    - Rate limiting per key
    - Key rotation support
    """

    KEY_PREFIX_LENGTH = 8
    KEY_LENGTH = 32
    SECRET_LENGTH = 48

    def __init__(self, storage_path: str = "data/api_keys.json"):
        self.storage_path = storage_path
        self._keys: Dict[str, APIKey] = {}
        self._key_lookup: Dict[str, str] = {}  # hash -> key_id
        self._usage: Dict[str, KeyUsageStats] = {}
        self._load()

    def _load(self):
        """Load keys from storage"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                for item in data.get("keys", []):
                    key = APIKey(
                        key_id=item["key_id"],
                        user_id=item["user_id"],
                        name=item["name"],
                        key_hash=item["key_hash"],
                        key_prefix=item["key_prefix"],
                        secret_hash=item.get("secret_hash"),
                        scopes=[KeyScope(s) for s in item.get("scopes", [])],
                        rate_limit_per_minute=item.get("rate_limit_per_minute", 60),
                        rate_limit_per_day=item.get("rate_limit_per_day", 10000),
                        expires_at=(
                            datetime.fromisoformat(item["expires_at"])
                            if item.get("expires_at") else None
                        ),
                        created_at=datetime.fromisoformat(item["created_at"]),
                        is_active=item.get("is_active", True)
                    )
                    self._keys[key.key_id] = key
                    self._key_lookup[key.key_hash] = key.key_id
        except Exception as e:
            logger.error(f"Failed to load API keys: {e}")

    def _save(self):
        """Save keys to storage"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = {
                "keys": [
                    {
                        "key_id": k.key_id,
                        "user_id": k.user_id,
                        "name": k.name,
                        "key_hash": k.key_hash,
                        "key_prefix": k.key_prefix,
                        "secret_hash": k.secret_hash,
                        "scopes": [s.value for s in k.scopes],
                        "rate_limit_per_minute": k.rate_limit_per_minute,
                        "rate_limit_per_day": k.rate_limit_per_day,
                        "expires_at": k.expires_at.isoformat() if k.expires_at else None,
                        "created_at": k.created_at.isoformat(),
                        "is_active": k.is_active
                    }
                    for k in self._keys.values()
                ]
            }
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save API keys: {e}")

    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash an API key using SHA-256"""
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _generate_key() -> str:
        """Generate a secure random API key"""
        return secrets.token_urlsafe(APIKeyManager.KEY_LENGTH)

    @staticmethod
    def _generate_secret() -> str:
        """Generate a secure random API secret"""
        return secrets.token_urlsafe(APIKeyManager.SECRET_LENGTH)

    async def create_key(
        self,
        user_id: str,
        name: str,
        scopes: Optional[List[KeyScope]] = None,
        rate_limit_per_minute: int = 60,
        rate_limit_per_day: int = 10000,
        expires_days: Optional[int] = None,
        with_secret: bool = False
    ) -> Dict[str, str]:
        """
        Create a new API key.

        Returns the plain key (and secret if requested) - these are not stored!
        """
        # Generate key
        plain_key = self._generate_key()
        key_hash = self._hash_key(plain_key)
        key_prefix = plain_key[:self.KEY_PREFIX_LENGTH]

        # Generate secret if requested
        plain_secret = None
        secret_hash = None
        if with_secret:
            plain_secret = self._generate_secret()
            secret_hash = self._hash_key(plain_secret)

        # Calculate expiration
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)

        # Create key object
        key_id = f"key_{secrets.token_hex(8)}"
        api_key = APIKey(
            key_id=key_id,
            user_id=user_id,
            name=name,
            key_hash=key_hash,
            key_prefix=key_prefix,
            secret_hash=secret_hash,
            scopes=scopes or SCOPE_GROUPS["read_only"],
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_day=rate_limit_per_day,
            expires_at=expires_at
        )

        self._keys[key_id] = api_key
        self._key_lookup[key_hash] = key_id
        self._save()

        logger.info(f"Created API key {key_id} for user {user_id}")

        result = {
            "key_id": key_id,
            "api_key": plain_key,
            "key_prefix": key_prefix
        }
        if plain_secret:
            result["api_secret"] = plain_secret

        return result

    async def validate_key(
        self,
        api_key: str,
        required_scopes: Optional[List[KeyScope]] = None
    ) -> Optional[APIKey]:
        """Validate an API key and check scopes"""
        key_hash = self._hash_key(api_key)

        if key_hash not in self._key_lookup:
            return None

        key_id = self._key_lookup[key_hash]
        key = self._keys.get(key_id)

        if not key or not key.is_valid:
            return None

        # Check scopes
        if required_scopes:
            if not key.has_any_scope(required_scopes):
                return None

        # Update last used
        key.last_used_at = datetime.utcnow()

        return key

    async def check_rate_limit(self, key_id: str) -> bool:
        """Check if key is within rate limits"""
        key = self._keys.get(key_id)
        if not key:
            return False

        if key_id not in self._usage:
            self._usage[key_id] = KeyUsageStats(key_id=key_id)

        usage = self._usage[key_id]
        now = datetime.utcnow()

        # Reset minute counter
        if (now - usage.minute_reset).total_seconds() >= 60:
            usage.requests_this_minute = 0
            usage.minute_reset = now

        # Reset day counter
        if (now - usage.day_reset).total_seconds() >= 86400:
            usage.requests_today = 0
            usage.day_reset = now

        # Check limits
        if usage.requests_this_minute >= key.rate_limit_per_minute:
            return False
        if usage.requests_today >= key.rate_limit_per_day:
            return False

        return True

    async def record_usage(self, key_id: str, is_error: bool = False):
        """Record API usage for a key"""
        if key_id not in self._usage:
            self._usage[key_id] = KeyUsageStats(key_id=key_id)

        usage = self._usage[key_id]
        usage.requests_this_minute += 1
        usage.requests_today += 1
        usage.total_requests += 1
        if is_error:
            usage.total_errors += 1

    async def revoke_key(self, key_id: str):
        """Revoke an API key"""
        if key_id in self._keys:
            self._keys[key_id].is_active = False
            self._save()
            logger.info(f"Revoked API key {key_id}")

    async def delete_key(self, key_id: str):
        """Delete an API key permanently"""
        if key_id in self._keys:
            key = self._keys.pop(key_id)
            if key.key_hash in self._key_lookup:
                del self._key_lookup[key.key_hash]
            self._save()
            logger.info(f"Deleted API key {key_id}")

    async def rotate_key(self, key_id: str) -> Optional[Dict[str, str]]:
        """Rotate an API key (generate new key, keep settings)"""
        old_key = self._keys.get(key_id)
        if not old_key:
            return None

        # Create new key with same settings
        result = await self.create_key(
            user_id=old_key.user_id,
            name=f"{old_key.name} (rotated)",
            scopes=old_key.scopes,
            rate_limit_per_minute=old_key.rate_limit_per_minute,
            rate_limit_per_day=old_key.rate_limit_per_day,
            with_secret=old_key.secret_hash is not None
        )

        # Revoke old key
        await self.revoke_key(key_id)

        return result

    async def get_user_keys(self, user_id: str) -> List[APIKey]:
        """Get all keys for a user"""
        return [k for k in self._keys.values() if k.user_id == user_id]

    async def get_key(self, key_id: str) -> Optional[APIKey]:
        """Get a key by ID"""
        return self._keys.get(key_id)

    async def get_usage_stats(self, key_id: str) -> Optional[Dict[str, Any]]:
        """Get usage stats for a key"""
        if key_id not in self._usage:
            return None

        usage = self._usage[key_id]
        key = self._keys.get(key_id)

        return {
            "key_id": key_id,
            "requests_today": usage.requests_today,
            "requests_this_minute": usage.requests_this_minute,
            "total_requests": usage.total_requests,
            "total_errors": usage.total_errors,
            "rate_limit_minute": key.rate_limit_per_minute if key else 0,
            "rate_limit_day": key.rate_limit_per_day if key else 0
        }


# Singleton
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get the API key manager singleton"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# Testing
if __name__ == "__main__":
    async def test():
        manager = APIKeyManager("data/test_api_keys.json")

        # Create a key
        result = await manager.create_key(
            user_id="test_user",
            name="Test Key",
            scopes=[KeyScope.READ_PORTFOLIO, KeyScope.READ_TRADES],
            with_secret=True
        )
        print(f"Created key: {result}")

        # Validate key
        key = await manager.validate_key(result["api_key"])
        print(f"Validated: {key.to_dict() if key else None}")

        # Check scope
        if key:
            print(f"Has READ_PORTFOLIO: {key.has_scope(KeyScope.READ_PORTFOLIO)}")
            print(f"Has WRITE_TRADES: {key.has_scope(KeyScope.WRITE_TRADES)}")

        # Check rate limit
        is_allowed = await manager.check_rate_limit(result["key_id"])
        print(f"Rate limit OK: {is_allowed}")

        # Record usage
        await manager.record_usage(result["key_id"])
        stats = await manager.get_usage_stats(result["key_id"])
        print(f"Usage stats: {stats}")

    asyncio.run(test())
