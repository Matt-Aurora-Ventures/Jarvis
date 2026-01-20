"""
Tests for Telegram UI Interactive Menus.

Tests cover:
- Portfolio overview with buttons
- Trading dashboard with quick actions
- Settings management menu
- Menu navigation
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


# =============================================================================
# Test Portfolio Menu
# =============================================================================

class TestPortfolioMenu:
    """Test portfolio overview menu generation."""

    def test_create_portfolio_menu(self):
        """Portfolio menu should be created with overview."""
        from tg_bot.ui.interactive_menus import PortfolioMenu

        menu = PortfolioMenu()
        keyboard = menu.build()

        assert isinstance(keyboard, InlineKeyboardMarkup)
        rows = keyboard.inline_keyboard
        assert len(rows) >= 1

    def test_portfolio_has_navigation_buttons(self):
        """Portfolio menu should have navigation buttons."""
        from tg_bot.ui.interactive_menus import PortfolioMenu

        menu = PortfolioMenu()
        keyboard = menu.build()

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have back or close button
        has_nav = any(
            "back" in b.callback_data.lower() or
            "close" in b.callback_data.lower()
            for b in all_buttons
        )
        assert has_nav

    def test_portfolio_with_positions(self):
        """Portfolio with positions should show position buttons."""
        from tg_bot.ui.interactive_menus import PortfolioMenu

        positions = [
            {"symbol": "SOL", "pnl_pct": 15.5, "id": "pos_1"},
            {"symbol": "BONK", "pnl_pct": -5.2, "id": "pos_2"},
        ]

        menu = PortfolioMenu()
        keyboard = menu.build_with_positions(positions)

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have position-related buttons
        assert any("SOL" in b.text for b in all_buttons)
        assert any("BONK" in b.text for b in all_buttons)

    def test_portfolio_empty_state(self):
        """Empty portfolio should show helpful message."""
        from tg_bot.ui.interactive_menus import PortfolioMenu

        menu = PortfolioMenu()
        text, keyboard = menu.build_empty()

        assert "no positions" in text.lower() or "empty" in text.lower()

    def test_portfolio_refresh_button(self):
        """Portfolio should have refresh button."""
        from tg_bot.ui.interactive_menus import PortfolioMenu

        menu = PortfolioMenu()
        keyboard = menu.build()

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        assert any("refresh" in b.callback_data.lower() for b in all_buttons)


# =============================================================================
# Test Trading Dashboard
# =============================================================================

class TestTradingDashboard:
    """Test trading dashboard menu generation."""

    def test_create_dashboard(self):
        """Dashboard should be created."""
        from tg_bot.ui.interactive_menus import TradingDashboard

        dashboard = TradingDashboard()
        keyboard = dashboard.build()

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_dashboard_quick_actions(self):
        """Dashboard should have quick action buttons."""
        from tg_bot.ui.interactive_menus import TradingDashboard

        dashboard = TradingDashboard()
        keyboard = dashboard.build()

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have core trading actions
        action_keywords = ["positions", "balance", "report"]
        for keyword in action_keywords:
            assert any(keyword in b.callback_data.lower() for b in all_buttons), \
                f"Missing {keyword} button"

    def test_dashboard_with_stats(self):
        """Dashboard should display stats when provided."""
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

        assert "10.5" in text or "10.50" in text
        # Allow for comma-formatted numbers like "1,050"
        assert "$1050" in text or "1050" in text or "1,050" in text
        assert "65" in text

    def test_dashboard_mode_toggle(self):
        """Dashboard should show mode toggle button."""
        from tg_bot.ui.interactive_menus import TradingDashboard

        dashboard = TradingDashboard()
        keyboard = dashboard.build(mode="paper")

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should indicate current mode
        has_mode_indicator = any(
            "paper" in b.text.lower() or "live" in b.text.lower()
            for b in all_buttons
        )
        assert has_mode_indicator

    def test_dashboard_for_admin(self):
        """Admin dashboard should have extra options."""
        from tg_bot.ui.interactive_menus import TradingDashboard

        dashboard = TradingDashboard()
        admin_keyboard = dashboard.build(is_admin=True)
        user_keyboard = dashboard.build(is_admin=False)

        admin_buttons = [b for row in admin_keyboard.inline_keyboard for b in row]
        user_buttons = [b for row in user_keyboard.inline_keyboard for b in row]

        # Admin should have more buttons
        assert len(admin_buttons) >= len(user_buttons)


# =============================================================================
# Test Settings Menu
# =============================================================================

class TestSettingsMenu:
    """Test settings management menu."""

    def test_create_settings_menu(self):
        """Settings menu should be created."""
        from tg_bot.ui.interactive_menus import SettingsMenu

        menu = SettingsMenu()
        keyboard = menu.build(user_id=12345)

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_settings_sections(self):
        """Settings should have organized sections."""
        from tg_bot.ui.interactive_menus import SettingsMenu

        menu = SettingsMenu()
        keyboard = menu.build(user_id=12345)

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Should have notification settings
        assert any("notif" in b.callback_data.lower() for b in all_buttons)

        # Should have theme/display settings
        assert any("theme" in b.callback_data.lower() or "display" in b.callback_data.lower() for b in all_buttons)

    def test_settings_toggle_notification(self):
        """Should generate toggle for notifications."""
        from tg_bot.ui.interactive_menus import SettingsMenu

        menu = SettingsMenu()

        # With notifications ON
        keyboard_on = menu.build(user_id=12345, settings={"notifications": True})
        rows_on = keyboard_on.inline_keyboard
        buttons_on = [b for row in rows_on for b in row]

        # With notifications OFF
        keyboard_off = menu.build(user_id=12345, settings={"notifications": False})
        rows_off = keyboard_off.inline_keyboard
        buttons_off = [b for row in rows_off for b in row]

        # Button text should differ based on state
        on_text = next((b.text for b in buttons_on if "notif" in b.callback_data.lower()), "")
        off_text = next((b.text for b in buttons_off if "notif" in b.callback_data.lower()), "")

        assert on_text != off_text

    def test_settings_risk_profile(self):
        """Settings should include risk profile option."""
        from tg_bot.ui.interactive_menus import SettingsMenu

        menu = SettingsMenu()
        keyboard = menu.build(user_id=12345)

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        assert any("risk" in b.callback_data.lower() for b in all_buttons)

    def test_settings_alert_preferences(self):
        """Settings should include alert preferences."""
        from tg_bot.ui.interactive_menus import SettingsMenu

        menu = SettingsMenu()
        keyboard = menu.build(user_id=12345)

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        assert any("alert" in b.callback_data.lower() for b in all_buttons)


# =============================================================================
# Test Menu Navigation
# =============================================================================

class TestMenuNavigation:
    """Test menu navigation system."""

    def test_navigate_to_submenu(self):
        """Should navigate to submenu."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        keyboard = nav.navigate_to("settings")

        assert isinstance(keyboard, InlineKeyboardMarkup)

    def test_back_to_main_menu(self):
        """Should navigate back to main menu."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        keyboard = nav.back_to_main()

        rows = keyboard.inline_keyboard
        all_buttons = [b for row in rows for b in row]

        # Main menu should have core options
        assert len(all_buttons) >= 3

    def test_breadcrumb_tracking(self):
        """Should track navigation breadcrumbs."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        nav.navigate_to("portfolio")
        nav.navigate_to("position_details")

        breadcrumbs = nav.get_breadcrumbs()

        assert "portfolio" in breadcrumbs
        assert "position_details" in breadcrumbs

    def test_back_button_navigation(self):
        """Back button should go to previous menu."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        nav.navigate_to("settings")
        nav.navigate_to("risk_profile")

        prev_menu = nav.go_back()

        assert prev_menu == "settings"

    @pytest.mark.asyncio
    async def test_handle_navigation_callback(self):
        """Should handle navigation callbacks."""
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

    def test_menu_state_persistence(self):
        """Menu state should persist for user session."""
        from tg_bot.ui.interactive_menus import MenuNavigator

        nav = MenuNavigator()
        user_id = 12345

        nav.navigate_to("portfolio", user_id=user_id)

        current = nav.get_current_menu(user_id)
        assert current == "portfolio"
