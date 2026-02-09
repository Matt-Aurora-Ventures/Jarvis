import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from telegram.error import TimedOut


@pytest.mark.asyncio
async def test_demo_callback_does_not_crash_on_callback_answer_timeout():
    """
    Regression: callback queries can intermittently time out (telegram.error.TimedOut).

    demo_callback should treat query.answer() timeouts as non-fatal and continue routing
    instead of bubbling up to the global error handler (which spams the admin/user).
    """
    from tg_bot.handlers.demo import demo_callback

    # CallbackQuery mock
    mock_query = MagicMock()
    mock_query.data = "demo:main"
    mock_query.answer = AsyncMock(side_effect=TimedOut())
    mock_query.message = MagicMock()
    mock_query.message.edit_text = AsyncMock()
    mock_query.message.chat_id = 12345

    # Update mock
    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user = MagicMock()
    mock_update.effective_user.id = 12345
    mock_update.effective_user.username = "admin"
    mock_update.effective_chat = MagicMock()
    mock_update.effective_chat.id = 12345
    mock_update.effective_message = MagicMock()
    mock_update.effective_message.reply_text = AsyncMock()

    # Context mock
    mock_context = MagicMock()
    mock_context.user_data = {}
    mock_context.bot = MagicMock()

    # Make the user admin, and keep the handler fast/deterministic.
    config = MagicMock()
    config.admin_ids = {12345}
    config.is_admin = lambda _uid, _username=None: True

    router = MagicMock()
    router.route = AsyncMock(return_value=("OK", None))

    with (
        patch("tg_bot.handlers.demo.demo_core.get_config", return_value=config),
        patch("tg_bot.handlers.demo.demo_core._process_demo_exit_checks", new_callable=AsyncMock, return_value=None),
        patch("tg_bot.handlers.demo.demo_core._get_demo_engine", new_callable=AsyncMock, side_effect=Exception("skip")),
        patch("tg_bot.handlers.demo.demo_core.get_market_regime", new_callable=AsyncMock, return_value={}),
        patch("tg_bot.handlers.demo.demo_core.get_callback_router", return_value=router),
    ):
        await demo_callback(mock_update, mock_context)

    # If demo_callback bubbled up, the global error handler would reply with a generic error.
    mock_update.effective_message.reply_text.assert_not_called()
    # Routing should still happen.
    mock_query.message.edit_text.assert_called()

