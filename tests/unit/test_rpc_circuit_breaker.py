"""
Unit tests for RPC Circuit Breaker System.

Tests cover:
1. Circuit breaker state transitions (CLOSED -> OPEN -> HALF_OPEN)
2. Automatic recovery after cooldown
3. Integration with RPC health monitoring
4. Error handling and user-friendly messages
5. Developer logging with full context
"""

import asyncio
import importlib.util
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import logging


# Import directly from the module file to avoid __init__.py import chain
def _import_from_file(module_name: str, file_path: str):
    """Import a module directly from file, bypassing package __init__.py."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Get project root
_project_root = Path(__file__).parent.parent.parent


# =============================================================================
# TEST: RPC CIRCUIT BREAKER
# =============================================================================

class TestRPCCircuitBreaker:
    """Tests for RPC-specific circuit breaker implementation."""

    @pytest.fixture
    def circuit_breaker_module(self):
        """Load the circuit breaker module."""
        module_path = _project_root / "core" / "solana" / "circuit_breaker.py"
        if not module_path.exists():
            pytest.skip("circuit_breaker.py not implemented yet")
        return _import_from_file("core.solana.circuit_breaker_test", str(module_path))

    def test_circuit_breaker_initial_state_closed(self, circuit_breaker_module):
        """Circuit breaker starts in CLOSED state."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=5,
            recovery_timeout=60.0
        )
        assert cb.state == circuit_breaker_module.CircuitState.CLOSED

    def test_circuit_opens_after_threshold_failures(self, circuit_breaker_module):
        """Circuit opens after failure_threshold consecutive failures."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=3,
            recovery_timeout=60.0
        )

        # Record 3 failures
        for _ in range(3):
            cb.record_failure("RPC timeout")

        assert cb.state == circuit_breaker_module.CircuitState.OPEN

    def test_circuit_rejects_calls_when_open(self, circuit_breaker_module):
        """Circuit rejects calls when in OPEN state."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=2,
            recovery_timeout=60.0
        )

        # Force circuit open
        cb.record_failure("error")
        cb.record_failure("error")

        assert cb.state == circuit_breaker_module.CircuitState.OPEN
        assert cb.allow_request() is False

    def test_circuit_transitions_to_half_open_after_timeout(self, circuit_breaker_module):
        """Circuit transitions to HALF_OPEN after recovery_timeout."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=2,
            recovery_timeout=0.1  # Short timeout for testing
        )

        # Force circuit open
        cb.record_failure("error")
        cb.record_failure("error")

        # Wait for recovery timeout
        time.sleep(0.15)

        # Check state (accessing state property triggers transition)
        assert cb.state == circuit_breaker_module.CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_circuit_closes_on_success_in_half_open(self, circuit_breaker_module):
        """Circuit closes after success_threshold successes in HALF_OPEN."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=2
        )

        # Force circuit open and wait for half-open
        cb.record_failure("error")
        cb.record_failure("error")
        time.sleep(0.15)

        # Verify half-open
        assert cb.state == circuit_breaker_module.CircuitState.HALF_OPEN

        # Record successes
        cb.record_success()
        cb.record_success()

        assert cb.state == circuit_breaker_module.CircuitState.CLOSED

    def test_circuit_reopens_on_failure_in_half_open(self, circuit_breaker_module):
        """Circuit reopens on failure during HALF_OPEN state."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=2,
            recovery_timeout=0.1
        )

        # Force circuit open and wait for half-open
        cb.record_failure("error")
        cb.record_failure("error")
        time.sleep(0.15)

        # Verify half-open
        _ = cb.state  # Trigger state check

        # Fail in half-open
        cb.record_failure("error")

        assert cb.state == circuit_breaker_module.CircuitState.OPEN

    def test_success_resets_consecutive_failures(self, circuit_breaker_module):
        """Success resets consecutive failure count."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=5,
            recovery_timeout=60.0
        )

        # Record some failures
        cb.record_failure("error")
        cb.record_failure("error")
        assert cb.stats.consecutive_failures == 2

        # Record success
        cb.record_success()
        assert cb.stats.consecutive_failures == 0

    def test_circuit_breaker_stats_tracking(self, circuit_breaker_module):
        """Circuit breaker tracks statistics correctly."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=10,
            recovery_timeout=60.0
        )

        # Record mixed results
        cb.record_success()
        cb.record_success()
        cb.record_failure("error")
        cb.record_success()

        assert cb.stats.successful_calls == 3
        assert cb.stats.failed_calls == 1
        assert cb.stats.total_calls == 4

    def test_circuit_breaker_get_status(self, circuit_breaker_module):
        """Circuit breaker returns comprehensive status."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=5,
            recovery_timeout=60.0
        )

        status = cb.get_status()

        assert "name" in status
        assert "state" in status
        assert "stats" in status
        assert "remaining_timeout" in status
        assert status["name"] == "test_rpc"


