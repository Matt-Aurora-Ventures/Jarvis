"""
Comprehensive tests for core/audit/ security logging system.

Tests cover:
- AuditLogger (logger.py)
- AuditStore, FileAuditStore, JSONAuditStore (storage.py)
- RetentionPolicy (retention.py)
- Report generation and anomaly detection (reports.py)
"""

import pytest
import json
import gzip
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List


# ==============================================================================
# Test: AuditLogger (core/audit/logger.py)
# ==============================================================================

class TestAuditEntry:
    """Tests for AuditEntry dataclass."""

    def test_entry_creation(self):
        """Test creating an audit entry with required fields."""
        from core.audit.logger import AuditEntry

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            actor="user123",
            action="login",
            resource="auth_system",
            details={"ip": "192.168.1.1"}
        )

        assert entry.actor == "user123"
        assert entry.action == "login"
        assert entry.resource == "auth_system"
        assert entry.details["ip"] == "192.168.1.1"

    def test_entry_to_dict(self):
        """Test converting entry to dictionary."""
        from core.audit.logger import AuditEntry

        now = datetime.now(timezone.utc)
        entry = AuditEntry(
            timestamp=now,
            actor="admin",
            action="delete",
            resource="user/456",
            details={"reason": "inactive"}
        )

        d = entry.to_dict()
        assert isinstance(d, dict)
        assert d["actor"] == "admin"
        assert d["action"] == "delete"
        assert "timestamp" in d

    def test_entry_optional_fields(self):
        """Test entry with optional fields."""
        from core.audit.logger import AuditEntry

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            actor="system",
            action="cleanup",
            resource="temp_files",
            details={},
            success=True,
            error_message=None,
            ip_address="127.0.0.1",
            session_id="sess_abc123"
        )

        assert entry.success is True
        assert entry.error_message is None
        assert entry.ip_address == "127.0.0.1"
        assert entry.session_id == "sess_abc123"


