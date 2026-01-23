import pytest
from unittest.mock import AsyncMock, Mock

from telegram.ext import ContextTypes

from tg_bot.handlers import demo as demo_mod


class DummyJupiter:
    async def get_token_price(self, _mint: str) -> float:
        return 1.0


@pytest.mark.asyncio
async def test_exit_triggers_take_profit_and_stop_loss(monkeypatch):
    monkeypatch.setattr(demo_mod, "_get_jupiter_client", lambda: DummyJupiter())

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {"trailing_stops": []}

    positions = [
        {
            "id": "p1",
            "symbol": "AAA",
            "entry_price": 100,
            "current_price": 120,
            "tp_percent": 10,
            "sl_percent": 20,
        },
        {
            "id": "p2",
            "symbol": "BBB",
            "entry_price": 100,
            "current_price": 80,
            "tp_percent": 50,
            "sl_percent": 10,
        },
    ]

    alerts = await demo_mod._check_demo_exit_triggers(context, positions)
    types = {a["type"] for a in alerts}

    assert "take_profit" in types
    assert "stop_loss" in types
    assert positions[0].get("tp_triggered") is True
    assert positions[1].get("sl_triggered") is True


@pytest.mark.asyncio
async def test_exit_triggers_trailing_stop(monkeypatch):
    monkeypatch.setattr(demo_mod, "_get_jupiter_client", lambda: DummyJupiter())

    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {
        "trailing_stops": [
            {
                "id": "ts1",
                "position_id": "p1",
                "trail_percent": 10,
                "highest_price": 120,
                "current_stop_price": 108,
                "active": True,
            }
        ]
    }

    positions = [
        {
            "id": "p1",
            "symbol": "AAA",
            "entry_price": 100,
            "current_price": 95,
        }
    ]

    alerts = await demo_mod._check_demo_exit_triggers(context, positions)
    assert any(alert["type"] == "trailing_stop" for alert in alerts)
    stop = context.user_data["trailing_stops"][0]
    assert stop.get("triggered") is True
    assert stop.get("active") is False


@pytest.mark.asyncio
async def test_maybe_execute_exit_runs_when_enabled(monkeypatch):
    context = Mock(spec=ContextTypes.DEFAULT_TYPE)
    context.user_data = {"ai_auto_trade": True, "wallet_address": "demo_wallet"}

    position = {"id": "p1", "symbol": "AAA", "address": "mint", "amount": 1.0}
    alert = {"type": "stop_loss", "position": position}

    monkeypatch.setenv("DEMO_TPSL_AUTO_EXECUTE", "1")
    monkeypatch.setattr(
        demo_mod,
        "_execute_swap_with_fallback",
        AsyncMock(return_value={"success": True, "tx_hash": "txhash", "source": "jupiter"}),
    )

    result = await demo_mod._maybe_execute_exit(context, alert)
    assert result is True
    assert position.get("exit_tx") == "txhash"
    assert position.get("exit_source") == "jupiter"
