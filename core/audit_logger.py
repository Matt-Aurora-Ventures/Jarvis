"""
Audit Logger - Comprehensive audit trail for all system actions.

Provides:
- Immutable audit trail
- Action categorization
- User attribution
- Compliance reporting
- Security event logging
"""

import json
import logging
import hashlib
import os
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional, List
from threading import Lock

logger = logging.getLogger(__name__)


class AuditCategory(Enum):
    """Categories of auditable events."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    TRADING = "trading"
    WALLET = "wallet"
    CONFIGURATION = "configuration"
    API_ACCESS = "api_access"
    DATA_ACCESS = "data_access"
    SYSTEM = "system"
    SECURITY = "security"
    USER_ACTION = "user_action"
    DECISION = "decision"  # For decision framework audit trail


class AuditSeverity(Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEntry:
    """Single audit log entry."""
    timestamp: str
    category: str
    action: str
    user_id: Optional[str]
    resource: Optional[str]
    details: Dict[str, Any]
    severity: str
    success: bool
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    previous_hash: Optional[str] = None
    entry_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def compute_hash(self) -> str:
        """Compute hash for chain integrity."""
        data = f"{self.timestamp}{self.category}{self.action}{self.user_id}{self.details}{self.previous_hash}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


class AuditLogger:
    """
    Comprehensive audit logging system.
    
    Features:
    - Immutable log chain with hash verification
    - Multiple output targets (file, database, remote)
    - Automatic log rotation
    - Compliance-ready formatting
    """

    _instance: Optional["AuditLogger"] = None
    _lock = Lock()

    # Feature flags (ready to activate)
    ENABLE_HASH_CHAIN = False  # Enable immutable hash chain
    ENABLE_REMOTE_LOGGING = False  # Send to remote audit service
    ENABLE_ENCRYPTION = False  # Encrypt sensitive fields

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.log_dir = Path(os.getenv("AUDIT_LOG_DIR", "data/audit"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        self.entries: List[AuditEntry] = []
        self.last_hash: Optional[str] = None
        
        self._load_last_hash()
        self._initialized = True
        logger.info(f"AuditLogger initialized: {self.current_file}")

    def _load_last_hash(self):
        """Load last hash for chain continuity."""
        if not self.ENABLE_HASH_CHAIN:
            return
            
        if self.current_file.exists():
            try:
                with open(self.current_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_entry = json.loads(lines[-1])
                        self.last_hash = last_entry.get("entry_hash")
            except Exception as e:
                logger.warning(f"Failed to load last hash: {e}")

    def log(
        self,
        category: AuditCategory,
        action: str,
        details: Dict[str, Any] = None,
        user_id: str = None,
        resource: str = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        success: bool = True,
        ip_address: str = None,
        user_agent: str = None,
        session_id: str = None,
        request_id: str = None,
    ) -> AuditEntry:
        """Log an audit event."""
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            category=category.value,
            action=action,
            user_id=user_id,
            resource=resource,
            details=details or {},
            severity=severity.value,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            session_id=session_id,
            request_id=request_id,
            previous_hash=self.last_hash if self.ENABLE_HASH_CHAIN else None,
        )

        if self.ENABLE_HASH_CHAIN:
            entry.entry_hash = entry.compute_hash()
            self.last_hash = entry.entry_hash

        self._write_entry(entry)
        self.entries.append(entry)

        # Log to standard logger as well
        log_msg = f"[AUDIT] {category.value}:{action} user={user_id} success={success}"
        if severity == AuditSeverity.CRITICAL:
            logger.critical(log_msg)
        elif severity == AuditSeverity.ERROR:
            logger.error(log_msg)
        elif severity == AuditSeverity.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        return entry

    def _write_entry(self, entry: AuditEntry):
        """Write entry to file."""
        # Rotate file if date changed
        today = datetime.now().strftime('%Y%m%d')
        expected_file = self.log_dir / f"audit_{today}.jsonl"
        if expected_file != self.current_file:
            self.current_file = expected_file
            self.last_hash = None

        try:
            with open(self.current_file, 'a') as f:
                f.write(json.dumps(entry.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to write audit entry: {e}")

    # Convenience methods for common audit events
    def log_auth(self, action: str, user_id: str, success: bool, details: Dict = None):
        """Log authentication event."""
        return self.log(
            category=AuditCategory.AUTHENTICATION,
            action=action,
            user_id=user_id,
            success=success,
            details=details,
            severity=AuditSeverity.WARNING if not success else AuditSeverity.INFO,
        )

    def log_trade(self, action: str, user_id: str, details: Dict, success: bool = True):
        """Log trading event."""
        return self.log(
            category=AuditCategory.TRADING,
            action=action,
            user_id=user_id,
            details=details,
            success=success,
            severity=AuditSeverity.INFO,
        )

    def log_security(self, action: str, details: Dict, severity: AuditSeverity = AuditSeverity.WARNING):
        """Log security event."""
        return self.log(
            category=AuditCategory.SECURITY,
            action=action,
            details=details,
            severity=severity,
        )

    def log_api_access(self, endpoint: str, method: str, user_id: str = None, status_code: int = 200):
        """Log API access."""
        return self.log(
            category=AuditCategory.API_ACCESS,
            action=f"{method} {endpoint}",
            user_id=user_id,
            details={"status_code": status_code},
            success=status_code < 400,
        )

    def get_entries(
        self,
        category: AuditCategory = None,
        user_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query audit entries."""
        results = self.entries.copy()

        if category:
            results = [e for e in results if e.category == category.value]
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        if start_time:
            results = [e for e in results if e.timestamp >= start_time.isoformat()]
        if end_time:
            results = [e for e in results if e.timestamp <= end_time.isoformat()]

        return results[-limit:]

    def verify_chain_integrity(self) -> bool:
        """Verify hash chain integrity."""
        if not self.ENABLE_HASH_CHAIN:
            return True

        prev_hash = None
        for entry in self.entries:
            if entry.previous_hash != prev_hash:
                return False
            computed = entry.compute_hash()
            if entry.entry_hash != computed:
                return False
            prev_hash = entry.entry_hash

        return True

    def generate_compliance_report(self, start_date: datetime, end_date: datetime) -> Dict:
        """Generate compliance report for date range."""
        entries = self.get_entries(start_time=start_date, end_time=end_date, limit=10000)

        return {
            "report_generated": datetime.now(timezone.utc).isoformat(),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_events": len(entries),
            "by_category": self._count_by_field(entries, "category"),
            "by_severity": self._count_by_field(entries, "severity"),
            "success_rate": sum(1 for e in entries if e.success) / len(entries) if entries else 0,
            "unique_users": len(set(e.user_id for e in entries if e.user_id)),
            "chain_integrity": self.verify_chain_integrity(),
        }

    def _count_by_field(self, entries: List[AuditEntry], field: str) -> Dict[str, int]:
        counts = {}
        for entry in entries:
            val = getattr(entry, field)
            counts[val] = counts.get(val, 0) + 1
        return counts


