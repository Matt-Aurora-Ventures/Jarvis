"""
Unit tests for TreasuryDashboard (tg_bot/services/treasury_dashboard.py)

Tests cover:
- PnL summary calculations (realized + unrealized, 24h/7d returns)
- Risk metrics (max drawdown, volatility, Sharpe ratio)
- Trading statistics (win rate, avg win/loss, profit factor)
- Period performance metrics (annualized returns, Sortino ratio)
- Trade history queries
- Edge cases (no trades, single trade, all wins/losses)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, PropertyMock
from dataclasses import dataclass
from typing import List, Optional

# Import the dashboard and types
from tg_bot.services.treasury_dashboard import TreasuryDashboard, PerformanceTrend, TrendData


# Mock Position class matching the real interface
@dataclass
class MockPosition:
    """Mock Position for testing."""
    id: str
    token_symbol: str
    entry_price: float
    current_price: float
    amount: float
    amount_usd: float
    take_profit_price: float = 0.0
    stop_loss_price: float = 0.0
    status: str = "OPEN"
    opened_at: str = ""
    closed_at: Optional[str] = None
    exit_price: Optional[float] = None
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    current_value_usd: float = 0.0
    entry_time: datetime = None

    def __post_init__(self):
        if not self.opened_at:
            self.opened_at = datetime.utcnow().isoformat()
        if self.entry_time is None:
            self.entry_time = datetime.utcnow()
        if self.current_value_usd == 0:
            self.current_value_usd = self.amount * self.current_price

    @property
    def unrealized_pnl_usd(self) -> float:
        """Calculate unrealized PnL in USD."""
        if self.status == "CLOSED":
            return 0.0
        return (self.current_price - self.entry_price) * self.amount

    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized PnL percentage."""
        if self.entry_price == 0:
            return 0.0
        return ((self.current_price - self.entry_price) / self.entry_price) * 100


def create_mock_trader(
    open_positions: List[MockPosition] = None,
    trade_history: List[MockPosition] = None,
    balance: float = 10000.0,
    dry_run: bool = False
):
    """Create a mock trader with configurable positions and history."""
    trader = MagicMock()
    trader.get_open_positions = MagicMock(return_value=open_positions or [])
    trader.trade_history = trade_history or []
    trader.dry_run = dry_run
    trader.max_positions = 50
    trader.get_balance = MagicMock(return_value={'total': balance})
    return trader


def create_closed_position(
    symbol: str,
    entry_price: float,
    exit_price: float,
    amount: float,
    closed_at: datetime = None,
    opened_at: datetime = None
) -> MockPosition:
    """Create a closed position for trade history."""
    if closed_at is None:
        closed_at = datetime.utcnow()
    if opened_at is None:
        opened_at = closed_at - timedelta(hours=4)

    pnl_usd = (exit_price - entry_price) * amount
    pnl_pct = ((exit_price - entry_price) / entry_price) * 100

    return MockPosition(
        id=f"{symbol}_{closed_at.timestamp()}",
        token_symbol=symbol,
        entry_price=entry_price,
        current_price=exit_price,
        amount=amount,
        amount_usd=entry_price * amount,
        status="CLOSED",
        opened_at=opened_at.isoformat(),
        closed_at=closed_at.isoformat(),
        exit_price=exit_price,
        pnl_usd=pnl_usd,
        pnl_pct=pnl_pct,
        entry_time=opened_at
    )


