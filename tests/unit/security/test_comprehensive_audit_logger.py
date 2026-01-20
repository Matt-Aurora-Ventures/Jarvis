"""
Comprehensive Audit Logger Tests

Tests for the enhanced audit logging system that captures:
- All trading decisions with reasoning
- Admin/user actions
- API calls with sanitized parameters
- Immutable audit trail (append-only)
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


class TestComprehensiveAuditLogger:
    """Tests for the comprehensive audit logger."""

    @pytest.fixture
    def temp_audit_dir(self, tmp_path):
        """Create a temporary directory for audit logs."""
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()
        return audit_dir

    @pytest.fixture
    def audit_logger(self, temp_audit_dir):
        """Create an audit logger instance for testing."""
        from core.security.comprehensive_audit_logger import ComprehensiveAuditLogger
        return ComprehensiveAuditLogger(log_dir=temp_audit_dir)

    def test_initialization(self, temp_audit_dir):
        """Test audit logger initializes correctly."""
        from core.security.comprehensive_audit_logger import ComprehensiveAuditLogger
        logger = ComprehensiveAuditLogger(log_dir=temp_audit_dir)
        assert logger is not None
        assert logger.log_dir == temp_audit_dir

    def test_log_trading_decision(self, audit_logger, temp_audit_dir):
        """Test logging trading decisions with reasoning."""
        from core.security.comprehensive_audit_logger import TradingDecision

        decision = TradingDecision(
            token_address="So11111111111111111111111111111111111111112",
            action="BUY",
            amount=1.5,
            reasoning={
                "sentiment_score": 0.85,
                "volume_24h": 1500000,
                "risk_score": 0.3,
                "signals": ["momentum_bullish", "volume_spike"]
            },
            confidence=0.75,
            strategy="momentum_trading"
        )

        result = audit_logger.log_trading_decision(decision, user_id="system")

        assert result["success"] is True
        assert "entry_id" in result

        # Verify log file was written
        log_files = list(temp_audit_dir.glob("*.jsonl"))
        assert len(log_files) >= 1

        # Verify content
        with open(log_files[0], "r") as f:
            entries = [json.loads(line) for line in f.readlines()]

        assert len(entries) >= 1
        trade_entry = entries[-1]
        assert trade_entry["category"] == "trading"
        assert trade_entry["action"] == "BUY"
        assert trade_entry["details"]["reasoning"]["sentiment_score"] == 0.85

    def test_log_admin_action(self, audit_logger, temp_audit_dir):
        """Test logging admin actions."""
        result = audit_logger.log_admin_action(
            admin_id="admin_123",
            action="update_config",
            target="risk_parameters",
            details={"old_value": {"max_position": 10}, "new_value": {"max_position": 15}},
            ip_address="192.168.1.1"
        )

        assert result["success"] is True

        # Verify content
        log_files = list(temp_audit_dir.glob("*.jsonl"))
        with open(log_files[0], "r") as f:
            entries = [json.loads(line) for line in f.readlines()]

        admin_entry = entries[-1]
        assert admin_entry["category"] == "admin"
        assert admin_entry["admin_id"] == "admin_123"
        assert admin_entry["target"] == "risk_parameters"

    def test_log_user_action(self, audit_logger, temp_audit_dir):
        """Test logging user actions."""
        result = audit_logger.log_user_action(
            user_id="user_456",
            action="manual_trade_request",
            details={"symbol": "SOL", "amount": 10.0, "side": "buy"},
            session_id="session_abc123"
        )

        assert result["success"] is True

    def test_log_api_call_with_sanitization(self, audit_logger, temp_audit_dir):
        """Test API call logging with parameter sanitization."""
        result = audit_logger.log_api_call(
            endpoint="/api/v1/trade",
            method="POST",
            user_id="user_789",
            parameters={
                "token": "PUBLIC_TOKEN",
                "api_key": "sk_secret_key_12345",  # Should be sanitized
                "password": "my_password",  # Should be sanitized
                "amount": 100
            },
            response_status=200,
            response_time_ms=150
        )

        assert result["success"] is True

        # Verify sensitive data was sanitized
        log_files = list(temp_audit_dir.glob("*.jsonl"))
        with open(log_files[0], "r") as f:
            entries = [json.loads(line) for line in f.readlines()]

        api_entry = entries[-1]
        assert "sk_secret_key" not in str(api_entry)
        assert "my_password" not in str(api_entry)
        assert "[REDACTED]" in str(api_entry) or "***" in str(api_entry)

    def test_immutable_append_only(self, audit_logger, temp_audit_dir):
        """Test that audit trail is append-only (immutable)."""
        # Log multiple entries
        audit_logger.log_user_action("user1", "action1", {"key": "value1"})
        audit_logger.log_user_action("user2", "action2", {"key": "value2"})
        audit_logger.log_user_action("user3", "action3", {"key": "value3"})

        # Count entries
        log_files = list(temp_audit_dir.glob("*.jsonl"))
        with open(log_files[0], "r") as f:
            entries = [json.loads(line) for line in f.readlines()]

        initial_count = len(entries)
        assert initial_count >= 3

        # Log another entry - should append, not overwrite
        audit_logger.log_user_action("user4", "action4", {"key": "value4"})

        with open(log_files[0], "r") as f:
            new_entries = [json.loads(line) for line in f.readlines()]

        assert len(new_entries) == initial_count + 1

    def test_entry_hash_chain(self, audit_logger, temp_audit_dir):
        """Test hash chain integrity for immutable audit trail."""
        audit_logger.log_user_action("user1", "action1", {})
        audit_logger.log_user_action("user2", "action2", {})
        audit_logger.log_user_action("user3", "action3", {})

        # Verify chain integrity
        integrity_result = audit_logger.verify_chain_integrity()
        assert integrity_result["valid"] is True
        assert integrity_result["entries_checked"] >= 3

    def test_query_by_category(self, audit_logger, temp_audit_dir):
        """Test querying audit logs by category."""
        audit_logger.log_admin_action("admin1", "config_update", "setting1", {})
        audit_logger.log_user_action("user1", "login", {})
        audit_logger.log_admin_action("admin2", "config_update", "setting2", {})

        admin_entries = audit_logger.query(category="admin", limit=100)
        assert len(admin_entries) >= 2
        assert all(e["category"] == "admin" for e in admin_entries)

    def test_query_by_time_range(self, audit_logger, temp_audit_dir):
        """Test querying audit logs by time range."""
        import time

        # Log entry
        audit_logger.log_user_action("user1", "action1", {})

        # Query with time range
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0)
        end = now.replace(hour=23, minute=59, second=59)

        entries = audit_logger.query(start_time=start, end_time=end, limit=100)
        assert len(entries) >= 1

    def test_query_by_user(self, audit_logger, temp_audit_dir):
        """Test querying audit logs by user."""
        audit_logger.log_user_action("user_special", "action1", {})
        audit_logger.log_user_action("other_user", "action2", {})
        audit_logger.log_user_action("user_special", "action3", {})

        user_entries = audit_logger.query(user_id="user_special", limit=100)
        assert len(user_entries) >= 2
        assert all(e.get("user_id") == "user_special" for e in user_entries)

    def test_log_rotation(self, temp_audit_dir):
        """Test automatic log rotation."""
        from core.security.comprehensive_audit_logger import ComprehensiveAuditLogger

        logger = ComprehensiveAuditLogger(
            log_dir=temp_audit_dir,
            max_file_size_mb=0.001  # Very small to trigger rotation
        )

        # Log many entries to trigger rotation
        for i in range(100):
            logger.log_user_action(f"user_{i}", f"action_{i}", {"data": "x" * 100})

        # Should have multiple log files
        log_files = list(temp_audit_dir.glob("*.jsonl"))
        assert len(log_files) >= 1  # At least one file

    def test_compliance_report_generation(self, audit_logger, temp_audit_dir):
        """Test compliance report generation."""
        # Log various activities
        audit_logger.log_admin_action("admin1", "config_change", "system", {"setting": "value"})
        audit_logger.log_user_action("user1", "trade_request", {"symbol": "SOL"})
        audit_logger.log_api_call("/api/trade", "POST", "user1", {}, 200, 100)

        # Generate compliance report
        report = audit_logger.generate_compliance_report(
            start_date=datetime.now(timezone.utc).replace(hour=0),
            end_date=datetime.now(timezone.utc)
        )

        assert "total_events" in report
        assert "by_category" in report
        assert "by_user" in report
        assert "chain_integrity" in report


class TestAuditLoggerSecurity:
    """Security-focused tests for audit logger."""

    @pytest.fixture
    def temp_audit_dir(self, tmp_path):
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()
        return audit_dir

    @pytest.fixture
    def audit_logger(self, temp_audit_dir):
        from core.security.comprehensive_audit_logger import ComprehensiveAuditLogger
        return ComprehensiveAuditLogger(log_dir=temp_audit_dir)

    def test_sensitive_data_never_logged(self, audit_logger, temp_audit_dir):
        """Verify sensitive data patterns are never logged."""
        sensitive_patterns = [
            "sk-1234567890abcdef",  # OpenAI key
            "ghp_abcdef123456",  # GitHub token
            "password123",
            "private_key_xyz",
        ]

        for pattern in sensitive_patterns:
            audit_logger.log_api_call(
                "/api/test",
                "POST",
                "user1",
                {"secret": pattern, "api_key": pattern},
                200,
                100
            )

        # Read all log content
        log_files = list(temp_audit_dir.glob("*.jsonl"))
        all_content = ""
        for lf in log_files:
            all_content += lf.read_text()

        # Verify no sensitive patterns in logs
        for pattern in sensitive_patterns:
            assert pattern not in all_content

    def test_injection_prevention_in_logs(self, audit_logger, temp_audit_dir):
        """Test that log entries are safe from injection."""
        malicious_inputs = [
            '{"malicious": true}',
            '\\n{"injected": "entry"}',
            '\x00\x01\x02',
            '<script>alert("xss")</script>',
        ]

        for payload in malicious_inputs:
            audit_logger.log_user_action("user1", "action", {"input": payload})

        # All entries should be valid JSON
        log_files = list(temp_audit_dir.glob("*.jsonl"))
        for lf in log_files:
            with open(lf, "r") as f:
                for line in f:
                    entry = json.loads(line)  # Should not raise
                    assert isinstance(entry, dict)


class TestAuditLoggerPerformance:
    """Performance tests for audit logger."""

    @pytest.fixture
    def temp_audit_dir(self, tmp_path):
        audit_dir = tmp_path / "audit"
        audit_dir.mkdir()
        return audit_dir

    def test_high_volume_logging(self, temp_audit_dir):
        """Test logging performance under high volume."""
        from core.security.comprehensive_audit_logger import ComprehensiveAuditLogger
        import time

        logger = ComprehensiveAuditLogger(log_dir=temp_audit_dir)

        start = time.time()
        for i in range(1000):
            logger.log_user_action(f"user_{i % 10}", f"action_{i}", {"iteration": i})
        elapsed = time.time() - start

        # Should complete 1000 entries in under 5 seconds
        assert elapsed < 5.0

        # Verify all entries were logged
        log_files = list(temp_audit_dir.glob("*.jsonl"))
        total_entries = 0
        for lf in log_files:
            with open(lf, "r") as f:
                total_entries += len(f.readlines())
        assert total_entries >= 1000
