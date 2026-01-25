"""Tests for reliability monitoring.

These tests verify:
- Circuit breaker state monitoring
- Error tracking and alerting
- Health dashboard data
- Auto-recovery tracking
"""

import pytest
import time
from unittest.mock import Mock, patch, AsyncMock


class TestReliabilityMonitor:
    """Test reliability monitoring functionality."""

    def test_monitor_registers_breakers(self):
        """Monitor should track registered circuit breakers."""
        from core.reliability.monitor import ReliabilityMonitor
        from core.reliability.circuit_breaker import CircuitBreaker

        monitor = ReliabilityMonitor()
        cb = CircuitBreaker(name="test_service")

        monitor.register_circuit_breaker(cb)

        assert "test_service" in monitor.get_monitored_services()

    def test_monitor_tracks_failures(self):
        """Monitor should track failure counts."""
        from core.reliability.monitor import ReliabilityMonitor

        monitor = ReliabilityMonitor()
        monitor.record_failure("service_a", Exception("error 1"))
        monitor.record_failure("service_a", Exception("error 2"))
        monitor.record_failure("service_b", Exception("error 1"))

        stats = monitor.get_failure_stats()
        assert stats["service_a"]["count"] == 2
        assert stats["service_b"]["count"] == 1

    def test_monitor_alerts_on_threshold(self):
        """Monitor should trigger alert when failure threshold hit."""
        from core.reliability.monitor import ReliabilityMonitor

        alert_triggered = []

        def on_alert(service, message):
            alert_triggered.append((service, message))

        monitor = ReliabilityMonitor(
            alert_threshold=3,
            on_alert=on_alert
        )

        for i in range(4):
            monitor.record_failure("failing_service", Exception(f"error {i}"))

        assert len(alert_triggered) >= 1
        assert alert_triggered[0][0] == "failing_service"

    def test_monitor_tracks_recovery(self):
        """Monitor should track service recovery."""
        from core.reliability.monitor import ReliabilityMonitor

        monitor = ReliabilityMonitor()

        # Record failures
        for _ in range(3):
            monitor.record_failure("service", Exception("fail"))

        # Record recovery
        monitor.record_success("service")
        monitor.record_success("service")
        monitor.record_success("service")

        health = monitor.get_service_health("service")
        assert health["recovering"] or health["healthy"]


class TestHealthDashboard:
    """Test health dashboard data generation."""

    def test_dashboard_summary(self):
        """Dashboard should provide overall summary."""
        from core.reliability.monitor import HealthDashboard
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState

        dashboard = HealthDashboard()

        cb1 = CircuitBreaker(name="healthy_service")
        cb2 = CircuitBreaker(name="failing_service")
        cb2.state = CircuitState.OPEN

        dashboard.register(cb1)
        dashboard.register(cb2)

        summary = dashboard.get_summary()

        assert summary["total_services"] == 2
        assert summary["healthy_count"] == 1
        assert summary["unhealthy_count"] == 1

    def test_dashboard_detailed_status(self):
        """Dashboard should provide detailed per-service status."""
        from core.reliability.monitor import HealthDashboard
        from core.reliability.circuit_breaker import CircuitBreaker

        dashboard = HealthDashboard()
        cb = CircuitBreaker(name="test_service", failure_threshold=5)
        cb.failure_count = 3

        dashboard.register(cb)

        details = dashboard.get_service_details("test_service")

        assert details["name"] == "test_service"
        assert details["state"] == "closed"
        assert details["failure_count"] == 3
        assert details["failure_threshold"] == 5

    def test_dashboard_history(self):
        """Dashboard should track state history."""
        from core.reliability.monitor import HealthDashboard
        from core.reliability.circuit_breaker import CircuitBreaker, CircuitState

        dashboard = HealthDashboard(history_size=10)
        cb = CircuitBreaker(name="service")

        dashboard.register(cb)

        # Simulate state changes
        dashboard.record_state_change("service", CircuitState.CLOSED, CircuitState.OPEN)
        dashboard.record_state_change("service", CircuitState.OPEN, CircuitState.HALF_OPEN)
        dashboard.record_state_change("service", CircuitState.HALF_OPEN, CircuitState.CLOSED)

        history = dashboard.get_state_history("service")

        assert len(history) == 3
        assert history[-1]["to_state"] == "closed"


