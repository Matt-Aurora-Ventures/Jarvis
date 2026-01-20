"""
Comprehensive Audit Logger

Production-grade audit logging system for security-critical operations:
- All trading decisions with reasoning
- Admin/user actions
- API calls with sanitized parameters
- Immutable audit trail (append-only) with hash chain

Security features:
- Hash chain for tamper detection
- Automatic sensitive data redaction
- Log rotation with retention
- Compliance report generation
"""

import json
import hashlib
import hmac
import os
import re
import logging
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger(__name__)


class AuditCategory(str, Enum):
    """Categories of auditable events."""
    TRADING = "trading"
    ADMIN = "admin"
    USER = "user"
    API = "api"
    SECURITY = "security"
    SYSTEM = "system"
    CONFIG = "config"
    AUTH = "auth"


class AuditSeverity(str, Enum):
    """Severity levels for audit events."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Patterns to redact from logs
SENSITIVE_PATTERNS = [
    (r'sk[-_]?[a-zA-Z0-9]{20,}', '[REDACTED_API_KEY]'),
    (r'ghp_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_TOKEN]'),
    (r'gho_[a-zA-Z0-9]{36}', '[REDACTED_GITHUB_OAUTH]'),
    (r'xox[baprs]-[a-zA-Z0-9-]{10,}', '[REDACTED_SLACK_TOKEN]'),
    (r'Bearer\s+[a-zA-Z0-9._-]+', 'Bearer [REDACTED]'),
    (r'"password"\s*:\s*"[^"]*"', '"password": "[REDACTED]"'),
    (r'"api_key"\s*:\s*"[^"]*"', '"api_key": "[REDACTED]"'),
    (r'"secret"\s*:\s*"[^"]*"', '"secret": "[REDACTED]"'),
    (r'"token"\s*:\s*"[^"]*"', '"token": "[REDACTED]"'),
    (r'"private_key"\s*:\s*"[^"]*"', '"private_key": "[REDACTED]"'),
]

# Keys to redact in dictionaries
SENSITIVE_KEYS = {
    'password', 'api_key', 'apikey', 'secret', 'secret_key', 'secretkey',
    'private_key', 'privatekey', 'token', 'access_token', 'refresh_token',
    'auth_token', 'bearer', 'credential', 'credentials', 'key'
}


@dataclass
class TradingDecision:
    """Represents a trading decision with full context."""
    token_address: str
    action: str  # BUY, SELL, HOLD
    amount: float
    reasoning: Dict[str, Any]
    confidence: float
    strategy: str
    price: Optional[float] = None
    slippage: Optional[float] = None
    gas_estimate: Optional[float] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEntry:
    """A single audit log entry with hash chain support."""
    timestamp: str
    category: str
    action: str
    details: Dict[str, Any]
    entry_id: str
    severity: str = "info"
    user_id: Optional[str] = None
    admin_id: Optional[str] = None
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    target: Optional[str] = None
    success: bool = True
    error: Optional[str] = None
    previous_hash: Optional[str] = None
    entry_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def compute_hash(self, secret_key: Optional[bytes] = None) -> str:
        """Compute hash for this entry."""
        data = f"{self.timestamp}|{self.category}|{self.action}|{json.dumps(self.details, sort_keys=True)}|{self.previous_hash or ''}"
        if secret_key:
            return hmac.new(secret_key, data.encode(), hashlib.sha256).hexdigest()[:32]
        return hashlib.sha256(data.encode()).hexdigest()[:32]


class ComprehensiveAuditLogger:
    """
    Production-grade audit logging with security features.

    Features:
    - Hash chain for immutability verification
    - Automatic sensitive data redaction
    - Multiple query capabilities
    - Log rotation
    - Compliance report generation
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        max_file_size_mb: float = 100,
        retention_days: int = 365,
        enable_hash_chain: bool = True,
        signing_key: Optional[str] = None
    ):
        """
        Initialize the comprehensive audit logger.

        Args:
            log_dir: Directory for audit logs
            max_file_size_mb: Maximum size per log file before rotation
            retention_days: How long to keep logs
            enable_hash_chain: Enable hash chain for tamper detection
            signing_key: Optional key for HMAC signing
        """
        self.log_dir = Path(log_dir) if log_dir else Path("data/audit")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.max_file_size_bytes = int(max_file_size_mb * 1024 * 1024)
        self.retention_days = retention_days
        self.enable_hash_chain = enable_hash_chain

        self._signing_key: Optional[bytes] = None
        if signing_key:
            self._signing_key = signing_key.encode()
        elif os.environ.get("JARVIS_AUDIT_KEY"):
            self._signing_key = os.environ["JARVIS_AUDIT_KEY"].encode()

        self._lock = threading.Lock()
        self._current_file: Optional[Path] = None
        self._last_hash: Optional[str] = None
        self._entry_count = 0

        # Initialize current log file
        self._init_current_file()

    def _init_current_file(self):
        """Initialize or get the current log file."""
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        self._current_file = self.log_dir / f"audit_{today}.jsonl"

        # Load last hash for chain continuity
        if self.enable_hash_chain and self._current_file.exists():
            try:
                with open(self._current_file, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_entry = json.loads(lines[-1])
                        self._last_hash = last_entry.get("entry_hash")
                        self._entry_count = len(lines)
            except Exception as e:
                logger.warning(f"Failed to load last hash: {e}")

    def _rotate_if_needed(self):
        """Rotate log file if size limit exceeded."""
        if not self._current_file or not self._current_file.exists():
            self._init_current_file()
            return

        if self._current_file.stat().st_size >= self.max_file_size_bytes:
            # Rotate to new file
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            self._current_file = self.log_dir / f"audit_{timestamp}.jsonl"
            self._entry_count = 0

    def _sanitize_value(self, value: Any) -> Any:
        """Recursively sanitize sensitive data from values."""
        if isinstance(value, str):
            result = value
            for pattern, replacement in SENSITIVE_PATTERNS:
                result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
            return result
        elif isinstance(value, dict):
            return self._sanitize_dict(value)
        elif isinstance(value, list):
            return [self._sanitize_value(v) for v in value]
        return value

    def _sanitize_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize sensitive keys from a dictionary."""
        result = {}
        for key, value in data.items():
            if key.lower() in SENSITIVE_KEYS:
                result[key] = "[REDACTED]"
            else:
                result[key] = self._sanitize_value(value)
        return result

    def _create_entry(
        self,
        category: str,
        action: str,
        details: Dict[str, Any],
        **kwargs
    ) -> AuditEntry:
        """Create an audit entry with hash chain."""
        import uuid

        # Sanitize details
        sanitized_details = self._sanitize_dict(details)

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            category=category,
            action=action,
            details=sanitized_details,
            entry_id=str(uuid.uuid4())[:8],
            previous_hash=self._last_hash if self.enable_hash_chain else None,
            **kwargs
        )

        if self.enable_hash_chain:
            entry.entry_hash = entry.compute_hash(self._signing_key)
            self._last_hash = entry.entry_hash

        return entry

    def _write_entry(self, entry: AuditEntry) -> Dict[str, Any]:
        """Write entry to log file."""
        with self._lock:
            self._rotate_if_needed()

            try:
                with open(self._current_file, 'a') as f:
                    f.write(json.dumps(entry.to_dict()) + "\n")
                self._entry_count += 1
                return {"success": True, "entry_id": entry.entry_id}
            except Exception as e:
                logger.error(f"Failed to write audit entry: {e}")
                return {"success": False, "error": str(e)}

    def log_trading_decision(
        self,
        decision: TradingDecision,
        user_id: str = "system"
    ) -> Dict[str, Any]:
        """
        Log a trading decision with full reasoning.

        Args:
            decision: The trading decision with context
            user_id: Who/what made the decision

        Returns:
            Result with success status and entry_id
        """
        entry = self._create_entry(
            category=AuditCategory.TRADING.value,
            action=decision.action,
            details={
                "token_address": decision.token_address,
                "amount": decision.amount,
                "reasoning": decision.reasoning,
                "confidence": decision.confidence,
                "strategy": decision.strategy,
                "price": decision.price,
                "slippage": decision.slippage,
                "gas_estimate": decision.gas_estimate,
                "risk_assessment": decision.risk_assessment,
                "metadata": decision.metadata,
            },
            user_id=user_id
        )
        return self._write_entry(entry)

    def log_admin_action(
        self,
        admin_id: str,
        action: str,
        target: str,
        details: Dict[str, Any],
        ip_address: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log an admin action.

        Args:
            admin_id: Admin performing the action
            action: What action was performed
            target: Target of the action
            details: Additional details
            ip_address: Admin's IP address
            success: Whether action succeeded
            error: Error message if failed
        """
        entry = self._create_entry(
            category=AuditCategory.ADMIN.value,
            action=action,
            details=details,
            admin_id=admin_id,
            target=target,
            ip_address=ip_address,
            success=success,
            error=error,
            severity=AuditSeverity.WARNING.value if not success else AuditSeverity.INFO.value
        )
        return self._write_entry(entry)

    def log_user_action(
        self,
        user_id: str,
        action: str,
        details: Dict[str, Any],
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log a user action.

        Args:
            user_id: User performing the action
            action: What action was performed
            details: Additional details
            session_id: User's session ID
            ip_address: User's IP address
        """
        entry = self._create_entry(
            category=AuditCategory.USER.value,
            action=action,
            details=details,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address
        )
        return self._write_entry(entry)

    def log_api_call(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[str],
        parameters: Dict[str, Any],
        response_status: int,
        response_time_ms: float,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Log an API call with sanitized parameters.

        Args:
            endpoint: API endpoint called
            method: HTTP method
            user_id: User making the call
            parameters: Request parameters (will be sanitized)
            response_status: HTTP response status
            response_time_ms: Response time in milliseconds
            ip_address: Client IP address
        """
        entry = self._create_entry(
            category=AuditCategory.API.value,
            action=f"{method} {endpoint}",
            details={
                "endpoint": endpoint,
                "method": method,
                "parameters": parameters,  # Will be sanitized by _create_entry
                "response_status": response_status,
                "response_time_ms": response_time_ms
            },
            user_id=user_id,
            ip_address=ip_address,
            success=response_status < 400
        )
        return self._write_entry(entry)

    def verify_chain_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the hash chain.

        Returns:
            Dict with 'valid' boolean and verification details
        """
        if not self.enable_hash_chain:
            return {"valid": True, "message": "Hash chain not enabled"}

        if not self._current_file or not self._current_file.exists():
            return {"valid": True, "entries_checked": 0}

        total = 0
        valid = 0
        invalid_entries = []
        prev_hash = None

        try:
            with open(self._current_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry_dict = json.loads(line)
                        total += 1

                        # Verify previous hash chain
                        stored_prev = entry_dict.get("previous_hash")
                        if stored_prev != prev_hash and line_num > 1:
                            invalid_entries.append({
                                "line": line_num,
                                "reason": "chain_broken"
                            })
                        else:
                            # Verify entry hash
                            stored_hash = entry_dict.get("entry_hash")
                            entry = AuditEntry(**{k: v for k, v in entry_dict.items()
                                                  if k in AuditEntry.__dataclass_fields__})
                            entry.entry_hash = None  # Clear for recomputation
                            entry.previous_hash = prev_hash
                            computed = entry.compute_hash(self._signing_key)

                            if stored_hash == computed:
                                valid += 1
                            else:
                                invalid_entries.append({
                                    "line": line_num,
                                    "reason": "hash_mismatch"
                                })

                        prev_hash = entry_dict.get("entry_hash")

                    except (json.JSONDecodeError, TypeError) as e:
                        invalid_entries.append({
                            "line": line_num,
                            "reason": f"parse_error: {str(e)}"
                        })

            return {
                "valid": len(invalid_entries) == 0,
                "entries_checked": total,
                "valid_entries": valid,
                "invalid_entries": invalid_entries[:10]  # First 10
            }

        except Exception as e:
            return {"valid": False, "error": str(e)}

    def query(
        self,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        admin_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Query audit log entries.

        Args:
            category: Filter by category
            user_id: Filter by user ID
            admin_id: Filter by admin ID
            start_time: Filter by start time
            end_time: Filter by end time
            action: Filter by action
            limit: Maximum entries to return

        Returns:
            List of matching entries
        """
        results = []

        # Get all log files in the directory
        log_files = sorted(self.log_dir.glob("audit_*.jsonl"), reverse=True)

        for log_file in log_files:
            if len(results) >= limit:
                break

            try:
                with open(log_file, 'r') as f:
                    for line in f:
                        if len(results) >= limit:
                            break

                        try:
                            entry = json.loads(line)

                            # Apply filters
                            if category and entry.get("category") != category:
                                continue
                            if user_id and entry.get("user_id") != user_id:
                                continue
                            if admin_id and entry.get("admin_id") != admin_id:
                                continue
                            if action and entry.get("action") != action:
                                continue

                            if start_time or end_time:
                                entry_time = datetime.fromisoformat(
                                    entry["timestamp"].replace("Z", "+00:00")
                                )
                                if start_time and entry_time < start_time.replace(tzinfo=timezone.utc):
                                    continue
                                if end_time and entry_time > end_time.replace(tzinfo=timezone.utc):
                                    continue

                            results.append(entry)

                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue

            except Exception as e:
                logger.warning(f"Error reading {log_file}: {e}")

        return results

    def generate_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Generate a compliance report for the given period.

        Args:
            start_date: Report period start
            end_date: Report period end

        Returns:
            Comprehensive compliance report
        """
        entries = self.query(start_time=start_date, end_time=end_date, limit=100000)

        # Aggregate statistics
        by_category = {}
        by_user = {}
        by_action = {}
        success_count = 0
        failure_count = 0

        for entry in entries:
            # By category
            cat = entry.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

            # By user
            user = entry.get("user_id") or entry.get("admin_id") or "system"
            by_user[user] = by_user.get(user, 0) + 1

            # By action
            action = entry.get("action", "unknown")
            by_action[action] = by_action.get(action, 0) + 1

            # Success/failure
            if entry.get("success", True):
                success_count += 1
            else:
                failure_count += 1

        total = len(entries)

        return {
            "report_generated": datetime.now(timezone.utc).isoformat(),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "total_events": total,
            "by_category": by_category,
            "by_user": dict(sorted(by_user.items(), key=lambda x: x[1], reverse=True)[:20]),
            "by_action": dict(sorted(by_action.items(), key=lambda x: x[1], reverse=True)[:20]),
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_count / total if total > 0 else 1.0,
            "chain_integrity": self.verify_chain_integrity()
        }


# Global instance
_audit_logger: Optional[ComprehensiveAuditLogger] = None


def get_comprehensive_audit_logger() -> ComprehensiveAuditLogger:
    """Get or create the global comprehensive audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = ComprehensiveAuditLogger()
    return _audit_logger
