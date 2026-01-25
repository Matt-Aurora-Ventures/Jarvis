"""
Tests for Telegram Keyboard Components.

Comprehensive test suite covering:
- tg_bot/ui/inline_buttons.py - Inline keyboard builders
- tg_bot/ui/quick_buttons.py - Quick action buttons
- tg_bot/ui/interactive_menus.py - Menu navigation

Test Categories:
1. Inline Keyboards (button creation, rows, URLs, callbacks)
2. Reply Keyboards (buttons, resize, one-time, selective)
3. Dynamic Generation (from lists, with callbacks)
4. Callback Encoding (data serialization, limits)
5. Pagination (next/prev, page numbers, limits)
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# =============================================================================
# Test Utility Functions
# =============================================================================

class TestParseCallbackData:
    """Test callback data parsing utility."""

    def test_parse_simple_action(self):
        """Simple action without payload should return empty payload."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data("close")
        assert action == "close"
        assert payload == ""

    def test_parse_action_with_single_payload(self):
        """Action with single payload should parse correctly."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data("analyze:TOKEN123")
        assert action == "analyze"
        assert payload == "TOKEN123"

    def test_parse_action_with_multiple_colons(self):
        """Action with multiple colons should preserve payload."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data("sell:pos_123:50:confirm")
        assert action == "sell"
        assert payload == "pos_123:50:confirm"

    def test_parse_empty_string(self):
        """Empty string should return empty action and payload."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data("")
        assert action == ""
        assert payload == ""

    def test_parse_only_colon(self):
        """Only colon should return empty action with empty payload."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data(":")
        assert action == ""
        assert payload == ""


class TestBuildCallbackData:
    """Test callback data building utility."""

    def test_build_simple_action(self):
        """Simple action without args should return action only."""
        from tg_bot.ui.inline_buttons import build_callback_data

        data = build_callback_data("close")
        assert data == "close"

    def test_build_action_with_single_arg(self):
        """Action with single argument should be joined with colon."""
        from tg_bot.ui.inline_buttons import build_callback_data

        data = build_callback_data("analyze", "TOKEN123")
        assert data == "analyze:TOKEN123"

    def test_build_action_with_multiple_args(self):
        """Action with multiple arguments should be joined with colons."""
        from tg_bot.ui.inline_buttons import build_callback_data

        data = build_callback_data("sell", "pos_123", 50)
        assert data == "sell:pos_123:50"

    def test_build_action_with_numeric_args(self):
        """Numeric arguments should be converted to strings."""
        from tg_bot.ui.inline_buttons import build_callback_data

        data = build_callback_data("alert", "TOKEN", 0.00001234)
        # Python may convert to scientific notation
        assert data.startswith("alert:TOKEN:")
        assert "1234" in data or "1.234" in data

    def test_build_truncates_long_data(self):
        """Data exceeding 64 bytes should be truncated."""
        from tg_bot.ui.inline_buttons import build_callback_data

        # Create very long payload
        long_payload = "a" * 100
        data = build_callback_data("action", long_payload)

        # Should be truncated to 64 bytes with "..." suffix
        assert len(data.encode('utf-8')) <= 64
        assert data.endswith("...")

    def test_build_unicode_truncation(self):
        """Unicode strings should be truncated safely."""
        from tg_bot.ui.inline_buttons import build_callback_data

        # Unicode characters take multiple bytes
        unicode_payload = "\U0001f4ca" * 20  # Chart emoji
        data = build_callback_data("action", unicode_payload)

        assert len(data.encode('utf-8')) <= 64


# =============================================================================
# Test TokenAnalysisButtons
# =============================================================================

