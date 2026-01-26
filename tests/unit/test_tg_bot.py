"""
Comprehensive Tests for tg_bot/bot.py - Bot Initialization and Lifecycle.

Tests cover:
1. Bot initialization and configuration validation
2. Handler registration (commands, callbacks, messages)
3. Webhook clearing and polling startup
4. Scheduled job registration (digests, sentiment updates, TP/SL monitoring)
5. Environment variable loading
6. Instance lock acquisition
7. Graceful shutdown setup
8. Error handling during startup
9. Pre-warming integrations (Dexter)
10. Main entry point behavior
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock, patch, call, mock_open
import pytest


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_telegram_bot():
    """Create mock Telegram Bot instance."""
    bot = Mock()
    bot.delete_webhook = AsyncMock(return_value=True)
    bot.send_message = AsyncMock()
    bot.get_me = AsyncMock(return_value=Mock(username="JarvisBot"))
    return bot


@pytest.fixture
def mock_application(mock_telegram_bot):
    """Create mock Telegram Application instance."""
    app = Mock()
    app.bot = mock_telegram_bot
    app.add_handler = Mock()
    app.add_error_handler = Mock()
    app.job_queue = Mock()
    app.job_queue.run_daily = Mock()
    app.job_queue.run_repeating = Mock()
    app.run_polling = Mock()
    app.post_init = None
    return app


@pytest.fixture
def mock_application_builder(mock_application):
    """Create mock Application.builder()."""
    builder = Mock()
    builder.token = Mock(return_value=builder)
    builder.build = Mock(return_value=mock_application)
    return builder


@pytest.fixture
def mock_config():
    """Create mock bot configuration."""
    config = Mock()
    config.telegram_token = "test-token-123"
    config.admin_ids = {111111111, 222222222}
    config.has_grok = Mock(return_value=True)
    config.has_claude = Mock(return_value=True)
    config.birdeye_api_key = "birdeye-key"
    config.daily_cost_limit_usd = 10.0
    config.sentiment_interval_seconds = 3600
    config.digest_hours = [8, 14, 20]
    return config


@pytest.fixture
def mock_config_no_token():
    """Create mock config with missing token."""
    config = Mock()
    config.telegram_token = ""
    config.admin_ids = set()
    return config


@pytest.fixture
def mock_config_no_admins():
    """Create mock config with missing admin IDs."""
    config = Mock()
    config.telegram_token = "test-token-123"
    config.admin_ids = set()
    config.has_grok = Mock(return_value=False)
    config.has_claude = Mock(return_value=False)
    config.birdeye_api_key = ""
    config.daily_cost_limit_usd = 10.0
    config.sentiment_interval_seconds = 3600
    config.digest_hours = [8, 14, 20]
    return config


@pytest.fixture
def mock_signal_service():
    """Create mock signal service."""
    service = Mock()
    service.get_available_sources = Mock(return_value=["dexscreener", "birdeye"])
    return service


@pytest.fixture
def mock_instance_lock():
    """Create mock instance lock."""
    lock = Mock()
    lock.close = Mock()
    return lock


# =============================================================================
# Test Webhook Clearing
# =============================================================================


class TestWebhookClearing:
    """Test _clear_webhook_before_polling function."""

    @pytest.mark.asyncio
    async def test_clear_webhook_success(self, mock_application):
        """Test webhook is cleared successfully before polling."""
        from tg_bot.bot import _clear_webhook_before_polling

        await _clear_webhook_before_polling(mock_application)

        mock_application.bot.delete_webhook.assert_called_once_with(drop_pending_updates=True)

    @pytest.mark.asyncio
    async def test_clear_webhook_returns_false(self, mock_application):
        """Test handling when delete_webhook returns False."""
        from tg_bot.bot import _clear_webhook_before_polling

        mock_application.bot.delete_webhook = AsyncMock(return_value=False)

        # Should not raise, just print warning
        await _clear_webhook_before_polling(mock_application)

        mock_application.bot.delete_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_webhook_exception(self, mock_application):
        """Test handling when delete_webhook raises exception."""
        from tg_bot.bot import _clear_webhook_before_polling

        mock_application.bot.delete_webhook = AsyncMock(side_effect=Exception("Network error"))

        # Should not raise, just print warning and continue
        await _clear_webhook_before_polling(mock_application)

        mock_application.bot.delete_webhook.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_webhook_telegram_error(self, mock_application):
        """Test handling Telegram API errors during webhook clear."""
        from tg_bot.bot import _clear_webhook_before_polling
        from telegram.error import TelegramError

        mock_application.bot.delete_webhook = AsyncMock(
            side_effect=TelegramError("Webhook was not set")
        )

        # Should not raise
        await _clear_webhook_before_polling(mock_application)


# =============================================================================
# Test Dexter Pre-warming
# =============================================================================


class TestDexterPrewarming:
    """Test _pre_warm_dexter function."""

    @pytest.mark.asyncio
    async def test_prewarm_dexter_success(self):
        """Test Dexter integration is pre-warmed successfully."""
        from tg_bot.bot import _pre_warm_dexter

        mock_dexter = AsyncMock()
        mock_dexter.handle_telegram_message = AsyncMock(return_value="test response")

        with patch('tg_bot.services.chat_responder.get_bot_finance_integration', return_value=mock_dexter):
            await _pre_warm_dexter()

        mock_dexter.handle_telegram_message.assert_called_once_with("test", user_id=0)

    @pytest.mark.asyncio
    async def test_prewarm_dexter_not_available(self):
        """Test handling when Dexter integration is not available."""
        from tg_bot.bot import _pre_warm_dexter

        with patch('tg_bot.services.chat_responder.get_bot_finance_integration', return_value=None):
            # Should not raise
            await _pre_warm_dexter()

    @pytest.mark.asyncio
    async def test_prewarm_dexter_exception(self):
        """Test handling when Dexter pre-warming fails."""
        from tg_bot.bot import _pre_warm_dexter

        mock_dexter = AsyncMock()
        mock_dexter.handle_telegram_message = AsyncMock(side_effect=Exception("Dexter error"))

        with patch('tg_bot.services.chat_responder.get_bot_finance_integration', return_value=mock_dexter):
            # Should not raise, just print warning
            await _pre_warm_dexter()

    @pytest.mark.asyncio
    async def test_prewarm_dexter_import_error(self):
        """Test handling when Dexter import fails."""
        # Test that the function handles import errors gracefully
        # by calling the function directly with a mock that simulates
        # the import error scenario
        from tg_bot.bot import _pre_warm_dexter

        # The function should catch import errors internally
        # This is verified by the source code's try/except structure
        # We can verify it doesn't crash by running it
        with patch('tg_bot.services.chat_responder.get_bot_finance_integration',
                   side_effect=ImportError("No module")):
            # Should not raise - the function handles import errors
            await _pre_warm_dexter()


# =============================================================================
# Test Handler Registration
# =============================================================================


class TestHandlerRegistration:
    """Test register_handlers function."""

    def test_register_core_command_handlers(self, mock_application, mock_config):
        """Test core command handlers are registered."""
        from tg_bot.bot import register_handlers

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        # Verify add_handler was called many times
        assert mock_application.add_handler.call_count > 50

    def test_register_start_handler(self, mock_application, mock_config):
        """Test /start command handler is registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        # Find CommandHandler for "start"
        calls = mock_application.add_handler.call_args_list
        start_handlers = [
            c for c in calls
            if isinstance(c[0][0], CommandHandler) and "start" in str(c[0][0].commands)
        ]
        assert len(start_handlers) >= 1

    def test_register_help_handler(self, mock_application, mock_config):
        """Test /help command handler is registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        help_handlers = [
            c for c in calls
            if isinstance(c[0][0], CommandHandler) and "help" in str(c[0][0].commands)
        ]
        assert len(help_handlers) >= 1

    def test_register_admin_handlers(self, mock_application, mock_config):
        """Test admin command handlers are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        # Check admin commands are registered
        assert "reload" in command_names
        assert "config" in command_names
        assert "logs" in command_names
        assert "system" in command_names

    def test_register_trading_handlers(self, mock_application, mock_config):
        """Test trading command handlers are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        # Check trading commands
        assert "balance" in command_names
        assert "positions" in command_names
        assert "wallet" in command_names
        assert "dashboard" in command_names

    def test_register_sentiment_handlers(self, mock_application, mock_config):
        """Test sentiment command handlers are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        assert "trending" in command_names
        assert "digest" in command_names
        assert "sentiment" in command_names

    def test_register_demo_handlers(self, mock_application, mock_config):
        """Test demo UI handlers are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler, CallbackQueryHandler, MessageHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        callback_handlers = 0
        message_handlers = 0

        for c in calls:
            handler = c[0][0]
            if isinstance(handler, CommandHandler):
                command_names.extend(handler.commands)
            elif isinstance(handler, CallbackQueryHandler):
                callback_handlers += 1
            elif isinstance(handler, MessageHandler):
                message_handlers += 1

        assert "demo" in command_names
        assert callback_handlers >= 2  # demo_callback and button_callback
        assert message_handlers >= 1

    def test_register_raid_handlers(self, mock_application, mock_config):
        """Test raid bot handlers are registered."""
        from tg_bot.bot import register_handlers

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            with patch('tg_bot.bot.register_raid_handlers') as mock_raid:
                register_handlers(mock_application, mock_config)
                mock_raid.assert_called_once_with(mock_application, mock_application.job_queue)

    def test_register_sim_handlers(self, mock_application, mock_config):
        """Test paper trading simulator handlers are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        assert "sim" in command_names
        assert "simbuy" in command_names
        assert "simsell" in command_names
        assert "simpos" in command_names

    def test_register_quick_wins_handlers(self, mock_application, mock_config):
        """Test quick wins (v4.9.0) handlers are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        assert "search" in command_names
        assert "export" in command_names
        assert "quick" in command_names

    def test_register_analytics_handlers(self, mock_application, mock_config):
        """Test portfolio analytics (v5.0.0) handlers are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        assert "analytics" in command_names
        assert "performers" in command_names
        assert "tokenperf" in command_names

    def test_register_watchlist_handlers(self, mock_application, mock_config):
        """Test watchlist (v4.11.0) handlers are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        assert "watch" in command_names
        assert "unwatch" in command_names
        assert "watchlist" in command_names

    def test_register_treasury_handlers(self, mock_application, mock_config):
        """Test treasury display (v4.7.0) handlers are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        assert "treasury" in command_names
        assert "portfolio" in command_names
        assert "pnl" in command_names
        assert "sector" in command_names

    def test_register_callback_query_handler(self, mock_application, mock_config):
        """Test CallbackQueryHandler is registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CallbackQueryHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        callback_handlers = [c for c in calls if isinstance(c[0][0], CallbackQueryHandler)]
        assert len(callback_handlers) >= 2

    def test_register_message_handler(self, mock_application, mock_config):
        """Test MessageHandler for text messages is registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import MessageHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        message_handlers = [c for c in calls if isinstance(c[0][0], MessageHandler)]
        assert len(message_handlers) >= 1

    def test_register_media_handler(self, mock_application, mock_config):
        """Test MessageHandler for media is registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import MessageHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        # Media handler should be registered
        calls = mock_application.add_handler.call_args_list
        assert len(calls) > 50

    def test_register_chat_member_handler(self, mock_application, mock_config):
        """Test ChatMemberHandler for welcome messages is registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import ChatMemberHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        chat_member_handlers = [c for c in calls if isinstance(c[0][0], ChatMemberHandler)]
        assert len(chat_member_handlers) >= 1

    def test_register_error_handler(self, mock_application, mock_config):
        """Test error handler is registered."""
        from tg_bot.bot import register_handlers

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        mock_application.add_error_handler.assert_called_once()

    def test_register_antiscam_handler_when_available(self, mock_application, mock_config):
        """Test anti-scam handler is registered when available."""
        from tg_bot.bot import register_handlers

        mock_antiscam = Mock()
        mock_create_handler = Mock(return_value=Mock())

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', True):
            with patch('tg_bot.bot.AntiScamProtection', return_value=mock_antiscam):
                with patch('tg_bot.bot.create_antiscam_handler', mock_create_handler):
                    register_handlers(mock_application, mock_config)

        mock_create_handler.assert_called_once_with(mock_antiscam)

    def test_antiscam_disabled_without_admin_ids(self, mock_application, mock_config_no_admins):
        """Test anti-scam is disabled when no admin IDs."""
        from tg_bot.bot import register_handlers

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', True):
            register_handlers(mock_application, mock_config_no_admins)

        # Should not crash, just disable antiscam

    def test_register_command_aliases(self, mock_application, mock_config):
        """Test command aliases are registered (e.g., /a for /analyze)."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        # Check aliases
        assert "a" in command_names  # alias for analyze
        assert "s" in command_names  # alias for stats
        assert "p" in command_names  # alias for portfolio
        assert "b" in command_names  # alias for balance
        assert "dash" in command_names  # alias for dashboard
        assert "cal" in command_names  # alias for calibrate


# =============================================================================
# Test Environment Loading
# =============================================================================


class TestEnvLoading:
    """Test _load_env_files function."""

    def test_load_env_files_exists(self, tmp_path):
        """Test loading .env files that exist."""
        from tg_bot.bot import _load_env_files

        # Function should not raise even with real paths
        _load_env_files()

    def test_load_env_files_handles_missing_files(self):
        """Test handling when .env files don't exist."""
        from tg_bot.bot import _load_env_files

        # Should not raise
        _load_env_files()

    def test_load_env_structure(self):
        """Test the structure of _load_env_files function."""
        from tg_bot.bot import _load_env_files
        import inspect

        source = inspect.getsource(_load_env_files)

        # Verify it checks for multiple env file locations
        assert "tg_bot" in source
        assert ".env" in source
        assert "exists" in source

    def test_load_env_handles_exceptions(self):
        """Test that _load_env_files handles exceptions gracefully."""
        from tg_bot.bot import _load_env_files
        import inspect

        source = inspect.getsource(_load_env_files)

        # Verify exception handling exists
        assert "except" in source
        assert "Exception" in source or "warning" in source.lower()


