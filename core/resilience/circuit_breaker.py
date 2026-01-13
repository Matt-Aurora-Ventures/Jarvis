"""Circuit breaker pattern implementation."""
import time
import asyncio
from enum import Enum
from typing import Callable, TypeVar, Optional, Any
from functools import wraps
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitStats:
    failures: int = 0
    successes: int = 0
    last_failure_time: float = 0
    consecutive_successes: int = 0
    total_calls: int = 0


class CircuitBreaker:
    """
    Circuit breaker for preventing cascade failures.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failures exceeded threshold, requests are rejected
    - HALF_OPEN: Testing if service recovered, limited requests allowed
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 3,
        timeout: float = 30.0,
        half_open_max_calls: int = 3
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function through the circuit breaker."""
        async with self._lock:
            if not self._can_execute():
                raise CircuitOpenError(f"Circuit {self.name} is open")
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            await self._on_success()
            return result
        
        except Exception as e:
            await self._on_failure()
            raise
    
    def _can_execute(self) -> bool:
        """Check if a call can be executed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.stats.last_failure_time >= self.timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        
        return False
    
    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            self.stats.successes += 1
            self.stats.total_calls += 1
            self.stats.consecutive_successes += 1
            
            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
    
    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.stats.failures += 1
            self.stats.total_calls += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = time.time()
            
            if self.state == CircuitState.CLOSED:
                if self.stats.failures >= self.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            
            elif self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        old_state = self.state
        self.state = new_state
        
        if new_state == CircuitState.CLOSED:
            self.stats.failures = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self.stats.consecutive_successes = 0
        
        logger.info(f"Circuit {self.name}: {old_state.value} -> {new_state.value}")
    
    def reset(self):
        """Reset the circuit breaker."""
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._half_open_calls = 0
    
    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN
    
    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.stats.failures,
            "successes": self.stats.successes,
            "total_calls": self.stats.total_calls,
            "failure_rate": self.stats.failures / max(self.stats.total_calls, 1)
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


_circuits: dict[str, CircuitBreaker] = {}


def get_circuit(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _circuits:
        _circuits[name] = CircuitBreaker(name, **kwargs)
    return _circuits[name]


def circuit_breaker(name: str, **kwargs):
    """Decorator to wrap a function with circuit breaker."""
    def decorator(func: Callable) -> Callable:
        circuit = get_circuit(name, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args, **inner_kwargs):
            return await circuit.call(func, *args, **inner_kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **inner_kwargs):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(circuit.call(func, *args, **inner_kwargs))
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
