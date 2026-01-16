"""Async API circuit breaker."""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Optional, TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """Raised when the circuit is open and requests are blocked."""

    def __init__(self, name: str, retry_after: float):
        super().__init__(f"Circuit '{name}' is open. Retry in {retry_after:.1f}s")
        self.name = name
        self.retry_after = retry_after


@dataclass
class CircuitConfig:
    failure_threshold: int = 5
    reset_timeout: float = 300.0


class APICircuitBreaker:
    """Simple async circuit breaker for API calls."""

    def __init__(self, name: str, failure_threshold: int = 5, reset_timeout: float = 300.0):
        self.name = name
        self.config = CircuitConfig(
            failure_threshold=failure_threshold,
            reset_timeout=reset_timeout,
        )
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def _before_call(self) -> None:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                retry_after = self._remaining_open_time()
                if retry_after > 0:
                    raise CircuitOpenError(self.name, retry_after)
                # Timeout elapsed, allow a probe
                self._state = CircuitState.HALF_OPEN

    async def _record_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._opened_at = None
            self._state = CircuitState.CLOSED

    async def _record_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            if self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.time()
            elif self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = time.time()

    def _remaining_open_time(self) -> float:
        if self._opened_at is None:
            return 0.0
        elapsed = time.time() - self._opened_at
        remaining = self.config.reset_timeout - elapsed
        return max(0.0, remaining)

    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """Execute an async function with circuit breaker protection."""
        await self._before_call()
        try:
            result = await func(*args, **kwargs)
        except Exception:
            await self._record_failure()
            raise
        await self._record_success()
        return result
