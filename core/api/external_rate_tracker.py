"""
External API Rate Limit Tracker

Tracks usage and remaining limits for external APIs:
- Grok/XAI API
- Coingecko API
- Twitter/X API
- Jupiter API
- Birdeye API
- LunarCrush API
- CryptoPanic API

Features:
- Tracks requests per API
- Monitors rate limit headers
- Preemptive backoff before hitting limits
- Usage analytics and cost estimation
- Alerts when approaching limits
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, List, Callable, Any, Tuple
from threading import Lock

logger = logging.getLogger(__name__)

# State persistence
STATE_DIR = Path.home() / ".lifeos" / "api_tracking"
STATE_FILE = STATE_DIR / "external_api_usage.json"


class APIProvider(Enum):
    """External API providers."""
    GROK = "grok"
    COINGECKO = "coingecko"
    TWITTER = "twitter"
    JUPITER = "jupiter"
    BIRDEYE = "birdeye"
    LUNARCRUSH = "lunarcrush"
    CRYPTOPANIC = "cryptopanic"
    HELIUS = "helius"
    DEXSCREENER = "dexscreener"
    SOLSCAN = "solscan"


@dataclass
class APILimits:
    """Rate limits for an API."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    cost_per_request: float = 0.0  # In dollars
    daily_cost_limit: float = 10.0
    burst_limit: int = 10
    backoff_threshold: float = 0.8  # Start backoff at 80% usage


# Known API limits (conservative estimates)
DEFAULT_LIMITS: Dict[APIProvider, APILimits] = {
    APIProvider.GROK: APILimits(
        requests_per_minute=20,
        requests_per_hour=200,
        requests_per_day=1000,
        cost_per_request=0.002,  # ~$2 per 1000 requests
        daily_cost_limit=10.0,
    ),
    APIProvider.COINGECKO: APILimits(
        requests_per_minute=30,
        requests_per_hour=500,
        requests_per_day=10000,
        cost_per_request=0.0,  # Free tier
    ),
    APIProvider.TWITTER: APILimits(
        requests_per_minute=15,
        requests_per_hour=100,
        requests_per_day=500,
        cost_per_request=0.0,
    ),
    APIProvider.JUPITER: APILimits(
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=50000,
        cost_per_request=0.0,
    ),
    APIProvider.BIRDEYE: APILimits(
        requests_per_minute=30,
        requests_per_hour=500,
        requests_per_day=5000,
        cost_per_request=0.0,
    ),
    APIProvider.LUNARCRUSH: APILimits(
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=1000,
        cost_per_request=0.0,
    ),
    APIProvider.CRYPTOPANIC: APILimits(
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=1000,
        cost_per_request=0.0,
    ),
    APIProvider.HELIUS: APILimits(
        requests_per_minute=100,
        requests_per_hour=3000,
        requests_per_day=100000,
        cost_per_request=0.0,
    ),
    APIProvider.DEXSCREENER: APILimits(
        requests_per_minute=60,
        requests_per_hour=1000,
        requests_per_day=50000,
        cost_per_request=0.0,
    ),
    APIProvider.SOLSCAN: APILimits(
        requests_per_minute=30,
        requests_per_hour=500,
        requests_per_day=10000,
        cost_per_request=0.0,
    ),
}


@dataclass
class APIUsageWindow:
    """Usage tracking for a time window."""
    window_start: datetime
    request_count: int = 0
    total_cost: float = 0.0
    errors: int = 0
    rate_limited_count: int = 0


@dataclass
class APIUsageState:
    """Complete usage state for an API."""
    provider: str
    minute_window: APIUsageWindow
    hour_window: APIUsageWindow
    day_window: APIUsageWindow
    total_requests: int = 0
    total_cost: float = 0.0
    last_request: Optional[datetime] = None
    last_rate_limit: Optional[datetime] = None
    consecutive_errors: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'provider': self.provider,
            'total_requests': self.total_requests,
            'total_cost': self.total_cost,
            'last_request': self.last_request.isoformat() if self.last_request else None,
            'last_rate_limit': self.last_rate_limit.isoformat() if self.last_rate_limit else None,
            'minute_requests': self.minute_window.request_count,
            'hour_requests': self.hour_window.request_count,
            'day_requests': self.day_window.request_count,
            'day_cost': self.day_window.total_cost,
        }


