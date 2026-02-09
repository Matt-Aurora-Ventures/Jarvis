import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_demo_callback_does_not_push_nav_for_view_chart():
    """
    view_chart sends chart photos but typically returns the same AI report menu.
    It should not pollute the nav stack (otherwise Previous Menu can get "stuck").
    """
    from tg_bot.handlers.demo import demo_callback

    mock_query = MagicMock()
    mock_query.data = "demo:view_chart"
    mock_query.answer = AsyncMock(return_value=None)
    mock_query.message = MagicMock()
    mock_query.message.edit_text = AsyncMock()

    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user = MagicMock(id=12345, username="admin")
    mock_update.effective_message = MagicMock()
    mock_update.effective_message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.user_data = {
        "demo_nav_stack": ["demo:main"],
        "demo_current_page": "demo:ai_report",
    }

    config = MagicMock()
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

    assert mock_context.user_data.get("demo_nav_stack") == ["demo:main"]
    assert mock_context.user_data.get("demo_current_page") == "demo:ai_report"


@pytest.mark.asyncio
async def test_demo_callback_does_not_push_nav_for_copy_ca_side_effect():
    """
    copy_ca sends a helper message but should not affect navigation history.
    """
    from tg_bot.handlers.demo import demo_callback

    mock_query = MagicMock()
    mock_query.data = "demo:copy_ca:tok123"
    mock_query.answer = AsyncMock(return_value=None)
    mock_query.message = MagicMock()
    mock_query.message.edit_text = AsyncMock()

    mock_update = MagicMock()
    mock_update.callback_query = mock_query
    mock_update.effective_user = MagicMock(id=12345, username="admin")
    mock_update.effective_message = MagicMock()
    mock_update.effective_message.reply_text = AsyncMock()

    mock_context = MagicMock()
    mock_context.user_data = {
        "demo_nav_stack": ["demo:main"],
        "demo_current_page": "demo:trending",
    }

    config = MagicMock()
    config.is_admin = lambda _uid, _username=None: True

    router = MagicMock()
    # Side-effect handlers return (None, None) and edit/send their own message.
    router.route = AsyncMock(return_value=(None, None))

    with (
        patch("tg_bot.handlers.demo.demo_core.get_config", return_value=config),
        patch("tg_bot.handlers.demo.demo_core._process_demo_exit_checks", new_callable=AsyncMock, return_value=None),
        patch("tg_bot.handlers.demo.demo_core._get_demo_engine", new_callable=AsyncMock, side_effect=Exception("skip")),
        patch("tg_bot.handlers.demo.demo_core.get_market_regime", new_callable=AsyncMock, return_value={}),
        patch("tg_bot.handlers.demo.demo_core.get_callback_router", return_value=router),
    ):
        await demo_callback(mock_update, mock_context)

    assert mock_context.user_data.get("demo_nav_stack") == ["demo:main"]
    assert mock_context.user_data.get("demo_current_page") == "demo:trending"

