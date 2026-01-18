"""
Tests for Quick Wins UI Improvements.

Tests:
- Command aliases
- Error message formatting
- Theme management
- Timezone service
- Search functionality
- Export functionality
- Session preferences
"""

import json
import pytest
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch


# ============================================================================
# Error Handler Tests
# ============================================================================

class TestErrorHandler:
    """Tests for user-friendly error handling."""

    def test_classify_token_not_found_error(self):
        """Error classification detects token not found."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        error = Exception("Token not found in database")
        assert classify_error(error) == ErrorCategory.TOKEN_NOT_FOUND

    def test_classify_rate_limit_error(self):
        """Error classification detects rate limiting."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        error = Exception("429 Too many requests")
        assert classify_error(error) == ErrorCategory.RATE_LIMITED

    def test_classify_api_error(self):
        """Error classification detects API errors."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        error = Exception("500 Internal Server Error from API")
        assert classify_error(error) == ErrorCategory.API_ERROR

    def test_classify_network_error(self):
        """Error classification detects network issues."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        error = Exception("Connection refused")
        assert classify_error(error) == ErrorCategory.NETWORK_ERROR

    def test_classify_timeout_error(self):
        """Error classification detects timeouts."""
        from tg_bot.error_handler import classify_error, ErrorCategory

        error = Exception("Request timed out after 30s")
        assert classify_error(error) == ErrorCategory.TIMEOUT

    def test_format_error_message(self):
        """Error messages are formatted correctly."""
        from tg_bot.error_handler import format_error_message, ErrorCategory

        error = Exception("Token not found")
        message = format_error_message(error, ErrorCategory.TOKEN_NOT_FOUND)

        assert "Token Not Found" in message
        assert "Try this:" in message

    def test_format_simple_error(self):
        """Simple errors format correctly."""
        from tg_bot.error_handler import format_simple_error

        message = format_simple_error("Something went wrong", "Try again")
        assert "Something went wrong" in message
        assert "Try again" in message

    def test_format_validation_error(self):
        """Validation errors include field info."""
        from tg_bot.error_handler import format_validation_error

        message = format_validation_error("token", "Invalid address format", "So11111...")
        assert "Invalid token" in message
        assert "Invalid address format" in message
        assert "So11111..." in message

    def test_extract_error_code(self):
        """HTTP error codes are extracted."""
        from tg_bot.error_handler import extract_error_code

        assert extract_error_code(Exception("HTTP 404 not found")) == "HTTP_404"
        # Error code pattern only matches error_code: format (no space before colon)
        assert extract_error_code(Exception("error_code: INVALID_TOKEN")) == "INVALID_TOKEN"


# ============================================================================
# Theme Manager Tests
# ============================================================================

class TestThemeManager:
    """Tests for theme management."""

    def test_default_theme_is_dark(self):
        """Default theme is dark mode."""
        from tg_bot.ui.theme import ThemeManager, ThemeMode

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ThemeManager(storage_path=Path(tmpdir) / "themes.json")
            assert manager.get_theme(12345) == ThemeMode.DARK

    def test_set_theme(self):
        """Theme can be set for a user."""
        from tg_bot.ui.theme import ThemeManager, ThemeMode

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ThemeManager(storage_path=Path(tmpdir) / "themes.json")
            manager.set_theme(12345, ThemeMode.LIGHT)
            assert manager.get_theme(12345) == ThemeMode.LIGHT

    def test_toggle_theme(self):
        """Theme can be toggled."""
        from tg_bot.ui.theme import ThemeManager, ThemeMode

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ThemeManager(storage_path=Path(tmpdir) / "themes.json")
            # Default is dark, toggle to light
            new_mode = manager.toggle_theme(12345)
            assert new_mode == ThemeMode.LIGHT

            # Toggle back to dark
            new_mode = manager.toggle_theme(12345)
            assert new_mode == ThemeMode.DARK

    def test_get_colors(self):
        """Colors are returned based on theme."""
        from tg_bot.ui.theme import ThemeManager, ThemeMode, DARK_THEME, LIGHT_THEME

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ThemeManager(storage_path=Path(tmpdir) / "themes.json")

            # Dark theme colors
            colors = manager.get_colors(12345)
            assert colors.use_decorative == DARK_THEME.use_decorative

            # Switch to light
            manager.set_theme(12345, ThemeMode.LIGHT)
            colors = manager.get_colors(12345)
            assert colors.use_decorative == LIGHT_THEME.use_decorative

    def test_themed_formatter(self):
        """ThemedFormatter formats correctly."""
        from tg_bot.ui.theme import ThemedFormatter, DARK_THEME

        formatter = ThemedFormatter(DARK_THEME)

        assert "*" in formatter.heading("Test")
        assert formatter.percentage(10.5).startswith(DARK_THEME.positive_prefix)
        assert formatter.percentage(-5.2).startswith(DARK_THEME.negative_prefix)


# ============================================================================
# Timezone Service Tests
# ============================================================================

