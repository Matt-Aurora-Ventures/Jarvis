"""
Dexter Paper Trading Module

Simulates trades without real capital to validate Dexter's decision quality.
Tracks hypothetical P&L and compares decisions vs actual price movement.

Features:
- Track entry/exit prices at multiple timeframes (5min, 1h, 4h)
- Calculate accuracy metrics
- Log all decisions for analysis
- Support for continuous 24+ hour paper trading sessions
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class TradeDirection(str, Enum):
    """Trade direction."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class PaperTrade:
    """Record of a paper trade."""
    trade_id: str
    symbol: str
    decision: str
    confidence: float
    entry_price: float
    entry_time: str
    grok_sentiment_score: float
    rationale: str = ""

    # Exit prices at different timeframes
    exit_price_5min: Optional[float] = None
    exit_price_1h: Optional[float] = None
    exit_price_4h: Optional[float] = None

    # P&L at different timeframes
    pnl_pct_5min: Optional[float] = None
    pnl_pct_1h: Optional[float] = None
    pnl_pct_4h: Optional[float] = None

    # Was the decision correct?
    accurate_5min: Optional[bool] = None
    accurate_1h: Optional[bool] = None
    accurate_4h: Optional[bool] = None

    # Metadata
    cost_usd: float = 0.0
    iterations: int = 0
    completed: bool = False


@dataclass
class PaperTradingStats:
    """Aggregate statistics for paper trading session."""
    total_trades: int = 0
    buy_count: int = 0
    sell_count: int = 0
    hold_count: int = 0

    # Accuracy at different timeframes
    accuracy_5min: float = 0.0
    accuracy_1h: float = 0.0
    accuracy_4h: float = 0.0

    # P&L stats
    total_pnl_pct_5min: float = 0.0
    total_pnl_pct_1h: float = 0.0
    total_pnl_pct_4h: float = 0.0
    avg_pnl_pct_5min: float = 0.0
    avg_pnl_pct_1h: float = 0.0
    avg_pnl_pct_4h: float = 0.0

    # Confidence stats
    avg_confidence: float = 0.0
    avg_grok_score: float = 0.0

    # Cost stats
    total_cost_usd: float = 0.0
    avg_cost_per_trade: float = 0.0

    # Time stats
    session_start: str = ""
    session_end: str = ""
    duration_hours: float = 0.0