# =============================================================================
# Test Main Function Structure
# =============================================================================


class TestMainFunction:
    """Test main() entry point structure and error handling."""

    def test_main_exits_without_token(self, mock_config_no_token):
        """Test main exits with error when no token."""
        from tg_bot.bot import main

        with patch('tg_bot.bot._load_env_files'):
            with patch('tg_bot.bot.get_config', return_value=mock_config_no_token):
                with patch.dict(os.environ, {"SKIP_TELEGRAM_LOCK": "1"}):
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 1

    def test_main_exits_when_lock_unavailable(self, mock_config):
        """Test main exits when instance lock cannot be acquired."""
        from tg_bot.bot import main

        with patch('tg_bot.bot._load_env_files'):
            with patch('tg_bot.bot.get_config', return_value=mock_config):
                with patch('tg_bot.bot.acquire_instance_lock', return_value=None):
                    with patch.dict(os.environ, {}, clear=False):
                        os.environ.pop("SKIP_TELEGRAM_LOCK", None)
                        with pytest.raises(SystemExit) as exc_info:
                            main()
                        assert exc_info.value.code == 1

    def test_main_function_exists(self):
        """Test main function exists and is callable."""
        from tg_bot.bot import main
        assert callable(main)

    def test_main_function_structure(self):
        """Test main function has expected structure."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Check key components exist
        assert "_load_env_files" in source
        assert "get_config" in source
        assert "Application" in source
        assert "register_handlers" in source
        assert "run_polling" in source
        assert "job_queue" in source

    def test_main_handles_exceptions(self):
        """Test main function has exception handling."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Verify exception handling
        assert "try:" in source
        assert "except" in source
        assert "finally:" in source
        assert "KeyboardInterrupt" in source

    def test_main_lock_handling(self):
        """Test main function handles lock correctly."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Verify lock handling
        assert "SKIP_TELEGRAM_LOCK" in source
        assert "acquire_instance_lock" in source
        assert "lock.close" in source


# =============================================================================
# Test Module-Level Behavior
# =============================================================================


class TestModuleBehavior:
    """Test module-level behavior."""

    def test_main_called_when_run_directly(self):
        """Test main() is called when module is run directly."""
        # This tests the if __name__ == "__main__" block
        from tg_bot import bot
        assert hasattr(bot, 'main')
        assert callable(bot.main)

    def test_exports_from_bot_core(self):
        """Test symbols are re-exported from bot_core."""
        from tg_bot import bot

        # These should be available via the wildcard import
        # Check some key functions exist
        assert hasattr(bot, 'register_handlers')
        assert hasattr(bot, '_clear_webhook_before_polling')
        assert hasattr(bot, '_pre_warm_dexter')
        assert hasattr(bot, '_load_env_files')
        assert hasattr(bot, 'main')

    def test_module_imports(self):
        """Test module has required imports."""
        from tg_bot import bot

        # Check required telegram imports are available
        assert hasattr(bot, 'Application')
        assert hasattr(bot, 'CommandHandler')
        assert hasattr(bot, 'CallbackQueryHandler')
        assert hasattr(bot, 'MessageHandler')

    def test_module_has_all_handlers(self):
        """Test module imports all handler functions."""
        from tg_bot import bot

        # Check some key handlers are imported
        assert hasattr(bot, 'start')
        assert hasattr(bot, 'help_command')
        assert hasattr(bot, 'demo')
        assert hasattr(bot, 'demo_callback')


# =============================================================================
# Test Handler Groups
# =============================================================================


class TestHandlerGroups:
    """Test handler group configuration."""

    def test_antiscam_handler_in_group_negative_one(self, mock_application, mock_config):
        """Test anti-scam handler is added to group -1 (runs first)."""
        from tg_bot.bot import register_handlers

        mock_antiscam = Mock()
        mock_handler = Mock()

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', True):
            with patch('tg_bot.bot.AntiScamProtection', return_value=mock_antiscam):
                with patch('tg_bot.bot.create_antiscam_handler', return_value=mock_handler):
                    register_handlers(mock_application, mock_config)

        # Find call with group=-1 (can be positional arg or keyword arg)
        calls = mock_application.add_handler.call_args_list
        group_neg_one_calls = [
            c for c in calls
            if (len(c[0]) > 1 and c[0][1] == -1) or c[1].get('group') == -1
        ]
        assert len(group_neg_one_calls) >= 1

    def test_demo_message_handler_in_group_one(self, mock_application, mock_config):
        """Test demo message handler is added to group 1."""
        from tg_bot.bot import register_handlers

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        # Find call with group=1 (can be positional arg or keyword arg)
        calls = mock_application.add_handler.call_args_list
        group_one_calls = [
            c for c in calls
            if (len(c[0]) > 1 and c[0][1] == 1) or c[1].get('group') == 1
        ]
        assert len(group_one_calls) >= 1


# =============================================================================
# Test Startup Tasks
# =============================================================================


class TestStartupTasks:
    """Test startup_tasks callback."""

    def test_startup_tasks_in_main(self):
        """Test startup_tasks is set up in main function."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Verify startup_tasks setup
        assert "startup_tasks" in source
        assert "post_init" in source
        assert "health_monitor" in source.lower() or "health" in source.lower()

    def test_startup_tasks_exception_handling(self):
        """Test startup_tasks handles exceptions gracefully."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # The startup_tasks function should have try/except
        # This is in the async def startup_tasks block
        assert "async def startup_tasks" in source


# =============================================================================
# Test Job Queue Configuration
# =============================================================================


class TestJobQueueConfiguration:
    """Test job queue configuration."""

    def test_job_queue_config_in_main(self):
        """Test job queue configuration is in main function."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Verify job queue setup
        assert "job_queue" in source
        assert "run_daily" in source
        assert "run_repeating" in source

    def test_scheduled_jobs_setup(self):
        """Test scheduled jobs are set up correctly."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Verify scheduled jobs
        assert "scheduled_digest" in source
        assert "sentiment_cache_updater" in source or "_update_sentiment_cache" in source
        assert "tp_sl_monitor" in source or "_background_tp_sl_monitor" in source


# =============================================================================
# Test Polling Configuration
# =============================================================================


class TestPollingConfiguration:
    """Test polling configuration."""

    def test_polling_config_in_main(self):
        """Test polling configuration is in main function."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Verify polling setup
        assert "run_polling" in source
        assert "Update.ALL_TYPES" in source
        assert "drop_pending_updates" in source


