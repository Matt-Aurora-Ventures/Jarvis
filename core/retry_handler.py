"""
Retry Handler - Robust retry logic with exponential backoff.
Handles transient failures with configurable retry strategies.
"""
import asyncio
import functools
import random
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any, Type, Tuple, Union
import json


class RetryStrategy(Enum):
    """Retry strategies."""
    FIXED = "fixed"                # Fixed delay between retries
    EXPONENTIAL = "exponential"    # Exponential backoff
    FIBONACCI = "fibonacci"        # Fibonacci backoff
    LINEAR = "linear"              # Linear increase
    RANDOM = "random"              # Random delay within range


class RetryOutcome(Enum):
    """Outcome of a retry attempt."""
    SUCCESS = "success"
    RETRY = "retry"
    FAILURE = "failure"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    base_delay: float = 1.0        # Base delay in seconds
    max_delay: float = 60.0        # Maximum delay
    jitter: float = 0.1            # Random jitter (0-1)
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()
    on_retry: Optional[Callable] = None
    on_failure: Optional[Callable] = None


@dataclass
class RetryAttempt:
    """A single retry attempt."""
    attempt_number: int
    started_at: datetime
    ended_at: Optional[datetime]
    outcome: RetryOutcome
    error: Optional[str]
    delay_before: float


@dataclass
class RetryContext:
    """Context for a retry operation."""
    operation_id: str
    operation_name: str
    config: RetryConfig
    attempts: List[RetryAttempt]
    started_at: datetime
    completed_at: Optional[datetime]
    final_outcome: Optional[RetryOutcome]
    final_result: Any
    total_delay: float


@dataclass
class CircuitBreakerState:
    """State of a circuit breaker."""
    name: str
    state: str                     # "closed", "open", "half_open"
    failure_count: int
    success_count: int
    last_failure: Optional[datetime]
    opened_at: Optional[datetime]
    cooldown_until: Optional[datetime]


