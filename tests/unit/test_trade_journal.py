"""
Trade Journal Tests

Comprehensive tests for the trade journaling system including:
- Automatic trade logging
- Entry/exit reasoning capture
- Screenshot/chart attachment support
- Performance tagging
- Pattern recognition
- Strategy categorization
- Per-strategy performance analysis
- Export to CSV/JSON
"""

import pytest
import asyncio
import tempfile
import json
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from decimal import Decimal
import sqlite3


class TestTradeJournalEnums:
    """Test enum definitions for trade journal."""

    def test_strategy_enum_values(self):
        """Test Strategy enum has expected values."""
        from core.trading.trade_journal import Strategy

        assert Strategy.MOMENTUM.value == "momentum"
        assert Strategy.MEAN_REVERSION.value == "mean_reversion"
        assert Strategy.BREAKOUT.value == "breakout"
        assert Strategy.TREND_FOLLOWING.value == "trend_following"
        assert Strategy.SCALPING.value == "scalping"
        assert Strategy.SWING.value == "swing"
        assert Strategy.ARBITRAGE.value == "arbitrage"
        assert Strategy.SENTIMENT.value == "sentiment"
        assert Strategy.WHALE_FOLLOW.value == "whale_follow"
        assert Strategy.NEWS.value == "news"
        assert Strategy.MANUAL.value == "manual"

    def test_trade_outcome_enum_values(self):
        """Test TradeOutcome enum has expected values."""
        from core.trading.trade_journal import TradeOutcome

        assert TradeOutcome.WIN.value == "win"
        assert TradeOutcome.LOSS.value == "loss"
        assert TradeOutcome.BREAKEVEN.value == "breakeven"
        assert TradeOutcome.PENDING.value == "pending"

    def test_trade_direction_enum_values(self):
        """Test TradeDirection enum has expected values."""
        from core.trading.trade_journal import TradeDirection

        assert TradeDirection.LONG.value == "long"
        assert TradeDirection.SHORT.value == "short"

    def test_performance_tag_enum_values(self):
        """Test PerformanceTag enum has expected values."""
        from core.trading.trade_journal import PerformanceTag

        assert PerformanceTag.PERFECT_ENTRY.value == "perfect_entry"
        assert PerformanceTag.EARLY_EXIT.value == "early_exit"
        assert PerformanceTag.LATE_EXIT.value == "late_exit"
        assert PerformanceTag.FOMO.value == "fomo"
        assert PerformanceTag.REVENGE_TRADE.value == "revenge_trade"
        assert PerformanceTag.FOLLOWED_PLAN.value == "followed_plan"


