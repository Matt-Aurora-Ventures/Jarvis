from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import asyncio

import pytest

# Import types directly from the types module (no heavy dependencies)
from bots.treasury.trading.types import Position, TradeDirection, TradeStatus, TradeReport

# Import analytics module - uses existing package system
from bots.treasury.trading.trading_analytics import TradingAnalytics

# Check if self-correcting is available (it won't be in tests, that's fine)
try:
    from bots.treasury.trading.trading_analytics import SELF_CORRECTING_AVAILABLE
except ImportError:
    SELF_CORRECTING_AVAILABLE = False


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


def test_generate_report_empty():
    """Test generate_report with no positions returns empty report."""
    report = TradingAnalytics.generate_report([], [])

    assert report.total_trades == 0
    assert report.winning_trades == 0
    assert report.losing_trades == 0
    assert report.win_rate == 0.0
    assert report.total_pnl_usd == 0.0


def test_generate_report_only_wins():
    """Test generate_report with only winning trades."""
    today = datetime.utcnow().isoformat()
    win1 = _pos("w1", TradeStatus.CLOSED, pnl_usd=10.0, closed_at=today)
    win2 = _pos("w2", TradeStatus.CLOSED, pnl_usd=20.0, closed_at=today)

    report = TradingAnalytics.generate_report([win1, win2], [])

    assert report.total_trades == 2
    assert report.winning_trades == 2
    assert report.losing_trades == 0
    assert report.win_rate == pytest.approx(100.0)
    assert report.average_win_usd == pytest.approx(15.0)
    assert report.average_loss_usd == pytest.approx(0.0)


def test_generate_report_only_losses():
    """Test generate_report with only losing trades."""
    today = datetime.utcnow().isoformat()
    loss1 = _pos("l1", TradeStatus.CLOSED, pnl_usd=-5.0, closed_at=today)
    loss2 = _pos("l2", TradeStatus.CLOSED, pnl_usd=-15.0, closed_at=today)

    report = TradingAnalytics.generate_report([loss1, loss2], [])

    assert report.total_trades == 2
    assert report.winning_trades == 0
    assert report.losing_trades == 2
    assert report.win_rate == pytest.approx(0.0)
    assert report.average_win_usd == pytest.approx(0.0)
    assert report.average_loss_usd == pytest.approx(-10.0)


def test_calculate_daily_pnl_empty():
    """Test daily PnL with empty positions."""
    pnl = TradingAnalytics.calculate_daily_pnl([], [])
    assert pnl == 0.0


def test_calculate_daily_pnl_with_z_suffix():
    """Test daily PnL parsing with ISO timestamp ending in Z."""
    today = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S") + "Z"
    closed_win = _pos("c1", TradeStatus.CLOSED, pnl_usd=25.0, closed_at=today)
    pnl = TradingAnalytics.calculate_daily_pnl([closed_win], [])
    assert pnl == pytest.approx(25.0)


# ==============================================================================
# Tests for self-correcting AI integration methods
# ==============================================================================

class TestTradingAnalyticsInstance:
    """Tests for instance methods that use self-correcting AI integration."""

    def test_init_with_all_components(self):
        """Test initialization with all self-correcting components."""
        mock_memory = MagicMock()
        mock_bus = MagicMock()
        mock_router = MagicMock()
        mock_adjuster = MagicMock()

        analytics = TradingAnalytics(
            memory=mock_memory,
            bus=mock_bus,
            router=mock_router,
            adjuster=mock_adjuster
        )

        assert analytics.memory == mock_memory
        assert analytics.bus == mock_bus
        assert analytics.router == mock_router
        assert analytics.adjuster == mock_adjuster

    def test_init_with_no_components(self):
        """Test initialization without any components."""
        analytics = TradingAnalytics()

        assert analytics.memory is None
        assert analytics.bus is None
        assert analytics.router is None
        assert analytics.adjuster is None


