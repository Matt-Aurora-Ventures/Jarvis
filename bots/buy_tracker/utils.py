"""
Buy Tracker Utilities - Retry logic, rate limiting, validation, and helpers.
"""

import asyncio
import time
import logging
import re
import html
import hashlib
from functools import wraps
from typing import Optional, Callable, Any, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)


# === RETRY WITH EXPONENTIAL BACKOFF ===

@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


def retry_async(config: Optional[RetryConfig] = None):
    """
    Decorator for async functions with exponential backoff retry.

    Usage:
        @retry_async(RetryConfig(max_retries=5))
        async def my_function():
            ...
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt == config.max_retries:
                        logger.error(f"{func.__name__} failed after {config.max_retries + 1} attempts: {e}")
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )

                    # Add jitter to prevent thundering herd
                    if config.jitter:
                        import random
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)

            raise last_exception
        return wrapper
    return decorator


def retry_sync(config: Optional[RetryConfig] = None):
    """
    Decorator for sync functions with exponential backoff retry.
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt == config.max_retries:
                        logger.error(f"{func.__name__} failed after {config.max_retries + 1} attempts: {e}")
                        raise

                    delay = min(
                        config.base_delay * (config.exponential_base ** attempt),
                        config.max_delay
                    )

                    if config.jitter:
                        import random
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)

            raise last_exception
        return wrapper
    return decorator


# === RATE LIMITER ===

