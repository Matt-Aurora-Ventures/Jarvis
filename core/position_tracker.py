"""
Position Tracker - Track and analyze trading positions.

Features:
- Position history storage
- Aggregate statistics (win rate, total P&L, etc.)
- Real-time position updates
- Performance analytics
"""

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "positions"
HISTORY_FILE = DATA_DIR / "position_history.jsonl"
STATS_FILE = DATA_DIR / "position_stats.json"
ACTIVE_FILE = ROOT / "data" / "active_position.json"


@dataclass
class Position:
    """Represents a trading position."""
    id: str
    symbol: str
    mint: str
    entry_price: float
    entry_time: float
    quantity: float
    position_usd: float
    is_paper: bool = True

    # Exit info (filled when closed)
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    exit_reason: Optional[str] = None

    # Targets
    take_profit_price: Optional[float] = None
    stop_loss_price: Optional[float] = None

    # Calculated fields
    pnl_usd: float = 0.0
    pnl_pct: float = 0.0
    hold_duration_minutes: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PositionStats:
    """Aggregate trading statistics."""
    total_positions: int = 0
    winning_positions: int = 0
    losing_positions: int = 0
    total_pnl_usd: float = 0.0
    total_pnl_pct: float = 0.0
    best_trade_pnl_pct: float = 0.0
    worst_trade_pnl_pct: float = 0.0
    avg_hold_duration_minutes: float = 0.0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    largest_win_usd: float = 0.0
    largest_loss_usd: float = 0.0
    current_streak: int = 0  # Positive = wins, negative = losses
    best_streak: int = 0
    worst_streak: int = 0
    last_updated: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PositionStats":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class PositionTracker:
    """
    Tracks all trading positions and calculates statistics.

    Features:
    - Stores position history
    - Calculates win rate, average P&L, etc.
    - Provides performance insights
    """

    def __init__(self):
        self._history: List[Position] = []
        self._stats = PositionStats()
        self._lock = threading.Lock()
        self._load()

    def _load(self) -> None:
        """Load position history from disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Load history
        if HISTORY_FILE.exists():
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                data = json.loads(line)
                                self._history.append(Position.from_dict(data))
                            except (json.JSONDecodeError, TypeError):
                                continue
                logger.info(f"Loaded {len(self._history)} positions from history")
            except Exception as e:
                logger.warning(f"Failed to load history: {e}")

        # Load stats
        if STATS_FILE.exists():
            try:
                data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
                self._stats = PositionStats.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load stats: {e}")
                self._recalculate_stats()

    def _save_history(self, position: Position) -> None:
        """Append a position to history file."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(position.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to save position: {e}")

    def _save_stats(self) -> None:
        """Save stats to disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            self._stats.last_updated = datetime.now(timezone.utc).isoformat()
            STATS_FILE.write_text(
                json.dumps(self._stats.to_dict(), indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Failed to save stats: {e}")

    def _recalculate_stats(self) -> None:
        """Recalculate all statistics from history."""
        if not self._history:
            self._stats = PositionStats()
            return

        wins = [p for p in self._history if p.pnl_pct > 0]
        losses = [p for p in self._history if p.pnl_pct <= 0]

        self._stats.total_positions = len(self._history)
        self._stats.winning_positions = len(wins)
        self._stats.losing_positions = len(losses)
        self._stats.total_pnl_usd = sum(p.pnl_usd for p in self._history)
        self._stats.total_pnl_pct = sum(p.pnl_pct for p in self._history)

        if self._history:
            self._stats.best_trade_pnl_pct = max(p.pnl_pct for p in self._history)
            self._stats.worst_trade_pnl_pct = min(p.pnl_pct for p in self._history)
            self._stats.avg_hold_duration_minutes = sum(
                p.hold_duration_minutes for p in self._history
            ) / len(self._history)
            self._stats.largest_win_usd = max((p.pnl_usd for p in wins), default=0)
            self._stats.largest_loss_usd = min((p.pnl_usd for p in losses), default=0)

        if self._stats.total_positions > 0:
            self._stats.win_rate = (
                self._stats.winning_positions / self._stats.total_positions * 100
            )

        if wins:
            self._stats.avg_win_pct = sum(p.pnl_pct for p in wins) / len(wins)

        if losses:
            self._stats.avg_loss_pct = sum(p.pnl_pct for p in losses) / len(losses)

        # Calculate streaks
        streak = 0
        best = 0
        worst = 0
        for p in self._history:
            if p.pnl_pct > 0:
                if streak >= 0:
                    streak += 1
                else:
                    streak = 1
                best = max(best, streak)
            else:
                if streak <= 0:
                    streak -= 1
                else:
                    streak = -1
                worst = min(worst, streak)

        self._stats.current_streak = streak
        self._stats.best_streak = best
        self._stats.worst_streak = worst

        self._save_stats()

    def record_position(self, position: Position) -> None:
        """Record a closed position."""
        with self._lock:
            self._history.append(position)
            self._save_history(position)
            self._recalculate_stats()

        logger.info(
            f"Recorded position: {position.symbol} "
            f"PnL: {position.pnl_pct:+.2f}% (${position.pnl_usd:+.2f})"
        )

    def close_position(
        self,
        exit_price: float,
        exit_reason: str = "MANUAL_EXIT",
    ) -> Optional[Position]:
        """
        Close the active position and record it.

        Returns the closed position or None if no active position.
        """
        if not ACTIVE_FILE.exists():
            return None

        try:
            data = json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read active position: {e}")
            return None

        # Create position record
        entry_price = float(data.get("entry_price", 0))
        quantity = float(data.get("quantity", 0))
        entry_time = float(data.get("entry_time", time.time()))
        exit_time = time.time()

        pnl_usd = (exit_price - entry_price) * quantity
        pnl_pct = ((exit_price - entry_price) / entry_price * 100) if entry_price else 0
        hold_duration = (exit_time - entry_time) / 60  # Minutes

        position = Position(
            id=data.get("id", f"pos_{int(time.time())}"),
            symbol=data.get("symbol", "?"),
            mint=data.get("mint", ""),
            entry_price=entry_price,
            entry_time=entry_time,
            quantity=quantity,
            position_usd=float(data.get("position_usd", 0)),
            is_paper=data.get("is_paper", True),
            exit_price=exit_price,
            exit_time=exit_time,
            exit_reason=exit_reason,
            take_profit_price=data.get("take_profit_price"),
            stop_loss_price=data.get("stop_loss_price"),
            pnl_usd=pnl_usd,
            pnl_pct=pnl_pct,
            hold_duration_minutes=hold_duration,
        )

        self.record_position(position)

        # Clear active position
        try:
            ACTIVE_FILE.unlink()
        except Exception:
            pass

        return position

    def get_stats(self) -> PositionStats:
        """Get current statistics."""
        return self._stats

    def get_history(self, limit: int = 50) -> List[Position]:
        """Get recent position history."""
        with self._lock:
            return list(reversed(self._history[-limit:]))

    def get_daily_pnl(self, days: int = 7) -> Dict[str, float]:
        """Get P&L breakdown by day."""
        result = {}
        cutoff = time.time() - (days * 86400)

        for position in self._history:
            if position.exit_time and position.exit_time > cutoff:
                day = datetime.fromtimestamp(
                    position.exit_time, tz=timezone.utc
                ).strftime("%Y-%m-%d")
                result[day] = result.get(day, 0) + position.pnl_usd

        return result

    def get_performance_by_symbol(self) -> Dict[str, Dict[str, Any]]:
        """Get performance breakdown by symbol."""
        result = {}

        for position in self._history:
            symbol = position.symbol
            if symbol not in result:
                result[symbol] = {
                    "trades": 0,
                    "wins": 0,
                    "total_pnl_usd": 0,
                    "total_pnl_pct": 0,
                }

            result[symbol]["trades"] += 1
            if position.pnl_pct > 0:
                result[symbol]["wins"] += 1
            result[symbol]["total_pnl_usd"] += position.pnl_usd
            result[symbol]["total_pnl_pct"] += position.pnl_pct

        # Calculate win rates
        for symbol, stats in result.items():
            if stats["trades"] > 0:
                stats["win_rate"] = stats["wins"] / stats["trades"] * 100
                stats["avg_pnl_pct"] = stats["total_pnl_pct"] / stats["trades"]
            else:
                stats["win_rate"] = 0
                stats["avg_pnl_pct"] = 0

        return result


# Global instance
_tracker: Optional[PositionTracker] = None
_lock = threading.Lock()


def get_tracker() -> PositionTracker:
    """Get the global position tracker instance."""
    global _tracker
    with _lock:
        if _tracker is None:
            _tracker = PositionTracker()
        return _tracker


def record_position(position: Position) -> None:
    """Record a closed position."""
    get_tracker().record_position(position)


def close_position(exit_price: float, exit_reason: str = "MANUAL_EXIT") -> Optional[Position]:
    """Close the active position."""
    return get_tracker().close_position(exit_price, exit_reason)


def get_stats() -> PositionStats:
    """Get current statistics."""
    return get_tracker().get_stats()


def get_history(limit: int = 50) -> List[Position]:
    """Get recent position history."""
    return get_tracker().get_history(limit)
