import pytest

from bots.treasury.trading.types import Position, TradeDirection, TradeStatus


def test_position_from_dict_sets_tp_sl_defaults():
    data = {
        "id": "p1",
        "token_mint": "So11111111111111111111111111111111111111112",
        "token_symbol": "SOL",
        "direction": "LONG",
        "entry_price": 10.0,
        "current_price": 10.0,
        "amount": 1.0,
        "amount_usd": 100.0,
        "take_profit_price": 0,
        "stop_loss_price": 0,
        "status": "OPEN",
        "opened_at": "2026-01-24T00:00:00",
    }

    pos = Position.from_dict(data)
    assert pos.take_profit_price == pytest.approx(12.0)
    assert pos.stop_loss_price == pytest.approx(9.0)


def test_position_unrealized_pnl_calculation():
    pos = Position(
        id="p2",
        token_mint="So11111111111111111111111111111111111111112",
        token_symbol="SOL",
        direction=TradeDirection.LONG,
        entry_price=10.0,
        current_price=12.0,
        amount=1.0,
        amount_usd=100.0,
        take_profit_price=12.0,
        stop_loss_price=9.0,
        status=TradeStatus.OPEN,
        opened_at="2026-01-24T00:00:00",
    )

    assert pos.unrealized_pnl == pytest.approx(20.0)
    assert pos.unrealized_pnl_pct == pytest.approx(20.0)


def test_position_to_dict_round_trip():
    pos = Position(
        id="p3",
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
        opened_at="2026-01-24T00:00:00",
    )

    data = pos.to_dict()
    assert data["direction"] == "LONG"
    assert data["status"] == "OPEN"
    round_trip = Position.from_dict(data)
    assert round_trip.id == pos.id
    assert round_trip.status == pos.status