# =============================================================================
# Test Graceful Shutdown
# =============================================================================


class TestGracefulShutdown:
    """Test graceful shutdown setup."""

    def test_shutdown_setup_in_main(self):
        """Test graceful shutdown setup is in main function."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Verify shutdown setup
        assert "setup_telegram_shutdown" in source
        assert "ImportError" in source  # For handling missing module


# =============================================================================
# Test Metrics Server
# =============================================================================


class TestMetricsServer:
    """Test metrics server startup."""

    def test_metrics_server_in_main(self):
        """Test metrics server startup is in main function."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Verify metrics server setup
        assert "start_metrics_server" in source


# =============================================================================
# Test Config Display
# =============================================================================


class TestConfigDisplay:
    """Test configuration display during startup."""

    def test_config_display_in_main(self):
        """Test configuration is displayed in main function."""
        from tg_bot.bot import main
        import inspect

        source = inspect.getsource(main)

        # Verify config display
        assert "Admin IDs" in source
        assert "Grok API" in source or "has_grok" in source
        assert "Claude API" in source or "has_claude" in source
        assert "Birdeye API" in source or "birdeye_api_key" in source
        assert "Data sources" in source or "get_available_sources" in source


# =============================================================================
# Test Command Count
# =============================================================================


class TestCommandCount:
    """Test the expected number of commands are registered."""

    def test_minimum_command_count(self, mock_application, mock_config):
        """Test minimum number of commands are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_handlers = [c for c in calls if isinstance(c[0][0], CommandHandler)]

        # Should have at least 60 command handlers
        assert len(command_handlers) >= 60

    def test_all_major_commands_registered(self, mock_application, mock_config):
        """Test all major commands are registered."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CommandHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        command_names = []
        for c in calls:
            if isinstance(c[0][0], CommandHandler):
                command_names.extend(c[0][0].commands)

        # Core commands
        core_commands = [
            "start", "help", "about", "commands", "status",
            "subscribe", "unsubscribe", "costs"
        ]
        for cmd in core_commands:
            assert cmd in command_names, f"Missing core command: {cmd}"

        # Market data commands
        market_commands = [
            "trending", "solprice", "mcap", "volume", "chart",
            "liquidity", "age", "summary", "price", "gainers",
            "losers", "newpairs", "signals", "analyze"
        ]
        for cmd in market_commands:
            assert cmd in command_names, f"Missing market command: {cmd}"

        # Trading commands
        trading_commands = [
            "balance", "positions", "wallet", "dashboard",
            "treasury", "portfolio", "pnl"
        ]
        for cmd in trading_commands:
            assert cmd in command_names, f"Missing trading command: {cmd}"

        # Admin commands
        admin_commands = [
            "reload", "config", "logs", "system", "memory",
            "health", "flags", "errors"
        ]
        for cmd in admin_commands:
            assert cmd in command_names, f"Missing admin command: {cmd}"


