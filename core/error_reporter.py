"""
Error Aggregation and Reporting - Track, aggregate, and report errors.
"""

import asyncio
import logging
import traceback
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from pathlib import Path
import json
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class ErrorRecord:
    """A single error occurrence."""
    id: Optional[int] = None
    timestamp: str = ""
    error_type: str = ""
    message: str = ""
    module: str = ""
    function: str = ""
    line_number: int = 0
    stack_trace: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""  # Hash for grouping similar errors
    severity: str = "ERROR"  # DEBUG, INFO, WARNING, ERROR, CRITICAL


@dataclass
class ErrorGroup:
    """Aggregated group of similar errors."""
    fingerprint: str
    error_type: str
    message: str
    count: int
    first_seen: str
    last_seen: str
    sample_trace: str
    affected_modules: List[str]
    is_resolved: bool = False
    resolution_notes: str = ""


@dataclass
class ErrorStats:
    """Statistics about errors."""
    total_errors: int
    unique_errors: int
    errors_by_severity: Dict[str, int]
    errors_by_module: Dict[str, int]
    errors_by_hour: Dict[int, int]
    top_errors: List[ErrorGroup]
    error_rate_per_minute: float


class ErrorDatabase:
    """SQLite storage for errors."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    error_type TEXT NOT NULL,
                    message TEXT,
                    module TEXT,
                    function TEXT,
                    line_number INTEGER,
                    stack_trace TEXT,
                    context_json TEXT,
                    fingerprint TEXT,
                    severity TEXT DEFAULT 'ERROR'
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_groups (
                    fingerprint TEXT PRIMARY KEY,
                    error_type TEXT,
                    message TEXT,
                    count INTEGER DEFAULT 1,
                    first_seen TEXT,
                    last_seen TEXT,
                    sample_trace TEXT,
                    affected_modules TEXT,
                    is_resolved INTEGER DEFAULT 0,
                    resolution_notes TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON errors(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_fingerprint ON errors(fingerprint)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_errors_severity ON errors(severity)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def record_error(self, error: ErrorRecord) -> int:
        """Record an error occurrence."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Insert error record
            cursor.execute("""
                INSERT INTO errors
                (timestamp, error_type, message, module, function, line_number,
                 stack_trace, context_json, fingerprint, severity)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                error.timestamp, error.error_type, error.message,
                error.module, error.function, error.line_number,
                error.stack_trace, json.dumps(error.context),
                error.fingerprint, error.severity
            ))

            # Update or create error group
            cursor.execute("""
                INSERT INTO error_groups
                (fingerprint, error_type, message, count, first_seen, last_seen,
                 sample_trace, affected_modules)
                VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    count = count + 1,
                    last_seen = excluded.last_seen,
                    affected_modules = CASE
                        WHEN affected_modules NOT LIKE '%' || excluded.affected_modules || '%'
                        THEN affected_modules || ',' || excluded.affected_modules
                        ELSE affected_modules
                    END
            """, (
                error.fingerprint, error.error_type, error.message[:200],
                error.timestamp, error.timestamp, error.stack_trace, error.module
            ))

            conn.commit()
            return cursor.lastrowid

    def get_recent_errors(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get recent errors."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM errors
                WHERE datetime(timestamp) > datetime('now', ?)
                ORDER BY timestamp DESC
                LIMIT ?
            """, (f'-{hours} hours', limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_error_groups(self, unresolved_only: bool = False) -> List[ErrorGroup]:
        """Get aggregated error groups."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM error_groups"
            if unresolved_only:
                query += " WHERE is_resolved = 0"
            query += " ORDER BY count DESC, last_seen DESC"

            cursor.execute(query)
            return [
                ErrorGroup(
                    fingerprint=row['fingerprint'],
                    error_type=row['error_type'],
                    message=row['message'],
                    count=row['count'],
                    first_seen=row['first_seen'],
                    last_seen=row['last_seen'],
                    sample_trace=row['sample_trace'],
                    affected_modules=row['affected_modules'].split(',') if row['affected_modules'] else [],
                    is_resolved=bool(row['is_resolved']),
                    resolution_notes=row['resolution_notes'] or ""
                )
                for row in cursor.fetchall()
            ]

    def mark_resolved(self, fingerprint: str, notes: str = ""):
        """Mark an error group as resolved."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE error_groups
                SET is_resolved = 1, resolution_notes = ?
                WHERE fingerprint = ?
            """, (notes, fingerprint))
            conn.commit()

    def get_stats(self, hours: int = 24) -> ErrorStats:
        """Get error statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total errors
            cursor.execute("""
                SELECT COUNT(*) as total FROM errors
                WHERE datetime(timestamp) > datetime('now', ?)
            """, (f'-{hours} hours',))
            total = cursor.fetchone()['total']

            # Unique errors
            cursor.execute("""
                SELECT COUNT(DISTINCT fingerprint) as unique_count FROM errors
                WHERE datetime(timestamp) > datetime('now', ?)
            """, (f'-{hours} hours',))
            unique = cursor.fetchone()['unique_count']

            # By severity
            cursor.execute("""
                SELECT severity, COUNT(*) as count FROM errors
                WHERE datetime(timestamp) > datetime('now', ?)
                GROUP BY severity
            """, (f'-{hours} hours',))
            by_severity = {row['severity']: row['count'] for row in cursor.fetchall()}

            # By module
            cursor.execute("""
                SELECT module, COUNT(*) as count FROM errors
                WHERE datetime(timestamp) > datetime('now', ?)
                GROUP BY module
                ORDER BY count DESC
                LIMIT 10
            """, (f'-{hours} hours',))
            by_module = {row['module']: row['count'] for row in cursor.fetchall()}

            # By hour
            cursor.execute("""
                SELECT strftime('%H', timestamp) as hour, COUNT(*) as count FROM errors
                WHERE datetime(timestamp) > datetime('now', ?)
                GROUP BY hour
            """, (f'-{hours} hours',))
            by_hour = {int(row['hour']): row['count'] for row in cursor.fetchall()}

            # Top errors
            top_errors = self.get_error_groups(unresolved_only=True)[:5]

            # Error rate
            rate = total / (hours * 60) if hours > 0 else 0

            return ErrorStats(
                total_errors=total,
                unique_errors=unique,
                errors_by_severity=by_severity,
                errors_by_module=by_module,
                errors_by_hour=by_hour,
                top_errors=top_errors,
                error_rate_per_minute=rate
            )

    def cleanup_old_errors(self, days: int = 30):
        """Delete errors older than specified days."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM errors
                WHERE datetime(timestamp) < datetime('now', ?)
            """, (f'-{days} days',))
            deleted = cursor.rowcount
            conn.commit()
            logger.info(f"Cleaned up {deleted} old error records")
            return deleted


class ErrorReporter:
    """
    Central error reporting and aggregation.

    Usage:
        reporter = ErrorReporter()

        # Automatic capture
        try:
            risky_operation()
        except Exception as e:
            reporter.capture_exception(e, context={"user_id": 123})

        # Get report
        stats = reporter.get_stats()
        report = reporter.generate_report()
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "errors.db"
        self.db = ErrorDatabase(db_path)
        self._alert_handlers: List[Callable] = []
        self._alert_threshold = 10  # Errors per minute to trigger alert
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._last_alert_time: Optional[datetime] = None

    def capture_exception(
        self,
        exc: Exception,
        context: Dict[str, Any] = None,
        severity: str = "ERROR"
    ) -> ErrorRecord:
        """Capture and record an exception."""
        # Extract info from exception
        tb = traceback.extract_tb(exc.__traceback__)
        if tb:
            last_frame = tb[-1]
            module = last_frame.filename
            function = last_frame.name
            line_number = last_frame.lineno
        else:
            module = function = ""
            line_number = 0

        # Generate fingerprint for grouping
        fingerprint = self._generate_fingerprint(exc, module, function)

        error = ErrorRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_type=type(exc).__name__,
            message=str(exc),
            module=module,
            function=function,
            line_number=line_number,
            stack_trace=traceback.format_exc(),
            context=context or {},
            fingerprint=fingerprint,
            severity=severity
        )

        self.db.record_error(error)
        self._check_alert_threshold(error)

        return error

    def capture_message(
        self,
        message: str,
        severity: str = "WARNING",
        module: str = "",
        context: Dict[str, Any] = None
    ) -> ErrorRecord:
        """Capture a warning or info message."""
        fingerprint = hashlib.md5(f"{message}:{module}".encode()).hexdigest()[:12]

        error = ErrorRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            error_type="Message",
            message=message,
            module=module,
            context=context or {},
            fingerprint=fingerprint,
            severity=severity
        )

        self.db.record_error(error)
        return error

    def _generate_fingerprint(self, exc: Exception, module: str, function: str) -> str:
        """Generate a fingerprint for error grouping."""
        components = [
            type(exc).__name__,
            module,
            function,
            str(exc)[:100]  # First 100 chars of message
        ]
        return hashlib.md5(":".join(components).encode()).hexdigest()[:12]

    def _check_alert_threshold(self, error: ErrorRecord):
        """Check if we should send an alert."""
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y%m%d%H%M")

        self._error_counts[minute_key] += 1

        # Clean old counts
        cutoff = (now - timedelta(minutes=5)).strftime("%Y%m%d%H%M")
        self._error_counts = {
            k: v for k, v in self._error_counts.items() if k >= cutoff
        }

        # Check threshold
        current_count = self._error_counts[minute_key]
        if current_count >= self._alert_threshold:
            # Rate limit alerts to once per 5 minutes
            if (self._last_alert_time is None or
                (now - self._last_alert_time).total_seconds() > 300):
                self._send_alert(current_count)
                self._last_alert_time = now

    def _send_alert(self, error_count: int):
        """Send alert to registered handlers."""
        for handler in self._alert_handlers:
            try:
                handler(f"High error rate detected: {error_count} errors in last minute")
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

    def add_alert_handler(self, handler: Callable):
        """Add a handler for error alerts."""
        self._alert_handlers.append(handler)

    def get_stats(self, hours: int = 24) -> ErrorStats:
        """Get error statistics."""
        return self.db.get_stats(hours)

    def get_recent_errors(self, hours: int = 24, limit: int = 100) -> List[Dict]:
        """Get recent errors."""
        return self.db.get_recent_errors(hours, limit)

    def get_error_groups(self, unresolved_only: bool = True) -> List[ErrorGroup]:
        """Get aggregated error groups."""
        return self.db.get_error_groups(unresolved_only)

    def mark_resolved(self, fingerprint: str, notes: str = ""):
        """Mark an error group as resolved."""
        self.db.mark_resolved(fingerprint, notes)

    def generate_report(self, hours: int = 24) -> str:
        """Generate a text error report."""
        stats = self.get_stats(hours)

        lines = [
            f"Error Report - Last {hours} Hours",
            "=" * 40,
            f"Total Errors: {stats.total_errors}",
            f"Unique Errors: {stats.unique_errors}",
            f"Error Rate: {stats.error_rate_per_minute:.2f}/minute",
            "",
            "By Severity:",
        ]

        for severity, count in stats.errors_by_severity.items():
            lines.append(f"  {severity}: {count}")

        lines.extend(["", "By Module:"])
        for module, count in list(stats.errors_by_module.items())[:5]:
            lines.append(f"  {module}: {count}")

        if stats.top_errors:
            lines.extend(["", "Top Unresolved Errors:"])
            for i, group in enumerate(stats.top_errors[:5], 1):
                lines.append(f"  {i}. [{group.count}x] {group.error_type}: {group.message[:50]}")

        return "\n".join(lines)

    def generate_json_report(self, hours: int = 24) -> Dict:
        """Generate a JSON error report."""
        stats = self.get_stats(hours)
        return {
            'period_hours': hours,
            'total_errors': stats.total_errors,
            'unique_errors': stats.unique_errors,
            'error_rate_per_minute': stats.error_rate_per_minute,
            'by_severity': stats.errors_by_severity,
            'by_module': stats.errors_by_module,
            'by_hour': stats.errors_by_hour,
            'top_errors': [
                {
                    'fingerprint': g.fingerprint,
                    'type': g.error_type,
                    'message': g.message,
                    'count': g.count,
                    'first_seen': g.first_seen,
                    'last_seen': g.last_seen
                }
                for g in stats.top_errors
            ]
        }


# === LOGGING INTEGRATION ===

class ErrorReportingHandler(logging.Handler):
    """Logging handler that sends errors to ErrorReporter."""

    def __init__(self, reporter: ErrorReporter, level: int = logging.ERROR):
        super().__init__(level)
        self.reporter = reporter

    def emit(self, record: logging.LogRecord):
        """Process a log record."""
        if record.exc_info:
            exc = record.exc_info[1]
            if exc:
                self.reporter.capture_exception(
                    exc,
                    context={
                        'logger': record.name,
                        'pathname': record.pathname,
                        'lineno': record.lineno
                    },
                    severity=record.levelname
                )
        elif record.levelno >= logging.WARNING:
            self.reporter.capture_message(
                record.getMessage(),
                severity=record.levelname,
                module=record.pathname
            )


# Singleton
_reporter: Optional[ErrorReporter] = None

def get_error_reporter() -> ErrorReporter:
    """Get singleton error reporter."""
    global _reporter
    if _reporter is None:
        _reporter = ErrorReporter()
    return _reporter


def setup_error_reporting(logger_instance: logging.Logger = None):
    """Setup error reporting with logging integration."""
    reporter = get_error_reporter()
    handler = ErrorReportingHandler(reporter)

    if logger_instance:
        logger_instance.addHandler(handler)
    else:
        logging.getLogger().addHandler(handler)

    return reporter
