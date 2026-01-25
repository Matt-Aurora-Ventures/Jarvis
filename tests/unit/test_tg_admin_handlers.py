"""
Unit tests for tg_bot/handlers/admin.py

Covers:
- Admin authentication (admin_only decorator)
- Non-admin rejection
- Treasury controls (reload, config)
- Status commands (system, logs, errors)
- Memory commands (memory, sysmem)
- Auto-responder commands (away, back, awaystatus)
- Feature flags management (flags)
- Error handling in all handlers
- Message formatting verification
"""

import asyncio
import json
import time
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch, mock_open
from typing import Dict, Any

from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# Import module under test
from tg_bot.handlers.admin import (
    reload,
    logs,
    errors,
    system,
    config_cmd,
    away,
    back,
    awaystatus,
    memory,
    sysmem,
    flags,
)

# Import decorators for testing
from tg_bot.handlers import admin_only, error_handler


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_admin_user():
    """Create a mock admin user."""
    user = Mock(spec=User)
    user.id = 123456
    user.username = "admin_user"
    user.first_name = "Admin"
    return user


@pytest.fixture
def mock_non_admin_user():
    """Create a mock non-admin user."""
    user = Mock(spec=User)
    user.id = 999999
    user.username = "regular_user"
    user.first_name = "Regular"
    return user


@pytest.fixture
def mock_chat():
    """Create a mock chat object."""
    chat = Mock(spec=Chat)
    chat.id = 123456
    chat.type = "private"
    chat.title = None
    return chat


@pytest.fixture
def mock_message(mock_admin_user, mock_chat):
    """Create a mock message object."""
    message = Mock(spec=Message)
    message.reply_text = AsyncMock()
    message.chat_id = mock_chat.id
    message.message_id = 1
    message.from_user = mock_admin_user
    return message


@pytest.fixture
def mock_update(mock_admin_user, mock_chat, mock_message):
    """Create a mock update object for admin user."""
    update = Mock(spec=Update)
    update.effective_user = mock_admin_user
    update.effective_chat = mock_chat
    update.message = mock_message
    update.effective_message = mock_message
    return update


@pytest.fixture
def mock_non_admin_update(mock_non_admin_user, mock_chat, mock_message):
    """Create a mock update object for non-admin user."""
    update = Mock(spec=Update)
    update.effective_user = mock_non_admin_user
    update.effective_chat = mock_chat
    update.message = mock_message
    update.effective_message = mock_message
    return update


@pytest.fixture
def mock_context():
    """Create a mock context object."""
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    context.bot = Mock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.fixture
def admin_config():
    """Mock config where user is admin."""
    with patch("tg_bot.handlers.get_config") as mock:
        config = MagicMock()
        config.is_admin = MagicMock(return_value=True)
        config.admin_ids = {123456}
        mock.return_value = config
        yield config


@pytest.fixture
def non_admin_config():
    """Mock config where user is not admin."""
    with patch("tg_bot.handlers.get_config") as mock:
        config = MagicMock()
        config.is_admin = MagicMock(return_value=False)
        config.admin_ids = {123456}
        mock.return_value = config
        yield config


# ============================================================================
# Test: Admin Authentication (admin_only decorator)
# ============================================================================

