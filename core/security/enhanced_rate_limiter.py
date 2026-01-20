"""
Enhanced Rate Limiter

Production-grade rate limiting with:
- IP-based rate limiting
- User-based rate limiting
- Distributed request throttling
- Suspicious pattern detection
- DDoS protection
- Auto-blacklisting
"""

import logging
import sqlite3
import threading
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Set
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


class LimitScope(str, Enum):
    """Scope of rate limit."""
    GLOBAL = "global"
    IP = "ip"
    USER = "user"
    ENDPOINT = "endpoint"


class LimitStrategy(str, Enum):
    """Rate limiting strategy."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class LimitConfig:
    """Rate limit configuration."""
    name: str
    scope: str
    requests_per_minute: int
    burst_size: int = 0
    endpoint_pattern: Optional[str] = None
    strategy: str = "token_bucket"


@dataclass
class RequestRecord:
    """Record of a request."""
    ip_address: str
    endpoint: str
    timestamp: float
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # Tokens per second
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.time()
        self._lock = threading.Lock()

    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

    def acquire(self, tokens: int = 1) -> Tuple[bool, float]:
        """Try to acquire tokens."""
        with self._lock:
            self._refill()

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0

            # Calculate wait time
            needed = tokens - self.tokens
            wait_time = needed / self.rate if self.rate > 0 else float('inf')
            return False, wait_time


class SlidingWindow:
    """Sliding window rate limiter."""

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: List[float] = []
        self._lock = threading.Lock()

    def acquire(self) -> Tuple[bool, float]:
        """Try to acquire a slot."""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds

            # Remove old requests
            self.requests = [t for t in self.requests if t > cutoff]

            if len(self.requests) < self.limit:
                self.requests.append(now)
                return True, 0

            # Calculate wait time
            oldest = min(self.requests) if self.requests else now
            wait_time = oldest + self.window_seconds - now
            return False, max(0, wait_time)


class EnhancedRateLimiter:
    """
    Enhanced rate limiter with DDoS protection.

    Features:
    - Multiple limit scopes (IP, user, global)
    - Burst handling
    - Auto-blacklisting
    - Suspicious pattern detection
    - Distributed coordination via SQLite
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        default_requests_per_minute: int = 60,
        default_burst_size: int = 10,
        blacklist_threshold: int = 100,
        blacklist_window_minutes: int = 5
    ):
        """
        Initialize the enhanced rate limiter.

        Args:
            db_path: Path to SQLite database
            default_requests_per_minute: Default rate limit
            default_burst_size: Default burst allowance
            blacklist_threshold: Blocked requests before blacklist
            blacklist_window_minutes: Window for blacklist threshold
        """
        self.db_path = db_path or str(
            Path("data/rate_limiter") / "rate_limiter.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.default_rpm = default_requests_per_minute
        self.default_burst = default_burst_size
        self.blacklist_threshold = blacklist_threshold
        self.blacklist_window = timedelta(minutes=blacklist_window_minutes)

        self._instance_id = str(uuid.uuid4())[:8]

        # In-memory limiters
        self._limiters: Dict[str, Dict[str, TokenBucket]] = defaultdict(dict)
        self._configs: Dict[str, LimitConfig] = {}
        self._global_limiter: Optional[TokenBucket] = None

        # Request records for pattern detection
        self._request_records: List[RequestRecord] = []
        self._blocked_counts: Dict[str, List[float]] = defaultdict(list)

        # Blacklist/whitelist
        self._blacklist: Set[str] = set()
        self._whitelist: Set[str] = set()

        # Auto-blacklist config
        self._auto_blacklist_enabled = False
        self._auto_blacklist_threshold = 100
        self._auto_blacklist_window = timedelta(minutes=5)

        self._lock = threading.Lock()

        self._init_database()

    def _init_database(self):
        """Initialize the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS rate_configs (
                name TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                requests_per_minute INTEGER NOT NULL,
                burst_size INTEGER DEFAULT 0,
                endpoint_pattern TEXT,
                strategy TEXT DEFAULT 'token_bucket'
            );

            CREATE TABLE IF NOT EXISTS request_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                timestamp REAL NOT NULL,
                allowed INTEGER NOT NULL,
                instance_id TEXT
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                ip_address TEXT PRIMARY KEY,
                added_at TEXT NOT NULL,
                reason TEXT,
                expires_at TEXT
            );

            CREATE TABLE IF NOT EXISTS whitelist (
                ip_address TEXT PRIMARY KEY,
                added_at TEXT NOT NULL,
                reason TEXT
            );

            CREATE TABLE IF NOT EXISTS instances (
                instance_id TEXT PRIMARY KEY,
                last_heartbeat TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_request_ip ON request_log(ip_address);
            CREATE INDEX IF NOT EXISTS idx_request_time ON request_log(timestamp);
        """)

        conn.commit()
        conn.close()

        # Load blacklist/whitelist
        self._load_lists()

    def _load_lists(self):
        """Load blacklist and whitelist from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT ip_address FROM blacklist WHERE expires_at IS NULL OR expires_at > ?",
                      (datetime.now(timezone.utc).isoformat(),))
        for row in cursor.fetchall():
            self._blacklist.add(row[0])

        cursor.execute("SELECT ip_address FROM whitelist")
        for row in cursor.fetchall():
            self._whitelist.add(row[0])

        conn.close()

    def configure_limit(
        self,
        name: str,
        scope: str,
        requests_per_minute: int,
        burst_size: Optional[int] = None,
        endpoint_pattern: Optional[str] = None,
        strategy: str = "token_bucket"
    ) -> Dict[str, Any]:
        """
        Configure a rate limit.

        Args:
            name: Limit name
            scope: 'ip', 'user', 'global', or 'endpoint'
            requests_per_minute: Max requests per minute
            burst_size: Burst allowance
            endpoint_pattern: Optional endpoint pattern
            strategy: 'token_bucket' or 'sliding_window'
        """
        if burst_size is None:
            burst_size = max(1, requests_per_minute // 6)

        config = LimitConfig(
            name=name,
            scope=scope,
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
            endpoint_pattern=endpoint_pattern,
            strategy=strategy
        )

        self._configs[name] = config

        # Create global limiter if needed
        if scope == "global":
            rate = requests_per_minute / 60.0
            self._global_limiter = TokenBucket(rate, burst_size)

        # Persist
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO rate_configs
            (name, scope, requests_per_minute, burst_size, endpoint_pattern, strategy)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, scope, requests_per_minute, burst_size, endpoint_pattern, strategy))
        conn.commit()
        conn.close()

        return {"success": True, "name": name}

    def _get_or_create_limiter(
        self,
        name: str,
        key: str,
        config: LimitConfig
    ) -> TokenBucket:
        """Get or create a limiter for the given key."""
        if key not in self._limiters[name]:
            rate = config.requests_per_minute / 60.0
            self._limiters[name][key] = TokenBucket(rate, config.burst_size)
        return self._limiters[name][key]

    def check_ip_limit(
        self,
        ip_address: str,
        endpoint: str
    ) -> Dict[str, Any]:
        """
        Check if request from IP is allowed.

        Args:
            ip_address: Client IP
            endpoint: Request endpoint

        Returns:
            Dict with 'allowed' and optional 'retry_after'
        """
        # Check whitelist
        if ip_address in self._whitelist:
            return {"allowed": True, "whitelisted": True}

        # Check blacklist
        if ip_address in self._blacklist:
            return {"allowed": False, "reason": "blacklisted"}

        # Find matching config
        config = None
        for cfg in self._configs.values():
            if cfg.scope == "ip":
                if cfg.endpoint_pattern is None or endpoint.startswith(cfg.endpoint_pattern):
                    config = cfg
                    break

        if config is None:
            return {"allowed": True, "no_limit_configured": True}

        limiter = self._get_or_create_limiter(config.name, ip_address, config)
        allowed, wait_time = limiter.acquire()

        if not allowed:
            self._record_blocked(ip_address)
            self._check_auto_blacklist(ip_address)

        return {
            "allowed": allowed,
            "retry_after": wait_time if not allowed else None
        }

    def check_user_limit(
        self,
        user_id: str,
        endpoint: str
    ) -> Dict[str, Any]:
        """
        Check if request from user is allowed.

        Args:
            user_id: User ID
            endpoint: Request endpoint

        Returns:
            Dict with 'allowed' and optional 'retry_after'
        """
        # Find matching config
        config = None
        for cfg in self._configs.values():
            if cfg.scope == "user":
                if cfg.endpoint_pattern is None or endpoint.startswith(cfg.endpoint_pattern):
                    config = cfg
                    break

        if config is None:
            return {"allowed": True, "no_limit_configured": True}

        limiter = self._get_or_create_limiter(config.name, user_id, config)
        allowed, wait_time = limiter.acquire()

        return {
            "allowed": allowed,
            "retry_after": wait_time if not allowed else None
        }

    def check_global_limit(
        self,
        endpoint: str
    ) -> Dict[str, Any]:
        """
        Check global rate limit.

        Args:
            endpoint: Request endpoint

        Returns:
            Dict with 'allowed'
        """
        if self._global_limiter is None:
            return {"allowed": True, "no_limit_configured": True}

        allowed, wait_time = self._global_limiter.acquire()

        return {
            "allowed": allowed,
            "retry_after": wait_time if not allowed else None
        }

    def record_request(
        self,
        ip_address: str,
        endpoint: str,
        timestamp: Optional[float] = None,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Record a request for pattern analysis.

        Args:
            ip_address: Client IP
            endpoint: Request endpoint
            timestamp: Request timestamp
            success: Whether request succeeded
            metadata: Additional metadata
        """
        record = RequestRecord(
            ip_address=ip_address,
            endpoint=endpoint,
            timestamp=timestamp or time.time(),
            success=success,
            metadata=metadata or {}
        )

        with self._lock:
            self._request_records.append(record)

            # Keep only last 10000 records
            if len(self._request_records) > 10000:
                self._request_records = self._request_records[-5000:]

    def _record_blocked(self, ip_address: str):
        """Record a blocked request for auto-blacklist."""
        now = time.time()
        self._blocked_counts[ip_address].append(now)

        # Clean old records
        cutoff = now - self._auto_blacklist_window.total_seconds()
        self._blocked_counts[ip_address] = [
            t for t in self._blocked_counts[ip_address] if t > cutoff
        ]

    def _check_auto_blacklist(self, ip_address: str):
        """Check if IP should be auto-blacklisted."""
        if not self._auto_blacklist_enabled:
            return

        blocked_count = len(self._blocked_counts.get(ip_address, []))
        if blocked_count >= self._auto_blacklist_threshold:
            self._blacklist.add(ip_address)

            # Persist
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO blacklist (ip_address, added_at, reason)
                VALUES (?, ?, ?)
            """, (
                ip_address,
                datetime.now(timezone.utc).isoformat(),
                f"auto_blacklist:exceeded_{blocked_count}_blocked_requests"
            ))
            conn.commit()
            conn.close()

            logger.warning(f"Auto-blacklisted IP: {ip_address}")

    def configure_auto_blacklist(
        self,
        blocked_threshold: int,
        time_window_minutes: int
    ):
        """Configure automatic blacklisting."""
        self._auto_blacklist_enabled = True
        self._auto_blacklist_threshold = blocked_threshold
        self._auto_blacklist_window = timedelta(minutes=time_window_minutes)

    def is_ip_blacklisted(self, ip_address: str) -> bool:
        """Check if IP is blacklisted."""
        return ip_address in self._blacklist

    def add_to_whitelist(self, ip_address: str, reason: str = "manual"):
        """Add IP to whitelist."""
        self._whitelist.add(ip_address)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO whitelist (ip_address, added_at, reason)
            VALUES (?, ?, ?)
        """, (ip_address, datetime.now(timezone.utc).isoformat(), reason))
        conn.commit()
        conn.close()

    def detect_ddos_pattern(
        self,
        endpoint: str,
        time_window_seconds: int = 60,
        threshold_requests: int = 1000
    ) -> Dict[str, Any]:
        """
        Detect DDoS pattern on an endpoint.

        Args:
            endpoint: Target endpoint
            time_window_seconds: Analysis window
            threshold_requests: Request count threshold

        Returns:
            DDoS detection results
        """
        now = time.time()
        cutoff = now - time_window_seconds

        matching_requests = [
            r for r in self._request_records
            if r.timestamp > cutoff and r.endpoint == endpoint
        ]

        request_count = len(matching_requests)
        unique_ips = len(set(r.ip_address for r in matching_requests))

        ddos_detected = request_count >= threshold_requests

        return {
            "ddos_detected": ddos_detected,
            "request_count": request_count,
            "unique_ips": unique_ips,
            "time_window_seconds": time_window_seconds,
            "threshold": threshold_requests
        }

    def detect_suspicious_pattern(
        self,
        ip_address: str
    ) -> Dict[str, Any]:
        """
        Detect suspicious patterns from an IP.

        Args:
            ip_address: IP to analyze

        Returns:
            Suspicious pattern analysis
        """
        now = time.time()
        cutoff = now - 300  # Last 5 minutes

        ip_requests = [
            r for r in self._request_records
            if r.ip_address == ip_address and r.timestamp > cutoff
        ]

        patterns = []
        is_suspicious = False

        if not ip_requests:
            return {"is_suspicious": False, "patterns": []}

        # Check endpoint diversity (scanning)
        unique_endpoints = set(r.endpoint for r in ip_requests)
        if len(unique_endpoints) > 50:
            patterns.append("endpoint_scanning")
            is_suspicious = True

        # Check failure rate (credential stuffing)
        failed_requests = [r for r in ip_requests if not r.success]
        if len(ip_requests) > 10:
            failure_rate = len(failed_requests) / len(ip_requests)
            if failure_rate > 0.9:
                patterns.append("credential_stuffing")
                is_suspicious = True

        # Check timing regularity (bot)
        if len(ip_requests) > 5:
            timestamps = sorted(r.timestamp for r in ip_requests)
            deltas = [timestamps[i] - timestamps[i-1] for i in range(1, len(timestamps))]

            if deltas:
                avg_delta = statistics.mean(deltas)
                std_delta = statistics.stdev(deltas) if len(deltas) > 1 else float('inf')

                # Very regular timing = bot
                if std_delta < 0.5 and avg_delta < 5:
                    patterns.append("bot_like_timing")
                    is_suspicious = True

        return {
            "is_suspicious": is_suspicious,
            "patterns": patterns,
            "request_count": len(ip_requests),
            "unique_endpoints": len(unique_endpoints),
            "failed_login_rate": len(failed_requests) / len(ip_requests) if ip_requests else 0,
            "timing_regularity": 1 - (statistics.stdev(deltas) / statistics.mean(deltas)
                                      if deltas and statistics.mean(deltas) > 0 else 0)
                                 if len(ip_requests) > 5 else None
        }

    def get_instance_id(self) -> str:
        """Get this instance's ID."""
        return self._instance_id

    def heartbeat(self):
        """Record heartbeat for this instance."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO instances (instance_id, last_heartbeat)
            VALUES (?, ?)
        """, (self._instance_id, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()

    def get_active_instances(self, timeout_seconds: int = 60) -> List[str]:
        """Get list of active instances."""
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=timeout_seconds)).isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT instance_id FROM instances WHERE last_heartbeat > ?",
            (cutoff,)
        )
        instances = [row[0] for row in cursor.fetchall()]
        conn.close()

        return instances


# Singleton
_rate_limiter: Optional[EnhancedRateLimiter] = None


def get_enhanced_rate_limiter() -> EnhancedRateLimiter:
    """Get or create the enhanced rate limiter singleton."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = EnhancedRateLimiter()
    return _rate_limiter