class TestJournalEntryDataclass:
    """Test JournalEntry dataclass."""

    def test_create_journal_entry(self):
        """Test creating a basic journal entry."""
        from core.trading.trade_journal import JournalEntry, Strategy, TradeDirection

        entry = JournalEntry(
            trade_id="test_001",
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        assert entry.trade_id == "test_001"
        assert entry.symbol == "SOL"
        assert entry.direction == TradeDirection.LONG
        assert entry.entry_price == 100.0
        assert entry.position_size == 10.0
        assert entry.strategy == Strategy.MOMENTUM

    def test_journal_entry_defaults(self):
        """Test journal entry has correct defaults."""
        from core.trading.trade_journal import (
            JournalEntry, Strategy, TradeDirection, TradeOutcome
        )

        entry = JournalEntry(
            trade_id="test_002",
            symbol="BTC",
            direction=TradeDirection.LONG,
            entry_price=50000.0,
            position_size=0.1,
            strategy=Strategy.BREAKOUT
        )

        assert entry.outcome == TradeOutcome.PENDING
        assert entry.exit_price is None
        assert entry.pnl_amount == 0.0
        assert entry.pnl_percent == 0.0
        assert entry.entry_reasoning == ""
        assert entry.exit_reasoning == ""
        assert entry.screenshots == []
        assert entry.tags == []
        assert entry.notes == ""

    def test_journal_entry_with_screenshots(self):
        """Test journal entry with screenshot attachments."""
        from core.trading.trade_journal import JournalEntry, Strategy, TradeDirection

        entry = JournalEntry(
            trade_id="test_003",
            symbol="ETH",
            direction=TradeDirection.LONG,
            entry_price=2000.0,
            position_size=5.0,
            strategy=Strategy.TREND_FOLLOWING,
            screenshots=[
                "/path/to/entry_chart.png",
                "/path/to/analysis.png"
            ]
        )

        assert len(entry.screenshots) == 2
        assert "/path/to/entry_chart.png" in entry.screenshots

    def test_journal_entry_with_performance_tags(self):
        """Test journal entry with performance tags."""
        from core.trading.trade_journal import (
            JournalEntry, Strategy, TradeDirection, PerformanceTag
        )

        entry = JournalEntry(
            trade_id="test_004",
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM,
            performance_tags=[PerformanceTag.PERFECT_ENTRY, PerformanceTag.FOLLOWED_PLAN]
        )

        assert len(entry.performance_tags) == 2
        assert PerformanceTag.PERFECT_ENTRY in entry.performance_tags

    def test_journal_entry_to_dict(self):
        """Test converting journal entry to dictionary."""
        from core.trading.trade_journal import JournalEntry, Strategy, TradeDirection

        entry = JournalEntry(
            trade_id="test_005",
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM,
            entry_reasoning="Strong momentum signal"
        )

        data = entry.to_dict()

        assert data["trade_id"] == "test_005"
        assert data["symbol"] == "SOL"
        assert data["direction"] == "long"
        assert data["entry_price"] == 100.0
        assert data["strategy"] == "momentum"
        assert data["entry_reasoning"] == "Strong momentum signal"


class TestTradeJournalDatabase:
    """Test TradeJournal database operations."""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Create a temporary database path."""
        return tmp_path / "test_journal.db"

    @pytest.fixture
    def journal(self, temp_db_path):
        """Create a TradeJournal instance with temp database."""
        from core.trading.trade_journal import TradeJournal
        return TradeJournal(db_path=temp_db_path)

    def test_journal_initialization(self, temp_db_path):
        """Test journal initializes database correctly."""
        from core.trading.trade_journal import TradeJournal

        journal = TradeJournal(db_path=temp_db_path)

        # Check database file was created
        assert temp_db_path.exists()

        # Check tables were created
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='journal_entries'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_log_trade_creates_entry(self, journal):
        """Test logging a trade creates an entry."""
        from core.trading.trade_journal import Strategy, TradeDirection

        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM,
            entry_reasoning="Strong upward momentum detected"
        )

        assert entry is not None
        assert entry.trade_id is not None
        assert entry.symbol == "SOL"
        assert entry.entry_reasoning == "Strong upward momentum detected"

    def test_log_trade_generates_unique_ids(self, journal):
        """Test that each logged trade gets a unique ID."""
        from core.trading.trade_journal import Strategy, TradeDirection

        entry1 = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        entry2 = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=105.0,
            position_size=5.0,
            strategy=Strategy.MOMENTUM
        )

        assert entry1.trade_id != entry2.trade_id

    def test_close_trade_calculates_pnl(self, journal):
        """Test closing a trade calculates P&L correctly."""
        from core.trading.trade_journal import Strategy, TradeDirection, TradeOutcome

        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        closed = journal.close_trade(
            trade_id=entry.trade_id,
            exit_price=120.0,
            exit_reasoning="Target reached"
        )

        assert closed.exit_price == 120.0
        assert closed.pnl_percent == pytest.approx(20.0, rel=0.01)
        assert closed.pnl_amount == pytest.approx(200.0, rel=0.01)
        assert closed.outcome == TradeOutcome.WIN

    def test_close_trade_short_calculates_pnl(self, journal):
        """Test closing a short trade calculates P&L correctly."""
        from core.trading.trade_journal import Strategy, TradeDirection, TradeOutcome

        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.SHORT,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MEAN_REVERSION
        )

        closed = journal.close_trade(
            trade_id=entry.trade_id,
            exit_price=80.0,
            exit_reasoning="Target reached"
        )

        assert closed.exit_price == 80.0
        assert closed.pnl_percent == pytest.approx(20.0, rel=0.01)
        assert closed.pnl_amount == pytest.approx(200.0, rel=0.01)
        assert closed.outcome == TradeOutcome.WIN

    def test_close_trade_loss(self, journal):
        """Test closing a losing trade."""
        from core.trading.trade_journal import Strategy, TradeDirection, TradeOutcome

        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        closed = journal.close_trade(
            trade_id=entry.trade_id,
            exit_price=90.0,
            exit_reasoning="Stop loss hit"
        )

        assert closed.pnl_percent == pytest.approx(-10.0, rel=0.01)
        assert closed.outcome == TradeOutcome.LOSS

    def test_close_trade_breakeven(self, journal):
        """Test closing a breakeven trade."""
        from core.trading.trade_journal import Strategy, TradeDirection, TradeOutcome

        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        closed = journal.close_trade(
            trade_id=entry.trade_id,
            exit_price=100.5,
            exit_reasoning="Closed at entry"
        )

        assert closed.outcome == TradeOutcome.BREAKEVEN

    def test_get_trade_by_id(self, journal):
        """Test retrieving a trade by ID."""
        from core.trading.trade_journal import Strategy, TradeDirection

        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        retrieved = journal.get_trade(entry.trade_id)

        assert retrieved is not None
        assert retrieved.trade_id == entry.trade_id
        assert retrieved.symbol == "SOL"

    def test_get_trade_not_found(self, journal):
        """Test retrieving a non-existent trade."""
        retrieved = journal.get_trade("nonexistent_id")
        assert retrieved is None

    def test_add_screenshot(self, journal):
        """Test adding a screenshot to a trade."""
        from core.trading.trade_journal import Strategy, TradeDirection

        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        journal.add_screenshot(entry.trade_id, "/path/to/chart.png")
        journal.add_screenshot(entry.trade_id, "/path/to/analysis.png")

        updated = journal.get_trade(entry.trade_id)
        assert len(updated.screenshots) == 2
        assert "/path/to/chart.png" in updated.screenshots

    def test_add_note(self, journal):
        """Test adding a note to a trade."""
        from core.trading.trade_journal import Strategy, TradeDirection

        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        journal.add_note(entry.trade_id, "Market showing strong bullish signals")

        updated = journal.get_trade(entry.trade_id)
        assert "Market showing strong bullish signals" in updated.notes

    def test_add_performance_tag(self, journal):
        """Test adding a performance tag to a trade."""
        from core.trading.trade_journal import Strategy, TradeDirection, PerformanceTag

        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        journal.add_performance_tag(entry.trade_id, PerformanceTag.PERFECT_ENTRY)
        journal.add_performance_tag(entry.trade_id, PerformanceTag.FOLLOWED_PLAN)

        updated = journal.get_trade(entry.trade_id)
        assert len(updated.performance_tags) == 2
        assert PerformanceTag.PERFECT_ENTRY in updated.performance_tags


class TestTradeJournalQueries:
    """Test TradeJournal query operations."""

    @pytest.fixture
    def journal_with_trades(self, tmp_path):
        """Create a journal with sample trades."""
        from core.trading.trade_journal import TradeJournal, Strategy, TradeDirection

        journal = TradeJournal(db_path=tmp_path / "test.db")

        # Log multiple trades with different strategies
        trades = [
            ("SOL", TradeDirection.LONG, 100.0, 10.0, Strategy.MOMENTUM, 120.0),
            ("SOL", TradeDirection.LONG, 110.0, 8.0, Strategy.MOMENTUM, 100.0),
            ("ETH", TradeDirection.LONG, 2000.0, 1.0, Strategy.BREAKOUT, 2200.0),
            ("BTC", TradeDirection.SHORT, 50000.0, 0.1, Strategy.MEAN_REVERSION, 48000.0),
            ("SOL", TradeDirection.LONG, 95.0, 15.0, Strategy.TREND_FOLLOWING, 105.0),
        ]

        for symbol, direction, entry, size, strategy, exit_price in trades:
            entry_obj = journal.log_trade(
                symbol=symbol,
                direction=direction,
                entry_price=entry,
                position_size=size,
                strategy=strategy
            )
            journal.close_trade(entry_obj.trade_id, exit_price)

        return journal

    def test_get_all_trades(self, journal_with_trades):
        """Test getting all trades."""
        trades = journal_with_trades.get_trades()
        assert len(trades) == 5

    def test_get_trades_by_symbol(self, journal_with_trades):
        """Test filtering trades by symbol."""
        trades = journal_with_trades.get_trades(symbol="SOL")
        assert len(trades) == 3

    def test_get_trades_by_strategy(self, journal_with_trades):
        """Test filtering trades by strategy."""
        from core.trading.trade_journal import Strategy

        trades = journal_with_trades.get_trades(strategy=Strategy.MOMENTUM)
        assert len(trades) == 2

    def test_get_trades_by_outcome(self, journal_with_trades):
        """Test filtering trades by outcome."""
        from core.trading.trade_journal import TradeOutcome

        trades = journal_with_trades.get_trades(outcome=TradeOutcome.WIN)
        assert len(trades) == 4  # 4 winning trades

    def test_get_trades_by_date_range(self, journal_with_trades):
        """Test filtering trades by date range."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        trades = journal_with_trades.get_trades(
            start_date=yesterday,
            end_date=tomorrow
        )
        assert len(trades) == 5

    def test_get_trades_limit(self, journal_with_trades):
        """Test limiting number of trades returned."""
        trades = journal_with_trades.get_trades(limit=3)
        assert len(trades) == 3

    def test_get_trades_offset(self, journal_with_trades):
        """Test offset for pagination."""
        all_trades = journal_with_trades.get_trades()
        offset_trades = journal_with_trades.get_trades(offset=2)

        assert len(offset_trades) == len(all_trades) - 2