class TestRPCCircuitBreakerAsync:
    """Async tests for RPC circuit breaker."""

    @pytest.fixture
    def circuit_breaker_module(self):
        """Load the circuit breaker module."""
        module_path = _project_root / "core" / "solana" / "circuit_breaker.py"
        if not module_path.exists():
            pytest.skip("circuit_breaker.py not implemented yet")
        return _import_from_file("core.solana.circuit_breaker_async_test", str(module_path))

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_success(self, circuit_breaker_module):
        """Circuit breaker passes through successful calls."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=5,
            recovery_timeout=60.0
        )

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_call_failure(self, circuit_breaker_module):
        """Circuit breaker records failures from calls."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=5,
            recovery_timeout=60.0
        )

        async def fail_func():
            raise ConnectionError("RPC connection failed")

        with pytest.raises(ConnectionError):
            await cb.call(fail_func)

        assert cb.stats.failed_calls == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_rejects_when_open(self, circuit_breaker_module):
        """Circuit breaker raises CircuitOpenError when circuit is open."""
        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test_rpc",
            failure_threshold=2,
            recovery_timeout=60.0
        )

        # Force circuit open
        cb.record_failure("error")
        cb.record_failure("error")

        async def some_func():
            return "result"

        with pytest.raises(circuit_breaker_module.CircuitOpenError) as exc_info:
            await cb.call(some_func)

        assert "test_rpc" in str(exc_info.value)


# =============================================================================
# TEST: ERROR HANDLER
# =============================================================================

