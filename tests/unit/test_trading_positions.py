import json
from datetime import datetime

import pytest

from bots.treasury.trading import trading_positions as positions_mod
from bots.treasury.trading.trading_positions import PositionManager
from bots.treasury.trading.types import Position, TradeDirection, TradeStatus


def _make_position(position_id: str = "p1") -> Position:
    return Position(
        id=position_id,
        token_mint="So11111111111111111111111111111111111111112",
        token_symbol="SOL",
        direction=TradeDirection.LONG,
        entry_price=1.0,
        current_price=1.0,
        amount=1.0,
        amount_usd=100.0,
        take_profit_price=1.2,
        stop_loss_price=0.9,
        status=TradeStatus.OPEN,
        opened_at=datetime.utcnow().isoformat(),
    )


@pytest.mark.asyncio
async def test_add_and_close_position(tmp_path, monkeypatch):
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    positions_file = tmp_path / "positions.json"
    history_file = tmp_path / "history.json"

    manager = PositionManager(positions_file=positions_file, history_file=history_file)

    pos = _make_position("p1")
    manager.add_position(pos)

    assert positions_file.exists()
    with open(positions_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data[0]["id"] == "p1"

    closed = manager.close_position("p1", exit_price=1.5, reason="test")
    assert closed is not None
    assert closed.status == TradeStatus.CLOSED
    assert len(manager.positions) == 0
    assert len(manager.trade_history) == 1


@pytest.mark.asyncio
async def test_update_position_price_updates_pnl(tmp_path, monkeypatch):
    monkeypatch.setattr(positions_mod, "SAFE_STATE_AVAILABLE", False)

    manager = PositionManager(
        positions_file=tmp_path / "positions.json",
        history_file=tmp_path / "history.json",
    )

    pos = _make_position("p2")
    manager.add_position(pos)

    manager.update_position_price("p2", current_price=1.1)

    updated = manager.get_position("p2")
    assert updated is not None
    assert updated.current_price == 1.1
    assert updated.pnl_pct > 0
    assert updated.pnl_usd > 0