class TestStrategyPerformance:
    """Test per-strategy performance analysis."""

    @pytest.fixture
    def journal_with_strategy_data(self, tmp_path):
        """Create journal with trades across multiple strategies."""
        from core.trading.trade_journal import TradeJournal, Strategy, TradeDirection

        journal = TradeJournal(db_path=tmp_path / "test.db")

        # Momentum trades: 3 wins, 1 loss
        for i, (entry, exit_price) in enumerate([
            (100, 120), (100, 115), (100, 110), (100, 90)
        ]):
            e = journal.log_trade(
                symbol="SOL",
                direction=TradeDirection.LONG,
                entry_price=entry,
                position_size=10.0,
                strategy=Strategy.MOMENTUM
            )
            journal.close_trade(e.trade_id, exit_price)

        # Breakout trades: 2 wins, 2 losses
        for entry, exit_price in [(100, 130), (100, 80), (100, 125), (100, 85)]:
            e = journal.log_trade(
                symbol="ETH",
                direction=TradeDirection.LONG,
                entry_price=entry,
                position_size=1.0,
                strategy=Strategy.BREAKOUT
            )
            journal.close_trade(e.trade_id, exit_price)

        return journal

    def test_get_strategy_performance(self, journal_with_strategy_data):
        """Test getting performance metrics for a specific strategy."""
        from core.trading.trade_journal import Strategy

        perf = journal_with_strategy_data.get_strategy_performance(Strategy.MOMENTUM)

        assert perf["total_trades"] == 4
        assert perf["win_count"] == 3
        assert perf["loss_count"] == 1
        assert perf["win_rate"] == pytest.approx(75.0, rel=0.01)
        assert perf["total_pnl"] > 0

    def test_get_all_strategies_performance(self, journal_with_strategy_data):
        """Test getting performance for all strategies."""
        perf = journal_with_strategy_data.get_all_strategies_performance()

        assert "momentum" in perf
        assert "breakout" in perf
        assert perf["momentum"]["win_rate"] > perf["breakout"]["win_rate"]

    def test_get_best_performing_strategy(self, journal_with_strategy_data):
        """Test identifying the best performing strategy."""
        best = journal_with_strategy_data.get_best_strategy(metric="win_rate")
        assert best == "momentum"

    def test_strategy_profit_factor(self, journal_with_strategy_data):
        """Test calculating profit factor per strategy."""
        from core.trading.trade_journal import Strategy

        perf = journal_with_strategy_data.get_strategy_performance(Strategy.MOMENTUM)

        # Profit factor = gross profit / gross loss
        assert perf["profit_factor"] > 1.0