class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    Usage:
        limiter = RateLimiter(max_requests=30, window_seconds=60)

        async def send_message():
            await limiter.acquire()
            # send message...
    """

    def __init__(self, max_requests: int = 30, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: list = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Acquire a rate limit token. Blocks if limit exceeded."""
        async with self._lock:
            now = time.time()

            # Remove old requests outside window
            self.requests = [t for t in self.requests if now - t < self.window_seconds]

            if len(self.requests) >= self.max_requests:
                # Calculate wait time
                oldest = min(self.requests)
                wait_time = self.window_seconds - (now - oldest) + 0.1

                if wait_time > 0:
                    logger.debug(f"Rate limit hit, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)

                    # Clean up again after waiting
                    now = time.time()
                    self.requests = [t for t in self.requests if now - t < self.window_seconds]

            self.requests.append(now)
            return True

    def can_proceed(self) -> bool:
        """Check if we can proceed without blocking."""
        now = time.time()
        self.requests = [t for t in self.requests if now - t < self.window_seconds]
        return len(self.requests) < self.max_requests


class TelegramRateLimiter:
    """
    Telegram-specific rate limiter respecting their limits.

    Limits:
    - 30 messages per second to same chat
    - 20 messages per minute to same group
    - 1 message per second global
    """

    def __init__(self):
        self.global_limiter = RateLimiter(max_requests=30, window_seconds=1.0)
        self.chat_limiters: Dict[str, RateLimiter] = defaultdict(
            lambda: RateLimiter(max_requests=20, window_seconds=60.0)
        )
        self._lock = asyncio.Lock()

    async def acquire(self, chat_id: str):
        """Acquire rate limit for a specific chat."""
        async with self._lock:
            await self.global_limiter.acquire()
            await self.chat_limiters[chat_id].acquire()


# Singleton instances
_telegram_limiter: Optional[TelegramRateLimiter] = None

def get_telegram_limiter() -> TelegramRateLimiter:
    """Get singleton Telegram rate limiter."""
    global _telegram_limiter
    if _telegram_limiter is None:
        _telegram_limiter = TelegramRateLimiter()
    return _telegram_limiter


# === CIRCUIT BREAKER ===

@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.

    States:
    - CLOSED: Normal operation
    - OPEN: Failing, reject all calls
    - HALF_OPEN: Testing if service recovered

    Usage:
        breaker = CircuitBreaker("jupiter_api")

        async def call_jupiter():
            if not breaker.can_proceed():
                raise CircuitOpenError("Jupiter API circuit is open")

            try:
                result = await jupiter_api.swap()
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                raise
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = self.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self._lock = asyncio.Lock()

    async def can_proceed(self) -> bool:
        """Check if request can proceed."""
        async with self._lock:
            if self.state == self.CLOSED:
                return True

            if self.state == self.OPEN:
                # Check if recovery timeout elapsed
                if self.last_failure_time:
                    elapsed = time.time() - self.last_failure_time
                    if elapsed >= self.config.recovery_timeout:
                        logger.info(f"Circuit {self.name} transitioning to HALF_OPEN")
                        self.state = self.HALF_OPEN
                        self.half_open_calls = 0
                        return True
                return False

            if self.state == self.HALF_OPEN:
                if self.half_open_calls < self.config.half_open_max_calls:
                    self.half_open_calls += 1
                    return True
                return False

            return False

    async def record_success(self):
        """Record a successful call."""
        async with self._lock:
            if self.state == self.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.half_open_max_calls:
                    logger.info(f"Circuit {self.name} recovered, transitioning to CLOSED")
                    self.state = self.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == self.CLOSED:
                self.failure_count = 0

    async def record_failure(self):
        """Record a failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == self.HALF_OPEN:
                logger.warning(f"Circuit {self.name} failed in HALF_OPEN, transitioning to OPEN")
                self.state = self.OPEN
                self.success_count = 0
            elif self.state == self.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    logger.warning(f"Circuit {self.name} threshold reached, transitioning to OPEN")
                    self.state = self.OPEN


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# === INPUT VALIDATION & SANITIZATION ===

# Solana address regex (base58, 32-44 chars)
SOLANA_ADDRESS_REGEX = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')

def is_valid_solana_address(address: str) -> bool:
    """Validate Solana address format."""
    if not address or not isinstance(address, str):
        return False
    return bool(SOLANA_ADDRESS_REGEX.match(address))


def sanitize_token_name(name: str, max_length: int = 50) -> str:
    """
    Sanitize token name for safe display.
    - Escape HTML entities
    - Remove control characters
    - Truncate to max length
    """
    if not name:
        return "Unknown"

    # Remove control characters
    name = ''.join(c for c in name if c.isprintable())

    # Escape HTML
    name = html.escape(name)

    # Truncate
    if len(name) > max_length:
        name = name[:max_length - 3] + "..."

    return name


def sanitize_telegram_message(text: str) -> str:
    """
    Sanitize text for Telegram message.
    - Escape special characters for MarkdownV2
    - Remove null bytes
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace('\x00', '')

    # For HTML parse mode, escape these
    text = html.escape(text)

    return text


def generate_dedup_key(tx_signature: str, token_mint: str) -> str:
    """Generate a deduplication key for an alert."""
    content = f"{tx_signature}:{token_mint}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# === HTTP TIMEOUT WRAPPER ===

DEFAULT_TIMEOUT = 30.0  # seconds

def get_timeout_config(timeout: Optional[float] = None) -> Dict[str, float]:
    """Get aiohttp timeout configuration."""
    t = timeout or DEFAULT_TIMEOUT
    return {
        'total': t,
        'connect': min(t / 3, 10.0),
        'sock_read': t,
        'sock_connect': min(t / 3, 10.0)
    }


# === SPENDING LIMITS ===

@dataclass
class SpendingLimits:
    """Spending limits for treasury protection."""
    max_single_trade_sol: float = 0.1
    max_single_trade_usd: float = 50.0
    max_daily_sol: float = 1.0
    max_daily_usd: float = 500.0
    max_position_percent: float = 10.0  # Max % of portfolio in single position

    daily_spent_sol: float = field(default=0.0)
    daily_spent_usd: float = field(default=0.0)
    last_reset: str = field(default="")

    def check_trade(self, amount_sol: float, amount_usd: float) -> tuple[bool, str]:
        """Check if trade is within limits. Returns (allowed, reason)."""
        # Reset daily counters if new day
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.last_reset != today:
            self.daily_spent_sol = 0.0
            self.daily_spent_usd = 0.0
            self.last_reset = today

        # Check single trade limits
        if amount_sol > self.max_single_trade_sol:
            return False, f"Trade exceeds max single trade ({amount_sol:.4f} > {self.max_single_trade_sol:.4f} SOL)"

        if amount_usd > self.max_single_trade_usd:
            return False, f"Trade exceeds max single trade (${amount_usd:.2f} > ${self.max_single_trade_usd:.2f})"

        # Check daily limits
        if self.daily_spent_sol + amount_sol > self.max_daily_sol:
            return False, f"Trade would exceed daily limit ({self.daily_spent_sol + amount_sol:.4f} > {self.max_daily_sol:.4f} SOL)"

        if self.daily_spent_usd + amount_usd > self.max_daily_usd:
            return False, f"Trade would exceed daily limit (${self.daily_spent_usd + amount_usd:.2f} > ${self.max_daily_usd:.2f})"

        return True, "OK"

    def record_trade(self, amount_sol: float, amount_usd: float):
        """Record a trade against limits."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self.last_reset != today:
            self.daily_spent_sol = 0.0
            self.daily_spent_usd = 0.0
            self.last_reset = today

        self.daily_spent_sol += amount_sol
        self.daily_spent_usd += amount_usd


# === AUDIT LOGGING ===

class AuditLogger:
    """
    Audit logger for tracking all trading actions.
    """

    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or str(Path(__file__).parent / "audit.log")
        self._setup_logger()

    def _setup_logger(self):
        """Setup dedicated audit logger."""
        self.logger = logging.getLogger("jarvis.audit")
        self.logger.setLevel(logging.INFO)

        # File handler
        handler = logging.FileHandler(self.log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        ))
        self.logger.addHandler(handler)

    def log_trade(self, action: str, token: str, amount: float,
                  price: float, user_id: str = "system", **kwargs):
        """Log a trade action."""
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info(
            f"TRADE | {action} | {token} | amount={amount} | price={price} | "
            f"user={user_id} | {extra}"
        )

    def log_alert(self, alert_type: str, token: str, chat_id: str, **kwargs):
        """Log an alert sent."""
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.info(
            f"ALERT | {alert_type} | {token} | chat={chat_id} | {extra}"
        )

    def log_error(self, error_type: str, message: str, **kwargs):
        """Log an error."""
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        self.logger.error(f"ERROR | {error_type} | {message} | {extra}")

    def log_limit_hit(self, limit_type: str, current: float, max_val: float):
        """Log when a limit is hit."""
        self.logger.warning(
            f"LIMIT | {limit_type} | current={current} | max={max_val}"
        )


# Singleton audit logger
_audit_logger: Optional[AuditLogger] = None

def get_audit_logger() -> AuditLogger:
    """Get singleton audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger


# Import Path for audit logger
from pathlib import Path
