"""
Treasury Database - SQLite backend for positions and performance analytics.

Migrates from JSON to proper SQLite for:
- Better querying and analytics
- Daily rollups and stats
- Full trade history
- Performance metrics over time
"""

import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from contextlib import contextmanager

from core.database import get_core_db

logger = logging.getLogger(__name__)

# Database path (kept for compatibility, but using unified layer)
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "jarvis.db"


@dataclass
class DBPosition:
    """A trading position stored in database."""
    id: str
    token_address: str
    token_symbol: str
    side: str  # LONG or SHORT
    entry_price: float
    entry_amount_sol: float
    entry_amount_tokens: float
    entry_timestamp: str
    exit_price: Optional[float] = None
    exit_timestamp: Optional[str] = None
    exit_reason: Optional[str] = None  # TP, SL, MANUAL
    pnl_sol: Optional[float] = None
    pnl_percent: Optional[float] = None
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None
    status: str = "OPEN"  # OPEN or CLOSED
    tx_entry: str = ""
    tx_exit: str = ""
    user_id: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DailyStats:
    """Daily performance rollup."""
    date: str
    trades_opened: int = 0
    trades_closed: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl_sol: float = 0.0
    total_pnl_percent: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    win_rate: float = 0.0


@dataclass
class TreasuryStats:
    """Overall treasury statistics."""
    total_trades: int = 0
    total_wins: int = 0
    total_losses: int = 0
    current_streak: int = 0  # Positive = wins, negative = losses
    best_win_streak: int = 0
    worst_loss_streak: int = 0
    all_time_pnl_sol: float = 0.0
    largest_win_sol: float = 0.0
    largest_win_token: str = ""
    largest_loss_sol: float = 0.0
    largest_loss_token: str = ""


@dataclass
class TradeLearning:
    """Learning/insight from a trade for persistent memory."""
    id: int = 0
    trade_id: str = ""
    token_symbol: str = ""
    token_type: str = ""  # SHITCOIN, MICRO, MID, ESTABLISHED
    learning_type: str = ""  # WIN_PATTERN, LOSS_PATTERN, ENTRY_TIMING, EXIT_TIMING
    insight: str = ""
    confidence: float = 0.5
    created_at: str = ""
    applied_count: int = 0  # How many times this learning was used


@dataclass
class ErrorLog:
    """Error log for improved error handling."""
    id: int = 0
    error_type: str = ""  # TRADE_FAILED, PRICE_FETCH, API_ERROR, etc.
    component: str = ""  # treasury, grok, telegram, etc.
    message: str = ""
    context: str = ""  # JSON context
    stack_trace: str = ""
    resolved: bool = False
    created_at: str = ""


@dataclass
class PickPerformance:
    """Track performance of Grok/JARVIS conviction picks."""
    id: int = 0
    pick_date: str = ""  # When the pick was made
    symbol: str = ""
    asset_class: str = ""  # token/stock/index
    contract: str = ""
    conviction_score: int = 0  # 1-100 original conviction
    entry_price: float = 0.0  # Price at pick time
    target_price: float = 0.0  # Target set by Grok
    stop_loss: float = 0.0  # Stop set by Grok
    timeframe: str = ""  # short/medium/long
    # Performance tracking
    current_price: float = 0.0
    max_price: float = 0.0  # Highest price since pick
    min_price: float = 0.0  # Lowest price since pick
    pnl_pct: float = 0.0  # Current P&L %
    max_gain_pct: float = 0.0  # Max potential gain hit
    hit_target: bool = False  # Did it hit target?
    hit_stop: bool = False  # Did it hit stop?
    outcome: str = ""  # WIN, LOSS, PENDING
    last_updated: str = ""
    reasoning: str = ""  # Original reasoning
    days_held: int = 0


