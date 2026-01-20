"""Tests for memory monitoring."""
import pytest
import time
import threading
from unittest.mock import patch, MagicMock

from core.performance.memory_monitor import (
    MemoryMonitor,
    MemorySnapshot,
    MemoryAlert,
    memory_monitor,
)


@pytest.fixture
def monitor():
    """Create a fresh monitor instance for testing."""
    return MemoryMonitor(
        snapshot_interval=0.1,  # Fast for testing
        warning_threshold_mb=50.0,
        critical_threshold_mb=100.0
    )


def test_memory_snapshot_creation(monitor):
    """Test creating memory snapshots."""
    monitor.start_tracking()

    snapshot = monitor.take_snapshot()

    assert isinstance(snapshot, MemorySnapshot)
    assert snapshot.rss_mb > 0
    assert snapshot.heap_mb >= 0
    assert snapshot.timestamp > 0
    assert isinstance(snapshot.gc_counts, tuple)
    assert len(snapshot.gc_counts) == 3
    assert isinstance(snapshot.object_counts, dict)
    assert isinstance(snapshot.top_allocations, list)

    monitor.stop_tracking()


def test_baseline_setting(monitor):
    """Test baseline snapshot is set on start_tracking."""
    monitor.start_tracking()

    assert monitor.baseline is not None
    assert isinstance(monitor.baseline, MemorySnapshot)

    monitor.stop_tracking()


def test_snapshot_history_limit(monitor):
    """Test snapshots are limited to 100."""
    monitor.start_tracking()

    # Take more than 100 snapshots
    for _ in range(120):
        monitor.take_snapshot()

    assert len(monitor.snapshots) == 100

    monitor.stop_tracking()


def test_leak_detection_memory_growth(monitor):
    """Test leak detection for memory growth."""
    monitor.start_tracking()

    # Create snapshots with artificial growth
    first = monitor.take_snapshot()

    # Simulate growth by modifying snapshots
    for i in range(10):
        snapshot = MemorySnapshot(
            timestamp=time.time(),
            rss_mb=first.rss_mb + (i + 1) * 20,  # 20MB growth per snapshot
            heap_mb=first.heap_mb,
            gc_counts=(0, 0, 0),
            object_counts={},
            top_allocations=[]
        )
        monitor.snapshots.append(snapshot)

    leaks = monitor.detect_leaks()

    assert len(leaks) > 0
    assert any(leak["type"] == "memory_growth" for leak in leaks)

    monitor.stop_tracking()


def test_leak_detection_object_growth(monitor):
    """Test leak detection for object count growth."""
    monitor.start_tracking()

    # Create snapshots with object growth
    first_snapshot = MemorySnapshot(
        timestamp=time.time(),
        rss_mb=100.0,
        heap_mb=50.0,
        gc_counts=(0, 0, 0),
        object_counts={"dict": 1000, "list": 500},
        top_allocations=[]
    )
    monitor.snapshots = [first_snapshot]
    monitor.baseline = first_snapshot

    # Add snapshot with significant object growth
    second_snapshot = MemorySnapshot(
        timestamp=time.time(),
        rss_mb=120.0,
        heap_mb=60.0,
        gc_counts=(0, 0, 0),
        object_counts={"dict": 20000, "list": 800},  # dict grew by 19000
        top_allocations=[]
    )
    monitor.snapshots.append(second_snapshot)

    leaks = monitor.detect_leaks()

    assert len(leaks) > 0
    assert any("dict" in leak["details"] for leak in leaks)

    monitor.stop_tracking()


def test_force_gc(monitor):
    """Test force garbage collection."""
    result = monitor.force_gc()

    assert "collected" in result
    assert "before" in result
    assert "after" in result
    assert isinstance(result["collected"], int)