class TestAuditLogger:
    """Tests for AuditLogger class."""

    def test_logger_initialization(self, tmp_path):
        """Test AuditLogger initializes correctly."""
        from core.audit.logger import AuditLogger

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        assert logger.log_dir == log_dir
        assert log_dir.exists()

    def test_logger_default_path(self):
        """Test AuditLogger uses default path when none provided."""
        from core.audit.logger import AuditLogger

        with patch.object(Path, 'mkdir'):
            logger = AuditLogger()
            assert "audit" in str(logger.log_dir)

    def test_log_action(self, tmp_path):
        """Test log_action method."""
        from core.audit.logger import AuditLogger

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_action(
            actor="user123",
            action="create_post",
            resource="posts/789",
            details={"title": "Hello World"}
        )

        # Verify log was written
        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) >= 1

        with open(log_files[0]) as f:
            entry = json.loads(f.readline())
            assert entry["actor"] == "user123"
            assert entry["action"] == "create_post"
            assert entry["resource"] == "posts/789"

    def test_log_access_granted(self, tmp_path):
        """Test log_access with granted=True."""
        from core.audit.logger import AuditLogger

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_access(
            user="user456",
            resource="secret/keys",
            granted=True
        )

        log_files = list(log_dir.glob("*.jsonl"))
        with open(log_files[0]) as f:
            entry = json.loads(f.readline())
            assert entry["actor"] == "user456"
            assert entry["action"] == "access"
            assert entry["details"]["granted"] is True

    def test_log_access_denied(self, tmp_path):
        """Test log_access with granted=False."""
        from core.audit.logger import AuditLogger

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_access(
            user="hacker",
            resource="admin/panel",
            granted=False
        )

        log_files = list(log_dir.glob("*.jsonl"))
        with open(log_files[0]) as f:
            entry = json.loads(f.readline())
            assert entry["details"]["granted"] is False

    def test_log_change(self, tmp_path):
        """Test log_change method."""
        from core.audit.logger import AuditLogger

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_change(
            entity="user/123",
            field="email",
            old="old@example.com",
            new="new@example.com"
        )

        log_files = list(log_dir.glob("*.jsonl"))
        with open(log_files[0]) as f:
            entry = json.loads(f.readline())
            assert entry["action"] == "change"
            assert entry["details"]["field"] == "email"
            assert entry["details"]["old_value"] == "old@example.com"
            assert entry["details"]["new_value"] == "new@example.com"

    def test_log_error(self, tmp_path):
        """Test log_error method."""
        from core.audit.logger import AuditLogger

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        logger.log_error(
            error="Connection timeout",
            context={"endpoint": "/api/trade", "timeout_ms": 5000}
        )

        log_files = list(log_dir.glob("*.jsonl"))
        with open(log_files[0]) as f:
            entry = json.loads(f.readline())
            assert entry["action"] == "error"
            assert entry["details"]["error"] == "Connection timeout"
            assert entry["details"]["context"]["endpoint"] == "/api/trade"

    def test_log_error_with_exception(self, tmp_path):
        """Test log_error with an exception object."""
        from core.audit.logger import AuditLogger

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        try:
            raise ValueError("Invalid amount")
        except ValueError as e:
            logger.log_error(
                error=e,
                context={"operation": "buy_token"}
            )

        log_files = list(log_dir.glob("*.jsonl"))
        with open(log_files[0]) as f:
            entry = json.loads(f.readline())
            assert "ValueError" in entry["details"]["error"]

    def test_multiple_log_entries(self, tmp_path):
        """Test writing multiple log entries."""
        from core.audit.logger import AuditLogger

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        for i in range(10):
            logger.log_action(
                actor=f"user{i}",
                action="test_action",
                resource=f"resource/{i}",
                details={"index": i}
            )

        log_files = list(log_dir.glob("*.jsonl"))
        with open(log_files[0]) as f:
            lines = f.readlines()
            assert len(lines) == 10

    def test_logger_thread_safety(self, tmp_path):
        """Test logger is thread-safe."""
        from core.audit.logger import AuditLogger
        import threading

        log_dir = tmp_path / "audit"
        logger = AuditLogger(log_dir=log_dir)

        errors = []

        def log_entries(thread_id):
            try:
                for i in range(50):
                    logger.log_action(
                        actor=f"thread_{thread_id}",
                        action="concurrent_write",
                        resource=f"item/{i}",
                        details={"thread": thread_id, "seq": i}
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=log_entries, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

        # Verify all entries were written
        log_files = list(log_dir.glob("*.jsonl"))
        total_lines = 0
        for lf in log_files:
            with open(lf) as f:
                total_lines += len(f.readlines())
        assert total_lines == 250  # 5 threads * 50 entries


class TestAuditLoggerSingleton:
    """Tests for global AuditLogger singleton."""

    def test_get_audit_logger(self):
        """Test getting global audit logger."""
        from core.audit.logger import get_audit_logger

        logger1 = get_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is logger2


# ==============================================================================
# Test: AuditStore (core/audit/storage.py)
# ==============================================================================

class TestAuditStoreAbstract:
    """Tests for AuditStore abstract base class."""

    def test_abstract_methods(self):
        """Test that AuditStore cannot be instantiated directly."""
        from core.audit.storage import AuditStore

        with pytest.raises(TypeError):
            AuditStore()

    def test_abstract_write(self):
        """Test write is abstract."""
        from core.audit.storage import AuditStore
        import abc

        assert hasattr(AuditStore.write, '__isabstractmethod__')

    def test_abstract_get_logs(self):
        """Test get_logs is abstract."""
        from core.audit.storage import AuditStore

        assert hasattr(AuditStore.get_logs, '__isabstractmethod__')


class TestFileAuditStore:
    """Tests for FileAuditStore - append-only file storage."""

    def test_initialization(self, tmp_path):
        """Test FileAuditStore initialization."""
        from core.audit.storage import FileAuditStore

        store = FileAuditStore(base_dir=tmp_path / "audit")
        assert store.base_dir.exists()

    def test_write_entry(self, tmp_path):
        """Test writing an entry to file store."""
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            actor="test_user",
            action="test_action",
            resource="test_resource",
            details={"key": "value"}
        )

        store.write(entry)

        # Verify file was created
        files = list(store.base_dir.glob("*.jsonl"))
        assert len(files) == 1

    def test_append_only(self, tmp_path):
        """Test that FileAuditStore is append-only."""
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        for i in range(5):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor=f"user_{i}",
                action="append_test",
                resource="resource",
                details={}
            )
            store.write(entry)

        files = list(store.base_dir.glob("*.jsonl"))
        with open(files[0]) as f:
            lines = f.readlines()
            assert len(lines) == 5

    def test_get_logs_no_filter(self, tmp_path):
        """Test get_logs returns all entries when no filter."""
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        for i in range(3):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor=f"user_{i}",
                action="action",
                resource="resource",
                details={}
            )
            store.write(entry)

        logs = store.get_logs()
        assert len(logs) == 3

    def test_get_logs_with_actor_filter(self, tmp_path):
        """Test get_logs with actor filter."""
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        for actor in ["alice", "bob", "alice"]:
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor=actor,
                action="action",
                resource="resource",
                details={}
            )
            store.write(entry)

        logs = store.get_logs(filters={"actor": "alice"})
        assert len(logs) == 2
        assert all(e["actor"] == "alice" for e in logs)

    def test_get_logs_with_action_filter(self, tmp_path):
        """Test get_logs with action filter."""
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        for action in ["login", "logout", "login"]:
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor="user",
                action=action,
                resource="auth",
                details={}
            )
            store.write(entry)

        logs = store.get_logs(filters={"action": "login"})
        assert len(logs) == 2

    def test_get_logs_with_time_range(self, tmp_path):
        """Test get_logs with time range filter."""
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        now = datetime.now(timezone.utc)

        # Write entries at different times
        for i, offset in enumerate([-2, -1, 0]):
            entry = AuditEntry(
                timestamp=now + timedelta(hours=offset),
                actor=f"user_{i}",
                action="action",
                resource="resource",
                details={}
            )
            store.write(entry)

        # Get logs from last hour
        logs = store.get_logs(filters={
            "start_time": now - timedelta(hours=1),
            "end_time": now + timedelta(hours=1)
        })

        assert len(logs) == 2  # Only entries from -1h and now

    def test_get_logs_with_limit(self, tmp_path):
        """Test get_logs respects limit."""
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        for i in range(10):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor="user",
                action="action",
                resource="resource",
                details={}
            )
            store.write(entry)

        logs = store.get_logs(limit=5)
        assert len(logs) == 5

    def test_export_json(self, tmp_path):
        """Test export to JSON format."""
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        for i in range(3):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor=f"user_{i}",
                action="action",
                resource="resource",
                details={}
            )
            store.write(entry)

        export_path = tmp_path / "export.json"
        store.export(
            format="json",
            output_path=export_path,
            date_range=(
                datetime.now(timezone.utc) - timedelta(days=1),
                datetime.now(timezone.utc) + timedelta(days=1)
            )
        )

        assert export_path.exists()
        with open(export_path) as f:
            data = json.load(f)
            assert len(data["entries"]) == 3

    def test_export_csv(self, tmp_path):
        """Test export to CSV format."""
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            actor="user",
            action="action",
            resource="resource",
            details={}
        )
        store.write(entry)

        export_path = tmp_path / "export.csv"
        store.export(
            format="csv",
            output_path=export_path,
            date_range=(
                datetime.now(timezone.utc) - timedelta(days=1),
                datetime.now(timezone.utc) + timedelta(days=1)
            )
        )

        assert export_path.exists()
        with open(export_path) as f:
            lines = f.readlines()
            assert len(lines) >= 2  # header + 1 entry


