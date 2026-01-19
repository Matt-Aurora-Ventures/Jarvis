"""
Mean Reversion Strategy - Identifies oversold conditions and entry opportunities.

Buys tokens trading below their moving average with high conviction.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from collections import deque
import statistics

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionConfig:
    """Configuration for mean reversion strategy."""
    short_window: int = 7  # Short MA (7 periods)
    long_window: int = 25  # Long MA (25 periods)
    reversion_threshold_pct: float = 15.0  # Buy if 15% below MA
    confidence_threshold: float = 70.0  # Min conviction (0-100)
    max_position_size_pct: float = 5.0  # Max position size


class MeanReversionStrategy:
    """Implements mean reversion trading strategy."""

    def __init__(self, config: Optional[MeanReversionConfig] = None):
        """Initialize mean reversion strategy.

        Args:
            config: Strategy configuration
        """
        self.config = config or MeanReversionConfig()
        self.price_history = {}  # symbol -> deque of prices
        self.signal_cache = {}  # symbol -> cached signal data

    def add_price_point(self, symbol: str, price: float) -> None:
        """Add a new price point to history.

        Args:
            symbol: Token symbol
            price: Current price
        """
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=self.config.long_window + 10)

        self.price_history[symbol].append(price)

    def calculate_moving_averages(self, symbol: str) -> Dict[str, Optional[float]]:
        """Calculate short and long moving averages.

        Args:
            symbol: Token symbol

        Returns:
            Dict with short_ma and long_ma
        """
        if symbol not in self.price_history or len(self.price_history[symbol]) < self.config.long_window:
            return {'short_ma': None, 'long_ma': None, 'sufficient_data': False}

        prices = list(self.price_history[symbol])

        # Short MA
        short_prices = prices[-self.config.short_window:]
        short_ma = statistics.mean(short_prices)

        # Long MA
        long_prices = prices[-self.config.long_window:]
        long_ma = statistics.mean(long_prices)

        return {
            'short_ma': short_ma,
            'long_ma': long_ma,
            'sufficient_data': True,
        }

    def calculate_reversion_signal(self, symbol: str, current_price: float) -> Dict[str, Any]:
        """Calculate mean reversion signal.

        Args:
            symbol: Token symbol
            current_price: Current market price

        Returns:
            Signal with buy recommendation
        """
        # Add price to history
        self.add_price_point(symbol, current_price)

        # Calculate MAs
        ma_data = self.calculate_moving_averages(symbol)

        if not ma_data['sufficient_data']:
            return {
                'symbol': symbol,
                'signal': 'INSUFFICIENT_DATA',
                'confidence': 0,
                'should_buy': False,
                'reason': 'Not enough price history',
            }

        short_ma = ma_data['short_ma']
        long_ma = ma_data['long_ma']

        # Calculate deviation from long MA
        deviation_pct = ((current_price - long_ma) / long_ma) * 100

        # Check if price is oversold (below MA)
        is_oversold = deviation_pct < -self.config.reversion_threshold_pct

        # Calculate confidence score
        confidence = 0.0

        if is_oversold:
            # Stronger confidence if price is further below MA
            oversold_severity = abs(deviation_pct) - self.config.reversion_threshold_pct
            confidence = min(95, 50 + (oversold_severity * 2))

            # Boost confidence if short MA is above long MA (uptrend)
            if short_ma > long_ma:
                confidence = min(100, confidence + 10)

            # Reduce confidence if in downtrend
            if short_ma < long_ma:
                confidence = max(50, confidence - 10)

        should_buy = is_oversold and confidence >= self.config.confidence_threshold

        signal_data = {
            'symbol': symbol,
            'current_price': current_price,
            'short_ma': short_ma,
            'long_ma': long_ma,
            'deviation_pct': deviation_pct,
            'is_oversold': is_oversold,
            'signal': 'BUY' if should_buy else 'HOLD',
            'confidence': confidence,
            'should_buy': should_buy,
            'reason': 'Price significantly below moving average' if should_buy else 'Price not sufficiently oversold',
        }

        # Cache signal
        self.signal_cache[symbol] = signal_data

        logger.info(
            f"Mean reversion signal for {symbol}: "
            f"price={current_price}, long_ma={long_ma}, "
            f"deviation={deviation_pct:.2f}%, confidence={confidence:.0f}%, "
            f"signal={'BUY' if should_buy else 'HOLD'}"
        )

        return signal_data

    def get_target_price(self, symbol: str) -> Optional[float]:
        """Calculate target price for mean reversion trade.

        Args:
            symbol: Token symbol

        Returns:
            Target price (mean average) or None
        """
        ma_data = self.calculate_moving_averages(symbol)

        if not ma_data['sufficient_data']:
            return None

        # Target is the long MA (mean value)
        return ma_data['long_ma']

    def get_risk_reward_ratio(self, symbol: str, current_price: float, stop_loss_pct: float = 10.0) -> Dict[str, float]:
        """Calculate risk/reward ratio for mean reversion trade.

        Args:
            symbol: Token symbol
            current_price: Entry price
            stop_loss_pct: Stop loss percentage below entry

        Returns:
            Risk/reward metrics
        """
        target_price = self.get_target_price(symbol)

        if target_price is None:
            return {'error': 'Insufficient data'}

        stop_loss = current_price * (1 - stop_loss_pct / 100)
        reward_amount = target_price - current_price
        risk_amount = current_price - stop_loss

        if risk_amount == 0:
            return {'error': 'Invalid risk calculation'}

        risk_reward_ratio = reward_amount / risk_amount if risk_amount > 0 else 0

        return {
            'entry_price': current_price,
            'target_price': target_price,
            'stop_loss': stop_loss,
            'reward_amount': reward_amount,
            'risk_amount': risk_amount,
            'risk_reward_ratio': risk_reward_ratio,
            'profitable': reward_amount > 0,
        }

    def get_signal_strength(self, symbol: str) -> float:
        """Get current signal strength (0-100).

        Args:
            symbol: Token symbol

        Returns:
            Signal strength score
        """
        if symbol in self.signal_cache:
            return self.signal_cache[symbol].get('confidence', 0)

        return 0

    def get_all_signals(self) -> Dict[str, Dict[str, Any]]:
        """Get all cached signals.

        Returns:
            Dictionary of all signals
        """
        return self.signal_cache.copy()

    def clear_history(self, symbol: Optional[str] = None) -> None:
        """Clear price history for a symbol or all.

        Args:
            symbol: Symbol to clear, or None for all
        """
        if symbol:
            if symbol in self.price_history:
                del self.price_history[symbol]
            if symbol in self.signal_cache:
                del self.signal_cache[symbol]
        else:
            self.price_history.clear()
            self.signal_cache.clear()


__all__ = ["MeanReversionStrategy", "MeanReversionConfig"]