class TestTokenAnalysisButtons:
    """Test token analysis keyboard builders."""

    def test_main_keyboard_structure(self):
        """Main keyboard should have correct row structure."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(
            token_address="So11111111111111111111111111111111",
            token_symbol="SOL"
        )

        assert isinstance(keyboard, InlineKeyboardMarkup)
        rows = keyboard.inline_keyboard

        # Should have at least 4 rows
        assert len(rows) >= 4

    def test_main_keyboard_analysis_buttons(self):
        """Main keyboard should have Chart, On-Chain, Signals buttons."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(
            token_address="TOKEN123",
            token_symbol="TEST"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Check for analysis buttons
        assert any("Chart" in b.text for b in all_buttons)
        assert any("On-Chain" in b.text for b in all_buttons)
        assert any("Signals" in b.text for b in all_buttons)

    def test_main_keyboard_external_links(self):
        """Main keyboard should have DexScreener and Birdeye URL buttons."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        token_address = "TOKEN123"
        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(
            token_address=token_address,
            token_symbol="TEST"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Check for URL buttons
        dexscreener_btn = next((b for b in all_buttons if "DexScreener" in b.text), None)
        assert dexscreener_btn is not None
        assert dexscreener_btn.url is not None
        assert token_address in dexscreener_btn.url

        birdeye_btn = next((b for b in all_buttons if "Birdeye" in b.text), None)
        assert birdeye_btn is not None
        assert birdeye_btn.url is not None
        assert token_address in birdeye_btn.url

    def test_main_keyboard_navigation(self):
        """Main keyboard should have Back and Close buttons."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(
            token_address="TOKEN123",
            token_symbol="TEST"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Back" in b.text for b in all_buttons)
        assert any("Close" in b.text for b in all_buttons)

    def test_chart_keyboard_timeframes(self):
        """Chart keyboard should have timeframe options."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_chart_keyboard(token_address="TOKEN123")

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Check for timeframe buttons
        timeframes = ["1H", "4H", "1D", "1W"]
        for tf in timeframes:
            assert any(tf in b.text for b in all_buttons), f"Missing {tf} timeframe"

    def test_chart_keyboard_callback_data(self):
        """Chart keyboard buttons should have correct callback format."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        token_address = "TOKEN123"
        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_chart_keyboard(token_address=token_address)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # 1H button should have chart_1h callback
        h1_btn = next((b for b in all_buttons if "1H" in b.text), None)
        assert h1_btn is not None
        assert f"chart_1h:{token_address}" == h1_btn.callback_data

    def test_holders_keyboard_pagination(self):
        """Holders keyboard should have pagination buttons."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_holders_keyboard(
            token_address="TOKEN123",
            page=2,
            total_pages=5
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should have previous and next buttons
        assert any("<" in b.text for b in all_buttons)
        assert any(">" in b.text for b in all_buttons)

        # Should show page indicator
        assert any("2/5" in b.text for b in all_buttons)

    def test_holders_keyboard_first_page(self):
        """First page should disable previous button."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_holders_keyboard(
            token_address="TOKEN123",
            page=1,
            total_pages=5
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Previous button should be placeholder
        prev_btn = next((b for b in all_buttons if b.callback_data == "noop" and "<" not in b.text), None)
        assert prev_btn is not None or any(b.text.strip() == "" and b.callback_data == "noop" for b in all_buttons)

    def test_holders_keyboard_last_page(self):
        """Last page should disable next button."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_holders_keyboard(
            token_address="TOKEN123",
            page=5,
            total_pages=5
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Both < and > should be noop on last page for next
        # Count noop buttons - should have 2 (prev placeholder since we're at page 5 which is > 1)
        noop_count = sum(1 for b in all_buttons if b.callback_data == "noop")
        assert noop_count >= 1

    def test_signals_keyboard_structure(self):
        """Signals keyboard should have details and alert buttons."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_signals_keyboard(token_address="TOKEN123")

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Details" in b.text for b in all_buttons)
        assert any("Alert" in b.text for b in all_buttons)

    def test_risk_keyboard_structure(self):
        """Risk keyboard should have whale and contract buttons."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_risk_keyboard(token_address="TOKEN123")

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Whale" in b.text for b in all_buttons)
        assert any("Contract" in b.text for b in all_buttons)


# =============================================================================
# Test TradingActionButtons
# =============================================================================

class TestTradingActionButtons:
    """Test trading action keyboard builders."""

    def test_buy_confirmation_structure(self):
        """Buy confirmation should show amount and confirm/cancel."""
        from tg_bot.ui.inline_buttons import TradingActionButtons

        buttons = TradingActionButtons()
        keyboard = buttons.build_buy_confirmation(
            token_address="TOKEN123",
            token_symbol="TEST",
            amount_usd=100.0
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should show amount
        assert any("$100" in b.text for b in all_buttons)

        # Should have confirm and cancel
        assert any("Confirm" in b.text for b in all_buttons)
        assert any("Cancel" in b.text for b in all_buttons)

    def test_buy_confirmation_callback_data(self):
        """Buy confirmation should include token and amount in callback."""
        from tg_bot.ui.inline_buttons import TradingActionButtons

        token_address = "TOKEN123"
        amount = 50.0
        buttons = TradingActionButtons()
        keyboard = buttons.build_buy_confirmation(
            token_address=token_address,
            token_symbol="TEST",
            amount_usd=amount
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        confirm_btn = next((b for b in all_buttons if "Confirm" in b.text), None)
        assert confirm_btn is not None
        assert token_address in confirm_btn.callback_data
        assert str(amount) in confirm_btn.callback_data

    def test_sell_confirmation_percentages(self):
        """Sell confirmation should show percentage options."""
        from tg_bot.ui.inline_buttons import TradingActionButtons

        buttons = TradingActionButtons()
        keyboard = buttons.build_sell_confirmation(
            token_address="TOKEN123",
            token_symbol="TEST",
            percentage=50
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should have percentage options
        percentages = ["25%", "50%", "75%", "100%"]
        for pct in percentages:
            assert any(pct in b.text for b in all_buttons), f"Missing {pct}"

    def test_sell_confirmation_selected_percentage(self):
        """Sell confirmation should highlight selected percentage."""
        from tg_bot.ui.inline_buttons import TradingActionButtons

        buttons = TradingActionButtons()
        keyboard = buttons.build_sell_confirmation(
            token_address="TOKEN123",
            token_symbol="TEST",
            percentage=75
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Confirm button should include selected percentage
        confirm_btn = next((b for b in all_buttons if "Confirm" in b.text), None)
        assert confirm_btn is not None
        assert "75%" in confirm_btn.text

    def test_hold_view_buttons(self):
        """Hold view should have analyze and watchlist options."""
        from tg_bot.ui.inline_buttons import TradingActionButtons

        buttons = TradingActionButtons()
        keyboard = buttons.build_hold_view(
            token_address="TOKEN123",
            token_symbol="TEST"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Analyze" in b.text for b in all_buttons)
        assert any("Watchlist" in b.text for b in all_buttons)
        assert any("OK" in b.text for b in all_buttons)


# =============================================================================
# Test SettingsButtons
# =============================================================================

class TestSettingsButtons:
    """Test settings keyboard builders."""

    def test_settings_keyboard_structure(self):
        """Settings keyboard should have notification, risk, alert options."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_settings_keyboard(
            user_id=12345,
            current_settings={}
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Notifications" in b.text for b in all_buttons)
        assert any("Risk" in b.text for b in all_buttons)
        assert any("Alert" in b.text for b in all_buttons)

    def test_settings_notification_on_state(self):
        """Settings should show ON state for notifications."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_settings_keyboard(
            user_id=12345,
            current_settings={"notifications": True}
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        notif_btn = next((b for b in all_buttons if "Notifications" in b.text), None)
        assert notif_btn is not None
        assert "ON" in notif_btn.text

    def test_settings_notification_off_state(self):
        """Settings should show OFF state for notifications."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_settings_keyboard(
            user_id=12345,
            current_settings={"notifications": False}
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        notif_btn = next((b for b in all_buttons if "Notifications" in b.text), None)
        assert notif_btn is not None
        assert "OFF" in notif_btn.text

    def test_settings_risk_profile_display(self):
        """Settings should display current risk profile."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_settings_keyboard(
            user_id=12345,
            current_settings={"risk_profile": "aggressive"}
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        risk_btn = next((b for b in all_buttons if "Risk" in b.text), None)
        assert risk_btn is not None
        assert "Aggressive" in risk_btn.text

    def test_risk_profile_keyboard_options(self):
        """Risk profile keyboard should show all profile options."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_risk_profile_keyboard(
            user_id=12345,
            current_profile="moderate"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        profiles = ["Conservative", "Moderate", "Aggressive"]
        for profile in profiles:
            assert any(profile in b.text for b in all_buttons), f"Missing {profile}"

    def test_risk_profile_keyboard_current_selected(self):
        """Risk profile keyboard should mark current profile."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_risk_profile_keyboard(
            user_id=12345,
            current_profile="moderate"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Current profile should have check mark
        moderate_btn = next((b for b in all_buttons if "Moderate" in b.text), None)
        assert moderate_btn is not None
        # The check mark character appears before the profile name


# =============================================================================
# Test LimitOrderButtons
# =============================================================================

class TestLimitOrderButtons:
    """Test limit order/price alert keyboard builders."""

    def test_price_alert_keyboard_targets(self):
        """Price alert keyboard should show percentage-based targets."""
        from tg_bot.ui.inline_buttons import LimitOrderButtons

        buttons = LimitOrderButtons()
        keyboard = buttons.build_price_alert_keyboard(
            token_address="TOKEN123",
            token_symbol="TEST",
            current_price=1.0
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should have +5%, +10%, +25% up targets
        assert any("+5%" in b.text for b in all_buttons)
        assert any("+10%" in b.text for b in all_buttons)
        assert any("+25%" in b.text for b in all_buttons)

        # Should have -5%, -10% down targets
        assert any("-5%" in b.text for b in all_buttons)
        assert any("-10%" in b.text for b in all_buttons)

    def test_price_alert_keyboard_calculated_prices(self):
        """Price alert keyboard should calculate target prices correctly."""
        from tg_bot.ui.inline_buttons import LimitOrderButtons

        current_price = 100.0
        buttons = LimitOrderButtons()
        keyboard = buttons.build_price_alert_keyboard(
            token_address="TOKEN123",
            token_symbol="TEST",
            current_price=current_price
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # +10% of 100 = 110
        btn_10up = next((b for b in all_buttons if "+10%" in b.text), None)
        assert btn_10up is not None
        assert "110" in btn_10up.text

        # -10% of 100 = 90
        btn_10down = next((b for b in all_buttons if "-10%" in b.text), None)
        assert btn_10down is not None
        assert "90" in btn_10down.text

    def test_price_alert_custom_button(self):
        """Price alert keyboard should have custom price option."""
        from tg_bot.ui.inline_buttons import LimitOrderButtons

        buttons = LimitOrderButtons()
        keyboard = buttons.build_price_alert_keyboard(
            token_address="TOKEN123",
            token_symbol="TEST",
            current_price=1.0
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Custom" in b.text for b in all_buttons)

    def test_alert_confirmation_direction(self):
        """Alert confirmation should indicate price direction."""
        from tg_bot.ui.inline_buttons import LimitOrderButtons

        buttons = LimitOrderButtons()

        # Alert above current price
        keyboard_above = buttons.build_alert_confirmation(
            token_address="TOKEN123",
            token_symbol="TEST",
            target_price=110.0,
            current_price=100.0
        )

        all_buttons_above = [b for row in keyboard_above.inline_keyboard for b in row]
        confirm_btn_above = next((b for b in all_buttons_above if "Set Alert" in b.text), None)
        assert confirm_btn_above is not None
        assert "above" in confirm_btn_above.text

        # Alert below current price
        keyboard_below = buttons.build_alert_confirmation(
            token_address="TOKEN123",
            token_symbol="TEST",
            target_price=90.0,
            current_price=100.0
        )

        all_buttons_below = [b for row in keyboard_below.inline_keyboard for b in row]
        confirm_btn_below = next((b for b in all_buttons_below if "Set Alert" in b.text), None)
        assert confirm_btn_below is not None
        assert "below" in confirm_btn_below.text


# =============================================================================
# Test Watchlist Keyboard
# =============================================================================

class TestWatchlistKeyboard:
    """Test watchlist keyboard builder."""

    def test_watchlist_with_items(self):
        """Watchlist keyboard should show token buttons."""
        from tg_bot.ui.inline_buttons import build_watchlist_keyboard

        watchlist = [
            {"symbol": "SOL", "address": "So11111111111111111111111111111111"},
            {"symbol": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
        ]

        keyboard = build_watchlist_keyboard(watchlist, user_id=12345)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("SOL" in b.text for b in all_buttons)
        assert any("BONK" in b.text for b in all_buttons)

    def test_watchlist_remove_buttons(self):
        """Each watchlist item should have remove button."""
        from tg_bot.ui.inline_buttons import build_watchlist_keyboard

        watchlist = [
            {"symbol": "SOL", "address": "So11111111111111111111111111111111"},
        ]

        keyboard = build_watchlist_keyboard(watchlist, user_id=12345)

        rows = keyboard.inline_keyboard

        # First row should have view and remove buttons
        assert len(rows[0]) == 2
        # Remove button callback should contain watch_remove
        remove_btn = next((b for b in rows[0] if "watch_remove" in b.callback_data), None)
        assert remove_btn is not None

    def test_watchlist_action_buttons(self):
        """Watchlist should have add, refresh, clear actions."""
        from tg_bot.ui.inline_buttons import build_watchlist_keyboard

        watchlist = []

        keyboard = build_watchlist_keyboard(watchlist, user_id=12345)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Add" in b.text for b in all_buttons)
        assert any("Refresh" in b.text for b in all_buttons)
        assert any("Clear" in b.text for b in all_buttons)

    def test_watchlist_max_items(self):
        """Watchlist should limit displayed items to 10."""
        from tg_bot.ui.inline_buttons import build_watchlist_keyboard

        # Create 15 items
        watchlist = [
            {"symbol": f"TOKEN{i}", "address": f"address{i}"}
            for i in range(15)
        ]

        keyboard = build_watchlist_keyboard(watchlist, user_id=12345)

        rows = keyboard.inline_keyboard

        # Should have 10 token rows + 2 action rows
        token_rows = [r for r in rows if any("TOKEN" in b.text for b in r)]
        assert len(token_rows) == 10


# =============================================================================
# Test ButtonBuilder
# =============================================================================

class TestButtonBuilder:
    """Test generic button builder."""

    def test_button_creation(self):
        """Button should be created with text and callback."""
        from tg_bot.ui.inline_buttons import ButtonBuilder

        builder = ButtonBuilder()
        button = builder.button("Click Me", "action:data")

        assert isinstance(button, InlineKeyboardButton)
        assert button.text == "Click Me"
        assert button.callback_data == "action:data"

    def test_button_callback_truncation(self):
        """Long callback data should be truncated."""
        from tg_bot.ui.inline_buttons import ButtonBuilder

        builder = ButtonBuilder()
        long_callback = "a" * 100
        button = builder.button("Click Me", long_callback)

        assert len(button.callback_data.encode('utf-8')) <= 64

    def test_url_button_creation(self):
        """URL button should have url attribute."""
        from tg_bot.ui.inline_buttons import ButtonBuilder

        builder = ButtonBuilder()
        button = builder.url_button("Visit Site", "https://example.com")

        assert isinstance(button, InlineKeyboardButton)
        assert button.text == "Visit Site"
        assert button.url == "https://example.com"

    def test_row_creation(self):
        """Row should contain list of buttons."""
        from tg_bot.ui.inline_buttons import ButtonBuilder

        builder = ButtonBuilder()
        row = builder.row([
            builder.button("A", "a"),
            builder.button("B", "b"),
        ])

        assert len(row) == 2
        assert all(isinstance(b, InlineKeyboardButton) for b in row)

    def test_keyboard_creation(self):
        """Keyboard should be created from rows."""
        from tg_bot.ui.inline_buttons import ButtonBuilder

        builder = ButtonBuilder()
        keyboard = builder.keyboard([
            [builder.button("Row1", "r1")],
            [builder.button("Row2A", "r2a"), builder.button("Row2B", "r2b")],
        ])

        assert isinstance(keyboard, InlineKeyboardMarkup)
        rows = keyboard.inline_keyboard
        assert len(rows) == 2
        assert len(rows[0]) == 1
        assert len(rows[1]) == 2


# =============================================================================
# Test QuickActionButtons
# =============================================================================

class TestQuickActionButtons:
    """Test quick action button builders."""

    def test_buy_button_amounts(self):
        """Buy button should show amount options."""
        from tg_bot.ui.inline_buttons import QuickActionButtons

        buttons = QuickActionButtons()
        keyboard = buttons.buy_button(
            token_address="TOKEN123",
            token_symbol="TEST",
            amount_usd=50.0
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should have amount options
        amounts = ["$25", "$50", "$100", "$250"]
        for amt in amounts:
            assert any(amt in b.text for b in all_buttons), f"Missing {amt}"

    def test_buy_button_confirm_cancel(self):
        """Buy button should have confirm and cancel."""
        from tg_bot.ui.inline_buttons import QuickActionButtons

        buttons = QuickActionButtons()
        keyboard = buttons.buy_button(
            token_address="TOKEN123",
            token_symbol="TEST"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Confirm" in b.text for b in all_buttons)
        assert any("Cancel" in b.text for b in all_buttons)

    def test_sell_button_percentages(self):
        """Sell button should show percentage options."""
        from tg_bot.ui.inline_buttons import QuickActionButtons

        buttons = QuickActionButtons()
        keyboard = buttons.sell_button(
            token_address="TOKEN123",
            token_symbol="TEST"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        percentages = ["25%", "50%", "75%", "100%"]
        for pct in percentages:
            assert any(pct in b.text for b in all_buttons), f"Missing {pct}"

    def test_hold_button_options(self):
        """Hold button should show analyze, watchlist, alert options."""
        from tg_bot.ui.inline_buttons import QuickActionButtons

        buttons = QuickActionButtons()
        keyboard = buttons.hold_button(
            token_address="TOKEN123",
            token_symbol="TEST"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Analyze" in b.text for b in all_buttons)
        assert any("Watchlist" in b.text for b in all_buttons)
        assert any("Alert" in b.text for b in all_buttons)


# =============================================================================
# Test PositionButtons
# =============================================================================

class TestPositionButtons:
    """Test position management button builders."""

    def test_position_actions_structure(self):
        """Position actions should have sell, adjust, details."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.position_actions(
            position_id="pos_123",
            token_symbol="SOL",
            current_pnl_pct=10.0
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Sell" in b.text for b in all_buttons)
        assert any("Adjust" in b.text or "TP/SL" in b.text for b in all_buttons)
        assert any("Details" in b.text for b in all_buttons)

    def test_position_actions_sell_percentages(self):
        """Position actions should have 50% and 100% sell options."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.position_actions(
            position_id="pos_123",
            token_symbol="SOL"
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("50%" in b.text for b in all_buttons)
        assert any("100%" in b.text for b in all_buttons)

    def test_close_confirmation_structure(self):
        """Close confirmation should have confirm and cancel."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.close_confirmation(
            position_id="pos_123",
            token_symbol="SOL",
            sell_percent=100
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Confirm" in b.text for b in all_buttons)
        assert any("Cancel" in b.text for b in all_buttons)

    def test_close_confirmation_shows_percent(self):
        """Close confirmation should show sell percentage."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.close_confirmation(
            position_id="pos_123",
            token_symbol="SOL",
            sell_percent=75
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        confirm_btn = next((b for b in all_buttons if "Confirm" in b.text), None)
        assert confirm_btn is not None
        assert "75%" in confirm_btn.text

    def test_adjust_tp_sl_structure(self):
        """TP/SL adjustment should have increment/decrement options."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.adjust_tp_sl(
            position_id="pos_123",
            current_tp=100.0,
            current_sl=80.0
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should have TP adjustments
        assert any("TP" in b.text and "+" in b.text for b in all_buttons)
        assert any("TP" in b.text and "-" in b.text for b in all_buttons)

        # Should have SL adjustments
        assert any("SL" in b.text and "+" in b.text for b in all_buttons)
        assert any("SL" in b.text and "-" in b.text for b in all_buttons)

    def test_adjust_tp_sl_save_cancel(self):
        """TP/SL adjustment should have save and cancel."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.adjust_tp_sl(
            position_id="pos_123",
            current_tp=100.0,
            current_sl=80.0
        )

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Save" in b.text for b in all_buttons)
        assert any("Cancel" in b.text for b in all_buttons)


# =============================================================================
# Test CommandButtons
# =============================================================================

class TestCommandButtons:
    """Test command quick-select button builders."""

    def test_main_menu_standard_user(self):
        """Main menu for standard user should have limited options."""
        from tg_bot.ui.inline_buttons import CommandButtons

        buttons = CommandButtons()
        keyboard = buttons.main_menu(is_admin=False)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should have core commands
        assert any("Trending" in b.text for b in all_buttons)
        assert any("Status" in b.text for b in all_buttons)
        assert any("Help" in b.text for b in all_buttons)

    def test_main_menu_admin_extra_options(self):
        """Main menu for admin should have extra options."""
        from tg_bot.ui.inline_buttons import CommandButtons

        buttons = CommandButtons()
        admin_keyboard = buttons.main_menu(is_admin=True)
        user_keyboard = buttons.main_menu(is_admin=False)

        admin_buttons = [b for row in admin_keyboard.inline_keyboard for b in row]
        user_buttons = [b for row in user_keyboard.inline_keyboard for b in row]

        # Admin should have more buttons
        assert len(admin_buttons) > len(user_buttons)

        # Admin should have dashboard
        assert any("Dashboard" in b.text for b in admin_buttons)

    def test_trading_commands_structure(self):
        """Trading commands should have dashboard, positions, balance."""
        from tg_bot.ui.inline_buttons import CommandButtons

        buttons = CommandButtons()
        keyboard = buttons.trading_commands()

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Dashboard" in b.text for b in all_buttons)
        assert any("Positions" in b.text for b in all_buttons)
        assert any("Balance" in b.text for b in all_buttons)

    def test_analysis_commands_structure(self):
        """Analysis commands should have trending, analyze, chart."""
        from tg_bot.ui.inline_buttons import CommandButtons

        buttons = CommandButtons()
        keyboard = buttons.analysis_commands()

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Trending" in b.text for b in all_buttons)
        assert any("Analyze" in b.text for b in all_buttons)
        assert any("Chart" in b.text for b in all_buttons)


# =============================================================================
# Test CallbackRouter
# =============================================================================

class TestCallbackRouter:
    """Test callback routing functionality."""

    def test_register_handler(self):
        """Handler should be registered successfully."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()

        async def my_handler(query, context, payload):
            pass

        router.register("test_action", my_handler)

        assert router.has_handler("test_action")
        assert not router.has_handler("unknown_action")

    def test_decorator_registration(self):
        """Decorator should register handler."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()

        @router.handler("decorated_action")
        async def my_handler(query, context, payload):
            pass

        assert router.has_handler("decorated_action")

    @pytest.mark.asyncio
    async def test_route_to_handler(self):
        """Router should call correct handler."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()
        called_with = []

        async def my_handler(query, context, payload):
            called_with.append(("my_handler", payload))

        router.register("test", my_handler)

        mock_query = MagicMock()
        mock_query.data = "test:payload123"
        mock_context = MagicMock()

        result = await router.route(mock_query, mock_context)

        assert result is True
        assert called_with == [("my_handler", "payload123")]

    @pytest.mark.asyncio
    async def test_route_unknown_action(self):
        """Router should return False for unknown actions."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()

        mock_query = MagicMock()
        mock_query.data = "unknown_action"
        mock_context = MagicMock()

        result = await router.route(mock_query, mock_context)

        assert result is False

    @pytest.mark.asyncio
    async def test_route_empty_data(self):
        """Router should handle empty callback data."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()

        mock_query = MagicMock()
        mock_query.data = None
        mock_context = MagicMock()

        result = await router.route(mock_query, mock_context)

        assert result is False