class TestJSONAuditStore:
    """Tests for JSONAuditStore - structured JSON storage."""

    def test_initialization(self, tmp_path):
        """Test JSONAuditStore initialization."""
        from core.audit.storage import JSONAuditStore

        store = JSONAuditStore(base_dir=tmp_path / "audit")
        assert store.base_dir.exists()

    def test_write_creates_daily_file(self, tmp_path):
        """Test JSONAuditStore creates daily JSON files."""
        from core.audit.storage import JSONAuditStore
        from core.audit.logger import AuditEntry

        store = JSONAuditStore(base_dir=tmp_path / "audit")

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            actor="user",
            action="action",
            resource="resource",
            details={}
        )
        store.write(entry)

        # Should create a dated JSON file
        today = datetime.now(timezone.utc).strftime("%Y%m%d")
        expected_file = tmp_path / "audit" / f"audit_{today}.json"
        assert expected_file.exists()

    def test_structured_json_format(self, tmp_path):
        """Test JSONAuditStore writes structured JSON."""
        from core.audit.storage import JSONAuditStore
        from core.audit.logger import AuditEntry

        store = JSONAuditStore(base_dir=tmp_path / "audit")

        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc),
            actor="user",
            action="action",
            resource="resource",
            details={"key": "value"}
        )
        store.write(entry)

        files = list(store.base_dir.glob("*.json"))
        with open(files[0]) as f:
            data = json.load(f)
            assert "entries" in data
            assert "metadata" in data
            assert len(data["entries"]) == 1

    def test_get_logs(self, tmp_path):
        """Test get_logs from JSON store."""
        from core.audit.storage import JSONAuditStore
        from core.audit.logger import AuditEntry

        store = JSONAuditStore(base_dir=tmp_path / "audit")

        for i in range(3):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor=f"user_{i}",
                action="action",
                resource="resource",
                details={}
            )
            store.write(entry)

        logs = store.get_logs()
        assert len(logs) == 3