class DexterPaperTrader:
    """
    Paper trading simulator for Dexter ReAct agent.

    Tracks hypothetical trades and calculates P&L vs actual price movement.
    Does not execute real trades.
    """

    def __init__(
        self,
        data_dir: str = "data/dexter/paper_trades",
        session_id: Optional[str] = None
    ):
        """
        Initialize paper trader.

        Args:
            data_dir: Directory to store paper trade logs
            session_id: Optional session ID (auto-generated if not provided)
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.session_id = session_id or f"paper_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.session_start = datetime.now(timezone.utc)

        # Trade storage
        self.trades: List[PaperTrade] = []
        self.pending_trades: Dict[str, PaperTrade] = {}  # trade_id -> trade

        # Price cache for exit price lookup
        self._price_cache: Dict[str, Dict[str, float]] = {}  # symbol -> {time: price}

        # File paths
        self.trades_file = self.data_dir / f"{self.session_id}_trades.jsonl"
        self.stats_file = self.data_dir / f"{self.session_id}_stats.json"

        logger.info(f"Paper trader initialized: session={self.session_id}")

    def record_decision(
        self,
        symbol: str,
        decision: str,
        confidence: float,
        entry_price: float,
        grok_sentiment_score: float,
        rationale: str = "",
        cost_usd: float = 0.0,
        iterations: int = 0
    ) -> PaperTrade:
        """
        Record a trading decision for paper trading.

        Args:
            symbol: Token symbol
            decision: TRADE_BUY, TRADE_SELL, or HOLD
            confidence: Decision confidence (0-100)
            entry_price: Current price at decision time
            grok_sentiment_score: Grok's sentiment score
            rationale: Decision rationale
            cost_usd: Cost of making this decision
            iterations: Number of ReAct iterations

        Returns:
            PaperTrade record
        """
        # Normalize decision
        direction = self._normalize_decision(decision)

        # Create trade record
        trade = PaperTrade(
            trade_id=f"{self.session_id}_{len(self.trades):04d}",
            symbol=symbol,
            decision=direction,
            confidence=confidence,
            entry_price=entry_price,
            entry_time=datetime.now(timezone.utc).isoformat(),
            grok_sentiment_score=grok_sentiment_score,
            rationale=rationale[:200] if rationale else "",
            cost_usd=cost_usd,
            iterations=iterations
        )

        # Add to lists
        self.trades.append(trade)
        if direction != TradeDirection.HOLD.value:
            self.pending_trades[trade.trade_id] = trade

        # Persist immediately
        self._append_trade(trade)

        logger.info(f"Paper trade recorded: {trade.trade_id} {direction} {symbol} @ ${entry_price:.4f}")

        return trade

    def update_exit_prices(
        self,
        trade_id: str,
        exit_price_5min: Optional[float] = None,
        exit_price_1h: Optional[float] = None,
        exit_price_4h: Optional[float] = None
    ) -> Optional[PaperTrade]:
        """
        Update exit prices for a paper trade.

        Args:
            trade_id: Trade ID to update
            exit_price_5min: Price 5 minutes after entry
            exit_price_1h: Price 1 hour after entry
            exit_price_4h: Price 4 hours after entry

        Returns:
            Updated PaperTrade or None if not found
        """
        trade = self._find_trade(trade_id)
        if not trade:
            logger.warning(f"Trade not found: {trade_id}")
            return None

        # Update exit prices
        if exit_price_5min is not None:
            trade.exit_price_5min = exit_price_5min
            trade.pnl_pct_5min = self._calculate_pnl(
                trade.entry_price, exit_price_5min, trade.decision
            )
            trade.accurate_5min = self._is_accurate(trade.pnl_pct_5min, trade.decision)

        if exit_price_1h is not None:
            trade.exit_price_1h = exit_price_1h
            trade.pnl_pct_1h = self._calculate_pnl(
                trade.entry_price, exit_price_1h, trade.decision
            )
            trade.accurate_1h = self._is_accurate(trade.pnl_pct_1h, trade.decision)

        if exit_price_4h is not None:
            trade.exit_price_4h = exit_price_4h
            trade.pnl_pct_4h = self._calculate_pnl(
                trade.entry_price, exit_price_4h, trade.decision
            )
            trade.accurate_4h = self._is_accurate(trade.pnl_pct_4h, trade.decision)

        # Mark completed if all timeframes have exit prices
        if all([trade.exit_price_5min, trade.exit_price_1h, trade.exit_price_4h]):
            trade.completed = True
            if trade_id in self.pending_trades:
                del self.pending_trades[trade_id]

        logger.info(f"Updated trade {trade_id}: 5m={trade.pnl_pct_5min}%, 1h={trade.pnl_pct_1h}%")

        return trade

    def get_stats(self) -> PaperTradingStats:
        """
        Calculate aggregate statistics for the paper trading session.

        Returns:
            PaperTradingStats with all metrics
        """
        stats = PaperTradingStats()
        stats.session_start = self.session_start.isoformat()
        stats.session_end = datetime.now(timezone.utc).isoformat()
        stats.duration_hours = (
            datetime.now(timezone.utc) - self.session_start
        ).total_seconds() / 3600

        if not self.trades:
            return stats

        stats.total_trades = len(self.trades)

        # Count by decision type
        for trade in self.trades:
            if trade.decision == TradeDirection.BUY.value:
                stats.buy_count += 1
            elif trade.decision == TradeDirection.SELL.value:
                stats.sell_count += 1
            else:
                stats.hold_count += 1

        # Calculate accuracy (only for non-HOLD trades with exit prices)
        actionable_trades = [
            t for t in self.trades
            if t.decision != TradeDirection.HOLD.value
        ]

        if actionable_trades:
            # 5-minute accuracy
            trades_5min = [t for t in actionable_trades if t.accurate_5min is not None]
            if trades_5min:
                stats.accuracy_5min = (
                    sum(1 for t in trades_5min if t.accurate_5min) / len(trades_5min)
                ) * 100

            # 1-hour accuracy
            trades_1h = [t for t in actionable_trades if t.accurate_1h is not None]
            if trades_1h:
                stats.accuracy_1h = (
                    sum(1 for t in trades_1h if t.accurate_1h) / len(trades_1h)
                ) * 100

            # 4-hour accuracy
            trades_4h = [t for t in actionable_trades if t.accurate_4h is not None]
            if trades_4h:
                stats.accuracy_4h = (
                    sum(1 for t in trades_4h if t.accurate_4h) / len(trades_4h)
                ) * 100

        # Calculate P&L stats
        pnl_5min = [t.pnl_pct_5min for t in self.trades if t.pnl_pct_5min is not None]
        pnl_1h = [t.pnl_pct_1h for t in self.trades if t.pnl_pct_1h is not None]
        pnl_4h = [t.pnl_pct_4h for t in self.trades if t.pnl_pct_4h is not None]

        if pnl_5min:
            stats.total_pnl_pct_5min = sum(pnl_5min)
            stats.avg_pnl_pct_5min = stats.total_pnl_pct_5min / len(pnl_5min)

        if pnl_1h:
            stats.total_pnl_pct_1h = sum(pnl_1h)
            stats.avg_pnl_pct_1h = stats.total_pnl_pct_1h / len(pnl_1h)

        if pnl_4h:
            stats.total_pnl_pct_4h = sum(pnl_4h)
            stats.avg_pnl_pct_4h = stats.total_pnl_pct_4h / len(pnl_4h)

        # Confidence and Grok stats
        confidences = [t.confidence for t in self.trades]
        grok_scores = [t.grok_sentiment_score for t in self.trades]
        stats.avg_confidence = sum(confidences) / len(confidences)
        stats.avg_grok_score = sum(grok_scores) / len(grok_scores)

        # Cost stats
        costs = [t.cost_usd for t in self.trades]
        stats.total_cost_usd = sum(costs)
        stats.avg_cost_per_trade = stats.total_cost_usd / len(costs)

        return stats

    def save_stats(self) -> str:
        """
        Save current statistics to JSON file.

        Returns:
            Path to stats file
        """
        stats = self.get_stats()
        with open(self.stats_file, 'w') as f:
            json.dump(asdict(stats), f, indent=2)
        logger.info(f"Stats saved to {self.stats_file}")
        return str(self.stats_file)

    def get_pending_trades(self) -> List[PaperTrade]:
        """
        Get trades that are awaiting exit price updates.

        Returns:
            List of pending trades
        """
        return list(self.pending_trades.values())

    def get_trades_for_symbol(self, symbol: str) -> List[PaperTrade]:
        """
        Get all trades for a specific symbol.

        Args:
            symbol: Token symbol

        Returns:
            List of trades for that symbol
        """
        return [t for t in self.trades if t.symbol.upper() == symbol.upper()]

    def generate_report(self) -> str:
        """
        Generate a text summary report.

        Returns:
            Formatted report string
        """
        stats = self.get_stats()

        report = f"""
