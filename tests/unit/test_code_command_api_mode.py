from unittest.mock import AsyncMock, Mock

import pytest
from telegram import Update, User, Chat, Message
from telegram.ext import ContextTypes

from tg_bot import bot_core


class DummyConfig:
    def is_admin(self, *_args, **_kwargs):
        return True


class DummyBridge:
    def __init__(self):
        self.memory = Mock()
        self.memory.add_message = Mock()


def _build_update() -> Update:
    user = Mock(spec=User)
    user.id = 123
    user.username = "admin"

    chat = Mock(spec=Chat)
    chat.id = 111
    chat.type = "private"

    message = Mock(spec=Message)
    message.reply_text = AsyncMock()
    message.edit_text = AsyncMock()

    update = Mock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.message = message
    return update


def _build_context() -> ContextTypes.DEFAULT_TYPE:
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = ["do", "thing"]
    context.bot = Mock()
    context.bot.send_message = AsyncMock()
    return context


@pytest.mark.asyncio
async def test_code_command_reports_api_not_configured(monkeypatch):
    class DummyHandler:
        USE_API_MODE = True
        _api_mode_available = False
        _claude_path = None

    monkeypatch.setattr(bot_core, "get_config", lambda: DummyConfig())
    monkeypatch.setattr("tg_bot.services.claude_cli_handler.get_claude_cli_handler", lambda: DummyHandler())
    monkeypatch.setattr("core.telegram_console_bridge.get_console_bridge", lambda: DummyBridge())

    update = _build_update()
    context = _build_context()

    await bot_core.code(update, context)

    assert update.message.reply_text.called
    args, kwargs = update.message.reply_text.call_args
    text = args[0] if args else kwargs.get("text", "")
    assert "Claude API not configured" in text


@pytest.mark.asyncio
async def test_code_command_sends_summary_on_success(monkeypatch):
    class DummyHandler:
        USE_API_MODE = True
        _api_mode_available = True
        _claude_path = None

        async def execute(self, *_args, **_kwargs):
            return True, "summary ok", "details ok"

    monkeypatch.setattr(bot_core, "get_config", lambda: DummyConfig())
    monkeypatch.setattr("tg_bot.services.claude_cli_handler.get_claude_cli_handler", lambda: DummyHandler())
    monkeypatch.setattr("core.telegram_console_bridge.get_console_bridge", lambda: DummyBridge())

    update = _build_update()
    context = _build_context()

    await bot_core.code(update, context)

    assert context.bot.send_message.called
    args, kwargs = context.bot.send_message.call_args
    text = kwargs.get("text") or (args[1] if len(args) > 1 else "")
    assert "Summary:" in text
    assert "summary ok" in text
