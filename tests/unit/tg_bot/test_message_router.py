"""Unit tests for MessageRouter.

TDD: These tests define the expected behavior of MessageRouter.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import os


class TestMessageRouter:
    """Tests for MessageRouter class."""

    def test_import_message_router(self):
        """MessageRouter can be imported from tg_bot.routing."""
        from tg_bot.routing import MessageRouter
        assert MessageRouter is not None

    def test_router_has_route_message_method(self):
        """MessageRouter has route_message async method."""
        from tg_bot.routing import MessageRouter
        router = MessageRouter()
        assert hasattr(router, "route_message")
        assert callable(router.route_message)

    def test_is_admin_checks_env_variable(self):
        """MessageRouter.is_admin checks TELEGRAM_ADMIN_IDS."""
        from tg_bot.routing import MessageRouter

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345,67890"}):
            router = MessageRouter()
            assert router.is_admin(12345) is True
            assert router.is_admin(67890) is True
            assert router.is_admin(11111) is False

    def test_is_terminal_command_detects_prefix(self):
        """_is_terminal_command detects > and /term prefixes."""
        from tg_bot.routing.message_router import MessageRouter

        assert MessageRouter._is_terminal_command("> ls -la") is True
        assert MessageRouter._is_terminal_command(">git status") is True
        assert MessageRouter._is_terminal_command("/term echo hello") is True
        assert MessageRouter._is_terminal_command("/TERM test") is True
        assert MessageRouter._is_terminal_command("hello world") is False
        assert MessageRouter._is_terminal_command("/help") is False

    def test_is_vibe_request_detects_prefixes(self):
        """_is_vibe_request detects vibe coding prefixes."""
        from tg_bot.routing.message_router import MessageRouter

        # Should trigger vibe coding
        assert MessageRouter._is_vibe_request("code: fix the bug") is True
        assert MessageRouter._is_vibe_request("cli: run tests") is True
        assert MessageRouter._is_vibe_request("vibe: implement feature") is True
        assert MessageRouter._is_vibe_request("jarvis fix the login error") is True
        assert MessageRouter._is_vibe_request("jarvis add logging") is True
        assert MessageRouter._is_vibe_request("ralph wiggum mode") is True
        assert MessageRouter._is_vibe_request("cascade this change") is True

        # Should NOT trigger vibe coding
        assert MessageRouter._is_vibe_request("hello jarvis") is False
        assert MessageRouter._is_vibe_request("what is the weather") is False
        assert MessageRouter._is_vibe_request("fix my problem") is False  # No jarvis prefix


@pytest.fixture
def mock_update():
    """Create mock Telegram Update."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = "test message"
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.effective_chat = MagicMock()
    update.effective_chat.id = 99999
    update.effective_chat.type = "group"
    return update


@pytest.fixture
def mock_context():
    """Create mock Telegram Context."""
    context = MagicMock()
    context.bot = MagicMock()
    context.bot.id = 88888
    context.bot.username = "testbot"
    return context