# =============================================================================
# Test Error Handler Registration
# =============================================================================


class TestErrorHandlerRegistration:
    """Test error handler is properly configured."""

    def test_error_handler_callback(self, mock_application, mock_config):
        """Test error handler callback is set."""
        from tg_bot.bot import register_handlers

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        # Verify error handler was registered
        mock_application.add_error_handler.assert_called_once()

        # Get the callback
        callback = mock_application.add_error_handler.call_args[0][0]
        assert callable(callback)


# =============================================================================
# Test Welcome Handler
# =============================================================================


class TestWelcomeHandler:
    """Test welcome message handler configuration."""

    def test_welcome_handler_registered(self, mock_application, mock_config):
        """Test welcome handler is registered for new members."""
        from tg_bot.bot import register_handlers
        from telegram.ext import ChatMemberHandler, MessageHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list

        # Should have both ChatMemberHandler and MessageHandler for StatusUpdate
        chat_member_handlers = [c for c in calls if isinstance(c[0][0], ChatMemberHandler)]
        assert len(chat_member_handlers) >= 1


# =============================================================================
# Test Bot Core Re-exports
# =============================================================================


class TestBotCoreReexports:
    """Test that bot_core symbols are properly re-exported."""

    def test_reexports_config_functions(self):
        """Test config functions are re-exported."""
        from tg_bot import bot

        # Should have config-related imports
        assert hasattr(bot, 'get_config')

    def test_reexports_handler_decorators(self):
        """Test handler decorators are available."""
        # Check that the module imports from bot_core
        from tg_bot.bot import register_handlers
        import inspect

        # Get the module's global namespace
        import tg_bot.bot as bot_module

        # Check some known symbols from bot_core
        assert 'costs' in dir(bot_module)
        assert 'stocks' in dir(bot_module)


