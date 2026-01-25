import pytest
from unittest.mock import AsyncMock, Mock, patch

from tests.demo_golden.harness import _build_callback_update, _build_context, _build_mock_update
from tg_bot.handlers import demo as demo_mod


@pytest.mark.asyncio
async def test_demo_callback_requires_admin():
    base_update = _build_mock_update(user_id=222222, username="user")
    cb_update = _build_callback_update("demo:main", base_update)
    cb_update.callback_query.answer = AsyncMock()
    cb_update.callback_query.message.edit_text = AsyncMock()
    context = _build_context()

    config = Mock()
    config.admin_ids = set()
    config.is_admin = lambda _uid, _username=None: False

    with patch("tg_bot.config.get_config", return_value=config):
        await demo_mod.demo_callback(cb_update, context)

    cb_update.callback_query.answer.assert_called()
    args, kwargs = cb_update.callback_query.answer.call_args
    assert args and "Admin only" in args[0]
    cb_update.callback_query.message.edit_text.assert_not_called()


@pytest.mark.asyncio
async def test_demo_message_handler_requires_admin():
    update = _build_mock_update(user_id=222222, username="user")
    update.message.text = "test"
    context = _build_context()

    config = Mock()
    config.admin_ids = set()
    config.is_admin = lambda _uid, _username=None: False

    with patch("tg_bot.config.get_config", return_value=config):
        await demo_mod.demo_message_handler(update, context)

    update.message.reply_text.assert_called()
    args, _kwargs = update.message.reply_text.call_args
    assert args and "Unauthorized" in args[0]