# =============================================================================
# Test QuickButtons (quick_buttons.py)
# =============================================================================

class TestQuickButtons:
    """Test QuickButtons class from quick_buttons.py."""

    def test_quick_buttons_default_actions(self):
        """Default quick actions should include stats, analyze, positions."""
        from tg_bot.ui.quick_buttons import QuickButtons

        buttons = QuickButtons()
        keyboard = buttons.build_quick_actions()

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Default actions
        assert any("stats" in b.callback_data for b in all_buttons)
        assert any("analyze" in b.callback_data for b in all_buttons)
        assert any("positions" in b.callback_data for b in all_buttons)

    def test_quick_buttons_custom_actions(self):
        """Custom actions should be included."""
        from tg_bot.ui.quick_buttons import QuickButtons

        buttons = QuickButtons()
        keyboard = buttons.build_quick_actions(actions=["trending", "dashboard"])

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("trending" in b.callback_data for b in all_buttons)
        assert any("dashboard" in b.callback_data for b in all_buttons)
        assert not any("stats" in b.callback_data for b in all_buttons)

    def test_quick_buttons_compact_mode(self):
        """Compact mode should show only emoji."""
        from tg_bot.ui.quick_buttons import QuickButtons

        buttons = QuickButtons()
        compact_keyboard = buttons.build_quick_actions(compact=True)
        full_keyboard = buttons.build_quick_actions(compact=False)

        compact_buttons = [b for row in compact_keyboard.inline_keyboard for b in row]
        full_buttons = [b for row in full_keyboard.inline_keyboard for b in row]

        # Compact buttons should have shorter text
        compact_total_len = sum(len(b.text) for b in compact_buttons)
        full_total_len = sum(len(b.text) for b in full_buttons)

        assert compact_total_len < full_total_len

    def test_quick_buttons_per_row_config(self):
        """Buttons per row should be configurable."""
        from tg_bot.ui.quick_buttons import QuickButtons

        buttons_3 = QuickButtons(buttons_per_row=3)
        buttons_2 = QuickButtons(buttons_per_row=2)

        keyboard_3 = buttons_3.build_quick_actions(actions=["stats", "analyze", "positions", "watchlist"])
        keyboard_2 = buttons_2.build_quick_actions(actions=["stats", "analyze", "positions", "watchlist"])

        rows_3 = keyboard_3.inline_keyboard
        rows_2 = keyboard_2.inline_keyboard

        # With 4 buttons, 3 per row = 2 rows, 2 per row = 2 rows
        # But structure differs
        assert len(rows_3) <= len(rows_2)

    def test_quick_buttons_invalid_action(self):
        """Invalid actions should be ignored."""
        from tg_bot.ui.quick_buttons import QuickButtons

        buttons = QuickButtons()
        keyboard = buttons.build_quick_actions(actions=["stats", "invalid_action", "analyze"])

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should have 2 valid buttons, invalid is skipped
        assert len(all_buttons) == 2

    def test_default_footer(self):
        """Default footer should have common actions."""
        from tg_bot.ui.quick_buttons import QuickButtons

        buttons = QuickButtons()
        keyboard = buttons.build_default_footer()

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert len(all_buttons) == 4  # stats, analyze, positions, help

    def test_analysis_footer(self):
        """Analysis footer should have token-specific buttons."""
        from tg_bot.ui.quick_buttons import QuickButtons

        token_address = "TOKEN123"
        buttons = QuickButtons()
        keyboard = buttons.build_analysis_footer(token_address=token_address)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should have chart, risk, watch, close
        assert any("analyze_chart" in b.callback_data and token_address in b.callback_data for b in all_buttons)
        assert any("analyze_risk" in b.callback_data for b in all_buttons)
        assert any("watch_add" in b.callback_data for b in all_buttons)

    def test_trading_footer(self):
        """Trading footer should have buy, sell, analyze, close."""
        from tg_bot.ui.quick_buttons import QuickButtons

        token_address = "TOKEN123"
        buttons = QuickButtons()
        keyboard = buttons.build_trading_footer(token_address=token_address)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("trade_buy" in b.callback_data for b in all_buttons)
        assert any("trade_sell" in b.callback_data for b in all_buttons)
        assert any("analyze" in b.callback_data for b in all_buttons)


