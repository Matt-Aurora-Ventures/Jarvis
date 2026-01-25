import pytest
from unittest.mock import AsyncMock, Mock, patch

from tests.demo_golden.harness import _build_callback_update, _build_context, _build_mock_update
from tg_bot.handlers import demo as demo_mod


class DummyTreasury:
    address = "DemoWallet1111111111111111111111111111111111"


class DummyWallet:
    def get_treasury(self):
        return DummyTreasury()


class DummyEngine:
    dry_run = True
    wallet = DummyWallet()

    async def get_portfolio_value(self):
        return 1.0, 100.0

    async def update_positions(self):
        return None

    def get_open_positions(self):
        return []


@pytest.mark.asyncio
async def test_demo_hub_prestocks_graceful_message():
    base_update = _build_mock_update()
    cb_update = _build_callback_update("demo:hub_prestocks", base_update)
    cb_update.callback_query.answer = AsyncMock()
    cb_update.callback_query.message.edit_text = AsyncMock()
    context = _build_context()

    config = Mock()
    config.admin_ids = {base_update.effective_user.id}
    config.is_admin = lambda _uid, _username=None: True

    with patch("tg_bot.handlers.demo_legacy.get_config", return_value=config), \
        patch("tg_bot.handlers.demo.get_market_regime", new=AsyncMock(return_value={"regime": "BULL"})), \
        patch("tg_bot.handlers.demo_legacy._get_demo_engine", new=AsyncMock(return_value=DummyEngine())):
        await demo_mod.demo_callback(cb_update, context)

    assert cb_update.callback_query.message.edit_text.called
    args, kwargs = cb_update.callback_query.message.edit_text.call_args
    text = args[0] if args else kwargs.get("text", "")
    assert "PreStocks data is not live yet" in text