class TestRecordTradeLearning:
    """Tests for record_trade_learning method."""

    def test_record_trade_learning_no_memory(self):
        """Test that record_trade_learning returns early when no memory is set."""
        analytics = TradingAnalytics(memory=None)
        # Should not raise, just return early
        analytics.record_trade_learning(
            token="SOL",
            action="BUY",
            pnl=50.0,
            pnl_pct=0.15,
            sentiment_score=0.8
        )

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_record_trade_learning_success_pattern(self):
        """Test recording a successful trade as a learning pattern."""
        mock_memory = MagicMock()
        mock_memory.add_learning.return_value = "learning_123"

        analytics = TradingAnalytics(memory=mock_memory)

        # Patch LearningType since it's conditionally imported
        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'LearningType',
            MagicMock(SUCCESS_PATTERN="SUCCESS_PATTERN", FAILURE_PATTERN="FAILURE_PATTERN")
        ):
            analytics.record_trade_learning(
                token="SOL",
                action="BUY",
                pnl=150.0,
                pnl_pct=0.15,  # 15% profit - success pattern
                sentiment_score=0.9,
                context={"market": "bullish"}
            )

        # Verify memory.add_learning was called
        mock_memory.add_learning.assert_called_once()

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_record_trade_learning_failure_pattern(self):
        """Test recording a losing trade as a failure pattern."""
        mock_memory = MagicMock()
        mock_memory.add_learning.return_value = "learning_456"

        analytics = TradingAnalytics(memory=mock_memory)

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'LearningType',
            MagicMock(SUCCESS_PATTERN="SUCCESS_PATTERN", FAILURE_PATTERN="FAILURE_PATTERN")
        ):
            analytics.record_trade_learning(
                token="BONK",
                action="SELL",
                pnl=-25.0,
                pnl_pct=-0.10,  # 10% loss - failure pattern
            )

        mock_memory.add_learning.assert_called_once()

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_record_trade_learning_small_pnl_ignored(self):
        """Test that small P&L changes are not recorded."""
        mock_memory = MagicMock()
        analytics = TradingAnalytics(memory=mock_memory)

        # Small gain - should be ignored
        analytics.record_trade_learning(
            token="SOL",
            action="BUY",
            pnl=1.0,
            pnl_pct=0.01,  # 1% - too small
        )

        mock_memory.add_learning.assert_not_called()

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_record_trade_learning_with_bus(self):
        """Test that trade learning broadcasts to message bus."""
        mock_memory = MagicMock()
        mock_memory.add_learning.return_value = "learning_789"
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()

        analytics = TradingAnalytics(memory=mock_memory, bus=mock_bus)

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'LearningType',
            MagicMock(SUCCESS_PATTERN="SUCCESS_PATTERN")
        ), patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'MessageType',
            MagicMock(NEW_LEARNING="NEW_LEARNING")
        ), patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'MessagePriority',
            MagicMock(NORMAL="NORMAL")
        ):
            analytics.record_trade_learning(
                token="SOL",
                action="BUY",
                pnl=200.0,
                pnl_pct=0.20,  # 20% profit
            )

        mock_memory.add_learning.assert_called_once()

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_record_trade_learning_with_adjuster(self):
        """Test that trade learning records metrics for self-adjuster."""
        mock_memory = MagicMock()
        mock_memory.add_learning.return_value = "learning_abc"
        mock_adjuster = MagicMock()

        analytics = TradingAnalytics(memory=mock_memory, adjuster=mock_adjuster)

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'LearningType',
            MagicMock(SUCCESS_PATTERN="SUCCESS_PATTERN")
        ), patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'MetricType',
            MagicMock(SUCCESS_RATE="SUCCESS_RATE")
        ):
            analytics.record_trade_learning(
                token="SOL",
                action="BUY",
                pnl=100.0,
                pnl_pct=0.12,
            )

        mock_adjuster.record_metric.assert_called_once()

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_record_trade_learning_exception_handling(self):
        """Test that exceptions in record_trade_learning are handled gracefully."""
        mock_memory = MagicMock()
        mock_memory.add_learning.side_effect = Exception("Database error")

        analytics = TradingAnalytics(memory=mock_memory)

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'LearningType',
            MagicMock(SUCCESS_PATTERN="SUCCESS_PATTERN")
        ):
            # Should not raise
            analytics.record_trade_learning(
                token="SOL",
                action="BUY",
                pnl=100.0,
                pnl_pct=0.15,
            )


class TestQueryAIForTradeAnalysis:
    """Tests for query_ai_for_trade_analysis async method."""

    @pytest.mark.asyncio
    async def test_query_ai_no_router(self):
        """Test query returns empty when no router is set."""
        analytics = TradingAnalytics(router=None)

        result = await analytics.query_ai_for_trade_analysis(
            token="SOL",
            sentiment="bullish",
            score=0.8
        )

        assert result == ""

    @pytest.mark.asyncio
    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    async def test_query_ai_success(self):
        """Test successful AI query for trade analysis."""
        mock_router = AsyncMock()
        mock_response = MagicMock()
        mock_response.model_used = "gpt-4"
        mock_response.text = "This token shows strong potential based on sentiment analysis."
        mock_router.query.return_value = mock_response

        analytics = TradingAnalytics(router=mock_router)

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'TaskType',
            MagicMock(REASONING="REASONING")
        ):
            result = await analytics.query_ai_for_trade_analysis(
                token="SOL",
                sentiment="bullish",
                score=0.85
            )

        assert result == mock_response.text
        mock_router.query.assert_called_once()

    @pytest.mark.asyncio
    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    async def test_query_ai_with_past_learnings(self):
        """Test AI query includes past learnings context."""
        mock_router = AsyncMock()
        mock_response = MagicMock()
        mock_response.model_used = "claude"
        mock_response.text = "Based on past experience, proceed with caution."
        mock_router.query.return_value = mock_response

        analytics = TradingAnalytics(router=mock_router)

        past_learnings = [
            MagicMock(content="SOL had 20% gain last month"),
            MagicMock(content="Volume spike preceded rally"),
        ]

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'TaskType',
            MagicMock(REASONING="REASONING")
        ):
            result = await analytics.query_ai_for_trade_analysis(
                token="SOL",
                sentiment="neutral",
                score=0.5,
                past_learnings=past_learnings
            )

        assert result == mock_response.text

    @pytest.mark.asyncio
    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    async def test_query_ai_exception_handling(self):
        """Test that exceptions in AI query are handled gracefully."""
        mock_router = AsyncMock()
        mock_router.query.side_effect = Exception("API timeout")

        analytics = TradingAnalytics(router=mock_router)

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'TaskType',
            MagicMock(REASONING="REASONING")
        ):
            result = await analytics.query_ai_for_trade_analysis(
                token="SOL",
                sentiment="bullish",
                score=0.9
            )

        assert result == ""


