"""
Tests for TelegramClient implementation.

TDD Phase 1: Write failing tests first.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestTelegramClientBasics:
    """Basic tests for TelegramClient."""

    def test_import_telegram_client(self):
        """Should be able to import TelegramClient."""
        from core.api.clients.telegram import TelegramClient
        assert TelegramClient is not None

    def test_telegram_client_inherits_base(self):
        """TelegramClient should inherit from BaseAPIClient."""
        from core.api.clients.telegram import TelegramClient
        from core.api.base import BaseAPIClient

        assert issubclass(TelegramClient, BaseAPIClient)

    def test_telegram_client_provider(self):
        """TelegramClient should have provider 'telegram'."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")
        assert client.provider == "telegram"

    def test_telegram_client_base_url(self):
        """TelegramClient should use Telegram API base URL."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")
        assert "api.telegram.org" in client.base_url


class TestTelegramClientConfiguration:
    """Tests for TelegramClient configuration."""

    def test_bot_token_from_env(self):
        """Should read bot token from environment if not provided."""
        from core.api.clients.telegram import TelegramClient

        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'env-token'}):
            client = TelegramClient()
            assert client._bot_token is not None

    def test_bot_token_from_argument(self):
        """Should use bot token from argument if provided."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="arg-token")
        assert client._bot_token == "arg-token"

    def test_base_url_includes_token(self):
        """Base URL should include bot token."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="123456:ABC")
        assert "123456:ABC" in client.base_url


class TestTelegramClientSendMessage:
    """Tests for send_message method."""

    @pytest.mark.asyncio
    async def test_send_message_method_exists(self):
        """send_message() method should exist."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")
        assert hasattr(client, 'send_message')

    @pytest.mark.asyncio
    async def test_send_message_returns_response(self):
        """send_message() should return a TelegramResponse."""
        from core.api.clients.telegram import TelegramClient, TelegramResponse

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {
                "ok": True,
                "result": {
                    "message_id": 123,
                    "chat": {"id": 456}
                }
            })

            response = await client.send_message(chat_id=456, text="Hello!")

            assert isinstance(response, TelegramResponse)
            assert response.success is True
            assert response.message_id == 123

    @pytest.mark.asyncio
    async def test_send_message_with_parse_mode(self):
        """send_message() should support parse_mode."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {"ok": True, "result": {"message_id": 1}})

            await client.send_message(
                chat_id=123,
                text="*Bold*",
                parse_mode="Markdown"
            )

            call_args = mock_req.call_args
            assert "parse_mode" in str(call_args)

    @pytest.mark.asyncio
    async def test_send_message_with_reply_markup(self):
        """send_message() should support reply_markup."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {"ok": True, "result": {"message_id": 1}})

            keyboard = {"inline_keyboard": [[{"text": "Button", "callback_data": "btn"}]]}

            await client.send_message(
                chat_id=123,
                text="Choose:",
                reply_markup=keyboard
            )

            call_args = mock_req.call_args
            assert "reply_markup" in str(call_args)


class TestTelegramClientSendPhoto:
    """Tests for send_photo method."""

    @pytest.mark.asyncio
    async def test_send_photo_method_exists(self):
        """send_photo() method should exist."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")
        assert hasattr(client, 'send_photo')

    @pytest.mark.asyncio
    async def test_send_photo_with_url(self):
        """send_photo() should support photo URL."""
        from core.api.clients.telegram import TelegramClient, TelegramResponse

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {
                "ok": True,
                "result": {"message_id": 124}
            })

            response = await client.send_photo(
                chat_id=456,
                photo="https://example.com/image.jpg"
            )

            assert response.success is True
            assert response.message_id == 124

    @pytest.mark.asyncio
    async def test_send_photo_with_caption(self):
        """send_photo() should support caption."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {"ok": True, "result": {"message_id": 1}})

            await client.send_photo(
                chat_id=123,
                photo="https://example.com/image.jpg",
                caption="My photo"
            )

            call_args = mock_req.call_args
            assert "caption" in str(call_args)


class TestTelegramClientEditMessage:
    """Tests for edit_message method."""

    @pytest.mark.asyncio
    async def test_edit_message_method_exists(self):
        """edit_message() method should exist."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")
        assert hasattr(client, 'edit_message')

    @pytest.mark.asyncio
    async def test_edit_message_text(self):
        """edit_message() should update message text."""
        from core.api.clients.telegram import TelegramClient, TelegramResponse

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {
                "ok": True,
                "result": {"message_id": 123}
            })

            response = await client.edit_message(
                chat_id=456,
                message_id=123,
                text="Updated text"
            )

            assert response.success is True

    @pytest.mark.asyncio
    async def test_edit_message_preserves_message_id(self):
        """edit_message() should return same message_id."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {
                "ok": True,
                "result": {"message_id": 999}
            })

            response = await client.edit_message(
                chat_id=456,
                message_id=999,
                text="Updated"
            )

            assert response.message_id == 999


class TestTelegramClientDeleteMessage:
    """Tests for delete_message method."""

    @pytest.mark.asyncio
    async def test_delete_message_method_exists(self):
        """delete_message() method should exist."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")
        assert hasattr(client, 'delete_message')

    @pytest.mark.asyncio
    async def test_delete_message_returns_success(self):
        """delete_message() should return success status."""
        from core.api.clients.telegram import TelegramClient, TelegramResponse

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (200, {"ok": True, "result": True})

            response = await client.delete_message(chat_id=456, message_id=123)

            assert isinstance(response, TelegramResponse)
            assert response.success is True


class TestTelegramResponse:
    """Tests for TelegramResponse dataclass."""

    def test_telegram_response_success(self):
        """TelegramResponse should store successful response."""
        from core.api.clients.telegram import TelegramResponse

        response = TelegramResponse(
            success=True,
            message_id=123,
            chat_id=456
        )

        assert response.success is True
        assert response.message_id == 123
        assert response.chat_id == 456
        assert response.error is None

    def test_telegram_response_failure(self):
        """TelegramResponse should store error response."""
        from core.api.clients.telegram import TelegramResponse

        response = TelegramResponse(
            success=False,
            error="Chat not found",
            error_code=400
        )

        assert response.success is False
        assert response.error == "Chat not found"
        assert response.error_code == 400


class TestTelegramClientErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_handles_chat_not_found(self):
        """Should handle chat not found error."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (400, {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: chat not found"
            })

            response = await client.send_message(chat_id=999, text="Test")

            assert response.success is False
            assert "chat not found" in response.error.lower()

    @pytest.mark.asyncio
    async def test_handles_rate_limit(self):
        """Should handle rate limit error with retry_after."""
        from core.api.clients.telegram import TelegramClient

        client = TelegramClient(bot_token="test-token")

        with patch.object(client, '_make_request', new_callable=AsyncMock) as mock_req:
            mock_req.return_value = (429, {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests: retry after 60",
                "parameters": {"retry_after": 60}
            })

            response = await client.send_message(chat_id=123, text="Test")

            assert response.success is False
            assert response.error_code == 429
            assert response.retry_after == 60
