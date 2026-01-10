"""
Anomaly Detection System
Prompt #90: Statistical anomaly detection for data quality

Detects outliers and suspicious patterns in collected data.
"""

import logging
import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Deque, Dict, List, Optional, Tuple
import statistics

logger = logging.getLogger("jarvis.data.anomaly")


# =============================================================================
# MODELS
# =============================================================================

class AnomalyType(Enum):
    """Type of anomaly detected"""
    STATISTICAL_OUTLIER = "statistical_outlier"
    SUDDEN_SPIKE = "sudden_spike"
    PATTERN_DEVIATION = "pattern_deviation"
    IMPOSSIBLE_VALUE = "impossible_value"
    TIMING_ANOMALY = "timing_anomaly"
    FREQUENCY_ANOMALY = "frequency_anomaly"


class AnomalySeverity(Enum):
    """Severity of detected anomaly"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    """A detected anomaly"""
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    field: str
    value: Any
    expected_range: Optional[Tuple[float, float]] = None
    z_score: Optional[float] = None
    message: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection"""
    has_anomalies: bool
    anomalies: List[Anomaly] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class FieldStats:
    """Statistics for a field"""
    field: str
    count: int = 0
    mean: float = 0.0
    std_dev: float = 0.0
    min_val: float = float('inf')
    max_val: float = float('-inf')
    recent_values: Deque[float] = field(default_factory=lambda: deque(maxlen=1000))


# =============================================================================
# ANOMALY DETECTOR
# =============================================================================