class TestHandleBusMessage:
    """Tests for handle_bus_message method."""

    def test_handle_bus_message_no_memory(self):
        """Test that handle_bus_message returns early when no memory is set."""
        analytics = TradingAnalytics(memory=None)
        mock_message = MagicMock()
        # Should not raise
        analytics.handle_bus_message(mock_message)

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_handle_sentiment_changed_message(self):
        """Test handling of sentiment changed message."""
        mock_memory = MagicMock()
        mock_memory.search_learnings.return_value = []

        analytics = TradingAnalytics(memory=mock_memory)

        mock_message = MagicMock()
        mock_message.type = MagicMock()
        mock_message.data = {
            "token": "SOL",
            "sentiment": "bullish",
            "score": 0.85
        }

        # Create a mock MessageType enum
        mock_msg_type = MagicMock()
        mock_msg_type.SENTIMENT_CHANGED = mock_message.type
        mock_msg_type.PRICE_ALERT = MagicMock()
        mock_msg_type.NEW_LEARNING = MagicMock()

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'MessageType',
            mock_msg_type
        ):
            analytics.handle_bus_message(mock_message)

        mock_memory.search_learnings.assert_called_once()

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_handle_sentiment_changed_with_learnings(self):
        """Test sentiment changed message when learnings exist."""
        mock_memory = MagicMock()
        mock_memory.search_learnings.return_value = [
            MagicMock(content="Previous SOL trade profitable"),
            MagicMock(content="Watch for volume spikes"),
        ]

        analytics = TradingAnalytics(memory=mock_memory)

        mock_message = MagicMock()
        mock_message.type = MagicMock()
        mock_message.data = {
            "token": "SOL",
            "sentiment": "bullish",
            "score": 0.9
        }

        mock_msg_type = MagicMock()
        mock_msg_type.SENTIMENT_CHANGED = mock_message.type
        mock_msg_type.PRICE_ALERT = MagicMock()
        mock_msg_type.NEW_LEARNING = MagicMock()

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'MessageType',
            mock_msg_type
        ):
            analytics.handle_bus_message(mock_message)

        mock_memory.search_learnings.assert_called_once()

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_handle_price_alert_message(self):
        """Test handling of price alert message."""
        mock_memory = MagicMock()
        analytics = TradingAnalytics(memory=mock_memory)

        mock_message = MagicMock()
        mock_message.type = MagicMock()
        mock_message.data = {
            "token": "SOL",
            "alert_type": "price_spike"
        }

        mock_msg_type = MagicMock()
        mock_msg_type.SENTIMENT_CHANGED = MagicMock()
        mock_msg_type.PRICE_ALERT = mock_message.type
        mock_msg_type.NEW_LEARNING = MagicMock()

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'MessageType',
            mock_msg_type
        ):
            analytics.handle_bus_message(mock_message)

        # No exception should be raised

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_handle_new_learning_message(self):
        """Test handling of new learning message."""
        mock_memory = MagicMock()
        analytics = TradingAnalytics(memory=mock_memory)

        mock_message = MagicMock()
        mock_message.type = MagicMock()
        mock_message.data = {
            "learning_id": "learning_xyz"
        }

        mock_msg_type = MagicMock()
        mock_msg_type.SENTIMENT_CHANGED = MagicMock()
        mock_msg_type.PRICE_ALERT = MagicMock()
        mock_msg_type.NEW_LEARNING = mock_message.type

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'MessageType',
            mock_msg_type
        ):
            analytics.handle_bus_message(mock_message)

        # No exception should be raised

    @patch('bots.treasury.trading.trading_analytics.SELF_CORRECTING_AVAILABLE', True)
    def test_handle_bus_message_exception(self):
        """Test that exceptions in handle_bus_message are handled gracefully."""
        mock_memory = MagicMock()
        mock_memory.search_learnings.side_effect = Exception("Memory error")

        analytics = TradingAnalytics(memory=mock_memory)

        mock_message = MagicMock()
        mock_message.type = MagicMock()
        mock_message.data = {"token": "SOL", "sentiment": "bullish", "score": 0.5}

        mock_msg_type = MagicMock()
        mock_msg_type.SENTIMENT_CHANGED = mock_message.type
        mock_msg_type.PRICE_ALERT = MagicMock()
        mock_msg_type.NEW_LEARNING = MagicMock()

        with patch.object(
            sys.modules['bots.treasury.trading.trading_analytics'],
            'MessageType',
            mock_msg_type
        ):
            # Should not raise
            analytics.handle_bus_message(mock_message)