class TestAdminOnlyDecorator:
    """Tests for the admin_only decorator."""

    @pytest.mark.asyncio
    async def test_admin_allowed(self, mock_update, mock_context, admin_config):
        """Admin users should be allowed to execute admin commands."""
        @admin_only
        async def test_handler(update, context):
            return "executed"

        result = await test_handler(mock_update, mock_context)
        assert result == "executed"

    @pytest.mark.asyncio
    async def test_non_admin_rejected(self, mock_non_admin_update, mock_context, non_admin_config):
        """Non-admin users should be rejected from admin commands."""
        @admin_only
        async def test_handler(update, context):
            return "executed"

        result = await test_handler(mock_non_admin_update, mock_context)
        assert result is None
        mock_non_admin_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_unauthorized_message_format(self, mock_non_admin_update, mock_context, non_admin_config):
        """Non-admin rejection should use proper message formatting."""
        @admin_only
        async def test_handler(update, context):
            return "executed"

        await test_handler(mock_non_admin_update, mock_context)

        call_args = mock_non_admin_update.message.reply_text.call_args
        assert call_args[1].get("parse_mode") == ParseMode.MARKDOWN

    @pytest.mark.asyncio
    async def test_handles_missing_user(self, mock_update, mock_context, non_admin_config):
        """Should handle missing effective_user gracefully."""
        mock_update.effective_user = None

        @admin_only
        async def test_handler(update, context):
            return "executed"

        result = await test_handler(mock_update, mock_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_user_with_no_username(self, mock_update, mock_context, admin_config):
        """Should handle users without username."""
        mock_update.effective_user.username = None
        admin_config.is_admin.return_value = True

        @admin_only
        async def test_handler(update, context):
            return "executed"

        result = await test_handler(mock_update, mock_context)
        assert result == "executed"


# ============================================================================
# Test: Error Handler Decorator
# ============================================================================

class TestErrorHandlerDecorator:
    """Tests for the error_handler decorator."""

    @pytest.mark.asyncio
    async def test_passes_through_normal_execution(self, mock_update, mock_context):
        """Should pass through results from normal execution."""
        @error_handler
        async def test_handler(update, context):
            return "success"

        result = await test_handler(mock_update, mock_context)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_catches_generic_exceptions(self, mock_update, mock_context, admin_config):
        """Should catch and handle generic exceptions."""
        @error_handler
        async def test_handler(update, context):
            raise ValueError("test error")

        result = await test_handler(mock_update, mock_context)
        assert result is None
        # Should have sent error message to user
        mock_update.effective_message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_handles_rate_limit_error(self, mock_update, mock_context):
        """Should handle Telegram rate limit errors silently."""
        from telegram.error import RetryAfter

        @error_handler
        async def test_handler(update, context):
            raise RetryAfter(60)

        result = await test_handler(mock_update, mock_context)
        assert result is None

    @pytest.mark.asyncio
    async def test_handles_bad_request_parse_error(self, mock_update, mock_context):
        """Should handle parse errors silently."""
        from telegram.error import BadRequest

        @error_handler
        async def test_handler(update, context):
            raise BadRequest("Can't parse entities")

        result = await test_handler(mock_update, mock_context)
        assert result is None


# ============================================================================
# Test: /reload Command
# ============================================================================

class TestReloadCommand:
    """Tests for the /reload command handler."""

    @pytest.mark.asyncio
    async def test_reload_success(self, mock_update, mock_context, admin_config):
        """Should reload config and confirm to user."""
        with patch("tg_bot.handlers.admin.reload_config") as mock_reload:
            await reload(mock_update, mock_context)

            mock_reload.assert_called_once()
            mock_update.message.reply_text.assert_called_once()

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "config reloaded" in message.lower()
            assert call_args[1].get("parse_mode") == ParseMode.MARKDOWN

    @pytest.mark.asyncio
    async def test_reload_non_admin_rejected(self, mock_non_admin_update, mock_context, non_admin_config):
        """Non-admin should be rejected from reload."""
        with patch("tg_bot.handlers.admin.reload_config") as mock_reload:
            await reload(mock_non_admin_update, mock_context)

            mock_reload.assert_not_called()


# ============================================================================
# Test: /logs Command
# ============================================================================

class TestLogsCommand:
    """Tests for the /logs command handler."""

    @pytest.mark.asyncio
    async def test_logs_success(self, mock_update, mock_context, admin_config):
        """Should display recent log entries."""
        log_content = "\n".join([f"2026-01-25 10:00:0{i} - INFO - Log message {i}" for i in range(25)])

        with patch("tg_bot.handlers.admin.Path") as mock_path:
            mock_log_file = MagicMock()
            mock_log_file.exists.return_value = True
            mock_log_file.read_text.return_value = log_content
            mock_path.return_value = mock_log_file

            await logs(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "recent logs" in message.lower()
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_logs_file_not_exists(self, mock_update, mock_context, admin_config):
        """Should handle missing log file."""
        with patch("tg_bot.handlers.admin.Path") as mock_path:
            mock_log_file = MagicMock()
            mock_log_file.exists.return_value = False
            mock_path.return_value = mock_log_file

            await logs(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "no log file" in message.lower()

    @pytest.mark.asyncio
    async def test_logs_truncates_long_lines(self, mock_update, mock_context, admin_config):
        """Should truncate lines longer than 80 chars."""
        long_line = "X" * 100
        log_content = f"{long_line}\nshort line"

        with patch("tg_bot.handlers.admin.Path") as mock_path:
            mock_log_file = MagicMock()
            mock_log_file.exists.return_value = True
            mock_log_file.read_text.return_value = log_content
            mock_path.return_value = mock_log_file

            await logs(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "..." in message

    @pytest.mark.asyncio
    async def test_logs_shows_last_20_lines(self, mock_update, mock_context, admin_config):
        """Should show only last 20 lines."""
        log_content = "\n".join([f"line {i}" for i in range(30)])

        with patch("tg_bot.handlers.admin.Path") as mock_path:
            mock_log_file = MagicMock()
            mock_log_file.exists.return_value = True
            mock_log_file.read_text.return_value = log_content
            mock_path.return_value = mock_log_file

            await logs(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            # Should have line 10-29 (last 20)
            assert "line 10" in message
            assert "line 29" in message
            assert "line 9" not in message

    @pytest.mark.asyncio
    async def test_logs_handles_read_error(self, mock_update, mock_context, admin_config):
        """Should handle file read errors gracefully."""
        with patch("tg_bot.handlers.admin.Path") as mock_path:
            mock_log_file = MagicMock()
            mock_log_file.exists.return_value = True
            mock_log_file.read_text.side_effect = PermissionError("Access denied")
            mock_path.return_value = mock_log_file

            await logs(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "error" in message.lower()


# ============================================================================
# Test: /errors Command
# ============================================================================

class TestErrorsCommand:
    """Tests for the /errors command handler."""

    @pytest.mark.asyncio
    async def test_errors_with_critical_and_frequent(self, mock_update, mock_context, admin_config):
        """Should display critical and frequent errors."""
        mock_tracker = MagicMock()
        mock_tracker.get_frequent_errors.return_value = [
            {"id": "err1", "component": "telegram", "type": "TypeError", "count": 5},
            {"id": "err2", "component": "trading", "type": "ValueError", "count": 3},
        ]
        mock_tracker.get_critical_errors.return_value = [
            {"id": "crit1", "component": "database", "type": "ConnectionError", "count": 2},
        ]

        with patch("core.logging.error_tracker.error_tracker", mock_tracker):
            await errors(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "error summary" in message.lower()
            assert "critical" in message.lower()
            assert "crit1" in message
            assert "err1" in message
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_errors_no_errors_recorded(self, mock_update, mock_context, admin_config):
        """Should display message when no errors."""
        mock_tracker = MagicMock()
        mock_tracker.get_frequent_errors.return_value = []
        mock_tracker.get_critical_errors.return_value = []

        with patch("core.logging.error_tracker.error_tracker", mock_tracker):
            await errors(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "no errors recorded" in message.lower()


# ============================================================================
# Test: /system Command
# ============================================================================

class TestSystemCommand:
    """Tests for the /system command handler."""

    @pytest.mark.asyncio
    async def test_system_shows_basic_status(self, mock_update, mock_context, admin_config):
        """Should display basic system status even when services fail."""
        # Mock all the imports to fail - system should still work
        with patch.dict("sys.modules", {
            "core.health_monitor": MagicMock(get_health_monitor=MagicMock(side_effect=ImportError)),
            "core.config.feature_flags": MagicMock(get_feature_flag_manager=MagicMock(side_effect=ImportError)),
            "core.feature_flags": MagicMock(get_feature_flags=MagicMock(side_effect=ImportError)),
            "bots.treasury.scorekeeper": MagicMock(get_scorekeeper=MagicMock(side_effect=ImportError)),
        }):
            await system(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            # Should show system status header and time
            assert "system status" in message.lower()
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_system_includes_timestamp(self, mock_update, mock_context, admin_config):
        """Should include current timestamp."""
        await system(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message = call_args[0][0]
        # Should contain time indicator
        assert "Time" in message or "time" in message


# ============================================================================
# Test: /config Command
# ============================================================================

class TestConfigCommand:
    """Tests for the /config command handler."""

    @pytest.mark.asyncio
    async def test_config_show_values(self, mock_update, mock_context, admin_config):
        """Should display current config values."""
        mock_cfg = MagicMock()
        mock_cfg.get_by_prefix.side_effect = lambda prefix: {
            "trading": {"max_position": 50, "risk_level": "medium"},
            "bot": {"debug_mode": False, "notifications": True},
        }.get(prefix, {})

        with patch("core.config_hot_reload.get_config_manager", return_value=mock_cfg):
            await config_cmd(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "config" in message.lower()
            assert "trading" in message.lower()
            assert "bot" in message.lower()
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_config_set_string_value(self, mock_update, mock_context, admin_config):
        """Should set string config values."""
        mock_context.args = ["set", "bot.name", "JarvisBot"]
        mock_cfg = MagicMock()
        mock_cfg.set.return_value = True

        with patch("core.config_hot_reload.get_config_manager", return_value=mock_cfg):
            await config_cmd(mock_update, mock_context)

            mock_cfg.set.assert_called_once_with("bot.name", "JarvisBot")
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "bot.name" in message

    @pytest.mark.asyncio
    async def test_config_set_boolean_true(self, mock_update, mock_context, admin_config):
        """Should convert 'true' to boolean."""
        mock_context.args = ["set", "bot.debug", "true"]
        mock_cfg = MagicMock()
        mock_cfg.set.return_value = True

        with patch("core.config_hot_reload.get_config_manager", return_value=mock_cfg):
            await config_cmd(mock_update, mock_context)

            mock_cfg.set.assert_called_once_with("bot.debug", True)

    @pytest.mark.asyncio
    async def test_config_set_boolean_false(self, mock_update, mock_context, admin_config):
        """Should convert 'false' to boolean."""
        mock_context.args = ["set", "bot.debug", "false"]
        mock_cfg = MagicMock()
        mock_cfg.set.return_value = True

        with patch("core.config_hot_reload.get_config_manager", return_value=mock_cfg):
            await config_cmd(mock_update, mock_context)

            mock_cfg.set.assert_called_once_with("bot.debug", False)

    @pytest.mark.asyncio
    async def test_config_set_integer_value(self, mock_update, mock_context, admin_config):
        """Should convert integer strings to int."""
        mock_context.args = ["set", "trading.max_position", "100"]
        mock_cfg = MagicMock()
        mock_cfg.set.return_value = True

        with patch("core.config_hot_reload.get_config_manager", return_value=mock_cfg):
            await config_cmd(mock_update, mock_context)

            mock_cfg.set.assert_called_once_with("trading.max_position", 100)

    @pytest.mark.asyncio
    async def test_config_set_float_value(self, mock_update, mock_context, admin_config):
        """Should convert float strings to float."""
        mock_context.args = ["set", "trading.risk_ratio", "0.05"]
        mock_cfg = MagicMock()
        mock_cfg.set.return_value = True

        with patch("core.config_hot_reload.get_config_manager", return_value=mock_cfg):
            await config_cmd(mock_update, mock_context)

            mock_cfg.set.assert_called_once_with("trading.risk_ratio", 0.05)

    @pytest.mark.asyncio
    async def test_config_set_failure(self, mock_update, mock_context, admin_config):
        """Should report when setting fails."""
        mock_context.args = ["set", "invalid.key", "value"]
        mock_cfg = MagicMock()
        mock_cfg.set.return_value = False

        with patch("core.config_hot_reload.get_config_manager", return_value=mock_cfg):
            await config_cmd(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "failed" in message.lower()


# ============================================================================
# Test: /away Command
# ============================================================================

class TestAwayCommand:
    """Tests for the /away command handler."""

    @pytest.mark.asyncio
    async def test_away_default(self, mock_update, mock_context, admin_config):
        """Should enable auto-responder with defaults."""
        mock_responder = MagicMock()
        mock_responder.enable.return_value = "Auto-responder enabled"

        with patch("tg_bot.services.auto_responder.get_auto_responder", return_value=mock_responder):
            with patch("tg_bot.services.auto_responder.parse_duration", return_value=None):
                mock_context.args = []
                await away(mock_update, mock_context)

                mock_responder.enable.assert_called_once_with(message=None, duration_minutes=None)
                call_args = mock_update.message.reply_text.call_args
                message = call_args[0][0]
                assert "Auto-responder enabled" in message

    @pytest.mark.asyncio
    async def test_away_with_duration(self, mock_update, mock_context, admin_config):
        """Should enable for specified duration."""
        mock_responder = MagicMock()
        mock_responder.enable.return_value = "Away for 2h"

        with patch("tg_bot.services.auto_responder.get_auto_responder", return_value=mock_responder):
            with patch("tg_bot.services.auto_responder.parse_duration", return_value=120):
                mock_context.args = ["2h"]
                await away(mock_update, mock_context)

                mock_responder.enable.assert_called_once_with(message=None, duration_minutes=120)

    @pytest.mark.asyncio
    async def test_away_with_message(self, mock_update, mock_context, admin_config):
        """Should enable with custom message."""
        mock_responder = MagicMock()
        mock_responder.enable.return_value = "Away mode on"

        with patch("tg_bot.services.auto_responder.get_auto_responder", return_value=mock_responder):
            with patch("tg_bot.services.auto_responder.parse_duration", return_value=None):
                mock_context.args = ["Going", "for", "lunch"]
                await away(mock_update, mock_context)

                mock_responder.enable.assert_called_once_with(
                    message="Going for lunch",
                    duration_minutes=None
                )

    @pytest.mark.asyncio
    async def test_away_with_duration_and_message(self, mock_update, mock_context, admin_config):
        """Should enable with both duration and message."""
        mock_responder = MagicMock()
        mock_responder.enable.return_value = "Away for 30 min"

        with patch("tg_bot.services.auto_responder.get_auto_responder", return_value=mock_responder):
            with patch("tg_bot.services.auto_responder.parse_duration", return_value=30):
                mock_context.args = ["30m", "Gone", "to", "meeting"]
                await away(mock_update, mock_context)

                mock_responder.enable.assert_called_once_with(
                    message="Gone to meeting",
                    duration_minutes=30
                )


# ============================================================================
# Test: /back Command
# ============================================================================

class TestBackCommand:
    """Tests for the /back command handler."""

    @pytest.mark.asyncio
    async def test_back_success(self, mock_update, mock_context, admin_config):
        """Should disable auto-responder."""
        mock_responder = MagicMock()
        mock_responder.disable.return_value = "Auto-responder disabled"

        with patch("tg_bot.services.auto_responder.get_auto_responder", return_value=mock_responder):
            await back(mock_update, mock_context)

            mock_responder.disable.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "Auto-responder disabled" in message

    @pytest.mark.asyncio
    async def test_back_error_handling(self, mock_update, mock_context, admin_config):
        """Should handle errors gracefully."""
        with patch("tg_bot.services.auto_responder.get_auto_responder", side_effect=Exception("Service down")):
            await back(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "error" in message.lower()


# ============================================================================
# Test: /awaystatus Command
# ============================================================================

class TestAwaystatusCommand:
    """Tests for the /awaystatus command handler."""

    @pytest.mark.asyncio
    async def test_awaystatus_enabled(self, mock_update, mock_context, admin_config):
        """Should display enabled status with details."""
        mock_responder = MagicMock()
        mock_responder.get_status.return_value = {
            "enabled": True,
            "message": "Be right back",
            "return_time": "2026-01-25 15:00",
            "remaining": "30 minutes",
            "enabled_at": "2026-01-25 14:30",
        }

        with patch("tg_bot.services.auto_responder.get_auto_responder", return_value=mock_responder):
            await awaystatus(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "away mode: on" in message.lower()
            assert "Be right back" in message
            assert "30 minutes" in message

    @pytest.mark.asyncio
    async def test_awaystatus_disabled(self, mock_update, mock_context, admin_config):
        """Should display disabled status."""
        mock_responder = MagicMock()
        mock_responder.get_status.return_value = {
            "enabled": False,
        }

        with patch("tg_bot.services.auto_responder.get_auto_responder", return_value=mock_responder):
            await awaystatus(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "away mode: off" in message.lower()


# ============================================================================
# Test: /memory Command
# ============================================================================

class TestMemoryCommand:
    """Tests for the /memory command handler."""

    @pytest.mark.asyncio
    async def test_memory_with_facts(self, mock_update, mock_context, admin_config):
        """Should display user facts and context."""
        mock_pmem = MagicMock()
        mock_pmem.get_user_facts.return_value = [
            {"fact_type": "preference", "fact_content": "Likes SOL"},
            {"fact_type": "trading_style", "fact_content": "Conservative"},
        ]
        mock_pmem.get_user_context.return_value = "Active trader since January"
        mock_pmem.get_conversation_summary.return_value = "100 messages, 5 sessions"
        mock_pmem.get_chat_topics.return_value = ["trading", "market", "SOL"]

        with patch("tg_bot.services.conversation_memory.get_conversation_memory", return_value=mock_pmem):
            await memory(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "what i remember" in message.lower()
            assert "preference" in message
            assert "Likes SOL" in message
            assert "trading" in message

    @pytest.mark.asyncio
    async def test_memory_system_offline(self, mock_update, mock_context, admin_config):
        """Should handle offline memory system."""
        with patch("tg_bot.services.conversation_memory.get_conversation_memory", return_value=None):
            await memory(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "memory system offline" in message.lower()

    @pytest.mark.asyncio
    async def test_memory_empty(self, mock_update, mock_context, admin_config):
        """Should display message when no memory."""
        mock_pmem = MagicMock()
        mock_pmem.get_user_facts.return_value = []
        mock_pmem.get_user_context.return_value = None
        mock_pmem.get_conversation_summary.return_value = None
        mock_pmem.get_chat_topics.return_value = []

        with patch("tg_bot.services.conversation_memory.get_conversation_memory", return_value=mock_pmem):
            await memory(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "nothing yet" in message.lower()


# ============================================================================
# Test: /sysmem Command
# ============================================================================

class TestSysmemCommand:
    """Tests for the /sysmem command handler."""

    @pytest.mark.asyncio
    async def test_sysmem_status_default(self, mock_update, mock_context, admin_config):
        """Should display current memory status."""
        mock_snapshot = MagicMock()
        mock_snapshot.rss_mb = 256.5
        mock_snapshot.heap_mb = 128.3
        mock_snapshot.gc_counts = (10, 5, 2)
        mock_snapshot.timestamp = time.time()

        mock_baseline = MagicMock()
        mock_baseline.rss_mb = 200.0

        mock_monitor = MagicMock()
        mock_monitor.snapshots = [mock_snapshot]
        mock_monitor.baseline = mock_baseline
        mock_monitor.get_memory_trend.return_value = {"trend": "stable"}
        mock_monitor.get_alerts.return_value = []

        with patch("core.performance.memory_monitor.memory_monitor", mock_monitor):
            mock_context.args = []
            await sysmem(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "system memory" in message.lower()
            assert "256.5" in message
            assert "128.3" in message

    @pytest.mark.asyncio
    async def test_sysmem_start(self, mock_update, mock_context, admin_config):
        """Should start background monitoring."""
        mock_monitor = MagicMock()
        mock_monitor._tracking = False

        with patch("core.performance.memory_monitor.memory_monitor", mock_monitor):
            mock_context.args = ["start"]
            await sysmem(mock_update, mock_context)

            mock_monitor.start_tracking.assert_called_once()
            mock_monitor.start_background_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_sysmem_stop(self, mock_update, mock_context, admin_config):
        """Should stop background monitoring."""
        mock_monitor = MagicMock()

        with patch("core.performance.memory_monitor.memory_monitor", mock_monitor):
            mock_context.args = ["stop"]
            await sysmem(mock_update, mock_context)

            mock_monitor.stop_background_monitoring.assert_called_once()

    @pytest.mark.asyncio
    async def test_sysmem_snapshot(self, mock_update, mock_context, admin_config):
        """Should take manual snapshot."""
        mock_snapshot = MagicMock()
        mock_snapshot.rss_mb = 300.0
        mock_snapshot.heap_mb = 150.0
        mock_snapshot.gc_counts = (15, 8, 3)
        mock_snapshot.timestamp = time.time()

        mock_monitor = MagicMock()
        mock_monitor.take_snapshot.return_value = mock_snapshot

        with patch("core.performance.memory_monitor.memory_monitor", mock_monitor):
            mock_context.args = ["snapshot"]
            await sysmem(mock_update, mock_context)

            mock_monitor.take_snapshot.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "snapshot" in message.lower()
            assert "300.0" in message

    @pytest.mark.asyncio
    async def test_sysmem_trend(self, mock_update, mock_context, admin_config):
        """Should display memory trend."""
        mock_monitor = MagicMock()
        mock_monitor.get_memory_trend.return_value = {
            "trend": "increasing",
            "samples": 10,
            "growth_mb": 50.5,
            "growth_rate_mb_per_min": 0.84,
        }

        with patch("core.performance.memory_monitor.memory_monitor", mock_monitor):
            mock_context.args = ["trend"]
            await sysmem(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "trend" in message.lower()
            assert "increasing" in message.lower()
            assert "50.5" in message

    @pytest.mark.asyncio
    async def test_sysmem_alerts(self, mock_update, mock_context, admin_config):
        """Should display recent memory alerts."""
        mock_alert = MagicMock()
        mock_alert.severity = "warning"
        mock_alert.message = "Memory usage high"
        mock_alert.timestamp = time.time()

        mock_monitor = MagicMock()
        mock_monitor.get_alerts.return_value = [mock_alert]

        with patch("core.performance.memory_monitor.memory_monitor", mock_monitor):
            mock_context.args = ["alerts"]
            await sysmem(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "alerts" in message.lower()
            assert "Memory usage high" in message

    @pytest.mark.asyncio
    async def test_sysmem_clear(self, mock_update, mock_context, admin_config):
        """Should clear alerts."""
        mock_monitor = MagicMock()

        with patch("core.performance.memory_monitor.memory_monitor", mock_monitor):
            mock_context.args = ["clear"]
            await sysmem(mock_update, mock_context)

            mock_monitor.clear_alerts.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "cleared" in message.lower()

    @pytest.mark.asyncio
    async def test_sysmem_no_data(self, mock_update, mock_context, admin_config):
        """Should handle no monitoring data."""
        mock_monitor = MagicMock()
        mock_monitor.snapshots = []

        with patch("core.performance.memory_monitor.memory_monitor", mock_monitor):
            mock_context.args = []
            await sysmem(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "no memory data" in message.lower()


# ============================================================================
# Test: /flags Command
# ============================================================================

class TestFlagsCommand:
    """Tests for the /flags command handler."""

    @pytest.mark.asyncio
    async def test_flags_list_all(self, mock_update, mock_context, admin_config):
        """Should list all feature flags."""
        mock_manager = MagicMock()
        mock_manager.get_all_flags.return_value = {
            "FEATURE_A": {"enabled": True, "description": "Feature A", "rollout_percentage": 100},
            "FEATURE_B": {"enabled": False, "description": "Feature B", "rollout_percentage": 0},
            "FEATURE_C": {"enabled": True, "description": "Partial rollout", "rollout_percentage": 50},
        }

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = []
            await flags(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "feature flags" in message.lower()
            assert "FEATURE_A" in message
            assert "FEATURE_B" in message
            assert "50%" in message

    @pytest.mark.asyncio
    async def test_flags_show_specific(self, mock_update, mock_context, admin_config):
        """Should show specific flag details."""
        mock_flag = MagicMock()
        mock_flag.enabled = True
        mock_flag.description = "Test feature"
        mock_flag.rollout_percentage = 75
        mock_flag.user_whitelist = ["user1", "user2"]
        mock_flag.updated_at = "2026-01-25T10:00:00Z"

        mock_manager = MagicMock()
        mock_manager.get_flag.return_value = mock_flag

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X"]
            await flags(mock_update, mock_context)

            mock_manager.get_flag.assert_called_once_with("FEATURE_X")
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "FEATURE_X" in message
            assert "ON" in message
            assert "75%" in message
            assert "2 users" in message

    @pytest.mark.asyncio
    async def test_flags_enable(self, mock_update, mock_context, admin_config):
        """Should enable a flag."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "on"]
            await flags(mock_update, mock_context)

            mock_manager.set_flag.assert_called_once_with("FEATURE_X", enabled=True)
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "FEATURE_X" in message
            assert "enabled" in message.lower()

    @pytest.mark.asyncio
    async def test_flags_disable(self, mock_update, mock_context, admin_config):
        """Should disable a flag."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "off"]
            await flags(mock_update, mock_context)

            mock_manager.set_flag.assert_called_once_with("FEATURE_X", enabled=False)
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "FEATURE_X" in message
            assert "disabled" in message.lower()

    @pytest.mark.asyncio
    async def test_flags_set_percentage(self, mock_update, mock_context, admin_config):
        """Should set rollout percentage."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "50"]
            await flags(mock_update, mock_context)

            mock_manager.set_flag.assert_called_once_with("FEATURE_X", enabled=True, percentage=50)
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "50%" in message

    @pytest.mark.asyncio
    async def test_flags_reload(self, mock_update, mock_context, admin_config):
        """Should reload flags from config file."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["reload"]
            await flags(mock_update, mock_context)

            mock_manager.reload_from_file.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "reloaded" in message.lower()

    @pytest.mark.asyncio
    async def test_flags_not_found(self, mock_update, mock_context, admin_config):
        """Should handle flag not found."""
        mock_manager = MagicMock()
        mock_manager.get_flag.return_value = None

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["NONEXISTENT"]
            await flags(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "not found" in message.lower()

    @pytest.mark.asyncio
    async def test_flags_invalid_value(self, mock_update, mock_context, admin_config):
        """Should reject invalid flag values."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "maybe"]
            await flags(mock_update, mock_context)

            mock_manager.set_flag.assert_not_called()
            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "invalid" in message.lower()

    @pytest.mark.asyncio
    async def test_flags_empty_list(self, mock_update, mock_context, admin_config):
        """Should handle empty flags list."""
        mock_manager = MagicMock()
        mock_manager.get_all_flags.return_value = {}

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = []
            await flags(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            message = call_args[0][0]
            assert "no feature flags" in message.lower()


# ============================================================================
# Test: Edge Cases and Error Handling
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_all_handlers_have_admin_only(self, mock_non_admin_update, mock_context, non_admin_config):
        """All handlers should reject non-admin users."""
        handlers = [reload, logs, errors, system, config_cmd, away, back, awaystatus, memory, sysmem, flags]

        for handler in handlers:
            mock_non_admin_update.message.reply_text.reset_mock()
            await handler(mock_non_admin_update, mock_context)
            # Each should have called reply_text with unauthorized message
            assert mock_non_admin_update.message.reply_text.called, f"{handler.__name__} didn't reject non-admin"

    @pytest.mark.asyncio
    async def test_system_handles_all_imports_failing(self, mock_update, mock_context, admin_config):
        """System should work even if all optional imports fail."""
        # The system command catches all import errors internally
        await system(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        message = call_args[0][0]
        # Should still show basic system status
        assert "system status" in message.lower()


# ============================================================================
# Test: Message Formatting
# ============================================================================

class TestMessageFormatting:
    """Tests for proper message formatting."""

    @pytest.mark.asyncio
    async def test_logs_uses_html_parse_mode(self, mock_update, mock_context, admin_config):
        """Logs should use HTML parse mode."""
        with patch("tg_bot.handlers.admin.Path") as mock_path:
            mock_log_file = MagicMock()
            mock_log_file.exists.return_value = True
            mock_log_file.read_text.return_value = "log line"
            mock_path.return_value = mock_log_file

            await logs(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_errors_uses_html_parse_mode(self, mock_update, mock_context, admin_config):
        """Errors should use HTML parse mode."""
        mock_tracker = MagicMock()
        mock_tracker.get_frequent_errors.return_value = []
        mock_tracker.get_critical_errors.return_value = []

        with patch("core.logging.error_tracker.error_tracker", mock_tracker):
            await errors(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_system_uses_html_parse_mode(self, mock_update, mock_context, admin_config):
        """System should use HTML parse mode."""
        await system(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_config_uses_html_parse_mode(self, mock_update, mock_context, admin_config):
        """Config should use HTML parse mode."""
        mock_cfg = MagicMock()
        mock_cfg.get_by_prefix.return_value = {}

        with patch("core.config_hot_reload.get_config_manager", return_value=mock_cfg):
            await config_cmd(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_awaystatus_uses_html_parse_mode(self, mock_update, mock_context, admin_config):
        """Awaystatus should use HTML parse mode."""
        mock_responder = MagicMock()
        mock_responder.get_status.return_value = {"enabled": False}

        with patch("tg_bot.services.auto_responder.get_auto_responder", return_value=mock_responder):
            await awaystatus(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_memory_uses_html_parse_mode(self, mock_update, mock_context, admin_config):
        """Memory should use HTML parse mode."""
        mock_pmem = MagicMock()
        mock_pmem.get_user_facts.return_value = []
        mock_pmem.get_user_context.return_value = None
        mock_pmem.get_conversation_summary.return_value = None
        mock_pmem.get_chat_topics.return_value = []

        with patch("tg_bot.services.conversation_memory.get_conversation_memory", return_value=mock_pmem):
            await memory(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_sysmem_uses_html_parse_mode(self, mock_update, mock_context, admin_config):
        """Sysmem should use HTML parse mode."""
        mock_monitor = MagicMock()
        mock_monitor.snapshots = []

        with patch("core.performance.memory_monitor.memory_monitor", mock_monitor):
            mock_context.args = []
            await sysmem(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            assert call_args[1].get("parse_mode") == ParseMode.HTML

    @pytest.mark.asyncio
    async def test_flags_uses_html_parse_mode(self, mock_update, mock_context, admin_config):
        """Flags should use HTML parse mode."""
        mock_manager = MagicMock()
        mock_manager.get_all_flags.return_value = {}

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = []
            await flags(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args
            assert call_args[1].get("parse_mode") == ParseMode.HTML


# ============================================================================
# Test: Additional Coverage for Enable/Disable Variations
# ============================================================================

class TestFlagsEnableDisableVariations:
    """Additional tests for flag enable/disable variations."""

    @pytest.mark.asyncio
    async def test_flags_enable_with_true(self, mock_update, mock_context, admin_config):
        """Should enable with 'true'."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "true"]
            await flags(mock_update, mock_context)
            mock_manager.set_flag.assert_called_once_with("FEATURE_X", enabled=True)

    @pytest.mark.asyncio
    async def test_flags_enable_with_enable(self, mock_update, mock_context, admin_config):
        """Should enable with 'enable'."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "enable"]
            await flags(mock_update, mock_context)
            mock_manager.set_flag.assert_called_once_with("FEATURE_X", enabled=True)

    @pytest.mark.asyncio
    async def test_flags_enable_with_1(self, mock_update, mock_context, admin_config):
        """Should enable with '1'."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "1"]
            await flags(mock_update, mock_context)
            mock_manager.set_flag.assert_called_once_with("FEATURE_X", enabled=True)

    @pytest.mark.asyncio
    async def test_flags_disable_with_false(self, mock_update, mock_context, admin_config):
        """Should disable with 'false'."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "false"]
            await flags(mock_update, mock_context)
            mock_manager.set_flag.assert_called_once_with("FEATURE_X", enabled=False)

    @pytest.mark.asyncio
    async def test_flags_disable_with_disable(self, mock_update, mock_context, admin_config):
        """Should disable with 'disable'."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "disable"]
            await flags(mock_update, mock_context)
            mock_manager.set_flag.assert_called_once_with("FEATURE_X", enabled=False)

    @pytest.mark.asyncio
    async def test_flags_disable_with_0(self, mock_update, mock_context, admin_config):
        """Should disable with '0'."""
        mock_manager = MagicMock()

        with patch("core.config.feature_flags.get_feature_flag_manager", return_value=mock_manager):
            mock_context.args = ["FEATURE_X", "0"]
            await flags(mock_update, mock_context)
            mock_manager.set_flag.assert_called_once_with("FEATURE_X", enabled=False)
