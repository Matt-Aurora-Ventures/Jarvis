"""
Tests for Emergency Stop Mechanism

Validates:
- Stop level transitions
- Trading permission checks
- Token-specific pauses
- Position unwinding logic
- Alert callbacks
- State persistence
"""

import pytest
import asyncio
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from core.trading.emergency_stop import (
    EmergencyStopManager,
    EmergencyConfig,
    StopLevel,
    UnwindStrategy,
    StopState,
)


@pytest.fixture
def temp_state_file(tmp_path):
    """Create a temporary state file for testing."""
    return tmp_path / "emergency_stop.json"


@pytest.fixture
def emergency_manager(temp_state_file):
    """Create an emergency stop manager with test config."""
    config = EmergencyConfig(state_file=temp_state_file)
    return EmergencyStopManager(config)


class TestStopLevels:
    """Test different emergency stop levels."""

    def test_initial_state_is_none(self, emergency_manager):
        """Verify initial state allows trading."""
        allowed, reason = emergency_manager.is_trading_allowed()
        assert allowed is True
        assert reason == ""
        assert emergency_manager.state.level == StopLevel.NONE

    def test_soft_stop_blocks_new_trades(self, emergency_manager):
        """Soft stop should block new positions."""
        success, msg = emergency_manager.activate_soft_stop(
            reason="Market volatility",
            activated_by="test_user"
        )

        assert success is True
        allowed, reason = emergency_manager.is_trading_allowed()
        assert allowed is False
        assert "SOFT STOP" in reason
        assert emergency_manager.state.level == StopLevel.SOFT_STOP

    def test_hard_stop_requires_unwind(self, emergency_manager):
        """Hard stop should trigger position unwinding."""
        success, msg = emergency_manager.activate_hard_stop(
            reason="Risk limit breach",
            activated_by="system",
            unwind_strategy=UnwindStrategy.GRACEFUL
        )

        assert success is True
        assert emergency_manager.should_unwind_positions() is True
        assert emergency_manager.get_unwind_strategy() == UnwindStrategy.GRACEFUL
        allowed, _ = emergency_manager.is_trading_allowed()
        assert allowed is False

    def test_kill_switch_immediate_halt(self, emergency_manager):
        """Kill switch should halt everything immediately."""
        success, msg = emergency_manager.activate_kill_switch(
            reason="Security incident",
            activated_by="admin",
            unwind_strategy=UnwindStrategy.IMMEDIATE
        )

        assert success is True
        assert emergency_manager.state.level == StopLevel.KILL_SWITCH
        assert emergency_manager.should_unwind_positions() is True
        assert emergency_manager.get_unwind_strategy() == UnwindStrategy.IMMEDIATE


class TestTokenPause:
    """Test token-specific pause functionality."""

    def test_pause_single_token(self, emergency_manager):
        """Pause trading for specific token."""
        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

        success, msg = emergency_manager.pause_token(
            token_mint=token_mint,
            reason="Suspicious activity",
            activated_by="fraud_detection"
        )

        assert success is True
        assert token_mint in emergency_manager.state.paused_tokens

        # Check trading permission for this token
        allowed, reason = emergency_manager.is_trading_allowed(token_mint)
        assert allowed is False
        assert "TOKEN PAUSED" in reason

        # Check other tokens still allowed
        other_token = "So11111111111111111111111111111111111111112"
        allowed, _ = emergency_manager.is_trading_allowed(other_token)
        assert allowed is True

    def test_resume_paused_token(self, emergency_manager):
        """Resume trading for previously paused token."""
        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

        # Pause
        emergency_manager.pause_token(token_mint, "Test pause", "admin")

        # Resume
        success, msg = emergency_manager.resume_token(token_mint)
        assert success is True
        assert token_mint not in emergency_manager.state.paused_tokens

        # Check trading allowed again
        allowed, _ = emergency_manager.is_trading_allowed(token_mint)
        assert allowed is True

    def test_pause_multiple_tokens(self, emergency_manager):
        """Pause multiple tokens independently."""
        tokens = [
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "So11111111111111111111111111111111111111112",
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        ]

        for token in tokens:
            emergency_manager.pause_token(token, f"Pause {token}", "admin")

        assert len(emergency_manager.state.paused_tokens) == 3

        # All should be blocked
        for token in tokens:
            allowed, _ = emergency_manager.is_trading_allowed(token)
            assert allowed is False


