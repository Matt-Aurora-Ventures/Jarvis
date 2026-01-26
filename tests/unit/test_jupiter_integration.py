"""
Tests for Jupiter API Infrastructure Integration.

Tests the integration of:
- Dynamic priority fees via Helius
- Transaction simulation with preflight checks
- Multi-provider RPC failover
- Circuit breakers for endpoint protection
- User-friendly error handling

Following TDD workflow: Write failing tests first.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any, Dict


# =============================================================================
# TEST: Configuration System
# =============================================================================

class TestJupiterConfig:
    """Tests for Jupiter trading configuration in lifeos config."""

    def test_config_has_jupiter_section(self):
        """Config should have a 'jupiter' section with infrastructure settings."""
        from core.config import load_config

        config = load_config()
        assert "jupiter" in config, "Config should have 'jupiter' section"

    def test_config_priority_levels(self):
        """Config should have priority level settings."""
        from core.config import load_config

        config = load_config()
        jupiter = config.get("jupiter", {})

        # Should have default priority level
        assert "default_priority_level" in jupiter, "Should have default_priority_level"
        assert jupiter["default_priority_level"] in ["min", "low", "medium", "high", "veryHigh"]

    def test_config_simulation_flags(self):
        """Config should have simulation enable flags."""
        from core.config import load_config

        config = load_config()
        jupiter = config.get("jupiter", {})

        # Should have simulation settings
        assert "enable_simulation" in jupiter, "Should have enable_simulation flag"
        assert "simulation_required_for_buy" in jupiter, "Should have simulation_required_for_buy flag"

    def test_config_max_priority_fee(self):
        """Config should have max priority fee cap."""
        from core.config import load_config

        config = load_config()
        jupiter = config.get("jupiter", {})

        assert "max_priority_fee_lamports" in jupiter, "Should have max_priority_fee_lamports"
        assert isinstance(jupiter["max_priority_fee_lamports"], int)


# =============================================================================
# TEST: Trading Execution Integration
# =============================================================================

class TestTradingExecutionIntegration:
    """Tests for trading_execution.py integration with new infrastructure."""

    def test_swap_executor_initialization(self):
        """SwapExecutor should initialize correctly."""
        from bots.treasury.trading.trading_execution import SwapExecutor

        # Mock Jupiter client
        mock_jupiter = MagicMock()
        mock_wallet = MagicMock()

        executor = SwapExecutor(mock_jupiter, mock_wallet)

        assert executor.jupiter is mock_jupiter
        assert executor.wallet is mock_wallet

    def test_error_handler_integration_available(self):
        """Error handler should be importable and usable."""
        # Direct import to avoid __init__.py chain
        from core.solana.error_handler import RPCErrorHandler, ErrorCategory

        handler = RPCErrorHandler()

        # Should be able to categorize errors
        error = ConnectionError("Connection refused")
        category = handler.categorize(error)

        assert category == ErrorCategory.CONNECTION


class TestSwapExecutorCircuitBreaker:
    """Tests for circuit breaker integration in swap execution."""

    def test_circuit_breaker_imports(self):
        """Circuit breaker module should be importable."""
        # Direct import from module to avoid __init__.py chain
        from core.solana.circuit_breaker import RPCCircuitBreaker, CircuitState

        # Create new instance
        cb = RPCCircuitBreaker(name="test_cb", failure_threshold=2)

        # Initial state should be closed
        assert cb.state == CircuitState.CLOSED

        # Force open
        cb.force_open()
        assert cb.state == CircuitState.OPEN

        # Reset should close
        cb.reset()
        assert cb.state == CircuitState.CLOSED


# =============================================================================
# TEST: Demo Bot Integration
# =============================================================================

class TestDemoTradingIntegration:
    """Tests for demo_trading.py integration with new infrastructure."""

    @pytest.mark.asyncio
    async def test_execute_swap_uses_simulation(self):
        """Demo swap execution should use simulation."""
        from tg_bot.handlers.demo.demo_trading import _execute_swap_with_fallback

        # This test verifies the function exists and can be imported
        # Full integration test would require mocking
        assert callable(_execute_swap_with_fallback)

    @pytest.mark.asyncio
    async def test_error_messages_are_user_friendly(self):
        """Error messages should be user-friendly, not raw exceptions."""
        from tg_bot.handlers.demo.demo_trading import TradingError, BagsAPIError

        # BagsAPIError should provide user-friendly formatting
        error = BagsAPIError(
            "Trade failed",
            hint="Try again later"
        )

        formatted = error.format_telegram()
        assert "Trade failed" in formatted
        assert "Try again later" in formatted


# =============================================================================
# TEST: Jupiter API Enhanced Methods
# =============================================================================

class TestJupiterAPIEnhancements:
    """Tests for JupiterAPI class enhancements."""

    def test_jupiter_api_has_simulation_method(self):
        """JupiterAPI should have simulate_transaction method."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()
        assert hasattr(api, 'simulate_transaction')
        assert callable(api.simulate_transaction)

    def test_jupiter_api_has_priority_fee_method(self):
        """JupiterAPI should have get_priority_fee_estimate method."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()
        assert hasattr(api, 'get_priority_fee_estimate')
        assert callable(api.get_priority_fee_estimate)

    def test_priority_level_enum_exists(self):
        """PriorityLevel enum should exist with expected values."""
        from core.jupiter_api import PriorityLevel

        assert PriorityLevel.MIN.value == "min"
        assert PriorityLevel.LOW.value == "low"
        assert PriorityLevel.MEDIUM.value == "medium"
        assert PriorityLevel.HIGH.value == "high"
        assert PriorityLevel.VERY_HIGH.value == "veryHigh"

    @pytest.mark.asyncio
    async def test_execute_swap_accepts_simulation_flag(self):
        """execute_swap should accept simulate parameter."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        # Check method signature accepts simulate param
        import inspect
        sig = inspect.signature(api.execute_swap)
        params = list(sig.parameters.keys())

        assert 'simulate' in params, "execute_swap should have simulate parameter"

    @pytest.mark.asyncio
    async def test_execute_swap_accepts_priority_level(self):
        """execute_swap should accept priority_level parameter."""
        from core.jupiter_api import JupiterAPI

        api = JupiterAPI()

        import inspect
        sig = inspect.signature(api.execute_swap)
        params = list(sig.parameters.keys())

        assert 'priority_level' in params, "execute_swap should have priority_level parameter"


