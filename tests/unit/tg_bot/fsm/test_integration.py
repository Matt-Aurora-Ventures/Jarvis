"""
Tests for FSM integration with Telegram bot.

TDD Phase 1: Define expected behaviors for bot integration.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestFSMContext:
    """Test FSM context for telegram handlers."""

    @pytest.mark.asyncio
    async def test_context_get_state(self):
        """Test getting state from context."""
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.states import TradingStates
        from tg_bot.fsm.storage import RedisFSMStorage

        # Create context with mock storage
        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        ctx = FSMContext(storage=storage, user_id=123, chat_id=456)

        # Initially no state
        state = await ctx.get_state()
        assert state is None

        # Set state
        await ctx.set_state(TradingStates.waiting_for_token)

        # Get state back
        state = await ctx.get_state()
        assert state == TradingStates.waiting_for_token

    @pytest.mark.asyncio
    async def test_context_get_data(self):
        """Test getting/setting session data from context."""
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.states import SessionData
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        ctx = FSMContext(storage=storage, user_id=123, chat_id=456)

        # Initially no data
        data = await ctx.get_data()
        assert data is None

        # Set data
        session = SessionData(
            user_id=123,
            chat_id=456,
            token_address="TokenABC",
            amount=1.5
        )
        await ctx.set_data(session)

        # Get data back
        data = await ctx.get_data()
        assert data is not None
        assert data.token_address == "TokenABC"

    @pytest.mark.asyncio
    async def test_context_update_data(self):
        """Test updating specific fields in session data."""
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.states import SessionData
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        ctx = FSMContext(storage=storage, user_id=123, chat_id=456)

        # Set initial data
        session = SessionData(user_id=123, chat_id=456, amount=1.0)
        await ctx.set_data(session)

        # Update specific field
        await ctx.update_data(amount=2.0, slippage=0.01)

        # Verify update
        data = await ctx.get_data()
        assert data.amount == 2.0
        assert data.slippage == 0.01

    @pytest.mark.asyncio
    async def test_context_clear(self):
        """Test clearing session."""
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.states import TradingStates, SessionData
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        ctx = FSMContext(storage=storage, user_id=123, chat_id=456)

        # Set state and data
        await ctx.set_state(TradingStates.waiting_for_token)
        await ctx.set_data(SessionData(user_id=123, chat_id=456))

        # Clear
        await ctx.clear()

        # Verify cleared
        assert await ctx.get_state() is None
        assert await ctx.get_data() is None

    @pytest.mark.asyncio
    async def test_context_finish(self):
        """Test finishing state machine (alias for clear)."""
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.states import TradingStates
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        ctx = FSMContext(storage=storage, user_id=123, chat_id=456)

        await ctx.set_state(TradingStates.executing_trade)
        await ctx.finish()

        assert await ctx.get_state() is None


class TestFSMMiddleware:
    """Test FSM middleware for automatic context injection."""

    @pytest.mark.asyncio
    async def test_middleware_injects_context(self):
        """Test that middleware injects FSM context into handlers."""
        from tg_bot.fsm.middleware import FSMMiddleware
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        middleware = FSMMiddleware(storage=storage)

        # Create mock update and context
        update = MagicMock()
        update.effective_user = MagicMock(id=123)
        update.effective_chat = MagicMock(id=456)

        context = MagicMock()
        context.user_data = {}

        # Create mock handler
        handler = AsyncMock(return_value="handled")

        # Process through middleware
        result = await middleware(handler, update, context)

        # Verify FSM context was injected
        assert "fsm" in context.user_data
        assert isinstance(context.user_data["fsm"], FSMContext)

        # Verify handler was called
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_middleware_handles_missing_user(self):
        """Test middleware handles updates without user."""
        from tg_bot.fsm.middleware import FSMMiddleware
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        middleware = FSMMiddleware(storage=storage)

        # Update without user
        update = MagicMock()
        update.effective_user = None

        context = MagicMock()
        context.user_data = {}

        handler = AsyncMock(return_value="handled")

        # Should not crash
        result = await middleware(handler, update, context)

        # Handler should still be called
        handler.assert_called_once()


class TestFSMRouter:
    """Test FSM-based message routing."""

    @pytest.mark.asyncio
    async def test_router_dispatches_by_state(self):
        """Test router calls correct handler based on state."""
        from tg_bot.fsm.router import FSMRouter
        from tg_bot.fsm.states import TradingStates
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        router = FSMRouter()

        # Register handlers
        token_handler = AsyncMock(return_value="token_handled")
        amount_handler = AsyncMock(return_value="amount_handled")

        router.register(TradingStates.waiting_for_token, token_handler)
        router.register(TradingStates.waiting_for_amount, amount_handler)

        # Create context in waiting_for_token state
        ctx = FSMContext(storage=storage, user_id=123, chat_id=456)
        await ctx.set_state(TradingStates.waiting_for_token)

        # Route message
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "TokenABC"

        result = await router.dispatch(update, ctx)

        # Correct handler called
        token_handler.assert_called_once()
        amount_handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_router_handles_no_state(self):
        """Test router handles messages with no state."""
        from tg_bot.fsm.router import FSMRouter
        from tg_bot.fsm.states import TradingStates
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        router = FSMRouter()

        # Register handler
        token_handler = AsyncMock()
        router.register(TradingStates.waiting_for_token, token_handler)

        # Context with no state
        ctx = FSMContext(storage=storage, user_id=123, chat_id=456)

        update = MagicMock()
        update.message = MagicMock()

        # Should return None (no matching handler)
        result = await router.dispatch(update, ctx)
        assert result is None
        token_handler.assert_not_called()


class TestTradingFlow:
    """Test complete trading flow with FSM."""

    @pytest.mark.asyncio
    async def test_buy_flow_complete(self):
        """Test complete buy flow through FSM."""
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.states import TradingStates, SessionData
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        ctx = FSMContext(storage=storage, user_id=123, chat_id=456)

        # Step 1: Start buy flow
        await ctx.set_state(TradingStates.waiting_for_token)
        await ctx.set_data(SessionData(
            user_id=123,
            chat_id=456,
            wallet_address="UserWallet123"
        ))

        # Step 2: Receive token
        await ctx.update_data(token_address="TokenABC", token_symbol="ABC")
        await ctx.set_state(TradingStates.waiting_for_amount)

        # Step 3: Receive amount
        await ctx.update_data(amount=1.5)
        await ctx.set_state(TradingStates.setting_slippage)

        # Step 4: Set slippage
        await ctx.update_data(slippage=0.02)
        await ctx.set_state(TradingStates.setting_tp_sl)

        # Step 5: Set TP/SL
        await ctx.update_data(take_profit=0.10, stop_loss=0.05)
        await ctx.set_state(TradingStates.waiting_for_confirmation)

        # Verify final state
        state = await ctx.get_state()
        assert state == TradingStates.waiting_for_confirmation

        data = await ctx.get_data()
        assert data.token_address == "TokenABC"
        assert data.amount == 1.5
        assert data.slippage == 0.02
        assert data.take_profit == 0.10
        assert data.stop_loss == 0.05

        # Step 6: Confirm and execute
        await ctx.set_state(TradingStates.executing_trade)

        # Step 7: Complete - clear state
        await ctx.finish()

        # Verify cleared
        assert await ctx.get_state() is None

    @pytest.mark.asyncio
    async def test_buy_flow_cancel(self):
        """Test canceling buy flow at any step."""
        from tg_bot.fsm.context import FSMContext
        from tg_bot.fsm.states import TradingStates, SessionData
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")
        ctx = FSMContext(storage=storage, user_id=123, chat_id=456)

        # Start flow
        await ctx.set_state(TradingStates.waiting_for_amount)
        await ctx.set_data(SessionData(
            user_id=123,
            chat_id=456,
            token_address="TokenABC",
        ))

        # User cancels
        await ctx.clear()

        # Verify reset
        assert await ctx.get_state() is None
        assert await ctx.get_data() is None