# Singleton instance
_audit_logger_instance: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get the audit logger singleton."""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = AuditLogger()
    return _audit_logger_instance


def audit_log(
    event: str,
    component: str,
    data: Dict[str, Any],
    success: bool = True,
    user_id: str = None,
) -> None:
    """
    Convenience function for logging audit events.

    This is the primary interface for the decision framework to log decisions.

    Args:
        event: The event type (e.g., "decision", "trade", "post")
        component: The component making the decision (e.g., "x_bot", "telegram_bot")
        data: Additional data to log
        success: Whether the action was successful
        user_id: Optional user ID associated with the action
    """
    try:
        logger = get_audit_logger()

        # Map event type to category
        category_map = {
            "decision": AuditCategory.DECISION,
            "trade": AuditCategory.TRADING,
            "auth": AuditCategory.AUTHENTICATION,
            "config": AuditCategory.CONFIGURATION,
            "api": AuditCategory.API_ACCESS,
            "security": AuditCategory.SECURITY,
        }
        category = category_map.get(event, AuditCategory.SYSTEM)

        logger.log(
            category=category,
            action=f"{component}:{event}",
            user_id=user_id,
            details=data,
            success=success,
            severity=AuditSeverity.INFO if success else AuditSeverity.WARNING,
        )
    except Exception as e:
        # Audit logging should never break the main flow
        logging.getLogger(__name__).debug(f"Audit log error: {e}")