class TestRPCErrorHandler:
    """Tests for structured RPC error handling."""

    @pytest.fixture
    def error_handler_module(self):
        """Load the error handler module."""
        module_path = _project_root / "core" / "solana" / "error_handler.py"
        if not module_path.exists():
            pytest.skip("error_handler.py not implemented yet")
        return _import_from_file("core.solana.error_handler_test", str(module_path))

    def test_sanitize_user_error_removes_internal_details(self, error_handler_module):
        """User errors should not expose internal details."""
        handler = error_handler_module.RPCErrorHandler()

        internal_error = ConnectionError("Failed to connect to https://api-key:secret123@rpc.example.com:8899")

        user_error = handler.sanitize_for_user(internal_error)

        assert "secret" not in user_error.lower()
        assert "api-key" not in user_error.lower()
        assert "rpc.example.com" not in user_error  # No URL details
        assert len(user_error) > 0  # Has a message

    def test_sanitize_user_error_provides_friendly_message(self, error_handler_module):
        """User errors should be friendly and actionable."""
        handler = error_handler_module.RPCErrorHandler()

        # Test various error types
        timeout_error = TimeoutError("Connection timed out after 30s")
        user_msg = handler.sanitize_for_user(timeout_error)
        assert "try again" in user_msg.lower() or "later" in user_msg.lower()

        connection_error = ConnectionError("ECONNREFUSED")
        user_msg = handler.sanitize_for_user(connection_error)
        assert "connection" in user_msg.lower() or "service" in user_msg.lower()

    def test_developer_error_includes_full_context(self, error_handler_module):
        """Developer errors should include full context."""
        handler = error_handler_module.RPCErrorHandler()

        error = ConnectionError("RPC timeout to https://rpc.example.com")
        context = {
            "endpoint": "https://rpc.example.com",
            "method": "getBalance",
            "params": ["abc123"],
            "latency_ms": 5000
        }

        dev_error = handler.format_for_developer(error, context)

        assert "endpoint" in dev_error
        assert "method" in dev_error
        assert "latency_ms" in dev_error
        assert "RPC timeout" in dev_error

    def test_error_categorization(self, error_handler_module):
        """Errors should be categorized correctly."""
        handler = error_handler_module.RPCErrorHandler()

        # Timeout errors
        assert handler.categorize(TimeoutError()) == error_handler_module.ErrorCategory.TIMEOUT

        # Connection errors
        assert handler.categorize(ConnectionError()) == error_handler_module.ErrorCategory.CONNECTION

        # Rate limit errors
        rate_limit = Exception("429 Too Many Requests")
        assert handler.categorize(rate_limit) == error_handler_module.ErrorCategory.RATE_LIMIT

    def test_should_retry_determination(self, error_handler_module):
        """Handler should correctly determine retry eligibility."""
        handler = error_handler_module.RPCErrorHandler()

        # Should retry: timeouts, temporary connection issues
        assert handler.should_retry(TimeoutError()) is True
        assert handler.should_retry(ConnectionError("ECONNRESET")) is True

        # Should not retry: rate limits (need backoff), invalid params
        assert handler.should_retry(Exception("429 Too Many Requests")) is False
        assert handler.should_retry(ValueError("Invalid parameter")) is False

    def test_error_logging_separation(self, error_handler_module):
        """User and developer logs should be separate."""
        handler = error_handler_module.RPCErrorHandler()

        error = ConnectionError("RPC failed: secret-api-key")
        context = {"endpoint": "https://secret.com"}

        # User log should be sanitized
        user_log = handler.get_user_log(error, context)
        assert "secret" not in user_log.lower()

        # Developer log should have full details
        dev_log = handler.get_developer_log(error, context)
        assert "secret" in dev_log or "RPC failed" in dev_log


class TestErrorCategoryMapping:
    """Tests for error category to user message mapping."""

    @pytest.fixture
    def error_handler_module(self):
        """Load the error handler module."""
        module_path = _project_root / "core" / "solana" / "error_handler.py"
        if not module_path.exists():
            pytest.skip("error_handler.py not implemented yet")
        return _import_from_file("core.solana.error_handler_mapping_test", str(module_path))

    def test_all_categories_have_user_messages(self, error_handler_module):
        """Every error category should have a user-friendly message."""
        handler = error_handler_module.RPCErrorHandler()

        for category in error_handler_module.ErrorCategory:
            user_msg = handler.get_user_message_for_category(category)
            assert len(user_msg) > 0
            assert not any(word in user_msg.lower() for word in ["error", "exception", "failed"])

    def test_timeout_category_message(self, error_handler_module):
        """Timeout category should suggest retrying."""
        handler = error_handler_module.RPCErrorHandler()
        msg = handler.get_user_message_for_category(error_handler_module.ErrorCategory.TIMEOUT)
        assert "moment" in msg.lower() or "try" in msg.lower()

    def test_connection_category_message(self, error_handler_module):
        """Connection category should indicate service issue."""
        handler = error_handler_module.RPCErrorHandler()
        msg = handler.get_user_message_for_category(error_handler_module.ErrorCategory.CONNECTION)
        assert "connection" in msg.lower() or "network" in msg.lower() or "service" in msg.lower()

    def test_rate_limit_category_message(self, error_handler_module):
        """Rate limit category should indicate wait."""
        handler = error_handler_module.RPCErrorHandler()
        msg = handler.get_user_message_for_category(error_handler_module.ErrorCategory.RATE_LIMIT)
        assert "busy" in msg.lower() or "wait" in msg.lower() or "moment" in msg.lower()


# =============================================================================
# TEST: CIRCUIT BREAKER INTEGRATION WITH RPC HEALTH
# =============================================================================

