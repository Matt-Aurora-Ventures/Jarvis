"""
Technical Indicators - Comprehensive TA library.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import math
from collections import deque

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    """Trend direction."""
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


class SignalType(Enum):
    """Trading signal type."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class OHLCV:
    """OHLCV candle data."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class IndicatorResult:
    """Result from an indicator calculation."""
    name: str
    value: float
    signal: SignalType
    interpretation: str
    timestamp: str


@dataclass
class TechnicalAnalysis:
    """Complete technical analysis result."""
    symbol: str
    timestamp: str
    price: float
    trend: TrendDirection
    overall_signal: SignalType
    indicators: Dict[str, IndicatorResult]
    support_levels: List[float]
    resistance_levels: List[float]
    pivot_points: Dict[str, float]
    summary: str


class TechnicalIndicators:
    """
    Technical indicators calculator.

    Usage:
        ta = TechnicalIndicators()

        # Add price data
        for candle in candles:
            ta.add_candle("SOL", candle)

        # Get indicators
        rsi = ta.rsi("SOL")
        macd = ta.macd("SOL")

        # Get full analysis
        analysis = ta.analyze("SOL")
    """

    def __init__(self, max_history: int = 500):
        self._candles: Dict[str, deque] = {}
        self._max_history = max_history

    def add_candle(self, symbol: str, candle: OHLCV):
        """Add a candle to history."""
        symbol = symbol.upper()
        if symbol not in self._candles:
            self._candles[symbol] = deque(maxlen=self._max_history)
        self._candles[symbol].append(candle)

    def add_candles(self, symbol: str, candles: List[OHLCV]):
        """Add multiple candles."""
        for candle in candles:
            self.add_candle(symbol, candle)

    def get_closes(self, symbol: str, periods: int = None) -> List[float]:
        """Get closing prices."""
        candles = self._candles.get(symbol.upper(), [])
        closes = [c.close for c in candles]
        if periods:
            closes = closes[-periods:]
        return closes

    def get_highs(self, symbol: str, periods: int = None) -> List[float]:
        """Get high prices."""
        candles = self._candles.get(symbol.upper(), [])
        highs = [c.high for c in candles]
        if periods:
            highs = highs[-periods:]
        return highs

    def get_lows(self, symbol: str, periods: int = None) -> List[float]:
        """Get low prices."""
        candles = self._candles.get(symbol.upper(), [])
        lows = [c.low for c in candles]
        if periods:
            lows = lows[-periods:]
        return lows

    def get_volumes(self, symbol: str, periods: int = None) -> List[float]:
        """Get volumes."""
        candles = self._candles.get(symbol.upper(), [])
        volumes = [c.volume for c in candles]
        if periods:
            volumes = volumes[-periods:]
        return volumes

    # Moving Averages

    def sma(self, symbol: str, period: int = 20) -> float:
        """Simple Moving Average."""
        closes = self.get_closes(symbol, period)
        if len(closes) < period:
            return 0
        return sum(closes) / len(closes)

    def ema(self, symbol: str, period: int = 20) -> float:
        """Exponential Moving Average."""
        closes = self.get_closes(symbol, period * 2)
        if len(closes) < period:
            return 0

        multiplier = 2 / (period + 1)
        ema = sum(closes[:period]) / period  # Start with SMA

        for price in closes[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    def wma(self, symbol: str, period: int = 20) -> float:
        """Weighted Moving Average."""
        closes = self.get_closes(symbol, period)
        if len(closes) < period:
            return 0

        weights = list(range(1, period + 1))
        weighted_sum = sum(p * w for p, w in zip(closes[-period:], weights))
        return weighted_sum / sum(weights)

    def vwap(self, symbol: str, period: int = 20) -> float:
        """Volume Weighted Average Price."""
        candles = list(self._candles.get(symbol.upper(), []))[-period:]
        if not candles:
            return 0

        cumulative_pv = sum((c.high + c.low + c.close) / 3 * c.volume for c in candles)
        cumulative_volume = sum(c.volume for c in candles)

        return cumulative_pv / cumulative_volume if cumulative_volume > 0 else 0

    # Momentum Indicators

    def rsi(self, symbol: str, period: int = 14) -> float:
        """Relative Strength Index."""
        closes = self.get_closes(symbol, period + 1)
        if len(closes) < period + 1:
            return 50  # Neutral default

        gains = []
        losses = []

        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    def stochastic(self, symbol: str, k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
        """Stochastic Oscillator (%K, %D)."""
        closes = self.get_closes(symbol, k_period)
        highs = self.get_highs(symbol, k_period)
        lows = self.get_lows(symbol, k_period)

        if len(closes) < k_period:
            return 50, 50

        highest_high = max(highs)
        lowest_low = min(lows)
        current_close = closes[-1]

        if highest_high == lowest_low:
            k = 50
        else:
            k = ((current_close - lowest_low) / (highest_high - lowest_low)) * 100

        # Calculate %D (SMA of %K)
        # Simplified: use current K as D
        d = k  # In practice, you'd calculate SMA of K values

        return k, d

    def cci(self, symbol: str, period: int = 20) -> float:
        """Commodity Channel Index."""
        candles = list(self._candles.get(symbol.upper(), []))[-period:]
        if len(candles) < period:
            return 0

        typical_prices = [(c.high + c.low + c.close) / 3 for c in candles]
        tp_mean = sum(typical_prices) / len(typical_prices)

        mean_deviation = sum(abs(tp - tp_mean) for tp in typical_prices) / len(typical_prices)

        if mean_deviation == 0:
            return 0

        current_tp = typical_prices[-1]
        cci = (current_tp - tp_mean) / (0.015 * mean_deviation)

        return cci

    def williams_r(self, symbol: str, period: int = 14) -> float:
        """Williams %R."""
        closes = self.get_closes(symbol, period)
        highs = self.get_highs(symbol, period)
        lows = self.get_lows(symbol, period)

        if len(closes) < period:
            return -50

        highest_high = max(highs)
        lowest_low = min(lows)
        current_close = closes[-1]

        if highest_high == lowest_low:
            return -50

        wr = ((highest_high - current_close) / (highest_high - lowest_low)) * -100

        return wr

    def momentum(self, symbol: str, period: int = 10) -> float:
        """Price Momentum."""
        closes = self.get_closes(symbol, period + 1)
        if len(closes) < period + 1:
            return 0

        return closes[-1] - closes[-period - 1]

    def roc(self, symbol: str, period: int = 10) -> float:
        """Rate of Change."""
        closes = self.get_closes(symbol, period + 1)
        if len(closes) < period + 1 or closes[-period - 1] == 0:
            return 0

        return ((closes[-1] - closes[-period - 1]) / closes[-period - 1]) * 100

    # MACD

    def macd(self, symbol: str, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, float]:
        """MACD (Moving Average Convergence Divergence)."""
        closes = self.get_closes(symbol, slow + signal)
        if len(closes) < slow:
            return {'macd': 0, 'signal': 0, 'histogram': 0}

        # Calculate EMAs
        fast_ema = self._calculate_ema(closes, fast)
        slow_ema = self._calculate_ema(closes, slow)

        macd_line = fast_ema - slow_ema

        # Signal line (simplified)
        signal_line = macd_line * 0.9  # Simplified

        histogram = macd_line - signal_line

        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }

    def _calculate_ema(self, data: List[float], period: int) -> float:
        """Calculate EMA from data."""
        if len(data) < period:
            return 0

        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period

        for price in data[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))

        return ema

    # Volatility Indicators

    def bollinger_bands(self, symbol: str, period: int = 20, std_dev: float = 2) -> Dict[str, float]:
        """Bollinger Bands."""
        closes = self.get_closes(symbol, period)
        if len(closes) < period:
            return {'upper': 0, 'middle': 0, 'lower': 0, 'bandwidth': 0}

        sma = sum(closes) / len(closes)
        variance = sum((p - sma) ** 2 for p in closes) / len(closes)
        std = math.sqrt(variance)

        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        bandwidth = ((upper - lower) / sma) * 100 if sma > 0 else 0

        return {
            'upper': upper,
            'middle': sma,
            'lower': lower,
            'bandwidth': bandwidth
        }

    def atr(self, symbol: str, period: int = 14) -> float:
        """Average True Range."""
        candles = list(self._candles.get(symbol.upper(), []))[-period - 1:]
        if len(candles) < 2:
            return 0

        true_ranges = []
        for i in range(1, len(candles)):
            current = candles[i]
            prev = candles[i - 1]

            tr = max(
                current.high - current.low,
                abs(current.high - prev.close),
                abs(current.low - prev.close)
            )
            true_ranges.append(tr)

        return sum(true_ranges[-period:]) / min(period, len(true_ranges))

    def volatility(self, symbol: str, period: int = 20) -> float:
        """Historical volatility (standard deviation of returns)."""
        closes = self.get_closes(symbol, period + 1)
        if len(closes) < 2:
            return 0

        returns = []
        for i in range(1, len(closes)):
            if closes[i - 1] > 0:
                ret = (closes[i] - closes[i - 1]) / closes[i - 1]
                returns.append(ret)

        if not returns:
            return 0

        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return math.sqrt(variance) * 100  # As percentage

    # Volume Indicators

    def obv(self, symbol: str) -> float:
        """On-Balance Volume."""
        candles = list(self._candles.get(symbol.upper(), []))
        if len(candles) < 2:
            return 0

        obv = 0
        for i in range(1, len(candles)):
            if candles[i].close > candles[i - 1].close:
                obv += candles[i].volume
            elif candles[i].close < candles[i - 1].close:
                obv -= candles[i].volume

        return obv

    def volume_sma(self, symbol: str, period: int = 20) -> float:
        """Volume Simple Moving Average."""
        volumes = self.get_volumes(symbol, period)
        if not volumes:
            return 0
        return sum(volumes) / len(volumes)

    def volume_ratio(self, symbol: str, period: int = 20) -> float:
        """Current volume vs average volume ratio."""
        volumes = self.get_volumes(symbol, period)
        if len(volumes) < period:
            return 1

        avg_volume = sum(volumes[:-1]) / (len(volumes) - 1)
        current_volume = volumes[-1]

        return current_volume / avg_volume if avg_volume > 0 else 1

    # Trend Indicators

    def adx(self, symbol: str, period: int = 14) -> float:
        """Average Directional Index."""
        candles = list(self._candles.get(symbol.upper(), []))[-period * 2:]
        if len(candles) < period + 1:
            return 0

        plus_dm_list = []
        minus_dm_list = []
        tr_list = []

        for i in range(1, len(candles)):
            current = candles[i]
            prev = candles[i - 1]

            # True Range
            tr = max(
                current.high - current.low,
                abs(current.high - prev.close),
                abs(current.low - prev.close)
            )
            tr_list.append(tr)

            # Directional Movement
            plus_dm = current.high - prev.high if current.high - prev.high > prev.low - current.low else 0
            minus_dm = prev.low - current.low if prev.low - current.low > current.high - prev.high else 0

            plus_dm_list.append(max(plus_dm, 0))
            minus_dm_list.append(max(minus_dm, 0))

        # Smoothed averages
        atr = sum(tr_list[-period:]) / period
        plus_di = (sum(plus_dm_list[-period:]) / period) / atr * 100 if atr > 0 else 0
        minus_di = (sum(minus_dm_list[-period:]) / period) / atr * 100 if atr > 0 else 0

        # ADX
        dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0

        return dx

    def supertrend(self, symbol: str, period: int = 10, multiplier: float = 3) -> Dict[str, Any]:
        """SuperTrend indicator."""
        candles = list(self._candles.get(symbol.upper(), []))[-period * 2:]
        if len(candles) < period:
            return {'value': 0, 'direction': 'neutral'}

        atr = self.atr(symbol, period)
        current = candles[-1]
        hl2 = (current.high + current.low) / 2

        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)

        if current.close > upper_band:
            return {'value': lower_band, 'direction': 'bullish'}
        elif current.close < lower_band:
            return {'value': upper_band, 'direction': 'bearish'}
        else:
            return {'value': hl2, 'direction': 'neutral'}

    # Support/Resistance

    def pivot_points(self, symbol: str) -> Dict[str, float]:
        """Calculate pivot points."""
        candles = list(self._candles.get(symbol.upper(), []))
        if not candles:
            return {}

        # Use last candle for calculation
        last = candles[-1]
        h, l, c = last.high, last.low, last.close

        pivot = (h + l + c) / 3
        r1 = 2 * pivot - l
        r2 = pivot + (h - l)
        r3 = r1 + (h - l)
        s1 = 2 * pivot - h
        s2 = pivot - (h - l)
        s3 = s1 - (h - l)

        return {
            'pivot': pivot,
            'r1': r1, 'r2': r2, 'r3': r3,
            's1': s1, 's2': s2, 's3': s3
        }

    def support_resistance(self, symbol: str, lookback: int = 50) -> Tuple[List[float], List[float]]:
        """Find support and resistance levels."""
        highs = self.get_highs(symbol, lookback)
        lows = self.get_lows(symbol, lookback)

        if not highs or not lows:
            return [], []

        # Simple approach: find local maxima and minima
        resistance_levels = []
        support_levels = []

        for i in range(2, len(highs) - 2):
            if highs[i] > highs[i - 1] and highs[i] > highs[i - 2] and \
               highs[i] > highs[i + 1] and highs[i] > highs[i + 2]:
                resistance_levels.append(highs[i])

            if lows[i] < lows[i - 1] and lows[i] < lows[i - 2] and \
               lows[i] < lows[i + 1] and lows[i] < lows[i + 2]:
                support_levels.append(lows[i])

        # Cluster nearby levels
        resistance_levels = self._cluster_levels(resistance_levels)
        support_levels = self._cluster_levels(support_levels)

        return support_levels[:5], resistance_levels[:5]

    def _cluster_levels(self, levels: List[float], threshold: float = 0.02) -> List[float]:
        """Cluster nearby price levels."""
        if not levels:
            return []

        levels = sorted(levels)
        clusters = []
        current_cluster = [levels[0]]

        for level in levels[1:]:
            if abs(level - current_cluster[-1]) / current_cluster[-1] < threshold:
                current_cluster.append(level)
            else:
                clusters.append(sum(current_cluster) / len(current_cluster))
                current_cluster = [level]

        if current_cluster:
            clusters.append(sum(current_cluster) / len(current_cluster))

        return clusters

    # Full Analysis

    def analyze(self, symbol: str) -> TechnicalAnalysis:
        """Perform complete technical analysis."""
        symbol = symbol.upper()
        closes = self.get_closes(symbol)
        if not closes:
            return TechnicalAnalysis(
                symbol=symbol,
                timestamp=datetime.now(timezone.utc).isoformat(),
                price=0,
                trend=TrendDirection.NEUTRAL,
                overall_signal=SignalType.NEUTRAL,
                indicators={},
                support_levels=[],
                resistance_levels=[],
                pivot_points={},
                summary="Insufficient data"
            )

        current_price = closes[-1]
        indicators = {}

        # RSI
        rsi_val = self.rsi(symbol)
        rsi_signal = SignalType.NEUTRAL
        if rsi_val < 30:
            rsi_signal = SignalType.STRONG_BUY
        elif rsi_val < 40:
            rsi_signal = SignalType.BUY
        elif rsi_val > 70:
            rsi_signal = SignalType.STRONG_SELL
        elif rsi_val > 60:
            rsi_signal = SignalType.SELL

        indicators['rsi'] = IndicatorResult(
            name='RSI',
            value=rsi_val,
            signal=rsi_signal,
            interpretation=f"RSI at {rsi_val:.1f}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        # MACD
        macd_data = self.macd(symbol)
        macd_signal = SignalType.NEUTRAL
        if macd_data['histogram'] > 0:
            macd_signal = SignalType.BUY if macd_data['macd'] > 0 else SignalType.NEUTRAL
        else:
            macd_signal = SignalType.SELL if macd_data['macd'] < 0 else SignalType.NEUTRAL

        indicators['macd'] = IndicatorResult(
            name='MACD',
            value=macd_data['macd'],
            signal=macd_signal,
            interpretation=f"MACD: {macd_data['macd']:.4f}, Histogram: {macd_data['histogram']:.4f}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        # Moving Averages
        sma_20 = self.sma(symbol, 20)
        sma_50 = self.sma(symbol, 50)
        ema_12 = self.ema(symbol, 12)

        ma_signal = SignalType.NEUTRAL
        if current_price > sma_20 and current_price > sma_50:
            ma_signal = SignalType.BUY
        elif current_price < sma_20 and current_price < sma_50:
            ma_signal = SignalType.SELL

        indicators['sma_20'] = IndicatorResult(
            name='SMA 20',
            value=sma_20,
            signal=ma_signal,
            interpretation=f"SMA(20): {sma_20:.4f}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        # Bollinger Bands
        bb = self.bollinger_bands(symbol)
        bb_signal = SignalType.NEUTRAL
        if current_price < bb['lower']:
            bb_signal = SignalType.BUY
        elif current_price > bb['upper']:
            bb_signal = SignalType.SELL

        indicators['bollinger'] = IndicatorResult(
            name='Bollinger Bands',
            value=bb['bandwidth'],
            signal=bb_signal,
            interpretation=f"Price vs BB: Lower={bb['lower']:.4f}, Upper={bb['upper']:.4f}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        # ADX
        adx_val = self.adx(symbol)
        indicators['adx'] = IndicatorResult(
            name='ADX',
            value=adx_val,
            signal=SignalType.NEUTRAL,
            interpretation=f"Trend strength: {'Strong' if adx_val > 25 else 'Weak'}",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

        # Determine overall trend
        trend = TrendDirection.NEUTRAL
        if current_price > sma_20 > sma_50 and rsi_val > 50:
            trend = TrendDirection.BULLISH if adx_val < 40 else TrendDirection.STRONG_BULLISH
        elif current_price < sma_20 < sma_50 and rsi_val < 50:
            trend = TrendDirection.BEARISH if adx_val < 40 else TrendDirection.STRONG_BEARISH

        # Overall signal
        buy_signals = sum(1 for ind in indicators.values() if ind.signal in [SignalType.BUY, SignalType.STRONG_BUY])
        sell_signals = sum(1 for ind in indicators.values() if ind.signal in [SignalType.SELL, SignalType.STRONG_SELL])

        if buy_signals >= 3:
            overall_signal = SignalType.STRONG_BUY if buy_signals >= 4 else SignalType.BUY
        elif sell_signals >= 3:
            overall_signal = SignalType.STRONG_SELL if sell_signals >= 4 else SignalType.SELL
        else:
            overall_signal = SignalType.NEUTRAL

        # Support/Resistance
        support, resistance = self.support_resistance(symbol)
        pivots = self.pivot_points(symbol)

        # Summary
        summary = f"{symbol} is {trend.value.replace('_', ' ')}. "
        summary += f"RSI: {rsi_val:.1f}, MACD: {'bullish' if macd_data['histogram'] > 0 else 'bearish'}. "
        summary += f"Signal: {overall_signal.value.replace('_', ' ').upper()}"

        return TechnicalAnalysis(
            symbol=symbol,
            timestamp=datetime.now(timezone.utc).isoformat(),
            price=current_price,
            trend=trend,
            overall_signal=overall_signal,
            indicators=indicators,
            support_levels=support,
            resistance_levels=resistance,
            pivot_points=pivots,
            summary=summary
        )


# Singleton
_indicators: Optional[TechnicalIndicators] = None


def get_technical_indicators() -> TechnicalIndicators:
    """Get singleton technical indicators calculator."""
    global _indicators
    if _indicators is None:
        _indicators = TechnicalIndicators()
    return _indicators
