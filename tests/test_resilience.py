"""Tests for resilience patterns."""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


class TestRetryWithBackoff:
    """Tests for retry logic."""
    
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self):
        from core.resilience.retry import retry_with_backoff
        
        call_count = 0
        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await retry_with_backoff(success_func, max_attempts=3)
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retries_on_failure(self):
        from core.resilience.retry import retry_with_backoff
        
        call_count = 0
        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("temporary failure")
            return "success"
        
        result = await retry_with_backoff(fail_then_succeed, max_attempts=3, base_delay=0.01)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self):
        from core.resilience.retry import retry_with_backoff
        
        async def always_fail():
            raise Exception("permanent failure")
        
        with pytest.raises(Exception, match="permanent failure"):
            await retry_with_backoff(always_fail, max_attempts=2, base_delay=0.01)


class TestCircuitBreaker:
    """Tests for circuit breaker pattern."""
    
    @pytest.mark.asyncio
    async def test_closed_state_allows_calls(self):
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState
        
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        
        result = await cb.call(lambda: "success")
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_opens_after_failures(self):
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState, CircuitOpenError
        
        cb = CircuitBreaker("test", failure_threshold=2)
        
        async def failing():
            raise Exception("fail")
        
        # Trigger failures
        for _ in range(2):
            try:
                await cb.call(failing)
            except Exception:
                pass
        
        assert cb.state == CircuitState.OPEN
        
        # Next call should be rejected
        with pytest.raises(CircuitOpenError):
            await cb.call(lambda: "test")
    
    def test_reset_circuit(self):
        from core.resilience.circuit_breaker import CircuitBreaker, CircuitState
        
        cb = CircuitBreaker("test")
        cb.state = CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


class TestFallback:
    """Tests for fallback patterns."""
    
    @pytest.mark.asyncio
    async def test_fallback_on_failure(self):
        from core.resilience.fallback import FallbackChain
        
        async def primary():
            raise Exception("primary failed")
        
        async def backup():
            return "backup result"
        
        chain = FallbackChain(primary, backup)
        result = await chain.execute()
        assert result == "backup result"
    
    @pytest.mark.asyncio
    async def test_uses_primary_on_success(self):
        from core.resilience.fallback import FallbackChain
        
        async def primary():
            return "primary result"
        
        async def backup():
            return "backup result"
        
        chain = FallbackChain(primary, backup)
        result = await chain.execute()
        assert result == "primary result"


class TestGracefulDegradation:
    """Tests for graceful degradation."""
    
    def test_register_service(self):
        from core.resilience.degradation import GracefulDegradation
        
        gd = GracefulDegradation()
        gd.register_service("database")
        gd.register_service("cache")
        
        assert "database" in gd.services
        assert "cache" in gd.services
    
    def test_service_level_updates(self):
        from core.resilience.degradation import GracefulDegradation, ServiceLevel
        
        gd = GracefulDegradation()
        gd.register_service("database")
        gd.register_service("cache")
        
        # All healthy
        gd.report_success("database")
        gd.report_success("cache")
        assert gd.service_level == ServiceLevel.FULL
        
        # One unhealthy
        for _ in range(5):
            gd.report_failure("cache")
        assert gd.service_level in [ServiceLevel.DEGRADED, ServiceLevel.FULL]
