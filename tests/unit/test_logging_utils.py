"""
Tests for bots.treasury.trading.logging_utils

Coverage targets:
- Lines 15-16, 22: Import fallback paths
- Lines 27-36: log_trading_error function
- Lines 44-45: log_trading_event fallback
- Lines 86-98: UPDATE, ERROR, and else branches of log_position_change
"""

import logging
import pytest
import sys
import builtins
from unittest.mock import patch, MagicMock


class TestLogTradingErrorFallback:
    """Tests for log_trading_error fallback path (lines 35-36)."""

    def test_log_trading_error_fallback_on_import_error(self):
        """Test log_trading_error falls back to logger.error on ImportError."""
        from bots.treasury.trading import logging_utils

        # Mock the import inside the function to fail
        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked import error")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "error") as mock_error:
            with patch.object(builtins, "__import__", failing_import):
                error = ValueError("Test error")
                logging_utils.log_trading_error(error, "test_context", {"key": "value"})

                # Verify fallback logger was called
                mock_error.assert_called_once()
                call_args = mock_error.call_args
                assert "[test_context]" in call_args[0][0]
                assert "Test error" in call_args[0][0]
                assert call_args[1].get("exc_info") == True

    def test_log_trading_error_with_none_metadata(self):
        """Test log_trading_error with None metadata."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "error") as mock_error:
            with patch.object(builtins, "__import__", failing_import):
                logging_utils.log_trading_error(
                    ValueError("Invalid value"),
                    "validation",
                    None  # No metadata
                )

                mock_error.assert_called_once()


class TestLogTradingEventFallback:
    """Tests for log_trading_event fallback path (lines 44-45)."""

    def test_log_trading_event_fallback_on_import_error(self):
        """Test log_trading_event falls back to logger.info on ImportError."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked import error")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "info") as mock_info:
            with patch.object(builtins, "__import__", failing_import):
                logging_utils.log_trading_event("TEST_EVENT", "Test message", {"data": 1})

                # Verify fallback logger was called
                mock_info.assert_called()
                # Find the call that matches our event
                calls = [str(c) for c in mock_info.call_args_list]
                assert any("[TEST_EVENT]" in c for c in calls)


class TestLogPositionChangeAllBranches:
    """Tests for log_position_change to cover all branches."""

    def test_log_position_open_action(self):
        """Test OPEN action branch (lines 72-78)."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "info") as mock_info:
            with patch.object(builtins, "__import__", failing_import):
                logging_utils.log_position_change(
                    action="OPEN",
                    position_id="pos123",
                    symbol="SOL",
                    details={
                        "amount_usd": 100.0,
                        "entry_price": 50.0,
                        "tp_price": 60.0,
                        "sl_price": 45.0
                    }
                )

                # Check the logger was called (at least twice - once for OPEN, once for event)
                assert mock_info.call_count >= 1
                # Find the POSITION:OPEN call
                calls = [str(c) for c in mock_info.call_args_list]
                assert any("[POSITION:OPEN]" in c for c in calls)

    def test_log_position_close_action(self):
        """Test CLOSE action branch (lines 79-85)."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "info") as mock_info:
            with patch.object(builtins, "__import__", failing_import):
                logging_utils.log_position_change(
                    action="CLOSE",
                    position_id="pos123",
                    symbol="SOL",
                    details={
                        "pnl_usd": 25.0,
                        "pnl_pct": 25.0,
                        "exit_price": 62.5,
                        "reason": "take_profit"
                    }
                )

                calls = [str(c) for c in mock_info.call_args_list]
                assert any("[POSITION:CLOSE]" in c for c in calls)

    def test_log_position_update_action(self):
        """Test UPDATE action branch (lines 86-91)."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "debug") as mock_debug:
            with patch.object(logging_utils.logger, "info"):
                with patch.object(builtins, "__import__", failing_import):
                    logging_utils.log_position_change(
                        action="UPDATE",
                        position_id="pos123",
                        symbol="SOL",
                        details={
                            "current_price": 55.0,
                            "unrealized_pnl": 10.0
                        }
                    )

                    mock_debug.assert_called_once()
                    call_str = mock_debug.call_args[0][0]
                    assert "[POSITION:UPDATE]" in call_str
                    assert "pos123" in call_str
                    assert "SOL" in call_str

    def test_log_position_error_action(self):
        """Test ERROR action branch (lines 92-96)."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "error") as mock_error:
            with patch.object(logging_utils.logger, "info"):
                with patch.object(builtins, "__import__", failing_import):
                    logging_utils.log_position_change(
                        action="ERROR",
                        position_id="pos123",
                        symbol="SOL",
                        details={
                            "error": "Connection timeout"
                        }
                    )

                    mock_error.assert_called_once()
                    call_str = mock_error.call_args[0][0]
                    assert "[POSITION:ERROR]" in call_str
                    assert "Connection timeout" in call_str

    def test_log_position_unknown_action(self):
        """Test else branch for unknown action (lines 97-98)."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "info") as mock_info:
            with patch.object(builtins, "__import__", failing_import):
                logging_utils.log_position_change(
                    action="RECONCILE",
                    position_id="pos123",
                    symbol="SOL",
                    details={
                        "old_value": 100,
                        "new_value": 105
                    }
                )

                calls = [str(c) for c in mock_info.call_args_list]
                assert any("[POSITION:RECONCILE]" in c for c in calls)

    def test_log_position_change_with_none_details(self):
        """Test default empty dict for None details (line 59)."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "info"):
            with patch.object(builtins, "__import__", failing_import):
                # Should not raise even with None details
                logging_utils.log_position_change(
                    action="OPEN",
                    position_id="pos123",
                    symbol="SOL",
                    details=None
                )


