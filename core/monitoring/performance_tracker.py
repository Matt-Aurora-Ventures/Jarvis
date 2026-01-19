"""
Performance Tracker - System and trading performance monitoring.

Tracks:
- System uptime (%)
- API availability (%)
- Average trade latency
- Bot recovery time after error

Thresholds:
- Uptime target: 99.5%
- API availability target: 99.9%

Alerts when metrics fall below targets.
"""

import json
import logging
import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.monitoring.performance_tracker")


@dataclass
class UptimeSample:
    """A single uptime sample."""
    timestamp: datetime
    is_up: bool


@dataclass
class APISample:
    """A single API availability sample."""
    timestamp: datetime
    service: str
    is_available: bool
    latency_ms: float


@dataclass
class TradeSample:
    """A single trade latency sample."""
    timestamp: datetime
    latency_ms: float


class PerformanceTracker:
    """
    Tracks system and trading performance metrics.

    Maintains rolling windows for:
    - Uptime samples (24h)
    - API availability (per service, 24h)
    - Trade latency (7 days)
    """

    def __init__(
        self,
        data_dir: str = "data/performance",
        uptime_target: float = 99.5,
        api_availability_target: float = 99.9,
        sample_retention_hours: int = 24,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.uptime_target = uptime_target
        self.api_availability_target = api_availability_target
        self.sample_retention_hours = sample_retention_hours

        # Sample storage
        self._uptime_samples: List[UptimeSample] = []
        self._api_samples: Dict[str, List[APISample]] = defaultdict(list)
        self._trade_samples: List[TradeSample] = []

        # Load existing data
        self._load_data()

    def _load_data(self):
        """Load persisted performance data."""
        data_path = self.data_dir / "performance_data.json"
        if data_path.exists():
            try:
                with open(data_path) as f:
                    data = json.load(f)

                # Load uptime samples
                for sample in data.get("uptime_samples", []):
                    self._uptime_samples.append(UptimeSample(
                        timestamp=datetime.fromisoformat(sample["timestamp"]),
                        is_up=sample["is_up"]
                    ))

                # Load API samples
                for service, samples in data.get("api_samples", {}).items():
                    for sample in samples:
                        self._api_samples[service].append(APISample(
                            timestamp=datetime.fromisoformat(sample["timestamp"]),
                            service=service,
                            is_available=sample["is_available"],
                            latency_ms=sample["latency_ms"]
                        ))

                # Load trade samples
                for sample in data.get("trade_samples", []):
                    self._trade_samples.append(TradeSample(
                        timestamp=datetime.fromisoformat(sample["timestamp"]),
                        latency_ms=sample["latency_ms"]
                    ))

                self._prune_old_samples()
            except Exception as e:
                logger.warning(f"Failed to load performance data: {e}")

    def _save_data(self):
        """Save performance data to disk."""
        self._prune_old_samples()

        data = {
            "uptime_samples": [
                {"timestamp": s.timestamp.isoformat(), "is_up": s.is_up}
                for s in self._uptime_samples[-10000:]  # Keep last 10k
            ],
            "api_samples": {
                service: [
                    {
                        "timestamp": s.timestamp.isoformat(),
                        "is_available": s.is_available,
                        "latency_ms": s.latency_ms
                    }
                    for s in samples[-5000:]  # Keep last 5k per service
                ]
                for service, samples in self._api_samples.items()
            },
            "trade_samples": [
                {"timestamp": s.timestamp.isoformat(), "latency_ms": s.latency_ms}
                for s in self._trade_samples[-10000:]
            ]
        }

        data_path = self.data_dir / "performance_data.json"
        try:
            with open(data_path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save performance data: {e}")

    def _prune_old_samples(self):
        """Remove samples older than retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.sample_retention_hours)

        self._uptime_samples = [
            s for s in self._uptime_samples if s.timestamp > cutoff
        ]

        for service in self._api_samples:
            self._api_samples[service] = [
                s for s in self._api_samples[service] if s.timestamp > cutoff
            ]

        # Trade samples kept longer (7 days)
        trade_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        self._trade_samples = [
            s for s in self._trade_samples if s.timestamp > trade_cutoff
        ]

    def record_uptime_sample(self, is_up: bool):
        """Record a system uptime sample."""
        sample = UptimeSample(
            timestamp=datetime.now(timezone.utc),
            is_up=is_up
        )
        self._uptime_samples.append(sample)
        self._save_data()

    def record_api_sample(
        self,
        service: str,
        is_available: bool,
        latency_ms: float
    ):
        """Record an API availability sample."""
        sample = APISample(
            timestamp=datetime.now(timezone.utc),
            service=service,
            is_available=is_available,
            latency_ms=latency_ms
        )
        self._api_samples[service].append(sample)
        self._save_data()

    def record_trade_latency(self, latency_ms: float):
        """Record a trade execution latency sample."""
        sample = TradeSample(
            timestamp=datetime.now(timezone.utc),
            latency_ms=latency_ms
        )
        self._trade_samples.append(sample)
        self._save_data()

    def get_uptime_stats(self) -> Dict[str, Any]:
        """Get uptime statistics."""
        if not self._uptime_samples:
            return {"uptime_percent": 100.0, "sample_count": 0}

        up_count = sum(1 for s in self._uptime_samples if s.is_up)
        total = len(self._uptime_samples)
        uptime_pct = (up_count / total) * 100 if total > 0 else 100.0

        return {
            "uptime_percent": round(uptime_pct, 2),
            "sample_count": total,
            "up_count": up_count,
            "down_count": total - up_count,
            "target": self.uptime_target,
            "meets_target": uptime_pct >= self.uptime_target
        }

    def get_api_availability(self) -> Dict[str, Dict[str, Any]]:
        """Get API availability statistics per service."""
        results = {}

        for service, samples in self._api_samples.items():
            if not samples:
                results[service] = {
                    "availability_percent": 100.0,
                    "sample_count": 0,
                    "avg_latency_ms": 0
                }
                continue

            available_count = sum(1 for s in samples if s.is_available)
            total = len(samples)
            availability_pct = (available_count / total) * 100 if total > 0 else 100.0

            latencies = [s.latency_ms for s in samples if s.is_available and s.latency_ms > 0]
            avg_latency = statistics.mean(latencies) if latencies else 0

            results[service] = {
                "availability_percent": round(availability_pct, 2),
                "sample_count": total,
                "avg_latency_ms": round(avg_latency, 2),
                "target": self.api_availability_target,
                "meets_target": availability_pct >= self.api_availability_target
            }

        return results

    def get_trade_latency_stats(self) -> Dict[str, Any]:
        """Get trade latency statistics."""
        if not self._trade_samples:
            return {
                "average_ms": 0,
                "min_ms": 0,
                "max_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "sample_count": 0
            }

        latencies = [s.latency_ms for s in self._trade_samples]

        return {
            "average_ms": round(statistics.mean(latencies), 2),
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "p50_ms": round(statistics.median(latencies), 2),
            "p95_ms": round(
                statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies),
                2
            ),
            "sample_count": len(latencies)
        }

    def check_targets(self) -> List[Dict[str, Any]]:
        """
        Check if performance targets are being met.

        Returns list of alerts for breached targets.
        """
        alerts = []

        # Check uptime
        uptime_stats = self.get_uptime_stats()
        if not uptime_stats.get("meets_target", True) and uptime_stats["sample_count"] > 10:
            alerts.append({
                "type": "uptime_breach",
                "severity": "warning",
                "message": f"System uptime ({uptime_stats['uptime_percent']:.1f}%) below target ({self.uptime_target}%)",
                "current": uptime_stats["uptime_percent"],
                "target": self.uptime_target
            })

        # Check API availability
        api_stats = self.get_api_availability()
        for service, stats in api_stats.items():
            if not stats.get("meets_target", True) and stats["sample_count"] > 10:
                alerts.append({
                    "type": "api_availability_breach",
                    "severity": "warning",
                    "message": f"API {service} availability ({stats['availability_percent']:.1f}%) below target ({self.api_availability_target}%)",
                    "service": service,
                    "current": stats["availability_percent"],
                    "target": self.api_availability_target
                })

        return alerts

    def get_all_stats(self) -> Dict[str, Any]:
        """Get all performance statistics."""
        return {
            "uptime": self.get_uptime_stats(),
            "api_availability": self.get_api_availability(),
            "trade_latency": self.get_trade_latency_stats(),
            "target_alerts": self.check_targets()
        }


# Singleton
_tracker: Optional[PerformanceTracker] = None


def get_performance_tracker() -> PerformanceTracker:
    """Get or create the performance tracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
    return _tracker