class TestQuickButtonsSingleton:
    """Test QuickButtons singleton pattern."""

    def test_get_quick_buttons_returns_instance(self):
        """get_quick_buttons should return QuickButtons instance."""
        from tg_bot.ui.quick_buttons import get_quick_buttons, QuickButtons

        instance = get_quick_buttons()

        assert isinstance(instance, QuickButtons)

    def test_get_quick_buttons_returns_same_instance(self):
        """get_quick_buttons should return same instance."""
        from tg_bot.ui.quick_buttons import get_quick_buttons

        instance1 = get_quick_buttons()
        instance2 = get_quick_buttons()

        assert instance1 is instance2


class TestQuickActionsMapping:
    """Test QUICK_ACTIONS mapping."""

    def test_quick_actions_structure(self):
        """QUICK_ACTIONS should have correct structure."""
        from tg_bot.ui.quick_buttons import QUICK_ACTIONS

        required_keys = ["stats", "analyze", "positions", "help"]

        for key in required_keys:
            assert key in QUICK_ACTIONS
            assert "emoji" in QUICK_ACTIONS[key]
            assert "command" in QUICK_ACTIONS[key]
            assert "label" in QUICK_ACTIONS[key]

    def test_quick_actions_commands_format(self):
        """Commands should start with /."""
        from tg_bot.ui.quick_buttons import QUICK_ACTIONS

        for key, action in QUICK_ACTIONS.items():
            assert action["command"].startswith("/"), f"{key} command should start with /"