class TestErrorLogger:
    """Test error logging to database."""

    def test_logs_error_with_context(self):
        """Should log error with full context."""
        from core.reliability.monitor import ErrorLogger

        logger = ErrorLogger()

        logger.log_error(
            error=ValueError("test error"),
            user_id=123,
            session_id="sess_abc",
            context={"action": "trade", "symbol": "SOL"}
        )

        # Verify logging occurred
        recent = logger.get_recent_errors(limit=1)
        assert len(recent) == 1
        assert recent[0]["error_type"] == "ValueError"
        assert recent[0]["context"]["symbol"] == "SOL"

    def test_error_aggregation(self):
        """Should aggregate errors by type."""
        from core.reliability.monitor import ErrorLogger

        logger = ErrorLogger()

        for i in range(5):
            logger.log_error(ValueError(f"error {i}"))
        for i in range(3):
            logger.log_error(TypeError(f"type error {i}"))

        aggregated = logger.get_error_aggregation()

        assert aggregated["ValueError"] == 5
        assert aggregated["TypeError"] == 3

    def test_error_trend_analysis(self):
        """Should analyze error trends."""
        from core.reliability.monitor import ErrorLogger

        logger = ErrorLogger()

        # Simulate error spike
        for i in range(10):
            logger.log_error(ConnectionError("conn fail"), timestamp=time.time() - 60)
        for i in range(2):
            logger.log_error(ConnectionError("conn fail"), timestamp=time.time())

        trend = logger.get_error_trend("ConnectionError", window_minutes=5)

        # Recent errors should be fewer than older ones
        assert "trend" in trend
        assert trend["trend"] in ["decreasing", "stable", "increasing"]


class TestAutoRecovery:
    """Test automatic recovery tracking."""

    def test_tracks_recovery_attempts(self):
        """Should track automatic recovery attempts."""
        from core.reliability.monitor import RecoveryTracker

        tracker = RecoveryTracker()

        tracker.record_recovery_attempt("service_a", success=False)
        tracker.record_recovery_attempt("service_a", success=False)
        tracker.record_recovery_attempt("service_a", success=True)

        stats = tracker.get_recovery_stats("service_a")

        assert stats["total_attempts"] == 3
        assert stats["successful_recoveries"] == 1
        assert stats["current_streak"] == 0  # Reset after success

    def test_calculates_mttr(self):
        """Should calculate Mean Time To Recovery."""
        from core.reliability.monitor import RecoveryTracker

        tracker = RecoveryTracker()

        # Simulate failure at T=0, recovery at T=60
        tracker.record_failure_start("service", timestamp=1000)
        tracker.record_recovery("service", timestamp=1060)

        # Second incident: failure at T=2000, recovery at T=2120
        tracker.record_failure_start("service", timestamp=2000)
        tracker.record_recovery("service", timestamp=2120)

        mttr = tracker.get_mttr("service")

        # Average recovery time should be (60 + 120) / 2 = 90 seconds
        assert 80 <= mttr <= 100

    def test_recovery_notifications(self):
        """Should notify on recovery."""
        from core.reliability.monitor import RecoveryTracker

        notifications = []

        def on_recovery(service, downtime):
            notifications.append((service, downtime))

        tracker = RecoveryTracker(on_recovery=on_recovery)

        tracker.record_failure_start("service")
        time.sleep(0.1)
        tracker.record_recovery("service")

        assert len(notifications) == 1
        assert notifications[0][0] == "service"
        assert notifications[0][1] >= 0.1
