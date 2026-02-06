"""
Unit tests for ClawdBot self-healing system.

Tests cover:
- Health monitoring
- Automatic restart logic
- Memory/CPU threshold detection
- Heartbeat mechanism
- Log error pattern detection
"""

import os
import sys
import time
import threading
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import after path setup
from bots.shared.self_healing import (
    HealthMonitor,
    ProcessWatchdog,
    HeartbeatManager,
    LogErrorDetector,
    SelfHealingConfig,
    ResourceThresholds,
    HealthStatus,
    RestartPolicy,
    ErrorPattern,
)


class TestSelfHealingConfig:
    """Tests for SelfHealingConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SelfHealingConfig()

        assert config.bot_name == "unknown"
        assert config.heartbeat_interval == 30
        assert config.health_check_interval == 60
        assert config.max_restart_attempts == 3
        assert config.restart_cooldown == 300
        assert config.memory_threshold_mb == 512
        assert config.cpu_threshold_percent == 80

    def test_custom_config(self):
        """Test custom configuration values."""
        config = SelfHealingConfig(
            bot_name="clawdjarvis",
            heartbeat_interval=15,
            memory_threshold_mb=256,
        )

        assert config.bot_name == "clawdjarvis"
        assert config.heartbeat_interval == 15
        assert config.memory_threshold_mb == 256


class TestResourceThresholds:
    """Tests for ResourceThresholds."""

    def test_default_thresholds(self):
        """Test default threshold values."""
        thresholds = ResourceThresholds()

        assert thresholds.memory_mb == 512
        assert thresholds.cpu_percent == 80
        assert thresholds.disk_percent == 90

    def test_is_memory_exceeded(self):
        """Test memory threshold check."""
        thresholds = ResourceThresholds(memory_mb=256)

        assert thresholds.is_memory_exceeded(300) is True
        assert thresholds.is_memory_exceeded(200) is False
        assert thresholds.is_memory_exceeded(256) is False  # At limit is OK

    def test_is_cpu_exceeded(self):
        """Test CPU threshold check."""
        thresholds = ResourceThresholds(cpu_percent=80)

        assert thresholds.is_cpu_exceeded(90) is True
        assert thresholds.is_cpu_exceeded(70) is False
        assert thresholds.is_cpu_exceeded(80) is False  # At limit is OK


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_status_values(self):
        """Test health status values exist."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.CRITICAL.value == "critical"

    def test_is_operational(self):
        """Test operational status check."""
        assert HealthStatus.HEALTHY.is_operational() is True
        assert HealthStatus.DEGRADED.is_operational() is True
        assert HealthStatus.UNHEALTHY.is_operational() is False
        assert HealthStatus.CRITICAL.is_operational() is False


class TestRestartPolicy:
    """Tests for RestartPolicy."""

    def test_default_policy(self):
        """Test default restart policy."""
        policy = RestartPolicy()

        assert policy.max_attempts == 3
        assert policy.cooldown_seconds == 300
        assert policy.backoff_multiplier == 2.0

    def test_should_restart_within_limit(self):
        """Test restart allowed within attempt limit."""
        policy = RestartPolicy(max_attempts=3)

        assert policy.should_restart(attempt_count=0) is True
        assert policy.should_restart(attempt_count=1) is True
        assert policy.should_restart(attempt_count=2) is True

    def test_should_restart_exceeds_limit(self):
        """Test restart denied when exceeding limit."""
        policy = RestartPolicy(max_attempts=3)

        assert policy.should_restart(attempt_count=3) is False
        assert policy.should_restart(attempt_count=5) is False

    def test_get_backoff_delay(self):
        """Test exponential backoff calculation."""
        policy = RestartPolicy(cooldown_seconds=10, backoff_multiplier=2.0)

        assert policy.get_backoff_delay(attempt=0) == 10
        assert policy.get_backoff_delay(attempt=1) == 20
        assert policy.get_backoff_delay(attempt=2) == 40

    def test_reset_attempts(self):
        """Test attempt counter reset."""
        policy = RestartPolicy()
        policy._attempt_count = 5

        policy.reset()

        assert policy._attempt_count == 0


