"""
Trailing Stop Strategy - Automatically adjusts stop loss as price moves up.

Protects profits while allowing unlimited upside potential.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TrailingStopConfig:
    """Configuration for trailing stop strategy."""
    trail_percentage: float = 10.0  # Trail price by 10%
    min_profit_pct: float = 5.0  # Only trail if profit > 5%
    update_frequency_minutes: int = 5  # Update every 5 minutes
    max_trailing_distance: float = 50.0  # Max trail distance in percent


class TrailingStopStrategy:
    """Implements trailing stop loss strategy."""

    def __init__(self, config: Optional[TrailingStopConfig] = None):
        """Initialize trailing stop strategy.

        Args:
            config: Strategy configuration
        """
        self.config = config or TrailingStopConfig()
        self.positions = {}  # Track position: entry_price, highest_price, stop_loss
        self.last_updates = {}  # Track last update time per position

    def enter_position(self, symbol: str, entry_price: float, position_id: str) -> Dict[str, Any]:
        """Record position entry with trailing stop initialization.

        Args:
            symbol: Token symbol
            entry_price: Entry price
            position_id: Unique position identifier

        Returns:
            Position state with initial stop loss
        """
        initial_stop = entry_price * (1 - self.config.min_profit_pct / 100)

        self.positions[position_id] = {
            'symbol': symbol,
            'entry_price': entry_price,
            'highest_price': entry_price,
            'stop_loss': initial_stop,
            'entry_time': datetime.utcnow(),
            'trailing_active': False,
        }
        self.last_updates[position_id] = datetime.utcnow()

        logger.info(f"Trailing stop initialized for {symbol}: entry={entry_price}, initial_sl={initial_stop}")

        return {
            'symbol': symbol,
            'entry_price': entry_price,
            'stop_loss': initial_stop,
            'trailing_active': False,
        }

    def update_trailing_stop(self, position_id: str, current_price: float) -> Dict[str, Any]:
        """Update trailing stop for a position.

        Args:
            position_id: Position identifier
            current_price: Current market price

        Returns:
            Updated stop loss and trail status
        """
        if position_id not in self.positions:
            return {'error': f'Position {position_id} not found'}

        pos = self.positions[position_id]
        previous_stop = pos['stop_loss']

        # Check if price has moved up significantly
        profit_pct = ((current_price - pos['entry_price']) / pos['entry_price']) * 100

        # Only activate trailing stop if minimum profit threshold reached
        if profit_pct >= self.config.min_profit_pct:
            pos['trailing_active'] = True

            # Update highest price if current price is higher
            if current_price > pos['highest_price']:
                pos['highest_price'] = current_price

            # Calculate new trailing stop
            new_stop = current_price * (1 - self.config.trail_percentage / 100)

            # Only move stop loss up, never down
            if new_stop > previous_stop:
                # Check max trailing distance
                trail_distance = ((pos['highest_price'] - new_stop) / pos['highest_price']) * 100

                if trail_distance <= self.config.max_trailing_distance:
                    pos['stop_loss'] = new_stop
                    self.last_updates[position_id] = datetime.utcnow()

                    logger.info(
                        f"Trailing stop updated for {pos['symbol']}: "
                        f"price={current_price}, stop_loss={new_stop}, "
                        f"profit={profit_pct:.2f}%, trail_distance={trail_distance:.2f}%"
                    )

                    return {
                        'symbol': pos['symbol'],
                        'current_price': current_price,
                        'stop_loss': new_stop,
                        'profit_pct': profit_pct,
                        'trailing_active': True,
                        'trail_distance_pct': trail_distance,
                        'stop_moved': new_stop > previous_stop,
                    }

        return {
            'symbol': pos['symbol'],
            'current_price': current_price,
            'stop_loss': pos['stop_loss'],
            'profit_pct': profit_pct,
            'trailing_active': pos['trailing_active'],
            'stop_moved': False,
        }

    def check_exit_signal(self, position_id: str, current_price: float) -> Dict[str, Any]:
        """Check if position should be exited based on trailing stop.

        Args:
            position_id: Position identifier
            current_price: Current market price

        Returns:
            Exit signal with reason
        """
        if position_id not in self.positions:
            return {'should_exit': False, 'reason': 'Position not found'}

        pos = self.positions[position_id]

        # Check if stop loss is hit
        if current_price <= pos['stop_loss']:
            profit_pct = ((pos['highest_price'] - pos['entry_price']) / pos['entry_price']) * 100

            logger.warning(
                f"Trailing stop triggered for {pos['symbol']}: "
                f"exit_price={current_price}, stop_loss={pos['stop_loss']}, "
                f"max_profit={profit_pct:.2f}%"
            )

            return {
                'should_exit': True,
                'reason': 'Trailing stop hit',
                'exit_price': current_price,
                'entry_price': pos['entry_price'],
                'max_price': pos['highest_price'],
                'max_profit_pct': profit_pct,
                'realized_loss_pct': ((current_price - pos['entry_price']) / pos['entry_price']) * 100,
            }

        return {
            'should_exit': False,
            'reason': 'Price above stop loss',
            'stop_loss': pos['stop_loss'],
            'current_price': current_price,
            'distance_to_stop_pct': ((current_price - pos['stop_loss']) / pos['stop_loss']) * 100,
        }

    def close_position(self, position_id: str) -> bool:
        """Remove position from tracking.

        Args:
            position_id: Position identifier

        Returns:
            Success flag
        """
        if position_id in self.positions:
            del self.positions[position_id]
            if position_id in self.last_updates:
                del self.last_updates[position_id]
            return True
        return False

    def get_position_status(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a position.

        Args:
            position_id: Position identifier

        Returns:
            Position status or None if not found
        """
        if position_id not in self.positions:
            return None

        pos = self.positions[position_id]
        return {
            'symbol': pos['symbol'],
            'entry_price': pos['entry_price'],
            'highest_price': pos['highest_price'],
            'stop_loss': pos['stop_loss'],
            'trailing_active': pos['trailing_active'],
            'entry_time': pos['entry_time'].isoformat(),
            'last_update': self.last_updates[position_id].isoformat(),
        }

    def get_all_positions(self) -> Dict[str, Any]:
        """Get status of all positions.

        Returns:
            Dictionary of all position statuses
        """
        return {
            pos_id: self.get_position_status(pos_id)
            for pos_id in self.positions.keys()
        }


__all__ = ["TrailingStopStrategy", "TrailingStopConfig"]
