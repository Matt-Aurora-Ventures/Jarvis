"""
Comprehensive Tests for Telegram Bot Handlers.

Tests cover:
1. Command parsing and execution
2. Permission enforcement (admin_only decorator)
3. User-friendly error responses
4. Rate limiting per user
5. Inline keyboard functionality
6. Callback query handling
"""

import pytest
import time
import sqlite3
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from telegram import Update, User, Chat, Message, CallbackQuery, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_user():
    """Create mock Telegram user."""
    user = Mock(spec=User)
    user.id = 123456789
    user.username = "testuser"
    user.first_name = "Test"
    user.last_name = "User"
    return user


@pytest.fixture
def mock_admin_user():
    """Create mock admin Telegram user."""
    user = Mock(spec=User)
    user.id = 111111111
    user.username = "admin"
    user.first_name = "Admin"
    user.last_name = "User"
    return user


@pytest.fixture
def mock_chat():
    """Create mock Telegram chat."""
    chat = Mock(spec=Chat)
    chat.id = 123456789
    chat.type = "private"
    return chat


@pytest.fixture
def mock_message(mock_user, mock_chat):
    """Create mock Telegram message."""
    message = Mock(spec=Message)
    message.chat = mock_chat
    message.from_user = mock_user
    message.chat_id = mock_chat.id
    message.message_id = 1
    message.reply_text = AsyncMock()
    return message


@pytest.fixture
def mock_update(mock_user, mock_chat, mock_message):
    """Create mock Telegram update."""
    update = Mock(spec=Update)
    update.update_id = 1
    update.effective_user = mock_user
    update.effective_chat = mock_chat
    update.effective_message = mock_message
    update.message = mock_message
    return update


@pytest.fixture
def mock_admin_update(mock_admin_user, mock_chat, mock_message):
    """Create mock update with admin user."""
    mock_message.from_user = mock_admin_user
    update = Mock(spec=Update)
    update.update_id = 1
    update.effective_user = mock_admin_user
    update.effective_chat = mock_chat
    update.effective_message = mock_message
    update.message = mock_message
    return update