================================================================================
                    DEXTER PAPER TRADING REPORT
================================================================================
Session ID: {self.session_id}
Duration: {stats.duration_hours:.1f} hours
Period: {stats.session_start[:19]} to {stats.session_end[:19]}

DECISION BREAKDOWN
------------------
Total Decisions: {stats.total_trades}
  - BUY:  {stats.buy_count} ({stats.buy_count/max(stats.total_trades,1)*100:.1f}%)
  - SELL: {stats.sell_count} ({stats.sell_count/max(stats.total_trades,1)*100:.1f}%)
  - HOLD: {stats.hold_count} ({stats.hold_count/max(stats.total_trades,1)*100:.1f}%)

ACCURACY VS PRICE MOVEMENT
--------------------------
  5-minute:  {stats.accuracy_5min:.1f}%
  1-hour:    {stats.accuracy_1h:.1f}%
  4-hour:    {stats.accuracy_4h:.1f}%

P&L ANALYSIS (Hypothetical)
---------------------------
  5-minute avg: {stats.avg_pnl_pct_5min:+.2f}%
  1-hour avg:   {stats.avg_pnl_pct_1h:+.2f}%
  4-hour avg:   {stats.avg_pnl_pct_4h:+.2f}%

CONFIDENCE METRICS
------------------
  Avg Confidence: {stats.avg_confidence:.1f}%
  Avg Grok Score: {stats.avg_grok_score:.1f}/100