class TestPatternRecognition:
    """Test pattern recognition in trade journal."""

    @pytest.fixture
    def journal_with_patterns(self, tmp_path):
        """Create journal with trades showing patterns."""
        from core.trading.trade_journal import (
            TradeJournal, Strategy, TradeDirection, PerformanceTag
        )

        journal = TradeJournal(db_path=tmp_path / "test.db")

        # Create trades with FOMO pattern
        for i in range(3):
            e = journal.log_trade(
                symbol="SOL",
                direction=TradeDirection.LONG,
                entry_price=100 + i * 10,  # Chasing price up
                position_size=10.0,
                strategy=Strategy.MANUAL
            )
            journal.add_performance_tag(e.trade_id, PerformanceTag.FOMO)
            journal.close_trade(e.trade_id, 95 + i * 10)  # All losses

        # Create trades with followed plan pattern
        for i in range(3):
            e = journal.log_trade(
                symbol="ETH",
                direction=TradeDirection.LONG,
                entry_price=2000,
                position_size=1.0,
                strategy=Strategy.BREAKOUT
            )
            journal.add_performance_tag(e.trade_id, PerformanceTag.FOLLOWED_PLAN)
            journal.close_trade(e.trade_id, 2200)  # All wins

        return journal

    def test_identify_losing_patterns(self, journal_with_patterns):
        """Test identifying patterns associated with losses."""
        patterns = journal_with_patterns.identify_losing_patterns()

        assert "fomo" in patterns
        assert patterns["fomo"]["loss_rate"] == 100.0
        assert patterns["fomo"]["avg_loss"] < 0

    def test_identify_winning_patterns(self, journal_with_patterns):
        """Test identifying patterns associated with wins."""
        patterns = journal_with_patterns.identify_winning_patterns()

        assert "followed_plan" in patterns
        assert patterns["followed_plan"]["win_rate"] == 100.0

    def test_get_pattern_analysis(self, journal_with_patterns):
        """Test comprehensive pattern analysis."""
        analysis = journal_with_patterns.get_pattern_analysis()

        assert "winning_patterns" in analysis
        assert "losing_patterns" in analysis
        assert "recommendations" in analysis