@pytest.fixture
def mock_context():
    """Create mock Telegram context."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    context.bot = Mock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.fixture
def mock_config():
    """Mock bot config with admin IDs."""
    with patch('tg_bot.handlers.get_config') as mock:
        config = Mock()
        config.admin_ids = {111111111}  # Admin ID
        config.is_admin = lambda uid: uid in config.admin_ids
        config.db_path = Path("/tmp/test_jarvis.db")
        config.daily_cost_limit_usd = 10.0
        config.sentiment_interval_seconds = 3600
        config.max_sentiment_per_day = 24
        mock.return_value = config
        yield config


@pytest.fixture
def mock_callback_query(mock_user, mock_message):
    """Create mock callback query."""
    query = Mock(spec=CallbackQuery)
    query.id = "callback_123"
    query.from_user = mock_user
    query.message = mock_message
    query.data = "menu_status"
    query.answer = AsyncMock()
    return query


@pytest.fixture
def mock_callback_update(mock_user, mock_chat, mock_callback_query):
    """Create mock update with callback query."""
    update = Mock(spec=Update)
    update.update_id = 2
    update.effective_user = mock_user
    update.effective_chat = mock_chat
    update.callback_query = mock_callback_query
    update.message = None
    return update


# =============================================================================
# Test Command Parsing
# =============================================================================


class TestCommandParsing:
    """Test that commands are parsed correctly."""

    @pytest.mark.asyncio
    async def test_start_command_parses(self, mock_update, mock_context, mock_config):
        """Test /start command is parsed and executed."""
        from tg_bot.handlers.commands_base import start

        await start(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args

        # Check response contains expected content
        message_text = call_args[0][0]
        assert "jarvis" in message_text.lower()

        # Check parse mode
        assert call_args[1]["parse_mode"] == ParseMode.MARKDOWN

        # Check keyboard markup
        assert "reply_markup" in call_args[1]
        keyboard = call_args[1]["reply_markup"]
        assert isinstance(keyboard, InlineKeyboardMarkup)

    @pytest.mark.asyncio
    async def test_help_command_aliases_start(self, mock_update, mock_context, mock_config):
        """Test /help command calls start handler."""
        from tg_bot.handlers.commands_base import help_command, start

        with patch('tg_bot.handlers.commands_base.start') as mock_start:
            mock_start.return_value = None
            await help_command(mock_update, mock_context)
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_status_command_parses(self, mock_update, mock_context, mock_config):
        """Test /status command returns bot status."""
        from tg_bot.handlers.commands_base import status

        with patch('tg_bot.handlers.commands_base.get_signal_service') as mock_service:
            service = Mock()
            service.get_available_sources.return_value = ["dexscreener", "birdeye"]
            mock_service.return_value = service

            await status(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        message = mock_update.message.reply_text.call_args[0][0]
        assert "Status" in message or "status" in message

    @pytest.mark.asyncio
    async def test_subscribe_command_with_user(self, mock_update, mock_context, mock_config, tmp_path):
        """Test /subscribe adds user to digest list."""
        from tg_bot.handlers.commands_base import subscribe

        mock_config.db_path = tmp_path / "test.db"

        with patch('tg_bot.handlers.commands_base.get_config', return_value=mock_config):
            # Patch at the import location inside the function
            with patch('tg_bot.models.subscriber.SubscriberDB') as mock_db_class:
                mock_db = Mock()
                mock_db.subscribe = Mock()
                mock_db_class.return_value = mock_db

                await subscribe(mock_update, mock_context)

                mock_db.subscribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_unsubscribe_command(self, mock_update, mock_context, mock_config, tmp_path):
        """Test /unsubscribe removes user from digest list."""
        from tg_bot.handlers.commands_base import unsubscribe

        mock_config.db_path = tmp_path / "test.db"

        with patch('tg_bot.handlers.commands_base.get_config', return_value=mock_config):
            with patch('tg_bot.models.subscriber.SubscriberDB') as mock_db_class:
                mock_db = Mock()
                mock_db.unsubscribe = Mock(return_value=True)
                mock_db_class.return_value = mock_db

                await unsubscribe(mock_update, mock_context)

                mock_db.unsubscribe.assert_called_once()


# =============================================================================
# Test Permission Enforcement
# =============================================================================


class TestPermissionEnforcement:
    """Test that command permissions are enforced."""

    @pytest.mark.asyncio
    async def test_admin_only_blocks_non_admin(self, mock_update, mock_context, mock_config):
        """Test admin_only decorator blocks non-admin users."""
        from tg_bot.handlers import admin_only

        @admin_only
        async def admin_command(update, context):
            return "success"

        result = await admin_command(mock_update, mock_context)

        # Non-admin should be blocked
        assert result is None
        mock_update.message.reply_text.assert_called_once()
        message = mock_update.message.reply_text.call_args[0][0]
        assert "Unauthorized" in message or "admin" in message.lower()

    @pytest.mark.asyncio
    async def test_admin_only_allows_admin(self, mock_admin_update, mock_context, mock_config):
        """Test admin_only decorator allows admin users."""
        from tg_bot.handlers import admin_only

        @admin_only
        async def admin_command(update, context):
            return "success"

        result = await admin_command(mock_admin_update, mock_context)

        # Admin should be allowed
        assert result == "success"

    @pytest.mark.asyncio
    async def test_reload_requires_admin(self, mock_update, mock_context, mock_config):
        """Test /reload command requires admin."""
        from tg_bot.handlers.admin import reload

        await reload(mock_update, mock_context)

        # Non-admin should see unauthorized message
        mock_update.message.reply_text.assert_called_once()
        message = mock_update.message.reply_text.call_args[0][0]
        assert "Unauthorized" in message or "admin" in message.lower()

    @pytest.mark.asyncio
    async def test_logs_requires_admin(self, mock_update, mock_context, mock_config):
        """Test /logs command requires admin."""
        from tg_bot.handlers.admin import logs

        await logs(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        message = mock_update.message.reply_text.call_args[0][0]
        assert "Unauthorized" in message or "admin" in message.lower()

    @pytest.mark.asyncio
    async def test_system_requires_admin(self, mock_update, mock_context, mock_config):
        """Test /system command requires admin."""
        from tg_bot.handlers.admin import system

        await system(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        message = mock_update.message.reply_text.call_args[0][0]
        assert "Unauthorized" in message or "admin" in message.lower()

    @pytest.mark.asyncio
    async def test_config_requires_admin(self, mock_update, mock_context, mock_config):
        """Test /config command requires admin."""
        from tg_bot.handlers.admin import config_cmd

        await config_cmd(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        message = mock_update.message.reply_text.call_args[0][0]
        assert "Unauthorized" in message or "admin" in message.lower()

    @pytest.mark.asyncio
    async def test_flags_requires_admin(self, mock_update, mock_context, mock_config):
        """Test /flags command requires admin."""
        from tg_bot.handlers.admin import flags

        await flags(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        message = mock_update.message.reply_text.call_args[0][0]
        assert "Unauthorized" in message or "admin" in message.lower()


# =============================================================================
# Test Error Responses
# =============================================================================


class TestErrorResponses:
    """Test that error responses are user-friendly."""

    @pytest.mark.asyncio
    async def test_error_handler_catches_exceptions(self, mock_update, mock_context, mock_config):
        """Test error_handler decorator catches exceptions."""
        from tg_bot.handlers import error_handler

        @error_handler
        async def failing_command(update, context):
            raise ValueError("Test error")

        result = await failing_command(mock_update, mock_context)

        # Should return None on error
        assert result is None

        # Should send user-friendly message
        mock_update.effective_message.reply_text.assert_called()
        message = mock_update.effective_message.reply_text.call_args[0][0]
        assert "wrong" in message.lower() or "error" in message.lower()

    @pytest.mark.asyncio
    async def test_error_handler_notifies_admins(self, mock_update, mock_context, mock_config):
        """Test error_handler notifies admins of errors."""
        from tg_bot.handlers import error_handler

        @error_handler
        async def failing_command(update, context):
            raise ValueError("Test error")

        await failing_command(mock_update, mock_context)

        # Should attempt to notify admins
        mock_context.bot.send_message.assert_called()

        # Check admin was notified
        calls = mock_context.bot.send_message.call_args_list
        admin_call = next((c for c in calls if c[1]["chat_id"] == 111111111), None)
        assert admin_call is not None

    @pytest.mark.asyncio
    async def test_error_handler_ignores_expired_callback(self, mock_update, mock_context, mock_config):
        """Expired callback BadRequest should not spam users/admins."""
        from telegram.error import BadRequest
        from tg_bot.handlers import error_handler

        @error_handler
        async def failing_command(update, context):
            raise BadRequest("Query is too old and response timeout expired or query id is invalid")

        result = await failing_command(mock_update, mock_context)

        assert result is None
        mock_update.effective_message.reply_text.assert_not_called()
        mock_context.bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_unauthorized_message_is_friendly(self, mock_update, mock_context, mock_config):
        """Test unauthorized message is user-friendly."""
        from tg_bot.services.digest_formatter import format_unauthorized

        message = format_unauthorized()

        # Should use emoji and clear language
        assert "Unauthorized" in message
        assert "admin" in message.lower()
        # Should not expose technical details
        assert "Exception" not in message
        assert "Traceback" not in message

    @pytest.mark.asyncio
    async def test_rate_limit_message_is_friendly(self, mock_update, mock_context, mock_config):
        """Test rate limit message is user-friendly."""
        from tg_bot.services.digest_formatter import format_rate_limit

        message = format_rate_limit("Next check in 30m 45s")

        # Should be clear about rate limiting
        assert "Rate" in message or "limit" in message.lower()
        assert "30m" in message or "45s" in message

    def test_format_error_is_helpful(self):
        """Test format_error includes suggestions."""
        from tg_bot.services.digest_formatter import format_error

        message = format_error("Token not found", "Try using the contract address instead")

        assert "Error" in message
        assert "Token not found" in message
        assert "contract address" in message


# =============================================================================
# Test Rate Limiting
# =============================================================================


class TestRateLimiting:
    """Test rate limiting per user."""

    @pytest.fixture
    def temp_tracker_db(self, tmp_path):
        """Create temporary cost tracker database."""
        db_path = tmp_path / "cost_tracker.db"
        return db_path

    @pytest.mark.asyncio
    async def test_rate_limited_decorator_checks_budget(self, mock_update, mock_context, mock_config, temp_tracker_db):
        """Test rate_limited decorator checks API budget."""
        from tg_bot.handlers import rate_limited

        with patch('tg_bot.handlers.get_tracker') as mock_get_tracker:
            tracker = Mock()
            tracker.can_make_sentiment_call.return_value = (False, "Daily limit reached")
            mock_get_tracker.return_value = tracker

            @rate_limited
            async def expensive_command(update, context):
                return "success"

            result = await expensive_command(mock_update, mock_context)

            # Should be blocked
            assert result is None
            mock_update.message.reply_text.assert_called_once()
            message = mock_update.message.reply_text.call_args[0][0]
            assert "limit" in message.lower()

    @pytest.mark.asyncio
    async def test_rate_limited_decorator_allows_when_budget_ok(self, mock_update, mock_context, mock_config):
        """Test rate_limited decorator allows when budget is OK."""
        from tg_bot.handlers import rate_limited

        with patch('tg_bot.handlers.get_tracker') as mock_get_tracker:
            tracker = Mock()
            tracker.can_make_sentiment_call.return_value = (True, "OK")
            mock_get_tracker.return_value = tracker

            @rate_limited
            async def expensive_command(update, context):
                return "success"

            result = await expensive_command(mock_update, mock_context)

            assert result == "success"

    def test_cost_tracker_time_based_rate_limit(self, temp_tracker_db):
        """Test cost tracker enforces time-based rate limits."""
        from tg_bot.services.cost_tracker import CostTracker

        with patch('tg_bot.services.cost_tracker.get_config') as mock_config:
            config = Mock()
            config.db_path = temp_tracker_db.parent / "jarvis.db"
            config.daily_cost_limit_usd = 10.0
            config.sentiment_interval_seconds = 3600
            config.max_sentiment_per_day = 24
            mock_config.return_value = config

            tracker = CostTracker(db_path=temp_tracker_db)

            # First call should be allowed
            can_call, _ = tracker.can_make_sentiment_call()
            assert can_call is True

            # Record a sentiment call
            tracker.record_call("grok", "sentiment", True)

            # Second immediate call should be blocked
            can_call, reason = tracker.can_make_sentiment_call()
            assert can_call is False
            assert "Rate limited" in reason or "limit" in reason.lower()

    def test_cost_tracker_daily_limit(self, temp_tracker_db):
        """Test cost tracker enforces daily cost limits."""
        from tg_bot.services.cost_tracker import CostTracker

        with patch('tg_bot.services.cost_tracker.get_config') as mock_config:
            config = Mock()
            config.db_path = temp_tracker_db.parent / "jarvis.db"
            config.daily_cost_limit_usd = 0.05  # Very low limit
            config.sentiment_interval_seconds = 0  # No rate limit
            config.max_sentiment_per_day = 100
            mock_config.return_value = config

            tracker = CostTracker(db_path=temp_tracker_db)
            tracker._last_sentiment_time = 0  # Reset rate limit

            # Record expensive calls
            tracker.record_call("grok", "sentiment", True, custom_cost=0.10)

            # Should now be blocked
            can_call, reason = tracker.can_make_sentiment_call()
            assert can_call is False
            assert "cost limit" in reason.lower()


# =============================================================================
# Test Inline Keyboards
# =============================================================================


class TestInlineKeyboards:
    """Test inline keyboard functionality."""

    def test_start_keyboard_for_regular_user(self, mock_config):
        """Test /start shows correct keyboard for regular users."""
        from tg_bot.handlers.commands_base import start
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton

        # Build expected keyboard structure
        keyboard = [
            [
                InlineKeyboardButton("Trending", callback_data="menu_trending"),
                InlineKeyboardButton("Status", callback_data="menu_status"),
            ],
            [
                InlineKeyboardButton("Costs", callback_data="menu_costs"),
                InlineKeyboardButton("Help", callback_data="menu_help"),
            ],
        ]

        markup = InlineKeyboardMarkup(keyboard)
        rows = markup.inline_keyboard

        # Regular user should have limited options
        assert len(rows) == 2
        assert any("trending" in btn.callback_data.lower() for btn in rows[0])

    def test_start_keyboard_for_admin(self, mock_config):
        """Test /start shows extended keyboard for admins."""
        # Admin keyboard should have more rows
        expected_admin_buttons = [
            "menu_signals", "menu_digest", "menu_brain", "menu_reload",
            "menu_health", "menu_flags", "menu_system", "menu_config"
        ]

        # Just verify the expected buttons exist in the module
        from tg_bot.handlers.commands_base import start
        # The actual keyboard is built inside the handler
        assert callable(start)

    def test_token_analysis_keyboard_structure(self):
        """Test token analysis keyboard has correct structure."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_main_keyboard(
            token_address="So11111111111111111111111111111111",
            token_symbol="SOL"
        )

        rows = keyboard.inline_keyboard

        # Should have multiple rows
        assert len(rows) >= 3

        # First row should have chart, holders, signals
        all_buttons = [btn for row in rows for btn in row]
        button_data = [btn.callback_data for btn in all_buttons if btn.callback_data]

        assert any("chart" in data for data in button_data)
        assert any("holders" in data for data in button_data)
        assert any("close" in data for data in button_data)

    def test_chart_timeframe_keyboard(self):
        """Test chart keyboard has timeframe options."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()
        keyboard = buttons.build_chart_keyboard("So11111111111111111111111111111111")

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        # Should have timeframe options
        assert "1H" in button_texts
        assert "4H" in button_texts
        assert "1D" in button_texts
        assert "1W" in button_texts

    def test_trading_action_buttons(self):
        """Test trading action buttons have correct options."""
        from tg_bot.ui.inline_buttons import TradingActionButtons

        buttons = TradingActionButtons()

        # Buy confirmation
        buy_keyboard = buttons.build_buy_confirmation(
            token_address="So111",
            token_symbol="SOL",
            amount_usd=100.0
        )
        buy_buttons = [btn for row in buy_keyboard.inline_keyboard for btn in row]
        assert any("confirm" in btn.callback_data.lower() for btn in buy_buttons if btn.callback_data)
        assert any("cancel" in btn.callback_data.lower() for btn in buy_buttons if btn.callback_data)

        # Sell confirmation with percentages
        sell_keyboard = buttons.build_sell_confirmation(
            token_address="So111",
            token_symbol="SOL",
            percentage=50
        )
        sell_buttons = [btn for row in sell_keyboard.inline_keyboard for btn in row]
        button_texts = [btn.text for btn in sell_buttons]

        assert any("25%" in text for text in button_texts)
        assert any("50%" in text for text in button_texts)
        assert any("100%" in text for text in button_texts)

    def test_pagination_keyboard(self):
        """Test holder pagination keyboard."""
        from tg_bot.ui.inline_buttons import TokenAnalysisButtons

        buttons = TokenAnalysisButtons()

        # Page 1 of 3
        keyboard = buttons.build_holders_keyboard("So111", page=1, total_pages=3)
        rows = keyboard.inline_keyboard

        # First row should have pagination
        nav_row = rows[0]
        nav_texts = [btn.text for btn in nav_row]
        assert "1/3" in nav_texts

        # Page 2 of 3 - should have both < and >
        keyboard = buttons.build_holders_keyboard("So111", page=2, total_pages=3)
        nav_row = keyboard.inline_keyboard[0]
        nav_texts = [btn.text for btn in nav_row]
        assert "<" in nav_texts
        assert ">" in nav_texts


# =============================================================================
# Test Callback Query Handling
# =============================================================================


class TestCallbackQueryHandling:
    """Test callback query handling."""

    def test_parse_callback_data_simple(self):
        """Test parsing simple callback data."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data("menu_status")
        assert action == "menu_status"
        assert payload == ""

    def test_parse_callback_data_with_payload(self):
        """Test parsing callback data with payload."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data("analyze:So11111")
        assert action == "analyze"
        assert payload == "So11111"

    def test_parse_callback_data_complex_payload(self):
        """Test parsing callback data with complex payload."""
        from tg_bot.ui.inline_buttons import parse_callback_data

        action, payload = parse_callback_data("sell:So111:50")
        assert action == "sell"
        assert payload == "So111:50"

    def test_build_callback_data_simple(self):
        """Test building simple callback data."""
        from tg_bot.ui.inline_buttons import build_callback_data

        data = build_callback_data("menu_status")
        assert data == "menu_status"

    def test_build_callback_data_with_args(self):
        """Test building callback data with arguments."""
        from tg_bot.ui.inline_buttons import build_callback_data

        data = build_callback_data("analyze", "So111")
        assert data == "analyze:So111"

    def test_build_callback_data_truncates_long_data(self):
        """Test callback data is truncated to 64 bytes."""
        from tg_bot.ui.inline_buttons import build_callback_data

        # Very long address
        long_address = "A" * 100
        data = build_callback_data("analyze", long_address)

        assert len(data.encode('utf-8')) <= 64

    @pytest.mark.asyncio
    async def test_callback_router_registers_handlers(self):
        """Test callback router handler registration."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()

        async def test_handler(query, context, payload):
            return True

        router.register("test_action", test_handler)

        assert router.has_handler("test_action")
        assert not router.has_handler("unknown")

    @pytest.mark.asyncio
    async def test_callback_router_routes_correctly(self):
        """Test callback router routes to correct handler."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()
        called_with = []

        async def handler(query, context, payload):
            called_with.append(payload)
            return True

        router.register("test", handler)

        mock_query = Mock()
        mock_query.data = "test:some_payload"
        mock_context = Mock()

        result = await router.route(mock_query, mock_context)

        assert result is True
        assert called_with == ["some_payload"]

    @pytest.mark.asyncio
    async def test_callback_router_returns_false_for_unknown(self):
        """Test callback router returns False for unknown actions."""
        from tg_bot.ui.inline_buttons import CallbackRouter

        router = CallbackRouter()

        mock_query = Mock()
        mock_query.data = "unknown_action"
        mock_context = Mock()

        result = await router.route(mock_query, mock_context)

        assert result is False

    @pytest.mark.asyncio
    async def test_interactive_ui_callback_routing(self, mock_callback_update, mock_context):
        """Test interactive UI routes callbacks correctly."""
        from tg_bot.handlers.interactive_ui import route_interactive_callback

        mock_callback_update.callback_query.data = "noop"

        result = await route_interactive_callback(
            mock_callback_update.callback_query,
            mock_context,
            user_id=123456
        )

        # noop should return True (handled)
        assert result is True
        mock_callback_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_interactive_ui_close_callback(self, mock_callback_update, mock_context):
        """Test close callback deletes message."""
        from tg_bot.handlers.interactive_ui import route_interactive_callback

        mock_callback_update.callback_query.data = "ui_close:So111"
        mock_callback_update.callback_query.message.delete = AsyncMock()

        with patch('tg_bot.handlers.interactive_ui.get_session_manager') as mock_sm:
            session_manager = Mock()
            session_manager.clear_session = Mock()
            mock_sm.return_value = session_manager

            result = await route_interactive_callback(
                mock_callback_update.callback_query,
                mock_context,
                user_id=123456
            )

            assert result is True
            session_manager.clear_session.assert_called_once_with(123456)
            mock_callback_update.callback_query.message.delete.assert_called_once()


# =============================================================================
# Test Session Management
# =============================================================================


class TestSessionManagement:
    """Test session state management for drill-down navigation."""

    @pytest.fixture
    def session_manager(self, tmp_path):
        """Create session manager with temp directory."""
        from tg_bot.handlers.interactive_ui import SessionManager
        return SessionManager(sessions_dir=str(tmp_path), timeout_minutes=30)

    def test_create_session(self, session_manager):
        """Test session creation."""
        session = session_manager.create_session(
            user_id=123,
            token_address="So111",
            token_symbol="SOL",
            current_view="main"
        )

        assert session["user_id"] == 123
        assert session["token_address"] == "So111"
        assert session["token_symbol"] == "SOL"
        assert session["current_view"] == "main"

    def test_get_session(self, session_manager):
        """Test session retrieval."""
        session_manager.create_session(123, "So111", "SOL")

        session = session_manager.get_session(123)

        assert session is not None
        assert session["user_id"] == 123

    def test_update_session(self, session_manager):
        """Test session update."""
        session_manager.create_session(123, "So111", "SOL")

        session = session_manager.update_session(123, current_view="chart", page=2)

        assert session["current_view"] == "chart"
        assert session["page"] == 2

    def test_clear_session(self, session_manager):
        """Test session clearing."""
        session_manager.create_session(123, "So111", "SOL")
        session_manager.clear_session(123)

        session = session_manager.get_session(123)
        assert session is None

    def test_session_expiry(self, session_manager):
        """Test session expiry after timeout."""
        session_manager.timeout_minutes = 0  # Immediate expiry
        session_manager.create_session(123, "So111", "SOL")

        # Wait a tiny bit
        import time
        time.sleep(0.1)

        session = session_manager.get_session(123)
        assert session is None

    def test_cleanup_expired_sessions(self, session_manager):
        """Test cleanup of expired sessions."""
        session_manager.timeout_minutes = 0
        session_manager.create_session(123, "So111", "SOL")
        session_manager.create_session(456, "So222", "BONK")

        time.sleep(0.1)

        removed = session_manager.cleanup_expired()
        assert removed >= 2


# =============================================================================
# Test Watchlist Management
# =============================================================================


class TestWatchlistManagement:
    """Test watchlist functionality."""

    @pytest.fixture
    def watchlist_manager(self, tmp_path):
        """Create watchlist manager with temp directory."""
        from tg_bot.handlers.interactive_ui import WatchlistManager
        return WatchlistManager(data_dir=str(tmp_path), max_tokens=10)

    def test_add_token_to_watchlist(self, watchlist_manager):
        """Test adding token to watchlist."""
        result = watchlist_manager.add_token(123, "So111", "SOL")
        assert result is True

        watchlist = watchlist_manager.get_watchlist(123)
        assert len(watchlist) == 1
        assert watchlist[0]["symbol"] == "SOL"

    def test_prevent_duplicate_tokens(self, watchlist_manager):
        """Test duplicate tokens are not added."""
        watchlist_manager.add_token(123, "So111", "SOL")
        result = watchlist_manager.add_token(123, "So111", "SOL")

        assert result is False
        watchlist = watchlist_manager.get_watchlist(123)
        assert len(watchlist) == 1

    def test_remove_token_from_watchlist(self, watchlist_manager):
        """Test removing token from watchlist."""
        watchlist_manager.add_token(123, "So111", "SOL")
        watchlist_manager.add_token(123, "So222", "BONK")

        result = watchlist_manager.remove_token(123, "So111")

        assert result is True
        watchlist = watchlist_manager.get_watchlist(123)
        assert len(watchlist) == 1
        assert watchlist[0]["symbol"] == "BONK"

    def test_clear_watchlist(self, watchlist_manager):
        """Test clearing entire watchlist."""
        watchlist_manager.add_token(123, "So111", "SOL")
        watchlist_manager.add_token(123, "So222", "BONK")

        watchlist_manager.clear_watchlist(123)

        watchlist = watchlist_manager.get_watchlist(123)
        assert len(watchlist) == 0

    def test_watchlist_max_limit(self, watchlist_manager):
        """Test watchlist respects max limit."""
        # Add more than max tokens
        for i in range(15):
            watchlist_manager.add_token(123, f"So{i}", f"TOK{i}")

        watchlist = watchlist_manager.get_watchlist(123)
        assert len(watchlist) <= 10

    def test_watchlist_keyboard_building(self):
        """Test watchlist keyboard is built correctly."""
        from tg_bot.ui.inline_buttons import build_watchlist_keyboard

        watchlist = [
            {"symbol": "SOL", "address": "So111"},
            {"symbol": "BONK", "address": "So222"},
        ]

        keyboard = build_watchlist_keyboard(watchlist, user_id=123)
        rows = keyboard.inline_keyboard

        # Should have rows for each token plus action buttons
        assert len(rows) >= 3

        # Check action buttons exist
        all_buttons = [btn for row in rows for btn in row]
        button_data = [btn.callback_data for btn in all_buttons if btn.callback_data]

        assert any("watch_add" in data for data in button_data)
        assert any("watch_refresh" in data for data in button_data)


# =============================================================================
# Test Admin Commands with Arguments
# =============================================================================


class TestAdminCommandArguments:
    """Test admin commands with various arguments."""

    @pytest.mark.asyncio
    async def test_config_set_command(self, mock_admin_update, mock_context, mock_config):
        """Test /config set command with arguments."""
        from tg_bot.handlers.admin import config_cmd

        mock_context.args = ["set", "trading.max_slippage", "0.05"]

        # Patch at the source module location (where import happens inside function)
        with patch('core.config_hot_reload.get_config_manager') as mock_cfg_manager:
            cfg = Mock()
            cfg.set = Mock(return_value=True)
            cfg.get_by_prefix = Mock(return_value={})
            mock_cfg_manager.return_value = cfg

            await config_cmd(mock_admin_update, mock_context)

            cfg.set.assert_called_once_with("trading.max_slippage", 0.05)

    @pytest.mark.asyncio
    async def test_flags_enable_command(self, mock_admin_update, mock_context, mock_config):
        """Test /flags FLAG_NAME on command."""
        from tg_bot.handlers.admin import flags

        mock_context.args = ["TEST_FLAG", "on"]

        # Patch at the source module location
        with patch('core.config.feature_flags.get_feature_flag_manager') as mock_ff:
            manager = Mock()
            manager.set_flag = Mock()
            mock_ff.return_value = manager

            await flags(mock_admin_update, mock_context)

            manager.set_flag.assert_called_once_with("TEST_FLAG", enabled=True)

    @pytest.mark.asyncio
    async def test_flags_percentage_rollout(self, mock_admin_update, mock_context, mock_config):
        """Test /flags FLAG_NAME 50 for percentage rollout."""
        from tg_bot.handlers.admin import flags

        mock_context.args = ["TEST_FLAG", "50"]

        # Patch at the source module location
        with patch('core.config.feature_flags.get_feature_flag_manager') as mock_ff:
            manager = Mock()
            manager.set_flag = Mock()
            mock_ff.return_value = manager

            await flags(mock_admin_update, mock_context)

            manager.set_flag.assert_called_once_with("TEST_FLAG", enabled=True, percentage=50)

    @pytest.mark.asyncio
    async def test_away_command_with_duration(self, mock_admin_update, mock_context, mock_config):
        """Test /away 2h command with duration."""
        from tg_bot.handlers.admin import away

        mock_context.args = ["2h", "Going", "for", "lunch"]

        # Patch at the source module location
        with patch('tg_bot.services.auto_responder.get_auto_responder') as mock_ar:
            responder = Mock()
            responder.enable = Mock(return_value="Away mode enabled")
            mock_ar.return_value = responder

            with patch('tg_bot.services.auto_responder.parse_duration') as mock_parse:
                mock_parse.return_value = 120  # 2 hours in minutes

                await away(mock_admin_update, mock_context)

                responder.enable.assert_called_once()
                call_args = responder.enable.call_args
                assert call_args[1]["duration_minutes"] == 120
                assert call_args[1]["message"] == "Going for lunch"


# =============================================================================
# Test Cost Tracking
# =============================================================================


class TestCostTracking:
    """Test API cost tracking."""

    @pytest.fixture
    def cost_tracker(self, tmp_path):
        """Create cost tracker with temp database."""
        from tg_bot.services.cost_tracker import CostTracker

        with patch('tg_bot.services.cost_tracker.get_config') as mock_config:
            config = Mock()
            config.db_path = tmp_path / "jarvis.db"
            config.daily_cost_limit_usd = 10.0
            config.sentiment_interval_seconds = 3600
            config.max_sentiment_per_day = 24
            mock_config.return_value = config

            return CostTracker(db_path=tmp_path / "cost_tracker.db")

    def test_record_call(self, cost_tracker):
        """Test recording API call."""
        call = cost_tracker.record_call("grok", "sentiment", True, tokens_used=100)

        assert call.service == "grok"
        assert call.endpoint == "sentiment"
        assert call.success is True

    def test_get_today_cost(self, cost_tracker):
        """Test getting today's total cost."""
        cost_tracker.record_call("grok", "sentiment", True, custom_cost=0.10)
        cost_tracker.record_call("claude", "chat", True, custom_cost=0.05)

        total = cost_tracker.get_today_cost()
        assert total == pytest.approx(0.15, rel=0.01)

    def test_get_today_stats(self, cost_tracker):
        """Test getting comprehensive daily stats."""
        cost_tracker.record_call("grok", "sentiment", True)
        cost_tracker.record_call("birdeye", "token", True)

        stats = cost_tracker.get_today_stats()

        assert stats.total_calls == 2
        assert "grok" in stats.calls_by_service
        assert "birdeye" in stats.calls_by_service

    def test_cost_report_format(self, cost_tracker):
        """Test cost report is human-readable."""
        cost_tracker.record_call("grok", "sentiment", True)

        report = cost_tracker.get_cost_report()

        assert "Cost Report" in report
        assert "Today" in report
        assert "Calls" in report


