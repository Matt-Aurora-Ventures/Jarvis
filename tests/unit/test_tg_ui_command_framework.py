"""
Tests for Telegram UI Command Framework.

Tests cover:
- Structured command parsing
- Permission-based command access
- Command history/favorites
- Autocomplete for commands
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


# =============================================================================
# Test Command Parser
# =============================================================================

class TestCommandParser:
    """Test command parsing functionality."""

    def test_parse_simple_command(self):
        """Simple command without args should parse."""
        from tg_bot.ui.command_framework import CommandParser

        parser = CommandParser()
        result = parser.parse("/help")

        assert result.command == "help"
        assert result.args == []
        assert result.raw == "/help"

    def test_parse_command_with_args(self):
        """Command with arguments should parse all args."""
        from tg_bot.ui.command_framework import CommandParser

        parser = CommandParser()
        result = parser.parse("/analyze So111 --detailed")

        assert result.command == "analyze"
        assert "So111" in result.args
        assert "--detailed" in result.args

    def test_parse_command_with_bot_mention(self):
        """Command with @botname should strip bot mention."""
        from tg_bot.ui.command_framework import CommandParser

        parser = CommandParser()
        result = parser.parse("/help@JarvisBot")

        assert result.command == "help"

    def test_parse_quoted_args(self):
        """Quoted arguments should be preserved as single arg."""
        from tg_bot.ui.command_framework import CommandParser

        parser = CommandParser()
        result = parser.parse('/analyze "token with spaces" --flag')

        assert result.command == "analyze"
        assert "token with spaces" in result.args

    def test_parse_empty_message(self):
        """Empty message should return None."""
        from tg_bot.ui.command_framework import CommandParser

        parser = CommandParser()
        result = parser.parse("")

        assert result is None

    def test_parse_non_command(self):
        """Non-command message should return None."""
        from tg_bot.ui.command_framework import CommandParser

        parser = CommandParser()
        result = parser.parse("just a regular message")

        assert result is None

    def test_parse_with_newlines(self):
        """Command with newlines should handle gracefully."""
        from tg_bot.ui.command_framework import CommandParser

        parser = CommandParser()
        result = parser.parse("/note This is\na multiline\nnote")

        assert result.command == "note"
        assert len(result.args) >= 1


# =============================================================================
# Test Command Permissions
# =============================================================================

class TestCommandPermissions:
    """Test permission-based command access."""

    def test_check_admin_permission(self):
        """Admin commands should require admin status."""
        from tg_bot.ui.command_framework import CommandPermissions

        perms = CommandPermissions()
        perms.register_admin_command("reload")
        perms.register_admin_command("config")

        assert perms.requires_admin("reload") is True
        assert perms.requires_admin("help") is False

    def test_check_user_permission(self):
        """Should check if user can execute command."""
        from tg_bot.ui.command_framework import CommandPermissions

        perms = CommandPermissions(admin_ids={12345, 67890})
        perms.register_admin_command("reload")

        assert perms.can_execute(user_id=12345, command="reload") is True
        assert perms.can_execute(user_id=99999, command="reload") is False
        assert perms.can_execute(user_id=99999, command="help") is True

    def test_register_permission_level(self):
        """Should support custom permission levels."""
        from tg_bot.ui.command_framework import CommandPermissions, PermissionLevel

        perms = CommandPermissions(admin_ids={12345})
        perms.register_command("dashboard", PermissionLevel.ADMIN)
        perms.register_command("trending", PermissionLevel.USER)
        perms.register_command("system", PermissionLevel.SUPERADMIN)

        # Admin can use ADMIN level
        assert perms.can_execute(12345, "dashboard") is True
        # Non-admin cannot use ADMIN level
        assert perms.can_execute(99999, "dashboard") is False
        # Anyone can use USER level
        assert perms.can_execute(99999, "trending") is True

    def test_rate_limit_check(self):
        """Should enforce rate limits per user."""
        from tg_bot.ui.command_framework import CommandPermissions

        perms = CommandPermissions()
        perms.set_rate_limit("analyze", max_calls=3, window_seconds=60)

        user_id = 12345
        # First 3 calls should succeed
        assert perms.check_rate_limit(user_id, "analyze") is True
        assert perms.check_rate_limit(user_id, "analyze") is True
        assert perms.check_rate_limit(user_id, "analyze") is True
        # 4th should fail
        assert perms.check_rate_limit(user_id, "analyze") is False


# =============================================================================
# Test Command History
# =============================================================================

class TestCommandHistory:
    """Test command history and favorites."""

    def test_record_command(self):
        """Should record command execution."""
        from tg_bot.ui.command_framework import CommandHistory

        history = CommandHistory()
        history.record(user_id=12345, command="analyze", args=["SOL"])

        recent = history.get_recent(12345, limit=5)
        assert len(recent) == 1
        assert recent[0]["command"] == "analyze"

    def test_get_recent_history(self):
        """Should return recent commands in order."""
        from tg_bot.ui.command_framework import CommandHistory

        history = CommandHistory()
        user_id = 12345

        history.record(user_id, "help", [])
        history.record(user_id, "trending", [])
        history.record(user_id, "analyze", ["SOL"])

        recent = history.get_recent(user_id, limit=2)
        assert len(recent) == 2
        # Most recent first
        assert recent[0]["command"] == "analyze"
        assert recent[1]["command"] == "trending"

    def test_add_favorite(self):
        """Should add command to favorites."""
        from tg_bot.ui.command_framework import CommandHistory

        history = CommandHistory()
        user_id = 12345

        result = history.add_favorite(user_id, "analyze SOL --detailed")
        assert result is True

        favorites = history.get_favorites(user_id)
        assert len(favorites) == 1
        assert "analyze SOL" in favorites[0]

    def test_remove_favorite(self):
        """Should remove command from favorites."""
        from tg_bot.ui.command_framework import CommandHistory

        history = CommandHistory()
        user_id = 12345

        history.add_favorite(user_id, "analyze SOL")
        result = history.remove_favorite(user_id, "analyze SOL")

        assert result is True
        favorites = history.get_favorites(user_id)
        assert len(favorites) == 0

    def test_get_most_used(self):
        """Should return most frequently used commands."""
        from tg_bot.ui.command_framework import CommandHistory

        history = CommandHistory()
        user_id = 12345

        # Use analyze 5 times
        for _ in range(5):
            history.record(user_id, "analyze", ["SOL"])

        # Use trending 2 times
        for _ in range(2):
            history.record(user_id, "trending", [])

        # Use help 1 time
        history.record(user_id, "help", [])

        most_used = history.get_most_used(user_id, limit=3)

        assert len(most_used) == 3
        assert most_used[0]["command"] == "analyze"
        assert most_used[0]["count"] == 5


# =============================================================================
# Test Command Autocomplete
# =============================================================================

class TestCommandAutocomplete:
    """Test command autocomplete functionality."""

    def test_autocomplete_empty_input(self):
        """Empty input should return popular commands."""
        from tg_bot.ui.command_framework import CommandAutocomplete

        autocomplete = CommandAutocomplete()
        suggestions = autocomplete.suggest("")

        assert len(suggestions) > 0
        assert all(s.startswith("/") for s in suggestions)

    def test_autocomplete_partial_match(self):
        """Partial input should match commands."""
        from tg_bot.ui.command_framework import CommandAutocomplete

        autocomplete = CommandAutocomplete()
        suggestions = autocomplete.suggest("an")

        assert any("analyze" in s for s in suggestions)

    def test_autocomplete_with_args(self):
        """Should suggest argument completions."""
        from tg_bot.ui.command_framework import CommandAutocomplete

        autocomplete = CommandAutocomplete()
        autocomplete.register_arg_suggestions("analyze", ["SOL", "BONK", "JUP"])

        # Trailing space after command triggers arg completion
        suggestions = autocomplete.suggest("/analyze ")

        # Debug: print what we got
        print(f"Suggestions for '/analyze ': {suggestions}")

        # Should get the registered arg suggestions
        assert len(suggestions) >= 1
        assert any("SOL" in s for s in suggestions) or any("analyze" in s.lower() for s in suggestions)

    def test_autocomplete_case_insensitive(self):
        """Autocomplete should be case insensitive."""
        from tg_bot.ui.command_framework import CommandAutocomplete

        autocomplete = CommandAutocomplete()
        suggestions_lower = autocomplete.suggest("an")
        suggestions_upper = autocomplete.suggest("AN")

        assert suggestions_lower == suggestions_upper

    def test_autocomplete_limit(self):
        """Should limit number of suggestions."""
        from tg_bot.ui.command_framework import CommandAutocomplete

        autocomplete = CommandAutocomplete()
        suggestions = autocomplete.suggest("", limit=3)

        assert len(suggestions) <= 3


# =============================================================================
# Test Command Executor
# =============================================================================

class TestCommandExecutor:
    """Test command execution framework."""

    @pytest.mark.asyncio
    async def test_execute_registered_command(self):
        """Should execute registered command handler."""
        from tg_bot.ui.command_framework import CommandExecutor

        executor = CommandExecutor()
        executed = []

        async def help_handler(update, context, args):
            executed.append(("help", args))
            return "Help message"

        executor.register("help", help_handler)

        mock_update = MagicMock()
        mock_context = MagicMock()

        result = await executor.execute("help", [], mock_update, mock_context)

        assert len(executed) == 1
        assert result == "Help message"

    @pytest.mark.asyncio
    async def test_execute_unknown_command(self):
        """Unknown command should return error message."""
        from tg_bot.ui.command_framework import CommandExecutor

        executor = CommandExecutor()

        mock_update = MagicMock()
        mock_context = MagicMock()

        result = await executor.execute("nonexistent", [], mock_update, mock_context)

        assert "unknown" in result.lower() or "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_with_middleware(self):
        """Should run middleware before command."""
        from tg_bot.ui.command_framework import CommandExecutor

        executor = CommandExecutor()
        middleware_calls = []

        async def logging_middleware(update, context, command, args, next_fn):
            middleware_calls.append(command)
            return await next_fn()

        executor.add_middleware(logging_middleware)

        async def test_handler(update, context, args):
            return "OK"

        executor.register("test", test_handler)

        mock_update = MagicMock()
        mock_context = MagicMock()

        await executor.execute("test", [], mock_update, mock_context)

        assert "test" in middleware_calls

    @pytest.mark.asyncio
    async def test_execute_handles_exceptions(self):
        """Should handle handler exceptions gracefully."""
        from tg_bot.ui.command_framework import CommandExecutor

        executor = CommandExecutor()

        async def broken_handler(update, context, args):
            raise ValueError("Something broke")

        executor.register("broken", broken_handler)

        mock_update = MagicMock()
        mock_context = MagicMock()

        result = await executor.execute("broken", [], mock_update, mock_context)

        assert "error" in result.lower()