class TestTimezoneService:
    """Tests for timezone management."""

    def test_default_timezone_is_utc(self):
        """Default timezone is UTC."""
        from tg_bot.services.timezone_service import TimezoneService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = TimezoneService(storage_path=Path(tmpdir) / "tz.json")
            assert service.get_timezone(12345) == "UTC"

    def test_set_timezone(self):
        """Timezone can be set for a user."""
        from tg_bot.services.timezone_service import TimezoneService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = TimezoneService(storage_path=Path(tmpdir) / "tz.json")
            result = service.set_timezone(12345, "America/New_York")
            assert result == True
            assert service.get_timezone(12345) == "America/New_York"

    def test_invalid_timezone_rejected(self):
        """Invalid timezone names are rejected."""
        from tg_bot.services.timezone_service import TimezoneService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = TimezoneService(storage_path=Path(tmpdir) / "tz.json")
            result = service.set_timezone(12345, "Invalid/Timezone")
            assert result == False

    def test_format_time(self):
        """Time is formatted correctly."""
        from tg_bot.services.timezone_service import TimezoneService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = TimezoneService(storage_path=Path(tmpdir) / "tz.json")
            dt = datetime(2024, 1, 15, 12, 30, 0, tzinfo=timezone.utc)
            formatted = service.format_time(dt, 12345)
            assert "2024-01-15" in formatted
            assert "12:30" in formatted

    def test_search_timezone(self):
        """Timezone search works."""
        from tg_bot.services.timezone_service import TimezoneService

        with tempfile.TemporaryDirectory() as tmpdir:
            service = TimezoneService(storage_path=Path(tmpdir) / "tz.json")
            # Use a simpler search term that matches the display name
            results = service.search_timezone("Eastern")
            assert len(results) > 0
            assert any("New_York" in r[0] for r in results)

    def test_common_timezones_list(self):
        """Common timezones list is populated."""
        from tg_bot.services.timezone_service import COMMON_TIMEZONES

        assert len(COMMON_TIMEZONES) > 0
        assert any("UTC" in tz[0] for tz in COMMON_TIMEZONES)


# ============================================================================
# Quick Buttons Tests
# ============================================================================

class TestQuickButtons:
    """Tests for emoji quick action buttons."""

    def test_build_quick_actions(self):
        """Quick action keyboard is built correctly."""
        from tg_bot.ui.quick_buttons import QuickButtons

        buttons = QuickButtons()
        keyboard = buttons.build_quick_actions(["stats", "analyze"])

        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

    def test_compact_mode(self):
        """Compact mode shows only emojis."""
        from tg_bot.ui.quick_buttons import QuickButtons, QUICK_ACTIONS

        buttons = QuickButtons()
        keyboard = buttons.build_quick_actions(["stats"], compact=True)

        # In compact mode, button text should be just emoji
        button_text = keyboard.inline_keyboard[0][0].text
        assert button_text == QUICK_ACTIONS["stats"]["emoji"]

    def test_full_mode(self):
        """Full mode shows emoji + label."""
        from tg_bot.ui.quick_buttons import QuickButtons, QUICK_ACTIONS

        buttons = QuickButtons()
        keyboard = buttons.build_quick_actions(["stats"], compact=False)

        button_text = keyboard.inline_keyboard[0][0].text
        assert QUICK_ACTIONS["stats"]["emoji"] in button_text
        assert QUICK_ACTIONS["stats"]["label"] in button_text

    def test_default_footer(self):
        """Default footer has common actions."""
        from tg_bot.ui.quick_buttons import QuickButtons

        buttons = QuickButtons()
        keyboard = buttons.build_default_footer()

        # Should have buttons
        assert len(keyboard.inline_keyboard) > 0


# ============================================================================
# Search Command Tests
# ============================================================================

class TestSearchCommand:
    """Tests for token search functionality."""

    def test_search_exact_match(self):
        """Exact symbol match is found first."""
        from tg_bot.handlers.commands.search_command import search_tokens

        results = search_tokens("SOL")
        assert len(results) > 0
        assert results[0]["symbol"] == "SOL"
        assert results[0]["match_type"] == "exact"

    def test_search_partial_symbol(self):
        """Partial symbol match works."""
        from tg_bot.handlers.commands.search_command import search_tokens

        results = search_tokens("bon")
        assert len(results) > 0
        assert any(r["symbol"] == "BONK" for r in results)

    def test_search_by_name(self):
        """Search by token name works."""
        from tg_bot.handlers.commands.search_command import search_tokens

        results = search_tokens("jupiter")
        assert len(results) > 0
        assert any(r["symbol"] == "JUP" for r in results)

    def test_search_no_results(self):
        """Empty results for unknown tokens."""
        from tg_bot.handlers.commands.search_command import search_tokens

        results = search_tokens("xyznonexistent")
        assert len(results) == 0

    def test_search_limit(self):
        """Search respects limit."""
        from tg_bot.handlers.commands.search_command import search_tokens

        results = search_tokens("o", limit=3)  # Should match many
        assert len(results) <= 3

    def test_popular_tokens_populated(self):
        """Popular tokens database is populated."""
        from tg_bot.handlers.commands.search_command import POPULAR_TOKENS

        assert len(POPULAR_TOKENS) > 10
        assert "SOL" in POPULAR_TOKENS
        assert "BONK" in POPULAR_TOKENS