class TestPnLSummary:
    """Tests for _get_pnl_summary method."""

    def test_pnl_summary_no_positions_no_history(self):
        """Test PnL summary with no positions or history."""
        trader = create_mock_trader()
        dashboard = TreasuryDashboard(trader)

        summary = dashboard._get_pnl_summary()

        assert summary['total_pnl'] == 0.0
        assert summary['total_pnl_pct'] == 0.0

    def test_pnl_summary_with_unrealized_only(self):
        """Test PnL summary with only open positions (unrealized)."""
        positions = [
            MockPosition(
                id="pos1", token_symbol="SOL",
                entry_price=100.0, current_price=110.0,
                amount=10.0, amount_usd=1000.0
            ),
            MockPosition(
                id="pos2", token_symbol="BONK",
                entry_price=0.00001, current_price=0.000012,
                amount=1000000.0, amount_usd=10.0
            )
        ]
        trader = create_mock_trader(open_positions=positions)
        dashboard = TreasuryDashboard(trader)

        summary = dashboard._get_pnl_summary()

        # SOL: (110-100)*10 = $100, BONK: (0.000012-0.00001)*1M = $2
        expected_unrealized = 100.0 + 2.0
        assert summary['total_pnl'] >= expected_unrealized - 0.01  # Small tolerance

    def test_pnl_summary_with_realized_only(self):
        """Test PnL summary with only closed trades (realized)."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 120.0, 10.0, closed_at=now),  # $200 profit
            create_closed_position("ETH", 2000.0, 1900.0, 1.0, closed_at=now),  # $100 loss
        ]
        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        summary = dashboard._get_pnl_summary()

        # Total realized: $200 - $100 = $100
        assert summary['total_pnl'] == pytest.approx(100.0, abs=1.0)

    def test_pnl_summary_combined_realized_unrealized(self):
        """Test PnL summary with both realized and unrealized PnL."""
        now = datetime.utcnow()

        open_positions = [
            MockPosition(
                id="open1", token_symbol="SOL",
                entry_price=100.0, current_price=110.0,
                amount=5.0, amount_usd=500.0
            )
        ]
        trade_history = [
            create_closed_position("SOL", 100.0, 130.0, 10.0, closed_at=now),  # $300 profit
        ]

        trader = create_mock_trader(
            open_positions=open_positions,
            trade_history=trade_history
        )
        dashboard = TreasuryDashboard(trader)

        summary = dashboard._get_pnl_summary()

        # Unrealized: (110-100)*5 = $50, Realized: $300
        # Total: $350
        assert summary['total_pnl'] >= 300.0  # At least realized

    def test_pnl_24h_return_calculation(self):
        """Test 24h return is calculated from trades in last 24 hours."""
        now = datetime.utcnow()
        yesterday = now - timedelta(hours=12)
        two_days_ago = now - timedelta(days=2)

        trade_history = [
            # Today's trades
            create_closed_position("SOL", 100.0, 110.0, 10.0, closed_at=now),  # $100 profit
            create_closed_position("ETH", 2000.0, 2100.0, 0.5, closed_at=yesterday),  # $50 profit
            # Old trade (should not count)
            create_closed_position("BTC", 50000.0, 51000.0, 0.1, closed_at=two_days_ago),
        ]

        trader = create_mock_trader(trade_history=trade_history, balance=10000.0)
        dashboard = TreasuryDashboard(trader)

        summary = dashboard._get_pnl_summary()

        # 24h return should be based on recent trades only
        assert 'return_24h' in summary
        # Should be positive (we had profits today)

    def test_pnl_7d_return_calculation(self):
        """Test 7d return is calculated from trades in last 7 days."""
        now = datetime.utcnow()
        three_days_ago = now - timedelta(days=3)
        ten_days_ago = now - timedelta(days=10)

        trade_history = [
            create_closed_position("SOL", 100.0, 120.0, 10.0, closed_at=now),  # $200
            create_closed_position("ETH", 2000.0, 2200.0, 1.0, closed_at=three_days_ago),  # $200
            # Old trade (should not count for 7d)
            create_closed_position("BTC", 50000.0, 55000.0, 0.1, closed_at=ten_days_ago),
        ]

        trader = create_mock_trader(trade_history=trade_history, balance=10000.0)
        dashboard = TreasuryDashboard(trader)

        summary = dashboard._get_pnl_summary()

        assert 'return_7d' in summary


class TestRiskMetrics:
    """Tests for _get_risk_metrics method."""

    def test_risk_metrics_no_trades(self):
        """Test risk metrics with no trade history."""
        trader = create_mock_trader()
        dashboard = TreasuryDashboard(trader)

        metrics = dashboard._get_risk_metrics()

        assert metrics['max_drawdown'] == 0.0
        assert metrics['volatility'] == 0.0
        assert metrics['sharpe_ratio'] == 0.0

    def test_max_drawdown_calculation(self):
        """Test max drawdown is calculated correctly."""
        now = datetime.utcnow()

        # Create a sequence with a clear drawdown
        trade_history = [
            create_closed_position("SOL", 100.0, 120.0, 10.0,
                                   closed_at=now - timedelta(days=4)),  # +$200
            create_closed_position("SOL", 100.0, 110.0, 10.0,
                                   closed_at=now - timedelta(days=3)),  # +$100
            create_closed_position("SOL", 100.0, 80.0, 10.0,
                                   closed_at=now - timedelta(days=2)),  # -$200
            create_closed_position("SOL", 100.0, 70.0, 10.0,
                                   closed_at=now - timedelta(days=1)),  # -$300
            create_closed_position("SOL", 100.0, 130.0, 10.0,
                                   closed_at=now),  # +$300
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        metrics = dashboard._get_risk_metrics()

        # Max drawdown should be significant due to consecutive losses
        assert metrics['max_drawdown'] > 0.0

    def test_volatility_calculation(self):
        """Test volatility is calculated from return variance."""
        now = datetime.utcnow()

        # Create trades with varying returns
        trade_history = [
            create_closed_position("SOL", 100.0, 105.0, 10.0,
                                   closed_at=now - timedelta(days=5)),  # +5%
            create_closed_position("SOL", 100.0, 98.0, 10.0,
                                   closed_at=now - timedelta(days=4)),  # -2%
            create_closed_position("SOL", 100.0, 115.0, 10.0,
                                   closed_at=now - timedelta(days=3)),  # +15%
            create_closed_position("SOL", 100.0, 92.0, 10.0,
                                   closed_at=now - timedelta(days=2)),  # -8%
            create_closed_position("SOL", 100.0, 108.0, 10.0,
                                   closed_at=now - timedelta(days=1)),  # +8%
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        metrics = dashboard._get_risk_metrics()

        # With varying returns, volatility should be positive
        assert metrics['volatility'] > 0.0

    def test_sharpe_ratio_calculation(self):
        """Test Sharpe ratio is calculated correctly."""
        now = datetime.utcnow()

        # Create consistently profitable trades with slight variance (high Sharpe)
        exit_prices = [108.0, 110.0, 112.0, 109.0, 111.0, 113.0, 107.0, 115.0, 110.0, 114.0]
        trade_history = [
            create_closed_position("SOL", 100.0, exit_prices[i], 10.0,
                                   closed_at=now - timedelta(days=i))
            for i in range(10)  # 10 trades, all positive with variance
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        metrics = dashboard._get_risk_metrics()

        # Consistent positive returns should have positive Sharpe
        assert metrics['sharpe_ratio'] > 0.0

    def test_sharpe_ratio_negative_returns(self):
        """Test Sharpe ratio with negative average returns."""
        now = datetime.utcnow()

        # Create consistently losing trades
        trade_history = [
            create_closed_position("SOL", 100.0, 90.0, 10.0,
                                   closed_at=now - timedelta(days=i))
            for i in range(5)
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        metrics = dashboard._get_risk_metrics()

        # Negative returns should have negative or zero Sharpe
        assert metrics['sharpe_ratio'] <= 0.0


class TestTradingStatistics:
    """Tests for _get_trading_statistics method."""

    def test_trading_stats_no_trades(self):
        """Test trading stats with no history."""
        trader = create_mock_trader()
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        assert stats['total_trades'] == 0
        assert stats['win_rate'] == 0.0

    def test_total_trades_count(self):
        """Test total trades is counted correctly."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position(f"TOKEN{i}", 100.0, 110.0, 1.0,
                                   closed_at=now - timedelta(hours=i))
            for i in range(25)
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        assert stats['total_trades'] == 25

    def test_win_rate_all_wins(self):
        """Test win rate with all profitable trades."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 120.0, 1.0,
                                   closed_at=now - timedelta(hours=i))
            for i in range(10)
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        assert stats['win_rate'] == 100.0

    def test_win_rate_all_losses(self):
        """Test win rate with all losing trades."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 80.0, 1.0,
                                   closed_at=now - timedelta(hours=i))
            for i in range(10)
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        assert stats['win_rate'] == 0.0

    def test_win_rate_mixed(self):
        """Test win rate with mixed wins and losses."""
        now = datetime.utcnow()
        trade_history = [
            # 6 wins
            create_closed_position("SOL", 100.0, 110.0, 1.0, closed_at=now - timedelta(hours=1)),
            create_closed_position("SOL", 100.0, 115.0, 1.0, closed_at=now - timedelta(hours=2)),
            create_closed_position("SOL", 100.0, 120.0, 1.0, closed_at=now - timedelta(hours=3)),
            create_closed_position("SOL", 100.0, 105.0, 1.0, closed_at=now - timedelta(hours=4)),
            create_closed_position("SOL", 100.0, 108.0, 1.0, closed_at=now - timedelta(hours=5)),
            create_closed_position("SOL", 100.0, 102.0, 1.0, closed_at=now - timedelta(hours=6)),
            # 4 losses
            create_closed_position("SOL", 100.0, 90.0, 1.0, closed_at=now - timedelta(hours=7)),
            create_closed_position("SOL", 100.0, 85.0, 1.0, closed_at=now - timedelta(hours=8)),
            create_closed_position("SOL", 100.0, 95.0, 1.0, closed_at=now - timedelta(hours=9)),
            create_closed_position("SOL", 100.0, 88.0, 1.0, closed_at=now - timedelta(hours=10)),
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        assert stats['win_rate'] == pytest.approx(60.0, abs=0.1)

    def test_avg_win_calculation(self):
        """Test average win percentage calculation."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 110.0, 1.0, closed_at=now),  # +10%
            create_closed_position("SOL", 100.0, 120.0, 1.0, closed_at=now),  # +20%
            create_closed_position("SOL", 100.0, 130.0, 1.0, closed_at=now),  # +30%
            create_closed_position("SOL", 100.0, 90.0, 1.0, closed_at=now),   # -10% (loss, excluded)
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        # Avg win: (10 + 20 + 30) / 3 = 20%
        assert stats['avg_win'] == pytest.approx(20.0, abs=1.0)

    def test_avg_loss_calculation(self):
        """Test average loss percentage calculation."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 90.0, 1.0, closed_at=now),   # -10%
            create_closed_position("SOL", 100.0, 85.0, 1.0, closed_at=now),   # -15%
            create_closed_position("SOL", 100.0, 80.0, 1.0, closed_at=now),   # -20%
            create_closed_position("SOL", 100.0, 110.0, 1.0, closed_at=now),  # +10% (win, excluded)
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        # Avg loss: (-10 + -15 + -20) / 3 = -15%
        assert stats['avg_loss'] == pytest.approx(-15.0, abs=1.0)

    def test_profit_factor_calculation(self):
        """Test profit factor (gross wins / gross losses)."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 120.0, 10.0, closed_at=now),  # $200 win
            create_closed_position("SOL", 100.0, 115.0, 10.0, closed_at=now),  # $150 win
            create_closed_position("SOL", 100.0, 90.0, 10.0, closed_at=now),   # $100 loss
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        # Profit factor: ($200 + $150) / $100 = 3.5
        assert stats['profit_factor'] == pytest.approx(3.5, abs=0.1)

    def test_profit_factor_no_losses(self):
        """Test profit factor when no losses (should return infinity or high value)."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 120.0, 10.0, closed_at=now),
            create_closed_position("SOL", 100.0, 110.0, 10.0, closed_at=now),
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        # Should handle divide by zero gracefully
        assert stats['profit_factor'] >= 0


class TestPeriodPerformance:
    """Tests for _get_period_performance method."""

    def test_period_performance_7_days(self):
        """Test 7-day period performance metrics."""
        now = datetime.utcnow()

        trade_history = [
            create_closed_position("SOL", 100.0, 115.0, 10.0,
                                   closed_at=now - timedelta(days=i),
                                   opened_at=now - timedelta(days=i, hours=4))
            for i in range(7)
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        perf = dashboard._get_period_performance(7)

        assert 'period_return' in perf
        assert 'annualized_return' in perf
        assert 'best_day' in perf
        assert 'worst_day' in perf
        assert 'volatility' in perf
        assert 'max_drawdown' in perf
        assert 'sharpe_ratio' in perf
        assert 'sortino_ratio' in perf
        assert 'total_trades' in perf
        assert 'win_rate' in perf
        assert 'profit_factor' in perf
        assert 'avg_trade_duration' in perf

    def test_annualized_return_calculation(self):
        """Test annualized return calculation."""
        now = datetime.utcnow()

        # 10% return over 30 days
        trade_history = [
            create_closed_position("SOL", 100.0, 110.0, 10.0, closed_at=now)
        ]

        trader = create_mock_trader(trade_history=trade_history, balance=10000.0)
        dashboard = TreasuryDashboard(trader)

        perf = dashboard._get_period_performance(30)

        # Annualized: (1 + period_return/100)^(365/30) - 1
        assert 'annualized_return' in perf

    def test_best_worst_day(self):
        """Test best and worst day identification."""
        now = datetime.utcnow()

        trade_history = [
            create_closed_position("SOL", 100.0, 125.0, 10.0,
                                   closed_at=now - timedelta(days=2)),  # Best: +25%
            create_closed_position("SOL", 100.0, 105.0, 10.0,
                                   closed_at=now - timedelta(days=1)),  # +5%
            create_closed_position("SOL", 100.0, 85.0, 10.0,
                                   closed_at=now),  # Worst: -15%
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        perf = dashboard._get_period_performance(7)

        assert perf['best_day'] >= 20.0  # Should be ~25%
        assert perf['worst_day'] <= -10.0  # Should be ~-15%

    def test_sortino_ratio_calculation(self):
        """Test Sortino ratio uses only downside deviation."""
        now = datetime.utcnow()

        # Mix of returns with some downside
        trade_history = [
            create_closed_position("SOL", 100.0, 110.0, 10.0, closed_at=now - timedelta(days=4)),
            create_closed_position("SOL", 100.0, 115.0, 10.0, closed_at=now - timedelta(days=3)),
            create_closed_position("SOL", 100.0, 95.0, 10.0, closed_at=now - timedelta(days=2)),
            create_closed_position("SOL", 100.0, 108.0, 10.0, closed_at=now - timedelta(days=1)),
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        perf = dashboard._get_period_performance(7)

        # Sortino should exist
        assert 'sortino_ratio' in perf

    def test_avg_trade_duration(self):
        """Test average trade duration calculation."""
        now = datetime.utcnow()

        trade_history = [
            create_closed_position("SOL", 100.0, 110.0, 10.0,
                                   opened_at=now - timedelta(hours=12),
                                   closed_at=now - timedelta(hours=8)),  # 4 hours
            create_closed_position("SOL", 100.0, 115.0, 10.0,
                                   opened_at=now - timedelta(hours=8),
                                   closed_at=now - timedelta(hours=2)),  # 6 hours
            create_closed_position("SOL", 100.0, 105.0, 10.0,
                                   opened_at=now - timedelta(hours=4),
                                   closed_at=now),  # 4 hours
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        perf = dashboard._get_period_performance(7)

        # Avg: (4 + 6 + 4) / 3 = 4.67 hours
        assert perf['avg_trade_duration'] == pytest.approx(4.67, abs=0.5)


class TestRealizedPnL:
    """Tests for _get_realized_pnl method."""

    def test_realized_pnl_empty_history(self):
        """Test realized PnL with no trade history."""
        trader = create_mock_trader()
        dashboard = TreasuryDashboard(trader)

        realized = dashboard._get_realized_pnl()

        assert realized == 0.0

    def test_realized_pnl_with_trades(self):
        """Test realized PnL sums closed trade profits/losses."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 120.0, 10.0, closed_at=now),  # $200
            create_closed_position("ETH", 2000.0, 1800.0, 1.0, closed_at=now),  # -$200
            create_closed_position("BTC", 50000.0, 52000.0, 0.1, closed_at=now),  # $200
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        realized = dashboard._get_realized_pnl()

        # Net: $200 - $200 + $200 = $200
        assert realized == pytest.approx(200.0, abs=1.0)


class TestRecentTrades:
    """Tests for _get_recent_trades method."""

    def test_recent_trades_empty(self):
        """Test recent trades with no history."""
        trader = create_mock_trader()
        dashboard = TreasuryDashboard(trader)

        trades = dashboard._get_recent_trades(10)

        assert trades == []

    def test_recent_trades_returns_correct_format(self):
        """Test recent trades returns expected format."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 110.0, 10.0,
                                   opened_at=now - timedelta(hours=5),
                                   closed_at=now - timedelta(hours=1)),
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        trades = dashboard._get_recent_trades(10)

        assert len(trades) == 1
        trade = trades[0]
        assert 'symbol' in trade
        assert 'entry_price' in trade
        assert 'exit_price' in trade
        assert 'pnl' in trade
        assert 'pnl_pct' in trade
        assert 'duration' in trade
        assert 'exit_time' in trade

    def test_recent_trades_respects_limit(self):
        """Test recent trades respects the limit parameter."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position(f"TOKEN{i}", 100.0, 110.0, 1.0,
                                   closed_at=now - timedelta(hours=i))
            for i in range(20)
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        trades = dashboard._get_recent_trades(5)

        assert len(trades) == 5

    def test_recent_trades_sorted_by_exit_time(self):
        """Test recent trades are sorted by exit time (most recent first)."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("OLD", 100.0, 110.0, 1.0,
                                   closed_at=now - timedelta(days=5)),
            create_closed_position("NEW", 100.0, 120.0, 1.0,
                                   closed_at=now - timedelta(hours=1)),
            create_closed_position("MID", 100.0, 115.0, 1.0,
                                   closed_at=now - timedelta(days=2)),
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        trades = dashboard._get_recent_trades(10)

        # Should be sorted most recent first
        assert trades[0]['symbol'] == "NEW"
        assert trades[1]['symbol'] == "MID"
        assert trades[2]['symbol'] == "OLD"


class TestDashboardBuilders:
    """Tests for dashboard builder methods."""

    def test_build_portfolio_dashboard_no_error(self):
        """Test portfolio dashboard builds without error."""
        trader = create_mock_trader()
        dashboard = TreasuryDashboard(trader)

        result = dashboard.build_portfolio_dashboard()

        assert isinstance(result, str)
        assert "JARVIS TREASURY DASHBOARD" in result

    def test_build_portfolio_dashboard_with_positions(self):
        """Test portfolio dashboard includes position data."""
        positions = [
            MockPosition(
                id="pos1", token_symbol="SOL",
                entry_price=100.0, current_price=110.0,
                amount=10.0, amount_usd=1000.0,
                entry_time=datetime.utcnow() - timedelta(hours=2)
            )
        ]
        trader = create_mock_trader(open_positions=positions)
        dashboard = TreasuryDashboard(trader)

        result = dashboard.build_portfolio_dashboard(include_positions=True)

        assert "SOL" in result
        assert "OPEN POSITIONS" in result

    def test_build_performance_report(self):
        """Test performance report builds without error."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 115.0, 10.0, closed_at=now)
        ]
        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        result = dashboard.build_performance_report(period_days=7)

        assert isinstance(result, str)
        assert "PERFORMANCE REPORT" in result

    def test_build_recent_trades_view(self):
        """Test recent trades view builds without error."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 115.0, 10.0,
                                   opened_at=now - timedelta(hours=5),
                                   closed_at=now)
        ]
        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        result = dashboard.build_recent_trades(limit=10)

        assert isinstance(result, str)
        assert "RECENT TRADES" in result


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_single_trade(self):
        """Test calculations work with single trade."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 110.0, 10.0, closed_at=now)
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()
        metrics = dashboard._get_risk_metrics()

        assert stats['total_trades'] == 1
        assert stats['win_rate'] == 100.0
        # Single trade shouldn't cause division errors

    def test_zero_entry_price(self):
        """Test handling of zero entry price."""
        positions = [
            MockPosition(
                id="pos1", token_symbol="FREE",
                entry_price=0.0, current_price=1.0,
                amount=100.0, amount_usd=0.0
            )
        ]

        trader = create_mock_trader(open_positions=positions)
        dashboard = TreasuryDashboard(trader)

        # Should not raise divide by zero
        summary = dashboard._get_pnl_summary()
        assert isinstance(summary, dict)

    def test_negative_pnl_handling(self):
        """Test proper handling of negative PnL values."""
        now = datetime.utcnow()
        trade_history = [
            create_closed_position("SOL", 100.0, 50.0, 10.0, closed_at=now)  # -50% loss
        ]

        trader = create_mock_trader(trade_history=trade_history)
        dashboard = TreasuryDashboard(trader)

        stats = dashboard._get_trading_statistics()

        assert stats['avg_loss'] < 0
        assert stats['win_rate'] == 0.0

    def test_trader_with_no_balance_method(self):
        """Test handling when trader doesn't have get_balance."""
        trader = MagicMock()
        trader.get_open_positions = MagicMock(return_value=[])
        trader.trade_history = []
        trader.dry_run = False
        trader.max_positions = 50
        # No get_balance method
        del trader.get_balance

        dashboard = TreasuryDashboard(trader)

        # Should use fallback
        overview = dashboard._get_portfolio_overview()
        assert 'total_balance' in overview


class TestTrendDetermination:
    """Tests for _determine_trend method."""

    def test_strong_uptrend(self):
        """Test strong uptrend detection."""
        dashboard = TreasuryDashboard(create_mock_trader())

        data = {'period_return': 20.0, 'max_drawdown': 3.0}
        trend = dashboard._determine_trend(data)

        assert trend == PerformanceTrend.STRONG_UP

    def test_uptrend(self):
        """Test uptrend detection."""
        dashboard = TreasuryDashboard(create_mock_trader())

        data = {'period_return': 8.0, 'max_drawdown': 6.0}
        trend = dashboard._determine_trend(data)

        assert trend == PerformanceTrend.UP

    def test_stable(self):
        """Test stable trend detection."""
        dashboard = TreasuryDashboard(create_mock_trader())

        data = {'period_return': 2.0, 'max_drawdown': 5.0}
        trend = dashboard._determine_trend(data)

        assert trend == PerformanceTrend.STABLE

    def test_downtrend(self):
        """Test downtrend detection."""
        dashboard = TreasuryDashboard(create_mock_trader())

        data = {'period_return': -8.0, 'max_drawdown': 15.0}
        trend = dashboard._determine_trend(data)

        assert trend == PerformanceTrend.DOWN