class TestExportFunctionality:
    """Test CSV and JSON export functionality."""

    @pytest.fixture
    def journal_with_export_data(self, tmp_path):
        """Create journal with data for export."""
        from core.trading.trade_journal import TradeJournal, Strategy, TradeDirection

        journal = TradeJournal(db_path=tmp_path / "test.db")

        # Create some trades
        for i in range(5):
            e = journal.log_trade(
                symbol="SOL",
                direction=TradeDirection.LONG,
                entry_price=100.0 + i,
                position_size=10.0,
                strategy=Strategy.MOMENTUM,
                entry_reasoning=f"Momentum signal {i}"
            )
            journal.close_trade(
                e.trade_id,
                exit_price=110.0 + i,
                exit_reasoning="Target reached"
            )

        return journal

    def test_export_to_json(self, journal_with_export_data, tmp_path):
        """Test exporting trades to JSON."""
        output_path = tmp_path / "export.json"

        journal_with_export_data.export_to_json(output_path)

        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert "trades" in data
        assert len(data["trades"]) == 5
        assert "metadata" in data
        assert data["trades"][0]["symbol"] == "SOL"

    def test_export_to_csv(self, journal_with_export_data, tmp_path):
        """Test exporting trades to CSV."""
        output_path = tmp_path / "export.csv"

        journal_with_export_data.export_to_csv(output_path)

        assert output_path.exists()

        with open(output_path, newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 5
        assert "symbol" in rows[0]
        assert "entry_price" in rows[0]
        assert "pnl_percent" in rows[0]

    def test_export_filtered_trades(self, journal_with_export_data, tmp_path):
        """Test exporting filtered trades."""
        from core.trading.trade_journal import TradeOutcome

        output_path = tmp_path / "wins.json"

        journal_with_export_data.export_to_json(
            output_path,
            outcome=TradeOutcome.WIN
        )

        with open(output_path) as f:
            data = json.load(f)

        assert len(data["trades"]) == 5  # All are wins

    def test_export_includes_analysis(self, journal_with_export_data, tmp_path):
        """Test export includes performance analysis."""
        output_path = tmp_path / "export.json"

        journal_with_export_data.export_to_json(output_path, include_analysis=True)

        with open(output_path) as f:
            data = json.load(f)

        assert "analysis" in data
        assert "total_trades" in data["analysis"]
        assert "win_rate" in data["analysis"]


class TestAutoCapture:
    """Test automatic trade capture functionality."""

    @pytest.fixture
    def journal(self, tmp_path):
        """Create a TradeJournal instance."""
        from core.trading.trade_journal import TradeJournal
        return TradeJournal(db_path=tmp_path / "test.db")

    def test_auto_capture_from_execution(self, journal):
        """Test auto-capturing trade from execution result."""
        from core.trading.trade_journal import Strategy, TradeDirection

        execution_result = {
            "tx_hash": "abc123",
            "token_symbol": "SOL",
            "side": "buy",
            "executed_price": 100.0,
            "executed_amount": 10.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        entry = journal.auto_capture(
            execution_result,
            strategy=Strategy.MOMENTUM,
            entry_reasoning="Auto-captured from execution"
        )

        assert entry is not None
        assert entry.symbol == "SOL"
        assert entry.direction == TradeDirection.LONG
        assert entry.entry_price == 100.0
        assert entry.metadata.get("tx_hash") == "abc123"

    def test_auto_capture_short_position(self, journal):
        """Test auto-capturing a short position."""
        from core.trading.trade_journal import Strategy, TradeDirection

        execution_result = {
            "tx_hash": "def456",
            "token_symbol": "ETH",
            "side": "sell",
            "executed_price": 2000.0,
            "executed_amount": 1.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        entry = journal.auto_capture(
            execution_result,
            strategy=Strategy.MEAN_REVERSION
        )

        assert entry.direction == TradeDirection.SHORT

    def test_auto_close_from_execution(self, journal):
        """Test auto-closing trade from execution result."""
        from core.trading.trade_journal import Strategy, TradeDirection

        # First create entry
        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )

        # Auto-close from execution
        execution_result = {
            "tx_hash": "ghi789",
            "token_symbol": "SOL",
            "side": "sell",
            "executed_price": 120.0,
            "executed_amount": 10.0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        closed = journal.auto_close(
            trade_id=entry.trade_id,
            execution_result=execution_result,
            exit_reasoning="Take profit hit"
        )

        assert closed.exit_price == 120.0
        assert closed.pnl_percent == pytest.approx(20.0, rel=0.01)


class TestPerformanceMetrics:
    """Test overall performance metrics calculation."""

    @pytest.fixture
    def journal_with_metrics_data(self, tmp_path):
        """Create journal with comprehensive trade data."""
        from core.trading.trade_journal import TradeJournal, Strategy, TradeDirection

        journal = TradeJournal(db_path=tmp_path / "test.db")

        # Create varied trade data
        trade_data = [
            (100, 120, Strategy.MOMENTUM),      # +20%
            (100, 90, Strategy.MOMENTUM),       # -10%
            (100, 115, Strategy.BREAKOUT),      # +15%
            (100, 130, Strategy.BREAKOUT),      # +30%
            (100, 85, Strategy.TREND_FOLLOWING),# -15%
            (100, 110, Strategy.TREND_FOLLOWING),# +10%
            (100, 105, Strategy.SCALPING),      # +5%
            (100, 103, Strategy.SCALPING),      # +3%
        ]

        for entry_price, exit_price, strategy in trade_data:
            e = journal.log_trade(
                symbol="SOL",
                direction=TradeDirection.LONG,
                entry_price=entry_price,
                position_size=10.0,
                strategy=strategy
            )
            journal.close_trade(e.trade_id, exit_price)

        return journal

    def test_get_overall_performance(self, journal_with_metrics_data):
        """Test getting overall performance metrics."""
        perf = journal_with_metrics_data.get_overall_performance()

        assert perf["total_trades"] == 8
        assert perf["win_count"] == 6
        assert perf["loss_count"] == 2
        assert perf["win_rate"] == pytest.approx(75.0, rel=0.01)

    def test_calculate_sharpe_ratio(self, journal_with_metrics_data):
        """Test Sharpe ratio calculation."""
        perf = journal_with_metrics_data.get_overall_performance()

        assert "sharpe_ratio" in perf
        # With mostly positive returns, Sharpe should be positive
        assert perf["sharpe_ratio"] > 0

    def test_calculate_max_drawdown(self, journal_with_metrics_data):
        """Test maximum drawdown calculation."""
        perf = journal_with_metrics_data.get_overall_performance()

        assert "max_drawdown" in perf
        assert perf["max_drawdown"] <= 0  # Drawdown is negative or zero

    def test_calculate_profit_factor(self, journal_with_metrics_data):
        """Test profit factor calculation."""
        perf = journal_with_metrics_data.get_overall_performance()

        assert "profit_factor" in perf
        assert perf["profit_factor"] > 1.0  # More wins than losses

    def test_get_performance_by_timeframe(self, journal_with_metrics_data):
        """Test getting performance by timeframe."""
        daily = journal_with_metrics_data.get_performance_by_timeframe("daily")
        weekly = journal_with_metrics_data.get_performance_by_timeframe("weekly")
        monthly = journal_with_metrics_data.get_performance_by_timeframe("monthly")

        assert len(daily) > 0
        assert len(weekly) > 0
        assert len(monthly) > 0


class TestJournalPersistence:
    """Test journal data persistence and recovery."""

    def test_data_persists_across_instances(self, tmp_path):
        """Test that data is properly persisted."""
        from core.trading.trade_journal import TradeJournal, Strategy, TradeDirection

        db_path = tmp_path / "persist_test.db"

        # Create journal and add trades
        journal1 = TradeJournal(db_path=db_path)
        entry = journal1.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM
        )
        trade_id = entry.trade_id

        # Create new instance
        journal2 = TradeJournal(db_path=db_path)
        retrieved = journal2.get_trade(trade_id)

        assert retrieved is not None
        assert retrieved.symbol == "SOL"
        assert retrieved.entry_price == 100.0

    def test_handles_corrupted_data_gracefully(self, tmp_path):
        """Test that corrupted data is handled gracefully."""
        from core.trading.trade_journal import TradeJournal

        db_path = tmp_path / "corrupt_test.db"

        # Create invalid data
        with open(db_path, 'w') as f:
            f.write("not a valid sqlite database")

        # Should handle gracefully and create new database
        try:
            journal = TradeJournal(db_path=db_path)
            # Should be able to use journal
            trades = journal.get_trades()
            assert isinstance(trades, list)
        except Exception as e:
            # Or raise a clear error
            assert "database" in str(e).lower() or "corrupt" in str(e).lower()


class TestConcurrency:
    """Test concurrent access handling."""

    def test_concurrent_writes(self, tmp_path):
        """Test handling concurrent writes."""
        import threading
        from core.trading.trade_journal import TradeJournal, Strategy, TradeDirection

        db_path = tmp_path / "concurrent_test.db"
        journal = TradeJournal(db_path=db_path)

        results = []
        errors = []

        def log_trade(i):
            try:
                entry = journal.log_trade(
                    symbol=f"TOKEN{i}",
                    direction=TradeDirection.LONG,
                    entry_price=100.0 + i,
                    position_size=10.0,
                    strategy=Strategy.MOMENTUM
                )
                results.append(entry.trade_id)
            except Exception as e:
                errors.append(str(e))

        # Run concurrent writes
        threads = [threading.Thread(target=log_trade, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All writes should succeed
        assert len(errors) == 0
        assert len(results) == 10
        assert len(set(results)) == 10  # All unique IDs


class TestReportGeneration:
    """Test report generation functionality."""

    @pytest.fixture
    def journal_for_reports(self, tmp_path):
        """Create journal with data for reports."""
        from core.trading.trade_journal import TradeJournal, Strategy, TradeDirection

        journal = TradeJournal(db_path=tmp_path / "report_test.db")

        # Add diverse trade data
        strategies = [
            Strategy.MOMENTUM,
            Strategy.BREAKOUT,
            Strategy.TREND_FOLLOWING,
            Strategy.MEAN_REVERSION
        ]

        for i, strategy in enumerate(strategies * 3):
            e = journal.log_trade(
                symbol="SOL" if i % 2 == 0 else "ETH",
                direction=TradeDirection.LONG,
                entry_price=100.0,
                position_size=10.0,
                strategy=strategy,
                entry_reasoning=f"Signal {i} detected"
            )
            exit_price = 110.0 if i % 3 != 0 else 95.0  # Mix of wins and losses
            journal.close_trade(e.trade_id, exit_price)

        return journal

    def test_generate_summary_report(self, journal_for_reports):
        """Test generating a summary report."""
        report = journal_for_reports.generate_report()

        assert "total_trades" in report
        assert "win_rate" in report
        assert "profit_factor" in report
        assert "strategy_breakdown" in report

    def test_generate_text_report(self, journal_for_reports):
        """Test generating a human-readable text report."""
        report = journal_for_reports.generate_text_report()

        assert isinstance(report, str)
        assert "Trading Journal Report" in report
        assert "Win Rate" in report
        assert "Total P&L" in report