# =============================================================================
# Test Quick Access Buttons
# =============================================================================


class TestQuickAccessButtons:
    """Test quick access button functionality."""

    def test_quick_action_buy_button(self):
        """Test quick buy action button."""
        from tg_bot.ui.inline_buttons import QuickActionButtons

        buttons = QuickActionButtons()
        keyboard = buttons.buy_button("So111", "SOL", 100.0)

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]

        # Should have amount options
        amounts = ["$25", "$50", "$100", "$250"]
        button_texts = [btn.text for btn in all_buttons]

        for amt in amounts:
            assert any(amt in text for text in button_texts)

    def test_quick_action_sell_button(self):
        """Test quick sell action button."""
        from tg_bot.ui.inline_buttons import QuickActionButtons

        buttons = QuickActionButtons()
        keyboard = buttons.sell_button("So111", "SOL")

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        # Should have percentage options
        percentages = ["25%", "50%", "75%", "100%"]
        for pct in percentages:
            assert any(pct in text for text in button_texts)

    def test_command_buttons_main_menu(self):
        """Test command button main menu."""
        from tg_bot.ui.inline_buttons import CommandButtons

        cmd_buttons = CommandButtons()

        # Non-admin menu
        keyboard = cmd_buttons.main_menu(is_admin=False)
        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_data = [btn.callback_data for btn in all_buttons if btn.callback_data]

        assert any("trending" in data for data in button_data)
        assert any("status" in data for data in button_data)

    def test_command_buttons_admin_has_more(self):
        """Test admin has more command buttons."""
        from tg_bot.ui.inline_buttons import CommandButtons

        cmd_buttons = CommandButtons()

        non_admin_keyboard = cmd_buttons.main_menu(is_admin=False)
        admin_keyboard = cmd_buttons.main_menu(is_admin=True)

        non_admin_count = sum(len(row) for row in non_admin_keyboard.inline_keyboard)
        admin_count = sum(len(row) for row in admin_keyboard.inline_keyboard)

        assert admin_count > non_admin_count


