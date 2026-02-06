"""
Security Audit Logger

Provides structured logging for security-critical operations:
- Action logging (actor, action, resource, details)
- Access logging (user, resource, granted)
- Change logging (entity, field, old_value, new_value)
- Error logging (error, context)

Features:
- Thread-safe append-only logging
- JSON Lines format for easy parsing
- Automatic timestamp and entry ID generation
- Optional IP address and session tracking
"""

import json
import logging
import threading
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

# Default audit log location
DEFAULT_AUDIT_DIR = Path("bots/logs/audit")


@dataclass
class AuditEntry:
    """A single audit log entry."""

    timestamp: datetime
    actor: str
    action: str
    resource: str
    details: Dict[str, Any]
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    success: bool = True
    error_message: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    user_agent: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for JSON serialization."""
        d = {
            "timestamp": self.timestamp.isoformat(),
            "entry_id": self.entry_id,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "success": self.success,
        }

        # Only include optional fields if they have values
        if self.error_message:
            d["error_message"] = self.error_message
        if self.ip_address:
            d["ip_address"] = self.ip_address
        if self.session_id:
            d["session_id"] = self.session_id
        if self.user_agent:
            d["user_agent"] = self.user_agent

        return d


class AuditLogger:
    """
    Thread-safe audit logger for security events.

    All events are appended to daily JSON Lines files.
    Designed for high-throughput concurrent access.
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        file_prefix: str = "audit",
    ):
        """
        Initialize the audit logger.

        Args:
            log_dir: Directory for audit log files
            file_prefix: Prefix for log file names
        """
        self.log_dir = Path(log_dir) if log_dir else DEFAULT_AUDIT_DIR
        self.file_prefix = file_prefix
        self._lock = threading.Lock()

        # Ensure directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def _get_current_log_file(self) -> Path:
        """Get the current day's log file path."""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self.log_dir / f"{self.file_prefix}_{today}.jsonl"

    def _write_entry(self, entry: AuditEntry) -> None:
        """Write an entry to the log file (thread-safe, append-only)."""
        with self._lock:
            log_file = self._get_current_log_file()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict()) + "\n")

    def _create_entry(
        self,
        actor: str,
        action: str,
        resource: str,
        details: Dict[str, Any],
        success: bool = True,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> AuditEntry:
        """Create an audit entry with current timestamp."""
        return AuditEntry(
            timestamp=datetime.now(timezone.utc),
            actor=actor,
            action=action,
            resource=resource,
            details=details,
            success=success,
            error_message=error_message,
            ip_address=ip_address,
            session_id=session_id,
        )

    def log_action(
        self,
        actor: str,
        action: str,
        resource: str,
        details: Dict[str, Any],
        **kwargs
    ) -> None:
        """
        Log a general action.

        Args:
            actor: Who performed the action (user ID, service name, etc.)
            action: What action was performed (create, update, delete, etc.)
            resource: What resource was affected (users/123, config/settings, etc.)
            details: Additional details about the action
            **kwargs: Additional entry fields (ip_address, session_id, etc.)
        """
        entry = self._create_entry(actor, action, resource, details, **kwargs)
        self._write_entry(entry)
        logger.debug(f"Audit: {action} by {actor} on {resource}")

    def log_access(
        self,
        user: str,
        resource: str,
        granted: bool,
        **kwargs
    ) -> None:
        """
        Log an access attempt.

        Args:
            user: User attempting access
            resource: Resource being accessed
            granted: Whether access was granted
            **kwargs: Additional entry fields
        """
        entry = self._create_entry(
            actor=user,
            action="access",
            resource=resource,
            details={"granted": granted},
            success=granted,
            **kwargs
        )
        self._write_entry(entry)

        level = logging.DEBUG if granted else logging.WARNING
        logger.log(level, f"Access {'granted' if granted else 'denied'}: {user} -> {resource}")

    def log_change(
        self,
        entity: str,
        field: str,
        old: Any,
        new: Any,
        actor: str = "system",
        **kwargs
    ) -> None:
        """
        Log a data change.

        Args:
            entity: Entity being changed (user/123, config, etc.)
            field: Field being changed
            old: Old value
            new: New value
            actor: Who made the change
            **kwargs: Additional entry fields
        """
        entry = self._create_entry(
            actor=actor,
            action="change",
            resource=entity,
            details={
                "field": field,
                "old_value": str(old) if old is not None else None,
                "new_value": str(new) if new is not None else None,
            },
            **kwargs
        )
        self._write_entry(entry)
        logger.debug(f"Change: {entity}.{field} by {actor}")

    def log_error(
        self,
        error: Union[str, Exception],
        context: Dict[str, Any],
        actor: str = "system",
        **kwargs
    ) -> None:
        """
        Log an error event.

        Args:
            error: Error message or exception
            context: Context information about the error
            actor: Who/what encountered the error
            **kwargs: Additional entry fields
        """
        error_str = str(error)
        if isinstance(error, Exception):
            error_str = f"{type(error).__name__}: {error}"

        entry = self._create_entry(
            actor=actor,
            action="error",
            resource="system",
            details={
                "error": error_str,
                "context": context,
            },
            success=False,
            error_message=error_str,
            **kwargs
        )
        self._write_entry(entry)
        logger.warning(f"Audit error logged: {error_str}")


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None
_logger_lock = threading.Lock()


def get_audit_logger() -> AuditLogger:
    """Get or create the global audit logger singleton."""
    global _audit_logger

    if _audit_logger is None:
        with _logger_lock:
            if _audit_logger is None:
                _audit_logger = AuditLogger()

    return _audit_logger


# Convenience functions
def audit_action(actor: str, action: str, resource: str, details: Dict[str, Any]) -> None:
    """Log an action using the global logger."""
    get_audit_logger().log_action(actor, action, resource, details)


def audit_access(user: str, resource: str, granted: bool) -> None:
    """Log an access attempt using the global logger."""
    get_audit_logger().log_access(user, resource, granted)


def audit_change(entity: str, field: str, old: Any, new: Any, actor: str = "system") -> None:
    """Log a change using the global logger."""
    get_audit_logger().log_change(entity, field, old, new, actor)


def audit_error(error: Union[str, Exception], context: Dict[str, Any]) -> None:
    """Log an error using the global logger."""
    get_audit_logger().log_error(error, context)