class ExternalAPIRateTracker:
    """
    Tracks and manages rate limits for external APIs.

    Features:
    - Track usage per API
    - Preemptive rate limiting (back off before hitting limits)
    - Cost tracking
    - Persistent state
    - Alerts on approaching limits
    """

    def __init__(
        self,
        custom_limits: Optional[Dict[APIProvider, APILimits]] = None,
        alert_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self._limits = {**DEFAULT_LIMITS}
        if custom_limits:
            self._limits.update(custom_limits)

        self._usage: Dict[APIProvider, APIUsageState] = {}
        self._lock = Lock()
        self._alert_callback = alert_callback

        # Initialize usage states
        for provider in APIProvider:
            self._init_usage_state(provider)

        # Load persisted state
        self._load_state()

        logger.info(
            f"ExternalAPIRateTracker initialized with {len(self._limits)} providers"
        )

    def _init_usage_state(self, provider: APIProvider) -> None:
        """Initialize usage state for a provider."""
        now = datetime.utcnow()
        self._usage[provider] = APIUsageState(
            provider=provider.value,
            minute_window=APIUsageWindow(window_start=now),
            hour_window=APIUsageWindow(window_start=now),
            day_window=APIUsageWindow(window_start=now.replace(hour=0, minute=0, second=0)),
        )

    def _rotate_windows(self, state: APIUsageState) -> None:
        """Rotate time windows if needed."""
        now = datetime.utcnow()

        # Minute window
        if now - state.minute_window.window_start > timedelta(minutes=1):
            state.minute_window = APIUsageWindow(window_start=now)

        # Hour window
        if now - state.hour_window.window_start > timedelta(hours=1):
            state.hour_window = APIUsageWindow(window_start=now)

        # Day window
        if now.date() > state.day_window.window_start.date():
            state.day_window = APIUsageWindow(
                window_start=now.replace(hour=0, minute=0, second=0)
            )

    def can_request(self, provider: APIProvider) -> Tuple[bool, Optional[float]]:
        """
        Check if we can make a request to this API.

        Returns:
            (can_request, wait_time_seconds)
        """
        with self._lock:
            state = self._usage.get(provider)
            if not state:
                return True, None

            self._rotate_windows(state)
            limits = self._limits.get(provider, APILimits())

            # Check each window with backoff threshold
            threshold = limits.backoff_threshold

            # Minute limit
            if state.minute_window.request_count >= limits.requests_per_minute * threshold:
                wait = 60 - (datetime.utcnow() - state.minute_window.window_start).seconds
                return False, max(1, wait)

            # Hour limit
            if state.hour_window.request_count >= limits.requests_per_hour * threshold:
                wait = 3600 - (datetime.utcnow() - state.hour_window.window_start).seconds
                return False, max(1, wait)

            # Day limit
            if state.day_window.request_count >= limits.requests_per_day * threshold:
                # Wait until tomorrow
                return False, 3600  # Just wait an hour, will reset eventually

            # Cost limit
            if state.day_window.total_cost >= limits.daily_cost_limit * threshold:
                self._send_alert(
                    provider,
                    f"Approaching daily cost limit: ${state.day_window.total_cost:.2f}/${limits.daily_cost_limit:.2f}"
                )
                return False, 3600

            return True, None

    def record_request(
        self,
        provider: APIProvider,
        success: bool = True,
        rate_limited: bool = False,
        cost_override: Optional[float] = None,
    ) -> None:
        """Record a request to an API."""
        with self._lock:
            state = self._usage.get(provider)
            if not state:
                return

            self._rotate_windows(state)
            limits = self._limits.get(provider, APILimits())
            cost = cost_override if cost_override is not None else limits.cost_per_request

            now = datetime.utcnow()
            state.last_request = now
            state.total_requests += 1
            state.total_cost += cost

            # Update windows
            state.minute_window.request_count += 1
            state.hour_window.request_count += 1
            state.day_window.request_count += 1
            state.day_window.total_cost += cost

            if rate_limited:
                state.last_rate_limit = now
                state.minute_window.rate_limited_count += 1
                state.hour_window.rate_limited_count += 1
                state.day_window.rate_limited_count += 1

            if not success:
                state.consecutive_errors += 1
                state.minute_window.errors += 1
                state.hour_window.errors += 1
                state.day_window.errors += 1
            else:
                state.consecutive_errors = 0

            # Check if we should alert
            self._check_alerts(provider, state, limits)

    def _check_alerts(
        self,
        provider: APIProvider,
        state: APIUsageState,
        limits: APILimits,
    ) -> None:
        """Check if any alerts should be sent."""
        threshold = limits.backoff_threshold

        # Approaching limits
        if state.minute_window.request_count >= limits.requests_per_minute * threshold:
            self._send_alert(
                provider,
                f"Approaching minute limit: {state.minute_window.request_count}/{limits.requests_per_minute}"
            )

        if state.hour_window.request_count >= limits.requests_per_hour * threshold:
            self._send_alert(
                provider,
                f"Approaching hour limit: {state.hour_window.request_count}/{limits.requests_per_hour}"
            )

        if state.day_window.request_count >= limits.requests_per_day * threshold:
            self._send_alert(
                provider,
                f"Approaching day limit: {state.day_window.request_count}/{limits.requests_per_day}"
            )

        # High error rate
        if state.consecutive_errors >= 5:
            self._send_alert(
                provider,
                f"High error rate: {state.consecutive_errors} consecutive errors"
            )

    def _send_alert(self, provider: APIProvider, message: str) -> None:
        """Send an alert."""
        logger.warning(f"API Alert [{provider.value}]: {message}")
        if self._alert_callback:
            try:
                self._alert_callback(provider.value, message)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def get_usage(self, provider: APIProvider) -> Optional[Dict[str, Any]]:
        """Get usage statistics for an API."""
        with self._lock:
            state = self._usage.get(provider)
            if state:
                self._rotate_windows(state)
                limits = self._limits.get(provider, APILimits())
                return {
                    **state.to_dict(),
                    'limits': {
                        'requests_per_minute': limits.requests_per_minute,
                        'requests_per_hour': limits.requests_per_hour,
                        'requests_per_day': limits.requests_per_day,
                        'daily_cost_limit': limits.daily_cost_limit,
                    },
                    'usage_pct': {
                        'minute': state.minute_window.request_count / limits.requests_per_minute * 100,
                        'hour': state.hour_window.request_count / limits.requests_per_hour * 100,
                        'day': state.day_window.request_count / limits.requests_per_day * 100,
                    },
                }
            return None

    def get_all_usage(self) -> Dict[str, Dict[str, Any]]:
        """Get usage for all APIs."""
        return {
            provider.value: self.get_usage(provider)
            for provider in APIProvider
            if self.get_usage(provider)
        }

    def update_limits_from_headers(
        self,
        provider: APIProvider,
        headers: Dict[str, str],
    ) -> None:
        """
        Update limits based on API response headers.

        Common headers:
        - X-RateLimit-Limit
        - X-RateLimit-Remaining
        - X-RateLimit-Reset
        - Retry-After
        """
        with self._lock:
            limits = self._limits.get(provider)
            if not limits:
                return

            # Parse common rate limit headers
            if 'x-ratelimit-limit' in headers:
                try:
                    limits.requests_per_minute = int(headers['x-ratelimit-limit'])
                except ValueError:
                    pass

            if 'x-ratelimit-remaining' in headers:
                try:
                    remaining = int(headers['x-ratelimit-remaining'])
                    state = self._usage.get(provider)
                    if state:
                        # Sync our count with actual remaining
                        current_used = limits.requests_per_minute - remaining
                        if current_used > state.minute_window.request_count:
                            state.minute_window.request_count = current_used
                except ValueError:
                    pass

            logger.debug(f"Updated limits for {provider.value} from headers")

    def _load_state(self) -> None:
        """Load persisted state."""
        try:
            if STATE_FILE.exists():
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)

                # Restore total counts
                for provider_name, stats in data.items():
                    try:
                        provider = APIProvider(provider_name)
                        if provider in self._usage:
                            self._usage[provider].total_requests = stats.get('total_requests', 0)
                            self._usage[provider].total_cost = stats.get('total_cost', 0.0)
                    except ValueError:
                        pass

                logger.debug("Loaded API rate tracker state")
        except Exception as e:
            logger.warning(f"Failed to load rate tracker state: {e}")

    def save_state(self) -> None:
        """Persist state to disk."""
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True)

            data = {
                provider.value: {
                    'total_requests': state.total_requests,
                    'total_cost': state.total_cost,
                }
                for provider, state in self._usage.items()
            }

            with open(STATE_FILE, 'w') as f:
                json.dump(data, f, indent=2)

            logger.debug("Saved API rate tracker state")
        except Exception as e:
            logger.error(f"Failed to save rate tracker state: {e}")

    def reset_provider(self, provider: APIProvider) -> None:
        """Reset usage tracking for a provider."""
        with self._lock:
            self._init_usage_state(provider)
            logger.info(f"Reset usage tracking for {provider.value}")


# Global singleton
_tracker: Optional[ExternalAPIRateTracker] = None


def get_api_tracker() -> ExternalAPIRateTracker:
    """Get the global API rate tracker."""
    global _tracker
    if _tracker is None:
        _tracker = ExternalAPIRateTracker()
    return _tracker


# Convenience functions
def can_call_api(provider: APIProvider) -> Tuple[bool, Optional[float]]:
    """Check if we can call an API."""
    return get_api_tracker().can_request(provider)


def record_api_call(
    provider: APIProvider,
    success: bool = True,
    rate_limited: bool = False,
) -> None:
    """Record an API call."""
    get_api_tracker().record_request(provider, success, rate_limited)


def get_api_usage(provider: APIProvider) -> Optional[Dict[str, Any]]:
    """Get usage for an API."""
    return get_api_tracker().get_usage(provider)
