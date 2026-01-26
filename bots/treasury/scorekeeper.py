"""
Treasury Scorekeeper - Persistent Trade Tracking and P&L

Tracks:
- All trades executed (buys and sells)
- Open positions with TP/SL orders
- Realized and unrealized P&L
- Win/loss record
- Performance metrics

Data persisted to JSON for reliability.
"""

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from core.database.sqlite_pool import sql_connection

logger = logging.getLogger(__name__)

# Persistence paths
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DB_PATH = DATA_DIR / "jarvis.db"
SCOREKEEPER_FILE = DATA_DIR / "treasury_scorekeeper.json"
ORDERS_FILE = DATA_DIR / "treasury_orders.json"


class PositionStatus(Enum):
    OPEN = "open"
    CLOSED_TP = "closed_tp"  # Closed at take profit
    CLOSED_SL = "closed_sl"  # Closed at stop loss
    CLOSED_MANUAL = "closed_manual"  # Manually closed
    FAILED = "failed"


@dataclass
class Position:
    """A trading position with TP/SL."""
    id: str
    symbol: str
    token_mint: str
    entry_price: float
    entry_amount_sol: float
    entry_amount_tokens: float
    take_profit_price: float
    stop_loss_price: float
    tp_order_id: str = ""
    sl_order_id: str = ""
    status: str = "open"
    exit_price: float = 0.0
    exit_amount_sol: float = 0.0
    pnl_sol: float = 0.0
    pnl_pct: float = 0.0
    opened_at: str = ""
    closed_at: str = ""
    tx_signature_entry: str = ""
    tx_signature_exit: str = ""
    user_id: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "Position":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    id: str
    symbol: str
    token_mint: str
    side: str  # "buy" or "sell"
    amount_sol: float
    amount_tokens: float
    price: float
    timestamp: str
    tx_signature: str = ""
    position_id: str = ""
    user_id: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ScoreCard:
    """Performance metrics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl_sol: float = 0.0
    total_pnl_usd: float = 0.0
    largest_win_sol: float = 0.0
    largest_loss_sol: float = 0.0
    current_streak: int = 0  # Positive = wins, negative = losses
    best_streak: int = 0
    worst_streak: int = 0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    win_rate: float = 0.0
    last_updated: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class Scorekeeper:
    """
    Persistent scorekeeper for treasury trading.
    
    Tracks all positions, trades, and performance metrics.
    Data is persisted to disk on every update.
    """

    _instance: Optional["Scorekeeper"] = None

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeRecord] = []
        self.scorecard = ScoreCard()
        self.orders: Dict[str, Dict] = {}  # TP/SL orders

        self._init_db()
        self._load()
        self._initialized = True
        logger.info(f"Scorekeeper initialized: {len(self.positions)} positions, {len(self.trades)} trades")

    def _get_conn(self) -> sqlite3.Connection:
        """Get a SQLite connection using the pooled connection manager."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Note: This returns a new connection managed by the pool.
        # The caller is responsible for closing it via try/finally.
        conn = sqlite3.connect(str(DB_PATH), timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        """Initialize SQLite schema for treasury tracking."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with sql_connection(str(DB_PATH)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    token_mint TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    entry_amount_sol REAL NOT NULL,
                    entry_amount_tokens REAL NOT NULL,
                    take_profit_price REAL,
                    stop_loss_price REAL,
                    tp_order_id TEXT,
                    sl_order_id TEXT,
                    status TEXT,
                    exit_price REAL,
                    exit_amount_sol REAL,
                    pnl_sol REAL,
                    pnl_pct REAL,
                    opened_at TEXT,
                    closed_at TEXT,
                    tx_signature_entry TEXT,
                    tx_signature_exit TEXT,
                    user_id INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    token_mint TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount_sol REAL NOT NULL,
                    amount_tokens REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    tx_signature TEXT,
                    position_id TEXT,
                    user_id INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scorecard (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_trades INTEGER DEFAULT 0,
                    winning_trades INTEGER DEFAULT 0,
                    losing_trades INTEGER DEFAULT 0,
                    total_pnl_sol REAL DEFAULT 0,
                    total_pnl_usd REAL DEFAULT 0,
                    largest_win_sol REAL DEFAULT 0,
                    largest_loss_sol REAL DEFAULT 0,
                    current_streak INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    worst_streak INTEGER DEFAULT 0,
                    avg_win_pct REAL DEFAULT 0,
                    avg_loss_pct REAL DEFAULT 0,
                    win_rate REAL DEFAULT 0,
                    last_updated TEXT DEFAULT ''
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS treasury_orders (
                    order_id TEXT PRIMARY KEY,
                    order_json TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_positions_status
                ON positions(status)
            """)

            # Pick performance tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pick_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pick_date TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    contract TEXT,
                    conviction_score INTEGER,
                    entry_price REAL,
                    target_price REAL,
                    stop_loss REAL,
                    timeframe TEXT,
                    reasoning TEXT,
                    current_price REAL,
                    max_price REAL,
                    min_price REAL,
                    pnl_pct REAL DEFAULT 0,
                    max_gain_pct REAL DEFAULT 0,
                    hit_target INTEGER DEFAULT 0,
                    hit_stop INTEGER DEFAULT 0,
                    outcome TEXT DEFAULT 'open',
                    days_held INTEGER DEFAULT 0,
                    last_updated TEXT
                )
            """)

            # Trade learnings table for feedback loop
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trade_learnings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    token_symbol TEXT NOT NULL,
                    token_type TEXT NOT NULL,
                    learning_type TEXT NOT NULL,
                    insight TEXT NOT NULL,
                    confidence REAL DEFAULT 0.5,
                    applied_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
            """)

            conn.execute("SELECT COUNT(*) FROM scorecard")
            if conn.execute("SELECT COUNT(*) FROM scorecard").fetchone()[0] == 0:
                conn.execute("INSERT INTO scorecard (id) VALUES (1)")
    def _load(self):
        """Load data from SQLite, migrating JSON if needed."""
        try:
            with self._get_conn() as conn:
                # Optimized queries with explicit column lists
                pos_rows = conn.execute("""
                    SELECT id, symbol, token_mint, entry_price, entry_amount_sol,
                           entry_amount_tokens, take_profit_price, stop_loss_price,
                           tp_order_id, sl_order_id, status, exit_price, exit_amount_sol,
                           pnl_sol, pnl_pct, opened_at, closed_at,
                           tx_signature_entry, tx_signature_exit, user_id
                    FROM positions
                """).fetchall()
                trade_rows = conn.execute("""
                    SELECT id, symbol, token_mint, side, amount_sol, amount_tokens,
                           price, timestamp, tx_signature, position_id, user_id
                    FROM trades
                """).fetchall()
                score_row = conn.execute("""
                    SELECT total_trades, winning_trades, losing_trades, total_pnl_sol,
                           total_pnl_usd, largest_win_sol, largest_loss_sol, current_streak,
                           best_streak, worst_streak, avg_win_pct, avg_loss_pct,
                           win_rate, last_updated
                    FROM scorecard WHERE id = 1
                """).fetchone()
                order_rows = conn.execute("""
                    SELECT order_id, position_id, type, price, status, placed_at, filled_at
                    FROM treasury_orders
                """).fetchall()

            if pos_rows or trade_rows or order_rows or score_row:
                self.positions = {
                    row["id"]: Position(
                        id=row["id"],
                        symbol=row["symbol"],
                        token_mint=row["token_mint"],
                        entry_price=row["entry_price"],
                        entry_amount_sol=row["entry_amount_sol"],
                        entry_amount_tokens=row["entry_amount_tokens"],
                        take_profit_price=row["take_profit_price"],
                        stop_loss_price=row["stop_loss_price"],
                        tp_order_id=row["tp_order_id"] or "",
                        sl_order_id=row["sl_order_id"] or "",
                        status=row["status"],
                        exit_price=row["exit_price"] or 0.0,
                        exit_amount_sol=row["exit_amount_sol"] or 0.0,
                        pnl_sol=row["pnl_sol"] or 0.0,
                        pnl_pct=row["pnl_pct"] or 0.0,
                        opened_at=row["opened_at"] or "",
                        closed_at=row["closed_at"] or "",
                        tx_signature_entry=row["tx_signature_entry"] or "",
                        tx_signature_exit=row["tx_signature_exit"] or "",
                        user_id=row["user_id"] or 0,
                    )
                    for row in pos_rows
                }
                self.trades = [
                    TradeRecord(
                        id=row["id"],
                        symbol=row["symbol"],
                        token_mint=row["token_mint"],
                        side=row["side"],
                        amount_sol=row["amount_sol"],
                        amount_tokens=row["amount_tokens"],
                        price=row["price"],
                        timestamp=row["timestamp"],
                        tx_signature=row["tx_signature"] or "",
                        position_id=row["position_id"] or "",
                        user_id=row["user_id"] or 0,
                    )
                    for row in trade_rows
                ]
                if score_row:
                    score_data = dict(score_row)
                    score_data.pop("id", None)
                    self.scorecard = ScoreCard(**score_data)
                self.orders = {
                    row["order_id"]: json.loads(row["order_json"])
                    for row in order_rows
                }
                logger.info(f"Loaded scorekeeper from SQLite: {len(self.positions)} positions")
                return
        except Exception as e:
            logger.error(f"Failed to load scorekeeper from SQLite: {e}")

        # Fallback: load legacy JSON once, then migrate into SQLite
        if SCOREKEEPER_FILE.exists():
            try:
                with open(SCOREKEEPER_FILE) as f:
                    data = json.load(f)

                self.positions = {
                    k: Position.from_dict(v) for k, v in data.get("positions", {}).items()
                }
                self.trades = [TradeRecord(**t) for t in data.get("trades", [])]
                self.scorecard = ScoreCard(**data.get("scorecard", {}))
                logger.info(f"Loaded legacy scorekeeper: {len(self.positions)} positions")
            except Exception as e:
                logger.error(f"Failed to load legacy scorekeeper: {e}")

        if ORDERS_FILE.exists():
            try:
                with open(ORDERS_FILE) as f:
                    self.orders = json.load(f)
                logger.info(f"Loaded legacy orders: {len(self.orders)} orders")
            except Exception as e:
                logger.error(f"Failed to load legacy orders: {e}")

        if self.positions or self.trades or self.orders:
            self._save()

    def _save(self):
        """Persist data to SQLite with explicit transaction control."""
        conn = None
        try:
            conn = self._get_conn()
            # Begin immediate transaction to lock the database for writing
            conn.execute("BEGIN IMMEDIATE")

            try:
                conn.execute("DELETE FROM positions")
                for pos in self.positions.values():
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO positions (
                            id, symbol, token_mint, entry_price, entry_amount_sol,
                            entry_amount_tokens, take_profit_price, stop_loss_price,
                            tp_order_id, sl_order_id, status, exit_price, exit_amount_sol,
                            pnl_sol, pnl_pct, opened_at, closed_at, tx_signature_entry,
                            tx_signature_exit, user_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pos.id,
                            pos.symbol,
                            pos.token_mint,
                            pos.entry_price,
                            pos.entry_amount_sol,
                            pos.entry_amount_tokens,
                            pos.take_profit_price,
                            pos.stop_loss_price,
                            pos.tp_order_id,
                            pos.sl_order_id,
                            pos.status,
                            pos.exit_price,
                            pos.exit_amount_sol,
                            pos.pnl_sol,
                            pos.pnl_pct,
                            pos.opened_at,
                            pos.closed_at,
                            pos.tx_signature_entry,
                            pos.tx_signature_exit,
                            pos.user_id,
                        ),
                    )

                conn.execute("DELETE FROM trades")
                for trade in self.trades:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO trades (
                            id, symbol, token_mint, side, amount_sol, amount_tokens,
                            price, timestamp, tx_signature, position_id, user_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            trade.id,
                            trade.symbol,
                            trade.token_mint,
                            trade.side,
                            trade.amount_sol,
                            trade.amount_tokens,
                            trade.price,
                            trade.timestamp,
                            trade.tx_signature,
                            trade.position_id,
                            trade.user_id,
                        ),
                    )

                conn.execute("DELETE FROM treasury_orders")
                for order_id, order_data in self.orders.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO treasury_orders (order_id, order_json) VALUES (?, ?)",
                        (order_id, json.dumps(order_data)),
                    )

                conn.execute(
                    """
                    UPDATE scorecard SET
                        total_trades = ?,
                        winning_trades = ?,
                        losing_trades = ?,
                        total_pnl_sol = ?,
                        total_pnl_usd = ?,
                        largest_win_sol = ?,
                        largest_loss_sol = ?,
                        current_streak = ?,
                        best_streak = ?,
                        worst_streak = ?,
                        avg_win_pct = ?,
                        avg_loss_pct = ?,
                        win_rate = ?,
                        last_updated = ?
                    WHERE id = 1
                    """,
                    (
                        self.scorecard.total_trades,
                        self.scorecard.winning_trades,
                        self.scorecard.losing_trades,
                        self.scorecard.total_pnl_sol,
                        self.scorecard.total_pnl_usd,
                        self.scorecard.largest_win_sol,
                        self.scorecard.largest_loss_sol,
                        self.scorecard.current_streak,
                        self.scorecard.best_streak,
                        self.scorecard.worst_streak,
                        self.scorecard.avg_win_pct,
                        self.scorecard.avg_loss_pct,
                        self.scorecard.win_rate,
                        self.scorecard.last_updated,
                    ),
                )

                # Commit the transaction atomically
                conn.commit()

                # Checkpoint WAL to ensure data is written to main database
                # This prevents unbounded WAL growth and ensures durability
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

            except Exception as e:
                # Rollback on any error
                conn.rollback()
                raise

        except Exception as e:
            logger.error(f"Failed to save scorekeeper to SQLite: {e}")
        finally:
            if conn:
                conn.close()

    def open_position(
        self,
        position_id: str,
        symbol: str,
        token_mint: str,
        entry_price: float,
        entry_amount_sol: float,
        entry_amount_tokens: float,
        take_profit_price: float,
        stop_loss_price: float,
        tp_order_id: str = "",
        sl_order_id: str = "",
        tx_signature: str = "",
        user_id: int = 0,
    ) -> Position:
        """Record a new position."""
        position = Position(
            id=position_id,
            symbol=symbol,
            token_mint=token_mint,
            entry_price=entry_price,
            entry_amount_sol=entry_amount_sol,
            entry_amount_tokens=entry_amount_tokens,
            take_profit_price=take_profit_price,
            stop_loss_price=stop_loss_price,
            tp_order_id=tp_order_id,
            sl_order_id=sl_order_id,
            status="open",
            opened_at=datetime.now(timezone.utc).isoformat(),
            tx_signature_entry=tx_signature,
            user_id=user_id,
        )

        self.positions[position_id] = position

        # Record the buy trade
        trade = TradeRecord(
            id=f"buy_{position_id}",
            symbol=symbol,
            token_mint=token_mint,
            side="buy",
            amount_sol=entry_amount_sol,
            amount_tokens=entry_amount_tokens,
            price=entry_price,
            timestamp=position.opened_at,
            tx_signature=tx_signature,
            position_id=position_id,
            user_id=user_id,
        )
        self.trades.append(trade)
        self.scorecard.total_trades += 1

        self._save()
        logger.info(f"Opened position {position_id}: {symbol} @ ${entry_price}")
        return position

    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_amount_sol: float,
        close_type: str = "manual",  # "tp", "sl", "manual"
        tx_signature: str = "",
    ) -> Optional[Position]:
        """Close a position and calculate P&L."""
        if position_id not in self.positions:
            logger.error(f"Position {position_id} not found")
            return None

        position = self.positions[position_id]
        if position.status != "open":
            logger.warning(f"Position {position_id} already closed")
            return position

        # Calculate P&L
        position.exit_price = exit_price
        position.exit_amount_sol = exit_amount_sol
        position.pnl_sol = exit_amount_sol - position.entry_amount_sol
        position.pnl_pct = (position.pnl_sol / position.entry_amount_sol * 100) if position.entry_amount_sol > 0 else 0
        position.closed_at = datetime.now(timezone.utc).isoformat()
        position.tx_signature_exit = tx_signature

        # Set status based on close type
        if close_type == "tp":
            position.status = "closed_tp"
        elif close_type == "sl":
            position.status = "closed_sl"
        else:
            position.status = "closed_manual"

        # Update scorecard
        self._update_scorecard(position)

        # Record the sell trade
        trade = TradeRecord(
            id=f"sell_{position_id}",
            symbol=position.symbol,
            token_mint=position.token_mint,
            side="sell",
            amount_sol=exit_amount_sol,
            amount_tokens=position.entry_amount_tokens,
            price=exit_price,
            timestamp=position.closed_at,
            tx_signature=tx_signature,
            position_id=position_id,
            user_id=position.user_id,
        )
        self.trades.append(trade)
        self.scorecard.total_trades += 1

        self._save()
        logger.info(
            f"Closed position {position_id}: {position.symbol} "
            f"P&L: {position.pnl_sol:+.4f} SOL ({position.pnl_pct:+.1f}%)"
        )

        # Extract learnings from this trade for future picks
        try:
            learnings = self.extract_learnings_from_closed_position(position)
            if learnings:
                logger.info(f"Extracted {len(learnings)} learnings from {position.symbol}")
        except Exception as e:
            logger.warning(f"Failed to extract learnings: {e}")

        return position

    def _update_scorecard(self, position: Position):
        """Update scorecard with closed position."""
        is_win = position.pnl_sol > 0

        if is_win:
            self.scorecard.winning_trades += 1
            if position.pnl_sol > self.scorecard.largest_win_sol:
                self.scorecard.largest_win_sol = position.pnl_sol

            if self.scorecard.current_streak >= 0:
                self.scorecard.current_streak += 1
            else:
                self.scorecard.current_streak = 1

            if self.scorecard.current_streak > self.scorecard.best_streak:
                self.scorecard.best_streak = self.scorecard.current_streak
        else:
            self.scorecard.losing_trades += 1
            if position.pnl_sol < self.scorecard.largest_loss_sol:
                self.scorecard.largest_loss_sol = position.pnl_sol

            if self.scorecard.current_streak <= 0:
                self.scorecard.current_streak -= 1
            else:
                self.scorecard.current_streak = -1

            if self.scorecard.current_streak < self.scorecard.worst_streak:
                self.scorecard.worst_streak = self.scorecard.current_streak

        self.scorecard.total_pnl_sol += position.pnl_sol

        # Calculate win rate
        total_closed = self.scorecard.winning_trades + self.scorecard.losing_trades
        if total_closed > 0:
            self.scorecard.win_rate = self.scorecard.winning_trades / total_closed * 100

        self.scorecard.last_updated = datetime.now(timezone.utc).isoformat()

    def save_order(self, order_id: str, order_data: Dict):
        """Save a TP/SL order for persistence."""
        self.orders[order_id] = order_data
        self._save()

    def remove_order(self, order_id: str):
        """Remove a completed/cancelled order."""
        if order_id in self.orders:
            del self.orders[order_id]
            self._save()

    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.status == "open"]

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a position by ID."""
        return self.positions.get(position_id)

    def get_position_by_token(self, token_mint: str) -> Optional[Position]:
        """Get open position for a token."""
        for pos in self.positions.values():
            if pos.token_mint == token_mint and pos.status == "open":
                return pos
        return None

    def sync_from_treasury_positions(self, treasury_positions: List[Dict]) -> int:
        """
        Sync positions from TreasuryTrader's .positions.json into scorekeeper.

        This ensures open positions with stop losses/take profits are visible
        in the Telegram dashboard.

        Args:
            treasury_positions: List of position dicts from trading.py

        Returns:
            Number of positions synced
        """
        synced_count = 0
        try:
            for pos_data in treasury_positions:
                # Only sync OPEN positions
                if pos_data.get("status") != "OPEN":
                    continue

                pos_id = pos_data.get("id")
                token_mint = pos_data.get("token_mint")

                # Skip if already in scorekeeper
                if pos_id in self.positions:
                    continue

                # Convert treasury position format to scorekeeper Position
                pos = Position(
                    id=pos_id,
                    symbol=pos_data.get("token_symbol", "UNKNOWN"),
                    token_mint=token_mint,
                    entry_price=pos_data.get("entry_price", 0.0),
                    entry_amount_sol=pos_data.get("amount_usd", 0.0) / 100.0,  # Approximate SOL value
                    entry_amount_tokens=pos_data.get("amount", 0.0),
                    take_profit_price=pos_data.get("take_profit_price", 0.0),
                    stop_loss_price=pos_data.get("stop_loss_price", 0.0),
                    tp_order_id=pos_data.get("tp_order_id", ""),
                    sl_order_id=pos_data.get("sl_order_id", ""),
                    status="open",
                    opened_at=pos_data.get("opened_at", datetime.now(timezone.utc).isoformat()),
                )

                self.positions[pos_id] = pos
                synced_count += 1
                logger.info(f"Synced position: {pos.symbol} ({pos.id})")

            # Save after syncing
            if synced_count > 0:
                self._save()
                logger.info(f"Synced {synced_count} positions from treasury")

        except Exception as e:
            logger.error(f"Failed to sync treasury positions: {e}")

        return synced_count

    def get_positions_by_token(self, token_mint: str) -> List[Position]:
        """Get open positions for a token."""
        return [
            pos for pos in self.positions.values()
            if pos.token_mint == token_mint and pos.status == "open"
        ]

    def get_recent_trades(self, limit: int = 20) -> List[TradeRecord]:
        """Get recent trades."""
        return sorted(self.trades, key=lambda t: t.timestamp, reverse=True)[:limit]

    def get_scorecard(self) -> ScoreCard:
        """Get current scorecard."""
        return self.scorecard

    def get_summary(self) -> Dict[str, Any]:
        """Get comprehensive summary."""
        open_positions = self.get_open_positions()

        return {
            "open_positions": len(open_positions),
            "total_trades": self.scorecard.total_trades,
            "winning_trades": self.scorecard.winning_trades,
            "losing_trades": self.scorecard.losing_trades,
            "win_rate": f"{self.scorecard.win_rate:.1f}%",
            "total_pnl_sol": f"{self.scorecard.total_pnl_sol:+.4f}",
            "largest_win": f"{self.scorecard.largest_win_sol:+.4f}",
            "largest_loss": f"{self.scorecard.largest_loss_sol:+.4f}",
            "current_streak": self.scorecard.current_streak,
            "best_streak": self.scorecard.best_streak,
            "worst_streak": self.scorecard.worst_streak,
            "positions": [
                {
                    "id": p.id,
                    "symbol": p.symbol,
                    "entry": f"${p.entry_price:.6f}",
                    "tp": f"${p.take_profit_price:.6f}",
                    "sl": f"${p.stop_loss_price:.6f}",
                    "amount_sol": f"{p.entry_amount_sol:.4f}",
                }
                for p in open_positions
            ],
        }

    def format_telegram_summary(self) -> str:
        """Format summary for Telegram."""
        summary = self.get_summary()
        open_pos = self.get_open_positions()

        lines = [
            "<b>TREASURY SCORECARD</b>",
            "",
            f"Total Trades: <code>{summary['total_trades']}</code>",
            f"Win Rate: <code>{summary['win_rate']}</code>",
            f"Total P&L: <code>{summary['total_pnl_sol']} SOL</code>",
            "",
            f"Wins: <code>{summary['winning_trades']}</code> | Losses: <code>{summary['losing_trades']}</code>",
            f"Largest Win: <code>{summary['largest_win']} SOL</code>",
            f"Largest Loss: <code>{summary['largest_loss']} SOL</code>",
            f"Current Streak: <code>{summary['current_streak']}</code>",
            "",
            f"<b>Open Positions ({len(open_pos)})</b>",
        ]

        for pos in open_pos:
            lines.append(
                f"- {pos.symbol}: {pos.entry_amount_sol:.4f} SOL @ ${pos.entry_price:.6f}"
            )

        return "\n".join(lines)


    def get_telegram_dashboard(self, balance_sol: float = 0.0, sol_price: float = 100.0) -> Dict[str, Any]:
        """
        Get comprehensive dashboard data for Telegram display.

        Returns dict with:
        - header: Treasury status header
        - positions_table: Open positions formatted table
        - recent_trades: List of recent trade results
        - stats_footer: Performance stats
        """
        open_positions = self.get_open_positions()
        closed_positions = [p for p in self.positions.values() if p.status != "open"]

        # Get recent closed trades (last 5)
        recent_closed = sorted(
            closed_positions,
            key=lambda p: p.closed_at or "",
            reverse=True
        )[:5]

        # Calculate streak display
        if self.scorecard.current_streak > 0:
            streak_display = f"🔥{self.scorecard.current_streak} wins"
        elif self.scorecard.current_streak < 0:
            streak_display = f"❄️{abs(self.scorecard.current_streak)} losses"
        else:
            streak_display = "—"

        return {
            # Header section
            "balance_sol": balance_sol,
            "balance_usd": balance_sol * sol_price,
            "win_rate": self.scorecard.win_rate,
            "wins": self.scorecard.winning_trades,
            "losses": self.scorecard.losing_trades,
            "current_streak": self.scorecard.current_streak,
            "streak_display": streak_display,
            "best_streak": self.scorecard.best_streak,
            "worst_streak": self.scorecard.worst_streak,

            # Open positions
            "open_positions": [
                {
                    "symbol": p.symbol,
                    "side": "LONG",
                    "entry_price": p.entry_price,
                    "entry_sol": p.entry_amount_sol,
                    "tp_price": p.take_profit_price,
                    "sl_price": p.stop_loss_price,
                    "opened_at": p.opened_at,
                }
                for p in open_positions
            ],

            # Recent trades
            "recent_trades": [
                {
                    "symbol": p.symbol,
                    "pnl_pct": p.pnl_pct,
                    "pnl_sol": p.pnl_sol,
                    "exit_reason": p.status.replace("closed_", "").upper(),
                    "is_win": p.pnl_sol > 0,
                }
                for p in recent_closed
            ],

            # Stats footer
            "total_pnl_sol": self.scorecard.total_pnl_sol,
            "total_pnl_usd": self.scorecard.total_pnl_sol * sol_price,
            "largest_win_sol": self.scorecard.largest_win_sol,
            "largest_loss_sol": self.scorecard.largest_loss_sol,
            "total_trades": self.scorecard.total_trades,
        }

    def format_telegram_dashboard_html(self, balance_sol: float = 0.0, sol_price: float = 100.0) -> str:
        """
        Format a beautiful HTML dashboard for Telegram.

        Returns multi-line HTML string ready for Telegram.
        """
        data = self.get_telegram_dashboard(balance_sol, sol_price)

        lines = []

        # ═══════════════════════════════════
        # HEADER
        # ═══════════════════════════════════
        lines.append("💰 <b>TREASURY STATUS</b>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"Balance: <code>{data['balance_sol']:.4f} SOL</code> (~${data['balance_usd']:,.2f})")
        lines.append(f"Win Rate: <code>{data['win_rate']:.1f}%</code> (W/L: {data['wins']}/{data['losses']})")
        lines.append(f"Streak: {data['streak_display']}")
        lines.append(f"Best: {data['best_streak']} | Worst: {data['worst_streak']}")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")

        # ═══════════════════════════════════
        # OPEN POSITIONS
        # ═══════════════════════════════════
        open_pos = data["open_positions"]
        lines.append(f"📊 <b>OPEN POSITIONS</b> ({len(open_pos)} active)")

        if open_pos:
            lines.append("<pre>")
            lines.append("Token    │ Entry      │ Size")
            lines.append("─────────┼────────────┼──────────")
            for pos in open_pos[:15]:  # Show top 15 positions
                symbol = pos["symbol"][:8].ljust(8)
                entry = f"${pos['entry_price']:.6f}"[:10].ljust(10)
                size = f"{pos['entry_sol']:.4f}"
                lines.append(f"{symbol} │ {entry} │ {size}")
            lines.append("</pre>")
            lines.append("<i>All positions have TP/SL active</i>")
        else:
            lines.append("<i>No active positions. Ready to deploy.</i>")

        lines.append("")

        # ═══════════════════════════════════
        # RECENT TRADES
        # ═══════════════════════════════════
        recent = data["recent_trades"]
        if recent:
            lines.append("📈 <b>RECENT TRADES</b>")
            for trade in recent:
                emoji = "✅" if trade["is_win"] else "❌"
                reason = trade["exit_reason"]
                reason_tag = f"({reason})" if reason in ("TP", "SL") else ""
                lines.append(
                    f"• {trade['symbol']}: <code>{trade['pnl_pct']:+.1f}%</code> {emoji} {reason_tag}"
                )
            lines.append("")

        # ═══════════════════════════════════
        # STATS FOOTER
        # ═══════════════════════════════════
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━")
        pnl_emoji = "📈" if data["total_pnl_sol"] >= 0 else "📉"
        lines.append(f"All-Time P&L: {pnl_emoji} <code>{data['total_pnl_sol']:+.6f} SOL</code>")
        if data["largest_win_sol"] > 0:
            lines.append(f"Largest Win: <code>{data['largest_win_sol']:+.6f} SOL</code>")
        if data["largest_loss_sol"] < 0:
            lines.append(f"Largest Loss: <code>{data['largest_loss_sol']:+.6f} SOL</code>")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━")

        return "\n".join(lines)


    # =========================================================================
    # PICK PERFORMANCE TRACKING
    # =========================================================================

    def save_pick(
        self,
        symbol: str,
        asset_class: str,
        contract: str,
        conviction_score: int,
        entry_price: float,
        target_price: float,
        stop_loss: float,
        timeframe: str,
        reasoning: str = "",
    ) -> bool:
        """
        Save a conviction pick to track its performance over time.

        Called when Grok generates a pick - tracks whether our predictions work.
        """
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO pick_performance (
                        pick_date, symbol, asset_class, contract, conviction_score,
                        entry_price, target_price, stop_loss, timeframe, reasoning,
                        current_price, max_price, min_price, pnl_pct, max_gain_pct,
                        hit_target, hit_stop, outcome, days_held, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 'open', 0, ?)
                """, (
                    datetime.now(timezone.utc).isoformat(),
                    symbol, asset_class, contract, conviction_score,
                    entry_price, target_price, stop_loss, timeframe, reasoning,
                    entry_price, entry_price, entry_price,
                    datetime.now(timezone.utc).isoformat()
                ))
            logger.info(f"Saved pick: {symbol} (conviction={conviction_score})")
            return True
        except Exception as e:
            logger.error(f"Failed to save pick: {e}")
            return False

    def update_pick_performance(
        self,
        symbol: str,
        current_price: float,
        outcome: str = None,
    ) -> bool:
        """
        Update a pick's performance based on current price.

        Called periodically to track max/min prices and check TP/SL hits.
        """
        try:
            with self._get_conn() as conn:
                # Get existing pick - optimized query
                row = conn.execute("""
                    SELECT id, pick_date, symbol, asset_class, contract, conviction_score,
                           entry_price, target_price, stop_loss, timeframe, current_price,
                           max_price, min_price, pnl_pct, max_gain_pct, hit_target, hit_stop,
                           outcome, last_updated, reasoning, days_held
                    FROM pick_performance
                    WHERE symbol = ? AND outcome = 'open'
                    ORDER BY pick_date DESC LIMIT 1
                """, (symbol,)).fetchone()

                if not row:
                    return False

                entry_price = row['entry_price']
                target_price = row['target_price']
                stop_loss_price = row['stop_loss']
                max_price = max(row['max_price'] or current_price, current_price)
                min_price = min(row['min_price'] or current_price, current_price)
                pnl_pct = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                max_gain_pct = ((max_price - entry_price) / entry_price * 100) if entry_price > 0 else 0

                hit_target = 1 if current_price >= target_price else 0
                hit_stop = 1 if current_price <= stop_loss_price else 0

                # Determine outcome
                if outcome:
                    final_outcome = outcome
                elif hit_target:
                    final_outcome = "win_tp"
                elif hit_stop:
                    final_outcome = "loss_sl"
                else:
                    final_outcome = "open"

                # Calculate days held
                pick_date = datetime.fromisoformat(row['pick_date'].replace('Z', '+00:00'))
                days_held = (datetime.now(timezone.utc) - pick_date).days

                conn.execute("""
                    UPDATE pick_performance SET
                        current_price = ?, max_price = ?, min_price = ?,
                        pnl_pct = ?, max_gain_pct = ?, hit_target = ?, hit_stop = ?,
                        outcome = ?, days_held = ?, last_updated = ?
                    WHERE id = ?
                """, (
                    current_price, max_price, min_price, pnl_pct, max_gain_pct,
                    hit_target, hit_stop, final_outcome, days_held,
                    datetime.now(timezone.utc).isoformat(), row['id']
                ))

            return True
        except Exception as e:
            logger.error(f"Failed to update pick performance: {e}")
            return False

    def get_historical_performance(self, asset_class: str = None) -> Dict[str, Any]:
        """
        Get historical performance metrics for improving future picks.

        Returns win rates, average gains/losses, best timeframes, etc.
        """
        try:
            with self._get_conn() as conn:
                # Optimized pick_performance queries
                columns = """id, pick_date, symbol, asset_class, contract, conviction_score,
                            entry_price, target_price, stop_loss, timeframe, current_price,
                            max_price, min_price, pnl_pct, max_gain_pct, hit_target, hit_stop,
                            outcome, last_updated, reasoning, days_held"""
                if asset_class:
                    rows = conn.execute(f"""
                        SELECT {columns}
                        FROM pick_performance
                        WHERE asset_class = ? AND outcome != 'open'
                    """, (asset_class,)).fetchall()
                else:
                    rows = conn.execute(f"""
                        SELECT {columns}
                        FROM pick_performance WHERE outcome != 'open'
                    """).fetchall()

            if not rows:
                return {"total_picks": 0, "win_rate": 0, "message": "no closed picks yet"}

            wins = [r for r in rows if 'win' in (r['outcome'] or '')]
            losses = [r for r in rows if 'loss' in (r['outcome'] or '')]

            total = len(rows)
            win_rate = len(wins) / total * 100 if total > 0 else 0
            avg_gain = sum(r['pnl_pct'] or 0 for r in wins) / len(wins) if wins else 0
            avg_loss = sum(r['pnl_pct'] or 0 for r in losses) / len(losses) if losses else 0
            avg_max_gain = sum(r['max_gain_pct'] or 0 for r in rows) / total if total > 0 else 0

            # Conviction correlation
            high_conv_wins = len([r for r in wins if (r['conviction_score'] or 0) >= 70])
            high_conv_total = len([r for r in rows if (r['conviction_score'] or 0) >= 70])
            high_conv_win_rate = high_conv_wins / high_conv_total * 100 if high_conv_total > 0 else 0

            return {
                "total_picks": total,
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(win_rate, 1),
                "avg_gain_pct": round(avg_gain, 1),
                "avg_loss_pct": round(avg_loss, 1),
                "avg_max_gain_pct": round(avg_max_gain, 1),
                "high_conviction_win_rate": round(high_conv_win_rate, 1),
            }
        except Exception as e:
            logger.error(f"Failed to get historical performance: {e}")
            return {"error": str(e)}

    # =========================================================================
    # TRADE LEARNING EXTRACTION
    # =========================================================================

    def extract_learnings_from_closed_position(self, position: Position) -> List[Dict]:
        """
        Analyze a closed position and extract learnings for future trades.

        Patterns we detect:
        - Win patterns: What worked (timeframe, conviction, asset type)
        - Loss patterns: What failed (too aggressive TP, too tight SL)
        - Token type patterns: Which categories perform better
        """
        learnings = []
        try:
            is_win = position.pnl_sol > 0
            pnl_pct = position.pnl_pct

            # Determine token type
            symbol = position.symbol.upper()
            if symbol.endswith('X') and any(symbol.startswith(s) for s in ['SPY', 'QQQ', 'TQQQ', 'GLD', 'NVDA', 'AAPL', 'TSLA', 'MSFT']):
                token_type = "XSTOCK"
            elif position.entry_amount_sol < 0.1:
                token_type = "MICRO"
            else:
                token_type = "MEME"

            # Learning type
            if is_win:
                learning_type = "WIN_PATTERN"
                if position.status == "closed_tp":
                    insight = f"{symbol} hit TP at +{pnl_pct:.1f}%. {token_type} can work with tight targets."
                else:
                    insight = f"{symbol} manual close at +{pnl_pct:.1f}%. Consider setting earlier TPs for {token_type}."
            else:
                learning_type = "LOSS_PATTERN"
                if position.status == "closed_sl":
                    insight = f"{symbol} hit SL at {pnl_pct:.1f}%. {token_type} may need wider stops or lower position sizes."
                else:
                    insight = f"{symbol} manual close at {pnl_pct:.1f}%. Cut losses faster on {token_type}."

            # Calculate TP/SL ratios
            if position.entry_price > 0:
                tp_pct = ((position.take_profit_price - position.entry_price) / position.entry_price) * 100
                sl_pct = ((position.stop_loss_price - position.entry_price) / position.entry_price) * 100

                if is_win and tp_pct > 20:
                    learnings.append({
                        "type": "TP_CALIBRATION",
                        "insight": f"High TP ({tp_pct:.0f}%) worked for {symbol}. {token_type} can handle aggressive targets.",
                        "confidence": 0.7,
                    })
                elif not is_win and abs(sl_pct) < 10:
                    learnings.append({
                        "type": "SL_CALIBRATION",
                        "insight": f"Tight SL ({sl_pct:.0f}%) triggered on {symbol}. {token_type} may need 10-15% SL.",
                        "confidence": 0.8,
                    })

            learnings.append({
                "type": learning_type,
                "token_type": token_type,
                "insight": insight,
                "confidence": 0.8 if is_win else 0.6,
            })

            # Save to database
            self._save_learnings(position.id, symbol, token_type, learnings)

        except Exception as e:
            logger.error(f"Failed to extract learnings: {e}")

        return learnings

    def _save_learnings(self, trade_id: str, symbol: str, token_type: str, learnings: List[Dict]):
        """Save extracted learnings to database."""
        try:
            with self._get_conn() as conn:
                for learning in learnings:
                    conn.execute("""
                        INSERT INTO trade_learnings (
                            trade_id, token_symbol, token_type, learning_type,
                            insight, confidence, applied_count, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
                    """, (
                        trade_id, symbol, token_type, learning['type'],
                        learning['insight'], learning['confidence'],
                        datetime.now(timezone.utc).isoformat()
                    ))
        except Exception as e:
            logger.error(f"Failed to save learnings: {e}")

    def get_learnings_for_context(self, token_type: str = None, limit: int = 5) -> str:
        """
        Get relevant learnings formatted for inclusion in Grok prompts.

        Returns a string that can be injected into conviction analysis prompts.
        """
        try:
            with self._get_conn() as conn:
                # Optimized trade_learnings queries
                columns = "id, trade_id, token_symbol, token_type, learning_type, insight, confidence, applied_count, created_at"
                if token_type:
                    rows = conn.execute(f"""
                        SELECT {columns}
                        FROM trade_learnings
                        WHERE token_type = ?
                        ORDER BY confidence DESC, created_at DESC
                        LIMIT ?
                    """, (token_type, limit)).fetchall()
                else:
                    rows = conn.execute(f"""
                        SELECT {columns}
                        FROM trade_learnings
                        ORDER BY confidence DESC, created_at DESC
                        LIMIT ?
                    """, (limit,)).fetchall()

            if not rows:
                return ""

            context_lines = ["HISTORICAL LEARNINGS (from past trades):"]
            for r in rows:
                context_lines.append(f"- [{r['token_type']}] {r['insight']}")

            return "\n".join(context_lines)

        except Exception as e:
            logger.error(f"Failed to get learnings context: {e}")
            return ""

    def get_performance_summary(self) -> str:
        """Get a brief performance summary for display."""
        try:
            perf = self.get_historical_performance()
            if perf.get('total_picks', 0) == 0:
                return "no picks tracked yet - building baseline"

            return (
                f"picks: {perf['total_picks']} | "
                f"win rate: {perf['win_rate']}% | "
                f"avg gain: +{perf['avg_gain_pct']}% | "
                f"avg loss: {perf['avg_loss_pct']}%"
            )
        except Exception as e:
            return f"performance unavailable: {e}"

    def get_open_picks(self) -> List[Dict]:
        """Get all open picks that need price updates."""
        try:
            with self._get_conn() as conn:
                # Optimized query for open picks
                rows = conn.execute("""
                    SELECT id, pick_date, symbol, asset_class, contract, conviction_score,
                           entry_price, target_price, stop_loss, timeframe, current_price,
                           max_price, min_price, pnl_pct, max_gain_pct, hit_target, hit_stop,
                           outcome, last_updated, reasoning, days_held
                    FROM pick_performance WHERE outcome = 'open'
                """).fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to get open picks: {e}")
            return []

    async def update_all_open_picks(self) -> Dict[str, int]:
        """
        Batch update all open picks with current prices.

        Returns dict with counts of updated/closed picks.
        """
        results = {"updated": 0, "closed_tp": 0, "closed_sl": 0, "expired": 0, "errors": 0}

        try:
            from core.data.free_price_api import get_token_price

            open_picks = self.get_open_picks()
            if not open_picks:
                return results

            for pick in open_picks:
                try:
                    symbol = pick['symbol']
                    contract = pick.get('contract', '')

                    # Try to get current price
                    current_price = 0.0
                    if contract:
                        try:
                            current_price = await get_token_price(contract)
                        except Exception:
                            pass

                    if current_price <= 0:
                        # Skip if we can't get price
                        continue

                    # Check for expired picks (beyond timeframe)
                    days_held = pick.get('days_held', 0)
                    timeframe = pick.get('timeframe', 'short')
                    max_days = {"short": 7, "medium": 28, "long": 90}.get(timeframe, 14)

                    if days_held > max_days:
                        # Expire the pick
                        self.update_pick_performance(symbol, current_price, outcome="expired")
                        results["expired"] += 1
                        continue

                    # Update with current price
                    self.update_pick_performance(symbol, current_price)

                    # Check if TP or SL was hit
                    if current_price >= pick['target_price']:
                        results["closed_tp"] += 1
                    elif current_price <= pick['stop_loss']:
                        results["closed_sl"] += 1
                    else:
                        results["updated"] += 1

                except Exception as e:
                    logger.debug(f"Error updating pick {pick.get('symbol', '?')}: {e}")
                    results["errors"] += 1

        except Exception as e:
            logger.error(f"Batch pick update failed: {e}")

        return results

    def get_calibration_stats(self) -> Dict[str, Any]:
        """
        Get TP/SL calibration stats for improving future recommendations.

        Analyzes closed picks to see if TP/SL levels were appropriate.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute("""
                    SELECT * FROM pick_performance WHERE outcome != 'open'
                """).fetchall()

            if not rows:
                return {"message": "not enough data yet"}

            stats = {
                "total_closed": len(rows),
                "tp_hits": 0,
                "sl_hits": 0,
                "expired": 0,
                "avg_max_gain_before_sl": 0.0,
                "avg_pnl_at_tp": 0.0,
                "optimal_tp_suggestion": "",
                "optimal_sl_suggestion": "",
            }

            tp_gains = []
            sl_max_gains = []

            for r in rows:
                outcome = r['outcome'] or ''
                if 'win' in outcome or r.get('hit_target'):
                    stats["tp_hits"] += 1
                    if r.get('pnl_pct'):
                        tp_gains.append(r['pnl_pct'])
                elif 'loss' in outcome or r.get('hit_stop'):
                    stats["sl_hits"] += 1
                    # Track max gain before SL - shows if TP was too aggressive
                    if r.get('max_gain_pct'):
                        sl_max_gains.append(r['max_gain_pct'])
                elif 'expired' in outcome:
                    stats["expired"] += 1

            if tp_gains:
                stats["avg_pnl_at_tp"] = round(sum(tp_gains) / len(tp_gains), 1)
            if sl_max_gains:
                stats["avg_max_gain_before_sl"] = round(sum(sl_max_gains) / len(sl_max_gains), 1)
                # If we're seeing gains before SL, we might be setting TP too high
                if stats["avg_max_gain_before_sl"] > 5:
                    stats["optimal_tp_suggestion"] = f"Consider tighter TPs around +{stats['avg_max_gain_before_sl']:.0f}%"
                    stats["optimal_sl_suggestion"] = "Current SL levels seem okay"

            return stats
        except Exception as e:
            logger.error(f"Failed to get calibration stats: {e}")
            return {"error": str(e)}


# Singleton accessor
def get_scorekeeper() -> Scorekeeper:
    """Get the scorekeeper singleton."""
    return Scorekeeper()