# ============================================================================
# Session Preferences Tests
# ============================================================================

class TestSessionPreferences:
    """Tests for session and user preferences."""

    def test_create_session(self):
        """Session can be created."""
        from tg_bot.sessions.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(sessions_dir=tmpdir, prefs_dir=tmpdir)
            session = manager.create_session(
                user_id=12345,
                token_address="So11111111111111111111111111111111111111112",
                token_symbol="SOL",
            )

            assert session["user_id"] == 12345
            assert session["token_symbol"] == "SOL"

    def test_get_preferences_default(self):
        """Default preferences are created for new users."""
        from tg_bot.sessions.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(sessions_dir=tmpdir, prefs_dir=tmpdir)
            prefs = manager.get_preferences(12345)

            assert prefs.user_id == 12345
            assert prefs.theme == "dark"
            assert prefs.timezone == "UTC"

    def test_update_preferences(self):
        """Preferences can be updated."""
        from tg_bot.sessions.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(sessions_dir=tmpdir, prefs_dir=tmpdir)
            prefs = manager.update_preferences(12345, theme="light")

            assert prefs.theme == "light"

    def test_record_token_view(self):
        """Token views are recorded."""
        from tg_bot.sessions.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(sessions_dir=tmpdir, prefs_dir=tmpdir)

            manager.record_token_view(12345, "token1")
            manager.record_token_view(12345, "token2")
            manager.record_token_view(12345, "token3")

            recent = manager.get_recent_tokens(12345)
            assert len(recent) == 3
            assert recent[0] == "token3"  # Most recent first

    def test_last_token_tracked(self):
        """Last analyzed token is tracked."""
        from tg_bot.sessions.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(sessions_dir=tmpdir, prefs_dir=tmpdir)

            manager.record_token_view(12345, "token1")
            manager.record_token_view(12345, "token2")

            last = manager.get_last_token(12345)
            assert last == "token2"

    def test_recent_tokens_limit(self):
        """Recent tokens limited to 5."""
        from tg_bot.sessions.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SessionManager(sessions_dir=tmpdir, prefs_dir=tmpdir)

            for i in range(10):
                manager.record_token_view(12345, f"token{i}")

            recent = manager.get_recent_tokens(12345)
            assert len(recent) == 5


# ============================================================================
# Export Command Tests
# ============================================================================

class TestExportCommand:
    """Tests for trading data export."""

    def test_format_positions_csv(self):
        """Positions format as valid CSV."""
        from tg_bot.handlers.commands.export_command import format_positions_csv

        positions = [
            {
                "symbol": "SOL",
                "address": "So11111...",
                "entry_price": 100.0,
                "current_price": 110.0,
                "amount": 10.0,
                "value_usd": 1100.0,
                "pnl_usd": 100.0,
                "pnl_pct": 10.0,
            }
        ]

        csv_str = format_positions_csv(positions)
        assert "symbol" in csv_str
        assert "SOL" in csv_str
        assert "100.0" in csv_str

    def test_format_trades_csv(self):
        """Trades format as valid CSV."""
        from tg_bot.handlers.commands.export_command import format_trades_csv

        trades = [
            {
                "id": "tx123",
                "symbol": "BONK",
                "side": "buy",
                "amount": 1000000,
                "price": 0.00001,
                "value_usd": 10.0,
            }
        ]

        csv_str = format_trades_csv(trades)
        assert "symbol" in csv_str
        assert "BONK" in csv_str
        assert "buy" in csv_str


# ============================================================================
# Integration Tests
# ============================================================================

class TestQuickWinsIntegration:
    """Integration tests for quick wins features."""

    def test_preferences_persist_across_sessions(self):
        """Preferences persist when manager is recreated."""
        from tg_bot.sessions.session_manager import SessionManager

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create manager and set preference
            manager1 = SessionManager(sessions_dir=tmpdir, prefs_dir=tmpdir)
            manager1.update_preferences(12345, theme="light", timezone="America/New_York")

            # Create new manager instance
            manager2 = SessionManager(sessions_dir=tmpdir, prefs_dir=tmpdir)
            prefs = manager2.get_preferences(12345)

            assert prefs.theme == "light"
            assert prefs.timezone == "America/New_York"

    def test_theme_manager_persists(self):
        """Theme settings persist."""
        from tg_bot.ui.theme import ThemeManager, ThemeMode

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / "themes.json"

            manager1 = ThemeManager(storage_path=storage)
            manager1.set_theme(12345, ThemeMode.LIGHT)

            manager2 = ThemeManager(storage_path=storage)
            assert manager2.get_theme(12345) == ThemeMode.LIGHT

    def test_timezone_service_persists(self):
        """Timezone settings persist."""
        from tg_bot.services.timezone_service import TimezoneService

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = Path(tmpdir) / "tz.json"

            service1 = TimezoneService(storage_path=storage)
            service1.set_timezone(12345, "Asia/Tokyo")

            service2 = TimezoneService(storage_path=storage)
            assert service2.get_timezone(12345) == "Asia/Tokyo"
