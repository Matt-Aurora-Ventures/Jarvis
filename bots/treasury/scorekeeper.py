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
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)

# Persistence paths
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
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

        self._load()
        self._initialized = True
        logger.info(f"Scorekeeper initialized: {len(self.positions)} positions, {len(self.trades)} trades")

    def _load(self):
        """Load data from disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load scorekeeper data
        if SCOREKEEPER_FILE.exists():
            try:
                with open(SCOREKEEPER_FILE) as f:
                    data = json.load(f)

                self.positions = {
                    k: Position.from_dict(v) for k, v in data.get("positions", {}).items()
                }
                self.trades = [TradeRecord(**t) for t in data.get("trades", [])]
                self.scorecard = ScoreCard(**data.get("scorecard", {}))
                logger.info(f"Loaded scorekeeper: {len(self.positions)} positions")
            except Exception as e:
                logger.error(f"Failed to load scorekeeper: {e}")

        # Load orders
        if ORDERS_FILE.exists():
            try:
                with open(ORDERS_FILE) as f:
                    self.orders = json.load(f)
                logger.info(f"Loaded {len(self.orders)} orders")
            except Exception as e:
                logger.error(f"Failed to load orders: {e}")

    def _save(self):
        """Save data to disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        try:
            data = {
                "positions": {k: v.to_dict() for k, v in self.positions.items()},
                "trades": [t.to_dict() for t in self.trades],
                "scorecard": self.scorecard.to_dict(),
            }
            with open(SCOREKEEPER_FILE, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save scorekeeper: {e}")

        try:
            with open(ORDERS_FILE, "w") as f:
                json.dump(self.orders, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save orders: {e}")

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


# Singleton accessor
def get_scorekeeper() -> Scorekeeper:
    """Get the scorekeeper singleton."""
    return Scorekeeper()
