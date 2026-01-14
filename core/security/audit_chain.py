"""
JARVIS Audit Trail Hash Chain Verification

Provides tamper-evident audit logging using hash chains.
Each audit entry is linked to the previous via cryptographic hash,
making any modification detectable.
"""
import hashlib
import json
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    """A single audit log entry in the hash chain."""
    sequence: int
    timestamp: float
    action: str
    user_id: str
    resource: str
    details: Dict[str, Any]
    previous_hash: str
    entry_hash: str = field(default="")

    def __post_init__(self):
        if not self.entry_hash:
            self.entry_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry."""
        content = {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "action": self.action,
            "user_id": self.user_id,
            "resource": self.resource,
            "details": self.details,
            "previous_hash": self.previous_hash
        }
        serialized = json.dumps(content, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(serialized.encode()).hexdigest()

    def verify(self) -> bool:
        """Verify this entry's hash is valid."""
        return self.entry_hash == self._compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditEntry":
        """Create from dictionary."""
        return cls(**data)


class AuditChain:
    """
    Tamper-evident audit log using hash chain.

    Each entry contains a hash of its contents plus the previous entry's hash,
    creating a chain where any modification breaks verification.

    Usage:
        chain = AuditChain()

        # Log an action
        entry = chain.log(
            action="user_login",
            user_id="user123",
            resource="session",
            details={"ip": "192.168.1.1"}
        )

        # Verify the entire chain
        valid, errors = chain.verify_chain()
        if not valid:
            for error in errors:
                print(f"Tampering detected: {error}")
    """

    GENESIS_HASH = "0" * 64  # Genesis block has all zeros

    def __init__(self, storage_path: Optional[Path] = None):
        self.entries: List[AuditEntry] = []
        self.storage_path = storage_path
        self._last_hash = self.GENESIS_HASH
        self._sequence = 0

        if storage_path and storage_path.exists():
            self._load()

    def log(
        self,
        action: str,
        user_id: str,
        resource: str,
        details: Optional[Dict[str, Any]] = None
    ) -> AuditEntry:
        """
        Add a new audit entry to the chain.

        Args:
            action: The action performed (e.g., "user_login", "trade_executed")
            user_id: ID of user performing action
            resource: Resource being accessed
            details: Additional context

        Returns:
            The created AuditEntry
        """
        entry = AuditEntry(
            sequence=self._sequence,
            timestamp=time.time(),
            action=action,
            user_id=user_id,
            resource=resource,
            details=details or {},
            previous_hash=self._last_hash
        )

        self.entries.append(entry)
        self._last_hash = entry.entry_hash
        self._sequence += 1

        logger.info(
            f"Audit: {action} by {user_id} on {resource} "
            f"[seq={entry.sequence}, hash={entry.entry_hash[:16]}...]"
        )

        if self.storage_path:
            self._persist(entry)

        return entry

    def verify_chain(self) -> tuple[bool, List[str]]:
        """
        Verify the integrity of the entire audit chain.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        expected_prev = self.GENESIS_HASH

        for i, entry in enumerate(self.entries):
            # Verify sequence
            if entry.sequence != i:
                errors.append(
                    f"Sequence mismatch at position {i}: "
                    f"expected {i}, got {entry.sequence}"
                )

            # Verify previous hash link
            if entry.previous_hash != expected_prev:
                errors.append(
                    f"Chain broken at sequence {entry.sequence}: "
                    f"previous_hash mismatch"
                )

            # Verify entry hash
            if not entry.verify():
                errors.append(
                    f"Entry {entry.sequence} hash invalid: "
                    f"content has been modified"
                )

            expected_prev = entry.entry_hash

        is_valid = len(errors) == 0

        if is_valid:
            logger.info(f"Audit chain verified: {len(self.entries)} entries valid")
        else:
            logger.error(f"Audit chain verification failed: {len(errors)} errors")

        return is_valid, errors

    def verify_entry(self, sequence: int) -> bool:
        """Verify a specific entry and its chain to genesis."""
        if sequence < 0 or sequence >= len(self.entries):
            return False

        expected_prev = self.GENESIS_HASH

        for i in range(sequence + 1):
            entry = self.entries[i]

            if entry.previous_hash != expected_prev:
                return False

            if not entry.verify():
                return False

            expected_prev = entry.entry_hash

        return True

    def get_entry(self, sequence: int) -> Optional[AuditEntry]:
        """Get entry by sequence number."""
        if 0 <= sequence < len(self.entries):
            return self.entries[sequence]
        return None

    def get_entries_by_action(self, action: str) -> List[AuditEntry]:
        """Get all entries for a specific action."""
        return [e for e in self.entries if e.action == action]

    def get_entries_by_user(self, user_id: str) -> List[AuditEntry]:
        """Get all entries for a specific user."""
        return [e for e in self.entries if e.user_id == user_id]

    def get_entries_in_range(
        self,
        start_time: float,
        end_time: float
    ) -> List[AuditEntry]:
        """Get entries within a time range."""
        return [
            e for e in self.entries
            if start_time <= e.timestamp <= end_time
        ]

    def export_chain(self) -> List[Dict[str, Any]]:
        """Export the entire chain as JSON-serializable data."""
        return [e.to_dict() for e in self.entries]

    def import_chain(self, data: List[Dict[str, Any]]) -> bool:
        """
        Import a chain from exported data.

        Returns True if import successful and chain is valid.
        """
        try:
            entries = [AuditEntry.from_dict(d) for d in data]

            # Temporarily set entries for verification
            old_entries = self.entries
            self.entries = entries

            valid, _ = self.verify_chain()

            if valid:
                if entries:
                    self._last_hash = entries[-1].entry_hash
                    self._sequence = entries[-1].sequence + 1
                return True
            else:
                self.entries = old_entries
                return False

        except Exception as e:
            logger.error(f"Failed to import chain: {e}")
            return False

    def _persist(self, entry: AuditEntry) -> None:
        """Append entry to storage file."""
        if not self.storage_path:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.storage_path, 'a') as f:
            f.write(json.dumps(entry.to_dict()) + '\n')

    def _load(self) -> None:
        """Load chain from storage file."""
        if not self.storage_path or not self.storage_path.exists():
            return

        entries = []
        with open(self.storage_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(AuditEntry.from_dict(json.loads(line)))

        if entries:
            self.entries = entries
            self._last_hash = entries[-1].entry_hash
            self._sequence = entries[-1].sequence + 1

            valid, errors = self.verify_chain()
            if not valid:
                logger.error(f"Loaded chain has integrity issues: {errors}")

    def get_stats(self) -> Dict[str, Any]:
        """Get chain statistics."""
        if not self.entries:
            return {
                "total_entries": 0,
                "first_entry": None,
                "last_entry": None,
                "actions": {},
                "users": {}
            }

        actions: Dict[str, int] = {}
        users: Dict[str, int] = {}

        for entry in self.entries:
            actions[entry.action] = actions.get(entry.action, 0) + 1
            users[entry.user_id] = users.get(entry.user_id, 0) + 1

        return {
            "total_entries": len(self.entries),
            "first_entry": datetime.fromtimestamp(
                self.entries[0].timestamp
            ).isoformat(),
            "last_entry": datetime.fromtimestamp(
                self.entries[-1].timestamp
            ).isoformat(),
            "actions": actions,
            "users": users,
            "chain_valid": self.verify_chain()[0]
        }


# Audit action constants
class AuditActions:
    """Standard audit action types."""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATED = "user_created"
    USER_DELETED = "user_deleted"

    TRADE_INITIATED = "trade_initiated"
    TRADE_EXECUTED = "trade_executed"
    TRADE_CANCELLED = "trade_cancelled"
    TRADE_FAILED = "trade_failed"

    WALLET_ACCESSED = "wallet_accessed"
    WALLET_TRANSFER = "wallet_transfer"

    CONFIG_CHANGED = "config_changed"
    PERMISSION_CHANGED = "permission_changed"

    EMERGENCY_SHUTDOWN = "emergency_shutdown"
    SECURITY_ALERT = "security_alert"

    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"


# Global audit chain instance
_audit_chain: Optional[AuditChain] = None


def get_audit_chain(storage_path: Optional[Path] = None) -> AuditChain:
    """Get or create the global audit chain."""
    global _audit_chain

    if _audit_chain is None:
        default_path = Path("data/audit/audit_chain.jsonl")
        _audit_chain = AuditChain(storage_path or default_path)

    return _audit_chain


def audit_log(
    action: str,
    user_id: str,
    resource: str,
    details: Optional[Dict[str, Any]] = None
) -> AuditEntry:
    """Convenience function to log to global audit chain."""
    return get_audit_chain().log(action, user_id, resource, details)


def verify_audit_chain() -> tuple[bool, List[str]]:
    """Verify the global audit chain integrity."""
    return get_audit_chain().verify_chain()
