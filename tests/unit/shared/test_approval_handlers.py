"""Tests for bots.shared.approval_handlers module."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import bots.shared.action_confirmation as ac_mod
import bots.shared.approval_handlers as mod


@pytest.fixture(autouse=True)
def patch_dirs_and_reset(tmp_path, monkeypatch):
    """Reset singleton and redirect file storage."""
    mod._confirmation = None
    monkeypatch.setattr(ac_mod, "CONFIRMATIONS_DIR", tmp_path)
    yield
    mod._confirmation = None


@pytest.fixture
def mock_bot():
    """Create a mock AsyncTeleBot that captures handler registrations."""
    bot = MagicMock()
    handlers = {}

    def message_handler(commands=None, **kwargs):
        def decorator(func):
            for cmd in (commands or []):
                handlers[cmd] = func
            return func
        return decorator

    bot.message_handler = message_handler
    bot._handlers = handlers
    bot.reply_to = AsyncMock()
    return bot


class TestRegisterHandlers:
    def test_registers_approve_and_deny(self, mock_bot):
        mod.register_approval_handlers(mock_bot, bot_name="Test", admin_chat_id=123)
        assert "approve" in mock_bot._handlers
        assert "deny" in mock_bot._handlers

    def test_creates_confirmation_singleton(self, mock_bot):
        mod.register_approval_handlers(mock_bot, bot_name="Test", admin_chat_id=123)
        conf = mod.get_confirmation()
        assert conf is not None
        assert conf.bot_name == "Test"

    @pytest.mark.asyncio
    async def test_approve_handler(self, mock_bot, tmp_path):
        mod.register_approval_handlers(mock_bot, bot_name="Test", admin_chat_id=123)
        conf = mod.get_confirmation()

        # Create a pending action
        result = await conf.request_confirmation("buy_token", "Buy SOL")
        cid = result["id"]

        msg = MagicMock()
        msg.text = f"/approve {cid}"
        msg.chat.id = 123
        msg.from_user.id = 123

        await mock_bot._handlers["approve"](msg)
        mock_bot.reply_to.assert_called_once()
        assert "Approved" in mock_bot.reply_to.call_args[0][1]

    @pytest.mark.asyncio
    async def test_deny_handler(self, mock_bot, tmp_path):
        mod.register_approval_handlers(mock_bot, bot_name="Test", admin_chat_id=123)
        conf = mod.get_confirmation()

        result = await conf.request_confirmation("buy_token")
        cid = result["id"]

        msg = MagicMock()
        msg.text = f"/deny {cid}"
        msg.chat.id = 123
        msg.from_user.id = 123

        await mock_bot._handlers["deny"](msg)
        assert "Denied" in mock_bot.reply_to.call_args[0][1]

    @pytest.mark.asyncio
    async def test_non_admin_ignored(self, mock_bot):
        mod.register_approval_handlers(mock_bot, bot_name="Test", admin_chat_id=123)

        msg = MagicMock()
        msg.text = "/approve abc"
        msg.chat.id = 999

        await mock_bot._handlers["approve"](msg)
        mock_bot.reply_to.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_id(self, mock_bot):
        mod.register_approval_handlers(mock_bot, bot_name="Test", admin_chat_id=123)

        msg = MagicMock()
        msg.text = "/approve nonexistent"
        msg.chat.id = 123
        msg.from_user.id = 123

        await mock_bot._handlers["approve"](msg)
        assert "Unknown" in mock_bot.reply_to.call_args[0][1]