class TestModuleLevelImports:
    """Tests for module-level import behavior."""

    def test_structured_logging_available_flag_exists(self):
        """Test that STRUCTURED_LOGGING_AVAILABLE is defined."""
        from bots.treasury.trading import logging_utils

        assert hasattr(logging_utils, "STRUCTURED_LOGGING_AVAILABLE")
        assert isinstance(logging_utils.STRUCTURED_LOGGING_AVAILABLE, bool)

    def test_logger_is_defined(self):
        """Test that logger is defined at module level."""
        from bots.treasury.trading import logging_utils

        assert hasattr(logging_utils, "logger")
        assert logging_utils.logger is not None

    def test_logger_has_required_methods(self):
        """Test that logger has standard logging methods."""
        from bots.treasury.trading import logging_utils

        assert hasattr(logging_utils.logger, "info")
        assert hasattr(logging_utils.logger, "error")
        assert hasattr(logging_utils.logger, "debug")
        assert hasattr(logging_utils.logger, "warning")


class TestLogPositionChangeIntegration:
    """Integration tests for log_position_change."""

    def test_log_position_change_builds_correct_log_data(self):
        """Test that log_data is built correctly with all fields."""
        from bots.treasury.trading import logging_utils
        from unittest.mock import ANY

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "info") as mock_info:
            with patch.object(builtins, "__import__", failing_import):
                logging_utils.log_position_change(
                    action="CLOSE",
                    position_id="pos456",
                    symbol="ETH",
                    details={
                        "pnl_usd": -10.0,
                        "pnl_pct": -5.0,
                        "exit_price": 2000.0,
                        "reason": "stop_loss"
                    }
                )

                # Check CLOSE log was called with correct format
                calls = [c for c in mock_info.call_args_list]
                close_call = [c for c in calls if "[POSITION:CLOSE]" in str(c)]
                assert len(close_call) >= 1

    def test_log_position_update_uses_debug_level(self):
        """Verify UPDATE uses debug level, not info."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "debug") as mock_debug:
            with patch.object(logging_utils.logger, "info") as mock_info:
                with patch.object(builtins, "__import__", failing_import):
                    logging_utils.log_position_change(
                        action="UPDATE",
                        position_id="pos789",
                        symbol="BTC",
                        details={
                            "current_price": 45000.0,
                            "unrealized_pnl": 500.0
                        }
                    )

                    # UPDATE should use debug, not info for position log
                    mock_debug.assert_called()
                    # Info is called for the event log
                    assert any("[POSITION_UPDATE]" in str(c) for c in mock_info.call_args_list)

    def test_log_position_error_uses_error_level(self):
        """Verify ERROR uses error level."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "error") as mock_error:
            with patch.object(logging_utils.logger, "info"):
                with patch.object(builtins, "__import__", failing_import):
                    logging_utils.log_position_change(
                        action="ERROR",
                        position_id="pos999",
                        symbol="DOGE",
                        details={
                            "error": "Network timeout"
                        }
                    )

                    mock_error.assert_called()
                    call_str = str(mock_error.call_args_list)
                    assert "Network timeout" in call_str


class TestLogTradingEventDirect:
    """Direct tests for log_trading_event."""

    def test_log_trading_event_with_data(self):
        """Test log_trading_event with data parameter."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "info") as mock_info:
            with patch.object(builtins, "__import__", failing_import):
                logging_utils.log_trading_event(
                    "TRADE_EXECUTED",
                    "Trade completed successfully",
                    {"trade_id": "t123", "amount": 100}
                )

                mock_info.assert_called()
                call_str = str(mock_info.call_args_list)
                assert "[TRADE_EXECUTED]" in call_str

    def test_log_trading_event_without_data(self):
        """Test log_trading_event without data parameter."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        with patch.object(logging_utils.logger, "info") as mock_info:
            with patch.object(builtins, "__import__", failing_import):
                logging_utils.log_trading_event(
                    "SYSTEM_START",
                    "Trading system initialized",
                    None
                )

                mock_info.assert_called()


class TestLogTradingErrorDirect:
    """Direct tests for log_trading_error."""

    def test_log_trading_error_with_different_exception_types(self):
        """Test log_trading_error with various exception types."""
        from bots.treasury.trading import logging_utils

        original_import = builtins.__import__

        def failing_import(name, *args, **kwargs):
            if "supervisor_health_bus" in name:
                raise ImportError("Mocked")
            return original_import(name, *args, **kwargs)

        exceptions = [
            RuntimeError("Runtime issue"),
            ValueError("Value issue"),
            ConnectionError("Connection issue"),
            TimeoutError("Timeout issue"),
        ]

        for exc in exceptions:
            with patch.object(logging_utils.logger, "error") as mock_error:
                with patch.object(builtins, "__import__", failing_import):
                    logging_utils.log_trading_error(exc, "test_context")

                    mock_error.assert_called()
                    call_str = str(mock_error.call_args_list)
                    assert "[test_context]" in call_str
