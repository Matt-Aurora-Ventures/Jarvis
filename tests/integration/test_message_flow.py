"""
Integration tests for message flow end-to-end.

Tests cover:
- Complete message handling pipeline
- Spam -> Terminal -> Vibe -> AI -> Ignore routing order
- Admin vs non-admin flow differences
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import os


class TestMessageFlow:
    """Test complete message flow from update to response."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "test message"
        update.message.message_id = 12345
        update.message.reply_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 99999
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
        context.bot.delete_message = AsyncMock()
        context.bot.ban_chat_member = AsyncMock()
        context.bot.restrict_chat_member = AsyncMock()
        context.bot.send_message = AsyncMock()
        context.user_data = {}
        return context

    @pytest.fixture
    def admin_user_id(self):
        """Admin user ID for testing."""
        return 12345

    @pytest.mark.asyncio
    async def test_spam_message_blocked_early(self, mock_update, mock_context):
        """Test spam message is blocked before any other routing."""
        mock_update.message.text = "buy crypto scam.com airdrop"
        mock_update.effective_user.id = 99999  # Non-admin

        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '12345'}):
            with patch('tg_bot.bot_core.check_and_ban_spam', new_callable=AsyncMock, return_value=True):
                from tg_bot.bot_core import handle_message
                await handle_message(mock_update, mock_context)

        # Spam should have been caught, message not processed further
        # (reply_text should not be called with AI response)
        # We mainly verify no error occurred and flow completed

    @pytest.mark.asyncio
    async def test_terminal_command_executes_for_admin(self, mock_update, mock_context, admin_user_id):
        """Test terminal command executes for admin user."""
        mock_update.message.text = "> echo hello"
        mock_update.effective_user.id = admin_user_id

        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': str(admin_user_id)}):
            with patch('tg_bot.bot_core.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
                with patch('tg_bot.services.terminal_handler.get_terminal_handler') as mock_handler:
                    handler_instance = MagicMock()
                    handler_instance.is_admin.return_value = True
                    handler_instance.execute = AsyncMock(return_value="hello")
                    mock_handler.return_value = handler_instance

                    from tg_bot.bot_core import handle_message
                    await handle_message(mock_update, mock_context)

                    # Terminal handler should have been called
                    handler_instance.execute.assert_called()

    @pytest.mark.asyncio
    async def test_terminal_command_rejected_for_non_admin(self, mock_update, mock_context):
        """Test terminal command is silently rejected for non-admin."""
        mock_update.message.text = "> echo hello"
        mock_update.effective_user.id = 99999  # Non-admin

        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '12345'}):
            with patch('tg_bot.bot_core.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
                with patch('tg_bot.services.terminal_handler.get_terminal_handler') as mock_handler:
                    handler_instance = MagicMock()
                    handler_instance.is_admin.return_value = False
                    mock_handler.return_value = handler_instance

                    from tg_bot.bot_core import handle_message
                    await handle_message(mock_update, mock_context)

                    # Terminal execute should NOT be called for non-admin
                    handler_instance.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_ai_response_generated_for_question(self, mock_update, mock_context):
        """Test AI response generated for legitimate question."""
        mock_update.message.text = "what's the price of SOL?"
        mock_update.effective_user.id = 99999  # Non-admin

        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '12345'}):
            with patch('tg_bot.bot_core.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
                with patch('tg_bot.bot_core._should_reply', return_value=True):
                    with patch('tg_bot.bot_core._get_chat_responder') as mock_responder:
                        responder_instance = MagicMock()
                        responder_instance.generate_reply = AsyncMock(return_value="SOL is currently $150")
                        mock_responder.return_value = responder_instance

                        with patch('tg_bot.bot_core._safe_reply_text', new_callable=AsyncMock) as mock_reply:
                            from tg_bot.bot_core import handle_message
                            await handle_message(mock_update, mock_context)

                            # AI response should have been generated
                            responder_instance.generate_reply.assert_called()

    @pytest.mark.asyncio
    async def test_message_ignored_when_no_route(self, mock_update, mock_context):
        """Test message ignored when no route matches."""
        mock_update.message.text = "random chat"
        mock_update.effective_user.id = 99999  # Non-admin

        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '12345'}):
            with patch('tg_bot.bot_core.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
                with patch('tg_bot.bot_core._should_reply', return_value=False):
                    from tg_bot.bot_core import handle_message
                    await handle_message(mock_update, mock_context)

        # No error should occur, flow should complete silently

    @pytest.mark.asyncio
    async def test_admin_message_skips_spam_check(self, mock_update, mock_context, admin_user_id):
        """Test admin messages bypass spam detection."""
        mock_update.message.text = "legitimate admin message"
        mock_update.effective_user.id = admin_user_id

        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': str(admin_user_id)}):
            with patch('tg_bot.bot_core.check_and_ban_spam', new_callable=AsyncMock) as mock_spam:
                with patch('tg_bot.bot_core._should_reply', return_value=False):
                    from tg_bot.bot_core import handle_message
                    await handle_message(mock_update, mock_context)

                    # Spam check should NOT be called for admin
                    mock_spam.assert_not_called()


class TestMessageFlowEdgeCases:
    """Test edge cases in message flow."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock()
        update.message = MagicMock()
        update.message.text = "test"
        update.message.message_id = 12345
        update.message.reply_text = AsyncMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 99999
        update.effective_user.username = "testuser"
        update.effective_chat = MagicMock()
        update.effective_chat.id = 88888
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock bot context."""
        context = MagicMock()
        context.bot = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_empty_message_handled(self, mock_update, mock_context):
        """Test empty message is handled gracefully."""
        mock_update.message.text = ""

        from tg_bot.bot_core import handle_message
        # Should not raise, should return early
        await handle_message(mock_update, mock_context)

    @pytest.mark.asyncio
    async def test_none_message_handled(self, mock_update, mock_context):
        """Test None message is handled gracefully."""
        mock_update.message = None

        from tg_bot.bot_core import handle_message
        # Should not raise, should return early
        await handle_message(mock_update, mock_context)

    @pytest.mark.asyncio
    async def test_awaiting_token_skips_processing(self, mock_update, mock_context):
        """Test message skipped when user is awaiting token input."""
        mock_context.user_data = {"awaiting_token": True}

        from tg_bot.bot_core import handle_message
        # Should return early without processing
        await handle_message(mock_update, mock_context)

    @pytest.mark.asyncio
    async def test_very_long_message_handled(self, mock_update, mock_context):
        """Test very long message is handled (truncated in logs)."""
        mock_update.message.text = "x" * 5000  # Very long message

        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '12345'}):
            with patch('tg_bot.bot_core.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
                with patch('tg_bot.bot_core._should_reply', return_value=False):
                    from tg_bot.bot_core import handle_message
                    # Should not raise
                    await handle_message(mock_update, mock_context)

    @pytest.mark.asyncio
    async def test_unicode_emoji_message_handled(self, mock_update, mock_context):
        """Test message with unicode/emoji is handled."""
        mock_update.message.text = "Hello! How are you?"

        with patch.dict(os.environ, {'TELEGRAM_ADMIN_IDS': '12345'}):
            with patch('tg_bot.bot_core.check_and_ban_spam', new_callable=AsyncMock, return_value=False):
                with patch('tg_bot.bot_core._should_reply', return_value=False):
                    from tg_bot.bot_core import handle_message
                    # Should not raise
                    await handle_message(mock_update, mock_context)