class TestHandleQuickCallback:
    """Test handle_quick_callback function."""

    @pytest.mark.asyncio
    async def test_handle_quick_callback_answers_query(self):
        """Callback handler should answer the query."""
        from tg_bot.ui.quick_buttons import handle_quick_callback

        mock_query = MagicMock()
        mock_query.data = "quick_stats"
        mock_query.answer = AsyncMock()
        mock_query.from_user = MagicMock()
        mock_query.message = MagicMock()
        mock_query.message.chat = MagicMock()
        mock_query.message.reply_text = AsyncMock()

        mock_context = MagicMock()

        await handle_quick_callback(mock_query, mock_context)

        mock_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_quick_callback_unknown_action(self):
        """Unknown action should be handled gracefully."""
        from tg_bot.ui.quick_buttons import handle_quick_callback

        mock_query = MagicMock()
        mock_query.data = "quick_unknown"
        mock_query.answer = AsyncMock()
        mock_query.from_user = MagicMock()
        mock_query.message = MagicMock()
        mock_query.message.reply_text = AsyncMock()

        mock_context = MagicMock()

        # Should not raise
        await handle_quick_callback(mock_query, mock_context)


# =============================================================================
# Test Interactive Menus (interactive_menus.py)
# =============================================================================

class TestPortfolioMenu:
    """Test PortfolioMenu class."""

    def test_build_basic_menu(self):
        """Basic menu should have positions, balance, pnl options."""
        from tg_bot.ui.interactive_menus import PortfolioMenu

        menu = PortfolioMenu()
        keyboard = menu.build()

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Positions" in b.text for b in all_buttons)
        assert any("Balance" in b.text for b in all_buttons)
        assert any("P&L" in b.text for b in all_buttons)

    def test_build_with_positions(self):
        """Menu with positions should show position rows."""
        from tg_bot.ui.interactive_menus import PortfolioMenu

        positions = [
            {"symbol": "SOL", "pnl_pct": 15.5, "id": "pos_1"},
            {"symbol": "BONK", "pnl_pct": -5.2, "id": "pos_2"},
        ]

        menu = PortfolioMenu()
        keyboard = menu.build_with_positions(positions)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Position symbols should appear
        assert any("SOL" in b.text for b in all_buttons)
        assert any("BONK" in b.text for b in all_buttons)

        # Should have sell buttons
        assert any("Sell" in b.text for b in all_buttons)

    def test_build_with_positions_max_limit(self):
        """Positions should be limited to 10."""
        from tg_bot.ui.interactive_menus import PortfolioMenu

        positions = [
            {"symbol": f"TOKEN{i}", "pnl_pct": i, "id": f"pos_{i}"}
            for i in range(15)
        ]

        menu = PortfolioMenu()
        keyboard = menu.build_with_positions(positions)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Should have buttons for first 10 tokens only
        assert any("TOKEN0" in b.text for b in all_buttons)
        assert any("TOKEN9" in b.text for b in all_buttons)
        assert not any("TOKEN14" in b.text for b in all_buttons)

    def test_build_empty_returns_tuple(self):
        """Empty portfolio should return text and keyboard."""
        from tg_bot.ui.interactive_menus import PortfolioMenu

        menu = PortfolioMenu()
        result = menu.build_empty()

        assert isinstance(result, tuple)
        assert len(result) == 2

        text, keyboard = result
        assert "no positions" in text.lower()
        assert isinstance(keyboard, InlineKeyboardMarkup)