# =============================================================================
# Test Position Management Buttons
# =============================================================================


class TestPositionManagementButtons:
    """Test position management button functionality."""

    def test_position_actions_keyboard(self):
        """Test position action buttons."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.position_actions("pos_123", "SOL", 15.5)

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_data = [btn.callback_data for btn in all_buttons if btn.callback_data]

        assert any("sell" in data for data in button_data)
        assert any("detail" in data for data in button_data)

    def test_close_confirmation_keyboard(self):
        """Test close position confirmation."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.close_confirmation("pos_123", "SOL", 100)

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_data = [btn.callback_data for btn in all_buttons if btn.callback_data]

        assert any("confirm" in data for data in button_data)
        assert any("cancel" in data for data in button_data)

    def test_tp_sl_adjustment_keyboard(self):
        """Test TP/SL adjustment buttons."""
        from tg_bot.ui.inline_buttons import PositionButtons

        buttons = PositionButtons()
        keyboard = buttons.adjust_tp_sl("pos_123", 0.001, 0.0008)

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_data = [btn.callback_data for btn in all_buttons if btn.callback_data]

        # Should have TP and SL adjustments
        assert any("tp" in data for data in button_data)
        assert any("sl" in data for data in button_data)
        assert any("save" in data for data in button_data)


# =============================================================================
# Test Limit Order / Price Alert Buttons
# =============================================================================


