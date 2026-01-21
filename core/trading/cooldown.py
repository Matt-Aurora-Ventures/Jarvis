"""
Trade Cooldown System

Prevents overtrading by enforcing a cooldown period between trades.
Key insight: Track CLOSURES not entries to handle unfilled orders properly.

Features:
- Configurable cooldown period (default 30 minutes)
- Per-symbol cooldowns
- Global cooldown option
- CSV logging for analysis
- Allows closing during cooldown (for retry attempts)
"""

import csv
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
from enum import Enum
import json

logger = logging.getLogger(__name__)


class CooldownType(Enum):
    """Type of cooldown."""
    POSITION_CLOSE = "position_close"
    LOSS = "loss"
    CONSECUTIVE_LOSS = "consecutive_loss"
    CIRCUIT_BREAKER = "circuit_breaker"
    MANUAL = "manual"
    STANDARD = "standard"  # Alias for general/default cooldown


@dataclass
class CooldownEvent:
    """Record of an event that triggered cooldown."""
    event_type: CooldownType
    symbol: str
    timestamp: datetime
    cooldown_until: datetime
    pnl: Optional[float] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_type': self.event_type.value,
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'cooldown_until': self.cooldown_until.isoformat(),
            'pnl': self.pnl,
            'reason': self.reason,
        }


@dataclass
class CooldownConfig:
    """Configuration for cooldown behavior."""
    # Time-based cooldowns
    default_cooldown_minutes: int = 30
    loss_cooldown_minutes: int = 60  # Longer cooldown after a loss
    consecutive_loss_cooldown_minutes: int = 120  # Even longer after consecutive losses
    circuit_breaker_cooldown_minutes: int = 480  # 8 hours for circuit breaker

    # Thresholds
    consecutive_loss_threshold: int = 3
    large_loss_threshold_pct: float = 0.02  # 2% loss triggers extended cooldown

    # Behavior
    per_symbol_cooldown: bool = True  # Track per symbol or global
    allow_close_during_cooldown: bool = True  # Always allow closing positions
    log_to_csv: bool = True

    # Paths
    csv_path: str = "data/position_closures.csv"
    state_path: str = "data/cooldown_state.json"


