"""
Trade Journal System

A comprehensive trade journaling system for tracking, analyzing, and improving
trading performance. Features include:

- Automatic trade logging with entry/exit details
- Entry/exit reasoning capture
- Screenshot/chart attachment support
- Performance tagging for pattern recognition
- Strategy categorization
- Per-strategy performance analysis
- Export to CSV/JSON
- Pattern recognition for winning/losing behaviors
"""

import csv
import json
import logging
import sqlite3
import statistics
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class Strategy(str, Enum):
    """Trading strategies for categorization."""
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    TREND_FOLLOWING = "trend_following"
    SCALPING = "scalping"
    SWING = "swing"
    ARBITRAGE = "arbitrage"
    SENTIMENT = "sentiment"
    WHALE_FOLLOW = "whale_follow"
    NEWS = "news"
    MANUAL = "manual"
    DCA = "dca"
    GRID = "grid"
    OTHER = "other"


class TradeOutcome(str, Enum):
    """Trade outcome classifications."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    PENDING = "pending"


class TradeDirection(str, Enum):
    """Trade direction."""
    LONG = "long"
    SHORT = "short"


class PerformanceTag(str, Enum):
    """Performance tags for pattern recognition."""
    PERFECT_ENTRY = "perfect_entry"
    EARLY_EXIT = "early_exit"
    LATE_EXIT = "late_exit"
    FOMO = "fomo"
    REVENGE_TRADE = "revenge_trade"
    FOLLOWED_PLAN = "followed_plan"
    OVERSIZE = "oversize"
    UNDERSIZE = "undersize"
    NO_STOP_LOSS = "no_stop_loss"
    MOVED_STOP_LOSS = "moved_stop_loss"
    CHASED_PRICE = "chased_price"
    EMOTIONAL = "emotional"
    DISCIPLINED = "disciplined"
    GOOD_RR = "good_rr"
    BAD_RR = "bad_rr"


@dataclass
class JournalEntry:
    """A trade journal entry with comprehensive tracking."""

    # Core identifiers
    trade_id: str
    symbol: str
    direction: TradeDirection
    entry_price: float
    position_size: float
    strategy: Strategy

    # Entry/Exit details
    exit_price: Optional[float] = None
    entry_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    exit_time: Optional[datetime] = None

    # P&L calculations
    pnl_amount: float = 0.0
    pnl_percent: float = 0.0
    outcome: TradeOutcome = TradeOutcome.PENDING

    # Reasoning capture
    entry_reasoning: str = ""
    exit_reasoning: str = ""

    # Attachments and notes
    screenshots: List[str] = field(default_factory=list)
    notes: str = ""

    # Performance tracking
    performance_tags: List[PerformanceTag] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Risk management
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    risk_reward_planned: Optional[float] = None
    risk_reward_actual: Optional[float] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    db_id: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to dictionary for serialization."""
        return {
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "direction": self.direction.value,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "position_size": self.position_size,
            "strategy": self.strategy.value,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "pnl_amount": self.pnl_amount,
            "pnl_percent": self.pnl_percent,
            "outcome": self.outcome.value,
            "entry_reasoning": self.entry_reasoning,
            "exit_reasoning": self.exit_reasoning,
            "screenshots": self.screenshots,
            "notes": self.notes,
            "performance_tags": [t.value for t in self.performance_tags],
            "tags": self.tags,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_reward_planned": self.risk_reward_planned,
            "risk_reward_actual": self.risk_reward_actual,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JournalEntry":
        """Create entry from dictionary."""
        return cls(
            trade_id=data["trade_id"],
            symbol=data["symbol"],
            direction=TradeDirection(data["direction"]),
            entry_price=data["entry_price"],
            exit_price=data.get("exit_price"),
            position_size=data["position_size"],
            strategy=Strategy(data["strategy"]),
            entry_time=datetime.fromisoformat(data["entry_time"]) if data.get("entry_time") else datetime.now(timezone.utc),
            exit_time=datetime.fromisoformat(data["exit_time"]) if data.get("exit_time") else None,
            pnl_amount=data.get("pnl_amount", 0.0),
            pnl_percent=data.get("pnl_percent", 0.0),
            outcome=TradeOutcome(data.get("outcome", "pending")),
            entry_reasoning=data.get("entry_reasoning", ""),
            exit_reasoning=data.get("exit_reasoning", ""),
            screenshots=data.get("screenshots", []),
            notes=data.get("notes", ""),
            performance_tags=[PerformanceTag(t) for t in data.get("performance_tags", [])],
            tags=data.get("tags", []),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            risk_reward_planned=data.get("risk_reward_planned"),
            risk_reward_actual=data.get("risk_reward_actual"),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.now(timezone.utc),
        )


class TradeJournal:
    """
    Trade Journal for tracking and analyzing trading performance.

    Usage:
        journal = TradeJournal()

        # Log a new trade
        entry = journal.log_trade(
            symbol="SOL",
            direction=TradeDirection.LONG,
            entry_price=100.0,
            position_size=10.0,
            strategy=Strategy.MOMENTUM,
            entry_reasoning="Strong momentum signal"
        )

        # Close the trade
        journal.close_trade(
            trade_id=entry.trade_id,
            exit_price=120.0,
            exit_reasoning="Target reached"
        )

        # Get performance by strategy
        perf = journal.get_strategy_performance(Strategy.MOMENTUM)

        # Export to JSON
        journal.export_to_json("trades.json")
    """

    # Breakeven threshold (% from entry)
    BREAKEVEN_THRESHOLD = 1.0

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize the trade journal."""
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "data" / "trade_journal.db"

        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Main journal entries table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS journal_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        trade_id TEXT UNIQUE NOT NULL,
                        symbol TEXT NOT NULL,
                        direction TEXT NOT NULL,
                        entry_price REAL NOT NULL,
                        exit_price REAL,
                        position_size REAL NOT NULL,
                        strategy TEXT NOT NULL,
                        entry_time TEXT NOT NULL,
                        exit_time TEXT,
                        pnl_amount REAL DEFAULT 0,
                        pnl_percent REAL DEFAULT 0,
                        outcome TEXT DEFAULT 'pending',
                        entry_reasoning TEXT DEFAULT '',
                        exit_reasoning TEXT DEFAULT '',
                        screenshots_json TEXT DEFAULT '[]',
                        notes TEXT DEFAULT '',
                        performance_tags_json TEXT DEFAULT '[]',
                        tags_json TEXT DEFAULT '[]',
                        stop_loss REAL,
                        take_profit REAL,
                        risk_reward_planned REAL,
                        risk_reward_actual REAL,
                        metadata_json TEXT DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)

                # Indexes for common queries
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_symbol ON journal_entries(symbol)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_strategy ON journal_entries(strategy)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_outcome ON journal_entries(outcome)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_entry_time ON journal_entries(entry_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_trade_id ON journal_entries(trade_id)")

                conn.commit()

        except sqlite3.DatabaseError:
            # Handle corrupted database by recreating
            logger.warning(f"Database may be corrupted, recreating: {self.db_path}")
            if self.db_path.exists():
                self.db_path.unlink()
            self._init_db()

    @contextmanager
    def _get_connection(self):
        """Get database connection with proper locking."""
        with self._lock:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    def log_trade(
        self,
        symbol: str,
        direction: TradeDirection,
        entry_price: float,
        position_size: float,
        strategy: Strategy,
        entry_reasoning: str = "",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> JournalEntry:
        """
        Log a new trade entry.

        Args:
            symbol: Trading symbol (e.g., "SOL", "BTC")
            direction: Trade direction (LONG or SHORT)
            entry_price: Entry price
            position_size: Position size (quantity or value)
            strategy: Trading strategy used
            entry_reasoning: Reason for entering the trade
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price
            tags: Optional custom tags
            metadata: Optional additional metadata

        Returns:
            JournalEntry with trade details
        """
        trade_id = f"trade_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)

        # Calculate planned risk/reward if stop loss and take profit are set
        risk_reward_planned = None
        if stop_loss and take_profit and entry_price:
            risk = abs(entry_price - stop_loss)
            reward = abs(take_profit - entry_price)
            if risk > 0:
                risk_reward_planned = reward / risk

        entry = JournalEntry(
            trade_id=trade_id,
            symbol=symbol.upper(),
            direction=direction,
            entry_price=entry_price,
            position_size=position_size,
            strategy=strategy,
            entry_time=now,
            entry_reasoning=entry_reasoning,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward_planned=risk_reward_planned,
            tags=tags or [],
            metadata=metadata or {},
            created_at=now,
            updated_at=now
        )

        self._save_entry(entry)
        logger.info(f"Logged trade {trade_id}: {symbol} {direction.value} @ {entry_price}")

        return entry

    def _save_entry(self, entry: JournalEntry):
        """Save entry to database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO journal_entries (
                    trade_id, symbol, direction, entry_price, exit_price,
                    position_size, strategy, entry_time, exit_time,
                    pnl_amount, pnl_percent, outcome, entry_reasoning, exit_reasoning,
                    screenshots_json, notes, performance_tags_json, tags_json,
                    stop_loss, take_profit, risk_reward_planned, risk_reward_actual,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.trade_id,
                entry.symbol,
                entry.direction.value,
                entry.entry_price,
                entry.exit_price,
                entry.position_size,
                entry.strategy.value,
                entry.entry_time.isoformat() if entry.entry_time else None,
                entry.exit_time.isoformat() if entry.exit_time else None,
                entry.pnl_amount,
                entry.pnl_percent,
                entry.outcome.value,
                entry.entry_reasoning,
                entry.exit_reasoning,
                json.dumps(entry.screenshots),
                entry.notes,
                json.dumps([t.value for t in entry.performance_tags]),
                json.dumps(entry.tags),
                entry.stop_loss,
                entry.take_profit,
                entry.risk_reward_planned,
                entry.risk_reward_actual,
                json.dumps(entry.metadata),
                entry.created_at.isoformat() if entry.created_at else None,
                entry.updated_at.isoformat() if entry.updated_at else None
            ))

            conn.commit()
            entry.db_id = cursor.lastrowid

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_reasoning: str = "",
        exit_time: Optional[datetime] = None
    ) -> Optional[JournalEntry]:
        """
        Close a trade and calculate P&L.

        Args:
            trade_id: Trade ID to close
            exit_price: Exit price
            exit_reasoning: Reason for exiting
            exit_time: Optional exit time (defaults to now)

        Returns:
            Updated JournalEntry or None if not found
        """
        entry = self.get_trade(trade_id)
        if not entry:
            logger.warning(f"Trade not found: {trade_id}")
            return None

        now = exit_time or datetime.now(timezone.utc)

        # Calculate P&L
        if entry.direction == TradeDirection.LONG:
            pnl_percent = ((exit_price - entry.entry_price) / entry.entry_price) * 100
            pnl_amount = (exit_price - entry.entry_price) * entry.position_size
        else:  # SHORT
            pnl_percent = ((entry.entry_price - exit_price) / entry.entry_price) * 100
            pnl_amount = (entry.entry_price - exit_price) * entry.position_size

        # Determine outcome
        if pnl_percent > self.BREAKEVEN_THRESHOLD:
            outcome = TradeOutcome.WIN
        elif pnl_percent < -self.BREAKEVEN_THRESHOLD:
            outcome = TradeOutcome.LOSS
        else:
            outcome = TradeOutcome.BREAKEVEN

        # Calculate actual risk/reward
        risk_reward_actual = None
        if entry.stop_loss and entry.entry_price:
            risk = abs(entry.entry_price - entry.stop_loss)
            reward = abs(exit_price - entry.entry_price)
            if risk > 0:
                risk_reward_actual = reward / risk

        # Update entry
        entry.exit_price = exit_price
        entry.exit_time = now
        entry.pnl_amount = pnl_amount
        entry.pnl_percent = pnl_percent
        entry.outcome = outcome
        entry.exit_reasoning = exit_reasoning
        entry.risk_reward_actual = risk_reward_actual
        entry.updated_at = now

        self._save_entry(entry)
        logger.info(f"Closed trade {trade_id}: {outcome.value} ${pnl_amount:.2f} ({pnl_percent:.2f}%)")

        return entry

    def get_trade(self, trade_id: str) -> Optional[JournalEntry]:
        """Get a trade by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM journal_entries WHERE trade_id = ?", (trade_id,))
            row = cursor.fetchone()
            return self._row_to_entry(row) if row else None

    def _row_to_entry(self, row: sqlite3.Row) -> JournalEntry:
        """Convert database row to JournalEntry."""
        perf_tags = []
        tags_json = row["performance_tags_json"]
        if tags_json:
            perf_tags = [PerformanceTag(t) for t in json.loads(tags_json)]

        return JournalEntry(
            db_id=row["id"],
            trade_id=row["trade_id"],
            symbol=row["symbol"],
            direction=TradeDirection(row["direction"]),
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            position_size=row["position_size"],
            strategy=Strategy(row["strategy"]),
            entry_time=datetime.fromisoformat(row["entry_time"]) if row["entry_time"] else None,
            exit_time=datetime.fromisoformat(row["exit_time"]) if row["exit_time"] else None,
            pnl_amount=row["pnl_amount"] or 0,
            pnl_percent=row["pnl_percent"] or 0,
            outcome=TradeOutcome(row["outcome"]) if row["outcome"] else TradeOutcome.PENDING,
            entry_reasoning=row["entry_reasoning"] or "",
            exit_reasoning=row["exit_reasoning"] or "",
            screenshots=json.loads(row["screenshots_json"]) if row["screenshots_json"] else [],
            notes=row["notes"] or "",
            performance_tags=perf_tags,
            tags=json.loads(row["tags_json"]) if row["tags_json"] else [],
            stop_loss=row["stop_loss"],
            take_profit=row["take_profit"],
            risk_reward_planned=row["risk_reward_planned"],
            risk_reward_actual=row["risk_reward_actual"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )

    def add_screenshot(self, trade_id: str, screenshot_path: str):
        """Add a screenshot to a trade."""
        entry = self.get_trade(trade_id)
        if entry:
            entry.screenshots.append(screenshot_path)
            entry.updated_at = datetime.now(timezone.utc)
            self._save_entry(entry)

    def add_note(self, trade_id: str, note: str):
        """Add a note to a trade."""
        entry = self.get_trade(trade_id)
        if entry:
            if entry.notes:
                entry.notes += f"\n{note}"
            else:
                entry.notes = note
            entry.updated_at = datetime.now(timezone.utc)
            self._save_entry(entry)

    def add_performance_tag(self, trade_id: str, tag: PerformanceTag):
        """Add a performance tag to a trade."""
        entry = self.get_trade(trade_id)
        if entry and tag not in entry.performance_tags:
            entry.performance_tags.append(tag)
            entry.updated_at = datetime.now(timezone.utc)
            self._save_entry(entry)

    def get_trades(
        self,
        symbol: Optional[str] = None,
        strategy: Optional[Strategy] = None,
        outcome: Optional[TradeOutcome] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[JournalEntry]:
        """
        Get trades with optional filters.

        Args:
            symbol: Filter by symbol
            strategy: Filter by strategy
            outcome: Filter by outcome
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of matching JournalEntry objects
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM journal_entries WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())

            if strategy:
                query += " AND strategy = ?"
                params.append(strategy.value)

            if outcome:
                query += " AND outcome = ?"
                params.append(outcome.value)

            if start_date:
                query += " AND entry_time >= ?"
                params.append(start_date.isoformat())

            if end_date:
                query += " AND entry_time <= ?"
                params.append(end_date.isoformat())

            query += " ORDER BY entry_time DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_strategy_performance(self, strategy: Strategy) -> Dict[str, Any]:
        """
        Get performance metrics for a specific strategy.

        Args:
            strategy: Strategy to analyze

        Returns:
            Dictionary with performance metrics
        """
        trades = self.get_trades(strategy=strategy)
        closed = [t for t in trades if t.outcome != TradeOutcome.PENDING]

        if not closed:
            return {
                "strategy": strategy.value,
                "total_trades": 0,
                "win_count": 0,
                "loss_count": 0,
                "breakeven_count": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "avg_pnl": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
            }

        wins = [t for t in closed if t.outcome == TradeOutcome.WIN]
        losses = [t for t in closed if t.outcome == TradeOutcome.LOSS]
        breakevens = [t for t in closed if t.outcome == TradeOutcome.BREAKEVEN]

        total_pnl = sum(t.pnl_amount for t in closed)
        gross_profit = sum(t.pnl_amount for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl_amount for t in losses)) if losses else 0

        return {
            "strategy": strategy.value,
            "total_trades": len(closed),
            "win_count": len(wins),
            "loss_count": len(losses),
            "breakeven_count": len(breakevens),
            "win_rate": (len(wins) / len(closed) * 100) if closed else 0.0,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(closed) if closed else 0.0,
            "avg_win": gross_profit / len(wins) if wins else 0.0,
            "avg_loss": -gross_loss / len(losses) if losses else 0.0,
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            "largest_win": max((t.pnl_amount for t in wins), default=0.0),
            "largest_loss": min((t.pnl_amount for t in losses), default=0.0),
        }

    def get_all_strategies_performance(self) -> Dict[str, Dict[str, Any]]:
        """Get performance metrics for all strategies with trades."""
        result = {}

        # Get unique strategies from database
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT strategy FROM journal_entries WHERE outcome != 'pending'")
            strategies = [row[0] for row in cursor.fetchall()]

        for strategy_value in strategies:
            try:
                strategy = Strategy(strategy_value)
                result[strategy_value] = self.get_strategy_performance(strategy)
            except ValueError:
                continue

        return result

    def get_best_strategy(self, metric: str = "win_rate") -> Optional[str]:
        """Get the best performing strategy based on a metric."""
        all_perf = self.get_all_strategies_performance()

        if not all_perf:
            return None

        valid_metrics = ["win_rate", "total_pnl", "profit_factor", "avg_pnl"]
        if metric not in valid_metrics:
            metric = "win_rate"

        return max(all_perf.keys(), key=lambda s: all_perf[s].get(metric, 0))

    def identify_losing_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Identify patterns associated with losing trades."""
        trades = self.get_trades(outcome=TradeOutcome.LOSS)

        patterns = {}
        for trade in trades:
            for tag in trade.performance_tags:
                tag_value = tag.value
                if tag_value not in patterns:
                    patterns[tag_value] = {
                        "count": 0,
                        "total_loss": 0.0,
                        "trades": []
                    }
                patterns[tag_value]["count"] += 1
                patterns[tag_value]["total_loss"] += trade.pnl_amount
                patterns[tag_value]["trades"].append(trade.trade_id)

        # Calculate averages
        for tag, data in patterns.items():
            if data["count"] > 0:
                data["avg_loss"] = data["total_loss"] / data["count"]
                data["loss_rate"] = 100.0  # All are losses since we filtered

        return patterns

    def identify_winning_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Identify patterns associated with winning trades."""
        trades = self.get_trades(outcome=TradeOutcome.WIN)

        patterns = {}
        for trade in trades:
            for tag in trade.performance_tags:
                tag_value = tag.value
                if tag_value not in patterns:
                    patterns[tag_value] = {
                        "count": 0,
                        "total_profit": 0.0,
                        "trades": []
                    }
                patterns[tag_value]["count"] += 1
                patterns[tag_value]["total_profit"] += trade.pnl_amount
                patterns[tag_value]["trades"].append(trade.trade_id)

        # Calculate averages
        for tag, data in patterns.items():
            if data["count"] > 0:
                data["avg_profit"] = data["total_profit"] / data["count"]
                data["win_rate"] = 100.0  # All are wins since we filtered

        return patterns

    def get_pattern_analysis(self) -> Dict[str, Any]:
        """Get comprehensive pattern analysis."""
        winning = self.identify_winning_patterns()
        losing = self.identify_losing_patterns()

        recommendations = []

        # Generate recommendations based on patterns
        for tag, data in losing.items():
            if data["count"] >= 2:
                recommendations.append(
                    f"Avoid '{tag}' pattern - caused {data['count']} losses "
                    f"with avg loss of ${abs(data['avg_loss']):.2f}"
                )

        for tag, data in winning.items():
            if data["count"] >= 2:
                recommendations.append(
                    f"Seek '{tag}' pattern - produced {data['count']} wins "
                    f"with avg profit of ${data['avg_profit']:.2f}"
                )

        return {
            "winning_patterns": winning,
            "losing_patterns": losing,
            "recommendations": recommendations
        }

    def auto_capture(
        self,
        execution_result: Dict[str, Any],
        strategy: Strategy,
        entry_reasoning: str = ""
    ) -> JournalEntry:
        """
        Auto-capture a trade from an execution result.

        Args:
            execution_result: Dict with keys: tx_hash, token_symbol, side,
                             executed_price, executed_amount, timestamp
            strategy: Trading strategy used
            entry_reasoning: Optional reasoning

        Returns:
            New JournalEntry
        """
        side = execution_result.get("side", "buy").lower()
        direction = TradeDirection.LONG if side == "buy" else TradeDirection.SHORT

        entry = self.log_trade(
            symbol=execution_result.get("token_symbol", "UNKNOWN"),
            direction=direction,
            entry_price=float(execution_result.get("executed_price", 0)),
            position_size=float(execution_result.get("executed_amount", 0)),
            strategy=strategy,
            entry_reasoning=entry_reasoning or "Auto-captured from execution",
            metadata={
                "tx_hash": execution_result.get("tx_hash"),
                "execution_timestamp": execution_result.get("timestamp")
            }
        )

        return entry

    def auto_close(
        self,
        trade_id: str,
        execution_result: Dict[str, Any],
        exit_reasoning: str = ""
    ) -> Optional[JournalEntry]:
        """
        Auto-close a trade from an execution result.

        Args:
            trade_id: Trade ID to close
            execution_result: Execution result dict
            exit_reasoning: Optional reasoning

        Returns:
            Closed JournalEntry or None
        """
        return self.close_trade(
            trade_id=trade_id,
            exit_price=float(execution_result.get("executed_price", 0)),
            exit_reasoning=exit_reasoning or "Auto-closed from execution"
        )

    def get_overall_performance(self) -> Dict[str, Any]:
        """Get overall performance metrics across all trades."""
        trades = self.get_trades()
        closed = [t for t in trades if t.outcome != TradeOutcome.PENDING]

        if not closed:
            return {
                "total_trades": 0,
                "win_count": 0,
                "loss_count": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "profit_factor": 0.0,
            }

        wins = [t for t in closed if t.outcome == TradeOutcome.WIN]
        losses = [t for t in closed if t.outcome == TradeOutcome.LOSS]

        total_pnl = sum(t.pnl_amount for t in closed)
        gross_profit = sum(t.pnl_amount for t in wins) if wins else 0
        gross_loss = abs(sum(t.pnl_amount for t in losses)) if losses else 0

        # Calculate returns for Sharpe ratio
        returns = [t.pnl_percent for t in closed]
        avg_return = statistics.mean(returns) if returns else 0
        std_return = statistics.stdev(returns) if len(returns) > 1 else 1
        sharpe_ratio = avg_return / std_return if std_return > 0 else 0

        # Calculate max drawdown
        cumulative_pnl = []
        running_pnl = 0
        for t in sorted(closed, key=lambda x: x.entry_time):
            running_pnl += t.pnl_amount
            cumulative_pnl.append(running_pnl)

        max_drawdown = 0
        peak = 0
        for pnl in cumulative_pnl:
            if pnl > peak:
                peak = pnl
            drawdown = peak - pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return {
            "total_trades": len(closed),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": (len(wins) / len(closed) * 100) if closed else 0.0,
            "total_pnl": total_pnl,
            "avg_pnl": total_pnl / len(closed) if closed else 0.0,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown": -max_drawdown,  # Negative to indicate loss
            "profit_factor": gross_profit / gross_loss if gross_loss > 0 else float('inf'),
            "largest_win": max((t.pnl_amount for t in wins), default=0.0),
            "largest_loss": min((t.pnl_amount for t in losses), default=0.0),
            "avg_win": gross_profit / len(wins) if wins else 0.0,
            "avg_loss": -gross_loss / len(losses) if losses else 0.0,
        }

    def get_performance_by_timeframe(self, timeframe: str = "daily") -> List[Dict[str, Any]]:
        """
        Get performance aggregated by timeframe.

        Args:
            timeframe: "daily", "weekly", or "monthly"

        Returns:
            List of performance data by period
        """
        trades = self.get_trades()
        closed = [t for t in trades if t.outcome != TradeOutcome.PENDING]

        if not closed:
            return []

        # Group by period
        periods = {}
        for trade in closed:
            if not trade.entry_time:
                continue

            if timeframe == "daily":
                key = trade.entry_time.strftime("%Y-%m-%d")
            elif timeframe == "weekly":
                # ISO week
                key = trade.entry_time.strftime("%Y-W%W")
            else:  # monthly
                key = trade.entry_time.strftime("%Y-%m")

            if key not in periods:
                periods[key] = []
            periods[key].append(trade)

        # Calculate metrics per period
        result = []
        for period, trades in sorted(periods.items()):
            wins = [t for t in trades if t.outcome == TradeOutcome.WIN]
            total_pnl = sum(t.pnl_amount for t in trades)

            result.append({
                "period": period,
                "trade_count": len(trades),
                "win_count": len(wins),
                "win_rate": (len(wins) / len(trades) * 100) if trades else 0.0,
                "total_pnl": total_pnl,
            })

        return result

    def export_to_json(
        self,
        output_path: Union[str, Path],
        outcome: Optional[TradeOutcome] = None,
        include_analysis: bool = False
    ):
        """
        Export trades to JSON file.

        Args:
            output_path: Path to output file
            outcome: Optional filter by outcome
            include_analysis: Include performance analysis
        """
        trades = self.get_trades(outcome=outcome) if outcome else self.get_trades()

        data = {
            "metadata": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "total_count": len(trades),
                "filters": {
                    "outcome": outcome.value if outcome else None
                }
            },
            "trades": [t.to_dict() for t in trades]
        }

        if include_analysis:
            data["analysis"] = self.get_overall_performance()
            data["analysis"]["strategy_breakdown"] = self.get_all_strategies_performance()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(trades)} trades to {output_path}")

    def export_to_csv(
        self,
        output_path: Union[str, Path],
        outcome: Optional[TradeOutcome] = None
    ):
        """
        Export trades to CSV file.

        Args:
            output_path: Path to output file
            outcome: Optional filter by outcome
        """
        trades = self.get_trades(outcome=outcome) if outcome else self.get_trades()

        if not trades:
            logger.warning("No trades to export")
            return

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "trade_id", "symbol", "direction", "strategy", "outcome",
            "entry_price", "exit_price", "position_size",
            "pnl_amount", "pnl_percent",
            "entry_time", "exit_time",
            "entry_reasoning", "exit_reasoning",
            "stop_loss", "take_profit",
            "risk_reward_planned", "risk_reward_actual",
            "notes", "tags"
        ]

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for trade in trades:
                writer.writerow({
                    "trade_id": trade.trade_id,
                    "symbol": trade.symbol,
                    "direction": trade.direction.value,
                    "strategy": trade.strategy.value,
                    "outcome": trade.outcome.value,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "position_size": trade.position_size,
                    "pnl_amount": trade.pnl_amount,
                    "pnl_percent": trade.pnl_percent,
                    "entry_time": trade.entry_time.isoformat() if trade.entry_time else "",
                    "exit_time": trade.exit_time.isoformat() if trade.exit_time else "",
                    "entry_reasoning": trade.entry_reasoning,
                    "exit_reasoning": trade.exit_reasoning,
                    "stop_loss": trade.stop_loss,
                    "take_profit": trade.take_profit,
                    "risk_reward_planned": trade.risk_reward_planned,
                    "risk_reward_actual": trade.risk_reward_actual,
                    "notes": trade.notes,
                    "tags": ",".join(trade.tags)
                })

        logger.info(f"Exported {len(trades)} trades to {output_path}")

    def generate_report(self) -> Dict[str, Any]:
        """Generate a comprehensive trading report."""
        overall = self.get_overall_performance()
        by_strategy = self.get_all_strategies_performance()
        patterns = self.get_pattern_analysis()

        return {
            **overall,
            "strategy_breakdown": by_strategy,
            "patterns": patterns,
        }

    def generate_text_report(self, days: int = 30) -> str:
        """Generate a human-readable text report."""
        perf = self.get_overall_performance()
        by_strategy = self.get_all_strategies_performance()

        lines = [
            "=" * 60,
            "Trading Journal Report",
            "=" * 60,
            "",
            f"Total Trades: {perf.get('total_trades', 0)}",
            f"Win Rate: {perf.get('win_rate', 0):.1f}%",
            f"Total P&L: ${perf.get('total_pnl', 0):,.2f}",
            f"Profit Factor: {perf.get('profit_factor', 0):.2f}",
            f"Sharpe Ratio: {perf.get('sharpe_ratio', 0):.2f}",
            f"Max Drawdown: ${perf.get('max_drawdown', 0):,.2f}",
            "",
            "-" * 40,
            "Performance by Strategy",
            "-" * 40,
        ]

        for strategy, stats in by_strategy.items():
            lines.append(
                f"  {strategy}: {stats['total_trades']} trades, "
                f"{stats['win_rate']:.0f}% WR, "
                f"${stats['total_pnl']:,.2f} P&L"
            )

        lines.extend([
            "",
            "-" * 40,
            "Summary",
            "-" * 40,
            f"Best Day: ${perf.get('largest_win', 0):,.2f}",
            f"Worst Day: ${perf.get('largest_loss', 0):,.2f}",
            f"Average Win: ${perf.get('avg_win', 0):,.2f}",
            f"Average Loss: ${perf.get('avg_loss', 0):,.2f}",
        ])

        return "\n".join(lines)


# Singleton instance
_journal: Optional[TradeJournal] = None


def get_trade_journal(db_path: Optional[Path] = None) -> TradeJournal:
    """Get the singleton trade journal instance."""
    global _journal
    if _journal is None:
        _journal = TradeJournal(db_path=db_path)
    return _journal


# For backwards compatibility
def get_journal() -> TradeJournal:
    """Alias for get_trade_journal."""
    return get_trade_journal()