COST ANALYSIS
-------------
  Total Cost:     ${stats.total_cost_usd:.3f}
  Avg Cost/Trade: ${stats.avg_cost_per_trade:.4f}

================================================================================
"""
        return report

    def _normalize_decision(self, decision: str) -> str:
        """Normalize decision string to enum value."""
        decision_upper = decision.upper()
        if "BUY" in decision_upper:
            return TradeDirection.BUY.value
        elif "SELL" in decision_upper:
            return TradeDirection.SELL.value
        else:
            return TradeDirection.HOLD.value

    def _calculate_pnl(
        self,
        entry_price: float,
        exit_price: float,
        decision: str
    ) -> float:
        """
        Calculate P&L percentage.

        For BUY: profit if price goes up
        For SELL: profit if price goes down
        For HOLD: 0%
        """
        if decision == TradeDirection.HOLD.value:
            return 0.0

        if entry_price == 0:
            return 0.0

        pnl = ((exit_price - entry_price) / entry_price) * 100

        # For SELL, invert the P&L
        if decision == TradeDirection.SELL.value:
            pnl = -pnl

        return round(pnl, 4)

    def _is_accurate(self, pnl_pct: float, decision: str) -> bool:
        """
        Determine if the decision was accurate.

        BUY is accurate if price went up (pnl > 0)
        SELL is accurate if price went down (pnl > 0 after inversion)
        """
        if decision == TradeDirection.HOLD.value:
            return True  # HOLD is always "accurate" in the sense it didn't lose
        return pnl_pct > 0

    def _find_trade(self, trade_id: str) -> Optional[PaperTrade]:
        """Find a trade by ID."""
        for trade in self.trades:
            if trade.trade_id == trade_id:
                return trade
        return None

    def _append_trade(self, trade: PaperTrade):
        """Append trade to JSONL file."""
        with open(self.trades_file, 'a') as f:
            f.write(json.dumps(asdict(trade)) + '\n')

    def load_session(self, session_id: str) -> bool:
        """
        Load an existing session from disk.

        Args:
            session_id: Session ID to load

        Returns:
            True if loaded successfully
        """
        trades_file = self.data_dir / f"{session_id}_trades.jsonl"
        if not trades_file.exists():
            logger.warning(f"Session not found: {session_id}")
            return False

        self.trades = []
        self.pending_trades = {}

        with open(trades_file) as f:
            for line in f:
                trade_dict = json.loads(line)
                trade = PaperTrade(**trade_dict)
                self.trades.append(trade)
                if not trade.completed and trade.decision != TradeDirection.HOLD.value:
                    self.pending_trades[trade.trade_id] = trade

        self.session_id = session_id
        logger.info(f"Loaded session {session_id}: {len(self.trades)} trades")
        return True
