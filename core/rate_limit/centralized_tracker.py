"""
Centralized Rate Limit Tracking
Reliability Audit Item #8: Centralized rate limit tracking and preemptive backoff

Provides system-wide visibility into rate limits across all services.

Features:
- Central registry of all rate limiters
- Usage tracking and metrics
- Preemptive backoff when approaching limits
- Cross-service coordination
- Dashboard-ready statistics
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

logger = logging.getLogger("jarvis.rate_limit.central")


class ServiceType(Enum):
    """Types of external services with rate limits"""
    SOLANA_RPC = "solana_rpc"
    JUPITER = "jupiter"
    HELIUS = "helius"
    BIRDEYE = "birdeye"
    DEXSCREENER = "dexscreener"
    TELEGRAM = "telegram"
    TWITTER = "twitter"
    GROK = "grok"
    COINGECKO = "coingecko"
    INTERNAL_API = "internal_api"
    CUSTOM = "custom"


@dataclass
class RateLimitState:
    """Current state of a rate limiter"""
    service: str
    requests_made: int
    requests_limit: int
    window_seconds: float
    window_start: float
    remaining: int
    reset_at: float
    is_limited: bool
    usage_pct: float


@dataclass
class RateLimitEvent:
    """A rate limit event (request or limit hit)"""
    timestamp: float
    service: str
    event_type: str  # 'request', 'limited', 'reset'
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceConfig:
    """Configuration for a service's rate limits"""
    service: str
    service_type: ServiceType
    requests_per_second: float = 10.0
    requests_per_minute: float = 300.0
    requests_per_hour: float = 10000.0
    burst_size: int = 20
    backoff_threshold_pct: float = 80.0  # Start backing off at 80% usage
    min_backoff_ms: int = 100
    max_backoff_ms: int = 5000