class AnomalyDetector:
    """
    Detects anomalies in data using statistical methods.

    Features:
    - Z-score based outlier detection
    - Moving average deviation
    - Impossible value detection
    - Pattern analysis
    - Adaptive thresholds
    """

    # Default thresholds
    DEFAULT_Z_SCORE_THRESHOLD = 3.0  # Standard deviations
    DEFAULT_SPIKE_THRESHOLD = 5.0    # Multiplier for sudden changes
    MIN_SAMPLES_FOR_STATS = 30       # Minimum samples before detection

    def __init__(
        self,
        z_score_threshold: float = None,
        spike_threshold: float = None,
    ):
        self.z_score_threshold = z_score_threshold or self.DEFAULT_Z_SCORE_THRESHOLD
        self.spike_threshold = spike_threshold or self.DEFAULT_SPIKE_THRESHOLD

        self._field_stats: Dict[str, FieldStats] = {}
        self._impossible_rules: Dict[str, Dict[str, Any]] = {}
        self._timing_stats: Dict[str, Deque[datetime]] = {}

        self._load_default_rules()

    def _load_default_rules(self):
        """Load default impossible value rules"""
        self._impossible_rules = {
            "pnl_pct": {
                "min": -100.0,  # Can't lose more than 100%
                "max": 100000.0,  # Sanity check
            },
            "amount_bucket": {
                "min": 0,
                "max": 1000000000,  # 1B SOL sanity check
            },
            "hold_duration_seconds": {
                "min": 0,
                "max": 31536000,  # 1 year max
            },
        }

    # =========================================================================
    # DETECTION
    # =========================================================================

    def check_anomaly(
        self,
        data: Dict[str, Any],
        fields: List[str] = None,
    ) -> AnomalyDetectionResult:
        """
        Check data for anomalies.

        Args:
            data: Data record to check
            fields: Specific fields to check (default: all numeric)

        Returns:
            AnomalyDetectionResult with any anomalies found
        """
        anomalies: List[Anomaly] = []

        # Determine fields to check
        if fields is None:
            fields = [k for k, v in data.items() if isinstance(v, (int, float))]

        for field_name in fields:
            value = data.get(field_name)

            if value is None:
                continue

            if not isinstance(value, (int, float)):
                continue

            # Check impossible values
            impossible = self._check_impossible(field_name, value)
            if impossible:
                anomalies.append(impossible)
                continue  # Skip other checks if impossible

            # Update stats and check for statistical anomalies
            stats = self._get_or_create_stats(field_name)
            self._update_stats(stats, value)

            if stats.count >= self.MIN_SAMPLES_FOR_STATS:
                # Z-score outlier detection
                outlier = self._check_statistical_outlier(stats, value)
                if outlier:
                    anomalies.append(outlier)

                # Sudden spike detection
                spike = self._check_spike(stats, value)
                if spike:
                    anomalies.append(spike)

        # Check timing anomalies
        timing_anomaly = self._check_timing_anomaly(data)
        if timing_anomaly:
            anomalies.append(timing_anomaly)

        return AnomalyDetectionResult(
            has_anomalies=len(anomalies) > 0,
            anomalies=anomalies,
            confidence=self._calculate_confidence(anomalies),
        )

    def check_batch(
        self,
        records: List[Dict[str, Any]],
        fields: List[str] = None,
    ) -> Tuple[List[AnomalyDetectionResult], Dict[str, int]]:
        """
        Check a batch of records for anomalies.

        Args:
            records: List of records to check
            fields: Specific fields to check

        Returns:
            (results, anomaly_counts_by_type)
        """
        results = [self.check_anomaly(record, fields) for record in records]

        # Count by type
        counts: Dict[str, int] = {}
        for result in results:
            for anomaly in result.anomalies:
                key = anomaly.anomaly_type.value
                counts[key] = counts.get(key, 0) + 1

        return results, counts

    # =========================================================================
    # ANOMALY CHECKS
    # =========================================================================

    def _check_impossible(
        self,
        field_name: str,
        value: float,
    ) -> Optional[Anomaly]:
        """Check for impossible values"""
        rules = self._impossible_rules.get(field_name)
        if not rules:
            return None

        min_val = rules.get("min")
        max_val = rules.get("max")

        if min_val is not None and value < min_val:
            return Anomaly(
                anomaly_type=AnomalyType.IMPOSSIBLE_VALUE,
                severity=AnomalySeverity.CRITICAL,
                field=field_name,
                value=value,
                expected_range=(min_val, max_val),
                message=f"{field_name}={value} is below minimum {min_val}",
            )

        if max_val is not None and value > max_val:
            return Anomaly(
                anomaly_type=AnomalyType.IMPOSSIBLE_VALUE,
                severity=AnomalySeverity.CRITICAL,
                field=field_name,
                value=value,
                expected_range=(min_val, max_val),
                message=f"{field_name}={value} exceeds maximum {max_val}",
            )

        return None

    def _check_statistical_outlier(
        self,
        stats: FieldStats,
        value: float,
    ) -> Optional[Anomaly]:
        """Check for statistical outliers using z-score"""
        if stats.std_dev == 0:
            return None

        z_score = abs((value - stats.mean) / stats.std_dev)

        if z_score > self.z_score_threshold:
            # Determine severity based on z-score
            if z_score > 5:
                severity = AnomalySeverity.HIGH
            elif z_score > 4:
                severity = AnomalySeverity.MEDIUM
            else:
                severity = AnomalySeverity.LOW

            expected_min = stats.mean - (self.z_score_threshold * stats.std_dev)
            expected_max = stats.mean + (self.z_score_threshold * stats.std_dev)

            return Anomaly(
                anomaly_type=AnomalyType.STATISTICAL_OUTLIER,
                severity=severity,
                field=stats.field,
                value=value,
                z_score=z_score,
                expected_range=(expected_min, expected_max),
                message=f"{stats.field}={value} is {z_score:.1f} std devs from mean",
            )

        return None

    def _check_spike(
        self,
        stats: FieldStats,
        value: float,
    ) -> Optional[Anomaly]:
        """Check for sudden spikes compared to recent values"""
        if len(stats.recent_values) < 10:
            return None

        recent = list(stats.recent_values)[-10:]
        recent_mean = statistics.mean(recent)

        if recent_mean == 0:
            return None

        change_ratio = abs(value / recent_mean) if recent_mean != 0 else 0

        if change_ratio > self.spike_threshold:
            return Anomaly(
                anomaly_type=AnomalyType.SUDDEN_SPIKE,
                severity=AnomalySeverity.MEDIUM,
                field=stats.field,
                value=value,
                expected_range=(
                    recent_mean / self.spike_threshold,
                    recent_mean * self.spike_threshold,
                ),
                message=f"{stats.field} spiked {change_ratio:.1f}x from recent average",
            )

        return None

    def _check_timing_anomaly(
        self,
        data: Dict[str, Any],
    ) -> Optional[Anomaly]:
        """Check for timing anomalies (too frequent/infrequent)"""
        user_hash = data.get("user_hash")
        if not user_hash:
            return None

        # Track submission times per user
        if user_hash not in self._timing_stats:
            self._timing_stats[user_hash] = deque(maxlen=100)

        now = datetime.now(timezone.utc)
        times = self._timing_stats[user_hash]

        # Check for rapid submissions (bot-like behavior)
        if len(times) >= 5:
            recent = [t for t in times if (now - t).total_seconds() < 60]
            if len(recent) >= 10:  # 10+ records in 1 minute
                return Anomaly(
                    anomaly_type=AnomalyType.FREQUENCY_ANOMALY,
                    severity=AnomalySeverity.HIGH,
                    field="submission_rate",
                    value=len(recent),
                    message=f"Unusually high submission rate: {len(recent)}/minute",
                )

        times.append(now)
        return None

    # =========================================================================
    # STATISTICS MANAGEMENT
    # =========================================================================

    def _get_or_create_stats(self, field_name: str) -> FieldStats:
        """Get or create statistics for a field"""
        if field_name not in self._field_stats:
            self._field_stats[field_name] = FieldStats(field=field_name)
        return self._field_stats[field_name]

    def _update_stats(self, stats: FieldStats, value: float):
        """Update running statistics with new value"""
        stats.count += 1
        stats.recent_values.append(value)

        # Update min/max
        stats.min_val = min(stats.min_val, value)
        stats.max_val = max(stats.max_val, value)

        # Welford's online algorithm for mean and variance
        delta = value - stats.mean
        stats.mean += delta / stats.count

        if stats.count > 1:
            # Update standard deviation using recent values
            if len(stats.recent_values) >= 2:
                stats.std_dev = statistics.stdev(stats.recent_values)

    def get_field_stats(self, field_name: str) -> Optional[FieldStats]:
        """Get current statistics for a field"""
        return self._field_stats.get(field_name)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get all field statistics as dict"""
        result = {}
        for name, stats in self._field_stats.items():
            result[name] = {
                "field": stats.field,
                "count": stats.count,
                "mean": stats.mean,
                "std_dev": stats.std_dev,
                "min": stats.min_val if stats.min_val != float('inf') else None,
                "max": stats.max_val if stats.max_val != float('-inf') else None,
            }
        return result

    def reset_stats(self, field_name: str = None):
        """Reset statistics"""
        if field_name:
            if field_name in self._field_stats:
                del self._field_stats[field_name]
        else:
            self._field_stats.clear()

    # =========================================================================
    # CONFIGURATION
    # =========================================================================

    def add_impossible_rule(
        self,
        field_name: str,
        min_val: float = None,
        max_val: float = None,
    ):
        """Add an impossible value rule"""
        self._impossible_rules[field_name] = {
            "min": min_val,
            "max": max_val,
        }

    def set_thresholds(
        self,
        z_score_threshold: float = None,
        spike_threshold: float = None,
    ):
        """Update detection thresholds"""
        if z_score_threshold is not None:
            self.z_score_threshold = z_score_threshold
        if spike_threshold is not None:
            self.spike_threshold = spike_threshold

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def _calculate_confidence(self, anomalies: List[Anomaly]) -> float:
        """Calculate confidence in anomaly detection"""
        if not anomalies:
            return 1.0

        # Lower confidence with more/severe anomalies
        severity_weights = {
            AnomalySeverity.LOW: 0.1,
            AnomalySeverity.MEDIUM: 0.2,
            AnomalySeverity.HIGH: 0.3,
            AnomalySeverity.CRITICAL: 0.4,
        }

        total_weight = sum(severity_weights.get(a.severity, 0.1) for a in anomalies)
        return max(0.0, 1.0 - total_weight)

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of detector state"""
        return {
            "fields_tracked": len(self._field_stats),
            "total_samples": sum(s.count for s in self._field_stats.values()),
            "thresholds": {
                "z_score": self.z_score_threshold,
                "spike": self.spike_threshold,
            },
            "impossible_rules": len(self._impossible_rules),
            "timing_users_tracked": len(self._timing_stats),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Get or create the anomaly detector singleton"""
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector
