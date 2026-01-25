"""
Unit tests for MessageRouter class.

Tests cover:
- Message routing logic for all routes (spam, terminal, vibe, AI, ignore)
- Admin detection
- Terminal command detection
- Vibe request detection
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import os


class TestMessageRouter:
    """Test MessageRouter class in tg_bot.routing.message_router."""

    @pytest.fixture
    def router(self):
        """Create MessageRouter instance with mock admin IDs."""
        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '12345,67890'}):
            from tg_bot.routing.message_router import MessageRouter
            return MessageRouter()

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "test message"
        update.message.message_id = 12345
        update.effective_user = MagicMock()
        update.effective_user.id = 99999  # Non-admin by default
        update.effective_user.username = "testuser"
        update.effective_chat = MagicMock()
        update.effective_chat.id = 88888
        update.effective_chat.type = "group"
        update.effective_chat.title = "Test Group"
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock bot context."""
        context = MagicMock()
        context.bot = MagicMock()
        context.user_data = {}
        return context

    # ==========================================================================
    # Admin Detection Tests
    # ==========================================================================

    def test_is_admin_returns_true_for_admin_id(self, router):
        """Test admin detection for admin user ID."""
        assert router.is_admin(12345) is True
        assert router.is_admin(67890) is True

    def test_is_admin_returns_false_for_non_admin(self, router):
        """Test admin detection for non-admin user ID."""
        assert router.is_admin(99999) is False
        assert router.is_admin(11111) is False

    def test_admin_ids_loaded_from_env(self):
        """Test admin IDs are loaded from environment variable."""
        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '111,222,333'}):
            from tg_bot.routing.message_router import MessageRouter
            router = MessageRouter()
            assert router.is_admin(111) is True
            assert router.is_admin(222) is True
            assert router.is_admin(333) is True
            assert router.is_admin(444) is False

    # ==========================================================================
    # Terminal Command Detection Tests
    # ==========================================================================

    def test_is_terminal_command_with_gt_prefix(self, router):
        """Test terminal command detection with > prefix."""
        assert router._is_terminal_command("> ls -la") is True
        assert router._is_terminal_command(">pwd") is True
        assert router._is_terminal_command("> echo hello") is True

    def test_is_terminal_command_with_term_prefix(self, router):
        """Test terminal command detection with /term prefix."""
        assert router._is_terminal_command("/term pwd") is True
        assert router._is_terminal_command("/term ls -la") is True
        assert router._is_terminal_command("/TERM echo test") is True

    def test_is_terminal_command_returns_false_for_normal_message(self, router):
        """Test terminal command detection returns false for normal messages."""
        assert router._is_terminal_command("normal message") is False
        assert router._is_terminal_command("what's up?") is False
        assert router._is_terminal_command("hello > there") is False

    # ==========================================================================
    # Vibe Request Detection Tests
    # ==========================================================================

    def test_is_vibe_request_with_code_prefix(self, router):
        """Test vibe request detection with code: prefix."""
        assert router._is_vibe_request("code: fix the bug") is True
        assert router._is_vibe_request("Code: implement feature") is True

    def test_is_vibe_request_with_vibe_prefix(self, router):
        """Test vibe request detection with vibe: prefix."""
        assert router._is_vibe_request("vibe: add tests") is True
        assert router._is_vibe_request("VIBE: refactor this") is True

    def test_is_vibe_request_with_ralph_wiggum(self, router):
        """Test vibe request detection with ralph wiggum prefix."""
        assert router._is_vibe_request("ralph wiggum improve everything") is True
        assert router._is_vibe_request("Ralph Wiggum fix bugs") is True

    def test_is_vibe_request_with_jarvis_action_prefixes(self, router):
        """Test vibe request detection with jarvis action prefixes."""
        assert router._is_vibe_request("jarvis fix the bug") is True
        assert router._is_vibe_request("jarvis add feature") is True
        assert router._is_vibe_request("jarvis create component") is True
        assert router._is_vibe_request("jarvis implement this") is True
        assert router._is_vibe_request("jarvis build the system") is True

    def test_is_vibe_request_returns_false_for_normal_message(self, router):
        """Test vibe request returns false for normal messages."""
        assert router._is_vibe_request("normal question") is False
        assert router._is_vibe_request("what's the price of SOL?") is False
        assert router._is_vibe_request("hello jarvis") is False  # Just greeting, not action

    # ==========================================================================
    # Message Routing Tests
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_route_empty_message(self, router, mock_update, mock_context):
        """Test routing returns ignored for empty message."""
        mock_update.message.text = ""

        result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "ignored"
        assert result["should_continue"] is False

    @pytest.mark.asyncio
    async def test_route_none_message(self, router, mock_update, mock_context):
        """Test routing returns ignored for None message."""
        mock_update.message = None

        result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "ignored"
        assert result["should_continue"] is False

    @pytest.mark.asyncio
    async def test_route_spam_message_blocked(self, router, mock_update, mock_context):
        """Test spam message routing - should be blocked."""
        mock_update.message.text = "buy crypto scam.com"
        mock_update.effective_user.id = 99999  # Non-admin

        with patch('tg_bot.routing.message_router.check_and_ban_spam', new_callable=AsyncMock, return_value=True):
            result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "spam_blocked"
        assert result["should_continue"] is False
        assert result["data"]["is_spam"] is True

    @pytest.mark.asyncio
    async def test_route_terminal_command_admin(self, router, mock_update, mock_context):
        """Test terminal command routing for admin."""
        mock_update.message.text = "> ls -la"
        mock_update.effective_user.id = 12345  # Admin

        with patch('tg_bot.routing.message_router.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
            result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "terminal"
        assert result["should_continue"] is True
        assert result["data"]["is_admin"] is True

    @pytest.mark.asyncio
    async def test_route_terminal_command_non_admin(self, router, mock_update, mock_context):
        """Test terminal command routing for non-admin (rejected)."""
        mock_update.message.text = "> ls -la"
        mock_update.effective_user.id = 99999  # Non-admin

        with patch('tg_bot.routing.message_router.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
            result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "terminal"
        assert result["should_continue"] is False  # Rejected for non-admin
        assert result["data"]["is_admin"] is False

    @pytest.mark.asyncio
    async def test_route_vibe_request_admin(self, router, mock_update, mock_context):
        """Test vibe coding routing for admin."""
        mock_update.message.text = "jarvis fix the bug"
        mock_update.effective_user.id = 12345  # Admin
        mock_update.effective_user.username = "admin"

        with patch('tg_bot.routing.message_router.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
            result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "vibe_coding"
        assert result["should_continue"] is True
        assert result["data"]["user_id"] == 12345
        assert result["data"]["username"] == "admin"

    @pytest.mark.asyncio
    async def test_route_vibe_request_non_admin_falls_through(self, router, mock_update, mock_context):
        """Test vibe coding routing for non-admin falls through to AI/ignored."""
        mock_update.message.text = "jarvis fix the bug"
        mock_update.effective_user.id = 99999  # Non-admin

        with patch('tg_bot.routing.message_router.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
            with patch('tg_bot.routing.message_router._should_reply', return_value=False):
                with patch('tg_bot.routing.message_router._is_message_for_jarvis', return_value=False):
                    result = await router.route_message(mock_update, mock_context)

        # Non-admin vibe requests should fall through to AI or ignored
        assert result["route"] in ["ai_response", "ignored"]

    @pytest.mark.asyncio
    async def test_route_ai_response(self, router, mock_update, mock_context):
        """Test AI response routing for question."""
        mock_update.message.text = "what's the price of SOL?"
        mock_update.effective_user.id = 99999  # Non-admin

        with patch('tg_bot.routing.message_router.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
            with patch('tg_bot.routing.message_router._should_reply', return_value=True):
                result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "ai_response"
        assert result["should_continue"] is True
        assert result["data"]["text"] == "what's the price of SOL?"

    @pytest.mark.asyncio
    async def test_route_ignored_message(self, router, mock_update, mock_context):
        """Test message routing when no route matches."""
        mock_update.message.text = "random chat message"
        mock_update.effective_user.id = 99999  # Non-admin

        with patch('tg_bot.routing.message_router.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
            with patch('tg_bot.routing.message_router._should_reply', return_value=False):
                result = await router.route_message(mock_update, mock_context)

        assert result["route"] == "ignored"
        assert result["should_continue"] is False

    @pytest.mark.asyncio
    async def test_admin_skips_spam_check(self, router, mock_update, mock_context):
        """Test that admin messages skip spam detection."""
        mock_update.message.text = "buy crypto scam words"  # Would trigger spam for non-admin
        mock_update.effective_user.id = 12345  # Admin

        # Should NOT call spam check for admin
        with patch('tg_bot.routing.message_router.check_and_ban_spam', new_callable=AsyncMock) as mock_spam:
            with patch('tg_bot.routing.message_router._is_message_for_jarvis', return_value=True):
                result = await router.route_message(mock_update, mock_context)

        # Spam check should NOT be called for admin
        mock_spam.assert_not_called()
        # Should route to AI response for admin
        assert result["route"] in ["ai_response", "vibe_coding", "terminal"]
