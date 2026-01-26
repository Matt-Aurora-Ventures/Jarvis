"""
Unit Tests for core/security/audit_logger.py

Comprehensive tests for the immutable audit logging system:
- Audit event creation and logging
- HMAC signature generation and verification
- Log storage (append-only behavior)
- Query and retrieval operations
- Integrity verification
- Convenience functions and global logger

Target: 85%+ code coverage
"""

import pytest
import json
import hashlib
import hmac
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, mock_open
from dataclasses import asdict


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_audit_dir(tmp_path):
    """Create a temporary directory for audit logs."""
    audit_dir = tmp_path / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir


@pytest.fixture
def temp_audit_file(tmp_path):
    """Create a temporary audit log file path."""
    return tmp_path / "test_audit.log"


@pytest.fixture
def audit_logger(temp_audit_file):
    """Create an AuditLogger instance without signing."""
    from core.security.audit_logger import AuditLogger
    return AuditLogger(log_path=temp_audit_file, sign_entries=False)


@pytest.fixture
def signed_audit_logger(temp_audit_file, monkeypatch):
    """Create an AuditLogger with signing enabled."""
    from core.security.audit_logger import AuditLogger
    monkeypatch.setenv("JARVIS_AUDIT_KEY", "test-signing-key-12345")
    return AuditLogger(log_path=temp_audit_file, sign_entries=True)


@pytest.fixture
def sample_audit_details():
    """Sample audit event details."""
    return {
        "token": "SOL",
        "amount": 100.0,
        "price": 150.25,
        "reason": "momentum_signal"
    }


@pytest.fixture
def reset_global_logger():
    """Reset the global audit logger between tests."""
    import core.security.audit_logger as module
    original = module._audit_logger
    yield
    module._audit_logger = original


# =============================================================================
# AuditEventType Tests
# =============================================================================

class TestAuditEventType:
    """Tests for AuditEventType enum."""

    def test_event_type_values(self):
        """Test all event type values are correct strings."""
        from core.security.audit_logger import AuditEventType

        assert AuditEventType.ADMIN_ACTION.value == "admin_action"
        assert AuditEventType.KEY_ROTATION.value == "key_rotation"
        assert AuditEventType.CONFIG_CHANGE.value == "config_change"
        assert AuditEventType.MANUAL_TRADE.value == "manual_trade"
        assert AuditEventType.FEATURE_FLAG.value == "feature_flag"
        assert AuditEventType.SECURITY_EVENT.value == "security_event"
        assert AuditEventType.DATA_ACCESS.value == "data_access"
        assert AuditEventType.LOGIN.value == "login"
        assert AuditEventType.LOGOUT.value == "logout"
        assert AuditEventType.PERMISSION_CHANGE.value == "permission_change"
        assert AuditEventType.SYSTEM_EVENT.value == "system_event"

    def test_event_type_is_string_enum(self):
        """Test that AuditEventType inherits from str."""
        from core.security.audit_logger import AuditEventType

        # Should be usable as a string
        assert "admin_action" == AuditEventType.ADMIN_ACTION
        assert isinstance(AuditEventType.ADMIN_ACTION, str)

    def test_event_type_members_count(self):
        """Test correct number of event types defined."""
        from core.security.audit_logger import AuditEventType

        assert len(AuditEventType) == 11


# =============================================================================
# AuditEntry Tests
# =============================================================================

