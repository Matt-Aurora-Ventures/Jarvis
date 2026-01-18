"""
Rate Limiter - Manage API rate limits and request throttling.
Implements token bucket, sliding window, and adaptive rate limiting.
"""
import asyncio
import sqlite3
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Tuple


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"
    ADAPTIVE = "adaptive"


class LimitScope(Enum):
    """Scope of rate limit."""
    GLOBAL = "global"              # Across all endpoints
    ENDPOINT = "endpoint"          # Per endpoint
    USER = "user"                  # Per user/wallet
    IP = "ip"                      # Per IP address


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""
    name: str
    requests_per_second: float
    burst_size: int                # Maximum burst
    strategy: RateLimitStrategy
    scope: LimitScope
    retry_after_seconds: float
    enabled: bool = True
    priority: int = 0              # Higher = more important
    metadata: Dict = field(default_factory=dict)


@dataclass
class RateLimitState:
    """Current state of a rate limiter."""
    name: str
    tokens: float                  # Current tokens (for token bucket)
    last_update: datetime
    request_count: int             # Requests in current window
    window_start: datetime
    is_limited: bool
    retry_after: Optional[datetime]


@dataclass
class RequestRecord:
    """Record of a request."""
    request_id: str
    endpoint: str
    scope_key: str
    timestamp: datetime
    allowed: bool
    wait_time_ms: float
    limit_name: Optional[str]


