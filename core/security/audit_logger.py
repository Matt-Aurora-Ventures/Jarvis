"""
Immutable Audit Logger

Provides append-only audit logging for security-critical operations:
- Admin actions
- Key rotations
- Configuration changes
- Manual trades
- Feature flag changes

Features:
- Append-only (immutable) log file
- JSON format for structured logging
- Optional integrity signatures
- Separate audit log (not mixed with app logs)
"""

import json
import hashlib
import hmac
import os
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of auditable events."""
    ADMIN_ACTION = "admin_action"
    KEY_ROTATION = "key_rotation"
    CONFIG_CHANGE = "config_change"
    MANUAL_TRADE = "manual_trade"
    FEATURE_FLAG = "feature_flag"
    SECURITY_EVENT = "security_event"
    DATA_ACCESS = "data_access"
    LOGIN = "login"
    LOGOUT = "logout"
    PERMISSION_CHANGE = "permission_change"
    SYSTEM_EVENT = "system_event"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: str
    event_type: str
    actor: str
    action: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    signature: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class AuditLogger:
    """
    Immutable audit logger for security events.

    All events are appended to a JSON Lines file.
    Optional HMAC signatures provide integrity verification.
    """

    def __init__(
        self,
        log_path: Optional[Path] = None,
        sign_entries: bool = False,
        signing_key_env: str = "JARVIS_AUDIT_KEY"
    ):
        """
        Initialize the audit logger.

        Args:
            log_path: Path to the audit log file
            sign_entries: Whether to sign entries with HMAC
            signing_key_env: Environment variable containing signing key
        """
        self.log_path = log_path or Path("data/audit.log")
        self.sign_entries = sign_entries
        self.signing_key_env = signing_key_env

        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        # Get signing key if needed
        self._signing_key: Optional[bytes] = None
        if self.sign_entries:
            key = os.environ.get(self.signing_key_env)
            if key:
                self._signing_key = key.encode()
            else:
                logger.warning(f"Signing enabled but {self.signing_key_env} not set")

    def _generate_signature(self, data: Dict[str, Any]) -> str:
        """Generate HMAC signature for an entry."""
        if not self._signing_key:
            return ""

        # Create deterministic string representation
        data_copy = {k: v for k, v in data.items() if k != "signature"}
        canonical = json.dumps(data_copy, sort_keys=True)

        # Generate HMAC-SHA256
        signature = hmac.new(
            self._signing_key,
            canonical.encode(),
            hashlib.sha256
        ).hexdigest()

        return signature

    def _create_entry(
        self,
        event_type: AuditEventType,
        actor: str,
        action: str,
        details: Dict[str, Any],
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditEntry:
        """Create an audit entry."""
        entry = AuditEntry(
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=event_type.value,
            actor=actor,
            action=action,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            success=success,
            error_message=error_message
        )

        # Add signature if enabled
        if self.sign_entries:
            entry.signature = self._generate_signature(entry.to_dict())

        return entry

    def _write_entry(self, entry: AuditEntry) -> None:
        """Write an entry to the log file (append-only)."""
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def log(
        self,
        event_type: AuditEventType,
        actor: str,
        action: str,
        details: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            actor: Who performed the action
            action: What action was performed
            details: Additional details
            **kwargs: Additional entry fields (success, error_message, etc.)
        """
        entry = self._create_entry(event_type, actor, action, details, **kwargs)
        self._write_entry(entry)
        logger.debug(f"Audit: {event_type.value} by {actor}: {action}")

    def log_admin_action(
        self,
        actor: str,
        action: str,
        details: Dict[str, Any],
        **kwargs
    ) -> None:
        """Log an admin action."""
        self.log(AuditEventType.ADMIN_ACTION, actor, action, details, **kwargs)

    def log_key_rotation(
        self,
        service: str,
        rotated_by: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """Log a key rotation event."""
        self.log(
            AuditEventType.KEY_ROTATION,
            actor=rotated_by,
            action="rotate_key",
            details={"service": service},
            success=success,
            error_message=error_message
        )

    def log_config_change(
        self,
        actor: str,
        setting: str,
        old_value: Any,
        new_value: Any
    ) -> None:
        """Log a configuration change."""
        self.log(
            AuditEventType.CONFIG_CHANGE,
            actor=actor,
            action="config_change",
            details={
                "setting": setting,
                "old_value": str(old_value),
                "new_value": str(new_value)
            }
        )

    def log_trade(
        self,
        actor: str,
        trade_type: str,
        symbol: str,
        amount: float,
        price: Optional[float] = None,
        **kwargs
    ) -> None:
        """Log a manual trade action."""
        details = {
            "trade_type": trade_type,
            "symbol": symbol,
            "amount": amount
        }
        if price is not None:
            details["price"] = price
        details.update(kwargs)

        self.log(
            AuditEventType.MANUAL_TRADE,
            actor=actor,
            action=trade_type,
            details=details
        )

    def log_feature_flag_change(
        self,
        flag_name: str,
        old_value: Any,
        new_value: Any,
        changed_by: str
    ) -> None:
        """Log a feature flag change."""
        self.log(
            AuditEventType.FEATURE_FLAG,
            actor=changed_by,
            action="feature_flag_change",
            details={
                "flag_name": flag_name,
                "old_value": old_value,
                "new_value": new_value
            }
        )

    def log_security_event(
        self,
        event_type: str,
        actor: str,
        details: Dict[str, Any],
        success: bool = True
    ) -> None:
        """Log a security-related event."""
        self.log(
            AuditEventType.SECURITY_EVENT,
            actor=actor,
            action=event_type,
            details=details,
            success=success
        )

    def log_login(
        self,
        user_id: str,
        ip_address: str,
        success: bool,
        method: str = "password"
    ) -> None:
        """Log a login attempt."""
        self.log(
            AuditEventType.LOGIN,
            actor=user_id,
            action="login",
            details={"method": method},
            ip_address=ip_address,
            success=success
        )

    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        actor: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> list:
        """
        Query audit log entries.

        Args:
            event_type: Filter by event type
            actor: Filter by actor
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum entries to return

        Returns:
            List of matching entries
        """
        if not self.log_path.exists():
            return []

        results = []

        with open(self.log_path, "r") as f:
            for line in f:
                if len(results) >= limit:
                    break

                try:
                    entry = json.loads(line)

                    # Apply filters
                    if event_type and entry.get("event_type") != event_type.value:
                        continue
                    if actor and entry.get("actor") != actor:
                        continue
                    if start_time:
                        entry_time = datetime.fromisoformat(
                            entry["timestamp"].replace("Z", "+00:00")
                        )
                        if entry_time < start_time:
                            continue
                    if end_time:
                        entry_time = datetime.fromisoformat(
                            entry["timestamp"].replace("Z", "+00:00")
                        )
                        if entry_time > end_time:
                            continue

                    results.append(entry)

                except (json.JSONDecodeError, KeyError):
                    continue

        return results

    def verify_integrity(self) -> Dict[str, Any]:
        """
        Verify integrity of all signed entries.

        Returns:
            Dict with verification results
        """
        if not self._signing_key:
            return {"error": "Signing key not available"}

        if not self.log_path.exists():
            return {"total": 0, "valid": 0, "invalid": 0}

        total = 0
        valid = 0
        invalid = 0
        invalid_lines = []

        with open(self.log_path, "r") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    entry = json.loads(line)
                    if "signature" not in entry:
                        continue

                    total += 1
                    stored_sig = entry.pop("signature")
                    expected_sig = self._generate_signature(entry)

                    if hmac.compare_digest(stored_sig, expected_sig):
                        valid += 1
                    else:
                        invalid += 1
                        invalid_lines.append(line_num)

                except (json.JSONDecodeError, KeyError):
                    continue

        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "invalid_lines": invalid_lines[:10]  # First 10 invalid lines
        }


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(sign_entries=True)
    return _audit_logger


# Convenience functions
def audit_admin_action(actor: str, action: str, details: Dict[str, Any]) -> None:
    """Log an admin action."""
    get_audit_logger().log_admin_action(actor, action, details)


def audit_key_rotation(service: str, rotated_by: str, success: bool = True) -> None:
    """Log a key rotation."""
    get_audit_logger().log_key_rotation(service, rotated_by, success)


def audit_config_change(actor: str, setting: str, old_value: Any, new_value: Any) -> None:
    """Log a config change."""
    get_audit_logger().log_config_change(actor, setting, old_value, new_value)


def audit_trade(actor: str, trade_type: str, symbol: str, amount: float, **kwargs) -> None:
    """Log a trade."""
    get_audit_logger().log_trade(actor, trade_type, symbol, amount, **kwargs)