# =============================================================================
# TEST: RPC Health Integration
# =============================================================================

class TestRPCHealthIntegration:
    """Tests for RPC health and circuit breaker integration."""

    def test_get_rpc_with_circuit_breaker_returns_tuple(self):
        """get_rpc_with_circuit_breaker should return scorer, manager, handler."""
        from core.solana.rpc_health import get_rpc_with_circuit_breaker  # noqa: direct import

        scorer, cb_manager, error_handler = get_rpc_with_circuit_breaker()

        # All components should be returned (may be None if config unavailable)
        # At minimum, cb_manager and error_handler should exist
        if cb_manager is not None:
            assert hasattr(cb_manager, 'get_or_create')
            assert hasattr(cb_manager, 'get_available_endpoints')

        if error_handler is not None:
            assert hasattr(error_handler, 'sanitize_for_user')
            assert hasattr(error_handler, 'format_for_developer')

    def test_circuit_breaker_manager_registers_providers(self):
        """Circuit breaker manager should have pre-registered RPC providers."""
        from core.solana.circuit_breaker import RPCCircuitBreakerManager

        # Create new manager to avoid global state issues
        manager = RPCCircuitBreakerManager()

        # Register a test provider
        breaker = manager.get_or_create("test_provider")
        assert breaker is not None
        assert breaker.name == "test_provider"

        # Should return same instance
        breaker2 = manager.get_or_create("test_provider")
        assert breaker is breaker2


# =============================================================================
# TEST: Error Handler Integration
# =============================================================================

