"""
Tests for FSM trading states.

TDD Phase 1: Define expected behaviors before implementation.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestTradingStates:
    """Test FSM state definitions."""

    def test_trading_states_defined(self):
        """Verify all required trading states exist."""
        from tg_bot.fsm.states import TradingStates

        # Verify required states exist
        assert hasattr(TradingStates, 'waiting_for_token')
        assert hasattr(TradingStates, 'waiting_for_amount')
        assert hasattr(TradingStates, 'waiting_for_confirmation')
        assert hasattr(TradingStates, 'setting_slippage')
        assert hasattr(TradingStates, 'setting_tp_sl')

    def test_trading_states_are_unique(self):
        """Each state should have a unique identifier."""
        from tg_bot.fsm.states import TradingStates

        states = [
            TradingStates.waiting_for_token,
            TradingStates.waiting_for_amount,
            TradingStates.waiting_for_confirmation,
            TradingStates.setting_slippage,
            TradingStates.setting_tp_sl,
        ]

        # State strings should be unique
        state_strs = [str(s) for s in states]
        assert len(state_strs) == len(set(state_strs))


class TestWalletStates:
    """Test FSM wallet management states."""

    def test_wallet_states_defined(self):
        """Verify all wallet states exist."""
        from tg_bot.fsm.states import WalletStates

        assert hasattr(WalletStates, 'viewing_balance')
        assert hasattr(WalletStates, 'selecting_wallet')
        assert hasattr(WalletStates, 'confirming_withdraw')


class TestPortfolioStates:
    """Test FSM portfolio states."""

    def test_portfolio_states_defined(self):
        """Verify portfolio states exist."""
        from tg_bot.fsm.states import PortfolioStates

        assert hasattr(PortfolioStates, 'viewing_positions')
        assert hasattr(PortfolioStates, 'selecting_position')
        assert hasattr(PortfolioStates, 'closing_position')


class TestSettingsStates:
    """Test FSM settings states."""

    def test_settings_states_defined(self):
        """Verify settings states exist."""
        from tg_bot.fsm.states import SettingsStates

        assert hasattr(SettingsStates, 'main_menu')
        assert hasattr(SettingsStates, 'editing_slippage')
        assert hasattr(SettingsStates, 'editing_default_tp')
        assert hasattr(SettingsStates, 'editing_default_sl')


class TestSessionData:
    """Test session data models."""

    def test_session_data_creation(self):
        """Test creating session data."""
        from tg_bot.fsm.states import SessionData

        data = SessionData(
            user_id=123456,
            chat_id=789012,
            wallet_address="So11111111111111111111111111111111111111112"
        )

        assert data.user_id == 123456
        assert data.chat_id == 789012
        assert data.wallet_address is not None

    def test_session_data_optional_fields(self):
        """Test session data has optional fields."""
        from tg_bot.fsm.states import SessionData

        data = SessionData(user_id=123456, chat_id=789012)

        assert data.token_address is None
        assert data.amount is None
        assert data.slippage is None
        assert data.take_profit is None
        assert data.stop_loss is None

    def test_session_data_serialization(self):
        """Test session data can be serialized/deserialized."""
        from tg_bot.fsm.states import SessionData

        data = SessionData(
            user_id=123456,
            chat_id=789012,
            token_address="TokenAddress123",
            amount=0.5,
            slippage=0.01
        )

        # Serialize to dict
        serialized = data.to_dict()
        assert isinstance(serialized, dict)
        assert serialized['user_id'] == 123456
        assert serialized['amount'] == 0.5

        # Deserialize back
        restored = SessionData.from_dict(serialized)
        assert restored.user_id == data.user_id
        assert restored.amount == data.amount

    def test_session_data_with_trade_context(self):
        """Test session data for trade flow."""
        from tg_bot.fsm.states import SessionData

        data = SessionData(
            user_id=123456,
            chat_id=789012,
            token_address="TokenABC",
            token_symbol="ABC",
            amount=1.0,
            slippage=0.02,
            take_profit=0.10,
            stop_loss=0.05
        )

        assert data.token_symbol == "ABC"
        assert data.take_profit == 0.10
        assert data.stop_loss == 0.05


class TestStateTransitions:
    """Test FSM state transition validation."""

    def test_valid_buy_flow_transitions(self):
        """Test valid state transitions for buy flow."""
        from tg_bot.fsm.states import TradingStates, is_valid_transition

        # Valid transitions in buy flow
        assert is_valid_transition(None, TradingStates.waiting_for_token)
        assert is_valid_transition(TradingStates.waiting_for_token, TradingStates.waiting_for_amount)
        assert is_valid_transition(TradingStates.waiting_for_amount, TradingStates.setting_slippage)
        assert is_valid_transition(TradingStates.setting_slippage, TradingStates.setting_tp_sl)
        assert is_valid_transition(TradingStates.setting_tp_sl, TradingStates.waiting_for_confirmation)
        assert is_valid_transition(TradingStates.waiting_for_confirmation, None)  # Back to idle

    def test_cancel_from_any_state(self):
        """Test that cancel (return to idle) is valid from any trading state."""
        from tg_bot.fsm.states import TradingStates, is_valid_transition

        trading_states = [
            TradingStates.waiting_for_token,
            TradingStates.waiting_for_amount,
            TradingStates.waiting_for_confirmation,
            TradingStates.setting_slippage,
            TradingStates.setting_tp_sl,
        ]

        for state in trading_states:
            assert is_valid_transition(state, None), f"Should allow cancel from {state}"
