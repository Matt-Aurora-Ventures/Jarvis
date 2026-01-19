"""Tests for circuit breaker pattern."""

import pytest
import time
from core.reliability.circuit_breaker import CircuitBreaker, CircuitBreakerOpen, circuit_breaker


def test_circuit_breaker_closed():
    """Test circuit breaker in closed state (normal operation)."""
    breaker = CircuitBreaker(name="test")
    
    def success_func():
        return "success"
    
    result = breaker.call(success_func)
    assert result == "success"
    assert breaker.state.value == "closed"


def test_circuit_breaker_opens_on_failures():
    """Test circuit breaker opens after threshold failures."""
    breaker = CircuitBreaker(failure_threshold=3, name="test")
    
    def failing_func():
        raise Exception("Service error")
    
    # Fail 3 times
    for _ in range(3):
        with pytest.raises(Exception):
            breaker.call(failing_func)
    
    assert breaker.state.value == "open"
    assert breaker.failure_count == 3


def test_circuit_breaker_rejects_calls_when_open():
    """Test circuit breaker rejects calls when open."""
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=1, name="test")
    
    # Trigger opening
    with pytest.raises(Exception):
        breaker.call(lambda: 1/0)
    
    assert breaker.state.value == "open"
    
    # Next call should be rejected immediately
    with pytest.raises(CircuitBreakerOpen):
        breaker.call(lambda: "success")


def test_circuit_breaker_recovers():
    """Test circuit breaker recovery from half-open to closed."""
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0, name="test")
    
    # Trigger opening
    with pytest.raises(Exception):
        breaker.call(lambda: 1/0)
    
    assert breaker.state.value == "open"
    time.sleep(0.1)  # Wait for recovery timeout
    
    # Successful call should reset
    result = breaker.call(lambda: "success")
    assert result == "success"
    assert breaker.state.value == "closed"


def test_circuit_breaker_decorator():
    """Test circuit breaker as decorator."""
    call_count = {"count": 0}
    
    @circuit_breaker(failure_threshold=2)
    def my_func():
        call_count["count"] += 1
        if call_count["count"] < 3:
            raise ValueError("Test error")
        return "success"
    
    # First two calls fail
    for _ in range(2):
        with pytest.raises(ValueError):
            my_func()
    
    # Circuit is now open
    with pytest.raises(CircuitBreakerOpen):
        my_func()


def test_circuit_breaker_status():
    """Test circuit breaker status reporting."""
    breaker = CircuitBreaker(name="test_breaker")
    status = breaker.get_status()
    
    assert "state" in status
    assert "failures" in status
    assert "successes" in status
    assert status["name"] == "test_breaker"


__all__ = []