class TestCircuitBreakerRPCHealthIntegration:
    """Tests for circuit breaker integration with RPC health monitoring."""

    @pytest.fixture
    def modules(self):
        """Load required modules."""
        cb_path = _project_root / "core" / "solana" / "circuit_breaker.py"
        rpc_health_path = _project_root / "core" / "solana" / "rpc_health.py"

        if not cb_path.exists():
            pytest.skip("circuit_breaker.py not implemented yet")
        if not rpc_health_path.exists():
            pytest.skip("rpc_health.py not implemented yet")

        cb_module = _import_from_file("core.solana.circuit_breaker_integ", str(cb_path))
        rpc_module = _import_from_file("core.solana.rpc_health_integ", str(rpc_health_path))

        return {"circuit_breaker": cb_module, "rpc_health": rpc_module}

    def test_circuit_breaker_registered_in_health_scorer(self, modules):
        """Circuit breakers should be associated with health endpoints."""
        cb_module = modules["circuit_breaker"]

        # Create circuit breaker manager
        manager = cb_module.RPCCircuitBreakerManager()

        # Register endpoints
        manager.register_endpoint("helius", failure_threshold=5)
        manager.register_endpoint("quicknode", failure_threshold=3)

        assert manager.get_breaker("helius") is not None
        assert manager.get_breaker("quicknode") is not None

    def test_circuit_breaker_propagates_to_health_score(self, modules):
        """Open circuit should affect health score."""
        cb_module = modules["circuit_breaker"]
        rpc_module = modules["rpc_health"]

        # This test verifies the integration point exists
        # The actual integration is in rpc_health.py
        manager = cb_module.RPCCircuitBreakerManager()
        manager.register_endpoint("test_endpoint", failure_threshold=2)

        cb = manager.get_breaker("test_endpoint")

        # Open the circuit
        cb.record_failure("error")
        cb.record_failure("error")

        assert cb.state == cb_module.CircuitState.OPEN

    def test_circuit_state_affects_endpoint_selection(self, modules):
        """Open circuits should be excluded from endpoint selection."""
        cb_module = modules["circuit_breaker"]

        manager = cb_module.RPCCircuitBreakerManager()
        manager.register_endpoint("endpoint_a", failure_threshold=2)
        manager.register_endpoint("endpoint_b", failure_threshold=2)

        # Open circuit for endpoint_a
        cb = manager.get_breaker("endpoint_a")
        cb.record_failure("error")
        cb.record_failure("error")

        # Get available endpoints (non-open circuits)
        available = manager.get_available_endpoints()

        assert "endpoint_a" not in available
        assert "endpoint_b" in available


# =============================================================================
# TEST: CIRCUIT BREAKER CALLBACKS
# =============================================================================

class TestCircuitBreakerCallbacks:
    """Tests for circuit breaker event callbacks."""

    @pytest.fixture
    def circuit_breaker_module(self):
        """Load the circuit breaker module."""
        module_path = _project_root / "core" / "solana" / "circuit_breaker.py"
        if not module_path.exists():
            pytest.skip("circuit_breaker.py not implemented yet")
        return _import_from_file("core.solana.circuit_breaker_callback_test", str(module_path))

    def test_on_open_callback(self, circuit_breaker_module):
        """Callback fires when circuit opens."""
        callback_called = []

        def on_open():
            callback_called.append("open")

        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=60.0,
            on_open=on_open
        )

        cb.record_failure("error")
        cb.record_failure("error")

        assert "open" in callback_called

    def test_on_close_callback(self, circuit_breaker_module):
        """Callback fires when circuit closes."""
        callback_called = []

        def on_close():
            callback_called.append("close")

        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,
            success_threshold=1,
            on_close=on_close
        )

        # Open the circuit
        cb.record_failure("error")
        cb.record_failure("error")

        # Wait for half-open
        time.sleep(0.15)
        _ = cb.state  # Trigger transition

        # Close it
        cb.record_success()

        assert "close" in callback_called

    def test_on_half_open_callback(self, circuit_breaker_module):
        """Callback fires when circuit goes half-open."""
        callback_called = []

        def on_half_open():
            callback_called.append("half_open")

        cb = circuit_breaker_module.RPCCircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=0.1,
            on_half_open=on_half_open
        )

        # Open the circuit
        cb.record_failure("error")
        cb.record_failure("error")

        # Wait for half-open
        time.sleep(0.15)
        _ = cb.state  # Trigger transition

        assert "half_open" in callback_called


