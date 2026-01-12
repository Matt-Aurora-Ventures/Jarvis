"""
PnL Tracker - Track profit and loss across positions.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    """Position status."""
    OPEN = "open"
    CLOSED = "closed"
    PARTIALLY_CLOSED = "partially_closed"


class TradeType(Enum):
    """Trade type."""
    SPOT = "spot"
    PERP = "perp"
    MARGIN = "margin"


@dataclass
class Position:
    """A trading position."""
    id: str
    symbol: str
    side: str  # "long" or "short"
    trade_type: TradeType
    entry_price: float
    current_price: float
    quantity: float
    entry_value: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    realized_pnl: float
    fees_paid: float
    status: PositionStatus
    opened_at: str
    closed_at: Optional[str] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    notes: str = ""


@dataclass
class Trade:
    """A single trade."""
    id: str
    position_id: str
    symbol: str
    side: str  # "buy" or "sell"
    price: float
    quantity: float
    value: float
    fee: float
    timestamp: str
    tx_signature: Optional[str] = None


@dataclass
class PnLSummary:
    """PnL summary statistics."""
    period: str
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    total_fees: float
    net_pnl: float
    win_count: int
    loss_count: int
    win_rate: float
    avg_win: float
    avg_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float
    total_volume: float
    roi_pct: float


@dataclass
class DailyPnL:
    """Daily PnL record."""
    date: str
    starting_balance: float
    ending_balance: float
    realized_pnl: float
    unrealized_pnl: float
    fees: float
    trades_count: int
    volume: float


class PnLTrackerDB:
    """SQLite storage for PnL data."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS positions (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    side TEXT,
                    trade_type TEXT,
                    entry_price REAL,
                    current_price REAL,
                    quantity REAL,
                    entry_value REAL,
                    current_value REAL,
                    unrealized_pnl REAL,
                    unrealized_pnl_pct REAL,
                    realized_pnl REAL,
                    fees_paid REAL,
                    status TEXT,
                    opened_at TEXT,
                    closed_at TEXT,
                    stop_loss REAL,
                    take_profit REAL,
                    notes TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    position_id TEXT,
                    symbol TEXT NOT NULL,
                    side TEXT,
                    price REAL,
                    quantity REAL,
                    value REAL,
                    fee REAL,
                    timestamp TEXT,
                    tx_signature TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_pnl (
                    date TEXT PRIMARY KEY,
                    starting_balance REAL,
                    ending_balance REAL,
                    realized_pnl REAL,
                    unrealized_pnl REAL,
                    fees REAL,
                    trades_count INTEGER,
                    volume REAL
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS balance_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    total_balance REAL,
                    available_balance REAL,
                    in_positions REAL,
                    unrealized_pnl REAL
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(timestamp)")

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


class PnLTracker:
    """
    Track profit and loss across positions.

    Usage:
        tracker = PnLTracker()

        # Open position
        position = tracker.open_position(
            symbol="SOL",
            side="long",
            entry_price=100.0,
            quantity=10
        )

        # Update price
        tracker.update_price("SOL", 110.0)

        # Close position
        tracker.close_position(position.id, exit_price=110.0)

        # Get summary
        summary = tracker.get_pnl_summary("7d")
    """

    def __init__(self, db_path: Optional[Path] = None):
        db_path = db_path or Path(__file__).parent.parent / "data" / "pnl.db"
        self.db = PnLTrackerDB(db_path)
        self._positions: Dict[str, Position] = {}
        self._prices: Dict[str, float] = {}
        self._starting_balance: float = 0
        self._load_positions()

    def _load_positions(self):
        """Load open positions from database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM positions WHERE status = 'open'")

            for row in cursor.fetchall():
                position = Position(
                    id=row['id'],
                    symbol=row['symbol'],
                    side=row['side'],
                    trade_type=TradeType(row['trade_type']),
                    entry_price=row['entry_price'],
                    current_price=row['current_price'],
                    quantity=row['quantity'],
                    entry_value=row['entry_value'],
                    current_value=row['current_value'],
                    unrealized_pnl=row['unrealized_pnl'],
                    unrealized_pnl_pct=row['unrealized_pnl_pct'],
                    realized_pnl=row['realized_pnl'],
                    fees_paid=row['fees_paid'],
                    status=PositionStatus(row['status']),
                    opened_at=row['opened_at'],
                    closed_at=row['closed_at'],
                    stop_loss=row['stop_loss'],
                    take_profit=row['take_profit'],
                    notes=row['notes'] or ""
                )
                self._positions[position.id] = position

        logger.info(f"Loaded {len(self._positions)} open positions")

    def open_position(
        self,
        symbol: str,
        side: str,
        entry_price: float,
        quantity: float,
        trade_type: TradeType = TradeType.SPOT,
        fee: float = 0,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        notes: str = "",
        tx_signature: str = ""
    ) -> Position:
        """Open a new position."""
        import uuid
        position_id = str(uuid.uuid4())[:8]
        trade_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        entry_value = entry_price * quantity

        position = Position(
            id=position_id,
            symbol=symbol.upper(),
            side=side,
            trade_type=trade_type,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            entry_value=entry_value,
            current_value=entry_value,
            unrealized_pnl=0,
            unrealized_pnl_pct=0,
            realized_pnl=0,
            fees_paid=fee,
            status=PositionStatus.OPEN,
            opened_at=now,
            stop_loss=stop_loss,
            take_profit=take_profit,
            notes=notes
        )

        # Record trade
        trade = Trade(
            id=trade_id,
            position_id=position_id,
            symbol=symbol.upper(),
            side="buy" if side == "long" else "sell",
            price=entry_price,
            quantity=quantity,
            value=entry_value,
            fee=fee,
            timestamp=now,
            tx_signature=tx_signature
        )

        self._save_position(position)
        self._save_trade(trade)

        self._positions[position_id] = position

        logger.info(f"Opened {side} position {position_id}: {quantity} {symbol} @ {entry_price}")

        return position

    def _save_position(self, position: Position):
        """Save position to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO positions
                (id, symbol, side, trade_type, entry_price, current_price,
                 quantity, entry_value, current_value, unrealized_pnl,
                 unrealized_pnl_pct, realized_pnl, fees_paid, status,
                 opened_at, closed_at, stop_loss, take_profit, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.id, position.symbol, position.side, position.trade_type.value,
                position.entry_price, position.current_price, position.quantity,
                position.entry_value, position.current_value, position.unrealized_pnl,
                position.unrealized_pnl_pct, position.realized_pnl, position.fees_paid,
                position.status.value, position.opened_at, position.closed_at,
                position.stop_loss, position.take_profit, position.notes
            ))
            conn.commit()

    def _save_trade(self, trade: Trade):
        """Save trade to database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades
                (id, position_id, symbol, side, price, quantity, value, fee, timestamp, tx_signature)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.id, trade.position_id, trade.symbol, trade.side,
                trade.price, trade.quantity, trade.value, trade.fee,
                trade.timestamp, trade.tx_signature
            ))
            conn.commit()

    def update_price(self, symbol: str, price: float):
        """Update price for a symbol."""
        symbol = symbol.upper()
        self._prices[symbol] = price

        # Update positions
        for position in self._positions.values():
            if position.symbol == symbol and position.status == PositionStatus.OPEN:
                position.current_price = price
                position.current_value = price * position.quantity

                if position.side == "long":
                    position.unrealized_pnl = position.current_value - position.entry_value
                else:
                    position.unrealized_pnl = position.entry_value - position.current_value

                position.unrealized_pnl_pct = (position.unrealized_pnl / position.entry_value) * 100

                self._save_position(position)

    def close_position(
        self,
        position_id: str,
        exit_price: Optional[float] = None,
        quantity: Optional[float] = None,
        fee: float = 0,
        tx_signature: str = ""
    ) -> Optional[Position]:
        """Close a position (fully or partially)."""
        position = self._positions.get(position_id)
        if not position:
            logger.error(f"Position {position_id} not found")
            return None

        import uuid
        trade_id = str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()

        # Use current price if not provided
        if exit_price is None:
            exit_price = self._prices.get(position.symbol, position.current_price)

        # Close quantity
        close_qty = quantity or position.quantity
        close_qty = min(close_qty, position.quantity)

        # Calculate PnL
        close_value = exit_price * close_qty
        entry_value_portion = position.entry_price * close_qty

        if position.side == "long":
            pnl = close_value - entry_value_portion
        else:
            pnl = entry_value_portion - close_value

        # Record trade
        trade = Trade(
            id=trade_id,
            position_id=position_id,
            symbol=position.symbol,
            side="sell" if position.side == "long" else "buy",
            price=exit_price,
            quantity=close_qty,
            value=close_value,
            fee=fee,
            timestamp=now,
            tx_signature=tx_signature
        )
        self._save_trade(trade)

        # Update position
        position.realized_pnl += pnl
        position.fees_paid += fee
        position.quantity -= close_qty

        if position.quantity <= 0:
            position.status = PositionStatus.CLOSED
            position.closed_at = now
            del self._positions[position_id]
        else:
            position.status = PositionStatus.PARTIALLY_CLOSED
            position.entry_value = position.entry_price * position.quantity
            position.current_value = position.current_price * position.quantity

            if position.side == "long":
                position.unrealized_pnl = position.current_value - position.entry_value
            else:
                position.unrealized_pnl = position.entry_value - position.current_value

        self._save_position(position)

        logger.info(f"Closed position {position_id}: PnL = ${pnl:.2f}")

        return position

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        return self._positions.get(position_id)

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Position]:
        """Get all open positions."""
        positions = list(self._positions.values())
        if symbol:
            positions = [p for p in positions if p.symbol == symbol.upper()]
        return positions

    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized PnL."""
        return sum(p.unrealized_pnl for p in self._positions.values())

    def get_pnl_summary(self, period: str = "all") -> PnLSummary:
        """Get PnL summary for a period."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            # Determine date filter
            date_filter = ""
            if period == "1d":
                date_filter = "AND datetime(opened_at) > datetime('now', '-1 day')"
            elif period == "7d":
                date_filter = "AND datetime(opened_at) > datetime('now', '-7 days')"
            elif period == "30d":
                date_filter = "AND datetime(opened_at) > datetime('now', '-30 days')"
            elif period == "ytd":
                year_start = datetime.now().replace(month=1, day=1).strftime('%Y-%m-%d')
                date_filter = f"AND opened_at >= '{year_start}'"

            # Get closed positions
            cursor.execute(f"""
                SELECT * FROM positions
                WHERE status = 'closed' {date_filter}
            """)

            closed_positions = cursor.fetchall()

            # Calculate stats
            wins = [p['realized_pnl'] for p in closed_positions if p['realized_pnl'] > 0]
            losses = [p['realized_pnl'] for p in closed_positions if p['realized_pnl'] < 0]

            realized_pnl = sum(p['realized_pnl'] for p in closed_positions)
            total_fees = sum(p['fees_paid'] for p in closed_positions)
            unrealized_pnl = self.get_total_unrealized_pnl()

            win_count = len(wins)
            loss_count = len(losses)
            total_trades = win_count + loss_count

            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            largest_win = max(wins) if wins else 0
            largest_loss = min(losses) if losses else 0

            gross_profit = sum(wins)
            gross_loss = abs(sum(losses))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

            # Total volume
            cursor.execute(f"""
                SELECT SUM(value) as total_volume FROM trades
                WHERE 1=1 {date_filter.replace('opened_at', 'timestamp')}
            """)
            result = cursor.fetchone()
            total_volume = result['total_volume'] or 0

            # ROI calculation
            total_entry = sum(p['entry_value'] for p in closed_positions)
            roi_pct = (realized_pnl / total_entry * 100) if total_entry > 0 else 0

            return PnLSummary(
                period=period,
                total_pnl=realized_pnl + unrealized_pnl,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                total_fees=total_fees,
                net_pnl=realized_pnl - total_fees,
                win_count=win_count,
                loss_count=loss_count,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss,
                largest_win=largest_win,
                largest_loss=largest_loss,
                profit_factor=profit_factor,
                total_volume=total_volume,
                roi_pct=roi_pct
            )

    def record_daily_pnl(self):
        """Record daily PnL snapshot."""
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        # Get today's stats
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT SUM(realized_pnl) as realized, SUM(fees_paid) as fees
                FROM positions WHERE date(closed_at) = ?
            """, (today,))
            result = cursor.fetchone()

            realized = result['realized'] or 0
            fees = result['fees'] or 0

            cursor.execute("""
                SELECT COUNT(*) as count, SUM(value) as volume
                FROM trades WHERE date(timestamp) = ?
            """, (today,))
            result = cursor.fetchone()

            trades_count = result['count'] or 0
            volume = result['volume'] or 0

            unrealized = self.get_total_unrealized_pnl()

            cursor.execute("""
                INSERT OR REPLACE INTO daily_pnl
                (date, starting_balance, ending_balance, realized_pnl,
                 unrealized_pnl, fees, trades_count, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today, self._starting_balance, self._starting_balance + realized,
                realized, unrealized, fees, trades_count, volume
            ))
            conn.commit()

    def get_daily_pnl(self, days: int = 30) -> List[DailyPnL]:
        """Get daily PnL history."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM daily_pnl
                WHERE date >= date('now', ?)
                ORDER BY date ASC
            """, (f'-{days} days',))

            return [
                DailyPnL(
                    date=row['date'],
                    starting_balance=row['starting_balance'],
                    ending_balance=row['ending_balance'],
                    realized_pnl=row['realized_pnl'],
                    unrealized_pnl=row['unrealized_pnl'],
                    fees=row['fees'],
                    trades_count=row['trades_count'],
                    volume=row['volume']
                )
                for row in cursor.fetchall()
            ]

    def get_trade_history(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Trade]:
        """Get trade history."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM trades"
            params = []

            if symbol:
                query += " WHERE symbol = ?"
                params.append(symbol.upper())

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [
                Trade(
                    id=row['id'],
                    position_id=row['position_id'],
                    symbol=row['symbol'],
                    side=row['side'],
                    price=row['price'],
                    quantity=row['quantity'],
                    value=row['value'],
                    fee=row['fee'],
                    timestamp=row['timestamp'],
                    tx_signature=row['tx_signature']
                )
                for row in cursor.fetchall()
            ]

    def get_position_history(
        self,
        symbol: Optional[str] = None,
        status: Optional[PositionStatus] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get position history."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM positions WHERE 1=1"
            params = []

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol.upper())

            if status:
                query += " AND status = ?"
                params.append(status.value)

            query += " ORDER BY opened_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]


# Singleton
_tracker: Optional[PnLTracker] = None


def get_pnl_tracker() -> PnLTracker:
    """Get singleton PnL tracker."""
    global _tracker
    if _tracker is None:
        _tracker = PnLTracker()
    return _tracker