class TestHealthMonitor:
    """Tests for HealthMonitor class."""

    def test_init_with_config(self):
        """Test initialization with config."""
        config = SelfHealingConfig(bot_name="testbot")
        monitor = HealthMonitor(config)

        assert monitor.bot_name == "testbot"
        assert monitor.is_running is False

    @patch('bots.shared.self_healing.psutil')
    def test_get_process_memory(self, mock_psutil):
        """Test getting process memory usage."""
        mock_process = Mock()
        mock_process.memory_info.return_value = Mock(rss=256 * 1024 * 1024)  # 256 MB
        mock_psutil.Process.return_value = mock_process

        config = SelfHealingConfig(bot_name="testbot")
        monitor = HealthMonitor(config)

        memory_mb = monitor.get_memory_usage_mb()

        assert memory_mb == 256

    @patch('bots.shared.self_healing.psutil')
    def test_get_cpu_usage(self, mock_psutil):
        """Test getting CPU usage percentage."""
        mock_process = Mock()
        mock_process.cpu_percent.return_value = 45.5
        mock_psutil.Process.return_value = mock_process

        config = SelfHealingConfig(bot_name="testbot")
        monitor = HealthMonitor(config)

        cpu_percent = monitor.get_cpu_usage_percent()

        assert cpu_percent == 45.5

    @patch('bots.shared.self_healing.psutil')
    def test_check_health_healthy(self, mock_psutil):
        """Test health check returns healthy status."""
        mock_process = Mock()
        mock_process.memory_info.return_value = Mock(rss=100 * 1024 * 1024)  # 100 MB
        mock_process.cpu_percent.return_value = 20.0
        mock_process.is_running.return_value = True
        mock_psutil.Process.return_value = mock_process

        config = SelfHealingConfig(
            bot_name="testbot",
            memory_threshold_mb=512,
            cpu_threshold_percent=80,
        )
        monitor = HealthMonitor(config)

        status = monitor.check_health()

        assert status == HealthStatus.HEALTHY

    @patch('bots.shared.self_healing.psutil')
    def test_check_health_degraded_memory(self, mock_psutil):
        """Test health check returns degraded on high memory."""
        mock_process = Mock()
        mock_process.memory_info.return_value = Mock(rss=600 * 1024 * 1024)  # 600 MB
        mock_process.cpu_percent.return_value = 20.0
        mock_process.is_running.return_value = True
        mock_psutil.Process.return_value = mock_process

        config = SelfHealingConfig(
            bot_name="testbot",
            memory_threshold_mb=512,
            cpu_threshold_percent=80,
        )
        monitor = HealthMonitor(config)

        status = monitor.check_health()

        assert status == HealthStatus.DEGRADED

    @patch('bots.shared.self_healing.psutil')
    def test_check_health_critical_both(self, mock_psutil):
        """Test health check returns critical when both exceed."""
        mock_process = Mock()
        mock_process.memory_info.return_value = Mock(rss=800 * 1024 * 1024)  # 800 MB
        mock_process.cpu_percent.return_value = 95.0
        mock_process.is_running.return_value = True
        mock_psutil.Process.return_value = mock_process

        config = SelfHealingConfig(
            bot_name="testbot",
            memory_threshold_mb=512,
            cpu_threshold_percent=80,
        )
        monitor = HealthMonitor(config)

        status = monitor.check_health()

        assert status == HealthStatus.CRITICAL