# ==============================================================================
# Test: RetentionPolicy (core/audit/retention.py)
# ==============================================================================

class TestRetentionPolicy:
    """Tests for RetentionPolicy class."""

    def test_default_retention_days(self):
        """Test default retention is 90 days."""
        from core.audit.retention import RetentionPolicy

        policy = RetentionPolicy()
        assert policy.retain_days == 90

    def test_custom_retention_days(self):
        """Test custom retention period."""
        from core.audit.retention import RetentionPolicy

        policy = RetentionPolicy(retain_days=30)
        assert policy.retain_days == 30

    def test_archive_old_logs(self, tmp_path):
        """Test archive_old_logs archives logs older than threshold."""
        from core.audit.retention import RetentionPolicy

        # Create old log file
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()

        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y%m%d")
        old_file = audit_dir / f"audit_{old_date}.jsonl"
        old_file.write_text('{"test": "data"}\n')

        policy = RetentionPolicy(retain_days=90, audit_dir=audit_dir)
        archived = policy.archive_old_logs()

        assert len(archived) == 1
        assert not old_file.exists()
        # Archived file should exist
        archive_dir = audit_dir / "archive"
        assert archive_dir.exists()

    def test_archive_keeps_recent_logs(self, tmp_path):
        """Test archive_old_logs keeps recent logs."""
        from core.audit.retention import RetentionPolicy

        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()

        # Create recent log file
        today = datetime.now().strftime("%Y%m%d")
        recent_file = audit_dir / f"audit_{today}.jsonl"
        recent_file.write_text('{"test": "data"}\n')

        policy = RetentionPolicy(retain_days=90, audit_dir=audit_dir)
        archived = policy.archive_old_logs()

        assert len(archived) == 0
        assert recent_file.exists()

    def test_delete_expired_logs(self, tmp_path):
        """Test delete_expired_logs removes very old archives."""
        from core.audit.retention import RetentionPolicy

        audit_dir = tmp_path / "audit"
        archive_dir = audit_dir / "archive"
        archive_dir.mkdir(parents=True)

        # Create very old archive (older than 2x retention)
        old_date = (datetime.now() - timedelta(days=200)).strftime("%Y%m%d")
        old_archive = archive_dir / f"audit_{old_date}.jsonl.gz"
        old_archive.write_bytes(gzip.compress(b'{"test": "data"}\n'))

        policy = RetentionPolicy(retain_days=90, audit_dir=audit_dir)
        deleted = policy.delete_expired_logs()

        assert len(deleted) == 1
        assert not old_archive.exists()

    def test_compress_archived(self, tmp_path):
        """Test compress_archived compresses archive files."""
        from core.audit.retention import RetentionPolicy

        audit_dir = tmp_path / "audit"
        archive_dir = audit_dir / "archive"
        archive_dir.mkdir(parents=True)

        # Create uncompressed archive file
        uncompressed = archive_dir / "audit_20250101.jsonl"
        test_data = '{"test": "data"}\n' * 100
        uncompressed.write_text(test_data)

        policy = RetentionPolicy(retain_days=90, audit_dir=audit_dir)
        compressed = policy.compress_archived()

        assert len(compressed) == 1
        assert not uncompressed.exists()
        compressed_file = archive_dir / "audit_20250101.jsonl.gz"
        assert compressed_file.exists()

    def test_run_retention_policy(self, tmp_path):
        """Test running full retention policy."""
        from core.audit.retention import RetentionPolicy

        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()

        # Create mix of old and new files
        today = datetime.now().strftime("%Y%m%d")
        old_date = (datetime.now() - timedelta(days=100)).strftime("%Y%m%d")

        (audit_dir / f"audit_{today}.jsonl").write_text('{"recent": true}\n')
        (audit_dir / f"audit_{old_date}.jsonl").write_text('{"old": true}\n')

        policy = RetentionPolicy(retain_days=90, audit_dir=audit_dir)
        result = policy.run()

        assert "archived" in result
        assert "deleted" in result
        assert "compressed" in result