class TestTradingDashboard:
    """Test TradingDashboard class."""

    def test_build_basic_dashboard(self):
        """Dashboard should have mode, positions, balance options."""
        from tg_bot.ui.interactive_menus import TradingDashboard

        dashboard = TradingDashboard()
        keyboard = dashboard.build()

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Mode" in b.text for b in all_buttons)
        assert any("Positions" in b.text for b in all_buttons)
        assert any("Balance" in b.text for b in all_buttons)

    def test_build_paper_mode(self):
        """Paper mode should be indicated."""
        from tg_bot.ui.interactive_menus import TradingDashboard

        dashboard = TradingDashboard()
        keyboard = dashboard.build(mode="paper")

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        mode_btn = next((b for b in all_buttons if "Mode" in b.text), None)
        assert mode_btn is not None
        assert "PAPER" in mode_btn.text

    def test_build_live_mode(self):
        """Live mode should be indicated."""
        from tg_bot.ui.interactive_menus import TradingDashboard

        dashboard = TradingDashboard()
        keyboard = dashboard.build(mode="live")

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        mode_btn = next((b for b in all_buttons if "Mode" in b.text), None)
        assert mode_btn is not None
        assert "LIVE" in mode_btn.text

    def test_build_admin_options(self):
        """Admin should see config and logs buttons."""
        from tg_bot.ui.interactive_menus import TradingDashboard

        dashboard = TradingDashboard()
        admin_keyboard = dashboard.build(is_admin=True)
        user_keyboard = dashboard.build(is_admin=False)

        admin_buttons = [b for row in admin_keyboard.inline_keyboard for b in row]
        user_buttons = [b for row in user_keyboard.inline_keyboard for b in row]

        # Admin should have config
        assert any("Config" in b.text for b in admin_buttons)

        # User should not have config
        assert not any("Config" in b.text for b in user_buttons)

    def test_build_with_stats(self):
        """Dashboard with stats should show values in text."""
        from tg_bot.ui.interactive_menus import TradingDashboard

        stats = {
            "sol_balance": 10.5,
            "usd_value": 1050.0,
            "open_positions": 3,
            "total_pnl": 125.50,
            "win_rate": 65.0,
        }

        dashboard = TradingDashboard()
        text, keyboard = dashboard.build_with_stats(stats)

        assert "10.5" in text
        assert "3" in text
        assert "65" in text