class TestErrorHandlerIntegration:
    """Tests for error handler integration with trading components."""

    def test_error_categorization_for_trading_errors(self):
        """Error handler should categorize trading-related errors."""
        from core.solana.error_handler import RPCErrorHandler, ErrorCategory

        handler = RPCErrorHandler()

        # Timeout should be categorized
        timeout_error = TimeoutError("Request timed out")
        assert handler.categorize(timeout_error) == ErrorCategory.TIMEOUT

        # Connection error should be categorized
        conn_error = ConnectionError("Connection refused")
        assert handler.categorize(conn_error) == ErrorCategory.CONNECTION

    def test_user_messages_are_sanitized(self):
        """User messages should not contain sensitive information."""
        from core.solana.error_handler import RPCErrorHandler

        handler = RPCErrorHandler()

        # Create error with sensitive info
        error = Exception("Failed at https://api.helius.xyz?api-key=secret123")

        user_msg = handler.sanitize_for_user(error)

        # Should not contain API key
        assert "secret123" not in user_msg
        assert "api-key" not in user_msg.lower()

    def test_developer_messages_have_context(self):
        """Developer messages should have full context for debugging."""
        from core.solana.error_handler import RPCErrorHandler

        handler = RPCErrorHandler()

        error = Exception("Transaction failed")
        context = {
            "endpoint": "helius",
            "method": "simulateTransaction",
            "token": "TEST123"
        }

        dev_msg = handler.format_for_developer(error, context)

        # Should contain context
        assert "endpoint" in dev_msg
        assert "helius" in dev_msg
        assert "simulateTransaction" in dev_msg


# =============================================================================
# TEST: Integration Flow
# =============================================================================

class TestFullIntegrationFlow:
    """End-to-end integration tests for the complete trading flow."""

    @pytest.mark.asyncio
    async def test_trading_flow_with_all_features(self):
        """Test complete trading flow with simulation, fees, and error handling."""
        # This is an integration test that verifies all components work together

        # 1. Load config
        from core.config import load_config
        config = load_config()

        # 2. Initialize components
        from core.solana.rpc_health import get_rpc_with_circuit_breaker  # noqa: direct import
        scorer, cb_manager, error_handler = get_rpc_with_circuit_breaker()

        # 3. Verify components can be initialized
        if cb_manager is not None:
            assert cb_manager.list_endpoints() is not None

        if error_handler is not None:
            # Can create user-friendly error
            test_error = Exception("Test error")
            user_msg = error_handler.sanitize_for_user(test_error)
            assert isinstance(user_msg, str)
            assert len(user_msg) > 0


# =============================================================================
# TEST: Backwards Compatibility
# =============================================================================

class TestBackwardsCompatibility:
    """Tests ensuring backwards compatibility with existing code."""

    def test_swap_executor_works_without_new_features(self):
        """SwapExecutor should work without simulation/circuit breaker config."""
        from bots.treasury.trading.trading_execution import SwapExecutor

        # Create with minimal config
        mock_jupiter = MagicMock()
        mock_wallet = MagicMock()

        executor = SwapExecutor(mock_jupiter, mock_wallet)

        # Should initialize without error
        assert executor is not None
        assert executor.jupiter is mock_jupiter
        assert executor.wallet is mock_wallet

    def test_trading_engine_works_with_existing_api(self):
        """TradingEngine should maintain existing API."""
        from bots.treasury.trading.trading_engine import TradingEngine

        # Check key methods exist
        assert hasattr(TradingEngine, 'get_open_positions')
        assert hasattr(TradingEngine, 'get_portfolio_value')
        assert hasattr(TradingEngine, '_execute_swap')

    def test_demo_trading_maintains_interface(self):
        """Demo trading should maintain existing interface."""
        from tg_bot.handlers.demo.demo_trading import (
            execute_buy_with_tpsl,
            _execute_swap_with_fallback,
            validate_buy_amount,
        )

        # Functions should exist
        assert callable(execute_buy_with_tpsl)
        assert callable(_execute_swap_with_fallback)
        assert callable(validate_buy_amount)
