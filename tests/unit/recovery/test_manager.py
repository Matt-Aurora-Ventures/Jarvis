"""
Tests for RecoveryManager - error-type-based recovery handling.

Tests the ability to register handlers for specific error types
and attempt recovery with configurable max attempts.
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock, AsyncMock, patch


class TestRecoveryManager:
    """Test suite for RecoveryManager class."""

    def test_init_default_max_attempts(self):
        """RecoveryManager should initialize with max_recovery_attempts = 3."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        assert manager.max_recovery_attempts == 3

    def test_init_custom_max_attempts(self):
        """RecoveryManager should accept custom max_recovery_attempts."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager(max_recovery_attempts=5)
        assert manager.max_recovery_attempts == 5

    def test_register_recovery_handler(self):
        """register_recovery should register a handler for an error type."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        handler = Mock(return_value=True)

        manager.register_recovery(ConnectionError, handler)

        assert ConnectionError in manager._handlers
        assert manager._handlers[ConnectionError] == handler

    def test_register_recovery_multiple_handlers(self):
        """register_recovery should handle multiple error types."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        conn_handler = Mock(return_value=True)
        timeout_handler = Mock(return_value=True)

        manager.register_recovery(ConnectionError, conn_handler)
        manager.register_recovery(TimeoutError, timeout_handler)

        assert len(manager._handlers) == 2
        assert manager._handlers[ConnectionError] == conn_handler
        assert manager._handlers[TimeoutError] == timeout_handler

    def test_attempt_recovery_with_registered_handler_success(self):
        """attempt_recovery should return True when handler succeeds."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        handler = Mock(return_value=True)
        manager.register_recovery(ConnectionError, handler)

        error = ConnectionError("Connection failed")
        result = manager.attempt_recovery(error)

        assert result is True
        handler.assert_called_once_with(error)

    def test_attempt_recovery_with_registered_handler_failure(self):
        """attempt_recovery should return False when handler fails."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        handler = Mock(return_value=False)
        manager.register_recovery(ConnectionError, handler)

        error = ConnectionError("Connection failed")
        result = manager.attempt_recovery(error)

        assert result is False

    def test_attempt_recovery_no_handler(self):
        """attempt_recovery should return False when no handler is registered."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        error = ConnectionError("Connection failed")

        result = manager.attempt_recovery(error)

        assert result is False

    def test_attempt_recovery_tracks_attempts(self):
        """attempt_recovery should track recovery attempts."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        handler = Mock(return_value=True)
        manager.register_recovery(ConnectionError, handler)

        error = ConnectionError("Connection failed")
        manager.attempt_recovery(error)
        manager.attempt_recovery(error)

        stats = manager.get_recovery_stats()
        assert stats["total_attempts"] >= 2

    def test_attempt_recovery_respects_max_attempts(self):
        """attempt_recovery should stop after max_recovery_attempts."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager(max_recovery_attempts=2)
        # Handler always fails
        handler = Mock(return_value=False)
        manager.register_recovery(ConnectionError, handler)

        error = ConnectionError("Connection failed")

        # First attempt
        result1 = manager.attempt_recovery(error)
        result2 = manager.attempt_recovery(error)
        # Third attempt should be blocked
        result3 = manager.attempt_recovery(error)

        # After max attempts, should stop trying
        assert handler.call_count <= 3  # Max attempts + 1

    def test_attempt_recovery_handler_exception(self):
        """attempt_recovery should handle exceptions in handlers gracefully."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        handler = Mock(side_effect=RuntimeError("Handler crashed"))
        manager.register_recovery(ConnectionError, handler)

        error = ConnectionError("Connection failed")
        result = manager.attempt_recovery(error)

        assert result is False

    def test_attempt_recovery_subclass_error(self):
        """attempt_recovery should match error subclasses."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        handler = Mock(return_value=True)
        # Register for base Exception
        manager.register_recovery(Exception, handler)

        # Should match subclass
        error = ConnectionError("Connection failed")
        result = manager.attempt_recovery(error)

        assert result is True

    def test_get_recovery_stats_structure(self):
        """get_recovery_stats should return proper dict structure."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        stats = manager.get_recovery_stats()

        assert isinstance(stats, dict)
        assert "total_attempts" in stats
        assert "successful_recoveries" in stats
        assert "failed_recoveries" in stats
        assert "handlers_registered" in stats

    def test_get_recovery_stats_after_operations(self):
        """get_recovery_stats should reflect actual operations."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        success_handler = Mock(return_value=True)
        fail_handler = Mock(return_value=False)

        manager.register_recovery(ConnectionError, success_handler)
        manager.register_recovery(TimeoutError, fail_handler)

        manager.attempt_recovery(ConnectionError("test"))
        manager.attempt_recovery(TimeoutError("test"))

        stats = manager.get_recovery_stats()

        assert stats["total_attempts"] == 2
        assert stats["successful_recoveries"] == 1
        assert stats["failed_recoveries"] == 1
        assert stats["handlers_registered"] == 2

    def test_recovery_with_context(self):
        """attempt_recovery should accept optional context."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()
        handler = Mock(return_value=True)
        manager.register_recovery(ConnectionError, handler)

        error = ConnectionError("test")
        context = {"component": "x_bot", "operation": "post_tweet"}

        result = manager.attempt_recovery(error, context=context)

        assert result is True
        # Handler should receive context
        handler.assert_called_once()
        call_args = handler.call_args
        # Check if context was passed
        assert call_args[0][0] == error

    def test_reset_attempt_counter(self):
        """RecoveryManager should allow resetting attempt counters."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager(max_recovery_attempts=2)
        handler = Mock(return_value=False)
        manager.register_recovery(ConnectionError, handler)

        error = ConnectionError("test")

        # Exhaust attempts
        manager.attempt_recovery(error)
        manager.attempt_recovery(error)

        # Reset
        manager.reset_attempts()

        # Should be able to attempt again
        manager.attempt_recovery(error)

        stats = manager.get_recovery_stats()
        assert stats["total_attempts"] == 3


class TestRecoveryManagerIntegration:
    """Integration tests for RecoveryManager with strategies."""

    def test_with_strategy_handler(self):
        """RecoveryManager should work with strategy-based handlers."""
        from core.recovery.manager import RecoveryManager

        manager = RecoveryManager()

        # Simple retry strategy
        attempts = []
        def retry_handler(error):
            attempts.append(error)
            return len(attempts) >= 2  # Succeed on second try

        manager.register_recovery(ConnectionError, retry_handler)

        error = ConnectionError("test")
        result1 = manager.attempt_recovery(error)
        result2 = manager.attempt_recovery(error)

        assert result1 is False
        assert result2 is True