class TokenBucket:
    """Token bucket implementation."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate           # Tokens per second
        self.capacity = capacity   # Maximum tokens
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = threading.Lock()

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

    def acquire(self, tokens: int = 1) -> Tuple[bool, float]:
        """Try to acquire tokens. Returns (success, wait_time_seconds)."""
        with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0

            # Calculate wait time
            needed = tokens - self.tokens
            wait_time = needed / self.rate
            return False, wait_time

    async def acquire_async(self, tokens: int = 1) -> bool:
        """Acquire tokens, waiting if necessary."""
        success, wait_time = self.acquire(tokens)
        if success:
            return True

        await asyncio.sleep(wait_time)
        return self.acquire(tokens)[0]


class SlidingWindow:
    """Sliding window rate limiter."""

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: List[float] = []
        self._lock = threading.Lock()

    def _cleanup(self):
        """Remove old requests."""
        now = time.time()
        cutoff = now - self.window_seconds
        self.requests = [t for t in self.requests if t > cutoff]

    def acquire(self) -> Tuple[bool, float]:
        """Try to acquire a slot."""
        with self._lock:
            self._cleanup()

            if len(self.requests) < self.limit:
                self.requests.append(time.time())
                return True, 0

            # Calculate wait time
            oldest = min(self.requests)
            wait_time = oldest + self.window_seconds - time.time()
            return False, max(0, wait_time)


class AdaptiveLimiter:
    """Adaptive rate limiter that adjusts based on response times."""

    def __init__(self, initial_rate: float, min_rate: float, max_rate: float):
        self.current_rate = initial_rate
        self.min_rate = min_rate
        self.max_rate = max_rate
        self.response_times: List[float] = []
        self.error_count = 0
        self.success_count = 0
        self._bucket = TokenBucket(initial_rate, int(initial_rate * 2))
        self._lock = threading.Lock()

    def record_response(self, response_time_ms: float, success: bool):
        """Record response to adapt rate."""
        with self._lock:
            self.response_times.append(response_time_ms)
            if len(self.response_times) > 100:
                self.response_times.pop(0)

            if success:
                self.success_count += 1
            else:
                self.error_count += 1

            # Adapt rate every 10 requests
            if (self.success_count + self.error_count) % 10 == 0:
                self._adapt()

    def _adapt(self):
        """Adapt rate based on performance."""
        if not self.response_times:
            return

        avg_response = sum(self.response_times) / len(self.response_times)
        error_rate = self.error_count / (self.success_count + self.error_count)

        # Slow down if errors or slow responses
        if error_rate > 0.1 or avg_response > 1000:
            self.current_rate = max(self.min_rate, self.current_rate * 0.8)
        # Speed up if everything is good
        elif error_rate < 0.01 and avg_response < 200:
            self.current_rate = min(self.max_rate, self.current_rate * 1.1)

        self._bucket = TokenBucket(self.current_rate, int(self.current_rate * 2))

    def acquire(self) -> Tuple[bool, float]:
        return self._bucket.acquire()


class RateLimiter:
    """
    Comprehensive rate limiter supporting multiple strategies.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "rate_limiter.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Limiters by name
        self.limiters: Dict[str, Any] = {}
        self.configs: Dict[str, RateLimitConfig] = {}

        # Scoped limiters
        self.scoped_limiters: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Statistics
        self.stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "limited_requests": 0,
            "total_wait_time_ms": 0
        }

        self._lock = threading.Lock()

    @contextmanager
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_db() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS rate_configs (
                    name TEXT PRIMARY KEY,
                    requests_per_second REAL NOT NULL,
                    burst_size INTEGER NOT NULL,
                    strategy TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    retry_after_seconds REAL NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    priority INTEGER DEFAULT 0,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS request_log (
                    request_id TEXT PRIMARY KEY,
                    endpoint TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    allowed INTEGER NOT NULL,
                    wait_time_ms REAL NOT NULL,
                    limit_name TEXT
                );

                CREATE TABLE IF NOT EXISTS limit_stats (
                    name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_requests INTEGER DEFAULT 0,
                    allowed_requests INTEGER DEFAULT 0,
                    limited_requests INTEGER DEFAULT 0,
                    avg_wait_time_ms REAL DEFAULT 0,
                    PRIMARY KEY (name, date)
                );

                CREATE INDEX IF NOT EXISTS idx_requests_time ON request_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_requests_endpoint ON request_log(endpoint);
            """)

    def configure(
        self,
        name: str,
        requests_per_second: float,
        burst_size: Optional[int] = None,
        strategy: RateLimitStrategy = RateLimitStrategy.TOKEN_BUCKET,
        scope: LimitScope = LimitScope.GLOBAL,
        retry_after_seconds: float = 1.0,
        priority: int = 0
    ) -> RateLimitConfig:
        """Configure a rate limit."""
        import json

        if burst_size is None:
            burst_size = int(requests_per_second * 2)

        config = RateLimitConfig(
            name=name,
            requests_per_second=requests_per_second,
            burst_size=burst_size,
            strategy=strategy,
            scope=scope,
            retry_after_seconds=retry_after_seconds,
            priority=priority
        )

        self.configs[name] = config

        # Create limiter based on strategy
        if strategy == RateLimitStrategy.TOKEN_BUCKET:
            self.limiters[name] = TokenBucket(requests_per_second, burst_size)
        elif strategy == RateLimitStrategy.SLIDING_WINDOW:
            self.limiters[name] = SlidingWindow(burst_size, 1.0 / requests_per_second * burst_size)
        elif strategy == RateLimitStrategy.ADAPTIVE:
            self.limiters[name] = AdaptiveLimiter(
                requests_per_second,
                requests_per_second * 0.1,
                requests_per_second * 2
            )
        else:
            self.limiters[name] = TokenBucket(requests_per_second, burst_size)

        # Save to database
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO rate_configs
                (name, requests_per_second, burst_size, strategy, scope,
                 retry_after_seconds, enabled, priority, metadata)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, '{}')
            """, (
                name, requests_per_second, burst_size, strategy.value,
                scope.value, retry_after_seconds, priority
            ))

        return config

    def acquire(
        self,
        name: str,
        scope_key: Optional[str] = None,
        tokens: int = 1
    ) -> Tuple[bool, float]:
        """
        Try to acquire rate limit tokens.
        Returns (allowed, wait_time_seconds).
        """
        config = self.configs.get(name)
        if not config or not config.enabled:
            return True, 0

        # Get or create scoped limiter
        if config.scope != LimitScope.GLOBAL and scope_key:
            limiter = self._get_scoped_limiter(name, scope_key, config)
        else:
            limiter = self.limiters.get(name)

        if not limiter:
            return True, 0

        allowed, wait_time = limiter.acquire(tokens)

        # Update stats
        with self._lock:
            self.stats["total_requests"] += 1
            if allowed:
                self.stats["allowed_requests"] += 1
            else:
                self.stats["limited_requests"] += 1
                self.stats["total_wait_time_ms"] += wait_time * 1000

        return allowed, wait_time

    def _get_scoped_limiter(
        self,
        name: str,
        scope_key: str,
        config: RateLimitConfig
    ) -> Any:
        """Get or create a scoped limiter."""
        if scope_key not in self.scoped_limiters[name]:
            if config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                limiter = TokenBucket(config.requests_per_second, config.burst_size)
            elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                limiter = SlidingWindow(
                    config.burst_size,
                    1.0 / config.requests_per_second * config.burst_size
                )
            else:
                limiter = TokenBucket(config.requests_per_second, config.burst_size)

            self.scoped_limiters[name][scope_key] = limiter

        return self.scoped_limiters[name][scope_key]

    async def acquire_async(
        self,
        name: str,
        scope_key: Optional[str] = None,
        tokens: int = 1,
        wait: bool = True
    ) -> bool:
        """Acquire rate limit, optionally waiting."""
        allowed, wait_time = self.acquire(name, scope_key, tokens)

        if allowed:
            return True

        if wait and wait_time > 0:
            await asyncio.sleep(wait_time)
            return self.acquire(name, scope_key, tokens)[0]

        return False

    def record_response(
        self,
        name: str,
        response_time_ms: float,
        success: bool
    ):
        """Record response for adaptive rate limiting."""
        limiter = self.limiters.get(name)
        if isinstance(limiter, AdaptiveLimiter):
            limiter.record_response(response_time_ms, success)

    def get_state(self, name: str) -> Optional[RateLimitState]:
        """Get current state of a rate limiter."""
        config = self.configs.get(name)
        limiter = self.limiters.get(name)

        if not config or not limiter:
            return None

        now = datetime.now()

        if isinstance(limiter, TokenBucket):
            return RateLimitState(
                name=name,
                tokens=limiter.tokens,
                last_update=datetime.fromtimestamp(limiter.last_update),
                request_count=0,
                window_start=now,
                is_limited=limiter.tokens < 1,
                retry_after=now + timedelta(seconds=config.retry_after_seconds) if limiter.tokens < 1 else None
            )
        elif isinstance(limiter, SlidingWindow):
            return RateLimitState(
                name=name,
                tokens=limiter.limit - len(limiter.requests),
                last_update=now,
                request_count=len(limiter.requests),
                window_start=datetime.fromtimestamp(min(limiter.requests)) if limiter.requests else now,
                is_limited=len(limiter.requests) >= limiter.limit,
                retry_after=None
            )

        return None

    def reset(self, name: str, scope_key: Optional[str] = None):
        """Reset a rate limiter."""
        config = self.configs.get(name)
        if not config:
            return

        if scope_key and name in self.scoped_limiters:
            if scope_key in self.scoped_limiters[name]:
                del self.scoped_limiters[name][scope_key]
        else:
            # Recreate limiter
            self.configure(
                name=name,
                requests_per_second=config.requests_per_second,
                burst_size=config.burst_size,
                strategy=config.strategy,
                scope=config.scope,
                retry_after_seconds=config.retry_after_seconds
            )

    def enable(self, name: str, enabled: bool = True):
        """Enable or disable a rate limit."""
        if name in self.configs:
            self.configs[name].enabled = enabled

    def get_statistics(self) -> Dict:
        """Get rate limiter statistics."""
        with self._lock:
            return {
                **self.stats,
                "limit_rate": self.stats["limited_requests"] / self.stats["total_requests"]
                             if self.stats["total_requests"] > 0 else 0,
                "avg_wait_time_ms": self.stats["total_wait_time_ms"] / self.stats["limited_requests"]
                                   if self.stats["limited_requests"] > 0 else 0,
                "num_limiters": len(self.limiters),
                "num_scoped_limiters": sum(len(s) for s in self.scoped_limiters.values())
            }

    def cleanup_scoped(self, max_age_seconds: int = 3600):
        """Clean up old scoped limiters."""
        # Would track last access time per scoped limiter
        # For now, just clear all
        for name in list(self.scoped_limiters.keys()):
            self.scoped_limiters[name].clear()


# Pre-configured limiters for common APIs
def create_default_limiters(limiter: RateLimiter):
    """Create default rate limiters for common APIs."""
    # Solana RPC
    limiter.configure(
        "solana_rpc",
        requests_per_second=10,
        burst_size=20,
        strategy=RateLimitStrategy.TOKEN_BUCKET
    )

    # Jupiter API
    limiter.configure(
        "jupiter_api",
        requests_per_second=5,
        burst_size=10,
        strategy=RateLimitStrategy.TOKEN_BUCKET
    )

    # Birdeye API
    limiter.configure(
        "birdeye_api",
        requests_per_second=2,
        burst_size=5,
        strategy=RateLimitStrategy.SLIDING_WINDOW
    )

    # Helius API
    limiter.configure(
        "helius_api",
        requests_per_second=10,
        burst_size=25,
        strategy=RateLimitStrategy.ADAPTIVE
    )

    # DEXScreener
    limiter.configure(
        "dexscreener_api",
        requests_per_second=1,
        burst_size=3,
        strategy=RateLimitStrategy.SLIDING_WINDOW
    )


# Singleton instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
        create_default_limiters(_rate_limiter)
    return _rate_limiter
