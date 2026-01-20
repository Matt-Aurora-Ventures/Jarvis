"""
Tests for Telegram UI Inline Button Framework.

Tests cover:
- Button creation and callback data formatting
- Buy/Sell quick action buttons
- Position management buttons
- Command quick-select buttons
- Callback parsing and routing
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# =============================================================================
# Test Button Builder Class
# =============================================================================

class TestButtonBuilder:
    """Test the ButtonBuilder utility class."""

    def test_create_simple_button(self):
        """Button with text and callback should be created."""
        from tg_bot.ui.inline_buttons import ButtonBuilder

        builder = ButtonBuilder()
        button = builder.button("Buy", "buy:SOL")

        assert isinstance(button, InlineKeyboardButton)
        assert button.text == "Buy"
        assert button.callback_data == "buy:SOL"

    def test_create_url_button(self):
        """Button with URL should not have callback_data."""
        from tg_bot.ui.inline_buttons import ButtonBuilder

        builder = ButtonBuilder()
        button = builder.url_button("View Chart", "https://dexscreener.com/solana/xyz")

        assert isinstance(button, InlineKeyboardButton)
        assert button.text == "View Chart"
        assert button.url == "https://dexscreener.com/solana/xyz"

    def test_create_row(self):
        """Row should contain multiple buttons."""
        from tg_bot.ui.inline_buttons import ButtonBuilder

        builder = ButtonBuilder()
        row = builder.row([
            builder.button("A", "a"),
            builder.button("B", "b"),
        ])

        assert len(row) == 2
        assert all(isinstance(b, InlineKeyboardButton) for b in row)

    def test_create_keyboard(self):
        """Keyboard should contain multiple rows."""
        from tg_bot.ui.inline_buttons import ButtonBuilder

        builder = ButtonBuilder()
        keyboard = builder.keyboard([
            [builder.button("Row1-A", "r1a"), builder.button("Row1-B", "r1b")],
            [builder.button("Row2-A", "r2a")],
        ])

        assert isinstance(keyboard, InlineKeyboardMarkup)
        # Telegram's InlineKeyboardMarkup stores rows in inline_keyboard
        rows = keyboard.inline_keyboard
        assert len(rows) == 2
        assert len(rows[0]) == 2
        assert len(rows[1]) == 1


# =============================================================================
# Test Quick Action Buttons
# =============================================================================

class TestQuickActionButtons:
    """Test quick action button generation."""

    def test_buy_button(self):
        """Buy button should have correct callback format."""
        from tg_bot.ui.inline_buttons import QuickActionButtons

        buttons = QuickActionButtons()
        keyboard = buttons.buy_button("So11111111111111111111111111111111", "SOL", 100.0)

        rows = keyboard.inline_keyboard
        # Should have at least confirm and cancel buttons
        assert len(rows) >= 1

        # Find confirm button
        all_buttons = [b for row in rows for b in row]
        confirm_btn = next((b for b in all_buttons if "confirm" in b.callback_data.lower()), None)
        assert confirm_btn is not None

    def test_sell_button_with_percentages(self):
        """Sell button should show percentage options."""
        from tg_bot.ui.inline_buttons import QuickActionButtons

        buttons = QuickActionButtons()
        keyboard = buttons.sell_button("So11111111111111111111111111111111", "SOL")

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have 25%, 50%, 75%, 100% options
        percentages = ["25", "50", "75", "100"]
        for pct in percentages:
            assert any(pct in b.text or pct in b.callback_data for b in all_buttons), f"Missing {pct}% option"

    def test_hold_button(self):
        """Hold/watch button should offer watchlist option."""
        from tg_bot.ui.inline_buttons import QuickActionButtons

        buttons = QuickActionButtons()
        keyboard = buttons.hold_button("So11111111111111111111111111111111", "SOL")

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have watchlist option
        assert any("watch" in b.callback_data.lower() for b in all_buttons)


# =============================================================================
# Test Position Management Buttons
# =============================================================================

class TestPositionButtons:
    """Test position management button generation."""

    def test_position_action_buttons(self):
        """Position should have sell, TP/SL adjust, and details buttons."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.position_actions(
            position_id="pos_123",
            token_symbol="SOL",
            current_pnl_pct=15.5
        )

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have sell option
        assert any("sell" in b.callback_data.lower() for b in all_buttons)

        # Should have details option
        assert any("detail" in b.callback_data.lower() for b in all_buttons)

    def test_close_position_confirmation(self):
        """Close confirmation should have confirm and cancel."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.close_confirmation(
            position_id="pos_123",
            token_symbol="SOL",
            sell_percent=100
        )

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have confirm
        assert any("confirm" in b.callback_data.lower() for b in all_buttons)

        # Should have cancel
        assert any("cancel" in b.callback_data.lower() for b in all_buttons)

    def test_adjust_tp_sl_buttons(self):
        """TP/SL adjustment should provide increment/decrement options."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.adjust_tp_sl(
            position_id="pos_123",
            current_tp=0.001,
            current_sl=0.0008
        )

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have TP adjustment
        assert any("tp" in b.callback_data.lower() for b in all_buttons)

        # Should have SL adjustment
        assert any("sl" in b.callback_data.lower() for b in all_buttons)


