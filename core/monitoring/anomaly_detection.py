"""
JARVIS Anomaly Detection

Provides statistical anomaly detection for metrics,
alerting when values deviate significantly from normal patterns.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
import asyncio
import logging
import math
import statistics

logger = logging.getLogger(__name__)


class AnomalyType(Enum):
    """Types of anomalies detected."""
    SPIKE = "spike"
    DROP = "drop"
    TREND = "trend"
    PATTERN = "pattern"
    THRESHOLD = "threshold"


class Severity(Enum):
    """Anomaly severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    """Represents a detected anomaly."""
    metric_name: str
    anomaly_type: AnomalyType
    severity: Severity
    current_value: float
    expected_value: float
    deviation: float  # Standard deviations from mean
    timestamp: datetime = field(default_factory=datetime.utcnow)
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "deviation": self.deviation,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "metadata": self.metadata,
        }


@dataclass
class MetricConfig:
    """Configuration for a monitored metric."""
    name: str
    window_size: int = 100  # Number of data points to consider
    z_score_threshold: float = 3.0  # Standard deviations for anomaly
    min_samples: int = 20  # Minimum samples before detection
    cooldown_seconds: int = 300  # Time between alerts for same metric
    absolute_min: Optional[float] = None  # Absolute minimum threshold
    absolute_max: Optional[float] = None  # Absolute maximum threshold


class ZScoreDetector:
    """
    Detects anomalies using Z-score (standard deviations from mean).

    Simple and effective for normally distributed metrics.
    """

    def __init__(self, config: MetricConfig):
        self.config = config
        self._values: deque = deque(maxlen=config.window_size)
        self._last_alert: Optional[datetime] = None

    def add_value(self, value: float) -> Optional[Anomaly]:
        """Add a value and check for anomalies."""
        self._values.append(value)

        if len(self._values) < self.config.min_samples:
            return None

        # Check absolute thresholds first
        if self.config.absolute_max is not None and value > self.config.absolute_max:
            return self._create_anomaly(
                value=value,
                expected=self.config.absolute_max,
                deviation=0,
                anomaly_type=AnomalyType.THRESHOLD,
                message=f"Value {value} exceeds maximum threshold {self.config.absolute_max}"
            )

        if self.config.absolute_min is not None and value < self.config.absolute_min:
            return self._create_anomaly(
                value=value,
                expected=self.config.absolute_min,
                deviation=0,
                anomaly_type=AnomalyType.THRESHOLD,
                message=f"Value {value} below minimum threshold {self.config.absolute_min}"
            )

        # Calculate Z-score
        mean = statistics.mean(self._values)
        stdev = statistics.stdev(self._values) if len(self._values) > 1 else 0

        if stdev == 0:
            return None

        z_score = (value - mean) / stdev

        if abs(z_score) >= self.config.z_score_threshold:
            # Check cooldown
            if self._last_alert:
                cooldown = timedelta(seconds=self.config.cooldown_seconds)
                if datetime.utcnow() - self._last_alert < cooldown:
                    return None

            self._last_alert = datetime.utcnow()

            anomaly_type = AnomalyType.SPIKE if z_score > 0 else AnomalyType.DROP

            return self._create_anomaly(
                value=value,
                expected=mean,
                deviation=z_score,
                anomaly_type=anomaly_type,
                message=f"Value {value:.2f} is {abs(z_score):.1f} standard deviations from mean {mean:.2f}"
            )

        return None

    def _create_anomaly(
        self,
        value: float,
        expected: float,
        deviation: float,
        anomaly_type: AnomalyType,
        message: str
    ) -> Anomaly:
        """Create an anomaly object with appropriate severity."""
        severity = self._calculate_severity(abs(deviation))

        return Anomaly(
            metric_name=self.config.name,
            anomaly_type=anomaly_type,
            severity=severity,
            current_value=value,
            expected_value=expected,
            deviation=deviation,
            message=message,
        )

    def _calculate_severity(self, deviation: float) -> Severity:
        """Calculate severity based on deviation."""
        if deviation >= 5:
            return Severity.CRITICAL
        elif deviation >= 4:
            return Severity.HIGH
        elif deviation >= 3:
            return Severity.MEDIUM
        else:
            return Severity.LOW


class MovingAverageDetector:
    """
    Detects anomalies using moving average comparison.

    Good for detecting gradual trends and shifts.
    """

    def __init__(self, config: MetricConfig):
        self.config = config
        self._values: deque = deque(maxlen=config.window_size)
        self._short_window = config.window_size // 4
        self._last_alert: Optional[datetime] = None

    def add_value(self, value: float) -> Optional[Anomaly]:
        """Add a value and check for trend anomalies."""
        self._values.append(value)

        if len(self._values) < self.config.min_samples:
            return None

        # Calculate short and long moving averages
        values_list = list(self._values)
        long_ma = statistics.mean(values_list)
        short_ma = statistics.mean(values_list[-self._short_window:])

        # Calculate percentage deviation
        if long_ma == 0:
            return None

        deviation_pct = ((short_ma - long_ma) / long_ma) * 100

        # Significant trend if short MA deviates > 20% from long MA
        if abs(deviation_pct) >= 20:
            if self._last_alert:
                cooldown = timedelta(seconds=self.config.cooldown_seconds)
                if datetime.utcnow() - self._last_alert < cooldown:
                    return None

            self._last_alert = datetime.utcnow()

            severity = Severity.HIGH if abs(deviation_pct) >= 50 else Severity.MEDIUM

            return Anomaly(
                metric_name=self.config.name,
                anomaly_type=AnomalyType.TREND,
                severity=severity,
                current_value=short_ma,
                expected_value=long_ma,
                deviation=deviation_pct / 100,
                message=f"Trend detected: short-term average {short_ma:.2f} deviates {deviation_pct:.1f}% from long-term {long_ma:.2f}",
            )

        return None