class CentralizedRateLimitTracker:
    """
    Central registry and tracker for all rate limiters.

    Provides:
    - Unified view of all rate limits
    - Usage statistics and trends
    - Preemptive backoff recommendations
    - Cross-service coordination
    """

    # Default configs for known services
    DEFAULT_CONFIGS = {
        ServiceType.SOLANA_RPC: ServiceConfig(
            service="solana_rpc",
            service_type=ServiceType.SOLANA_RPC,
            requests_per_second=50,
            requests_per_minute=1000,
            requests_per_hour=30000,
        ),
        ServiceType.JUPITER: ServiceConfig(
            service="jupiter",
            service_type=ServiceType.JUPITER,
            requests_per_second=10,
            requests_per_minute=300,
            requests_per_hour=5000,
        ),
        ServiceType.HELIUS: ServiceConfig(
            service="helius",
            service_type=ServiceType.HELIUS,
            requests_per_second=30,
            requests_per_minute=600,
            requests_per_hour=20000,
        ),
        ServiceType.TELEGRAM: ServiceConfig(
            service="telegram",
            service_type=ServiceType.TELEGRAM,
            requests_per_second=30,
            requests_per_minute=60,  # Conservative
            requests_per_hour=3600,
        ),
        ServiceType.TWITTER: ServiceConfig(
            service="twitter",
            service_type=ServiceType.TWITTER,
            requests_per_second=1,
            requests_per_minute=15,
            requests_per_hour=300,  # Twitter is very strict
        ),
        ServiceType.GROK: ServiceConfig(
            service="grok",
            service_type=ServiceType.GROK,
            requests_per_second=1,
            requests_per_minute=10,
            requests_per_hour=50,  # Grok daily limits
        ),
    }

    def __init__(
        self,
        cleanup_interval_sec: int = 60,
        history_window_sec: int = 3600,
    ):
        self.cleanup_interval_sec = cleanup_interval_sec
        self.history_window_sec = history_window_sec

        # Service configurations
        self._configs: Dict[str, ServiceConfig] = {}

        # Request tracking per service (sliding window)
        self._requests: Dict[str, Deque[float]] = {}

        # Rate limit events history
        self._events: Deque[RateLimitEvent] = deque(maxlen=10000)

        # Currently limited services
        self._limited_until: Dict[str, float] = {}

        # Callbacks for limit events
        self._callbacks: List[Callable[[str, str], None]] = []

        # Lock for thread safety
        self._lock = threading.Lock()

        # Initialize default configs
        for service_type, config in self.DEFAULT_CONFIGS.items():
            self.register_service(config)

        # Start cleanup thread
        self._running = True
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="RateLimitCleanup"
        )
        self._cleanup_thread.start()

    def stop(self):
        """Stop the tracker"""
        self._running = False

    def _cleanup_loop(self):
        """Background cleanup of old requests"""
        while self._running:
            try:
                self._cleanup_old_requests()
            except Exception as e:
                logger.error(f"Rate limit cleanup error: {e}")
            time.sleep(self.cleanup_interval_sec)

    def _cleanup_old_requests(self):
        """Remove requests older than tracking window"""
        cutoff = time.time() - self.history_window_sec

        with self._lock:
            for service in list(self._requests.keys()):
                requests = self._requests[service]
                while requests and requests[0] < cutoff:
                    requests.popleft()

    def register_service(
        self,
        config: ServiceConfig,
    ):
        """Register a service for rate limit tracking"""
        with self._lock:
            self._configs[config.service] = config
            if config.service not in self._requests:
                self._requests[config.service] = deque()

        logger.info(f"Registered rate limit tracking for {config.service}")

    def record_request(
        self,
        service: str,
        count: int = 1,
        metadata: Dict[str, Any] = None,
    ) -> Tuple[bool, Optional[float]]:
        """
        Record a request and check if rate limited.

        Args:
            service: Service name
            count: Number of requests to record
            metadata: Additional request metadata

        Returns:
            Tuple of (is_allowed, recommended_backoff_ms)
        """
        now = time.time()

        with self._lock:
            # Check if currently limited
            if service in self._limited_until:
                if now < self._limited_until[service]:
                    wait_time = (self._limited_until[service] - now) * 1000
                    return False, wait_time
                else:
                    del self._limited_until[service]

            # Get or create config
            config = self._configs.get(service)
            if config is None:
                # Create default config
                config = ServiceConfig(
                    service=service,
                    service_type=ServiceType.CUSTOM,
                )
                self._configs[service] = config
                self._requests[service] = deque()

            # Record request
            requests = self._requests[service]
            for _ in range(count):
                requests.append(now)

            # Record event
            self._events.append(RateLimitEvent(
                timestamp=now,
                service=service,
                event_type="request",
                metadata=metadata or {},
            ))

            # Calculate current usage
            cutoff_second = now - 1
            cutoff_minute = now - 60
            cutoff_hour = now - 3600

            count_second = sum(1 for t in requests if t >= cutoff_second)
            count_minute = sum(1 for t in requests if t >= cutoff_minute)
            count_hour = sum(1 for t in requests if t >= cutoff_hour)

            # Check limits
            is_limited = (
                count_second > config.requests_per_second or
                count_minute > config.requests_per_minute or
                count_hour > config.requests_per_hour
            )

            if is_limited:
                # Calculate backoff
                backoff_ms = min(
                    config.max_backoff_ms,
                    config.min_backoff_ms * (count_minute / config.requests_per_minute)
                )
                self._limited_until[service] = now + (backoff_ms / 1000)

                self._events.append(RateLimitEvent(
                    timestamp=now,
                    service=service,
                    event_type="limited",
                    metadata={"backoff_ms": backoff_ms},
                ))

                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(service, "limited")
                    except Exception as e:
                        logger.error(f"Rate limit callback error: {e}")

                return False, backoff_ms

            # Check if approaching limit (preemptive backoff)
            usage_pct = max(
                count_second / config.requests_per_second * 100,
                count_minute / config.requests_per_minute * 100,
            )

            if usage_pct >= config.backoff_threshold_pct:
                # Recommend backoff
                backoff_ms = config.min_backoff_ms * (usage_pct / 100)
                return True, backoff_ms

            return True, None

    def record_external_limit(
        self,
        service: str,
        retry_after_sec: float,
    ):
        """
        Record that an external service returned a rate limit.

        Args:
            service: Service name
            retry_after_sec: Seconds to wait (from Retry-After header)
        """
        now = time.time()

        with self._lock:
            self._limited_until[service] = now + retry_after_sec

            self._events.append(RateLimitEvent(
                timestamp=now,
                service=service,
                event_type="external_limit",
                metadata={"retry_after": retry_after_sec},
            ))

        logger.warning(f"External rate limit from {service}: wait {retry_after_sec}s")

    def get_state(self, service: str) -> Optional[RateLimitState]:
        """Get current rate limit state for a service"""
        now = time.time()

        with self._lock:
            config = self._configs.get(service)
            if config is None:
                return None

            requests = self._requests.get(service, deque())

            cutoff_minute = now - 60
            count_minute = sum(1 for t in requests if t >= cutoff_minute)

            usage_pct = (count_minute / config.requests_per_minute) * 100
            remaining = max(0, int(config.requests_per_minute - count_minute))

            is_limited = service in self._limited_until and now < self._limited_until[service]
            reset_at = self._limited_until.get(service, now + 60)

            return RateLimitState(
                service=service,
                requests_made=count_minute,
                requests_limit=int(config.requests_per_minute),
                window_seconds=60,
                window_start=cutoff_minute,
                remaining=remaining,
                reset_at=reset_at,
                is_limited=is_limited,
                usage_pct=usage_pct,
            )

    def get_all_states(self) -> Dict[str, RateLimitState]:
        """Get state for all tracked services"""
        states = {}
        with self._lock:
            services = list(self._configs.keys())

        for service in services:
            state = self.get_state(service)
            if state:
                states[service] = state

        return states

    def get_summary(self) -> Dict[str, Any]:
        """Get summary for health dashboard"""
        states = self.get_all_states()

        limited = [s.service for s in states.values() if s.is_limited]
        high_usage = [s.service for s in states.values() if s.usage_pct >= 80]

        return {
            "services_tracked": len(states),
            "currently_limited": limited,
            "high_usage": high_usage,
            "status": "warning" if limited else "ok",
            "by_service": {
                s.service: {
                    "usage_pct": round(s.usage_pct, 1),
                    "remaining": s.remaining,
                    "is_limited": s.is_limited,
                }
                for s in states.values()
            },
        }

    def on_limit_event(self, callback: Callable[[str, str], None]):
        """Register callback for rate limit events"""
        self._callbacks.append(callback)

    def get_recommended_delay(self, service: str) -> float:
        """
        Get recommended delay before next request.

        Returns delay in seconds, 0 if no delay needed.
        """
        state = self.get_state(service)
        if state is None:
            return 0

        if state.is_limited:
            return max(0, state.reset_at - time.time())

        if state.usage_pct >= 80:
            # Spread requests over remaining window
            config = self._configs.get(service)
            if config:
                return config.min_backoff_ms / 1000

        return 0


# =============================================================================
# SINGLETON
# =============================================================================

_tracker: Optional[CentralizedRateLimitTracker] = None


def get_rate_limit_tracker() -> CentralizedRateLimitTracker:
    """Get or create the rate limit tracker singleton"""
    global _tracker
    if _tracker is None:
        _tracker = CentralizedRateLimitTracker()
    return _tracker


def track_request(
    service: str,
    count: int = 1,
) -> Tuple[bool, Optional[float]]:
    """
    Convenience function to track a request.

    Returns:
        Tuple of (is_allowed, recommended_backoff_ms)
    """
    tracker = get_rate_limit_tracker()
    return tracker.record_request(service, count)


async def wait_if_needed(service: str):
    """
    Async helper that waits if rate limited.

    Usage:
        await wait_if_needed("jupiter")
        response = await make_request(...)
    """
    tracker = get_rate_limit_tracker()
    delay = tracker.get_recommended_delay(service)
    if delay > 0:
        logger.debug(f"Rate limit backoff for {service}: {delay:.2f}s")
        await asyncio.sleep(delay)
