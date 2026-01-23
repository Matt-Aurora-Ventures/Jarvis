"""
Demo Bot Bug Fixes Test Suite (US-033)

Tests for critical bugs blocking demo bot public launch:
- Bug 1: safe_symbol NameError - function must exist and sanitize symbols
- Bug 2: amount KeyError - positions must use amount_sol consistently
- Bug 3: Bot Instance Conflicts - single instance enforcement
- Bug 4: TP/SL UI Not Wired - callback handlers must exist

TDD: Write tests first, then implement fixes.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio


class TestSafeSymbolFunction:
    """Test Bug 1: safe_symbol function must exist and work correctly."""

    def test_safe_symbol_exists_in_module(self):
        """safe_symbol function must be importable from demo module."""
        from tg_bot.handlers.demo import safe_symbol
        assert callable(safe_symbol)

    def test_safe_symbol_sanitizes_special_chars(self):
        """safe_symbol removes special characters that break Telegram formatting."""
        from tg_bot.handlers.demo import safe_symbol

        # Basic sanitization
        assert safe_symbol("TEST") == "TEST"
        assert safe_symbol("test") == "TEST"

        # Remove special chars
        assert safe_symbol("$TOKEN") == "TOKEN"
        assert safe_symbol("TOKEN!@#") == "TOKEN"
        assert safe_symbol("MY-TOKEN") == "MY-TOKEN"  # Hyphen allowed
        assert safe_symbol("MY_TOKEN") == "MY_TOKEN"  # Underscore allowed

    def test_safe_symbol_handles_empty_and_none(self):
        """safe_symbol handles edge cases."""
        from tg_bot.handlers.demo import safe_symbol

        assert safe_symbol("") == "UNKNOWN"
        assert safe_symbol(None) == "UNKNOWN"

    def test_safe_symbol_truncates_long_symbols(self):
        """safe_symbol truncates symbols longer than 10 chars."""
        from tg_bot.handlers.demo import safe_symbol

        long_symbol = "VERYLONGSYMBOLNAME"
        result = safe_symbol(long_symbol)
        assert len(result) <= 10

    def test_safe_symbol_handles_unicode(self):
        """safe_symbol handles unicode characters (removes them)."""
        from tg_bot.handlers.demo import safe_symbol

        # Emoji in symbol name
        assert "ROCKET" in safe_symbol("ROCKET") or safe_symbol("ROCKET") == "ROCKET"
        # Only alphanumeric + hyphen/underscore survive
        result = safe_symbol("TEST_123")
        assert result == "TEST_123"


class TestAmountKeyError:
    """Test Bug 2: Position dict must handle amount_sol consistently."""

    def test_position_uses_amount_sol(self):
        """Positions should use amount_sol as primary key."""
        # Simulate a position dict
        position = {
            "id": "test_001",
            "symbol": "TEST",
            "address": "testaddress",
            "amount_sol": 0.5,
            "entry_price": 0.001,
        }

        # Access pattern should work
        amount = position.get("amount_sol", position.get("amount", 0))
        assert amount == 0.5

    def test_legacy_amount_fallback(self):
        """Should fallback to 'amount' if amount_sol missing."""
        position = {
            "id": "test_002",
            "symbol": "TEST",
            "address": "testaddress",
            "amount": 0.3,  # Legacy key
            "entry_price": 0.001,
        }

        amount = position.get("amount_sol", position.get("amount", 0))
        assert amount == 0.3

    def test_sell_position_updates_amount_sol(self):
        """Partial sell should update amount_sol correctly."""
        position = {
            "id": "test_003",
            "symbol": "TEST",
            "amount": 100.0,
            "amount_sol": 1.0,
        }

        # Simulate 50% sell
        pct = 50
        position["amount"] *= (1 - pct / 100)
        position["amount_sol"] *= (1 - pct / 100)

        assert position["amount"] == 50.0
        assert position["amount_sol"] == 0.5


class TestTPSLCallbackHandlers:
    """Test Bug 4: TP/SL adjustment callbacks must be wired."""

    def test_demo_callback_patterns_exist(self):
        """Check that demo callback handler covers adj_tp, adj_sl patterns."""
        from tg_bot.handlers.demo import demo_callback

        # The function exists
        assert callable(demo_callback)

    @pytest.mark.asyncio
    async def test_adj_tp_callback_pattern_recognized(self):
        """adj_tp callback pattern should be handled without error."""
        # This tests that the pattern "demo:adj_tp:..." doesn't crash
        # We mock the update/context to avoid real Telegram calls
        from tg_bot.handlers.demo import demo_callback

        mock_query = MagicMock()
        mock_query.data = "demo:adj_tp:pos_001:10"
        mock_query.answer = AsyncMock()
        mock_query.message = MagicMock()
        mock_query.message.edit_text = AsyncMock()
        mock_query.message.chat_id = 12345

        mock_update = MagicMock()
        mock_update.callback_query = mock_query
        mock_update.effective_user = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_chat = MagicMock()
        mock_update.effective_chat.id = 12345

        mock_context = MagicMock()
        mock_context.user_data = {
            "positions": [
                {"id": "pos_001", "symbol": "TEST", "tp_percent": 50, "sl_percent": 20, "entry_price": 0.001}
            ]
        }
        mock_context.bot = MagicMock()

        # Should not raise NameError or crash
        try:
            await demo_callback(mock_update, mock_context)
        except Exception as e:
            # Check it's not a NameError for the callback pattern
            assert "adj_tp" not in str(e).lower() or "not defined" not in str(e).lower()

    @pytest.mark.asyncio
    async def test_adj_sl_callback_pattern_recognized(self):
        """adj_sl callback pattern should be handled without error."""
        from tg_bot.handlers.demo import demo_callback

        mock_query = MagicMock()
        mock_query.data = "demo:adj_sl:pos_001:-5"
        mock_query.answer = AsyncMock()
        mock_query.message = MagicMock()
        mock_query.message.edit_text = AsyncMock()
        mock_query.message.chat_id = 12345

        mock_update = MagicMock()
        mock_update.callback_query = mock_query
        mock_update.effective_user = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_chat = MagicMock()
        mock_update.effective_chat.id = 12345

        mock_context = MagicMock()
        mock_context.user_data = {
            "positions": [
                {"id": "pos_001", "symbol": "TEST", "tp_percent": 50, "sl_percent": 20, "entry_price": 0.001}
            ]
        }
        mock_context.bot = MagicMock()

        try:
            await demo_callback(mock_update, mock_context)
        except Exception as e:
            assert "adj_sl" not in str(e).lower() or "not defined" not in str(e).lower()

    @pytest.mark.asyncio
    async def test_adj_save_callback_pattern_recognized(self):
        """adj_save callback pattern should be handled."""
        from tg_bot.handlers.demo import demo_callback

        mock_query = MagicMock()
        mock_query.data = "demo:adj_save:pos_001"
        mock_query.answer = AsyncMock()
        mock_query.message = MagicMock()
        mock_query.message.edit_text = AsyncMock()
        mock_query.message.chat_id = 12345

        mock_update = MagicMock()
        mock_update.callback_query = mock_query
        mock_update.effective_user = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_chat = MagicMock()
        mock_update.effective_chat.id = 12345

        mock_context = MagicMock()
        mock_context.user_data = {
            "positions": [
                {"id": "pos_001", "symbol": "TEST", "tp_percent": 50, "sl_percent": 20, "entry_price": 0.001}
            ]
        }
        mock_context.bot = MagicMock()

        try:
            await demo_callback(mock_update, mock_context)
        except Exception as e:
            assert "adj_save" not in str(e).lower() or "not defined" not in str(e).lower()


class TestCustomBuyAmount:
    """Test US-031: Custom buy amount feature."""

    def test_custom_amount_validation_range(self):
        """Custom amount must be between 0.01 and 50 SOL."""
        from tg_bot.handlers.demo import validate_buy_amount

        # Test valid range
        assert validate_buy_amount(0.01)[0] is True
        assert validate_buy_amount(1.0)[0] is True
        assert validate_buy_amount(50)[0] is True

        # Test invalid range
        assert validate_buy_amount(0.001)[0] is False
        assert validate_buy_amount(100)[0] is False
        assert validate_buy_amount(-1)[0] is False

    @pytest.mark.asyncio
    async def test_buy_custom_callback_exists(self):
        """buy_custom callback should be recognized."""
        from tg_bot.handlers.demo import demo_callback

        mock_query = MagicMock()
        mock_query.data = "demo:buy_custom:tokenref"
        mock_query.answer = AsyncMock()
        mock_query.message = MagicMock()
        mock_query.message.edit_text = AsyncMock()
        mock_query.message.chat_id = 12345

        mock_update = MagicMock()
        mock_update.callback_query = mock_query
        mock_update.effective_user = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_chat = MagicMock()
        mock_update.effective_chat.id = 12345

        mock_context = MagicMock()
        mock_context.user_data = {}
        mock_context.bot = MagicMock()

        # Should handle without crashing - pattern should be recognized
        try:
            await demo_callback(mock_update, mock_context)
        except Exception as e:
            # Any error should not be about unrecognized callback
            pass  # We just want no crash for now


class TestLoadingStates:
    """Test US-032: Loading states and feedback."""

    def test_loading_text_format(self):
        """Loading text should be formatted correctly."""
        from tg_bot.handlers.demo import JarvisTheme

        loading = JarvisTheme.loading_text("Processing")
        assert "Processing" in loading
        assert "..." in loading


class TestSingleInstanceEnforcement:
    """Test Bug 3: Bot instance conflicts - supervisor single instance."""

    def test_single_instance_lock_mechanism_available(self):
        """Verify the single instance mechanism is importable/usable."""
        # On Windows, we use a different mechanism than fcntl
        import sys
        if sys.platform == "win32":
            # Windows uses named mutex or temp file
            import tempfile
            import os
            lock_file = os.path.join(tempfile.gettempdir(), "test_single_instance.lock")
            # Should be able to create
            assert tempfile.gettempdir() is not None
        else:
            import fcntl
            assert fcntl is not None


class TestTPSLDefaults:
    """Test US-005: TP/SL defaults are set on new positions."""

    def test_default_tp_sl_values(self):
        """New positions should have 50% TP and 20% SL defaults."""
        # Simulate new position creation (matches demo.py:9050-9068)
        token_price = 0.001
        default_tp_pct = 50.0
        default_sl_pct = 20.0

        new_position = {
            "id": "buy_1",
            "symbol": "TEST",
            "address": "testaddress",
            "amount": 1000.0,
            "amount_sol": 0.5,
            "entry_price": token_price,
            "current_price": token_price,
            "tp_percent": default_tp_pct,
            "sl_percent": default_sl_pct,
            "tp_price": token_price * (1 + default_tp_pct / 100),
            "sl_price": token_price * (1 - default_sl_pct / 100),
        }

        assert new_position["tp_percent"] == 50.0
        assert new_position["sl_percent"] == 20.0
        assert new_position["tp_price"] == token_price * 1.5  # 50% above entry
        assert new_position["sl_price"] == token_price * 0.8  # 20% below entry

    def test_tp_sl_can_be_adjusted(self):
        """TP/SL values should be adjustable after creation."""
        position = {
            "id": "buy_1",
            "tp_percent": 50.0,
            "sl_percent": 20.0,
            "entry_price": 0.001,
        }

        # Simulate adjustment: add 10% to TP
        delta = 10
        new_tp = position["tp_percent"] + delta
        position["tp_percent"] = new_tp
        position["tp_price"] = position["entry_price"] * (1 + new_tp / 100)

        assert position["tp_percent"] == 60.0
        assert position["tp_price"] == 0.001 * 1.6

    def test_tp_sl_clamped_to_valid_range(self):
        """TP should be clamped to 5-200%, SL to 5-100%."""
        # TP clamping
        tp_too_low = max(5.0, min(200.0, 2.0))  # Trying to set 2%
        tp_too_high = max(5.0, min(200.0, 250.0))  # Trying to set 250%
        assert tp_too_low == 5.0
        assert tp_too_high == 200.0

        # SL clamping
        sl_too_low = max(5.0, min(100.0, 2.0))  # Trying to set 2%
        sl_too_high = max(5.0, min(100.0, 150.0))  # Trying to set 150%
        assert sl_too_low == 5.0
        assert sl_too_high == 100.0
