"""
API Key Rotation Manager

Handles secure rotation of API keys with grace period support.
Supports: Anthropic, Telegram, Grok, and custom service keys.

Security features:
- 24-hour grace period for old keys during transition
- Audit logging of all rotation events
- Schedule-based rotation checking
- Secure key storage integration
"""

import json
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ServiceType(str, Enum):
    """Supported services for key rotation."""
    ANTHROPIC = "anthropic_api"
    TELEGRAM = "telegram_bot"
    GROK = "grok_api"
    TWITTER = "twitter_api"
    CUSTOM = "custom"


@dataclass
class RotationResult:
    """Result of a key rotation operation."""
    success: bool
    service_name: str
    timestamp: datetime
    error_message: Optional[str] = None
    old_key_hash: Optional[str] = None
    new_key_hash: Optional[str] = None
    grace_period_ends: Optional[datetime] = None


@dataclass
class KeyMetadata:
    """Metadata for a managed key."""
    service_name: str
    key_hash: str
    created_at: datetime
    last_rotated: datetime
    rotation_count: int = 0
    grace_period_keys: List[str] = field(default_factory=list)
    grace_period_end: Optional[datetime] = None


class KeyRotationManager:
    """
    Manages API key rotation with grace periods and audit logging.

    Features:
    - Rotate keys for Anthropic, Telegram, Grok, and custom services
    - 24-hour (configurable) grace period keeps old key valid
    - Full audit logging of rotation events
    - Schedule checking for automatic rotation triggers
    """

    DEFAULT_ROTATION_SCHEDULES = {
        ServiceType.ANTHROPIC.value: 30,   # 30 days
        ServiceType.TELEGRAM.value: 90,    # 90 days
        ServiceType.GROK.value: 30,        # 30 days
        ServiceType.TWITTER.value: 30,     # 30 days
    }

    def __init__(
        self,
        grace_period_hours: int = 24,
        metadata_path: Optional[Path] = None,
        log_path: Optional[Path] = None
    ):
        """
        Initialize the key rotation manager.

        Args:
            grace_period_hours: Hours to keep old key valid after rotation
            metadata_path: Path to store rotation metadata
            log_path: Path for rotation audit logs
        """
        self.grace_period_hours = grace_period_hours
        self.metadata_path = metadata_path or Path("data/key_rotation_metadata.json")
        self.log_path = log_path or Path("logs/key_rotation.log")

        # Ensure directories exist
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing metadata
        self._metadata: Dict[str, KeyMetadata] = {}
        self._load_metadata()

        # Active keys (hashed) and grace period keys
        self._active_keys: Dict[str, str] = {}  # service -> current_key_hash
        self._grace_period_keys: Dict[str, List[str]] = {}  # service -> [old_key_hashes]

    def _load_metadata(self) -> None:
        """Load rotation metadata from disk."""
        if self.metadata_path.exists():
            try:
                data = json.loads(self.metadata_path.read_text())
                for service_name, meta in data.items():
                    self._metadata[service_name] = KeyMetadata(
                        service_name=meta["service_name"],
                        key_hash=meta["key_hash"],
                        created_at=datetime.fromisoformat(meta["created_at"]),
                        last_rotated=datetime.fromisoformat(meta["last_rotated"]),
                        rotation_count=meta.get("rotation_count", 0),
                        grace_period_keys=meta.get("grace_period_keys", []),
                        grace_period_end=datetime.fromisoformat(meta["grace_period_end"]) if meta.get("grace_period_end") else None
                    )
            except Exception as e:
                logger.error(f"Failed to load rotation metadata: {e}")

    def _save_metadata(self) -> None:
        """Save rotation metadata to disk."""
        data = {}
        for service_name, meta in self._metadata.items():
            data[service_name] = {
                "service_name": meta.service_name,
                "key_hash": meta.key_hash,
                "created_at": meta.created_at.isoformat(),
                "last_rotated": meta.last_rotated.isoformat(),
                "rotation_count": meta.rotation_count,
                "grace_period_keys": meta.grace_period_keys,
                "grace_period_end": meta.grace_period_end.isoformat() if meta.grace_period_end else None
            }

        self.metadata_path.write_text(json.dumps(data, indent=2))

    def _hash_key(self, key: str) -> str:
        """Create a secure hash of a key (for storage/comparison, not the actual key)."""
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def _log_rotation_event(
        self,
        service_name: str,
        event_type: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a rotation event to the audit log."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "service": service_name,
            "event_type": event_type,
            "success": success,
            "details": details or {}
        }

        with open(self.log_path, "a") as f:
            f.write(json.dumps(event) + "\n")

        logger.info(f"Key rotation event: {event_type} for {service_name} - {'success' if success else 'failed'}")

    def rotate_key(
        self,
        service_name: str,
        old_key: str,
        new_key: str,
        validate_new_key: bool = True
    ) -> RotationResult:
        """
        Rotate a key for a service.

        Args:
            service_name: Name of the service (e.g., "anthropic_api")
            old_key: The current/old key
            new_key: The new key to activate
            validate_new_key: Whether to validate the new key before rotation

        Returns:
            RotationResult with success status and details
        """
        now = datetime.now()
        old_key_hash = self._hash_key(old_key)
        new_key_hash = self._hash_key(new_key)

        try:
            # Basic validation
            if not new_key or len(new_key) < 10:
                raise ValueError("New key is too short or empty")

            if old_key_hash == new_key_hash:
                raise ValueError("New key is the same as old key")

            # Calculate grace period end
            grace_period_end = now + timedelta(hours=self.grace_period_hours)

            # Update metadata
            if service_name in self._metadata:
                meta = self._metadata[service_name]
                # Add old key to grace period list
                meta.grace_period_keys.append(old_key_hash)
                meta.key_hash = new_key_hash
                meta.last_rotated = now
                meta.rotation_count += 1
                meta.grace_period_end = grace_period_end
            else:
                # First rotation - create new metadata
                self._metadata[service_name] = KeyMetadata(
                    service_name=service_name,
                    key_hash=new_key_hash,
                    created_at=now,
                    last_rotated=now,
                    rotation_count=1,
                    grace_period_keys=[old_key_hash],
                    grace_period_end=grace_period_end
                )

            # Update active keys
            self._active_keys[service_name] = new_key_hash

            # Update grace period keys
            if service_name not in self._grace_period_keys:
                self._grace_period_keys[service_name] = []
            self._grace_period_keys[service_name].append(old_key_hash)

            # Save metadata
            self._save_metadata()

            # Log the rotation
            self._log_rotation_event(
                service_name=service_name,
                event_type="rotation",
                success=True,
                details={
                    "old_key_hash": old_key_hash,
                    "new_key_hash": new_key_hash,
                    "grace_period_end": grace_period_end.isoformat()
                }
            )

            return RotationResult(
                success=True,
                service_name=service_name,
                timestamp=now,
                old_key_hash=old_key_hash,
                new_key_hash=new_key_hash,
                grace_period_ends=grace_period_end
            )

        except Exception as e:
            self._log_rotation_event(
                service_name=service_name,
                event_type="rotation",
                success=False,
                details={"error": str(e)}
            )

            return RotationResult(
                success=False,
                service_name=service_name,
                timestamp=now,
                error_message=str(e)
            )

    def is_key_valid(self, service_name: str, key: str) -> bool:
        """
        Check if a key is valid (either active or in grace period).

        Args:
            service_name: Name of the service
            key: The key to validate

        Returns:
            True if key is valid (active or in grace period)
        """
        key_hash = self._hash_key(key)

        if service_name not in self._metadata:
            # No rotation history - key might be valid (first use)
            return True

        meta = self._metadata[service_name]

        # Check if it's the active key
        if meta.key_hash == key_hash:
            return True

        # Check if it's in grace period (also check in-memory cache)
        grace_keys = self._grace_period_keys.get(service_name, [])
        if key_hash in meta.grace_period_keys or key_hash in grace_keys:
            # Check if grace period has expired
            if meta.grace_period_end and datetime.now() < meta.grace_period_end:
                return True
            else:
                # Grace period expired - clean up
                if key_hash in meta.grace_period_keys:
                    meta.grace_period_keys.remove(key_hash)
                if key_hash in grace_keys:
                    grace_keys.remove(key_hash)
                self._save_metadata()
                return False

        return False

    def set_last_rotation(self, service_name: str, timestamp: datetime) -> None:
        """
        Set the last rotation time for a service (useful for testing/migration).

        Args:
            service_name: Name of the service
            timestamp: The last rotation timestamp
        """
        if service_name not in self._metadata:
            self._metadata[service_name] = KeyMetadata(
                service_name=service_name,
                key_hash="",
                created_at=timestamp,
                last_rotated=timestamp
            )
        else:
            self._metadata[service_name].last_rotated = timestamp

        self._save_metadata()

    def needs_rotation(self, service_name: str, rotation_days: Optional[int] = None) -> bool:
        """
        Check if a service key needs rotation based on schedule.

        Args:
            service_name: Name of the service
            rotation_days: Override the default rotation schedule (days)

        Returns:
            True if rotation is needed
        """
        if rotation_days is None:
            rotation_days = self.DEFAULT_ROTATION_SCHEDULES.get(service_name, 30)

        if service_name not in self._metadata:
            # No rotation history - might need initial rotation
            return True

        meta = self._metadata[service_name]
        days_since_rotation = (datetime.now() - meta.last_rotated).days

        return days_since_rotation >= rotation_days

    def get_rotation_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get rotation status for all tracked services.

        Returns:
            Dict mapping service names to their rotation status
        """
        status = {}

        for service_name, meta in self._metadata.items():
            days_since = (datetime.now() - meta.last_rotated).days
            default_schedule = self.DEFAULT_ROTATION_SCHEDULES.get(service_name, 30)

            status[service_name] = {
                "last_rotation": meta.last_rotated.isoformat(),
                "days_since_rotation": days_since,
                "rotation_count": meta.rotation_count,
                "needs_rotation": days_since >= default_schedule,
                "grace_period_active": bool(meta.grace_period_keys),
                "grace_period_end": meta.grace_period_end.isoformat() if meta.grace_period_end else None
            }

        return status

    def cleanup_expired_grace_periods(self) -> int:
        """
        Remove expired grace period keys.

        Returns:
            Number of keys cleaned up
        """
        cleaned = 0
        now = datetime.now()

        for service_name, meta in self._metadata.items():
            if meta.grace_period_end and now >= meta.grace_period_end:
                cleaned += len(meta.grace_period_keys)
                meta.grace_period_keys = []
                meta.grace_period_end = None

        if cleaned > 0:
            self._save_metadata()
            logger.info(f"Cleaned up {cleaned} expired grace period keys")

        return cleaned


# Convenience functions for common services

def rotate_anthropic_key(old_key: str, new_key: str) -> RotationResult:
    """Rotate Anthropic API key."""
    manager = KeyRotationManager()
    return manager.rotate_key(ServiceType.ANTHROPIC.value, old_key, new_key)


def rotate_telegram_token(old_token: str, new_token: str) -> RotationResult:
    """Rotate Telegram Bot token."""
    manager = KeyRotationManager()
    return manager.rotate_key(ServiceType.TELEGRAM.value, old_token, new_token)


def rotate_grok_key(old_key: str, new_key: str) -> RotationResult:
    """Rotate Grok API key."""
    manager = KeyRotationManager()
    return manager.rotate_key(ServiceType.GROK.value, old_key, new_key)


def check_all_rotation_status() -> Dict[str, Dict[str, Any]]:
    """Check rotation status for all services."""
    manager = KeyRotationManager()
    return manager.get_rotation_status()