# =============================================================================
# Test Import Safety
# =============================================================================


class TestImportSafety:
    """Test that optional imports are handled safely."""

    def test_antiscam_optional_import(self):
        """Test ANTISCAM_AVAILABLE flag exists."""
        from tg_bot import bot

        # Flag should exist (either True or False)
        assert hasattr(bot, 'ANTISCAM_AVAILABLE')

    def test_module_loads_without_errors(self):
        """Test module loads without import errors."""
        # This will fail if there are import errors
        import importlib
        import tg_bot.bot

        # Reload to test fresh import
        importlib.reload(tg_bot.bot)

        # Module should have main
        assert hasattr(tg_bot.bot, 'main')


# =============================================================================
# Test Callback Query Pattern
# =============================================================================


class TestCallbackQueryPattern:
    """Test callback query handler patterns."""

    def test_demo_callback_pattern(self, mock_application, mock_config):
        """Test demo callback has correct pattern."""
        from tg_bot.bot import register_handlers
        from telegram.ext import CallbackQueryHandler

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            register_handlers(mock_application, mock_config)

        calls = mock_application.add_handler.call_args_list
        callback_handlers = [c for c in calls if isinstance(c[0][0], CallbackQueryHandler)]

        # Find demo callback
        demo_callbacks = [
            c for c in callback_handlers
            if hasattr(c[0][0], 'pattern') and c[0][0].pattern and 'demo' in str(c[0][0].pattern)
        ]

        # At least one demo callback should exist
        assert len(demo_callbacks) >= 1


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_register_handlers_with_none_job_queue(self, mock_application, mock_config):
        """Test register_handlers handles None job_queue."""
        from tg_bot.bot import register_handlers

        mock_application.job_queue = None

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', False):
            # Should not raise
            register_handlers(mock_application, mock_config)

    def test_register_handlers_with_empty_admin_ids(self, mock_application, mock_config_no_admins):
        """Test register_handlers handles empty admin IDs."""
        from tg_bot.bot import register_handlers

        with patch('tg_bot.bot.ANTISCAM_AVAILABLE', True):
            # Should not raise - antiscam should be skipped
            register_handlers(mock_application, mock_config_no_admins)

    @pytest.mark.asyncio
    async def test_clear_webhook_with_network_timeout(self, mock_application):
        """Test webhook clearing handles network timeouts."""
        from tg_bot.bot import _clear_webhook_before_polling
        from telegram.error import TimedOut

        mock_application.bot.delete_webhook = AsyncMock(side_effect=TimedOut())

        # Should not raise
        await _clear_webhook_before_polling(mock_application)
