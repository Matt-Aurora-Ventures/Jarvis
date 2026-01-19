"""Tests for chaos engineering."""

import pytest
from core.reliability.chaos_testing import ChaosMonkey, ChaoticFailure


def test_chaos_monkey_disabled():
    """Test chaos monkey with disabled chaos."""
    monkey = ChaosMonkey(failure_rate=0.9, enabled=False)
    
    def my_func():
        return "success"
    
    for _ in range(10):
        result = monkey.inject_failure(my_func)
        assert result == "success"


def test_chaos_monkey_enabled():
    """Test chaos monkey with enabled chaos."""
    monkey = ChaosMonkey(failure_rate=1.0, enabled=True)
    
    def my_func():
        return "success"
    
    with pytest.raises(ChaoticFailure):
        monkey.inject_failure(my_func)
    
    assert monkey.failures_injected == 1


def test_chaos_monkey_random_failures():
    """Test chaos monkey with random failure rate."""
    monkey = ChaosMonkey(failure_rate=0.5, enabled=True)
    
    def my_func():
        return "success"
    
    successes = 0
    failures = 0
    
    for _ in range(100):
        try:
            monkey.inject_failure(my_func)
            successes += 1
        except ChaoticFailure:
            failures += 1
    
    # Should have both successes and failures
    assert successes > 0
    assert failures > 0


def test_chaos_monkey_failure_tracking():
    """Test chaos monkey tracks failures."""
    monkey = ChaosMonkey(failure_rate=1.0, enabled=True)
    
    def failing_func():
        raise ValueError("test")
    
    for _ in range(5):
        with pytest.raises(ChaoticFailure):
            monkey.inject_failure(failing_func)
    
    assert monkey.failures_injected == 5


def test_chaos_monkey_disabling():
    """Test enabling/disabling chaos monkey."""
    monkey = ChaosMonkey(failure_rate=1.0, enabled=True)
    
    def my_func():
        return "success"
    
    # First call fails
    with pytest.raises(ChaoticFailure):
        monkey.inject_failure(my_func)
    
    # Disable chaos
    monkey.enabled = False
    
    # Next call succeeds
    result = monkey.inject_failure(my_func)
    assert result == "success"


def test_chaos_monkey_failure_counts():
    """Test failure counting accuracy."""
    monkey = ChaosMonkey(failure_rate=1.0, enabled=True)
    
    def my_func():
        pass
    
    for i in range(10):
        try:
            monkey.inject_failure(my_func)
        except ChaoticFailure:
            pass
    
    assert monkey.failures_injected == 10


__all__ = []