class TestAuditEntry:
    """Tests for AuditEntry dataclass."""

    def test_audit_entry_creation(self):
        """Test creating an AuditEntry with all fields."""
        from core.security.audit_logger import AuditEntry

        entry = AuditEntry(
            timestamp="2026-01-26T12:00:00Z",
            event_type="admin_action",
            actor="admin_user",
            action="update_config",
            details={"key": "value"},
            ip_address="192.168.1.1",
            user_agent="Test/1.0",
            success=True,
            error_message=None,
            signature="abc123"
        )

        assert entry.timestamp == "2026-01-26T12:00:00Z"
        assert entry.event_type == "admin_action"
        assert entry.actor == "admin_user"
        assert entry.action == "update_config"
        assert entry.details == {"key": "value"}
        assert entry.ip_address == "192.168.1.1"
        assert entry.user_agent == "Test/1.0"
        assert entry.success is True
        assert entry.error_message is None
        assert entry.signature == "abc123"

    def test_audit_entry_defaults(self):
        """Test AuditEntry default values."""
        from core.security.audit_logger import AuditEntry

        entry = AuditEntry(
            timestamp="2026-01-26T12:00:00Z",
            event_type="login",
            actor="user1",
            action="login_attempt",
            details={}
        )

        assert entry.ip_address is None
        assert entry.user_agent is None
        assert entry.success is True
        assert entry.error_message is None
        assert entry.signature is None

    def test_audit_entry_to_dict(self):
        """Test converting AuditEntry to dictionary."""
        from core.security.audit_logger import AuditEntry

        entry = AuditEntry(
            timestamp="2026-01-26T12:00:00Z",
            event_type="admin_action",
            actor="admin",
            action="test",
            details={"test": "data"},
            ip_address="10.0.0.1",
            success=True
        )

        result = entry.to_dict()

        assert result["timestamp"] == "2026-01-26T12:00:00Z"
        assert result["event_type"] == "admin_action"
        assert result["actor"] == "admin"
        assert result["action"] == "test"
        assert result["details"] == {"test": "data"}
        assert result["ip_address"] == "10.0.0.1"
        assert result["success"] is True

    def test_audit_entry_to_dict_excludes_none(self):
        """Test that to_dict excludes None values."""
        from core.security.audit_logger import AuditEntry

        entry = AuditEntry(
            timestamp="2026-01-26T12:00:00Z",
            event_type="login",
            actor="user1",
            action="login",
            details={},
            ip_address=None,
            user_agent=None,
            error_message=None,
            signature=None
        )

        result = entry.to_dict()

        assert "ip_address" not in result
        assert "user_agent" not in result
        assert "error_message" not in result
        assert "signature" not in result

    def test_audit_entry_with_nested_details(self):
        """Test AuditEntry with complex nested details."""
        from core.security.audit_logger import AuditEntry

        complex_details = {
            "trade": {
                "symbol": "SOL/USDC",
                "amount": 100.5,
                "nested": {"level2": {"level3": "value"}}
            },
            "signals": ["momentum", "volume"],
            "scores": [0.8, 0.9, 0.75]
        }

        entry = AuditEntry(
            timestamp="2026-01-26T12:00:00Z",
            event_type="manual_trade",
            actor="trader1",
            action="execute_trade",
            details=complex_details
        )

        result = entry.to_dict()
        assert result["details"]["trade"]["symbol"] == "SOL/USDC"
        assert result["details"]["signals"] == ["momentum", "volume"]


# =============================================================================
# AuditLogger Initialization Tests
# =============================================================================

class TestAuditLoggerInit:
    """Tests for AuditLogger initialization."""

    def test_init_with_default_path(self):
        """Test initialization with default log path."""
        from core.security.audit_logger import AuditLogger

        with patch.object(Path, 'mkdir') as mock_mkdir:
            logger = AuditLogger()
            assert logger.log_path == Path("data/audit.log")
            assert logger.sign_entries is False

    def test_init_with_custom_path(self, temp_audit_file):
        """Test initialization with custom log path."""
        from core.security.audit_logger import AuditLogger

        logger = AuditLogger(log_path=temp_audit_file)
        assert logger.log_path == temp_audit_file

    def test_init_creates_parent_directory(self, tmp_path):
        """Test that parent directory is created if it doesn't exist."""
        from core.security.audit_logger import AuditLogger

        deep_path = tmp_path / "deep" / "nested" / "audit.log"
        logger = AuditLogger(log_path=deep_path)

        assert deep_path.parent.exists()

    def test_init_with_signing_enabled_and_key(self, temp_audit_file, monkeypatch):
        """Test initialization with signing enabled and key present."""
        from core.security.audit_logger import AuditLogger

        monkeypatch.setenv("JARVIS_AUDIT_KEY", "my-secret-key")
        logger = AuditLogger(log_path=temp_audit_file, sign_entries=True)

        assert logger.sign_entries is True
        assert logger._signing_key == b"my-secret-key"

    def test_init_with_signing_enabled_but_no_key(self, temp_audit_file, monkeypatch, caplog):
        """Test initialization with signing but missing key logs warning."""
        from core.security.audit_logger import AuditLogger

        monkeypatch.delenv("JARVIS_AUDIT_KEY", raising=False)

        with patch('core.security.audit_logger.logger') as mock_logger:
            logger = AuditLogger(log_path=temp_audit_file, sign_entries=True)

            assert logger._signing_key is None
            mock_logger.warning.assert_called()

    def test_init_with_custom_signing_key_env(self, temp_audit_file, monkeypatch):
        """Test initialization with custom signing key environment variable."""
        from core.security.audit_logger import AuditLogger

        monkeypatch.setenv("CUSTOM_AUDIT_KEY", "custom-key-value")
        logger = AuditLogger(
            log_path=temp_audit_file,
            sign_entries=True,
            signing_key_env="CUSTOM_AUDIT_KEY"
        )

        assert logger._signing_key == b"custom-key-value"


# =============================================================================
# Signature Generation Tests
# =============================================================================

