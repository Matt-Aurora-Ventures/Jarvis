"""
Unit tests for the Skill Telegram Handler.

Tests /skill command handler for Telegram bot integration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


class TestSkillCommand:
    """Tests for /skill command handler."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram Update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.username = "testuser"
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Telegram context."""
        context = MagicMock()
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_skill_command_no_args_shows_help(self, mock_update, mock_context):
        """skill_command with no args should show help message."""
        from tg_bot.handlers.skills import skill_command

        mock_context.args = []

        await skill_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "skill" in call_args.lower()
        assert "usage" in call_args.lower() or "help" in call_args.lower()

    @pytest.mark.asyncio
    async def test_skill_list_shows_available_skills(self, mock_update, mock_context, tmp_path):
        """skill_command list should show available skills."""
        from tg_bot.handlers.skills import skill_command

        # Create a test skill
        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Test Skill\nA test.")
        (skill_dir / "script.py").write_text("print('test')")

        mock_context.args = ["list"]

        with patch("tg_bot.handlers.skills.get_skill_manager") as mock_get_manager:
            manager = MagicMock()
            manager.list_installed.return_value = ["test_skill"]
            manager.registry.get_skill.return_value = {
                "name": "test_skill",
                "title": "Test Skill",
                "description": "A test.",
            }
            mock_get_manager.return_value = manager

            await skill_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "test_skill" in call_args.lower() or "Test Skill" in call_args

    @pytest.mark.asyncio
    async def test_skill_run_executes_skill(self, mock_update, mock_context):
        """skill_command run should execute specified skill."""
        from tg_bot.handlers.skills import skill_command

        mock_context.args = ["run", "echo", "Hello", "World"]

        with patch("tg_bot.handlers.skills.get_skill_executor") as mock_get_executor:
            executor = MagicMock()
            result = MagicMock()
            result.success = True
            result.output = "Echo: Hello World"
            result.execution_time = 0.1
            executor.execute.return_value = result
            mock_get_executor.return_value = executor

            await skill_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        call_args = str(mock_update.message.reply_text.call_args)
        assert "Hello World" in call_args or "Echo" in call_args

    @pytest.mark.asyncio
    async def test_skill_run_shows_error_on_failure(self, mock_update, mock_context):
        """skill_command run should show error when skill fails."""
        from tg_bot.handlers.skills import skill_command

        mock_context.args = ["run", "broken"]

        with patch("tg_bot.handlers.skills.get_skill_executor") as mock_get_executor:
            executor = MagicMock()
            result = MagicMock()
            result.success = False
            result.error = "Skill not found"
            result.output = ""
            result.stderr = ""
            executor.execute.return_value = result
            mock_get_executor.return_value = executor

            await skill_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called()
        call_args = str(mock_update.message.reply_text.call_args)
        assert "error" in call_args.lower() or "fail" in call_args.lower() or "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_skill_info_shows_skill_details(self, mock_update, mock_context):
        """skill_command info should show skill details."""
        from tg_bot.handlers.skills import skill_command

        mock_context.args = ["info", "echo"]

        with patch("tg_bot.handlers.skills.get_skill_manager") as mock_get_manager:
            manager = MagicMock()
            manager.registry.get_skill.return_value = {
                "name": "echo",
                "title": "Echo Skill",
                "description": "Echoes back arguments.",
                "path": Path("/skills/echo"),
                "has_script": True,
            }
            mock_get_manager.return_value = manager

            await skill_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "echo" in call_args.lower()

    @pytest.mark.asyncio
    async def test_skill_info_not_found(self, mock_update, mock_context):
        """skill_command info should handle non-existent skill."""
        from tg_bot.handlers.skills import skill_command

        mock_context.args = ["info", "nonexistent"]

        with patch("tg_bot.handlers.skills.get_skill_manager") as mock_get_manager:
            manager = MagicMock()
            manager.registry.get_skill.return_value = None
            mock_get_manager.return_value = manager

            await skill_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "not found" in call_args.lower()

    @pytest.mark.asyncio
    async def test_skill_command_requires_admin_for_install(self, mock_update, mock_context):
        """skill_command install should require admin privileges."""
        from tg_bot.handlers.skills import skill_command

        mock_context.args = ["install", "https://example.com/skill.zip"]
        mock_update.effective_user.id = 99999  # Non-admin user

        with patch("tg_bot.handlers.skills.is_admin") as mock_is_admin:
            mock_is_admin.return_value = False

            await skill_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "admin" in call_args.lower() or "permission" in call_args.lower()


class TestSkillCallbacks:
    """Tests for skill-related callback handlers."""

    @pytest.fixture
    def mock_callback_query(self):
        """Create mock callback query."""
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = ""
        query.from_user = MagicMock()
        query.from_user.id = 12345
        return query

    @pytest.mark.asyncio
    async def test_skill_callback_run(self, mock_callback_query):
        """Skill callback should handle run action."""
        from tg_bot.handlers.skills import handle_skill_callback

        mock_callback_query.data = "skill:run:echo"

        with patch("tg_bot.handlers.skills.get_skill_executor") as mock_get_executor:
            executor = MagicMock()
            result = MagicMock()
            result.success = True
            result.output = "Echo output"
            executor.execute.return_value = result
            mock_get_executor.return_value = executor

            context = MagicMock()
            await handle_skill_callback(None, context, mock_callback_query)

        mock_callback_query.answer.assert_called()