class TestResume:
    """Test resuming trading after emergency stop."""

    def test_resume_from_soft_stop(self, emergency_manager):
        """Resume trading from soft stop."""
        # Activate soft stop
        emergency_manager.activate_soft_stop("Test", "admin")

        # Resume
        success, msg = emergency_manager.resume_trading("admin")
        assert success is True
        assert emergency_manager.state.level == StopLevel.NONE

        # Trading should be allowed
        allowed, _ = emergency_manager.is_trading_allowed()
        assert allowed is True

    def test_resume_from_kill_switch(self, emergency_manager):
        """Resume trading from kill switch."""
        # Activate kill switch
        emergency_manager.activate_kill_switch("Emergency", "system")

        # Resume
        success, msg = emergency_manager.resume_trading("admin")
        assert success is True

        # Verify full reset
        assert emergency_manager.state.level == StopLevel.NONE
        assert emergency_manager.state.activated_at is None
        assert emergency_manager.state.reason == ""


class TestStatePersistence:
    """Test state is persisted to disk."""

    def test_state_saved_on_activation(self, emergency_manager, temp_state_file):
        """State file should be created on activation."""
        emergency_manager.activate_soft_stop("Test", "admin")

        # Check file exists
        assert temp_state_file.exists()

        # Check file content
        with open(temp_state_file) as f:
            data = json.load(f)
            assert data["level"] == "SOFT_STOP"
            assert data["activated_by"] == "admin"
            assert data["reason"] == "Test"

    def test_state_loaded_on_init(self, temp_state_file):
        """State should be restored from disk on initialization."""
        # Create initial manager and activate stop
        config1 = EmergencyConfig(state_file=temp_state_file)
        manager1 = EmergencyStopManager(config1)
        manager1.activate_hard_stop("Test persistence", "admin")

        # Create new manager - should load state
        config2 = EmergencyConfig(state_file=temp_state_file)
        manager2 = EmergencyStopManager(config2)

        # Verify state restored
        assert manager2.state.level == StopLevel.HARD_STOP
        assert manager2.state.reason == "Test persistence"
        assert manager2.state.activated_by == "admin"

    def test_resume_clears_state_file(self, emergency_manager, temp_state_file):
        """Resuming should update state file."""
        emergency_manager.activate_soft_stop("Test", "admin")
        emergency_manager.resume_trading("admin")

        # Check file reflects NONE state
        with open(temp_state_file) as f:
            data = json.load(f)
            assert data["level"] == "NONE"


class TestAlertCallbacks:
    """Test alert callbacks are triggered."""

    @pytest.mark.asyncio
    async def test_callback_on_activation(self, emergency_manager):
        """Alert callback should fire on stop activation."""
        callback_mock = AsyncMock()
        emergency_manager.register_alert_callback(callback_mock)

        # Activate stop
        emergency_manager.activate_soft_stop("Test alert", "admin")

        # Wait for async callback
        await asyncio.sleep(0.1)

        # Verify callback was called
        callback_mock.assert_called_once()
        call_args = callback_mock.call_args[0][0]
        assert "SOFT STOP ACTIVATED" in call_args
        assert "Test alert" in call_args

    @pytest.mark.asyncio
    async def test_callback_on_resume(self, emergency_manager):
        """Alert callback should fire on resume."""
        callback_mock = AsyncMock()
        emergency_manager.register_alert_callback(callback_mock)

        # Activate and resume
        emergency_manager.activate_soft_stop("Test", "admin")
        await asyncio.sleep(0.1)
        callback_mock.reset_mock()

        emergency_manager.resume_trading("admin")
        await asyncio.sleep(0.1)

        # Verify resume callback
        callback_mock.assert_called_once()
        call_args = callback_mock.call_args[0][0]
        assert "TRADING RESUMED" in call_args

    @pytest.mark.asyncio
    async def test_multiple_callbacks(self, emergency_manager):
        """Multiple callbacks should all fire."""
        callback1 = AsyncMock()
        callback2 = AsyncMock()
        callback3 = Mock()  # Sync callback

        emergency_manager.register_alert_callback(callback1)
        emergency_manager.register_alert_callback(callback2)
        emergency_manager.register_alert_callback(callback3)

        emergency_manager.activate_kill_switch("Test multi", "admin")
        await asyncio.sleep(0.1)

        callback1.assert_called_once()
        callback2.assert_called_once()
        callback3.assert_called_once()


