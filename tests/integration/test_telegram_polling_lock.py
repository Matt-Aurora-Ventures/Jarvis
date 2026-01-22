"""Integration-style stub to ensure polling lock prevents duplicates."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class _DummyLock:
    def close(self):
        return None


@pytest.mark.asyncio
async def test_public_bot_polling_lock_prevents_duplicates(monkeypatch):
    from tg_bot.public_trading_bot_integration import PublicTradingBotIntegration
    from core.utils import instance_lock

    bot1 = PublicTradingBotIntegration(bot_token="test-token")
    bot2 = PublicTradingBotIntegration(bot_token="test-token")

    for bot in (bot1, bot2):
        bot.app = MagicMock()
        bot.app.updater = MagicMock()
        bot.app.updater.start_polling = AsyncMock()

    locks = [_DummyLock(), None]

    def _acquire(*_args, **_kwargs):
        return locks.pop(0)

    monkeypatch.setattr(instance_lock, "acquire_instance_lock", _acquire)

    ok1 = await bot1.start_polling()
    ok2 = await bot2.start_polling()

    assert ok1 is True
    assert ok2 is False
    bot1.app.updater.start_polling.assert_called_once()
    bot2.app.updater.start_polling.assert_not_called()
