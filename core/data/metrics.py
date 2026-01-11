"""
Data Collection Metrics - Monitor data collection health and consent trends.

Provides:
- Collection rate monitoring
- Consent tier distribution
- Data quality scoring
- Anomaly detection rates
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics tracked."""
    COLLECTION_RATE = "collection_rate"
    CONSENT_RATE = "consent_rate"
    QUALITY_SCORE = "quality_score"
    ANOMALY_RATE = "anomaly_rate"
    DELETION_RATE = "deletion_rate"
    STORAGE_USAGE = "storage_usage"


@dataclass
class MetricPoint:
    """Single metric data point."""
    metric_type: MetricType
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsentDistribution:
    """Distribution of users across consent tiers."""
    tier_0_none: int = 0  # No data collection
    tier_1_anonymous: int = 0  # Anonymous aggregates
    tier_2_pseudonymous: int = 0  # Pseudonymous data
    tier_3_full: int = 0  # Full data with rewards
    total_users: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tier_0_none": self.tier_0_none,
            "tier_1_anonymous": self.tier_1_anonymous,
            "tier_2_pseudonymous": self.tier_2_pseudonymous,
            "tier_3_full": self.tier_3_full,
            "total_users": self.total_users,
            "opt_in_rate": (self.tier_1_anonymous + self.tier_2_pseudonymous + self.tier_3_full) / max(self.total_users, 1),
        }


@dataclass
class QualityMetrics:
    """Data quality metrics."""
    completeness_score: float = 0.0  # 0-1, percentage of required fields filled
    accuracy_score: float = 0.0  # 0-1, based on validation results
    freshness_score: float = 0.0  # 0-1, based on data age
    consistency_score: float = 0.0  # 0-1, cross-field consistency

    @property
    def overall_score(self) -> float:
        """Calculate overall quality score."""
        return (
            self.completeness_score * 0.3 +
            self.accuracy_score * 0.3 +
            self.freshness_score * 0.2 +
            self.consistency_score * 0.2
        )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "completeness": self.completeness_score,
            "accuracy": self.accuracy_score,
            "freshness": self.freshness_score,
            "consistency": self.consistency_score,
            "overall": self.overall_score,
        }


@dataclass
class CollectionStats:
    """Statistics for data collection."""
    total_records: int = 0
    records_last_hour: int = 0
    records_last_day: int = 0
    records_last_week: int = 0
    avg_records_per_hour: float = 0.0
    peak_hour_records: int = 0
    unique_users: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_records": self.total_records,
            "records_last_hour": self.records_last_hour,
            "records_last_day": self.records_last_day,
            "records_last_week": self.records_last_week,
            "avg_records_per_hour": self.avg_records_per_hour,
            "peak_hour_records": self.peak_hour_records,
            "unique_users": self.unique_users,
        }