class TreasuryDatabase:
    """
    SQLite database manager for treasury trading.

    Provides:
    - Position management (open, close, query)
    - Performance analytics
    - Daily stat rollups
    - Full history for ML/analysis
    """

    _instance: Optional["TreasuryDatabase"] = None

    def __new__(cls, db_path: str = None):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, db_path: str = None):
        if self._initialized:
            return

        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()
        self._initialized = True
        logger.info(f"TreasuryDatabase initialized at {self.db_path}")

    @contextmanager
    def _get_conn(self):
        """Context manager for database connections (via unified layer)."""
        db = get_core_db()
        with db.connection() as conn:
            yield conn

    def _init_schema(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Positions table (current and historical)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id TEXT PRIMARY KEY,
                    token_address TEXT NOT NULL,
                    token_symbol TEXT NOT NULL,
                    side TEXT CHECK(side IN ('LONG', 'SHORT')),
                    entry_price REAL NOT NULL,
                    entry_amount_sol REAL NOT NULL,
                    entry_amount_tokens REAL NOT NULL,
                    entry_timestamp TEXT NOT NULL,
                    exit_price REAL,
                    exit_timestamp TEXT,
                    exit_reason TEXT,
                    pnl_sol REAL,
                    pnl_percent REAL,
                    tp_price REAL,
                    sl_price REAL,
                    status TEXT CHECK(status IN ('OPEN', 'CLOSED')) DEFAULT 'OPEN',
                    tx_entry TEXT,
                    tx_exit TEXT,
                    user_id INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Daily stats rollup
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT PRIMARY KEY,
                    trades_opened INTEGER DEFAULT 0,
                    trades_closed INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_pnl_sol REAL DEFAULT 0,
                    total_pnl_percent REAL DEFAULT 0,
                    largest_win REAL DEFAULT 0,
                    largest_loss REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0
                )
            """)

            # Running totals (singleton row)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS treasury_stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_trades INTEGER DEFAULT 0,
                    total_wins INTEGER DEFAULT 0,
                    total_losses INTEGER DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    best_win_streak INTEGER DEFAULT 0,
                    worst_loss_streak INTEGER DEFAULT 0,
                    all_time_pnl_sol REAL DEFAULT 0,
                    largest_win_sol REAL DEFAULT 0,
                    largest_win_token TEXT DEFAULT '',
                    largest_loss_sol REAL DEFAULT 0,
                    largest_loss_token TEXT DEFAULT '',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Initialize treasury_stats if empty
            cursor.execute("SELECT COUNT(*) FROM treasury_stats")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO treasury_stats (id, total_trades, total_wins, total_losses)
                    VALUES (1, 0, 0, 0)
                """)

            # Trade learnings table (persistent memory)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trade_learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    token_symbol TEXT,
                    token_type TEXT,
                    learning_type TEXT,
                    insight TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    applied_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Error logs table (improved error tracking)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS error_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    error_type TEXT NOT NULL,
                    component TEXT NOT NULL,
                    message TEXT NOT NULL,
                    context TEXT,
                    stack_trace TEXT,
                    resolved INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Pick performance tracking (Grok/JARVIS conviction picks)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pick_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pick_date TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    contract TEXT,
                    conviction_score INTEGER DEFAULT 0,
                    entry_price REAL DEFAULT 0,
                    target_price REAL DEFAULT 0,
                    stop_loss REAL DEFAULT 0,
                    timeframe TEXT,
                    current_price REAL DEFAULT 0,
                    max_price REAL DEFAULT 0,
                    min_price REAL DEFAULT 0,
                    pnl_pct REAL DEFAULT 0,
                    max_gain_pct REAL DEFAULT 0,
                    hit_target INTEGER DEFAULT 0,
                    hit_stop INTEGER DEFAULT 0,
                    outcome TEXT DEFAULT 'PENDING',
                    reasoning TEXT,
                    days_held INTEGER DEFAULT 0,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(pick_date, symbol)
                )
            """)

            # Indexes for fast queries (wrapped in try/except for schema variations)
            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_positions_status
                    ON positions(status)
                """)
            except Exception as e:
                logger.debug(f"Index idx_positions_status already exists or creation failed: {e}")

            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_positions_token
                    ON positions(token_symbol)
                """)
            except Exception as e:
                logger.debug(f"Index idx_positions_token already exists or creation failed: {e}")

            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_positions_timestamp
                    ON positions(entry_timestamp)
                """)
            except Exception as e:
                logger.debug(f"Index idx_positions_timestamp already exists or creation failed: {e}")

            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_learnings_type
                    ON trade_learnings(learning_type)
                """)
            except Exception as e:
                logger.debug(f"Index idx_learnings_type already exists or creation failed: {e}")

            try:
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_errors_component
                    ON error_logs(component)
                """)
            except Exception as e:
                logger.debug(f"Index idx_errors_component already exists or creation failed: {e}")

    # =========================================================================
    # Position Management
    # =========================================================================

    def open_position(self, position: DBPosition) -> str:
        """Record a new position."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO positions (
                    id, token_address, token_symbol, side,
                    entry_price, entry_amount_sol, entry_amount_tokens,
                    entry_timestamp, tp_price, sl_price, status,
                    tx_entry, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
            """, (
                position.id,
                position.token_address,
                position.token_symbol,
                position.side,
                position.entry_price,
                position.entry_amount_sol,
                position.entry_amount_tokens,
                position.entry_timestamp,
                position.tp_price,
                position.sl_price,
                position.tx_entry,
                position.user_id,
            ))

            # Update daily stats
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cursor.execute("""
                INSERT INTO daily_stats (date, trades_opened)
                VALUES (?, 1)
                ON CONFLICT(date) DO UPDATE SET
                    trades_opened = trades_opened + 1
            """, (today,))

            # Update treasury stats
            cursor.execute("""
                UPDATE treasury_stats SET
                    total_trades = total_trades + 1,
                    updated_at = ?
                WHERE id = 1
            """, (datetime.now(timezone.utc).isoformat(),))

        logger.info(f"Opened position {position.id}: {position.token_symbol}")
        return position.id

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_amount_sol: float,
        reason: str = "MANUAL",
        tx_exit: str = ""
    ) -> bool:
        """Close a position and calculate P&L."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Get the position - optimized query with explicit columns
            cursor.execute("""
                SELECT id, token_address, token_symbol, side, entry_price, entry_amount_sol,
                       entry_amount_tokens, entry_timestamp, status, tp_price, sl_price,
                       tx_entry, tx_exit, user_id
                FROM positions WHERE id = ?
            """, (position_id,))
            row = cursor.fetchone()

            if not row:
                logger.error(f"Position {position_id} not found")
                return False

            if row["status"] == "CLOSED":
                logger.warning(f"Position {position_id} already closed")
                return False

            # Calculate P&L
            entry_sol = row["entry_amount_sol"]
            pnl_sol = exit_amount_sol - entry_sol
            pnl_percent = (pnl_sol / entry_sol * 100) if entry_sol > 0 else 0

            exit_timestamp = datetime.now(timezone.utc).isoformat()

            # Update position
            cursor.execute("""
                UPDATE positions SET
                    status = 'CLOSED',
                    exit_price = ?,
                    exit_timestamp = ?,
                    exit_reason = ?,
                    pnl_sol = ?,
                    pnl_percent = ?,
                    tx_exit = ?
                WHERE id = ?
            """, (
                exit_price,
                exit_timestamp,
                reason,
                pnl_sol,
                pnl_percent,
                tx_exit,
                position_id,
            ))

            # Update daily stats
            is_win = pnl_sol > 0
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            cursor.execute("""
                INSERT INTO daily_stats (date, trades_closed, wins, losses, total_pnl_sol, largest_win, largest_loss)
                VALUES (?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    trades_closed = trades_closed + 1,
                    wins = wins + ?,
                    losses = losses + ?,
                    total_pnl_sol = total_pnl_sol + ?,
                    largest_win = MAX(largest_win, ?),
                    largest_loss = MIN(largest_loss, ?)
            """, (
                today,
                1 if is_win else 0,
                0 if is_win else 1,
                pnl_sol,
                pnl_sol if is_win else 0,
                pnl_sol if not is_win else 0,
                # For ON CONFLICT
                1 if is_win else 0,
                0 if is_win else 1,
                pnl_sol,
                pnl_sol if is_win else 0,
                pnl_sol if not is_win else 0,
            ))

            # Update treasury stats
            self._update_treasury_stats(cursor, pnl_sol, is_win, row["token_symbol"])

        logger.info(
            f"Closed position {position_id}: {row['token_symbol']} "
            f"P&L: {pnl_sol:+.6f} SOL ({pnl_percent:+.1f}%)"
        )
        return True

    def _update_treasury_stats(self, cursor, pnl_sol: float, is_win: bool, token_symbol: str):
        """Update running treasury statistics."""
        # Get current stats - optimized query with explicit columns
        cursor.execute("""
            SELECT total_trades, total_wins, total_losses, current_streak,
                   best_win_streak, worst_loss_streak, all_time_pnl_sol,
                   largest_win_sol, largest_win_token, largest_loss_sol, largest_loss_token
            FROM treasury_stats WHERE id = 1
        """)
        stats = dict(cursor.fetchone())

        # Update streak
        if is_win:
            if stats["current_streak"] >= 0:
                new_streak = stats["current_streak"] + 1
            else:
                new_streak = 1
            best_streak = max(stats["best_win_streak"], new_streak)
            worst_streak = stats["worst_loss_streak"]
        else:
            if stats["current_streak"] <= 0:
                new_streak = stats["current_streak"] - 1
            else:
                new_streak = -1
            worst_streak = min(stats["worst_loss_streak"], new_streak)
            best_streak = stats["best_win_streak"]

        # Update largest win/loss
        largest_win = stats["largest_win_sol"]
        largest_win_token = stats["largest_win_token"]
        largest_loss = stats["largest_loss_sol"]
        largest_loss_token = stats["largest_loss_token"]

        if is_win and pnl_sol > largest_win:
            largest_win = pnl_sol
            largest_win_token = token_symbol
        elif not is_win and pnl_sol < largest_loss:
            largest_loss = pnl_sol
            largest_loss_token = token_symbol

        cursor.execute("""
            UPDATE treasury_stats SET
                total_wins = total_wins + ?,
                total_losses = total_losses + ?,
                current_streak = ?,
                best_win_streak = ?,
                worst_loss_streak = ?,
                all_time_pnl_sol = all_time_pnl_sol + ?,
                largest_win_sol = ?,
                largest_win_token = ?,
                largest_loss_sol = ?,
                largest_loss_token = ?,
                updated_at = ?
            WHERE id = 1
        """, (
            1 if is_win else 0,
            0 if is_win else 1,
            new_streak,
            best_streak,
            worst_streak,
            pnl_sol,
            largest_win,
            largest_win_token,
            largest_loss,
            largest_loss_token,
            datetime.now(timezone.utc).isoformat(),
        ))

    # =========================================================================
    # Queries
    # =========================================================================

    def get_open_positions(self) -> List[DBPosition]:
        """Get all open positions - HOT PATH optimized."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # Explicit column list for better query plan
            cursor.execute("""
                SELECT id, token_address, token_symbol, side, entry_price, entry_amount_sol,
                       entry_amount_tokens, entry_timestamp, exit_price, exit_timestamp,
                       exit_reason, pnl_sol, pnl_percent, tp_price, sl_price, status,
                       tx_entry, tx_exit, user_id
                FROM positions WHERE status = 'OPEN'
            """)
            return [DBPosition(**dict(row)) for row in cursor.fetchall()]

    def get_position(self, position_id: str) -> Optional[DBPosition]:
        """Get a position by ID - optimized."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, token_address, token_symbol, side, entry_price, entry_amount_sol,
                       entry_amount_tokens, entry_timestamp, exit_price, exit_timestamp,
                       exit_reason, pnl_sol, pnl_percent, tp_price, sl_price, status,
                       tx_entry, tx_exit, user_id
                FROM positions WHERE id = ?
            """, (position_id,))
            row = cursor.fetchone()
            return DBPosition(**dict(row)) if row else None

    def get_position_by_token(self, token_address: str) -> Optional[DBPosition]:
        """Get open position for a token - HOT PATH optimized."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, token_address, token_symbol, side, entry_price, entry_amount_sol,
                       entry_amount_tokens, entry_timestamp, exit_price, exit_timestamp,
                       exit_reason, pnl_sol, pnl_percent, tp_price, sl_price, status,
                       tx_entry, tx_exit, user_id
                FROM positions
                WHERE token_address = ? AND status = 'OPEN'
            """, (token_address,))
            row = cursor.fetchone()
            return DBPosition(**dict(row)) if row else None

    def get_recent_trades(self, limit: int = 10) -> List[DBPosition]:
        """Get recent closed trades - optimized."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, token_address, token_symbol, side, entry_price, entry_amount_sol,
                       entry_amount_tokens, entry_timestamp, exit_price, exit_timestamp,
                       exit_reason, pnl_sol, pnl_percent, tp_price, sl_price, status,
                       tx_entry, tx_exit, user_id
                FROM positions
                WHERE status = 'CLOSED'
                ORDER BY exit_timestamp DESC
                LIMIT ?
            """, (limit,))
            return [DBPosition(**dict(row)) for row in cursor.fetchall()]

    def get_stats(self) -> TreasuryStats:
        """Get overall treasury statistics - optimized."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT total_trades, total_wins, total_losses, current_streak,
                       best_win_streak, worst_loss_streak, all_time_pnl_sol,
                       largest_win_sol, largest_win_token, largest_loss_sol, largest_loss_token
                FROM treasury_stats WHERE id = 1
            """)
            row = cursor.fetchone()
            if row:
                return TreasuryStats(
                    total_trades=row["total_trades"],
                    total_wins=row["total_wins"],
                    total_losses=row["total_losses"],
                    current_streak=row["current_streak"],
                    best_win_streak=row["best_win_streak"],
                    worst_loss_streak=row["worst_loss_streak"],
                    all_time_pnl_sol=row["all_time_pnl_sol"],
                    largest_win_sol=row["largest_win_sol"],
                    largest_win_token=row["largest_win_token"],
                    largest_loss_sol=row["largest_loss_sol"],
                    largest_loss_token=row["largest_loss_token"],
                )
            return TreasuryStats()

    def get_win_rate(self) -> float:
        """Get overall win rate."""
        stats = self.get_stats()
        total = stats.total_wins + stats.total_losses
        return (stats.total_wins / total * 100) if total > 0 else 0.0

    def get_daily_stats(self, days: int = 30) -> List[DailyStats]:
        """Get daily stats for the last N days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, trades_opened, trades_closed, wins, losses,
                       total_pnl_sol, total_pnl_percent, largest_win,
                       largest_loss, win_rate
                FROM daily_stats
                WHERE date >= ?
                ORDER BY date DESC
            """, (cutoff,))
            return [DailyStats(**dict(row)) for row in cursor.fetchall()]

    def get_telegram_summary(self) -> Dict[str, Any]:
        """Get summary data formatted for Telegram display."""
        stats = self.get_stats()
        open_pos = self.get_open_positions()
        recent = self.get_recent_trades(5)

        win_rate = self.get_win_rate()

        return {
            "stats": {
                "win_rate": win_rate,
                "wins": stats.total_wins,
                "losses": stats.total_losses,
                "total_pnl_sol": stats.all_time_pnl_sol,
                "current_streak": stats.current_streak,
                "best_streak": stats.best_win_streak,
                "worst_streak": stats.worst_loss_streak,
                "largest_win": stats.largest_win_sol,
                "largest_loss": stats.largest_loss_sol,
            },
            "open_positions": [
                {
                    "symbol": p.token_symbol,
                    "entry_price": p.entry_price,
                    "entry_sol": p.entry_amount_sol,
                    "tp": p.tp_price,
                    "sl": p.sl_price,
                }
                for p in open_pos
            ],
            "recent_trades": [
                {
                    "symbol": p.token_symbol,
                    "pnl_pct": p.pnl_percent,
                    "pnl_sol": p.pnl_sol,
                    "reason": p.exit_reason,
                    "is_win": (p.pnl_sol or 0) > 0,
                }
                for p in recent
            ],
        }

    # =========================================================================
    # Persistent Memory (Trade Learnings)
    # =========================================================================

    def store_learning(
        self,
        insight: str,
        learning_type: str,
        trade_id: str = "",
        token_symbol: str = "",
        token_type: str = "",
        confidence: float = 0.5,
    ) -> int:
        """Store a learning/insight from a trade."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trade_learnings
                (trade_id, token_symbol, token_type, learning_type, insight, confidence, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                token_symbol,
                token_type,
                learning_type,
                insight,
                confidence,
                datetime.now(timezone.utc).isoformat(),
            ))
            return cursor.lastrowid

    def get_learnings(
        self,
        token_type: str = None,
        learning_type: str = None,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> List[TradeLearning]:
        """Get learnings, optionally filtered by type."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # Optimized: explicit column list
            query = """SELECT id, trade_id, token_symbol, token_type, learning_type,
                             insight, confidence, created_at, applied_count
                      FROM trade_learnings WHERE confidence >= ?"""
            params = [min_confidence]

            if token_type:
                query += " AND token_type = ?"
                params.append(token_type)
            if learning_type:
                query += " AND learning_type = ?"
                params.append(learning_type)

            query += " ORDER BY confidence DESC, created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [TradeLearning(**dict(row)) for row in cursor.fetchall()]

    def get_learnings_for_token(self, token_symbol: str) -> List[TradeLearning]:
        """Get learnings relevant to a specific token."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, trade_id, token_symbol, token_type, learning_type,
                       insight, confidence, created_at, applied_count
                FROM trade_learnings
                WHERE token_symbol = ? OR token_symbol = ''
                ORDER BY confidence DESC, created_at DESC
                LIMIT 10
            """, (token_symbol,))
            return [TradeLearning(**dict(row)) for row in cursor.fetchall()]

    def increment_learning_applied(self, learning_id: int):
        """Increment the applied count for a learning."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE trade_learnings SET applied_count = applied_count + 1
                WHERE id = ?
            """, (learning_id,))

    # =========================================================================
    # Error Logging
    # =========================================================================

    def log_error(
        self,
        error_type: str,
        component: str,
        message: str,
        context: str = "",
        stack_trace: str = "",
    ) -> int:
        """Log an error for tracking."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO error_logs
                (error_type, component, message, context, stack_trace, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                error_type,
                component,
                message,
                context,
                stack_trace,
                datetime.now(timezone.utc).isoformat(),
            ))
            logger.warning(f"Error logged: [{component}] {error_type}: {message}")
            return cursor.lastrowid

    def get_recent_errors(self, component: str = None, limit: int = 20) -> List[ErrorLog]:
        """Get recent errors, optionally filtered by component."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            columns = "id, error_type, component, message, context, stack_trace, resolved, created_at"
            if component:
                cursor.execute(f"""
                    SELECT {columns}
                    FROM error_logs
                    WHERE component = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (component, limit))
            else:
                cursor.execute(f"""
                    SELECT {columns}
                    FROM error_logs
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))
            return [ErrorLog(**dict(row)) for row in cursor.fetchall()]

    def get_unresolved_errors(self) -> List[ErrorLog]:
        """Get all unresolved errors."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, error_type, component, message, context,
                       stack_trace, resolved, created_at
                FROM error_logs
                WHERE resolved = 0
                ORDER BY created_at DESC
            """)
            return [ErrorLog(**dict(row)) for row in cursor.fetchall()]

    def resolve_error(self, error_id: int):
        """Mark an error as resolved."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE error_logs SET resolved = 1
                WHERE id = ?
            """, (error_id,))

    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors by type and component."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Count by component
            cursor.execute("""
                SELECT component, COUNT(*) as count
                FROM error_logs
                WHERE created_at > datetime('now', '-7 days')
                GROUP BY component
            """)
            by_component = {row["component"]: row["count"] for row in cursor.fetchall()}

            # Count by type
            cursor.execute("""
                SELECT error_type, COUNT(*) as count
                FROM error_logs
                WHERE created_at > datetime('now', '-7 days')
                GROUP BY error_type
            """)
            by_type = {row["error_type"]: row["count"] for row in cursor.fetchall()}

            # Unresolved count
            cursor.execute("SELECT COUNT(*) FROM error_logs WHERE resolved = 0")
            unresolved = cursor.fetchone()[0]

            return {
                "by_component": by_component,
                "by_type": by_type,
                "unresolved_count": unresolved,
            }

    # =========================================================================
    # Pick Performance Tracking
    # =========================================================================

    def record_pick(
        self,
        symbol: str,
        asset_class: str,
        conviction_score: int,
        entry_price: float,
        target_price: float,
        stop_loss: float,
        timeframe: str,
        reasoning: str = "",
        contract: str = "",
    ) -> int:
        """Record a new conviction pick for tracking."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO pick_performance
                (pick_date, symbol, asset_class, contract, conviction_score,
                 entry_price, target_price, stop_loss, timeframe, reasoning,
                 current_price, max_price, min_price, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today,
                symbol,
                asset_class,
                contract,
                conviction_score,
                entry_price,
                target_price,
                stop_loss,
                timeframe,
                reasoning,
                entry_price,  # current_price starts at entry
                entry_price,  # max_price starts at entry
                entry_price,  # min_price starts at entry
                datetime.now(timezone.utc).isoformat(),
            ))
            logger.info(f"Recorded pick: {symbol} (conviction: {conviction_score})")
            return cursor.lastrowid

    def update_pick_price(
        self,
        symbol: str,
        current_price: float,
        pick_date: str = None,
    ) -> bool:
        """Update the current price and calculate performance for a pick."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Get the pick - optimized query
            columns = """id, pick_date, symbol, asset_class, contract, conviction_score,
                        entry_price, target_price, stop_loss, timeframe, current_price,
                        max_price, min_price, pnl_pct, max_gain_pct, hit_target, hit_stop,
                        outcome, last_updated, reasoning, days_held"""
            if pick_date:
                cursor.execute(f"""
                    SELECT {columns}
                    FROM pick_performance
                    WHERE symbol = ? AND pick_date = ?
                """, (symbol, pick_date))
            else:
                cursor.execute(f"""
                    SELECT {columns}
                    FROM pick_performance
                    WHERE symbol = ? AND outcome = 'PENDING'
                    ORDER BY pick_date DESC LIMIT 1
                """, (symbol,))

            row = cursor.fetchone()
            if not row:
                return False

            pick = dict(row)
            entry_price = pick["entry_price"]
            target_price = pick["target_price"]
            stop_loss = pick["stop_loss"]

            # Update max/min prices
            new_max = max(pick["max_price"], current_price)
            new_min = min(pick["min_price"], current_price) if pick["min_price"] > 0 else current_price

            # Calculate P&L
            pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            max_gain_pct = ((new_max - entry_price) / entry_price * 100) if entry_price > 0 else 0

            # Check if hit target or stop
            hit_target = current_price >= target_price if target_price > 0 else False
            hit_stop = current_price <= stop_loss if stop_loss > 0 else False

            # Determine outcome
            outcome = "PENDING"
            if hit_target:
                outcome = "WIN"
            elif hit_stop:
                outcome = "LOSS"

            # Calculate days held
            pick_date_dt = datetime.strptime(pick["pick_date"], "%Y-%m-%d")
            days_held = (datetime.now() - pick_date_dt).days

            cursor.execute("""
                UPDATE pick_performance SET
                    current_price = ?,
                    max_price = ?,
                    min_price = ?,
                    pnl_pct = ?,
                    max_gain_pct = ?,
                    hit_target = ?,
                    hit_stop = ?,
                    outcome = ?,
                    days_held = ?,
                    last_updated = ?
                WHERE id = ?
            """, (
                current_price,
                new_max,
                new_min,
                pnl_pct,
                max_gain_pct,
                1 if hit_target else 0,
                1 if hit_stop else 0,
                outcome,
                days_held,
                datetime.now(timezone.utc).isoformat(),
                pick["id"],
            ))
            return True

    def get_pending_picks(self) -> List[PickPerformance]:
        """Get all pending picks that need price updates."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pick_performance
                WHERE outcome = 'PENDING'
                ORDER BY pick_date DESC
            """)
            return [PickPerformance(**dict(row)) for row in cursor.fetchall()]

    def get_pick_history(
        self,
        days: int = 30,
        outcome: str = None,
    ) -> List[PickPerformance]:
        """Get pick history for analysis."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            query = """
                SELECT * FROM pick_performance
                WHERE pick_date > date('now', ?)
            """
            params = [f"-{days} days"]

            if outcome:
                query += " AND outcome = ?"
                params.append(outcome)

            query += " ORDER BY pick_date DESC"
            cursor.execute(query, params)
            return [PickPerformance(**dict(row)) for row in cursor.fetchall()]

    def get_pick_statistics(self, days: int = 30) -> Dict[str, Any]:
        """Get statistics on pick performance."""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # Total picks
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                       SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                       SUM(CASE WHEN outcome = 'PENDING' THEN 1 ELSE 0 END) as pending,
                       AVG(pnl_pct) as avg_pnl,
                       AVG(CASE WHEN outcome = 'WIN' THEN pnl_pct ELSE NULL END) as avg_win,
                       AVG(CASE WHEN outcome = 'LOSS' THEN pnl_pct ELSE NULL END) as avg_loss,
                       MAX(pnl_pct) as best_pick,
                       MIN(pnl_pct) as worst_pick,
                       AVG(conviction_score) as avg_conviction
                FROM pick_performance
                WHERE pick_date > date('now', ?)
            """, (f"-{days} days",))

            row = cursor.fetchone()
            stats = dict(row) if row else {}

            # Win rate by conviction tier
            cursor.execute("""
                SELECT
                    CASE
                        WHEN conviction_score >= 80 THEN 'HIGH (80+)'
                        WHEN conviction_score >= 60 THEN 'MEDIUM (60-79)'
                        ELSE 'LOW (<60)'
                    END as tier,
                    COUNT(*) as total,
                    SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                    ROUND(AVG(pnl_pct), 2) as avg_pnl
                FROM pick_performance
                WHERE pick_date > date('now', ?) AND outcome != 'PENDING'
                GROUP BY tier
            """, (f"-{days} days",))

            by_conviction = {}
            for row in cursor.fetchall():
                tier_data = dict(row)
                by_conviction[tier_data["tier"]] = {
                    "total": tier_data["total"],
                    "wins": tier_data["wins"],
                    "win_rate": tier_data["wins"] / tier_data["total"] if tier_data["total"] > 0 else 0,
                    "avg_pnl": tier_data["avg_pnl"] or 0,
                }

            # By asset class
            cursor.execute("""
                SELECT asset_class,
                       COUNT(*) as total,
                       SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                       ROUND(AVG(pnl_pct), 2) as avg_pnl
                FROM pick_performance
                WHERE pick_date > date('now', ?) AND outcome != 'PENDING'
                GROUP BY asset_class
            """, (f"-{days} days",))

            by_asset_class = {}
            for row in cursor.fetchall():
                asset_data = dict(row)
                by_asset_class[asset_data["asset_class"]] = {
                    "total": asset_data["total"],
                    "wins": asset_data["wins"],
                    "win_rate": asset_data["wins"] / asset_data["total"] if asset_data["total"] > 0 else 0,
                    "avg_pnl": asset_data["avg_pnl"] or 0,
                }

            total = stats.get("total", 0) or 0
            wins = stats.get("wins", 0) or 0
            losses = stats.get("losses", 0) or 0
            closed = wins + losses

            return {
                "total_picks": total,
                "wins": wins,
                "losses": losses,
                "pending": stats.get("pending", 0) or 0,
                "win_rate": wins / closed if closed > 0 else 0,
                "avg_pnl": stats.get("avg_pnl") or 0,
                "avg_win": stats.get("avg_win") or 0,
                "avg_loss": stats.get("avg_loss") or 0,
                "best_pick_pnl": stats.get("best_pick") or 0,
                "worst_pick_pnl": stats.get("worst_pick") or 0,
                "avg_conviction": stats.get("avg_conviction") or 0,
                "by_conviction": by_conviction,
                "by_asset_class": by_asset_class,
            }


# Singleton accessor
def get_treasury_database() -> TreasuryDatabase:
    """Get the treasury database singleton."""
    return TreasuryDatabase()