class TestHeartbeatManager:
    """Tests for HeartbeatManager class."""

    def test_init(self):
        """Test heartbeat manager initialization."""
        manager = HeartbeatManager(
            bot_name="testbot",
            interval=30,
        )

        assert manager.bot_name == "testbot"
        assert manager.interval == 30
        assert manager.last_heartbeat is None

    def test_record_heartbeat(self):
        """Test recording a heartbeat."""
        manager = HeartbeatManager(bot_name="testbot", interval=30)

        before = datetime.now()
        manager.record_heartbeat()
        after = datetime.now()

        assert manager.last_heartbeat is not None
        assert before <= manager.last_heartbeat <= after

    def test_is_alive_no_heartbeat(self):
        """Test is_alive returns False with no heartbeat."""
        manager = HeartbeatManager(bot_name="testbot", interval=30)

        assert manager.is_alive() is False

    def test_is_alive_recent_heartbeat(self):
        """Test is_alive returns True with recent heartbeat."""
        manager = HeartbeatManager(bot_name="testbot", interval=30)
        manager.record_heartbeat()

        assert manager.is_alive() is True

    def test_is_alive_stale_heartbeat(self):
        """Test is_alive returns False with stale heartbeat."""
        manager = HeartbeatManager(bot_name="testbot", interval=30)
        manager.last_heartbeat = datetime.now() - timedelta(seconds=60)

        assert manager.is_alive() is False

    def test_get_seconds_since_heartbeat(self):
        """Test calculating seconds since last heartbeat."""
        manager = HeartbeatManager(bot_name="testbot", interval=30)
        manager.last_heartbeat = datetime.now() - timedelta(seconds=45)

        seconds = manager.get_seconds_since_heartbeat()

        assert 44 <= seconds <= 46  # Allow small timing variance

    def test_write_heartbeat_file(self):
        """Test writing heartbeat to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            heartbeat_dir = Path(tmpdir)
            manager = HeartbeatManager(
                bot_name="testbot",
                interval=30,
                heartbeat_dir=heartbeat_dir,
            )

            manager.record_heartbeat()

            heartbeat_file = heartbeat_dir / "testbot.heartbeat"
            assert heartbeat_file.exists()

            content = heartbeat_file.read_text()
            assert "testbot" in content


class TestProcessWatchdog:
    """Tests for ProcessWatchdog class."""

    def test_init(self):
        """Test watchdog initialization."""
        config = SelfHealingConfig(bot_name="testbot")
        watchdog = ProcessWatchdog(config)

        assert watchdog.bot_name == "testbot"
        assert watchdog.restart_count == 0
        assert watchdog.is_running is False

    def test_register_restart_callback(self):
        """Test registering restart callback."""
        config = SelfHealingConfig(bot_name="testbot")
        watchdog = ProcessWatchdog(config)

        callback = Mock()
        watchdog.on_restart(callback)

        assert callback in watchdog._restart_callbacks

    def test_register_alert_callback(self):
        """Test registering alert callback."""
        config = SelfHealingConfig(bot_name="testbot")
        watchdog = ProcessWatchdog(config)

        callback = Mock()
        watchdog.on_alert(callback)

        assert callback in watchdog._alert_callbacks

    def test_trigger_alert(self):
        """Test triggering alert callbacks."""
        config = SelfHealingConfig(bot_name="testbot")
        watchdog = ProcessWatchdog(config)

        callback1 = Mock()
        callback2 = Mock()
        watchdog.on_alert(callback1)
        watchdog.on_alert(callback2)

        watchdog._trigger_alert("HIGH_MEMORY", {"memory_mb": 600})

        callback1.assert_called_once()
        callback2.assert_called_once()

    @patch('bots.shared.self_healing.psutil')
    def test_should_restart_on_crash(self, mock_psutil):
        """Test restart decision when process crashes."""
        mock_process = Mock()
        mock_process.is_running.return_value = False
        mock_psutil.Process.return_value = mock_process

        config = SelfHealingConfig(
            bot_name="testbot",
            max_restart_attempts=3,
        )
        watchdog = ProcessWatchdog(config)

        should_restart, reason = watchdog.should_restart()

        assert should_restart is True
        assert "not running" in reason.lower() or "crashed" in reason.lower()


class TestLogErrorDetector:
    """Tests for LogErrorDetector class."""

    def test_init_with_default_patterns(self):
        """Test initialization with default error patterns."""
        detector = LogErrorDetector(bot_name="testbot")

        assert len(detector.patterns) > 0

    def test_add_pattern(self):
        """Test adding custom error pattern."""
        detector = LogErrorDetector(bot_name="testbot")

        pattern = ErrorPattern(
            name="custom_error",
            regex=r"CUSTOM ERROR: (.+)",
            severity="high",
        )
        detector.add_pattern(pattern)

        assert pattern in detector.patterns

    def test_detect_critical_error(self):
        """Test detecting critical error in log line."""
        detector = LogErrorDetector(bot_name="testbot")

        log_line = "2026-02-02 03:00:00 CRITICAL - Database connection lost"

        matches = detector.check_line(log_line)

        assert len(matches) > 0
        assert any(m.severity == "critical" for m in matches)

    def test_detect_exception(self):
        """Test detecting exception in log line."""
        detector = LogErrorDetector(bot_name="testbot")

        log_line = "Traceback (most recent call last):"

        matches = detector.check_line(log_line)

        assert len(matches) > 0

    def test_detect_memory_error(self):
        """Test detecting memory error in log line."""
        detector = LogErrorDetector(bot_name="testbot")

        log_line = "MemoryError: Unable to allocate 1024 bytes"

        matches = detector.check_line(log_line)

        assert len(matches) > 0
        assert any("memory" in m.name.lower() for m in matches)

    def test_no_match_for_normal_log(self):
        """Test no error detected in normal log line."""
        detector = LogErrorDetector(bot_name="testbot")

        log_line = "2026-02-02 03:00:00 INFO - Bot started successfully"

        matches = detector.check_line(log_line)

        assert len(matches) == 0

    def test_get_error_summary(self):
        """Test getting error summary."""
        detector = LogErrorDetector(bot_name="testbot")

        detector.check_line("CRITICAL - Error 1")
        detector.check_line("ERROR - Error 2")
        detector.check_line("INFO - Normal")
        detector.check_line("ERROR - Error 3")

        summary = detector.get_error_summary()

        assert summary["total_errors"] >= 3
        assert "by_severity" in summary


class TestErrorPattern:
    """Tests for ErrorPattern dataclass."""

    def test_basic_pattern(self):
        """Test basic error pattern."""
        pattern = ErrorPattern(
            name="test_error",
            regex=r"ERROR: (.+)",
            severity="high",
        )

        assert pattern.name == "test_error"
        assert pattern.severity == "high"

    def test_pattern_match(self):
        """Test pattern matching."""
        pattern = ErrorPattern(
            name="test_error",
            regex=r"ERROR: (.+)",
            severity="high",
        )

        import re
        match = re.search(pattern.regex, "ERROR: Something went wrong")

        assert match is not None
        assert match.group(1) == "Something went wrong"

    def test_pattern_action(self):
        """Test pattern with action callback."""
        action_called = []

        def custom_action(match):
            action_called.append(match)

        pattern = ErrorPattern(
            name="actionable_error",
            regex=r"RESTART_NEEDED",
            severity="critical",
            action=custom_action,
        )

        import re
        match = re.search(pattern.regex, "RESTART_NEEDED")
        if match and pattern.action:
            pattern.action(match)

        assert len(action_called) == 1


class TestIntegration:
    """Integration tests for self-healing system."""

    def test_full_watchdog_lifecycle(self):
        """Test full watchdog start/stop lifecycle."""
        config = SelfHealingConfig(
            bot_name="testbot",
            heartbeat_interval=1,  # Fast for testing
            health_check_interval=1,
        )

        with patch('bots.shared.self_healing.psutil') as mock_psutil:
            mock_process = Mock()
            mock_process.memory_info.return_value = Mock(rss=100 * 1024 * 1024)
            mock_process.cpu_percent.return_value = 20.0
            mock_process.is_running.return_value = True
            mock_psutil.Process.return_value = mock_process

            watchdog = ProcessWatchdog(config)

            # Start watchdog
            watchdog.start()
            assert watchdog.is_running is True

            # Let it run briefly
            time.sleep(0.1)

            # Stop watchdog
            watchdog.stop()
            assert watchdog.is_running is False

    def test_alert_on_high_memory(self):
        """Test alert triggered on high memory usage."""
        config = SelfHealingConfig(
            bot_name="testbot",
            memory_threshold_mb=256,
            health_check_interval=0.1,  # Fast for testing
        )

        alerts = []

        with patch('bots.shared.self_healing.psutil') as mock_psutil:
            mock_process = Mock()
            mock_process.memory_info.return_value = Mock(rss=500 * 1024 * 1024)  # 500 MB
            mock_process.cpu_percent.return_value = 20.0
            mock_process.is_running.return_value = True
            mock_psutil.Process.return_value = mock_process

            watchdog = ProcessWatchdog(config)
            watchdog.on_alert(lambda t, d: alerts.append((t, d)))

            # Run single health check
            watchdog._run_health_check()

            # Should have triggered memory alert
            assert any("memory" in alert[0].lower() for alert in alerts)