def test_alert_triggering(monitor):
    """Test memory alert triggering."""
    monitor.start_tracking()

    # Create baseline
    baseline = MemorySnapshot(
        timestamp=time.time(),
        rss_mb=100.0,
        heap_mb=50.0,
        gc_counts=(0, 0, 0),
        object_counts={},
        top_allocations=[]
    )
    monitor.snapshots = [baseline]
    monitor.baseline = baseline

    # Add snapshot exceeding warning threshold
    warning_snapshot = MemorySnapshot(
        timestamp=time.time(),
        rss_mb=160.0,  # 60MB growth > 50MB threshold
        heap_mb=80.0,
        gc_counts=(0, 0, 0),
        object_counts={},
        top_allocations=[]
    )
    monitor.snapshots.append(warning_snapshot)

    monitor.check_thresholds()

    alerts = monitor.get_alerts()
    assert len(alerts) > 0
    assert alerts[0].severity == "warning"

    # Add snapshot exceeding critical threshold
    critical_snapshot = MemorySnapshot(
        timestamp=time.time(),
        rss_mb=210.0,  # 110MB growth > 100MB threshold
        heap_mb=100.0,
        gc_counts=(0, 0, 0),
        object_counts={},
        top_allocations=[]
    )
    monitor.snapshots.append(critical_snapshot)

    monitor.check_thresholds()

    alerts = monitor.get_alerts()
    assert any(a.severity == "critical" for a in alerts)

    monitor.stop_tracking()


def test_alert_callbacks(monitor):
    """Test alert callback notifications."""
    callback_called = []

    def alert_callback(alert: MemoryAlert):
        callback_called.append(alert)

    monitor.register_alert_callback(alert_callback)

    # Trigger an alert
    monitor._trigger_alert(
        severity="warning",
        message="Test alert",
        details={"test": True}
    )

    assert len(callback_called) == 1
    assert callback_called[0].severity == "warning"
    assert callback_called[0].message == "Test alert"


def test_get_alerts_filtering(monitor):
    """Test alert filtering by time and severity."""
    now = time.time()

    # Create alerts at different times and severities
    monitor._trigger_alert("warning", "Old warning", {})
    time.sleep(0.1)

    monitor._trigger_alert("critical", "Recent critical", {})

    # Filter by time
    recent = monitor.get_alerts(since=now + 0.05)
    assert len(recent) == 1
    assert recent[0].severity == "critical"

    # Filter by severity
    warnings = monitor.get_alerts(severity="warning")
    assert len(warnings) == 1
    assert warnings[0].message == "Old warning"


def test_clear_alerts(monitor):
    """Test clearing alerts."""
    monitor._trigger_alert("warning", "Test", {})
    monitor._trigger_alert("critical", "Test2", {})

    assert len(monitor.get_alerts()) == 2

    monitor.clear_alerts()

    assert len(monitor.get_alerts()) == 0


def test_memory_trend_stable(monitor):
    """Test memory trend detection - stable."""
    now = time.time()

    # Create stable memory snapshots
    for i in range(10):
        snapshot = MemorySnapshot(
            timestamp=now - (60 * (10 - i)),
            rss_mb=100.0 + (i * 0.1),  # Very slow growth
            heap_mb=50.0,
            gc_counts=(0, 0, 0),
            object_counts={},
            top_allocations=[]
        )
        monitor.snapshots.append(snapshot)

    trend = monitor.get_memory_trend(window_minutes=60)

    assert trend["trend"] == "stable"
    assert trend["samples"] == 10
    assert abs(trend["growth_rate_mb_per_min"]) < 1.0


def test_memory_trend_increasing(monitor):
    """Test memory trend detection - increasing."""
    now = time.time()

    # Create increasing memory snapshots
    for i in range(10):
        snapshot = MemorySnapshot(
            timestamp=now - (60 * (10 - i)),
            rss_mb=100.0 + (i * 10),  # 10MB per snapshot
            heap_mb=50.0,
            gc_counts=(0, 0, 0),
            object_counts={},
            top_allocations=[]
        )
        monitor.snapshots.append(snapshot)

    trend = monitor.get_memory_trend(window_minutes=60)

    assert trend["trend"] == "increasing"
    assert trend["growth_rate_mb_per_min"] > 1.0


def test_memory_trend_decreasing(monitor):
    """Test memory trend detection - decreasing."""
    now = time.time()

    # Create decreasing memory snapshots
    for i in range(10):
        snapshot = MemorySnapshot(
            timestamp=now - (60 * (10 - i)),
            rss_mb=200.0 - (i * 10),  # Decreasing
            heap_mb=50.0,
            gc_counts=(0, 0, 0),
            object_counts={},
            top_allocations=[]
        )
        monitor.snapshots.append(snapshot)

    trend = monitor.get_memory_trend(window_minutes=60)

    assert trend["trend"] == "decreasing"
    assert trend["growth_rate_mb_per_min"] < -1.0