class DataCollectionMonitor:
    """
    Monitor data collection health and metrics.

    Tracks:
    - Collection rates and trends
    - Consent tier distribution
    - Data quality scores
    - Anomaly detection performance
    """

    def __init__(self):
        self._metrics: List[MetricPoint] = []
        self._max_history = 10000
        self._collection_stats = CollectionStats()
        self._consent_distribution = ConsentDistribution()
        self._quality_metrics = QualityMetrics()
        self._anomaly_counts: Dict[str, int] = {}
        self._last_update = datetime.utcnow()

    def record_metric(
        self,
        metric_type: MetricType,
        value: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MetricPoint:
        """Record a metric data point."""
        point = MetricPoint(
            metric_type=metric_type,
            value=value,
            metadata=metadata or {},
        )

        self._metrics.append(point)

        # Trim history
        if len(self._metrics) > self._max_history:
            self._metrics = self._metrics[-self._max_history:]

        return point

    def record_collection(
        self,
        user_id: str,
        data_category: str,
        record_count: int = 1,
    ) -> None:
        """Record a data collection event."""
        self._collection_stats.total_records += record_count
        self._collection_stats.records_last_hour += record_count
        self._collection_stats.records_last_day += record_count
        self._collection_stats.records_last_week += record_count

        # Track unique users (simplified - in production use a set or HLL)
        self._collection_stats.unique_users += 1

        self.record_metric(
            MetricType.COLLECTION_RATE,
            record_count,
            {"user_id": user_id[:8] + "...", "category": data_category},
        )

    def record_consent_change(
        self,
        old_tier: int,
        new_tier: int,
    ) -> None:
        """Record a consent tier change."""
        # Decrement old tier
        if old_tier == 0:
            self._consent_distribution.tier_0_none = max(0, self._consent_distribution.tier_0_none - 1)
        elif old_tier == 1:
            self._consent_distribution.tier_1_anonymous = max(0, self._consent_distribution.tier_1_anonymous - 1)
        elif old_tier == 2:
            self._consent_distribution.tier_2_pseudonymous = max(0, self._consent_distribution.tier_2_pseudonymous - 1)
        elif old_tier == 3:
            self._consent_distribution.tier_3_full = max(0, self._consent_distribution.tier_3_full - 1)

        # Increment new tier
        if new_tier == 0:
            self._consent_distribution.tier_0_none += 1
        elif new_tier == 1:
            self._consent_distribution.tier_1_anonymous += 1
        elif new_tier == 2:
            self._consent_distribution.tier_2_pseudonymous += 1
        elif new_tier == 3:
            self._consent_distribution.tier_3_full += 1

        self.record_metric(
            MetricType.CONSENT_RATE,
            new_tier,
            {"old_tier": old_tier, "new_tier": new_tier},
        )

    def record_new_user(self, consent_tier: int) -> None:
        """Record a new user with their consent tier."""
        self._consent_distribution.total_users += 1

        if consent_tier == 0:
            self._consent_distribution.tier_0_none += 1
        elif consent_tier == 1:
            self._consent_distribution.tier_1_anonymous += 1
        elif consent_tier == 2:
            self._consent_distribution.tier_2_pseudonymous += 1
        elif consent_tier == 3:
            self._consent_distribution.tier_3_full += 1

    def record_anomaly(self, anomaly_type: str) -> None:
        """Record an anomaly detection."""
        self._anomaly_counts[anomaly_type] = self._anomaly_counts.get(anomaly_type, 0) + 1

        self.record_metric(
            MetricType.ANOMALY_RATE,
            1.0,
            {"type": anomaly_type},
        )

    def record_deletion(self, user_id: str, record_count: int) -> None:
        """Record a data deletion event."""
        self.record_metric(
            MetricType.DELETION_RATE,
            record_count,
            {"user_id": user_id[:8] + "..."},
        )

    def update_quality_metrics(
        self,
        completeness: float,
        accuracy: float,
        freshness: float,
        consistency: float,
    ) -> QualityMetrics:
        """Update data quality metrics."""
        self._quality_metrics = QualityMetrics(
            completeness_score=completeness,
            accuracy_score=accuracy,
            freshness_score=freshness,
            consistency_score=consistency,
        )

        self.record_metric(
            MetricType.QUALITY_SCORE,
            self._quality_metrics.overall_score,
            self._quality_metrics.to_dict(),
        )

        return self._quality_metrics

    def get_metrics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get metrics summary for the past N hours."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent_metrics = [m for m in self._metrics if m.timestamp >= cutoff]

        # Group by type
        by_type: Dict[str, List[float]] = {}
        for m in recent_metrics:
            type_name = m.metric_type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(m.value)

        # Calculate stats
        summary = {}
        for type_name, values in by_type.items():
            summary[type_name] = {
                "count": len(values),
                "sum": sum(values),
                "avg": sum(values) / len(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
            }

        return {
            "period_hours": hours,
            "metrics": summary,
            "collection_stats": self._collection_stats.to_dict(),
            "consent_distribution": self._consent_distribution.to_dict(),
            "quality_metrics": self._quality_metrics.to_dict(),
            "anomaly_counts": self._anomaly_counts,
            "generated_at": datetime.utcnow().isoformat(),
        }

    def get_consent_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get consent tier trends over time."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        consent_metrics = [
            m for m in self._metrics
            if m.metric_type == MetricType.CONSENT_RATE and m.timestamp >= cutoff
        ]

        # Group by day
        by_day: Dict[str, Dict[str, int]] = {}
        for m in consent_metrics:
            day = m.timestamp.strftime("%Y-%m-%d")
            if day not in by_day:
                by_day[day] = {"upgrades": 0, "downgrades": 0}

            old_tier = m.metadata.get("old_tier", 0)
            new_tier = m.metadata.get("new_tier", 0)

            if new_tier > old_tier:
                by_day[day]["upgrades"] += 1
            elif new_tier < old_tier:
                by_day[day]["downgrades"] += 1

        return [
            {"date": day, **stats}
            for day, stats in sorted(by_day.items())
        ]

    def get_collection_rate_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get hourly collection rates."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        collection_metrics = [
            m for m in self._metrics
            if m.metric_type == MetricType.COLLECTION_RATE and m.timestamp >= cutoff
        ]

        # Group by hour
        by_hour: Dict[str, float] = {}
        for m in collection_metrics:
            hour = m.timestamp.strftime("%Y-%m-%d %H:00")
            by_hour[hour] = by_hour.get(hour, 0) + m.value

        return [
            {"hour": hour, "records": count}
            for hour, count in sorted(by_hour.items())
        ]

    async def run_hourly_rollup(self) -> None:
        """Run hourly metrics rollup (call this from a scheduler)."""
        # Reset hourly counters
        self._collection_stats.records_last_hour = 0

        # Calculate hourly average
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        hour_metrics = [
            m for m in self._metrics
            if m.metric_type == MetricType.COLLECTION_RATE and m.timestamp >= hour_ago
        ]

        hour_total = sum(m.value for m in hour_metrics)

        # Update peak if needed
        if hour_total > self._collection_stats.peak_hour_records:
            self._collection_stats.peak_hour_records = int(hour_total)

        logger.info(f"Hourly rollup complete: {hour_total} records collected")

    async def run_daily_rollup(self) -> None:
        """Run daily metrics rollup (call this from a scheduler)."""
        # Reset daily counter
        self._collection_stats.records_last_day = 0

        logger.info("Daily rollup complete")

    def reset_weekly_stats(self) -> None:
        """Reset weekly statistics."""
        self._collection_stats.records_last_week = 0

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall data collection health status."""
        quality = self._quality_metrics.overall_score
        consent_rate = self._consent_distribution.to_dict()["opt_in_rate"]

        # Determine health status
        if quality >= 0.8 and consent_rate >= 0.5:
            status = "healthy"
        elif quality >= 0.5 and consent_rate >= 0.25:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "quality_score": quality,
            "consent_rate": consent_rate,
            "collection_rate": self._collection_stats.avg_records_per_hour,
            "anomaly_rate": sum(self._anomaly_counts.values()) / max(self._collection_stats.total_records, 1),
            "checked_at": datetime.utcnow().isoformat(),
        }


# Singleton instance
_monitor: Optional[DataCollectionMonitor] = None


def get_data_collection_monitor() -> DataCollectionMonitor:
    """Get the global data collection monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = DataCollectionMonitor()
    return _monitor