class TestSignatureGeneration:
    """Tests for HMAC signature generation."""

    def test_generate_signature_with_key(self, signed_audit_logger):
        """Test signature generation with valid key."""
        data = {"action": "test", "timestamp": "2026-01-26T12:00:00Z"}
        signature = signed_audit_logger._generate_signature(data)

        assert signature != ""
        assert len(signature) == 64  # SHA256 hex digest length

    def test_generate_signature_without_key(self, audit_logger):
        """Test signature generation returns empty without key."""
        data = {"action": "test", "timestamp": "2026-01-26T12:00:00Z"}
        signature = audit_logger._generate_signature(data)

        assert signature == ""

    def test_signature_excludes_signature_field(self, signed_audit_logger):
        """Test that signature field is excluded from signature calculation."""
        data1 = {"action": "test", "timestamp": "2026-01-26T12:00:00Z"}
        data2 = {"action": "test", "timestamp": "2026-01-26T12:00:00Z", "signature": "old_sig"}

        sig1 = signed_audit_logger._generate_signature(data1)
        sig2 = signed_audit_logger._generate_signature(data2)

        assert sig1 == sig2

    def test_signature_is_deterministic(self, signed_audit_logger):
        """Test that same data produces same signature."""
        data = {"action": "test", "value": 123}

        sig1 = signed_audit_logger._generate_signature(data)
        sig2 = signed_audit_logger._generate_signature(data)

        assert sig1 == sig2

    def test_different_data_different_signatures(self, signed_audit_logger):
        """Test that different data produces different signatures."""
        data1 = {"action": "test1", "value": 123}
        data2 = {"action": "test2", "value": 123}

        sig1 = signed_audit_logger._generate_signature(data1)
        sig2 = signed_audit_logger._generate_signature(data2)

        assert sig1 != sig2


# =============================================================================
# Entry Creation Tests
# =============================================================================

class TestEntryCreation:
    """Tests for audit entry creation."""

    def test_create_entry_basic(self, audit_logger, sample_audit_details):
        """Test basic entry creation."""
        from core.security.audit_logger import AuditEventType

        entry = audit_logger._create_entry(
            event_type=AuditEventType.ADMIN_ACTION,
            actor="admin_user",
            action="update_settings",
            details=sample_audit_details
        )

        assert entry.event_type == "admin_action"
        assert entry.actor == "admin_user"
        assert entry.action == "update_settings"
        assert entry.details == sample_audit_details
        assert entry.success is True
        assert entry.timestamp.endswith("Z")

    def test_create_entry_with_failure(self, audit_logger):
        """Test entry creation with failure status."""
        from core.security.audit_logger import AuditEventType

        entry = audit_logger._create_entry(
            event_type=AuditEventType.LOGIN,
            actor="unknown_user",
            action="login_attempt",
            details={},
            success=False,
            error_message="Invalid credentials"
        )

        assert entry.success is False
        assert entry.error_message == "Invalid credentials"

    def test_create_entry_with_ip_and_agent(self, audit_logger):
        """Test entry creation with IP address and user agent."""
        from core.security.audit_logger import AuditEventType

        entry = audit_logger._create_entry(
            event_type=AuditEventType.DATA_ACCESS,
            actor="api_client",
            action="fetch_data",
            details={"resource": "positions"},
            ip_address="203.0.113.42",
            user_agent="Mozilla/5.0"
        )

        assert entry.ip_address == "203.0.113.42"
        assert entry.user_agent == "Mozilla/5.0"

    def test_create_entry_adds_signature_when_enabled(self, signed_audit_logger):
        """Test entry creation adds signature when signing is enabled."""
        from core.security.audit_logger import AuditEventType

        entry = signed_audit_logger._create_entry(
            event_type=AuditEventType.CONFIG_CHANGE,
            actor="admin",
            action="update_config",
            details={}
        )

        assert entry.signature is not None
        assert len(entry.signature) == 64

    def test_create_entry_no_signature_when_disabled(self, audit_logger):
        """Test entry creation has no signature when signing is disabled."""
        from core.security.audit_logger import AuditEventType

        entry = audit_logger._create_entry(
            event_type=AuditEventType.CONFIG_CHANGE,
            actor="admin",
            action="update_config",
            details={}
        )

        assert entry.signature is None

    def test_create_entry_timestamp_format(self, audit_logger):
        """Test entry timestamp is ISO format with Z suffix."""
        from core.security.audit_logger import AuditEventType

        entry = audit_logger._create_entry(
            event_type=AuditEventType.SYSTEM_EVENT,
            actor="system",
            action="startup",
            details={}
        )

        # Should be parseable as ISO format
        timestamp = entry.timestamp.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(timestamp)
        assert parsed is not None


# =============================================================================
# Write Entry Tests
# =============================================================================