def test_background_monitoring_start_stop(monitor):
    """Test background monitoring thread."""
    monitor.start_tracking()
    monitor.start_background_monitoring()

    assert monitor._monitor_thread is not None
    assert monitor._monitor_thread.is_alive()

    # Wait for at least one snapshot
    time.sleep(0.2)

    assert len(monitor.snapshots) > 0

    monitor.stop_background_monitoring()

    # Thread should stop
    time.sleep(0.2)
    assert not monitor._monitor_thread.is_alive()

    monitor.stop_tracking()


def test_background_monitoring_threshold_checks(monitor):
    """Test background monitoring checks thresholds."""
    monitor.start_tracking()

    # Mock take_snapshot to return growing memory
    snapshot_count = [0]

    original_take_snapshot = monitor.take_snapshot

    def mock_take_snapshot():
        snapshot = original_take_snapshot()
        snapshot_count[0] += 1
        # Simulate growing memory
        snapshot.rss_mb = 100.0 + (snapshot_count[0] * 60)  # Exceeds critical after 2 snapshots
        return snapshot

    monitor.take_snapshot = mock_take_snapshot

    monitor.start_background_monitoring()

    # Wait for monitoring to trigger alerts
    time.sleep(0.5)

    monitor.stop_background_monitoring()

    alerts = monitor.get_alerts()
    assert len(alerts) > 0

    monitor.stop_tracking()


def test_get_report(monitor):
    """Test report generation."""
    monitor.start_tracking()
    monitor.take_snapshot()

    report = monitor.get_report()

    assert "Memory Report" in report
    assert "RSS:" in report
    assert "Heap:" in report
    assert "GC counts:" in report

    monitor.stop_tracking()


def test_get_report_no_snapshots():
    """Test report when no snapshots available."""
    monitor = MemoryMonitor()

    report = monitor.get_report()

    assert report == "No snapshots available"


def test_get_report_with_leaks(monitor):
    """Test report includes leak detection."""
    monitor.start_tracking()

    # Create snapshots with growth
    first = monitor.take_snapshot()

    for i in range(5):
        snapshot = MemorySnapshot(
            timestamp=time.time(),
            rss_mb=first.rss_mb + (i + 1) * 50,
            heap_mb=first.heap_mb,
            gc_counts=(0, 0, 0),
            object_counts={},
            top_allocations=[]
        )
        monitor.snapshots.append(snapshot)

    report = monitor.get_report()

    assert "Potential Leaks:" in report

    monitor.stop_tracking()


def test_get_report_with_trend(monitor):
    """Test report includes memory trend."""
    now = time.time()

    for i in range(10):
        snapshot = MemorySnapshot(
            timestamp=now - (60 * (10 - i)),
            rss_mb=100.0 + (i * 5),
            heap_mb=50.0,
            gc_counts=(0, 0, 0),
            object_counts={},
            top_allocations=[]
        )
        monitor.snapshots.append(snapshot)

    report = monitor.get_report()

    assert "Trend (60min):" in report


def test_get_report_with_alerts(monitor):
    """Test report includes recent alerts."""
    monitor.start_tracking()
    monitor.take_snapshot()

    monitor._trigger_alert("warning", "Test alert", {})

    report = monitor.get_report()

    assert "Recent Alerts" in report
    assert "Test alert" in report

    monitor.stop_tracking()


def test_global_monitor_instance():
    """Test global monitor instance exists."""
    assert memory_monitor is not None
    assert isinstance(memory_monitor, MemoryMonitor)


def test_alert_history_limit(monitor):
    """Test alerts are limited to 100."""
    # Trigger more than 100 alerts
    for i in range(120):
        monitor._trigger_alert("warning", f"Alert {i}", {})

    alerts = monitor.get_alerts()
    assert len(alerts) == 100


def test_get_object_referrers(monitor):
    """Test getting object referrers."""
    # Create some test objects
    test_dict = {"key": "value"}
    test_list = [1, 2, 3]

    referrers = monitor.get_object_referrers("dict", limit=5)

    assert isinstance(referrers, list)
    # Should find some dicts (at least our test_dict)
    assert len(referrers) > 0