# ==============================================================================
# Test: Reports (core/audit/reports.py)
# ==============================================================================

class TestDailyReport:
    """Tests for generate_daily_report function."""

    def test_generate_daily_report(self, tmp_path):
        """Test generating a daily report."""
        from core.audit.reports import generate_daily_report
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        # Add some test entries
        for i in range(5):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor=f"user_{i % 2}",
                action="login" if i % 2 == 0 else "logout",
                resource="auth",
                details={}
            )
            store.write(entry)

        report = generate_daily_report(store)

        assert "date" in report
        assert "total_events" in report
        assert report["total_events"] == 5
        assert "by_actor" in report
        assert "by_action" in report

    def test_daily_report_empty(self, tmp_path):
        """Test daily report with no events."""
        from core.audit.reports import generate_daily_report
        from core.audit.storage import FileAuditStore

        store = FileAuditStore(base_dir=tmp_path / "audit")

        report = generate_daily_report(store)

        assert report["total_events"] == 0


class TestSecurityReport:
    """Tests for generate_security_report function."""

    def test_generate_security_report(self, tmp_path):
        """Test generating a security report."""
        from core.audit.reports import generate_security_report
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        # Add security-relevant entries
        for i in range(3):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor="user",
                action="access",
                resource="secret/keys",
                details={"granted": i % 2 == 0}
            )
            store.write(entry)

        report = generate_security_report(store)

        assert "access_denied_count" in report
        assert "access_granted_count" in report
        assert "sensitive_resource_access" in report

    def test_security_report_failed_logins(self, tmp_path):
        """Test security report counts failed logins."""
        from core.audit.reports import generate_security_report
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        # Add failed login attempts
        for i in range(5):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor="attacker",
                action="login",
                resource="auth",
                details={"granted": False},
                success=False
            )
            store.write(entry)

        report = generate_security_report(store)

        assert report["failed_login_count"] >= 5