# =============================================================================
# Test Command Select Buttons
# =============================================================================

class TestCommandButtons:
    """Test command quick-select button generation."""

    def test_main_menu_buttons(self):
        """Main menu should have core commands."""
        from tg_bot.ui.inline_buttons import CommandButtons

        buttons = CommandButtons()
        keyboard = buttons.main_menu(is_admin=False)

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have common commands
        commands = ["trending", "status", "help"]
        for cmd in commands:
            assert any(cmd in b.callback_data.lower() for b in all_buttons), f"Missing {cmd}"

    def test_admin_menu_buttons(self):
        """Admin menu should have extra commands."""
        from tg_bot.ui.inline_buttons import CommandButtons

        buttons = CommandButtons()
        keyboard = buttons.main_menu(is_admin=True)

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Admin should have more buttons than non-admin
        non_admin_keyboard = buttons.main_menu(is_admin=False)
        non_admin_buttons = [b for row in non_admin_keyboard.inline_keyboard for b in row]

        assert len(all_buttons) > len(non_admin_buttons)

    def test_trading_commands(self):
        """Trading command buttons should be available."""
        from tg_bot.ui.inline_buttons import CommandButtons

        buttons = CommandButtons()
        keyboard = buttons.trading_commands()

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have trading-related commands
        assert any("dashboard" in b.callback_data.lower() or "position" in b.callback_data.lower() for b in all_buttons)

    def test_analysis_commands(self):
        """Analysis command buttons should be available."""
        from tg_bot.ui.inline_buttons import CommandButtons

        buttons = CommandButtons()
        keyboard = buttons.analysis_commands()

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have analysis commands
        assert any("analyze" in b.callback_data.lower() or "chart" in b.callback_data.lower() for b in all_buttons)


# =============================================================================
# Test Callback Data Utilities
# =============================================================================

class TestCallbackDataUtils:
    """Test callback data parsing and building utilities."""

    def test_parse_callback_simple(self):
        """Simple callback should parse correctly."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data("menu_back")
        assert action == "menu_back"
        assert payload == ""

    def test_parse_callback_with_payload(self):
        """Callback with payload should parse correctly."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data("sell:pos_123:50")
        assert action == "sell"
        assert payload == "pos_123:50"

    def test_build_callback_simple(self):
        """Build simple callback data."""
        from tg_bot.ui.inline_buttons import build_callback_data

        data = build_callback_data("menu_back")
        assert data == "menu_back"

    def test_build_callback_with_args(self):
        """Build callback with arguments."""
        from tg_bot.ui.inline_buttons import build_callback_data

        data = build_callback_data("sell", "pos_123", 50)
        assert data == "sell:pos_123:50"

    def test_callback_data_max_length(self):
        """Callback data should not exceed Telegram's 64-byte limit."""
        from tg_bot.ui.inline_buttons import build_callback_data

        # Very long payload
        data = build_callback_data("action", "a" * 100)
        assert len(data.encode('utf-8')) <= 64


# =============================================================================
# Test Callback Router
# =============================================================================

class TestCallbackRouter:
    """Test callback routing functionality."""

    def test_register_handler(self):
        """Handler registration should work."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()

        async def my_handler(query, context, payload):
            pass

        router.register("test_action", my_handler)
        assert router.has_handler("test_action")

    def test_register_with_decorator(self):
        """Decorator registration should work."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()

        @router.handler("decorated_action")
        async def my_handler(query, context, payload):
            pass

        assert router.has_handler("decorated_action")

    @pytest.mark.asyncio
    async def test_route_callback(self):
        """Routing should call correct handler."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()
        called_with = []

        async def my_handler(query, context, payload):
            called_with.append(payload)
            return True

        router.register("test", my_handler)

        mock_query = MagicMock()
        mock_query.data = "test:some_payload"
        mock_context = MagicMock()

        result = await router.route(mock_query, mock_context)

        assert result is True
        assert called_with == ["some_payload"]

    @pytest.mark.asyncio
    async def test_route_unknown_callback(self):
        """Unknown callbacks should return False."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()

        mock_query = MagicMock()
        mock_query.data = "unknown_action"
        mock_context = MagicMock()

        result = await router.route(mock_query, mock_context)
        assert result is False
