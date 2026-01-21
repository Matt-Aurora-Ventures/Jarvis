"""
Error Rate Tracking and Alerting
Reliability Audit Item #19: Error rate metrics and alerting

Tracks error rates across the system and triggers alerts when
thresholds are exceeded.

Features:
- Sliding window error counting
- Error categorization by type/source
- Configurable thresholds per category
- Automatic alert triggering
- Rate calculation (errors per minute)
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple
import threading

logger = logging.getLogger("jarvis.monitoring.error_rate")


class ErrorCategory(Enum):
    """Error categories for tracking"""
    API = "api"                    # REST API errors
    TRADING = "trading"            # Trading operation errors
    BLOCKCHAIN = "blockchain"      # Solana/blockchain errors
    EXTERNAL = "external"          # External service errors
    DATABASE = "database"          # Database errors
    AUTH = "auth"                  # Authentication errors
    VALIDATION = "validation"      # Input validation errors
    INTERNAL = "internal"          # Internal system errors
    TIMEOUT = "timeout"            # Timeout errors
    RATE_LIMIT = "rate_limit"      # Rate limit errors


@dataclass
class ErrorEvent:
    """A single error event"""
    timestamp: float
    category: ErrorCategory
    error_code: Optional[str]
    message: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorRateThreshold:
    """Threshold configuration for alerting"""
    category: ErrorCategory
    errors_per_minute: float
    errors_per_hour: float
    consecutive_errors: int = 5
    alert_cooldown_sec: int = 300  # 5 minutes between alerts


@dataclass
class ErrorRateStats:
    """Current error rate statistics"""
    category: str
    count_1min: int
    count_5min: int
    count_1hour: int
    rate_per_minute: float
    rate_per_hour: float
    last_error: Optional[datetime]
    threshold_exceeded: bool


class ErrorRateTracker:
    """
    Tracks error rates and triggers alerts when thresholds are exceeded.

    Uses sliding time windows to calculate error rates per category.
    Integrates with the Alerter system for notifications.
    """

    # Default thresholds
    DEFAULT_THRESHOLDS = {
        ErrorCategory.API: ErrorRateThreshold(
            category=ErrorCategory.API,
            errors_per_minute=10,
            errors_per_hour=100,
        ),
        ErrorCategory.TRADING: ErrorRateThreshold(
            category=ErrorCategory.TRADING,
            errors_per_minute=3,
            errors_per_hour=20,
            consecutive_errors=3,
        ),
        ErrorCategory.BLOCKCHAIN: ErrorRateThreshold(
            category=ErrorCategory.BLOCKCHAIN,
            errors_per_minute=5,
            errors_per_hour=50,
        ),
        ErrorCategory.EXTERNAL: ErrorRateThreshold(
            category=ErrorCategory.EXTERNAL,
            errors_per_minute=10,
            errors_per_hour=100,
        ),
        ErrorCategory.DATABASE: ErrorRateThreshold(
            category=ErrorCategory.DATABASE,
            errors_per_minute=5,
            errors_per_hour=30,
            consecutive_errors=3,
        ),
        ErrorCategory.AUTH: ErrorRateThreshold(
            category=ErrorCategory.AUTH,
            errors_per_minute=20,
            errors_per_hour=200,
        ),
        ErrorCategory.TIMEOUT: ErrorRateThreshold(
            category=ErrorCategory.TIMEOUT,
            errors_per_minute=10,
            errors_per_hour=100,
        ),
    }

    def __init__(
        self,
        window_size_sec: int = 3600,  # 1 hour window
        cleanup_interval_sec: int = 60,
    ):
        self.window_size_sec = window_size_sec
        self.cleanup_interval_sec = cleanup_interval_sec

        # Error storage by category
        self._errors: Dict[ErrorCategory, Deque[ErrorEvent]] = {
            cat: deque() for cat in ErrorCategory
        }

        # Thresholds
        self._thresholds: Dict[ErrorCategory, ErrorRateThreshold] = dict(
            self.DEFAULT_THRESHOLDS
        )

        # Alert state
        self._last_alert_time: Dict[ErrorCategory, float] = {}
        self._consecutive_errors: Dict[ErrorCategory, int] = {
            cat: 0 for cat in ErrorCategory
        }
        self._last_error_source: Dict[ErrorCategory, Optional[str]] = {
            cat: None for cat in ErrorCategory
        }

        # Callbacks
        self._alert_callbacks: List[Callable[[ErrorCategory, ErrorRateStats], None]] = []

        # Lock for thread safety
        self._lock = threading.Lock()

        # Start cleanup task
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="ErrorRateCleanup"
        )
        self._cleanup_thread.start()

    def stop(self):
        """Stop the cleanup thread"""
        self._running = False

    def _cleanup_loop(self):
        """Background cleanup of old errors"""
        while self._running:
            try:
                self._cleanup_old_errors()
            except Exception as e:
                logger.error(f"Error cleanup failed: {e}")
            time.sleep(self.cleanup_interval_sec)

    def _cleanup_old_errors(self):
        """Remove errors older than the window"""
        cutoff = time.time() - self.window_size_sec

        with self._lock:
            for category in ErrorCategory:
                errors = self._errors[category]
                while errors and errors[0].timestamp < cutoff:
                    errors.popleft()

    def record_error(
        self,
        category: ErrorCategory,
        message: str,
        source: str,
        error_code: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ):
        """
        Record an error event.

        Args:
            category: Error category
            message: Error message
            source: Source of the error (module/function)
            error_code: Optional structured error code
            metadata: Additional error context
        """
        now = time.time()

        event = ErrorEvent(
            timestamp=now,
            category=category,
            error_code=error_code,
            message=message,
            source=source,
            metadata=metadata or {},
        )

        with self._lock:
            self._errors[category].append(event)

            # Track consecutive errors from same source
            if self._last_error_source[category] == source:
                self._consecutive_errors[category] += 1
            else:
                self._consecutive_errors[category] = 1
                self._last_error_source[category] = source

        # Check thresholds (outside lock to avoid blocking)
        self._check_thresholds(category)

        logger.debug(f"Recorded error [{category.value}]: {message[:100]}")

    def _check_thresholds(self, category: ErrorCategory):
        """Check if error thresholds are exceeded"""
        threshold = self._thresholds.get(category)
        if threshold is None:
            return

        stats = self.get_stats(category)

        # Check if any threshold exceeded
        exceeded = False
        reason = []

        if stats.rate_per_minute > threshold.errors_per_minute:
            exceeded = True
            reason.append(f"rate {stats.rate_per_minute:.1f}/min > {threshold.errors_per_minute}/min")

        if stats.rate_per_hour > threshold.errors_per_hour:
            exceeded = True
            reason.append(f"rate {stats.rate_per_hour:.1f}/hr > {threshold.errors_per_hour}/hr")

        with self._lock:
            if self._consecutive_errors[category] >= threshold.consecutive_errors:
                exceeded = True
                reason.append(f"consecutive {self._consecutive_errors[category]} >= {threshold.consecutive_errors}")

        if not exceeded:
            return

        # Check cooldown
        now = time.time()
        last_alert = self._last_alert_time.get(category, 0)
        if now - last_alert < threshold.alert_cooldown_sec:
            return

        self._last_alert_time[category] = now

        # Trigger alert
        logger.warning(f"Error rate threshold exceeded for {category.value}: {', '.join(reason)}")

        for callback in self._alert_callbacks:
            try:
                callback(category, stats)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def get_stats(self, category: ErrorCategory) -> ErrorRateStats:
        """Get current error statistics for a category"""
        now = time.time()
        cutoff_1min = now - 60
        cutoff_5min = now - 300
        cutoff_1hr = now - 3600

        with self._lock:
            errors = self._errors[category]

            count_1min = sum(1 for e in errors if e.timestamp >= cutoff_1min)
            count_5min = sum(1 for e in errors if e.timestamp >= cutoff_5min)
            count_1hr = sum(1 for e in errors if e.timestamp >= cutoff_1hr)

            last_error = None
            if errors:
                last_error = datetime.fromtimestamp(errors[-1].timestamp, tz=timezone.utc)

        threshold = self._thresholds.get(category)
        threshold_exceeded = False
        if threshold:
            rate_per_min = count_1min
            rate_per_hr = count_1hr
            threshold_exceeded = (
                rate_per_min > threshold.errors_per_minute or
                rate_per_hr > threshold.errors_per_hour
            )

        return ErrorRateStats(
            category=category.value,
            count_1min=count_1min,
            count_5min=count_5min,
            count_1hour=count_1hr,
            rate_per_minute=count_1min,  # Errors in last minute = rate per minute
            rate_per_hour=count_1hr,
            last_error=last_error,
            threshold_exceeded=threshold_exceeded,
        )

    def get_all_stats(self) -> Dict[str, ErrorRateStats]:
        """Get stats for all categories"""
        return {
            cat.value: self.get_stats(cat)
            for cat in ErrorCategory
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get summary for health dashboard"""
        all_stats = self.get_all_stats()

        total_1min = sum(s.count_1min for s in all_stats.values())
        total_1hr = sum(s.count_1hour for s in all_stats.values())
        exceeded = [s.category for s in all_stats.values() if s.threshold_exceeded]

        return {
            "total_errors_1min": total_1min,
            "total_errors_1hr": total_1hr,
            "categories_exceeded": exceeded,
            "status": "warning" if exceeded else "ok",
            "by_category": {
                cat: {
                    "count_1min": s.count_1min,
                    "count_1hr": s.count_1hour,
                    "exceeded": s.threshold_exceeded,
                }
                for cat, s in all_stats.items()
                if s.count_1hr > 0
            },
        }

    def set_threshold(
        self,
        category: ErrorCategory,
        errors_per_minute: float = None,
        errors_per_hour: float = None,
        consecutive_errors: int = None,
    ):
        """Update thresholds for a category"""
        if category not in self._thresholds:
            self._thresholds[category] = ErrorRateThreshold(
                category=category,
                errors_per_minute=errors_per_minute or 10,
                errors_per_hour=errors_per_hour or 100,
            )
        else:
            threshold = self._thresholds[category]
            if errors_per_minute is not None:
                threshold = ErrorRateThreshold(
                    category=threshold.category,
                    errors_per_minute=errors_per_minute,
                    errors_per_hour=threshold.errors_per_hour,
                    consecutive_errors=threshold.consecutive_errors,
                    alert_cooldown_sec=threshold.alert_cooldown_sec,
                )
            if errors_per_hour is not None:
                threshold = ErrorRateThreshold(
                    category=threshold.category,
                    errors_per_minute=threshold.errors_per_minute,
                    errors_per_hour=errors_per_hour,
                    consecutive_errors=threshold.consecutive_errors,
                    alert_cooldown_sec=threshold.alert_cooldown_sec,
                )
            if consecutive_errors is not None:
                threshold = ErrorRateThreshold(
                    category=threshold.category,
                    errors_per_minute=threshold.errors_per_minute,
                    errors_per_hour=threshold.errors_per_hour,
                    consecutive_errors=consecutive_errors,
                    alert_cooldown_sec=threshold.alert_cooldown_sec,
                )
            self._thresholds[category] = threshold

    def on_threshold_exceeded(
        self,
        callback: Callable[[ErrorCategory, ErrorRateStats], None]
    ):
        """Register callback for threshold exceeded events"""
        self._alert_callbacks.append(callback)

    def get_recent_errors(
        self,
        category: Optional[ErrorCategory] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get recent error events"""
        with self._lock:
            if category:
                errors = list(self._errors[category])
            else:
                errors = []
                for cat_errors in self._errors.values():
                    errors.extend(cat_errors)
                errors.sort(key=lambda e: e.timestamp, reverse=True)

        return [
            {
                "timestamp": datetime.fromtimestamp(e.timestamp, tz=timezone.utc).isoformat(),
                "category": e.category.value,
                "error_code": e.error_code,
                "message": e.message[:200],
                "source": e.source,
            }
            for e in errors[-limit:]
        ]


# =============================================================================
# SINGLETON
# =============================================================================

_tracker: Optional[ErrorRateTracker] = None


def get_error_rate_tracker() -> ErrorRateTracker:
    """Get or create the error rate tracker singleton"""
    global _tracker
    if _tracker is None:
        _tracker = ErrorRateTracker()
    return _tracker


def record_error(
    category: ErrorCategory,
    message: str,
    source: str,
    error_code: Optional[str] = None,
    metadata: Dict[str, Any] = None,
):
    """Convenience function to record an error"""
    tracker = get_error_rate_tracker()
    tracker.record_error(
        category=category,
        message=message,
        source=source,
        error_code=error_code,
        metadata=metadata,
    )


# =============================================================================
# INTEGRATION WITH ALERTER
# =============================================================================

async def setup_alerter_integration():
    """Set up integration with the alerter system"""
    try:
        from core.monitoring.alerter import get_alerter, AlertType

        alerter = get_alerter()
        tracker = get_error_rate_tracker()

        async def on_threshold_exceeded(category: ErrorCategory, stats: ErrorRateStats):
            """Send alert when threshold exceeded"""
            message = (
                f"Error rate threshold exceeded for {category.value}:\n"
                f"- Errors in last minute: {stats.count_1min}\n"
                f"- Errors in last hour: {stats.count_1hour}\n"
                f"- Rate: {stats.rate_per_minute:.1f}/min"
            )

            await alerter.send_alert(
                alert_type=AlertType.WARNING,
                message=message,
                channels=["telegram", "log"],
                alert_id=f"error_rate_{category.value}",
            )

        def sync_callback(category: ErrorCategory, stats: ErrorRateStats):
            """Sync wrapper for async alert"""
            asyncio.create_task(on_threshold_exceeded(category, stats))

        tracker.on_threshold_exceeded(sync_callback)
        logger.info("Error rate tracker integrated with alerter")

    except ImportError:
        logger.warning("Alerter not available for integration")