class TestAnomalyDetection:
    """Tests for detect_anomalies function."""

    def test_detect_high_frequency_actor(self, tmp_path):
        """Test detecting high-frequency actor activity."""
        from core.audit.reports import detect_anomalies
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        # Simulate rapid activity from one actor
        for i in range(100):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor="suspicious_user",
                action="api_call",
                resource="api/data",
                details={}
            )
            store.write(entry)

        anomalies = detect_anomalies(store, window_minutes=60)

        assert len(anomalies) > 0
        assert any(a["type"] == "high_frequency" for a in anomalies)

    def test_detect_unusual_access_pattern(self, tmp_path):
        """Test detecting unusual access patterns."""
        from core.audit.reports import detect_anomalies
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        # Multiple access denied events
        for i in range(10):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor="user",
                action="access",
                resource="admin/secrets",
                details={"granted": False}
            )
            store.write(entry)

        anomalies = detect_anomalies(store, window_minutes=60)

        assert any(a["type"] == "access_denied_spike" for a in anomalies)

    def test_no_anomalies_normal_activity(self, tmp_path):
        """Test no anomalies for normal activity."""
        from core.audit.reports import detect_anomalies
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        # Normal activity
        for i in range(5):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor=f"user_{i}",
                action="normal_action",
                resource="resource",
                details={}
            )
            store.write(entry)

        anomalies = detect_anomalies(store, window_minutes=60)

        # Should have no or few anomalies
        assert len(anomalies) == 0 or all(a["severity"] == "low" for a in anomalies)


class TestAlertOnSuspicious:
    """Tests for alert_on_suspicious function."""

    def test_alert_triggered(self, tmp_path):
        """Test that alerts are triggered for suspicious activity."""
        from core.audit.reports import alert_on_suspicious, AlertCallback
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        # Add suspicious activity
        for i in range(20):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor="attacker",
                action="login",
                resource="auth",
                details={"granted": False},
                success=False
            )
            store.write(entry)

        alerts_received = []

        def callback(alert: Dict[str, Any]):
            alerts_received.append(alert)

        alert_on_suspicious(store, callback=callback)

        assert len(alerts_received) > 0

    def test_alert_with_threshold(self, tmp_path):
        """Test alert threshold configuration."""
        from core.audit.reports import alert_on_suspicious
        from core.audit.storage import FileAuditStore
        from core.audit.logger import AuditEntry

        store = FileAuditStore(base_dir=tmp_path / "audit")

        # Add activity below threshold
        for i in range(3):
            entry = AuditEntry(
                timestamp=datetime.now(timezone.utc),
                actor="user",
                action="login",
                resource="auth",
                details={"granted": False},
                success=False
            )
            store.write(entry)

        alerts_received = []

        def callback(alert: Dict[str, Any]):
            alerts_received.append(alert)

        # Set high threshold
        alert_on_suspicious(store, callback=callback, threshold=10)

        # Should not trigger alert
        assert len(alerts_received) == 0


# ==============================================================================
# Test: Integration
# ==============================================================================

class TestIntegration:
    """Integration tests for the complete audit system."""

    def test_full_workflow(self, tmp_path):
        """Test complete audit workflow."""
        from core.audit.logger import AuditLogger
        from core.audit.storage import FileAuditStore
        from core.audit.retention import RetentionPolicy
        from core.audit.reports import generate_daily_report

        audit_dir = tmp_path / "audit"

        # Create logger with file store
        logger = AuditLogger(log_dir=audit_dir)
        store = FileAuditStore(base_dir=audit_dir)

        # Log various actions
        logger.log_action("admin", "create_user", "users/new", {"email": "new@test.com"})
        logger.log_access("user1", "documents/secret", granted=True)
        logger.log_change("settings", "theme", "light", "dark")
        logger.log_error("Database timeout", {"query": "SELECT *"})

        # Generate report
        report = generate_daily_report(store)

        assert report["total_events"] == 4

        # Run retention (should not archive new logs)
        policy = RetentionPolicy(retain_days=90, audit_dir=audit_dir)
        result = policy.run()

        assert len(result["archived"]) == 0

    def test_audit_log_location(self, tmp_path):
        """Test audit logs go to correct location."""
        from core.audit.logger import AuditLogger

        # Use bots/logs/audit path
        audit_path = tmp_path / "bots" / "logs" / "audit"
        logger = AuditLogger(log_dir=audit_path)

        logger.log_action("test", "test", "test", {})

        assert audit_path.exists()
        assert len(list(audit_path.glob("*.jsonl"))) >= 1
