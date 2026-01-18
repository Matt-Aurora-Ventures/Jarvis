"""
Tests for inline button UI components.

Tests cover:
- TokenAnalysisButtons - drill-down analysis buttons
- TradingActionButtons - BUY/HOLD/SELL confirmation
- SettingsButtons - user preferences
- LimitOrderButtons - price alert buttons
- Callback data format and parsing
"""

import pytest
from unittest.mock import MagicMock


# =============================================================================
# Test TokenAnalysisButtons
# =============================================================================

class TestTokenAnalysisButtons:
    """Test token analysis button templates."""

    def test_main_keyboard_structure(self):
        """Main keyboard should have proper row structure."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard("test_address", "TEST")

        assert keyboard.inline_keyboard is not None
        assert len(keyboard.inline_keyboard) >= 2  # At least 2 rows

    def test_main_keyboard_has_required_buttons(self):
        """Main keyboard should have all required drill-down buttons."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard("test_address", "TEST")

        all_texts = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text.lower())

        # Required buttons (partial match for emoji variants)
        required = ["chart", "chain", "signal", "risk"]
        for req in required:
            assert any(req in text for text in all_texts), f"Missing {req} button"

    def test_callback_data_includes_address(self):
        """Callback data should include token address."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        test_address = "So11111111111111111111111111111111111111112"
        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(test_address, "SOL")

        # Check that at least one button has the address in callback_data
        has_address = False
        for row in keyboard.inline_keyboard:
            for btn in row:
                if btn.callback_data and test_address in btn.callback_data:
                    has_address = True
                    break

        assert has_address, "No button contains token address in callback_data"

    def test_dexscreener_url_button(self):
        """Should have DexScreener URL button."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        test_address = "So11111111111111111111111111111111111111112"
        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(test_address, "SOL")

        has_dexscreener = False
        for row in keyboard.inline_keyboard:
            for btn in row:
                if btn.url and "dexscreener" in btn.url.lower():
                    has_dexscreener = True
                    assert test_address in btn.url
                    break

        assert has_dexscreener, "Missing DexScreener URL button"


# =============================================================================
# Test TradingActionButtons
# =============================================================================

class TestTradingActionButtons:
    """Test trading action confirmation buttons."""

    def test_buy_confirmation_keyboard(self):
        """Buy confirmation should have confirm/cancel buttons."""
        from tg_bot.ui.inline_buttons import TradingActionButtons

        buttons = TradingActionButtons()
        keyboard = buttons.build_buy_confirmation("test_address", "TEST", 100.0)

        all_texts = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text.lower())

        assert any("confirm" in text or "yes" in text for text in all_texts)
        assert any("cancel" in text or "no" in text for text in all_texts)

    def test_sell_confirmation_keyboard(self):
        """Sell confirmation should have confirm/cancel buttons."""
        from tg_bot.ui.inline_buttons import TradingActionButtons

        buttons = TradingActionButtons()
        keyboard = buttons.build_sell_confirmation("test_address", "TEST", 50)  # 50%

        all_texts = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text.lower())

        assert any("confirm" in text or "yes" in text for text in all_texts)
        assert any("cancel" in text or "no" in text for text in all_texts)

    def test_hold_keyboard_has_close_button(self):
        """Hold notification should have close button."""
        from tg_bot.ui.inline_buttons import TradingActionButtons

        buttons = TradingActionButtons()
        keyboard = buttons.build_hold_view("test_address", "TEST")

        all_texts = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text.lower())

        assert any("close" in text or "dismiss" in text or "ok" in text for text in all_texts)


# =============================================================================
# Test SettingsButtons
# =============================================================================

class TestSettingsButtons:
    """Test user preference settings buttons."""

    def test_settings_keyboard_has_notification_toggle(self):
        """Settings should have notification toggle."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_settings_keyboard(user_id=12345, current_settings={})

        all_texts = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text.lower())

        # Should have some kind of notification/alert toggle
        assert any("notif" in text or "alert" in text for text in all_texts)

    def test_settings_keyboard_has_risk_profile(self):
        """Settings should have risk profile option."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_settings_keyboard(user_id=12345, current_settings={})

        all_texts = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text.lower())

        # Should have risk-related setting
        assert any("risk" in text or "profile" in text for text in all_texts)


# =============================================================================
# Test LimitOrderButtons
# =============================================================================

class TestLimitOrderButtons:
    """Test price alert / limit order buttons."""

    def test_price_alert_keyboard(self):
        """Price alert keyboard should have common price targets."""
        from tg_bot.ui.inline_buttons import LimitOrderButtons

        buttons = LimitOrderButtons()
        keyboard = buttons.build_price_alert_keyboard("test_address", "TEST", current_price=100.0)

        all_texts = []
        for row in keyboard.inline_keyboard:
            for btn in row:
                all_texts.append(btn.text.lower())

        # Should have percentage-based price targets
        assert len(all_texts) >= 3  # At least a few options

    def test_price_alert_callback_format(self):
        """Price alert callbacks should have parseable format."""
        from tg_bot.ui.inline_buttons import LimitOrderButtons

        buttons = LimitOrderButtons()
        keyboard = buttons.build_price_alert_keyboard("test_address", "TEST", current_price=100.0)

        for row in keyboard.inline_keyboard:
            for btn in row:
                if btn.callback_data and "alert" in btn.callback_data:
                    # Should be parseable format like "alert:address:price" or similar
                    parts = btn.callback_data.split(":")
                    assert len(parts) >= 2


# =============================================================================
# Test Callback Parsing
# =============================================================================

class TestCallbackParsing:
    """Test callback data parsing utilities."""

    def test_parse_analyze_callback(self):
        """Should parse analyze callback data correctly."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, token_address = parse_callback_data("analyze_chart:So111")
        assert action == "analyze_chart"
        assert token_address == "So111"

    def test_parse_watchlist_callback(self):
        """Should parse watchlist callback data correctly."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, token_address = parse_callback_data("watch_remove:So111")
        assert action == "watch_remove"
        assert token_address == "So111"

    def test_parse_simple_callback(self):
        """Should handle callbacks without address."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, token_address = parse_callback_data("ui_close")
        assert action == "ui_close"
        assert token_address == ""

    def test_parse_complex_callback(self):
        """Should handle multi-part callback data."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, data = parse_callback_data("alert:address:150.0")
        assert action == "alert"
        assert "address" in data or data == "address:150.0"


# =============================================================================
# Test Button Building Edge Cases
# =============================================================================

class TestButtonEdgeCases:
    """Test edge cases in button building."""

    def test_long_token_symbol(self):
        """Should handle long token symbols."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        # Long symbol shouldn't break button generation
        keyboard = buttons.build_main_keyboard("test_address", "VERYLONGTOKENSYMBOL")
        assert keyboard is not None

    def test_special_characters_in_address(self):
        """Should handle addresses with all base58 characters."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        address = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnop"
        keyboard = buttons.build_main_keyboard(address, "TEST")
        assert keyboard is not None

    def test_empty_symbol(self):
        """Should handle empty symbol."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard("test_address", "")
        assert keyboard is not None