class TestWriteEntry:
    """Tests for writing entries to log file."""

    def test_write_entry_creates_file(self, audit_logger, temp_audit_file):
        """Test that writing creates log file if it doesn't exist."""
        from core.security.audit_logger import AuditEntry

        entry = AuditEntry(
            timestamp="2026-01-26T12:00:00Z",
            event_type="test",
            actor="user",
            action="test_action",
            details={}
        )

        audit_logger._write_entry(entry)

        assert temp_audit_file.exists()

    def test_write_entry_appends_json_line(self, audit_logger, temp_audit_file):
        """Test that entries are written as JSON lines."""
        from core.security.audit_logger import AuditEntry

        entry = AuditEntry(
            timestamp="2026-01-26T12:00:00Z",
            event_type="test",
            actor="user",
            action="test_action",
            details={"key": "value"}
        )

        audit_logger._write_entry(entry)

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["event_type"] == "test"
        assert parsed["actor"] == "user"
        assert parsed["details"]["key"] == "value"

    def test_write_multiple_entries_append(self, audit_logger, temp_audit_file):
        """Test that multiple entries are appended correctly."""
        from core.security.audit_logger import AuditEntry

        for i in range(3):
            entry = AuditEntry(
                timestamp=f"2026-01-26T12:0{i}:00Z",
                event_type="test",
                actor=f"user_{i}",
                action="action",
                details={}
            )
            audit_logger._write_entry(entry)

        lines = temp_audit_file.read_text().strip().split("\n")
        assert len(lines) == 3

        for i, line in enumerate(lines):
            parsed = json.loads(line)
            assert parsed["actor"] == f"user_{i}"


# =============================================================================
# Log Method Tests
# =============================================================================

class TestLogMethod:
    """Tests for the main log method."""

    def test_log_basic_event(self, audit_logger, temp_audit_file):
        """Test logging a basic event."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(
            AuditEventType.SYSTEM_EVENT,
            actor="system",
            action="startup",
            details={"version": "1.0"}
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["event_type"] == "system_event"
        assert parsed["actor"] == "system"
        assert parsed["details"]["version"] == "1.0"

    def test_log_with_kwargs(self, audit_logger, temp_audit_file):
        """Test logging with additional kwargs."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(
            AuditEventType.LOGIN,
            actor="user123",
            action="login",
            details={},
            ip_address="192.168.1.100",
            success=True
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["ip_address"] == "192.168.1.100"
        assert parsed["success"] is True

    def test_log_calls_debug_logger(self, audit_logger):
        """Test that log calls debug logger."""
        from core.security.audit_logger import AuditEventType

        with patch('core.security.audit_logger.logger') as mock_logger:
            audit_logger.log(
                AuditEventType.ADMIN_ACTION,
                actor="admin",
                action="test",
                details={}
            )

            mock_logger.debug.assert_called()


# =============================================================================
# Convenience Method Tests
# =============================================================================