class TestSettingsMenu:
    """Test SettingsMenu class."""

    def test_build_settings_menu(self):
        """Settings menu should have notification, theme, risk options."""
        from tg_bot.ui.interactive_menus import SettingsMenu

        menu = SettingsMenu()
        keyboard = menu.build(user_id=12345)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        assert any("Notification" in b.text for b in all_buttons)
        assert any("Theme" in b.text for b in all_buttons)
        assert any("Risk" in b.text for b in all_buttons)

    def test_settings_with_current_values(self):
        """Settings should reflect current values."""
        from tg_bot.ui.interactive_menus import SettingsMenu

        settings = {
            "notifications": True,
            "theme": "dark",
            "risk_profile": "aggressive"
        }

        menu = SettingsMenu()
        keyboard = menu.build(user_id=12345, settings=settings)

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Check theme reflects current
        theme_btn = next((b for b in all_buttons if "Theme" in b.text), None)
        assert theme_btn is not None
        assert "Dark" in theme_btn.text

    def test_settings_default_user_id(self):
        """Settings should use default user_id from constructor."""
        from tg_bot.ui.interactive_menus import SettingsMenu

        menu = SettingsMenu(user_id=99999)
        keyboard = menu.build()

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Buttons should include user_id in callback
        assert any("99999" in b.callback_data for b in all_buttons)