class CircuitBreaker:
    """Circuit breaker for fault tolerance."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        cooldown_seconds: float = 30.0
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.cooldown_seconds = cooldown_seconds

        self.state = "closed"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure: Optional[datetime] = None
        self.opened_at: Optional[datetime] = None
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        with self._lock:
            if self.state == "closed":
                return True

            if self.state == "open":
                # Check if cooldown has passed
                if self.opened_at:
                    cooldown_end = self.opened_at + timedelta(seconds=self.cooldown_seconds)
                    if datetime.now() > cooldown_end:
                        self.state = "half_open"
                        return True
                return False

            # half_open - allow one attempt
            return True

    def record_success(self):
        """Record a successful execution."""
        with self._lock:
            if self.state == "half_open":
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = "closed"
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == "closed":
                self.failure_count = 0

    def record_failure(self):
        """Record a failed execution."""
        with self._lock:
            self.failure_count += 1
            self.last_failure = datetime.now()

            if self.state == "half_open":
                self._open()
            elif self.failure_count >= self.failure_threshold:
                self._open()

    def _open(self):
        """Open the circuit breaker."""
        self.state = "open"
        self.opened_at = datetime.now()
        self.success_count = 0

    def get_state(self) -> CircuitBreakerState:
        """Get current state."""
        return CircuitBreakerState(
            name=self.name,
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            last_failure=self.last_failure,
            opened_at=self.opened_at,
            cooldown_until=self.opened_at + timedelta(seconds=self.cooldown_seconds)
                          if self.opened_at else None
        )


class RetryHandler:
    """
    Robust retry handler with multiple strategies and circuit breakers.
    """

    # Fibonacci sequence for backoff
    FIBONACCI = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            Path(__file__).parent.parent / "data" / "retry_handler.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.default_config = RetryConfig()

        # Statistics
        self.stats = {
            "total_operations": 0,
            "total_retries": 0,
            "total_successes": 0,
            "total_failures": 0,
            "circuit_opens": 0
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
                CREATE TABLE IF NOT EXISTS retry_contexts (
                    operation_id TEXT PRIMARY KEY,
                    operation_name TEXT NOT NULL,
                    config TEXT NOT NULL,
                    attempts TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    final_outcome TEXT,
                    total_delay REAL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS circuit_breaker_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_contexts_name ON retry_contexts(operation_name);
                CREATE INDEX IF NOT EXISTS idx_cb_events_name ON circuit_breaker_events(name);
            """)

    def get_circuit_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        cooldown_seconds: float = 30.0
    ) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                success_threshold=success_threshold,
                cooldown_seconds=cooldown_seconds
            )
        return self.circuit_breakers[name]

    def calculate_delay(
        self,
        attempt: int,
        config: RetryConfig
    ) -> float:
        """Calculate delay before next retry."""
        if config.strategy == RetryStrategy.FIXED:
            delay = config.base_delay

        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (2 ** (attempt - 1))

        elif config.strategy == RetryStrategy.FIBONACCI:
            idx = min(attempt - 1, len(self.FIBONACCI) - 1)
            delay = config.base_delay * self.FIBONACCI[idx]

        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * attempt

        elif config.strategy == RetryStrategy.RANDOM:
            delay = random.uniform(config.base_delay, config.max_delay)

        else:
            delay = config.base_delay

        # Apply jitter
        if config.jitter > 0:
            jitter_range = delay * config.jitter
            delay += random.uniform(-jitter_range, jitter_range)

        # Cap at max delay
        return min(delay, config.max_delay)

    async def execute_async(
        self,
        func: Callable,
        *args,
        config: Optional[RetryConfig] = None,
        operation_name: Optional[str] = None,
        circuit_breaker_name: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Execute an async function with retry logic."""
        import uuid

        config = config or self.default_config
        operation_name = operation_name or func.__name__
        operation_id = str(uuid.uuid4())[:12]

        context = RetryContext(
            operation_id=operation_id,
            operation_name=operation_name,
            config=config,
            attempts=[],
            started_at=datetime.now(),
            completed_at=None,
            final_outcome=None,
            final_result=None,
            total_delay=0
        )

        # Check circuit breaker
        cb = None
        if circuit_breaker_name:
            cb = self.get_circuit_breaker(circuit_breaker_name)
            if not cb.can_execute():
                context.final_outcome = RetryOutcome.CIRCUIT_OPEN
                context.completed_at = datetime.now()
                self._save_context(context)
                raise CircuitBreakerOpenError(f"Circuit breaker {circuit_breaker_name} is open")

        attempt = 0
        last_exception = None

        while attempt < config.max_attempts:
            attempt += 1
            delay = self.calculate_delay(attempt, config) if attempt > 1 else 0

            if delay > 0:
                context.total_delay += delay
                await asyncio.sleep(delay)

            attempt_record = RetryAttempt(
                attempt_number=attempt,
                started_at=datetime.now(),
                ended_at=None,
                outcome=RetryOutcome.RETRY,
                error=None,
                delay_before=delay
            )

            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                attempt_record.ended_at = datetime.now()
                attempt_record.outcome = RetryOutcome.SUCCESS
                context.attempts.append(attempt_record)

                context.final_outcome = RetryOutcome.SUCCESS
                context.final_result = result
                context.completed_at = datetime.now()

                if cb:
                    cb.record_success()

                self.stats["total_successes"] += 1
                self._save_context(context)
                return result

            except config.non_retryable_exceptions as e:
                # Don't retry these
                attempt_record.ended_at = datetime.now()
                attempt_record.outcome = RetryOutcome.FAILURE
                attempt_record.error = str(e)
                context.attempts.append(attempt_record)

                context.final_outcome = RetryOutcome.FAILURE
                context.completed_at = datetime.now()

                if cb:
                    cb.record_failure()

                self.stats["total_failures"] += 1
                self._save_context(context)
                raise

            except config.retryable_exceptions as e:
                last_exception = e
                attempt_record.ended_at = datetime.now()
                attempt_record.outcome = RetryOutcome.RETRY
                attempt_record.error = str(e)
                context.attempts.append(attempt_record)

                self.stats["total_retries"] += 1

                if config.on_retry:
                    try:
                        config.on_retry(attempt, config.max_attempts, e)
                    except Exception:
                        pass

                if cb:
                    cb.record_failure()

            except Exception as e:
                # Unexpected exception
                last_exception = e
                attempt_record.ended_at = datetime.now()
                attempt_record.outcome = RetryOutcome.FAILURE
                attempt_record.error = str(e)
                context.attempts.append(attempt_record)

                if cb:
                    cb.record_failure()

                break

        # All retries exhausted
        context.final_outcome = RetryOutcome.FAILURE
        context.completed_at = datetime.now()

        self.stats["total_failures"] += 1

        if config.on_failure:
            try:
                config.on_failure(last_exception)
            except Exception:
                pass

        self._save_context(context)

        if last_exception:
            raise last_exception
        raise RetryExhaustedError(f"All {config.max_attempts} retries exhausted")

    def execute(
        self,
        func: Callable,
        *args,
        config: Optional[RetryConfig] = None,
        operation_name: Optional[str] = None,
        circuit_breaker_name: Optional[str] = None,
        **kwargs
    ) -> Any:
        """Execute a sync function with retry logic."""
        import uuid

        config = config or self.default_config
        operation_name = operation_name or func.__name__
        operation_id = str(uuid.uuid4())[:12]

        context = RetryContext(
            operation_id=operation_id,
            operation_name=operation_name,
            config=config,
            attempts=[],
            started_at=datetime.now(),
            completed_at=None,
            final_outcome=None,
            final_result=None,
            total_delay=0
        )

        # Check circuit breaker
        cb = None
        if circuit_breaker_name:
            cb = self.get_circuit_breaker(circuit_breaker_name)
            if not cb.can_execute():
                context.final_outcome = RetryOutcome.CIRCUIT_OPEN
                context.completed_at = datetime.now()
                self._save_context(context)
                raise CircuitBreakerOpenError(f"Circuit breaker {circuit_breaker_name} is open")

        attempt = 0
        last_exception = None

        while attempt < config.max_attempts:
            attempt += 1
            delay = self.calculate_delay(attempt, config) if attempt > 1 else 0

            if delay > 0:
                context.total_delay += delay
                time.sleep(delay)

            attempt_record = RetryAttempt(
                attempt_number=attempt,
                started_at=datetime.now(),
                ended_at=None,
                outcome=RetryOutcome.RETRY,
                error=None,
                delay_before=delay
            )

            try:
                result = func(*args, **kwargs)

                attempt_record.ended_at = datetime.now()
                attempt_record.outcome = RetryOutcome.SUCCESS
                context.attempts.append(attempt_record)

                context.final_outcome = RetryOutcome.SUCCESS
                context.final_result = result
                context.completed_at = datetime.now()

                if cb:
                    cb.record_success()

                self.stats["total_successes"] += 1
                self._save_context(context)
                return result

            except config.non_retryable_exceptions as e:
                attempt_record.ended_at = datetime.now()
                attempt_record.outcome = RetryOutcome.FAILURE
                attempt_record.error = str(e)
                context.attempts.append(attempt_record)

                context.final_outcome = RetryOutcome.FAILURE
                context.completed_at = datetime.now()

                if cb:
                    cb.record_failure()

                self.stats["total_failures"] += 1
                self._save_context(context)
                raise

            except config.retryable_exceptions as e:
                last_exception = e
                attempt_record.ended_at = datetime.now()
                attempt_record.outcome = RetryOutcome.RETRY
                attempt_record.error = str(e)
                context.attempts.append(attempt_record)

                self.stats["total_retries"] += 1

                if cb:
                    cb.record_failure()

        # All retries exhausted
        context.final_outcome = RetryOutcome.FAILURE
        context.completed_at = datetime.now()

        self.stats["total_failures"] += 1
        self._save_context(context)

        if last_exception:
            raise last_exception
        raise RetryExhaustedError(f"All {config.max_attempts} retries exhausted")

    def _save_context(self, context: RetryContext):
        """Save retry context to database."""
        with self._get_db() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO retry_contexts
                (operation_id, operation_name, config, attempts,
                 started_at, completed_at, final_outcome, total_delay)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                context.operation_id, context.operation_name,
                json.dumps({
                    "max_attempts": context.config.max_attempts,
                    "strategy": context.config.strategy.value,
                    "base_delay": context.config.base_delay,
                    "max_delay": context.config.max_delay
                }),
                json.dumps([{
                    "attempt_number": a.attempt_number,
                    "started_at": a.started_at.isoformat(),
                    "ended_at": a.ended_at.isoformat() if a.ended_at else None,
                    "outcome": a.outcome.value,
                    "error": a.error,
                    "delay_before": a.delay_before
                } for a in context.attempts]),
                context.started_at.isoformat(),
                context.completed_at.isoformat() if context.completed_at else None,
                context.final_outcome.value if context.final_outcome else None,
                context.total_delay
            ))

    def retry(
        self,
        config: Optional[RetryConfig] = None,
        circuit_breaker_name: Optional[str] = None
    ):
        """Decorator for automatic retries."""
        def decorator(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await self.execute_async(
                    func, *args,
                    config=config,
                    circuit_breaker_name=circuit_breaker_name,
                    **kwargs
                )

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return self.execute(
                    func, *args,
                    config=config,
                    circuit_breaker_name=circuit_breaker_name,
                    **kwargs
                )

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def get_statistics(self) -> Dict:
        """Get retry statistics."""
        return {
            **self.stats,
            "circuit_breakers": {
                name: cb.get_state().__dict__
                for name, cb in self.circuit_breakers.items()
            }
        }


class RetryExhaustedError(Exception):
    """All retries have been exhausted."""
    pass


class CircuitBreakerOpenError(Exception):
    """Circuit breaker is open."""
    pass


# Singleton instance
_retry_handler: Optional[RetryHandler] = None


def get_retry_handler() -> RetryHandler:
    """Get or create the retry handler singleton."""
    global _retry_handler
    if _retry_handler is None:
        _retry_handler = RetryHandler()
    return _retry_handler