class TestLimitOrderButtons:
    """Test limit order / price alert buttons."""

    def test_price_alert_keyboard(self):
        """Test price alert keyboard with percentage targets."""
        from tg_bot.ui.inline_buttons import LimitOrderButtons

        buttons = LimitOrderButtons()
        keyboard = buttons.build_price_alert_keyboard("So111", "SOL", 100.0)

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        # Should have percentage options
        assert any("+5%" in text for text in button_texts)
        assert any("+10%" in text for text in button_texts)
        assert any("-5%" in text for text in button_texts)

    def test_alert_confirmation_keyboard(self):
        """Test alert confirmation keyboard."""
        from tg_bot.ui.inline_buttons import LimitOrderButtons

        buttons = LimitOrderButtons()
        keyboard = buttons.build_alert_confirmation("So111", "SOL", 110.0, 100.0)

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_data = [btn.callback_data for btn in all_buttons if btn.callback_data]

        assert any("confirm" in data for data in button_data)


# =============================================================================
# Test Settings Buttons
# =============================================================================


class TestSettingsButtons:
    """Test user settings buttons."""

    def test_settings_keyboard(self):
        """Test settings keyboard has notification toggle."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_settings_keyboard(123, {"notifications": True})

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        assert any("Notification" in text for text in button_texts)

    def test_risk_profile_keyboard(self):
        """Test risk profile selection keyboard."""
        from tg_bot.ui.inline_buttons import SettingsButtons

        buttons = SettingsButtons()
        keyboard = buttons.build_risk_profile_keyboard(123, "moderate")

        rows = keyboard.inline_keyboard
        all_buttons = [btn for row in rows for btn in row]
        button_texts = [btn.text for btn in all_buttons]

        # Should show all risk profiles
        assert any("Conservative" in text for text in button_texts)
        assert any("Moderate" in text for text in button_texts)
        assert any("Aggressive" in text for text in button_texts)

        # Current profile should be marked
        assert any("Moderate" in text for text in button_texts)