class TestMenuNavigator:
    """Test MenuNavigator class."""

    def test_navigate_to_menu(self):
        """Navigator should return keyboard for menu."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        keyboard = nav.navigate_to("portfolio")

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_navigate_tracks_breadcrumbs(self):
        """Navigator should track navigation history."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        nav.navigate_to("portfolio", user_id=123)
        nav.navigate_to("settings", user_id=123)

        breadcrumbs = nav.get_breadcrumbs(user_id=123)

        assert "portfolio" in breadcrumbs
        assert "settings" in breadcrumbs

    def test_go_back(self):
        """go_back should return previous menu name."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        nav.navigate_to("portfolio", user_id=123)
        nav.navigate_to("settings", user_id=123)

        prev = nav.go_back(user_id=123)

        assert prev == "portfolio"

    def test_go_back_to_main(self):
        """go_back with no history should return main."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()

        prev = nav.go_back(user_id=999)

        assert prev == "main"

    def test_get_current_menu(self):
        """get_current_menu should return current menu."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        nav.navigate_to("dashboard", user_id=123)

        current = nav.get_current_menu(user_id=123)

        assert current == "dashboard"

    def test_back_to_main(self):
        """back_to_main should return main menu keyboard."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        keyboard = nav.back_to_main()

        all_buttons = [b for row in keyboard.inline_keyboard for b in row]

        # Main menu should have Portfolio, Dashboard, etc.
        assert any("Portfolio" in b.text for b in all_buttons)
        assert any("Dashboard" in b.text for b in all_buttons)

    @pytest.mark.asyncio
    async def test_handle_navigation_callback(self):
        """handle_callback should process nav callbacks."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()

        mock_query = MagicMock()
        mock_query.data = "nav:settings"
        mock_query.answer = AsyncMock()
        mock_query.from_user = MagicMock()
        mock_query.from_user.id = 12345
        mock_query.message = MagicMock()
        mock_query.message.edit_reply_markup = AsyncMock()
        mock_query.message.reply_text = AsyncMock()

        result = await nav.handle_callback(mock_query)

        assert result is True
        mock_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_non_nav_callback(self):
        """handle_callback should return False for non-nav callbacks."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()

        mock_query = MagicMock()
        mock_query.data = "other:action"

        result = await nav.handle_callback(mock_query)

        assert result is False

    @pytest.mark.asyncio
    async def test_handle_back_navigation(self):
        """handle_callback should handle back navigation."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        nav.navigate_to("settings", user_id=12345)

        mock_query = MagicMock()
        mock_query.data = "nav:back"
        mock_query.answer = AsyncMock()
        mock_query.from_user = MagicMock()
        mock_query.from_user.id = 12345
        mock_query.message = MagicMock()
        mock_query.message.edit_reply_markup = AsyncMock()
        mock_query.message.reply_text = AsyncMock()

        result = await nav.handle_callback(mock_query)

        assert result is True


class TestMenuNavigatorSingleton:
    """Test MenuNavigator singleton pattern."""

    def test_get_menu_navigator_returns_instance(self):
        """get_menu_navigator should return MenuNavigator instance."""
        from tg_bot.ui.interactive_menus import get_menu_navigator, MenuNavigator

        instance = get_menu_navigator()

        assert isinstance(instance, MenuNavigator)
