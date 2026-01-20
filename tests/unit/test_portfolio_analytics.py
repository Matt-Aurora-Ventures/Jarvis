"""
Tests for Portfolio Analytics module.

Tests:
- Total portfolio value calculation
- P&L by token
- Win/loss ratio
- Average hold time
- Best/worst performers
- Performance metrics
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from core.trading.portfolio_analytics import (
    PortfolioAnalytics,
    TokenPerformance,
    PerformanceMetrics,
    PortfolioSnapshot,
    get_portfolio_analytics
)


@pytest.fixture
def temp_positions_file():
    """Create a temporary positions file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        positions = [
            {
                "id": "pos1",
                "token_symbol": "SOL",
                "token_mint": "So11111111111111111111111111111111111111112",
                "status": "OPEN",
                "amount": 10.0,
                "entry_price": 100.0,
                "current_price": 110.0,
                "pnl_usd": 100.0,
                "pnl_pct": 10.0,
                "opened_at": "2024-01-01T00:00:00+00:00",
                "closed_at": None
            },
            {
                "id": "pos2",
                "token_symbol": "BONK",
                "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                "status": "OPEN",
                "amount": 1000000.0,
                "entry_price": 0.00001,
                "current_price": 0.000012,
                "pnl_usd": 2.0,
                "pnl_pct": 20.0,
                "opened_at": "2024-01-02T00:00:00+00:00",
                "closed_at": None
            }
        ]
        json.dump(positions, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def temp_scorekeeper_file():
    """Create a temporary scorekeeper file with closed positions."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        data = {
            "trade_history": [
                {
                    "id": "closed1",
                    "token_symbol": "SOL",
                    "token_mint": "So11111111111111111111111111111111111111112",
                    "status": "CLOSED",
                    "amount": 5.0,
                    "entry_price": 90.0,
                    "exit_price": 105.0,
                    "pnl_usd": 75.0,
                    "pnl_pct": 16.67,
                    "opened_at": "2023-12-01T00:00:00+00:00",
                    "closed_at": "2023-12-10T00:00:00+00:00"
                },
                {
                    "id": "closed2",
                    "token_symbol": "BONK",
                    "token_mint": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
                    "status": "CLOSED",
                    "amount": 2000000.0,
                    "entry_price": 0.00001,
                    "exit_price": 0.000008,
                    "pnl_usd": -4.0,
                    "pnl_pct": -20.0,
                    "opened_at": "2023-12-05T00:00:00+00:00",
                    "closed_at": "2023-12-08T00:00:00+00:00"
                },
                {
                    "id": "closed3",
                    "token_symbol": "JUP",
                    "token_mint": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
                    "status": "CLOSED",
                    "amount": 100.0,
                    "entry_price": 1.5,
                    "exit_price": 2.0,
                    "pnl_usd": 50.0,
                    "pnl_pct": 33.33,
                    "opened_at": "2023-12-15T00:00:00+00:00",
                    "closed_at": "2023-12-20T00:00:00+00:00"
                }
            ]
        }
        json.dump(data, f)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


class TestPortfolioAnalytics:
    """Test suite for PortfolioAnalytics class."""

    def test_init_with_files(self, temp_positions_file, temp_scorekeeper_file):
        """Test initialization with data files."""
        analytics = PortfolioAnalytics(
            positions_file=temp_positions_file,
            scorekeeper_file=temp_scorekeeper_file
        )

        assert len(analytics.positions) == 2
        assert len(analytics.closed_positions) == 3

    def test_get_portfolio_value(self, temp_positions_file, temp_scorekeeper_file):
        """Test portfolio value calculation."""
        analytics = PortfolioAnalytics(
            positions_file=temp_positions_file,
            scorekeeper_file=temp_scorekeeper_file
        )

        total_value, total_invested, unrealized_pnl = analytics.get_portfolio_value()

        # SOL: 10 * 110 = 1100
        # BONK: 1000000 * 0.000012 = 12
        # Total value: 1112
        assert total_value == pytest.approx(1112.0, rel=0.01)

        # SOL invested: 10 * 100 = 1000
        # BONK invested: 1000000 * 0.00001 = 10
        # Total invested: 1010
        assert total_invested == pytest.approx(1010.0, rel=0.01)

        # Unrealized PnL: 1112 - 1010 = 102
        assert unrealized_pnl == pytest.approx(102.0, rel=0.01)

    def test_get_performance_metrics(self, temp_positions_file, temp_scorekeeper_file):
        """Test overall performance metrics calculation."""
        analytics = PortfolioAnalytics(
            positions_file=temp_positions_file,
            scorekeeper_file=temp_scorekeeper_file
        )

        metrics = analytics.get_performance_metrics()

        assert metrics.total_positions == 5  # 2 open + 3 closed
        assert metrics.open_positions == 2
        assert metrics.closed_positions == 3

        # 2 wins (closed1, closed3), 1 loss (closed2)
        assert metrics.total_wins == 2
        assert metrics.total_losses == 1
        assert metrics.win_rate == pytest.approx(66.67, rel=0.1)

        # Profit factor: (75 + 50) / 4 = 31.25
        assert metrics.profit_factor == pytest.approx(31.25, rel=0.1)

        # Realized PnL: 75 - 4 + 50 = 121
        assert metrics.total_realized_pnl_usd == pytest.approx(121.0, rel=0.1)

        # Unrealized PnL: 100 + 2 = 102
        assert metrics.total_unrealized_pnl_usd == pytest.approx(102.0, rel=0.1)

        # Total PnL: 121 + 102 = 223
        assert metrics.total_pnl_usd == pytest.approx(223.0, rel=0.1)

    def test_get_token_performance(self, temp_positions_file, temp_scorekeeper_file):
        """Test per-token performance breakdown."""
        analytics = PortfolioAnalytics(
            positions_file=temp_positions_file,
            scorekeeper_file=temp_scorekeeper_file
        )

        token_perf = analytics.get_token_performance()

        # Should have 3 tokens: SOL, BONK, JUP
        assert len(token_perf) == 3

        # Find SOL performance
        sol_perf = next((tp for tp in token_perf if tp.token_symbol == "SOL"), None)
        assert sol_perf is not None
        assert sol_perf.total_positions == 2  # 1 open + 1 closed
        assert sol_perf.open_positions == 1
        assert sol_perf.closed_positions == 1
        assert sol_perf.wins == 1
        assert sol_perf.losses == 0
        assert sol_perf.win_rate == 100.0

        # Find BONK performance
        bonk_perf = next((tp for tp in token_perf if tp.token_symbol == "BONK"), None)
        assert bonk_perf is not None
        assert bonk_perf.total_positions == 2
        assert bonk_perf.wins == 0
        assert bonk_perf.losses == 1
        assert bonk_perf.win_rate == 0.0

        # Find JUP performance
        jup_perf = next((tp for tp in token_perf if tp.token_symbol == "JUP"), None)
        assert jup_perf is not None
        assert jup_perf.total_positions == 1
        assert jup_perf.closed_positions == 1
        assert jup_perf.wins == 1

    def test_get_top_performers(self, temp_positions_file, temp_scorekeeper_file):
        """Test getting top and bottom performers."""
        analytics = PortfolioAnalytics(
            positions_file=temp_positions_file,
            scorekeeper_file=temp_scorekeeper_file
        )

        best, worst = analytics.get_top_performers(limit=3, metric="pnl_pct")

        # Best should have highest PnL %
        assert len(best) <= 3
        assert best[0]["token_symbol"] == "JUP"  # 33.33%

        # Worst should have lowest PnL %
        assert len(worst) <= 3
        assert worst[0]["token_symbol"] == "BONK"  # -20%

    def test_get_summary_stats(self, temp_positions_file, temp_scorekeeper_file):
        """Test comprehensive summary statistics."""
        analytics = PortfolioAnalytics(
            positions_file=temp_positions_file,
            scorekeeper_file=temp_scorekeeper_file
        )

        summary = analytics.get_summary_stats()

        assert "portfolio_value" in summary
        assert "performance" in summary
        assert "streaks" in summary
        assert "tokens" in summary
        assert "best_position" in summary
        assert "worst_position" in summary

        assert summary["portfolio_value"]["current_usd"] > 0
        assert summary["performance"]["win_rate"] > 0
        assert summary["tokens"]["total_unique_tokens"] == 3

    def test_empty_portfolio(self):
        """Test analytics with empty portfolio."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            temp_pos = Path(f.name)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"trade_history": []}, f)
            temp_score = Path(f.name)

        try:
            analytics = PortfolioAnalytics(
                positions_file=temp_pos,
                scorekeeper_file=temp_score
            )

            metrics = analytics.get_performance_metrics()
            assert metrics.total_positions == 0
            assert metrics.win_rate == 0.0

            total_value, invested, pnl = analytics.get_portfolio_value()
            assert total_value == 0.0
            assert invested == 0.0
            assert pnl == 0.0

            token_perf = analytics.get_token_performance()
            assert len(token_perf) == 0

        finally:
            temp_pos.unlink(missing_ok=True)
            temp_score.unlink(missing_ok=True)

    def test_streak_calculation(self, temp_scorekeeper_file):
        """Test win/loss streak calculation."""
        # Create positions file with only wins
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            temp_pos = Path(f.name)

        try:
            analytics = PortfolioAnalytics(
                positions_file=temp_pos,
                scorekeeper_file=temp_scorekeeper_file
            )

            metrics = analytics.get_performance_metrics()

            # Positions sorted by close time:
            # 1. closed2 (BONK) closed 2023-12-08 - LOSS
            # 2. closed1 (SOL) closed 2023-12-10 - WIN
            # 3. closed3 (JUP) closed 2023-12-20 - WIN
            # Current streak should be 2 wins
            assert metrics.current_streak == 2

            # Should track longest winning and losing streaks
            assert metrics.longest_winning_streak >= 0
            assert metrics.longest_losing_streak >= 0

        finally:
            temp_pos.unlink(missing_ok=True)

    def test_hold_time_calculation(self, temp_scorekeeper_file):
        """Test average hold time calculation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            temp_pos = Path(f.name)

        try:
            analytics = PortfolioAnalytics(
                positions_file=temp_pos,
                scorekeeper_file=temp_scorekeeper_file
            )

            metrics = analytics.get_performance_metrics()

            # Should calculate average hold time from closed positions
            assert metrics.avg_hold_time_hours > 0

            # Verify it's reasonable (positions held for days)
            assert metrics.avg_hold_time_hours >= 24  # At least 1 day

        finally:
            temp_pos.unlink(missing_ok=True)

    def test_reload_data(self, temp_positions_file, temp_scorekeeper_file):
        """Test reloading data from files."""
        analytics = PortfolioAnalytics(
            positions_file=temp_positions_file,
            scorekeeper_file=temp_scorekeeper_file
        )

        initial_count = len(analytics.positions)

        # Modify the file
        with open(temp_positions_file, 'w') as f:
            json.dump([], f)

        # Reload should pick up changes
        analytics.reload()
        assert len(analytics.positions) == 0
        assert len(analytics.positions) != initial_count

    def test_get_portfolio_analytics_singleton(self):
        """Test singleton accessor."""
        analytics1 = get_portfolio_analytics()
        analytics2 = get_portfolio_analytics()

        # Should return same instance
        assert analytics1 is analytics2


class TestTokenPerformance:
    """Test TokenPerformance dataclass."""

    def test_token_performance_creation(self):
        """Test creating TokenPerformance instances."""
        tp = TokenPerformance(
            token_symbol="SOL",
            token_mint="So11111111111111111111111111111111111111112",
            total_positions=5,
            open_positions=2,
            closed_positions=3,
            wins=2,
            losses=1,
            win_rate=66.67,
            total_pnl_usd=150.0,
            avg_pnl_usd=50.0,
            avg_pnl_pct=15.0,
            best_pnl_pct=25.0,
            worst_pnl_pct=-10.0,
            avg_hold_time_hours=72.0,
            total_invested_usd=1000.0,
            current_value_usd=1150.0,
            unrealized_pnl_usd=150.0
        )

        assert tp.token_symbol == "SOL"
        assert tp.win_rate == 66.67
        assert tp.total_pnl_usd == 150.0


class TestPerformanceMetrics:
    """Test PerformanceMetrics dataclass."""

    def test_performance_metrics_creation(self):
        """Test creating PerformanceMetrics instances."""
        metrics = PerformanceMetrics(
            total_positions=10,
            open_positions=5,
            closed_positions=5,
            total_wins=3,
            total_losses=2,
            win_rate=60.0,
            avg_win_pct=15.0,
            avg_loss_pct=-8.0,
            profit_factor=1.5,
            avg_hold_time_hours=48.0,
            total_realized_pnl_usd=100.0,
            total_unrealized_pnl_usd=50.0,
            total_pnl_usd=150.0,
            best_position={"token_symbol": "SOL", "pnl_pct": 25.0},
            worst_position={"token_symbol": "BONK", "pnl_pct": -15.0},
            current_streak=2,
            longest_winning_streak=3,
            longest_losing_streak=2
        )

        assert metrics.win_rate == 60.0
        assert metrics.profit_factor == 1.5
        assert metrics.current_streak == 2


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_missing_files(self):
        """Test handling of missing data files."""
        analytics = PortfolioAnalytics(
            positions_file=Path("/nonexistent/positions.json"),
            scorekeeper_file=Path("/nonexistent/scorekeeper.json")
        )

        # Should handle gracefully
        assert len(analytics.positions) == 0
        assert len(analytics.closed_positions) == 0

    def test_malformed_json(self):
        """Test handling of malformed JSON files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json{")
            temp_path = Path(f.name)

        try:
            analytics = PortfolioAnalytics(positions_file=temp_path)
            # Should handle error gracefully
            assert len(analytics.positions) == 0
        finally:
            temp_path.unlink(missing_ok=True)

    def test_positions_with_missing_fields(self):
        """Test positions with missing or null fields."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            positions = [
                {
                    "id": "pos1",
                    "token_symbol": "SOL",
                    "status": "OPEN",
                    # Missing many fields
                }
            ]
            json.dump(positions, f)
            temp_path = Path(f.name)

        try:
            analytics = PortfolioAnalytics(positions_file=temp_path)

            # Should not crash
            value, invested, pnl = analytics.get_portfolio_value()
            assert value >= 0
            assert invested >= 0

        finally:
            temp_path.unlink(missing_ok=True)

    def test_zero_division_protection(self):
        """Test protection against division by zero."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            positions = [
                {
                    "id": "pos1",
                    "token_symbol": "SOL",
                    "status": "OPEN",
                    "amount": 0,  # Zero amount
                    "entry_price": 0,  # Zero price
                    "current_price": 100,
                    "pnl_usd": 0,
                    "pnl_pct": 0
                }
            ]
            json.dump(positions, f)
            temp_path = Path(f.name)

        try:
            analytics = PortfolioAnalytics(positions_file=temp_path)

            # Should not crash on division by zero
            summary = analytics.get_summary_stats()
            assert summary is not None

        finally:
            temp_path.unlink(missing_ok=True)
