"""
ClawdBots Rate Limiter Module.

Provides rate limiting for API calls using the token bucket algorithm.
Supports per-API and per-bot limits with request queuing.

Usage:
    from bots.shared.rate_limiter import check_rate_limit, wait_for_rate_limit

    # Check if request is allowed
    if check_rate_limit("telegram", "clawdjarvis"):
        # Make API call
        pass

    # Or wait until allowed (async)
    await wait_for_rate_limit("openai", "clawdmatt")
"""

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Any


# Default rate limits (requests per minute)
DEFAULT_LIMITS: Dict[str, int] = {
    "telegram": 30,
    "openai": 60,
    "anthropic": 60,
    "xai": 30,
}

# Default limit for unknown APIs
DEFAULT_UNKNOWN_LIMIT = 60

# Default state file path
DEFAULT_STATE_PATH = "/root/clawdbots/rate_limits.json"


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""

    capacity: float  # Max tokens (requests per minute)
    tokens: float = field(default=0.0)
    last_update: float = field(default_factory=time.time)
    requests_made: int = field(default=0)
    requests_blocked: int = field(default=0)

    def __post_init__(self):
        """Initialize tokens to full capacity."""
        if self.tokens == 0.0:
            self.tokens = float(self.capacity)

    @property
    def refill_rate(self) -> float:
        """Tokens per second (capacity is per minute)."""
        return self.capacity / 60.0

    def refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_update = now

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if successful."""
        self.refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            self.requests_made += 1
            return True

        self.requests_blocked += 1
        return False

    def time_until_token(self, tokens: float = 1.0) -> float:
        """Calculate time until tokens are available."""
        self.refill()

        if self.tokens >= tokens:
            return 0.0

        needed = tokens - self.tokens
        return needed / self.refill_rate

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "capacity": self.capacity,
            "tokens": self.tokens,
            "last_update": self.last_update,
            "requests_made": self.requests_made,
            "requests_blocked": self.requests_blocked,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TokenBucket":
        """Deserialize from dictionary."""
        return cls(
            capacity=data.get("capacity", DEFAULT_UNKNOWN_LIMIT),
            tokens=data.get("tokens", 0.0),
            last_update=data.get("last_update", time.time()),
            requests_made=data.get("requests_made", 0),
            requests_blocked=data.get("requests_blocked", 0),
        )


class RateLimiter:
    """
    Rate limiter using token bucket algorithm.

    Supports per-API and per-bot limits with persistence.
    """

    def __init__(
        self,
        limits: Optional[Dict[str, int]] = None,
        state_path: Optional[str] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            limits: Custom rate limits (requests per minute) by API name.
            state_path: Path to JSON file for state persistence.
        """
        self._limits = dict(DEFAULT_LIMITS)
        if limits:
            self._limits.update(limits)

        self._state_path = state_path or os.environ.get(
            "RATE_LIMIT_STATE_PATH", DEFAULT_STATE_PATH
        )

        # Buckets keyed by (api_name, bot_name)
        self._buckets: Dict[tuple, TokenBucket] = {}
        self._lock = threading.RLock()

        # Load persisted state
        self._load_state()

    def _get_bucket(self, api_name: str, bot_name: str) -> TokenBucket:
        """Get or create a token bucket for the given API/bot combination."""
        key = (api_name, bot_name)

        if key not in self._buckets:
            capacity = self._limits.get(api_name, DEFAULT_UNKNOWN_LIMIT)
            self._buckets[key] = TokenBucket(capacity=capacity)

        return self._buckets[key]

    def check(self, api_name: str, bot_name: str) -> bool:
        """
        Check if a request is allowed.

        Args:
            api_name: Name of the API (e.g., "telegram", "openai").
            bot_name: Name of the bot making the request.

        Returns:
            True if request is allowed, False if rate limited.

        Raises:
            TypeError: If api_name or bot_name is None.
            ValueError: If api_name or bot_name is invalid.
        """
        if api_name is None:
            raise TypeError("api_name cannot be None")
        if bot_name is None:
            raise TypeError("bot_name cannot be None")

        with self._lock:
            bucket = self._get_bucket(api_name, bot_name)
            result = bucket.consume()
            self._save_state()
            return result

    async def wait(self, api_name: str, bot_name: str) -> None:
        """
        Wait until a request is allowed.

        Args:
            api_name: Name of the API.
            bot_name: Name of the bot making the request.
        """
        if api_name is None:
            raise TypeError("api_name cannot be None")
        if bot_name is None:
            raise TypeError("bot_name cannot be None")

        while True:
            with self._lock:
                bucket = self._get_bucket(api_name, bot_name)
                wait_time = bucket.time_until_token()

            if wait_time <= 0:
                with self._lock:
                    bucket = self._get_bucket(api_name, bot_name)
                    if bucket.consume():
                        self._save_state()
                        return

            # Wait for tokens to refill
            await asyncio.sleep(max(wait_time, 0.01))

    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limit statistics.

        Returns:
            Dictionary with stats per API and per bot.
        """
        with self._lock:
            stats: Dict[str, Any] = {}

            for (api_name, bot_name), bucket in self._buckets.items():
                if api_name not in stats:
                    stats[api_name] = {
                        "requests": 0,
                        "blocked": 0,
                        "limit": self._limits.get(api_name, DEFAULT_UNKNOWN_LIMIT),
                        "by_bot": {},
                    }

                stats[api_name]["requests"] += bucket.requests_made
                stats[api_name]["blocked"] += bucket.requests_blocked
                stats[api_name]["by_bot"][bot_name] = {
                    "requests": bucket.requests_made,
                    "blocked": bucket.requests_blocked,
                    "tokens_remaining": bucket.tokens,
                }

            return stats

    def set_limit(self, api_name: str, requests_per_minute: int) -> None:
        """
        Set rate limit for an API.

        Args:
            api_name: Name of the API.
            requests_per_minute: Maximum requests per minute.

        Raises:
            ValueError: If requests_per_minute is negative.
        """
        if requests_per_minute < 0:
            raise ValueError("requests_per_minute cannot be negative")

        with self._lock:
            self._limits[api_name] = requests_per_minute

            # Update existing buckets for this API
            for (api, bot), bucket in self._buckets.items():
                if api == api_name:
                    bucket.capacity = requests_per_minute
                    # Don't overflow tokens
                    bucket.tokens = min(bucket.tokens, requests_per_minute)

            self._save_state()

    def reset(self) -> None:
        """Reset all rate limits and statistics."""
        with self._lock:
            self._buckets.clear()
            self._limits = dict(DEFAULT_LIMITS)
            self._save_state()

    def _load_state(self) -> None:
        """Load state from JSON file."""
        try:
            path = Path(self._state_path)
            if path.exists():
                with open(path, "r") as f:
                    data = json.load(f)

                # Restore limits
                if "limits" in data:
                    self._limits.update(data["limits"])

                # Restore buckets
                if "buckets" in data:
                    for key_str, bucket_data in data["buckets"].items():
                        # Key is stored as "api_name:bot_name"
                        parts = key_str.split(":", 1)
                        if len(parts) == 2:
                            key = (parts[0], parts[1])
                            self._buckets[key] = TokenBucket.from_dict(bucket_data)
        except (json.JSONDecodeError, IOError, OSError):
            # Ignore errors, use defaults
            pass

    def _save_state(self) -> None:
        """Save state to JSON file."""
        try:
            path = Path(self._state_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "limits": self._limits,
                "buckets": {
                    f"{api}:{bot}": bucket.to_dict()
                    for (api, bot), bucket in self._buckets.items()
                },
                "last_saved": time.time(),
            }

            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except (IOError, OSError):
            # Ignore save errors
            pass


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None
_limiter_lock = threading.Lock()


def _get_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter

    with _limiter_lock:
        if _rate_limiter is None:
            _rate_limiter = RateLimiter()
        return _rate_limiter


def check_rate_limit(api_name: str, bot_name: str) -> bool:
    """
    Check if a request is allowed.

    Args:
        api_name: Name of the API (e.g., "telegram", "openai").
        bot_name: Name of the bot making the request.

    Returns:
        True if request is allowed, False if rate limited.
    """
    return _get_limiter().check(api_name, bot_name)


async def wait_for_rate_limit(api_name: str, bot_name: str) -> None:
    """
    Wait until a request is allowed.

    Args:
        api_name: Name of the API.
        bot_name: Name of the bot making the request.
    """
    await _get_limiter().wait(api_name, bot_name)


def get_rate_limit_stats() -> Dict[str, Any]:
    """
    Get rate limit statistics.

    Returns:
        Dictionary with stats per API and per bot.
    """
    return _get_limiter().get_stats()


def set_rate_limit(api_name: str, requests_per_minute: int) -> None:
    """
    Set rate limit for an API.

    Args:
        api_name: Name of the API.
        requests_per_minute: Maximum requests per minute.
    """
    _get_limiter().set_limit(api_name, requests_per_minute)


def reset_rate_limits() -> None:
    """Reset all rate limits and statistics."""
    global _rate_limiter

    with _limiter_lock:
        if _rate_limiter is not None:
            _rate_limiter.reset()
        # Create fresh instance
        _rate_limiter = RateLimiter()
