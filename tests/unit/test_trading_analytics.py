from datetime import datetime

import pytest

from bots.treasury.trading.trading_analytics import TradingAnalytics
from bots.treasury.trading.types import Position, TradeDirection, TradeStatus


def _pos(
    position_id: str,
    status: TradeStatus,
    pnl_usd: float = 0.0,
    entry_price: float = 1.0,
    current_price: float = 1.0,
    amount_usd: float = 100.0,
    opened_at: str = None,
    closed_at: str = None,
) -> Position:
    now = datetime.utcnow().isoformat()
    return Position(
        id=position_id,
        token_mint="So11111111111111111111111111111111111111112",
        token_symbol="SOL",
        direction=TradeDirection.LONG,
        entry_price=entry_price,
        current_price=current_price,
        amount=1.0,
        amount_usd=amount_usd,
        take_profit_price=1.2,
        stop_loss_price=0.9,
        status=status,
        opened_at=opened_at or now,
        closed_at=closed_at,
        pnl_usd=pnl_usd,
        pnl_pct=(pnl_usd / amount_usd) * 100 if amount_usd else 0.0,
    )


def test_calculate_daily_pnl():
    today = datetime.utcnow().isoformat()

    closed_win = _pos("c1", TradeStatus.CLOSED, pnl_usd=10.0, closed_at=today)
    closed_loss = _pos("c2", TradeStatus.CLOSED, pnl_usd=-5.0, closed_at=today)

    open_pos = _pos(
        "o1",
        TradeStatus.OPEN,
        entry_price=1.0,
        current_price=1.02,
        opened_at=today,
    )

    pnl = TradingAnalytics.calculate_daily_pnl([closed_win, closed_loss], [open_pos])
    assert pnl == pytest.approx(10.0 - 5.0 + 2.0)


def test_generate_report():
    today = datetime.utcnow().isoformat()

    closed_win = _pos("c1", TradeStatus.CLOSED, pnl_usd=10.0, closed_at=today)
    closed_loss = _pos("c2", TradeStatus.CLOSED, pnl_usd=-5.0, closed_at=today)
    open_pos = _pos("o1", TradeStatus.OPEN, entry_price=1.0, current_price=1.05, opened_at=today)

    report = TradingAnalytics.generate_report([closed_win, closed_loss], [open_pos])

    assert report.total_trades == 2
    assert report.winning_trades == 1
    assert report.losing_trades == 1
    assert report.win_rate == pytest.approx(50.0)
    assert report.total_pnl_usd == pytest.approx(5.0)
    assert report.total_pnl_pct == pytest.approx(2.5)
    assert report.best_trade_pnl == pytest.approx(10.0)
    assert report.worst_trade_pnl == pytest.approx(-5.0)
    assert report.avg_trade_pnl == pytest.approx(2.5)
    assert report.average_win_usd == pytest.approx(10.0)
    assert report.average_loss_usd == pytest.approx(-5.0)
    assert report.open_positions == 1
    assert report.unrealized_pnl > 0