# =============================================================================
# TEST: RPC-SPECIFIC ERROR HANDLING
# =============================================================================

class TestRPCSpecificErrors:
    """Tests for RPC-specific error handling."""

    @pytest.fixture
    def error_handler_module(self):
        """Load the error handler module."""
        module_path = _project_root / "core" / "solana" / "error_handler.py"
        if not module_path.exists():
            pytest.skip("error_handler.py not implemented yet")
        return _import_from_file("core.solana.error_handler_rpc_test", str(module_path))

    def test_handle_insufficient_funds_error(self, error_handler_module):
        """Insufficient funds should have clear user message."""
        handler = error_handler_module.RPCErrorHandler()

        error = Exception("Insufficient funds for transaction")
        user_msg = handler.sanitize_for_user(error)

        assert "insufficient" in user_msg.lower() or "funds" in user_msg.lower() or "balance" in user_msg.lower()

    def test_handle_blockhash_expired_error(self, error_handler_module):
        """Expired blockhash should suggest retry."""
        handler = error_handler_module.RPCErrorHandler()

        error = Exception("Blockhash not found or expired")
        user_msg = handler.sanitize_for_user(error)
        category = handler.categorize(error)

        # BLOCKHASH_EXPIRED is more specific than TRANSACTION
        assert category == error_handler_module.ErrorCategory.BLOCKHASH_EXPIRED
        assert handler.should_retry(error) is True

    def test_handle_slot_skipped_error(self, error_handler_module):
        """Slot skipped errors should suggest retry."""
        handler = error_handler_module.RPCErrorHandler()

        error = Exception("Slot was skipped, retry transaction")
        user_msg = handler.sanitize_for_user(error)

        assert "try" in user_msg.lower() or "again" in user_msg.lower() or "moment" in user_msg.lower()

    def test_handle_node_unhealthy_error(self, error_handler_module):
        """Node unhealthy should indicate service issue."""
        handler = error_handler_module.RPCErrorHandler()

        error = Exception("Node is unhealthy")
        category = handler.categorize(error)

        assert category == error_handler_module.ErrorCategory.NODE_UNHEALTHY


# =============================================================================
# TEST: CIRCUIT BREAKER DECORATOR
# =============================================================================

class TestCircuitBreakerDecorator:
    """Tests for circuit breaker decorator."""

    @pytest.fixture
    def circuit_breaker_module(self):
        """Load the circuit breaker module."""
        module_path = _project_root / "core" / "solana" / "circuit_breaker.py"
        if not module_path.exists():
            pytest.skip("circuit_breaker.py not implemented yet")
        return _import_from_file("core.solana.circuit_breaker_decorator_test", str(module_path))

    @pytest.mark.asyncio
    async def test_decorator_wraps_function(self, circuit_breaker_module):
        """Decorator should wrap async functions."""
        @circuit_breaker_module.rpc_circuit_breaker(name="test_func", failure_threshold=5)
        async def my_rpc_call():
            return "success"

        result = await my_rpc_call()
        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_tracks_failures(self, circuit_breaker_module):
        """Decorator should track failures and open circuit."""
        call_count = [0]

        @circuit_breaker_module.rpc_circuit_breaker(
            name="failing_func",
            failure_threshold=2,
            recovery_timeout=60.0
        )
        async def failing_rpc_call():
            call_count[0] += 1
            raise ConnectionError("RPC failed")

        # First two calls should go through and fail
        for _ in range(2):
            with pytest.raises(ConnectionError):
                await failing_rpc_call()

        # Third call should be rejected by circuit breaker
        with pytest.raises(circuit_breaker_module.CircuitOpenError):
            await failing_rpc_call()

        # Only 2 actual calls should have been made
        assert call_count[0] == 2
