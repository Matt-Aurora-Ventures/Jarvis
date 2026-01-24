"""
Trading Position Management

Position state persistence, loading, and reconciliation.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .types import Position, TradeStatus, TradeDirection
from .constants import (
    POSITIONS_FILE,
    HISTORY_FILE,
    LEGACY_POSITIONS_FILE,
    LEGACY_HISTORY_FILE,
)
from .logging_utils import log_trading_error, log_trading_event

logger = logging.getLogger(__name__)

# Import SafeState if available
try:
    from core.safe_state import SafeState
    SAFE_STATE_AVAILABLE = True
except ImportError:
    SAFE_STATE_AVAILABLE = False
    SafeState = None


class PositionManager:
    """Manages trading positions with persistent state."""

    def __init__(
        self,
        positions_file: Path = None,
        history_file: Path = None,
        state_profile: Optional[str] = None
    ):
        """
        Initialize position manager.

        Args:
            positions_file: Custom path for positions state file
            history_file: Custom path for trade history file
            state_profile: Profile name for state isolation (e.g., "demo")
        """
        self._state_profile = (state_profile or "").strip().lower()

        # Configure paths based on profile
        if self._state_profile and self._state_profile != "treasury":
            self._configure_state_paths(self._state_profile)
        else:
            self.POSITIONS_FILE = positions_file or POSITIONS_FILE
            self.HISTORY_FILE = history_file or HISTORY_FILE

        # Legacy fallback paths
        self._legacy_positions_files: List[Path] = [
            LEGACY_POSITIONS_FILE,
            Path(__file__).resolve().parents[3] / "bots" / "treasury" / ".positions.json",
        ]
        self._legacy_history_files: List[Path] = [
            LEGACY_HISTORY_FILE,
            Path(__file__).resolve().parents[3] / "bots" / "treasury" / ".trade_history.json",
        ]

        # State containers
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Position] = []

        # SafeState instances for atomic file access
        self._positions_state = None
        self._history_state = None

    def _configure_state_paths(self, profile: str) -> None:
        """Override state files for a non-treasury profile."""
        profile_state_dir = Path(__file__).resolve().parents[3] / "data" / profile / "trader"
        profile_state_dir.mkdir(parents=True, exist_ok=True)

        self.POSITIONS_FILE = profile_state_dir / "positions.json"
        self.HISTORY_FILE = profile_state_dir / "trade_history.json"

        legacy_trading_dir = Path.home() / ".lifeos" / profile / "trading"
        legacy_trading_dir.mkdir(parents=True, exist_ok=True)

        self._legacy_positions_files = [
            legacy_trading_dir / "positions.json",
        ]
        self._legacy_history_files = [
            legacy_trading_dir / "trade_history.json",
        ]

    def load_state(self):
        """Load positions and history from disk with file locking."""
        logger.info("Loading trading state...")

        # Ensure canonical directories exist
        self.POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        legacy_positions_loaded = False
        legacy_history_loaded = False

        if SAFE_STATE_AVAILABLE:
            self._positions_state = SafeState(self.POSITIONS_FILE, default_value=[])
            self._history_state = SafeState(self.HISTORY_FILE, default_value=[])

            try:
                data = self._positions_state.read()
                for pos_data in data:
                    pos = Position.from_dict(pos_data)
                    self.positions[pos.id] = pos
                    logger.info(f"[LOAD] Position {pos.id}: {pos.token_symbol} - status={pos.status.value}, amount=${pos.amount_usd:.2f}")
            except Exception as e:
                logger.error(f"Failed to load positions from primary: {e}")
                legacy_positions_loaded = self._load_from_secondary()
            else:
                primary_missing = not self.POSITIONS_FILE.exists()
                primary_empty = self.POSITIONS_FILE.exists() and self.POSITIONS_FILE.stat().st_size == 0
                if (primary_missing or primary_empty) and not self.positions:
                    legacy_positions_loaded = self._load_from_secondary()

            try:
                data = self._history_state.read()
                self.trade_history = [Position.from_dict(p) for p in data]
                logger.info(f"[LOAD] Trade history: {len(self.trade_history)} closed positions")
            except Exception as e:
                logger.error(f"Failed to load history: {e}")
                legacy_history_loaded = self._load_history_from_legacy()
        else:
            # Fallback to original implementation
            if self.POSITIONS_FILE.exists():
                try:
                    with open(self.POSITIONS_FILE) as f:
                        data = json.load(f)
                        for pos_data in data:
                            pos = Position.from_dict(pos_data)
                            self.positions[pos.id] = pos
                            logger.info(f"[LOAD] Position {pos.id}: {pos.token_symbol} - status={pos.status.value}, amount=${pos.amount_usd:.2f}")
                except Exception as e:
                    logger.error(f"Failed to load positions from primary: {e}")
                    legacy_positions_loaded = self._load_from_secondary()
            else:
                legacy_positions_loaded = self._load_from_secondary()

            if self.HISTORY_FILE.exists():
                try:
                    with open(self.HISTORY_FILE) as f:
                        data = json.load(f)
                        self.trade_history = [Position.from_dict(p) for p in data]
                        logger.info(f"[LOAD] Trade history: {len(self.trade_history)} closed positions")
                except Exception as e:
                    logger.error(f"Failed to load history: {e}")
                    legacy_history_loaded = self._load_history_from_legacy()
            else:
                legacy_history_loaded = self._load_history_from_legacy()

        # Persist migrated legacy state into canonical store
        if legacy_positions_loaded or legacy_history_loaded:
            try:
                self.save_state()
                logger.info("[MIGRATE] Persisted legacy trading state into canonical files")
            except Exception as e:
                logger.warning(f"[MIGRATE] Failed to persist legacy state: {e}")

        # Log summary
        open_count = len([p for p in self.positions.values() if p.is_open])
        total_value = sum(p.amount_usd for p in self.positions.values() if p.is_open)
        logger.info(f"[LOAD] State loaded: {open_count} open positions, total value ${total_value:.2f}")

    def _load_from_secondary(self) -> bool:
        """Load positions from legacy locations (read-only fallback)."""
        for legacy_path in self._legacy_positions_files:
            if not legacy_path.exists():
                continue
            try:
                with open(legacy_path) as f:
                    data = json.load(f)
                    for pos_data in data:
                        pos = Position.from_dict(pos_data)
                        if pos.id not in self.positions:
                            self.positions[pos.id] = pos
                            logger.info(f"[LOAD-LEGACY] Position {pos.id}: {pos.token_symbol}")
                logger.info(f"[LOAD-LEGACY] Recovered {len(data)} positions from {legacy_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to load positions from legacy {legacy_path}: {e}")
        return False

    def _load_history_from_legacy(self) -> bool:
        """Load trade history from legacy locations (read-only fallback)."""
        for legacy_path in self._legacy_history_files:
            if not legacy_path.exists():
                continue
            try:
                with open(legacy_path) as f:
                    data = json.load(f)
                    self.trade_history = [Position.from_dict(p) for p in data]
                logger.info(f"[LOAD-LEGACY] Trade history: {len(self.trade_history)} closed positions from {legacy_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to load history from legacy {legacy_path}: {e}")
        return False

    def save_state(self):
        """Save positions and history to disk with file locking."""
        positions_data = [p.to_dict() for p in self.positions.values()]
        history_data = [p.to_dict() for p in self.trade_history]

        try:
            if SAFE_STATE_AVAILABLE and self._positions_state:
                # Use SafeState for atomic writes with locking
                self._positions_state.write(positions_data)
                self._history_state.write(history_data)
            else:
                # Fallback to original implementation
                self.POSITIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
                with open(self.POSITIONS_FILE, 'w') as f:
                    json.dump(positions_data, f, indent=2)
                with open(self.HISTORY_FILE, 'w') as f:
                    json.dump(history_data, f, indent=2)

        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            log_trading_error(e, "save_state", {"positions_count": len(self.positions)})

    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.is_open]

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a specific position."""
        return self.positions.get(position_id)

    def add_position(self, position: Position):
        """Add a new position."""
        self.positions[position.id] = position
        self.save_state()

    def remove_position(self, position_id: str) -> Optional[Position]:
        """Remove and return a position."""
        position = self.positions.pop(position_id, None)
        if position:
            self.save_state()
        return position

    def close_position(self, position_id: str, exit_price: float, reason: str = "Manual close"):
        """Close a position and move to history."""
        if position_id not in self.positions:
            return None

        position = self.positions[position_id]
        position.status = TradeStatus.CLOSED
        position.closed_at = datetime.utcnow().isoformat()
        position.exit_price = exit_price

        # Calculate P&L
        if position.entry_price > 0:
            position.pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100
            position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)

        # Move to history
        self.trade_history.append(position)
        del self.positions[position_id]
        self.save_state()

        return position

    def update_position_price(self, position_id: str, current_price: float):
        """Update position's current price and unrealized P&L."""
        if position_id not in self.positions:
            return

        position = self.positions[position_id]
        position.current_price = current_price

        if position.entry_price > 0:
            position.pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            position.pnl_usd = position.amount_usd * (position.pnl_pct / 100)