class TestMessageRouterRouting:
    """Tests for message routing logic."""

    @pytest.mark.asyncio
    async def test_route_ignored_for_empty_message(self, mock_update, mock_context):
        """Empty messages are ignored."""
        from tg_bot.routing import MessageRouter

        mock_update.message = None

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": ""}):
            router = MessageRouter()
            result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "ignored"
        assert result["should_continue"] is False

    @pytest.mark.asyncio
    async def test_route_terminal_for_admin(self, mock_update, mock_context):
        """Terminal commands route correctly for admin."""
        from tg_bot.routing import MessageRouter

        mock_update.message.text = "> ls -la"
        mock_update.effective_user.id = 12345

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            router = MessageRouter()
            result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "terminal"
        assert result["should_continue"] is True
        assert result["data"]["is_admin"] is True

    @pytest.mark.asyncio
    async def test_route_terminal_blocked_for_non_admin(self, mock_update, mock_context):
        """Terminal commands are blocked for non-admin."""
        from tg_bot.routing import MessageRouter

        mock_update.message.text = "> rm -rf /"
        mock_update.effective_user.id = 99999  # Not admin

        # Mock spam check to return False (not spam)
        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            with patch("tg_bot.bot_core.check_and_ban_spam", new_callable=AsyncMock, return_value=False):
                router = MessageRouter()
                result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "terminal"
        assert result["should_continue"] is False  # Should not continue for non-admin

    @pytest.mark.asyncio
    async def test_route_vibe_coding_for_admin(self, mock_update, mock_context):
        """Vibe coding requests route correctly for admin."""
        from tg_bot.routing import MessageRouter

        mock_update.message.text = "jarvis fix the bug"
        mock_update.effective_user.id = 12345

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            router = MessageRouter()
            result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "vibe_coding"
        assert result["should_continue"] is True

    @pytest.mark.asyncio
    async def test_route_vibe_coding_not_for_non_admin(self, mock_update, mock_context):
        """Vibe coding requests don't route for non-admin."""
        from tg_bot.routing import MessageRouter

        mock_update.message.text = "jarvis fix the bug"
        mock_update.effective_user.id = 99999  # Not admin

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            with patch("tg_bot.bot_core.check_and_ban_spam", new_callable=AsyncMock, return_value=False):
                with patch("tg_bot.bot_core._should_reply", return_value=True):
                    router = MessageRouter()
                    result = await router.route_message(mock_update, mock_context)

        # Should route to AI, not vibe coding
        assert result["route"] == "ai_response"

    @pytest.mark.asyncio
    async def test_route_spam_blocked(self, mock_update, mock_context):
        """Spam messages are blocked."""
        from tg_bot.routing import MessageRouter

        mock_update.message.text = "buy crypto at scam.com"
        mock_update.effective_user.id = 99999  # Not admin

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            with patch("tg_bot.bot_core.check_and_ban_spam", new_callable=AsyncMock, return_value=True):
                router = MessageRouter()
                result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "spam_blocked"
        assert result["should_continue"] is False

    @pytest.mark.asyncio
    async def test_route_ai_response(self, mock_update, mock_context):
        """Regular messages route to AI response."""
        from tg_bot.routing import MessageRouter

        mock_update.message.text = "hello jarvis"
        mock_update.effective_user.id = 99999  # Not admin

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            with patch("tg_bot.bot_core.check_and_ban_spam", new_callable=AsyncMock, return_value=False):
                with patch("tg_bot.bot_core._should_reply", return_value=True):
                    router = MessageRouter()
                    result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "ai_response"
        assert result["should_continue"] is True

    @pytest.mark.asyncio
    async def test_route_ignored_when_no_match(self, mock_update, mock_context):
        """Messages that don't match any route are ignored."""
        from tg_bot.routing import MessageRouter

        mock_update.message.text = "random message"
        mock_update.effective_user.id = 99999  # Not admin

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            with patch("tg_bot.bot_core.check_and_ban_spam", new_callable=AsyncMock, return_value=False):
                with patch("tg_bot.bot_core._should_reply", return_value=False):
                    router = MessageRouter()
                    result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "ignored"
        assert result["should_continue"] is False

    @pytest.mark.asyncio
    async def test_admin_skips_spam_check(self, mock_update, mock_context):
        """Admin messages skip spam detection."""
        from tg_bot.routing import MessageRouter

        mock_update.message.text = "hello"
        mock_update.effective_user.id = 12345  # Admin

        spam_mock = AsyncMock(return_value=True)  # Would be spam if checked

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            with patch("tg_bot.bot_core.check_and_ban_spam", spam_mock):
                with patch("tg_bot.bot_core._is_message_for_jarvis", return_value=True):
                    router = MessageRouter()
                    result = await router.route_message(mock_update, mock_context)

        # Spam check should NOT have been called for admin
        spam_mock.assert_not_called()
        # Should route to AI response since admin
        assert result["route"] == "ai_response"


class TestMessageRouterChainOrder:
    """Tests verifying the chain-of-responsibility order."""

    @pytest.mark.asyncio
    async def test_terminal_before_vibe(self, mock_update, mock_context):
        """Terminal commands are checked before vibe coding."""
        from tg_bot.routing import MessageRouter

        # "> jarvis fix" could match both terminal and vibe
        mock_update.message.text = "> jarvis fix bug"
        mock_update.effective_user.id = 12345

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            router = MessageRouter()
            result = await router.route_message(mock_update, mock_context)

        # Terminal should win (checked first)
        assert result["route"] == "terminal"

    @pytest.mark.asyncio
    async def test_vibe_before_ai(self, mock_update, mock_context):
        """Vibe coding is checked before AI response."""
        from tg_bot.routing import MessageRouter

        mock_update.message.text = "jarvis fix the bug"
        mock_update.effective_user.id = 12345

        with patch.dict(os.environ, {"TELEGRAM_ADMIN_IDS": "12345"}):
            router = MessageRouter()
            result = await router.route_message(mock_update, mock_context)

        # Vibe should win over AI
        assert result["route"] == "vibe_coding"