class AnomalyDetector:
    """
    Main anomaly detection manager.

    Monitors multiple metrics and triggers alerts when anomalies are detected.

    Usage:
        detector = AnomalyDetector()

        # Configure metrics
        detector.add_metric(MetricConfig(
            name="api_latency",
            z_score_threshold=3.0,
            absolute_max=5000
        ))

        # Add values as they come in
        anomaly = detector.record("api_latency", 150.5)
        if anomaly:
            await send_alert(anomaly)
    """

    def __init__(self):
        self._detectors: Dict[str, List] = {}  # metric -> [detector, detector, ...]
        self._callbacks: List[Callable] = []
        self._anomalies: deque = deque(maxlen=1000)
        self._lock = asyncio.Lock()

    def add_metric(
        self,
        config: MetricConfig,
        detector_types: Optional[List[str]] = None
    ) -> None:
        """Add a metric to monitor."""
        if detector_types is None:
            detector_types = ["zscore", "moving_average"]

        detectors = []
        for dtype in detector_types:
            if dtype == "zscore":
                detectors.append(ZScoreDetector(config))
            elif dtype == "moving_average":
                detectors.append(MovingAverageDetector(config))

        self._detectors[config.name] = detectors
        logger.info(f"Added anomaly detection for metric: {config.name}")

    def add_callback(self, callback: Callable) -> None:
        """Add a callback to be called when anomalies are detected."""
        self._callbacks.append(callback)

    def record(self, metric_name: str, value: float) -> Optional[Anomaly]:
        """Record a metric value and check for anomalies."""
        detectors = self._detectors.get(metric_name, [])

        for detector in detectors:
            anomaly = detector.add_value(value)
            if anomaly:
                self._anomalies.append(anomaly)
                logger.warning(f"Anomaly detected: {anomaly.message}")

                # Trigger callbacks
                for callback in self._callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            asyncio.create_task(callback(anomaly))
                        else:
                            callback(anomaly)
                    except Exception as e:
                        logger.error(f"Error in anomaly callback: {e}")

                return anomaly

        return None

    async def record_async(self, metric_name: str, value: float) -> Optional[Anomaly]:
        """Thread-safe async version of record."""
        async with self._lock:
            return self.record(metric_name, value)

    def get_recent_anomalies(self, limit: int = 100) -> List[Anomaly]:
        """Get recent anomalies."""
        return list(self._anomalies)[-limit:]

    def get_anomaly_stats(self) -> Dict[str, Any]:
        """Get statistics about detected anomalies."""
        anomalies = list(self._anomalies)

        if not anomalies:
            return {"total": 0, "by_metric": {}, "by_severity": {}, "by_type": {}}

        by_metric = {}
        by_severity = {}
        by_type = {}

        for a in anomalies:
            by_metric[a.metric_name] = by_metric.get(a.metric_name, 0) + 1
            by_severity[a.severity.value] = by_severity.get(a.severity.value, 0) + 1
            by_type[a.anomaly_type.value] = by_type.get(a.anomaly_type.value, 0) + 1

        return {
            "total": len(anomalies),
            "by_metric": by_metric,
            "by_severity": by_severity,
            "by_type": by_type,
        }


# Pre-configured metric configs for common JARVIS metrics
JARVIS_METRICS = {
    "api_latency_ms": MetricConfig(
        name="api_latency_ms",
        z_score_threshold=3.0,
        absolute_max=5000,  # 5 seconds max
        cooldown_seconds=300,
    ),
    "error_rate": MetricConfig(
        name="error_rate",
        z_score_threshold=2.5,
        absolute_max=0.1,  # 10% max error rate
        cooldown_seconds=60,
    ),
    "memory_usage_mb": MetricConfig(
        name="memory_usage_mb",
        z_score_threshold=3.0,
        absolute_max=2000,  # 2GB max
        cooldown_seconds=600,
    ),
    "trade_volume_usd": MetricConfig(
        name="trade_volume_usd",
        z_score_threshold=4.0,  # Higher threshold for volatile metric
        cooldown_seconds=300,
    ),
    "llm_tokens_per_request": MetricConfig(
        name="llm_tokens_per_request",
        z_score_threshold=3.0,
        absolute_max=100000,
        cooldown_seconds=300,
    ),
    "bot_response_time_ms": MetricConfig(
        name="bot_response_time_ms",
        z_score_threshold=3.0,
        absolute_max=10000,  # 10 seconds max
        cooldown_seconds=300,
    ),
}


# Global instance
_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get the global anomaly detector."""
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector


def setup_default_detection() -> AnomalyDetector:
    """Set up anomaly detection with default JARVIS metrics."""
    detector = get_anomaly_detector()

    for config in JARVIS_METRICS.values():
        detector.add_metric(config)

    logger.info("Anomaly detection initialized with default metrics")
    return detector


async def alert_callback(anomaly: Anomaly) -> None:
    """Default alert callback for anomalies."""
    # This would be connected to actual alerting system
    logger.warning(
        f"ALERT [{anomaly.severity.value.upper()}] "
        f"{anomaly.metric_name}: {anomaly.message}"
    )