class TestGetStatus:
    """Test status reporting."""

    def test_status_reflects_current_state(self, emergency_manager):
        """Status should match current state."""
        emergency_manager.activate_hard_stop(
            "Test status",
            "admin",
            UnwindStrategy.GRACEFUL
        )

        status = emergency_manager.get_status()

        assert status["level"] == "HARD_STOP"
        assert status["trading_allowed"] is False
        assert status["activated_by"] == "admin"
        assert status["reason"] == "Test status"
        assert status["should_unwind"] is True
        assert status["unwind_strategy"] == "GRACEFUL"

    def test_status_includes_paused_tokens(self, emergency_manager):
        """Status should list paused tokens."""
        tokens = ["token1", "token2", "token3"]
        for token in tokens:
            emergency_manager.pause_token(token, "Test", "admin")

        status = emergency_manager.get_status()
        assert len(status["paused_tokens"]) == 3
        assert set(status["paused_tokens"]) == set(tokens)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_resume_when_not_stopped(self, emergency_manager):
        """Resuming when already normal should succeed."""
        success, msg = emergency_manager.resume_trading("admin")
        assert success is True

    def test_resume_token_not_paused(self, emergency_manager):
        """Resuming unpause token should fail gracefully."""
        success, msg = emergency_manager.resume_token("fake_token")
        assert success is False
        assert "not paused" in msg

    def test_multiple_activations(self, emergency_manager):
        """Multiple activations should update state."""
        emergency_manager.activate_soft_stop("First", "user1")
        emergency_manager.activate_hard_stop("Second", "user2")

        # Should be at HARD_STOP now
        assert emergency_manager.state.level == StopLevel.HARD_STOP
        assert emergency_manager.state.reason == "Second"
        assert emergency_manager.state.activated_by == "user2"

    def test_token_pause_with_existing_stop(self, emergency_manager):
        """Token pause should work alongside global stops."""
        # Activate soft stop
        emergency_manager.activate_soft_stop("Global stop", "admin")

        # Pause specific token
        token = "test_token"
        emergency_manager.pause_token(token, "Token issue", "admin")

        # Both should block
        allowed, reason = emergency_manager.is_trading_allowed(token)
        assert allowed is False
        # Could be blocked by either global or token pause


class TestUnwindStrategies:
    """Test different position unwinding strategies."""

    def test_immediate_unwind_strategy(self, emergency_manager):
        """IMMEDIATE strategy for kill switch."""
        emergency_manager.activate_kill_switch(
            "Emergency",
            "admin",
            UnwindStrategy.IMMEDIATE
        )

        assert emergency_manager.get_unwind_strategy() == UnwindStrategy.IMMEDIATE

    def test_graceful_unwind_strategy(self, emergency_manager):
        """GRACEFUL strategy for hard stop."""
        emergency_manager.activate_hard_stop(
            "Controlled shutdown",
            "admin",
            UnwindStrategy.GRACEFUL
        )

        assert emergency_manager.get_unwind_strategy() == UnwindStrategy.GRACEFUL

    def test_no_unwind_for_soft_stop(self, emergency_manager):
        """Soft stop should not trigger unwinding."""
        emergency_manager.activate_soft_stop("Pause", "admin")

        assert emergency_manager.should_unwind_positions() is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