class CooldownManager:
    """
    Manages trade cooldowns to prevent overtrading.

    Key Design Decisions:
    1. Track closures, not entries - handles unfilled orders
    2. Allow closing during cooldown - for retry attempts
    3. Extended cooldowns after losses
    4. Per-symbol tracking for diversified trading
    """

    def __init__(self, config: Optional[CooldownConfig] = None):
        self.config = config or CooldownConfig()

        # Active cooldowns per symbol
        self._cooldowns: Dict[str, datetime] = {}

        # Global cooldown (overrides per-symbol)
        self._global_cooldown: Optional[datetime] = None

        # Recent events
        self._events: List[CooldownEvent] = []

        # Loss tracking
        self._consecutive_losses: Dict[str, int] = {}

        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.config.csv_path), exist_ok=True)

        # Load existing state
        self._load_state()

        logger.info(
            f"CooldownManager initialized: default={self.config.default_cooldown_minutes}min, "
            f"per_symbol={self.config.per_symbol_cooldown}"
        )

    def _load_state(self) -> None:
        """Load cooldown state from file."""
        try:
            if os.path.exists(self.config.state_path):
                with open(self.config.state_path, 'r') as f:
                    state = json.load(f)

                for symbol, ts in state.get('cooldowns', {}).items():
                    self._cooldowns[symbol] = datetime.fromisoformat(ts)

                if state.get('global_cooldown'):
                    self._global_cooldown = datetime.fromisoformat(state['global_cooldown'])

                self._consecutive_losses = state.get('consecutive_losses', {})

                logger.info(f"Loaded cooldown state: {len(self._cooldowns)} symbol cooldowns")
        except Exception as e:
            logger.warning(f"Could not load cooldown state: {e}")

    def _save_state(self) -> None:
        """Save cooldown state to file."""
        try:
            state = {
                'cooldowns': {
                    symbol: ts.isoformat()
                    for symbol, ts in self._cooldowns.items()
                    if ts > datetime.utcnow()
                },
                'global_cooldown': (
                    self._global_cooldown.isoformat()
                    if self._global_cooldown and self._global_cooldown > datetime.utcnow()
                    else None
                ),
                'consecutive_losses': self._consecutive_losses,
                'updated_at': datetime.utcnow().isoformat(),
            }

            with open(self.config.state_path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save cooldown state: {e}")

    def can_enter_trade(self, symbol: str) -> tuple[bool, Optional[str]]:
        """
        Check if a new trade can be entered for the given symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Tuple of (can_trade, reason_if_blocked)
        """
        now = datetime.utcnow()

        # Check global cooldown first
        if self._global_cooldown and self._global_cooldown > now:
            remaining = (self._global_cooldown - now).total_seconds() / 60
            return False, f"Global cooldown active ({remaining:.0f} min remaining)"

        # Check symbol-specific cooldown
        if self.config.per_symbol_cooldown and symbol in self._cooldowns:
            cooldown_until = self._cooldowns[symbol]
            if cooldown_until > now:
                remaining = (cooldown_until - now).total_seconds() / 60
                return False, f"Cooldown for {symbol} ({remaining:.0f} min remaining)"

        return True, None

    # Alias for API compatibility with RiskManager
    def can_trade(self, symbol: str) -> tuple[bool, Optional[str]]:
        """Alias for can_enter_trade() - API compatibility."""
        return self.can_enter_trade(symbol)

    def can_close_position(self, symbol: str) -> bool:
        """
        Check if a position can be closed.
        Always returns True if allow_close_during_cooldown is enabled.
        """
        return self.config.allow_close_during_cooldown

    def on_position_close(
        self,
        symbol: str,
        pnl: float,
        reason: str = "",
    ) -> CooldownEvent:
        """
        Called when a position is closed. Triggers cooldown.

        Args:
            symbol: Trading pair symbol
            pnl: Profit/loss from the trade
            reason: Reason for closing

        Returns:
            CooldownEvent describing the cooldown
        """
        now = datetime.utcnow()

        # Determine cooldown duration based on outcome
        cooldown_type = CooldownType.POSITION_CLOSE
        cooldown_minutes = self.config.default_cooldown_minutes

        if pnl < 0:
            # Track consecutive losses
            self._consecutive_losses[symbol] = self._consecutive_losses.get(symbol, 0) + 1

            # Check for large loss
            if abs(pnl) >= self.config.large_loss_threshold_pct:
                cooldown_type = CooldownType.LOSS
                cooldown_minutes = self.config.loss_cooldown_minutes
                reason = f"Large loss ({pnl:.2%}): {reason}"

            # Check for consecutive losses
            if self._consecutive_losses[symbol] >= self.config.consecutive_loss_threshold:
                cooldown_type = CooldownType.CONSECUTIVE_LOSS
                cooldown_minutes = self.config.consecutive_loss_cooldown_minutes
                reason = f"{self._consecutive_losses[symbol]} consecutive losses: {reason}"

        else:
            # Reset consecutive losses on profit
            self._consecutive_losses[symbol] = 0

        cooldown_until = now + timedelta(minutes=cooldown_minutes)

        # Set cooldown
        if self.config.per_symbol_cooldown:
            self._cooldowns[symbol] = cooldown_until
        else:
            self._global_cooldown = cooldown_until

        # Create event
        event = CooldownEvent(
            event_type=cooldown_type,
            symbol=symbol,
            timestamp=now,
            cooldown_until=cooldown_until,
            pnl=pnl,
            reason=reason,
        )

        self._events.append(event)
        if len(self._events) > 1000:
            self._events = self._events[-500:]

        # Log to CSV
        if self.config.log_to_csv:
            self._log_to_csv(event)

        # Save state
        self._save_state()

        logger.info(
            f"COOLDOWN SET: {symbol} until {cooldown_until.isoformat()} "
            f"({cooldown_minutes} min, type={cooldown_type.value})"
        )

        return event

    # Alias for API compatibility with RiskManager
    def record_closure(
        self,
        symbol: str,
        cooldown_type_or_pnl=None,  # RiskManager passes CooldownType, legacy passes pnl
        reason: str = "",
        pnl_pct: float = 0.0,
        **kwargs,
    ) -> CooldownEvent:
        """Alias for on_position_close() - API compatibility with RiskManager.

        RiskManager calls: record_closure(symbol, CooldownType.X, pnl_pct=...)
        We map pnl_pct to our pnl parameter.
        """
        # If cooldown_type_or_pnl is a number, treat it as pnl (legacy)
        # If it's CooldownType or None, use pnl_pct instead
        if isinstance(cooldown_type_or_pnl, (int, float)):
            pnl = cooldown_type_or_pnl
        else:
            pnl = pnl_pct / 100.0 if pnl_pct else 0.0  # Convert percentage to decimal
        return self.on_position_close(symbol, pnl, reason)

    def set_circuit_breaker_cooldown(self, reason: str = "Circuit breaker triggered") -> None:
        """Set a global circuit breaker cooldown."""
        now = datetime.utcnow()
        cooldown_until = now + timedelta(minutes=self.config.circuit_breaker_cooldown_minutes)

        self._global_cooldown = cooldown_until

        event = CooldownEvent(
            event_type=CooldownType.CIRCUIT_BREAKER,
            symbol="GLOBAL",
            timestamp=now,
            cooldown_until=cooldown_until,
            reason=reason,
        )

        self._events.append(event)

        if self.config.log_to_csv:
            self._log_to_csv(event)

        self._save_state()

        logger.warning(
            f"CIRCUIT BREAKER COOLDOWN: Trading halted until {cooldown_until.isoformat()}"
        )

    def set_manual_cooldown(
        self,
        symbol: str,
        minutes: int,
        reason: str = "Manual cooldown"
    ) -> CooldownEvent:
        """Set a manual cooldown for a symbol."""
        now = datetime.utcnow()
        cooldown_until = now + timedelta(minutes=minutes)

        if symbol == "GLOBAL":
            self._global_cooldown = cooldown_until
        else:
            self._cooldowns[symbol] = cooldown_until

        event = CooldownEvent(
            event_type=CooldownType.MANUAL,
            symbol=symbol,
            timestamp=now,
            cooldown_until=cooldown_until,
            reason=reason,
        )

        self._events.append(event)
        self._save_state()

        return event

    def clear_cooldown(self, symbol: str) -> None:
        """Clear cooldown for a symbol."""
        if symbol == "GLOBAL":
            self._global_cooldown = None
        elif symbol in self._cooldowns:
            del self._cooldowns[symbol]

        self._save_state()
        logger.info(f"Cooldown cleared for {symbol}")

    def clear_all_cooldowns(self) -> None:
        """Clear all cooldowns."""
        self._cooldowns.clear()
        self._global_cooldown = None
        self._consecutive_losses.clear()
        self._save_state()
        logger.info("All cooldowns cleared")

    def _log_to_csv(self, event: CooldownEvent) -> None:
        """Log closure event to CSV file."""
        try:
            file_exists = os.path.exists(self.config.csv_path)

            with open(self.config.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)

                if not file_exists:
                    writer.writerow([
                        'timestamp', 'symbol', 'event_type', 'pnl',
                        'cooldown_until', 'reason'
                    ])

                writer.writerow([
                    event.timestamp.isoformat(),
                    event.symbol,
                    event.event_type.value,
                    event.pnl,
                    event.cooldown_until.isoformat(),
                    event.reason,
                ])
        except Exception as e:
            logger.error(f"Could not log to CSV: {e}")

    def get_active_cooldowns(self) -> Dict[str, Any]:
        """Get all currently active cooldowns."""
        now = datetime.utcnow()

        result = {
            'global_cooldown': None,
            'symbol_cooldowns': {},
            'consecutive_losses': self._consecutive_losses.copy(),
        }

        if self._global_cooldown and self._global_cooldown > now:
            result['global_cooldown'] = {
                'until': self._global_cooldown.isoformat(),
                'remaining_minutes': (self._global_cooldown - now).total_seconds() / 60,
            }

        for symbol, until in self._cooldowns.items():
            if until > now:
                result['symbol_cooldowns'][symbol] = {
                    'until': until.isoformat(),
                    'remaining_minutes': (until - now).total_seconds() / 60,
                }

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get cooldown manager statistics."""
        now = datetime.utcnow()
        active_cooldowns = sum(
            1 for until in self._cooldowns.values() if until > now
        )

        return {
            'active_symbol_cooldowns': active_cooldowns,
            'global_cooldown_active': (
                self._global_cooldown is not None and
                self._global_cooldown > now
            ),
            'total_events': len(self._events),
            'consecutive_losses': self._consecutive_losses,
            'config': {
                'default_minutes': self.config.default_cooldown_minutes,
                'loss_minutes': self.config.loss_cooldown_minutes,
                'consecutive_loss_minutes': self.config.consecutive_loss_cooldown_minutes,
                'per_symbol': self.config.per_symbol_cooldown,
            }
        }


# Global singleton instance
_cooldown_manager: Optional[CooldownManager] = None


def get_cooldown_manager(config: Optional[CooldownConfig] = None) -> CooldownManager:
    """Get or create the global cooldown manager instance."""
    global _cooldown_manager
    if _cooldown_manager is None:
        _cooldown_manager = CooldownManager(config)
    return _cooldown_manager