class TestLogAdminAction:
    """Tests for log_admin_action method."""

    def test_log_admin_action(self, audit_logger, temp_audit_file):
        """Test logging admin action."""
        audit_logger.log_admin_action(
            actor="admin_user",
            action="disable_feature",
            details={"feature": "trading", "reason": "maintenance"}
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["event_type"] == "admin_action"
        assert parsed["actor"] == "admin_user"
        assert parsed["action"] == "disable_feature"

    def test_log_admin_action_with_kwargs(self, audit_logger, temp_audit_file):
        """Test admin action with additional kwargs."""
        audit_logger.log_admin_action(
            actor="admin",
            action="update",
            details={},
            ip_address="10.0.0.1"
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["ip_address"] == "10.0.0.1"


class TestLogKeyRotation:
    """Tests for log_key_rotation method."""

    def test_log_key_rotation_success(self, audit_logger, temp_audit_file):
        """Test logging successful key rotation."""
        audit_logger.log_key_rotation(
            service="openai",
            rotated_by="admin_user",
            success=True
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["event_type"] == "key_rotation"
        assert parsed["actor"] == "admin_user"
        assert parsed["action"] == "rotate_key"
        assert parsed["details"]["service"] == "openai"
        assert parsed["success"] is True

    def test_log_key_rotation_failure(self, audit_logger, temp_audit_file):
        """Test logging failed key rotation."""
        audit_logger.log_key_rotation(
            service="telegram",
            rotated_by="system",
            success=False,
            error_message="Key validation failed"
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["success"] is False
        assert parsed["error_message"] == "Key validation failed"


class TestLogConfigChange:
    """Tests for log_config_change method."""

    def test_log_config_change(self, audit_logger, temp_audit_file):
        """Test logging config change."""
        audit_logger.log_config_change(
            actor="admin",
            setting="max_positions",
            old_value=10,
            new_value=20
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["event_type"] == "config_change"
        assert parsed["action"] == "config_change"
        assert parsed["details"]["setting"] == "max_positions"
        assert parsed["details"]["old_value"] == "10"
        assert parsed["details"]["new_value"] == "20"

    def test_log_config_change_converts_to_string(self, audit_logger, temp_audit_file):
        """Test that config values are converted to strings."""
        audit_logger.log_config_change(
            actor="admin",
            setting="risk_multiplier",
            old_value=1.5,
            new_value=2.0
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["details"]["old_value"] == "1.5"
        assert parsed["details"]["new_value"] == "2.0"


class TestLogTrade:
    """Tests for log_trade method."""

    def test_log_trade_basic(self, audit_logger, temp_audit_file):
        """Test logging basic trade."""
        audit_logger.log_trade(
            actor="trader1",
            trade_type="buy",
            symbol="SOL",
            amount=100.0
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["event_type"] == "manual_trade"
        assert parsed["action"] == "buy"
        assert parsed["details"]["trade_type"] == "buy"
        assert parsed["details"]["symbol"] == "SOL"
        assert parsed["details"]["amount"] == 100.0

    def test_log_trade_with_price(self, audit_logger, temp_audit_file):
        """Test logging trade with price."""
        audit_logger.log_trade(
            actor="trader1",
            trade_type="sell",
            symbol="ETH",
            amount=5.5,
            price=3200.50
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["details"]["price"] == 3200.50

    def test_log_trade_with_extra_kwargs(self, audit_logger, temp_audit_file):
        """Test logging trade with additional kwargs in details."""
        audit_logger.log_trade(
            actor="bot",
            trade_type="buy",
            symbol="BONK",
            amount=1000000,
            price=0.00001,
            reason="momentum_signal",
            confidence=0.85
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["details"]["reason"] == "momentum_signal"
        assert parsed["details"]["confidence"] == 0.85


class TestLogFeatureFlagChange:
    """Tests for log_feature_flag_change method."""

    def test_log_feature_flag_change(self, audit_logger, temp_audit_file):
        """Test logging feature flag change."""
        audit_logger.log_feature_flag_change(
            flag_name="DEXTER_ENABLED",
            old_value=False,
            new_value=True,
            changed_by="admin"
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["event_type"] == "feature_flag"
        assert parsed["action"] == "feature_flag_change"
        assert parsed["details"]["flag_name"] == "DEXTER_ENABLED"
        assert parsed["details"]["old_value"] is False
        assert parsed["details"]["new_value"] is True


class TestLogSecurityEvent:
    """Tests for log_security_event method."""

    def test_log_security_event_success(self, audit_logger, temp_audit_file):
        """Test logging successful security event."""
        audit_logger.log_security_event(
            event_type="failed_login_attempt",
            actor="unknown",
            details={"attempts": 5, "ip": "1.2.3.4"},
            success=False
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["event_type"] == "security_event"
        assert parsed["action"] == "failed_login_attempt"
        assert parsed["success"] is False


class TestLogLogin:
    """Tests for log_login method."""

    def test_log_login_success(self, audit_logger, temp_audit_file):
        """Test logging successful login."""
        audit_logger.log_login(
            user_id="user123",
            ip_address="192.168.1.50",
            success=True,
            method="password"
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["event_type"] == "login"
        assert parsed["actor"] == "user123"
        assert parsed["action"] == "login"
        assert parsed["ip_address"] == "192.168.1.50"
        assert parsed["details"]["method"] == "password"
        assert parsed["success"] is True

    def test_log_login_failure(self, audit_logger, temp_audit_file):
        """Test logging failed login."""
        audit_logger.log_login(
            user_id="attacker",
            ip_address="10.0.0.99",
            success=False,
            method="api_key"
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())

        assert parsed["success"] is False
        assert parsed["details"]["method"] == "api_key"


# =============================================================================
# Query Method Tests
# =============================================================================

class TestQueryMethod:
    """Tests for the query method."""

    def test_query_empty_log(self, audit_logger):
        """Test querying non-existent log file."""
        results = audit_logger.query()
        assert results == []

    def test_query_all_entries(self, audit_logger, temp_audit_file):
        """Test querying all entries."""
        from core.security.audit_logger import AuditEventType

        for i in range(5):
            audit_logger.log(
                AuditEventType.SYSTEM_EVENT,
                actor=f"user_{i}",
                action="action",
                details={}
            )

        results = audit_logger.query()
        assert len(results) == 5

    def test_query_by_event_type(self, audit_logger, temp_audit_file):
        """Test filtering by event type."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(AuditEventType.LOGIN, "user1", "login", {})
        audit_logger.log(AuditEventType.ADMIN_ACTION, "admin", "update", {})
        audit_logger.log(AuditEventType.LOGIN, "user2", "login", {})

        results = audit_logger.query(event_type=AuditEventType.LOGIN)
        assert len(results) == 2
        assert all(r["event_type"] == "login" for r in results)

    def test_query_by_actor(self, audit_logger, temp_audit_file):
        """Test filtering by actor."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(AuditEventType.SYSTEM_EVENT, "user_a", "action1", {})
        audit_logger.log(AuditEventType.SYSTEM_EVENT, "user_b", "action2", {})
        audit_logger.log(AuditEventType.SYSTEM_EVENT, "user_a", "action3", {})

        results = audit_logger.query(actor="user_a")
        assert len(results) == 2
        assert all(r["actor"] == "user_a" for r in results)

    def test_query_by_start_time(self, audit_logger, temp_audit_file):
        """Test filtering by start time."""
        from core.security.audit_logger import AuditEventType

        # Log an entry now
        audit_logger.log(AuditEventType.SYSTEM_EVENT, "user", "action", {})

        # Query with start time in the past should find the entry
        now = datetime.now(timezone.utc)
        results = audit_logger.query(start_time=now - timedelta(hours=1))
        assert len(results) >= 1

        # Query with start time in the future should find nothing
        future_results = audit_logger.query(start_time=now + timedelta(hours=1))
        assert len(future_results) == 0

    def test_query_by_end_time(self, audit_logger, temp_audit_file):
        """Test filtering by end time."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(AuditEventType.SYSTEM_EVENT, "user", "action", {})

        now = datetime.now(timezone.utc)
        results = audit_logger.query(end_time=now + timedelta(hours=1))
        assert len(results) >= 1

    def test_query_with_limit(self, audit_logger, temp_audit_file):
        """Test query respects limit."""
        from core.security.audit_logger import AuditEventType

        for i in range(10):
            audit_logger.log(AuditEventType.SYSTEM_EVENT, f"user_{i}", "action", {})

        results = audit_logger.query(limit=5)
        assert len(results) == 5

    def test_query_handles_malformed_json(self, audit_logger, temp_audit_file):
        """Test query handles malformed JSON gracefully."""
        from core.security.audit_logger import AuditEventType

        # Write valid entry
        audit_logger.log(AuditEventType.SYSTEM_EVENT, "user", "action", {})

        # Append malformed JSON
        with open(temp_audit_file, "a") as f:
            f.write("not valid json\n")

        # Write another valid entry
        audit_logger.log(AuditEventType.SYSTEM_EVENT, "user2", "action", {})

        results = audit_logger.query()
        assert len(results) == 2  # Should skip malformed line

    def test_query_combined_filters(self, audit_logger, temp_audit_file):
        """Test query with multiple filters."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(AuditEventType.LOGIN, "admin", "login", {})
        audit_logger.log(AuditEventType.ADMIN_ACTION, "admin", "update", {})
        audit_logger.log(AuditEventType.LOGIN, "user", "login", {})

        results = audit_logger.query(
            event_type=AuditEventType.LOGIN,
            actor="admin"
        )
        assert len(results) == 1
        assert results[0]["actor"] == "admin"
        assert results[0]["event_type"] == "login"


# =============================================================================
# Integrity Verification Tests
# =============================================================================

class TestVerifyIntegrity:
    """Tests for integrity verification."""

    def test_verify_integrity_no_signing_key(self, audit_logger):
        """Test verification fails without signing key."""
        result = audit_logger.verify_integrity()
        assert "error" in result
        assert result["error"] == "Signing key not available"

    def test_verify_integrity_empty_log(self, signed_audit_logger, temp_audit_file):
        """Test verification on non-existent log."""
        # Don't write anything
        result = signed_audit_logger.verify_integrity()
        assert result["total"] == 0
        assert result["valid"] == 0
        assert result["invalid"] == 0

    def test_verify_integrity_all_valid(self, signed_audit_logger, temp_audit_file):
        """Test verification with all valid signed entries."""
        from core.security.audit_logger import AuditEventType

        for i in range(5):
            signed_audit_logger.log(
                AuditEventType.SYSTEM_EVENT,
                actor=f"user_{i}",
                action="action",
                details={}
            )

        result = signed_audit_logger.verify_integrity()
        assert result["total"] == 5
        assert result["valid"] == 5
        assert result["invalid"] == 0
        assert len(result["invalid_lines"]) == 0

    def test_verify_integrity_detects_tampering(self, signed_audit_logger, temp_audit_file):
        """Test verification detects tampered entries."""
        from core.security.audit_logger import AuditEventType

        signed_audit_logger.log(AuditEventType.SYSTEM_EVENT, "user", "action", {})

        # Tamper with the entry
        content = temp_audit_file.read_text()
        entry = json.loads(content.strip())
        entry["actor"] = "tampered_user"
        temp_audit_file.write_text(json.dumps(entry) + "\n")

        result = signed_audit_logger.verify_integrity()
        assert result["invalid"] == 1
        assert 1 in result["invalid_lines"]

    def test_verify_integrity_skips_unsigned(self, signed_audit_logger, temp_audit_file):
        """Test verification skips entries without signatures."""
        # Write entry without signature
        with open(temp_audit_file, "w") as f:
            entry = {"event_type": "test", "actor": "user", "action": "test", "details": {}}
            f.write(json.dumps(entry) + "\n")

        result = signed_audit_logger.verify_integrity()
        assert result["total"] == 0  # No signed entries to verify

    def test_verify_integrity_limits_invalid_lines(self, signed_audit_logger, temp_audit_file, monkeypatch):
        """Test that only first 10 invalid lines are reported."""
        from core.security.audit_logger import AuditEventType

        # Create many entries then tamper with them
        for i in range(15):
            signed_audit_logger.log(AuditEventType.SYSTEM_EVENT, f"user_{i}", "action", {})

        # Tamper with all entries
        lines = temp_audit_file.read_text().strip().split("\n")
        tampered = []
        for line in lines:
            entry = json.loads(line)
            entry["actor"] = "tampered"
            tampered.append(json.dumps(entry))
        temp_audit_file.write_text("\n".join(tampered) + "\n")

        result = signed_audit_logger.verify_integrity()
        assert result["invalid"] == 15
        assert len(result["invalid_lines"]) == 10  # Only first 10


# =============================================================================
# Global Logger Tests
# =============================================================================

class TestGetAuditLogger:
    """Tests for get_audit_logger function."""

    def test_get_audit_logger_creates_instance(self, reset_global_logger, monkeypatch):
        """Test get_audit_logger creates a new instance."""
        import core.security.audit_logger as module
        module._audit_logger = None

        monkeypatch.setenv("JARVIS_AUDIT_KEY", "test-key")

        from core.security.audit_logger import get_audit_logger, AuditLogger

        logger = get_audit_logger()
        assert isinstance(logger, AuditLogger)
        assert logger.sign_entries is True

    def test_get_audit_logger_returns_singleton(self, reset_global_logger, monkeypatch):
        """Test get_audit_logger returns same instance."""
        import core.security.audit_logger as module
        module._audit_logger = None

        monkeypatch.setenv("JARVIS_AUDIT_KEY", "test-key")

        from core.security.audit_logger import get_audit_logger

        logger1 = get_audit_logger()
        logger2 = get_audit_logger()

        assert logger1 is logger2


# =============================================================================
# Convenience Function Tests
# =============================================================================

class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_audit_admin_action_function(self, reset_global_logger, tmp_path, monkeypatch):
        """Test audit_admin_action convenience function."""
        import core.security.audit_logger as module
        module._audit_logger = None

        log_path = tmp_path / "audit.log"
        monkeypatch.setenv("JARVIS_AUDIT_KEY", "test-key")

        from core.security.audit_logger import audit_admin_action, get_audit_logger, AuditLogger

        # Create logger with custom path
        module._audit_logger = AuditLogger(log_path=log_path, sign_entries=False)

        audit_admin_action("admin", "test_action", {"key": "value"})

        content = log_path.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event_type"] == "admin_action"

    def test_audit_key_rotation_function(self, reset_global_logger, tmp_path, monkeypatch):
        """Test audit_key_rotation convenience function."""
        import core.security.audit_logger as module
        module._audit_logger = None

        log_path = tmp_path / "audit.log"

        from core.security.audit_logger import audit_key_rotation, AuditLogger

        module._audit_logger = AuditLogger(log_path=log_path, sign_entries=False)

        audit_key_rotation("openai", "admin", success=True)

        content = log_path.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event_type"] == "key_rotation"

    def test_audit_config_change_function(self, reset_global_logger, tmp_path, monkeypatch):
        """Test audit_config_change convenience function."""
        import core.security.audit_logger as module
        module._audit_logger = None

        log_path = tmp_path / "audit.log"

        from core.security.audit_logger import audit_config_change, AuditLogger

        module._audit_logger = AuditLogger(log_path=log_path, sign_entries=False)

        audit_config_change("admin", "max_risk", 0.1, 0.2)

        content = log_path.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event_type"] == "config_change"

    def test_audit_trade_function(self, reset_global_logger, tmp_path, monkeypatch):
        """Test audit_trade convenience function."""
        import core.security.audit_logger as module
        module._audit_logger = None

        log_path = tmp_path / "audit.log"

        from core.security.audit_logger import audit_trade, AuditLogger

        module._audit_logger = AuditLogger(log_path=log_path, sign_entries=False)

        audit_trade("trader", "buy", "SOL", 100.0, price=150.0)

        content = log_path.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event_type"] == "manual_trade"
        assert parsed["details"]["symbol"] == "SOL"


# =============================================================================
# Edge Case and Error Handling Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_log_with_empty_details(self, audit_logger, temp_audit_file):
        """Test logging with empty details dict."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(AuditEventType.SYSTEM_EVENT, "user", "action", {})

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())
        assert parsed["details"] == {}

    def test_log_with_unicode_characters(self, audit_logger, temp_audit_file):
        """Test logging with unicode characters."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(
            AuditEventType.SYSTEM_EVENT,
            actor="user",
            action="action",
            details={"message": "Hello", "emoji": "OK", "chinese": "Test"}
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())
        assert "message" in parsed["details"]

    def test_log_with_special_characters(self, audit_logger, temp_audit_file):
        """Test logging with special characters."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(
            AuditEventType.SYSTEM_EVENT,
            actor="user@domain.com",
            action="test\"action",
            details={"path": "/home/user\\data", "newline": "line1\nline2"}
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())
        assert parsed["actor"] == "user@domain.com"

    def test_log_with_very_large_details(self, audit_logger, temp_audit_file):
        """Test logging with large details payload."""
        from core.security.audit_logger import AuditEventType

        large_details = {
            "data": "x" * 10000,
            "list": list(range(1000))
        }

        audit_logger.log(
            AuditEventType.DATA_ACCESS,
            actor="user",
            action="fetch",
            details=large_details
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())
        assert len(parsed["details"]["data"]) == 10000

    def test_query_with_time_range_no_matches(self, audit_logger, temp_audit_file):
        """Test query with time range that matches nothing."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(AuditEventType.SYSTEM_EVENT, "user", "action", {})

        # Query for time range in the past
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        results = audit_logger.query(
            start_time=past,
            end_time=past + timedelta(days=1)
        )

        assert len(results) == 0

    def test_signature_with_nested_dict(self, signed_audit_logger):
        """Test signature generation with deeply nested dict."""
        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "value": "deep"
                    }
                }
            }
        }

        sig = signed_audit_logger._generate_signature(data)
        assert len(sig) == 64

    def test_log_file_permission_error(self, audit_logger, temp_audit_file):
        """Test handling of permission error when writing."""
        from core.security.audit_logger import AuditEntry

        entry = AuditEntry(
            timestamp="2026-01-26T12:00:00Z",
            event_type="test",
            actor="user",
            action="test",
            details={}
        )

        # Mock open to raise permission error
        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with pytest.raises(PermissionError):
                audit_logger._write_entry(entry)


# =============================================================================
# All Event Type Logging Tests
# =============================================================================

class TestAllEventTypes:
    """Test logging each event type."""

    def test_log_data_access_event(self, audit_logger, temp_audit_file):
        """Test logging data access event."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(
            AuditEventType.DATA_ACCESS,
            actor="api_user",
            action="read_positions",
            details={"endpoint": "/api/positions", "count": 50}
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event_type"] == "data_access"

    def test_log_logout_event(self, audit_logger, temp_audit_file):
        """Test logging logout event."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(
            AuditEventType.LOGOUT,
            actor="user123",
            action="logout",
            details={"session_duration_seconds": 3600}
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event_type"] == "logout"

    def test_log_permission_change_event(self, audit_logger, temp_audit_file):
        """Test logging permission change event."""
        from core.security.audit_logger import AuditEventType

        audit_logger.log(
            AuditEventType.PERMISSION_CHANGE,
            actor="admin",
            action="grant_role",
            details={"target_user": "user456", "role": "trader"}
        )

        content = temp_audit_file.read_text()
        parsed = json.loads(content.strip())
        assert parsed["event_type"] == "permission_change"


# =============================================================================
# Performance and Load Tests
# =============================================================================

class TestPerformance:
    """Performance-related tests."""

    def test_rapid_logging(self, audit_logger, temp_audit_file):
        """Test rapid sequential logging."""
        from core.security.audit_logger import AuditEventType
        import time

        start = time.time()
        for i in range(100):
            audit_logger.log(
                AuditEventType.SYSTEM_EVENT,
                actor=f"user_{i}",
                action="action",
                details={"iteration": i}
            )
        elapsed = time.time() - start

        # Should complete 100 logs in under 2 seconds
        assert elapsed < 2.0

        # Verify all entries written
        lines = temp_audit_file.read_text().strip().split("\n")
        assert len(lines) == 100

    def test_query_large_log(self, audit_logger, temp_audit_file):
        """Test querying a large log file."""
        from core.security.audit_logger import AuditEventType

        # Create 500 entries
        for i in range(500):
            audit_logger.log(
                AuditEventType.SYSTEM_EVENT,
                actor=f"user_{i % 10}",
                action="action",
                details={}
            )

        # Query with filter
        results = audit_logger.query(actor="user_0")
        assert len(results) == 50  # 500/10 = 50 entries for user_0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
