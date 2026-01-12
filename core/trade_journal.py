"""
Trade Journal - Record trades with notes, analysis, and lessons learned.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import json
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TradeOutcome(Enum):
    """Trade outcome classifications."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    PENDING = "pending"


class TradeMistake(Enum):
    """Common trading mistakes for categorization."""
    FOMO = "fomo"
    EARLY_EXIT = "early_exit"
    LATE_EXIT = "late_exit"
    OVERSIZE = "oversize"
    NO_STOP_LOSS = "no_stop_loss"
    IGNORED_SIGNAL = "ignored_signal"
    REVENGE_TRADE = "revenge_trade"
    EMOTIONAL = "emotional"
    NONE = "none"


class TradeSetup(Enum):
    """Trade setup types."""
    BREAKOUT = "breakout"
    PULLBACK = "pullback"
    TREND_FOLLOW = "trend_follow"
    REVERSAL = "reversal"
    MOMENTUM = "momentum"
    NEWS = "news"
    WHALE_FOLLOW = "whale_follow"
    SENTIMENT = "sentiment"
    OTHER = "other"


@dataclass
class JournalEntry:
    """A trade journal entry."""
    id: Optional[int] = None
    trade_id: str = ""
    timestamp: str = ""

    # Trade details
    symbol: str = ""
    direction: str = ""  # LONG, SHORT
    entry_price: float = 0.0
    exit_price: float = 0.0
    position_size: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0

    # Outcome
    outcome: TradeOutcome = TradeOutcome.PENDING
    pnl_amount: float = 0.0
    pnl_percent: float = 0.0
    risk_reward_actual: float = 0.0

    # Analysis
    setup_type: TradeSetup = TradeSetup.OTHER
    thesis: str = ""  # Why entered the trade
    market_conditions: str = ""
    timeframe: str = ""  # 1m, 5m, 1h, etc

    # Reflection
    what_went_well: str = ""
    what_went_wrong: str = ""
    lessons_learned: str = ""
    mistakes: List[TradeMistake] = field(default_factory=list)
    rating: int = 0  # 1-5 stars

    # Screenshots/evidence
    entry_screenshot: str = ""
    exit_screenshot: str = ""

    # Emotions
    pre_trade_emotion: str = ""
    during_trade_emotion: str = ""
    post_trade_emotion: str = ""

    # Tags and metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class JournalDB:
    """SQLite storage for trade journal."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    timestamp TEXT,
                    symbol TEXT,
                    direction TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    position_size REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    outcome TEXT,
                    pnl_amount REAL,
                    pnl_percent REAL,
                    risk_reward_actual REAL,
                    setup_type TEXT,
                    thesis TEXT,
                    market_conditions TEXT,
                    timeframe TEXT,
                    what_went_well TEXT,
                    what_went_wrong TEXT,
                    lessons_learned TEXT,
                    mistakes_json TEXT,
                    rating INTEGER,
                    entry_screenshot TEXT,
                    exit_screenshot TEXT,
                    pre_trade_emotion TEXT,
                    during_trade_emotion TEXT,
                    post_trade_emotion TEXT,
                    tags_json TEXT,
                    metadata_json TEXT
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_symbol ON journal_entries(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_time ON journal_entries(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_journal_outcome ON journal_entries(outcome)")

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()


class TradeJournal:
    """
    Trading journal for recording and analyzing trades.

    Usage:
        journal = TradeJournal()

        # Create entry
        entry = journal.create_entry(
            symbol="SOL",
            direction="LONG",
            entry_price=100,
            position_size=1.0,
            thesis="Strong momentum, whale accumulation"
        )

        # Update with exit
        journal.close_entry(
            entry.id,
            exit_price=110,
            lessons_learned="Patience paid off"
        )

        # Get analysis
        analysis = journal.get_performance_analysis()
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "journal.db"
        self.db = JournalDB(db_path)

    def create_entry(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        position_size: float = 0.0,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        thesis: str = "",
        setup_type: TradeSetup = TradeSetup.OTHER,
        timeframe: str = "",
        market_conditions: str = "",
        pre_trade_emotion: str = "",
        tags: List[str] = None
    ) -> JournalEntry:
        """Create a new journal entry."""
        import uuid

        entry = JournalEntry(
            trade_id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(timezone.utc).isoformat(),
            symbol=symbol.upper(),
            direction=direction.upper(),
            entry_price=entry_price,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            thesis=thesis,
            setup_type=setup_type,
            timeframe=timeframe,
            market_conditions=market_conditions,
            pre_trade_emotion=pre_trade_emotion,
            tags=tags or []
        )

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO journal_entries
                (trade_id, timestamp, symbol, direction, entry_price, position_size,
                 stop_loss, take_profit, outcome, setup_type, thesis, timeframe,
                 market_conditions, pre_trade_emotion, tags_json, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.trade_id, entry.timestamp, entry.symbol, entry.direction,
                entry.entry_price, entry.position_size, entry.stop_loss, entry.take_profit,
                TradeOutcome.PENDING.value, entry.setup_type.value, entry.thesis,
                entry.timeframe, entry.market_conditions, entry.pre_trade_emotion,
                json.dumps(entry.tags), json.dumps({})
            ))
            conn.commit()
            entry.id = cursor.lastrowid

        logger.info(f"Created journal entry: {entry.trade_id} - {entry.symbol}")
        return entry

    def close_entry(
        self,
        entry_id: int = None,
        trade_id: str = None,
        exit_price: float = 0.0,
        pnl_amount: float = None,
        what_went_well: str = "",
        what_went_wrong: str = "",
        lessons_learned: str = "",
        mistakes: List[TradeMistake] = None,
        rating: int = 0,
        during_trade_emotion: str = "",
        post_trade_emotion: str = ""
    ) -> Optional[JournalEntry]:
        """Close a journal entry with exit details."""
        entry = self.get_entry(entry_id=entry_id, trade_id=trade_id)
        if not entry:
            return None

        # Calculate P&L if not provided
        if pnl_amount is None and entry.entry_price > 0 and exit_price > 0:
            if entry.direction == "LONG":
                pnl_percent = ((exit_price - entry.entry_price) / entry.entry_price) * 100
            else:  # SHORT
                pnl_percent = ((entry.entry_price - exit_price) / entry.entry_price) * 100

            pnl_amount = entry.position_size * (exit_price - entry.entry_price)
            if entry.direction == "SHORT":
                pnl_amount = -pnl_amount
        else:
            pnl_percent = (pnl_amount / (entry.entry_price * entry.position_size) * 100
                         if entry.entry_price and entry.position_size else 0)

        # Determine outcome
        if pnl_percent > 1:
            outcome = TradeOutcome.WIN
        elif pnl_percent < -1:
            outcome = TradeOutcome.LOSS
        else:
            outcome = TradeOutcome.BREAKEVEN

        # Calculate actual risk/reward
        risk_reward_actual = 0
        if entry.stop_loss and entry.entry_price:
            risk = abs(entry.entry_price - entry.stop_loss)
            if risk > 0:
                reward = abs(exit_price - entry.entry_price)
                risk_reward_actual = reward / risk

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE journal_entries SET
                    exit_price = ?,
                    pnl_amount = ?,
                    pnl_percent = ?,
                    outcome = ?,
                    risk_reward_actual = ?,
                    what_went_well = ?,
                    what_went_wrong = ?,
                    lessons_learned = ?,
                    mistakes_json = ?,
                    rating = ?,
                    during_trade_emotion = ?,
                    post_trade_emotion = ?
                WHERE id = ?
            """, (
                exit_price, pnl_amount, pnl_percent, outcome.value,
                risk_reward_actual, what_went_well, what_went_wrong,
                lessons_learned,
                json.dumps([m.value for m in (mistakes or [])]),
                rating, during_trade_emotion, post_trade_emotion,
                entry.id
            ))
            conn.commit()

        return self.get_entry(entry_id=entry.id)

    def get_entry(
        self,
        entry_id: int = None,
        trade_id: str = None
    ) -> Optional[JournalEntry]:
        """Get a journal entry."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            if entry_id:
                cursor.execute("SELECT * FROM journal_entries WHERE id = ?", (entry_id,))
            elif trade_id:
                cursor.execute("SELECT * FROM journal_entries WHERE trade_id = ?", (trade_id,))
            else:
                return None

            row = cursor.fetchone()
            return self._row_to_entry(row) if row else None

    def get_entries(
        self,
        symbol: str = None,
        outcome: TradeOutcome = None,
        days: int = 30,
        limit: int = 100
    ) -> List[JournalEntry]:
        """Get journal entries with filters."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT * FROM journal_entries
                WHERE datetime(timestamp) > datetime('now', ?)
            """
            params = [f'-{days} days']

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())
            if outcome:
                query += " AND outcome = ?"
                params.append(outcome.value)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [self._row_to_entry(row) for row in cursor.fetchall()]

    def _row_to_entry(self, row: sqlite3.Row) -> JournalEntry:
        """Convert database row to JournalEntry."""
        mistakes = []
        if row['mistakes_json']:
            mistakes = [TradeMistake(m) for m in json.loads(row['mistakes_json'])]

        return JournalEntry(
            id=row['id'],
            trade_id=row['trade_id'],
            timestamp=row['timestamp'],
            symbol=row['symbol'],
            direction=row['direction'] or "",
            entry_price=row['entry_price'] or 0,
            exit_price=row['exit_price'] or 0,
            position_size=row['position_size'] or 0,
            stop_loss=row['stop_loss'] or 0,
            take_profit=row['take_profit'] or 0,
            outcome=TradeOutcome(row['outcome']) if row['outcome'] else TradeOutcome.PENDING,
            pnl_amount=row['pnl_amount'] or 0,
            pnl_percent=row['pnl_percent'] or 0,
            risk_reward_actual=row['risk_reward_actual'] or 0,
            setup_type=TradeSetup(row['setup_type']) if row['setup_type'] else TradeSetup.OTHER,
            thesis=row['thesis'] or "",
            market_conditions=row['market_conditions'] or "",
            timeframe=row['timeframe'] or "",
            what_went_well=row['what_went_well'] or "",
            what_went_wrong=row['what_went_wrong'] or "",
            lessons_learned=row['lessons_learned'] or "",
            mistakes=mistakes,
            rating=row['rating'] or 0,
            entry_screenshot=row['entry_screenshot'] or "",
            exit_screenshot=row['exit_screenshot'] or "",
            pre_trade_emotion=row['pre_trade_emotion'] or "",
            during_trade_emotion=row['during_trade_emotion'] or "",
            post_trade_emotion=row['post_trade_emotion'] or "",
            tags=json.loads(row['tags_json']) if row['tags_json'] else [],
            metadata=json.loads(row['metadata_json']) if row['metadata_json'] else {}
        )

    def get_performance_analysis(self, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive performance analysis."""
        entries = self.get_entries(days=days, limit=1000)

        if not entries:
            return {'error': 'No trades found'}

        closed = [e for e in entries if e.outcome != TradeOutcome.PENDING]
        wins = [e for e in closed if e.outcome == TradeOutcome.WIN]
        losses = [e for e in closed if e.outcome == TradeOutcome.LOSS]

        # Win rate
        win_rate = len(wins) / len(closed) * 100 if closed else 0

        # P&L
        total_pnl = sum(e.pnl_amount for e in closed)
        avg_win = sum(e.pnl_amount for e in wins) / len(wins) if wins else 0
        avg_loss = sum(e.pnl_amount for e in losses) / len(losses) if losses else 0

        # Profit factor
        gross_profit = sum(e.pnl_amount for e in wins)
        gross_loss = abs(sum(e.pnl_amount for e in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        # By setup type
        by_setup = {}
        for setup in TradeSetup:
            setup_trades = [e for e in closed if e.setup_type == setup]
            if setup_trades:
                setup_wins = [e for e in setup_trades if e.outcome == TradeOutcome.WIN]
                by_setup[setup.value] = {
                    'count': len(setup_trades),
                    'win_rate': len(setup_wins) / len(setup_trades) * 100,
                    'avg_pnl': sum(e.pnl_percent for e in setup_trades) / len(setup_trades)
                }

        # Common mistakes
        all_mistakes = []
        for e in closed:
            all_mistakes.extend(e.mistakes)

        mistake_counts = {}
        for m in all_mistakes:
            mistake_counts[m.value] = mistake_counts.get(m.value, 0) + 1

        # Best and worst trades
        sorted_by_pnl = sorted(closed, key=lambda e: e.pnl_percent, reverse=True)

        return {
            'period_days': days,
            'total_trades': len(entries),
            'closed_trades': len(closed),
            'pending_trades': len(entries) - len(closed),
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'largest_win': sorted_by_pnl[0].pnl_percent if sorted_by_pnl else 0,
            'largest_loss': sorted_by_pnl[-1].pnl_percent if sorted_by_pnl else 0,
            'by_setup': by_setup,
            'common_mistakes': mistake_counts,
            'best_trades': [
                {'symbol': e.symbol, 'pnl': e.pnl_percent, 'setup': e.setup_type.value}
                for e in sorted_by_pnl[:3]
            ],
            'worst_trades': [
                {'symbol': e.symbol, 'pnl': e.pnl_percent, 'setup': e.setup_type.value}
                for e in sorted_by_pnl[-3:]
            ]
        }

    def get_lessons_summary(self, days: int = 30) -> List[str]:
        """Get summary of lessons learned."""
        entries = self.get_entries(days=days)
        lessons = [e.lessons_learned for e in entries if e.lessons_learned]
        return lessons

    def generate_report(self, days: int = 30) -> str:
        """Generate a trading journal report."""
        analysis = self.get_performance_analysis(days)

        lines = [
            f"Trading Journal Report - Last {days} Days",
            "=" * 50,
            "",
            f"Total Trades: {analysis.get('total_trades', 0)}",
            f"Win Rate: {analysis.get('win_rate', 0):.1f}%",
            f"Total P&L: ${analysis.get('total_pnl', 0):,.2f}",
            f"Profit Factor: {analysis.get('profit_factor', 0):.2f}",
            "",
            "Performance by Setup:",
        ]

        for setup, stats in analysis.get('by_setup', {}).items():
            lines.append(f"  {setup}: {stats['count']} trades, {stats['win_rate']:.0f}% WR")

        if analysis.get('common_mistakes'):
            lines.extend(["", "Common Mistakes:"])
            for mistake, count in sorted(analysis['common_mistakes'].items(), key=lambda x: -x[1]):
                lines.append(f"  {mistake}: {count}x")

        return "\n".join(lines)


# Singleton
_journal: Optional[TradeJournal] = None

def get_trade_journal() -> TradeJournal:
    """Get singleton trade journal."""
    global _journal
    if _journal is None:
        _journal = TradeJournal()
    return _journal
