"""
Trading Strategies Module for Life OS Bot
==========================================

Implements core algorithmic trading strategies:
- TrendFollower: Moving average crossover
- MeanReversion: Bollinger Bands + RSI
- DCABot: Dollar-cost averaging automation
- ArbitrageScanner: Cross-DEX price detection
- SentimentAnalyzer: NLP sentiment hooks

Usage:
    from core.trading_strategies import TrendFollower, MeanReversion
    
    strategy = TrendFollower(short_period=9, long_period=21)
    signal = strategy.analyze(price_history)
"""

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class TradeSignal:
    """Represents a trading signal from a strategy."""
    action: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 to 1.0
    strategy: str
    symbol: str
    price: float
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "confidence": self.confidence,
            "strategy": self.strategy,
            "symbol": self.symbol,
            "price": self.price,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""
    
    name: str = "BaseStrategy"
    
    @abstractmethod
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        """Analyze price data and return a trading signal."""
        pass
    
    def _calculate_sma(self, prices: List[float], period: int) -> float:
        """Calculate Simple Moving Average."""
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        return sum(prices[-period:]) / period
    
    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Calculate Exponential Moving Average."""
        if len(prices) < period:
            return prices[-1] if prices else 0.0
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema
    
    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Calculate Relative Strength Index."""
        if len(prices) < period + 1:
            return 50.0  # Neutral
        
        gains = []
        losses = []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i - 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_bollinger_bands(
        self, prices: List[float], period: int = 20, std_dev: float = 2.0
    ) -> Tuple[float, float, float]:
        """Calculate Bollinger Bands (upper, middle, lower)."""
        if len(prices) < period:
            middle = prices[-1] if prices else 0
            return middle, middle, middle
        
        middle = self._calculate_sma(prices, period)
        
        # Calculate standard deviation
        squared_diff_sum = sum((p - middle) ** 2 for p in prices[-period:])
        std = (squared_diff_sum / period) ** 0.5
        
        upper = middle + (std_dev * std)
        lower = middle - (std_dev * std)
        
        return upper, middle, lower


class TrendFollower(BaseStrategy):
    """
    Trend Following Strategy using Moving Average Crossover.
    
    Generates BUY when short MA crosses above long MA (golden cross).
    Generates SELL when short MA crosses below long MA (death cross).
    """
    
    name = "TrendFollower"
    
    def __init__(self, short_period: int = 9, long_period: int = 21, use_ema: bool = False):
        self.short_period = short_period
        self.long_period = long_period
        self.use_ema = use_ema
        self._prev_short: Optional[float] = None
        self._prev_long: Optional[float] = None
    
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        if len(prices) < self.long_period:
            return TradeSignal(
                action="HOLD",
                confidence=0.0,
                strategy=self.name,
                symbol=symbol,
                price=prices[-1] if prices else 0.0,
                metadata={"reason": "Insufficient data"}
            )
        
        calc_fn = self._calculate_ema if self.use_ema else self._calculate_sma
        short_ma = calc_fn(prices, self.short_period)
        long_ma = calc_fn(prices, self.long_period)
        current_price = prices[-1]
        
        action = "HOLD"
        confidence = 0.0
        reason = "No crossover detected"
        
        # Detect crossover
        if self._prev_short is not None and self._prev_long is not None:
            # Golden cross (bullish)
            if self._prev_short <= self._prev_long and short_ma > long_ma:
                action = "BUY"
                confidence = min(0.9, (short_ma - long_ma) / long_ma * 10)
                reason = "Golden cross detected"
            # Death cross (bearish)
            elif self._prev_short >= self._prev_long and short_ma < long_ma:
                action = "SELL"
                confidence = min(0.9, (long_ma - short_ma) / long_ma * 10)
                reason = "Death cross detected"
            # Trend continuation
            elif short_ma > long_ma:
                action = "HOLD"
                confidence = 0.3
                reason = "Uptrend continuation"
            else:
                action = "HOLD"
                confidence = 0.3
                reason = "Downtrend continuation"
        
        self._prev_short = short_ma
        self._prev_long = long_ma
        
        return TradeSignal(
            action=action,
            confidence=confidence,
            strategy=self.name,
            symbol=symbol,
            price=current_price,
            metadata={
                "short_ma": round(short_ma, 4),
                "long_ma": round(long_ma, 4),
                "reason": reason
            }
        )


class MeanReversion(BaseStrategy):
    """
    Mean Reversion Strategy using Bollinger Bands + RSI.
    
    BUY when price below lower band AND RSI < 30 (oversold).
    SELL when price above upper band AND RSI > 70 (overbought).
    """
    
    name = "MeanReversion"
    
    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_oversold: float = 30.0,
        rsi_overbought: float = 70.0
    ):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
    
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        min_data = max(self.bb_period, self.rsi_period + 1)
        if len(prices) < min_data:
            return TradeSignal(
                action="HOLD",
                confidence=0.0,
                strategy=self.name,
                symbol=symbol,
                price=prices[-1] if prices else 0.0,
                metadata={"reason": "Insufficient data"}
            )
        
        current_price = prices[-1]
        upper, middle, lower = self._calculate_bollinger_bands(
            prices, self.bb_period, self.bb_std
        )
        rsi = self._calculate_rsi(prices, self.rsi_period)
        
        action = "HOLD"
        confidence = 0.0
        reason = "Price within normal range"
        
        # Oversold condition
        if current_price < lower and rsi < self.rsi_oversold:
            action = "BUY"
            # Higher confidence for more extreme conditions
            confidence = min(0.95, 0.5 + (self.rsi_oversold - rsi) / 100)
            reason = f"Oversold: Price below BB, RSI={rsi:.1f}"
        
        # Overbought condition
        elif current_price > upper and rsi > self.rsi_overbought:
            action = "SELL"
            confidence = min(0.95, 0.5 + (rsi - self.rsi_overbought) / 100)
            reason = f"Overbought: Price above BB, RSI={rsi:.1f}"
        
        # Approaching oversold
        elif current_price < middle and rsi < 40:
            action = "HOLD"
            confidence = 0.2
            reason = "Approaching oversold"
        
        # Approaching overbought
        elif current_price > middle and rsi > 60:
            action = "HOLD"
            confidence = 0.2
            reason = "Approaching overbought"
        
        return TradeSignal(
            action=action,
            confidence=confidence,
            strategy=self.name,
            symbol=symbol,
            price=current_price,
            metadata={
                "rsi": round(rsi, 2),
                "bb_upper": round(upper, 4),
                "bb_middle": round(middle, 4),
                "bb_lower": round(lower, 4),
                "reason": reason
            }
        )


class DCABot(BaseStrategy):
    """
    Dollar-Cost Averaging Bot.
    
    Generates BUY signals at regular intervals regardless of price.
    Optionally can enhance with "smart DCA" to buy more when prices dip.
    """
    
    name = "DCABot"
    
    def __init__(
        self,
        interval_hours: float = 24.0,
        smart_dca: bool = True,
        dip_threshold: float = 0.05  # 5% below average = buy more
    ):
        self.interval_hours = interval_hours
        self.smart_dca = smart_dca
        self.dip_threshold = dip_threshold
        self._last_buy_time: float = 0.0
        self._price_history: List[float] = []
    
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        current_price = prices[-1] if prices else 0.0
        current_time = time.time()
        
        # Track price history for smart DCA
        self._price_history.append(current_price)
        if len(self._price_history) > 100:
            self._price_history = self._price_history[-100:]
        
        # Check if interval has passed
        hours_since_last = (current_time - self._last_buy_time) / 3600
        
        if hours_since_last < self.interval_hours:
            return TradeSignal(
                action="HOLD",
                confidence=0.0,
                strategy=self.name,
                symbol=symbol,
                price=current_price,
                metadata={
                    "hours_until_next": round(self.interval_hours - hours_since_last, 2),
                    "reason": "Waiting for next interval"
                }
            )
        
        # Time to DCA
        confidence = 0.7
        multiplier = 1.0
        reason = "Regular DCA interval"
        
        if self.smart_dca and len(self._price_history) > 10:
            avg_price = sum(self._price_history) / len(self._price_history)
            deviation = (avg_price - current_price) / avg_price
            
            if deviation > self.dip_threshold:
                # Price is significantly below average, buy more
                multiplier = 1.0 + deviation
                confidence = 0.85
                reason = f"Smart DCA: {deviation*100:.1f}% below avg, multiplier={multiplier:.2f}x"
            elif deviation < -self.dip_threshold:
                # Price is significantly above average, buy less
                multiplier = max(0.5, 1.0 + deviation)  # Still buy, just less
                confidence = 0.6
                reason = f"Smart DCA: {abs(deviation)*100:.1f}% above avg, multiplier={multiplier:.2f}x"
        
        self._last_buy_time = current_time
        
        return TradeSignal(
            action="BUY",
            confidence=confidence,
            strategy=self.name,
            symbol=symbol,
            price=current_price,
            metadata={
                "multiplier": round(multiplier, 2),
                "reason": reason
            }
        )


class ArbitrageScanner(BaseStrategy):
    """
    Cross-DEX Arbitrage Scanner.
    
    Compares prices across multiple DEXs to find profitable spreads.
    """
    
    name = "ArbitrageScanner"
    
    def __init__(
        self,
        min_spread_pct: float = 0.5,  # Minimum 0.5% spread to trade
        max_slippage_pct: float = 0.3  # Account for slippage
    ):
        self.min_spread_pct = min_spread_pct
        self.max_slippage_pct = max_slippage_pct
    
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        """
        For single-exchange use. See scan_multi_dex for cross-exchange.
        """
        return TradeSignal(
            action="HOLD",
            confidence=0.0,
            strategy=self.name,
            symbol=symbol,
            price=prices[-1] if prices else 0.0,
            metadata={"reason": "Use scan_multi_dex for arbitrage detection"}
        )
    
    def scan_multi_dex(
        self,
        symbol: str,
        dex_prices: Dict[str, float]
    ) -> Optional[TradeSignal]:
        """
        Scan multiple DEX prices for arbitrage opportunities.
        
        Args:
            symbol: Trading pair (e.g., "ETH/USDC")
            dex_prices: Dict of DEX name -> price
        
        Returns:
            TradeSignal if opportunity found, None otherwise
        """
        if len(dex_prices) < 2:
            return None
        
        # Find best buy (lowest) and sell (highest) venues
        sorted_dexes = sorted(dex_prices.items(), key=lambda x: x[1])
        buy_dex, buy_price = sorted_dexes[0]
        sell_dex, sell_price = sorted_dexes[-1]
        
        # Calculate spread
        spread_pct = ((sell_price - buy_price) / buy_price) * 100
        net_spread = spread_pct - self.max_slippage_pct
        
        if net_spread < self.min_spread_pct:
            return None
        
        return TradeSignal(
            action="BUY",  # Buy on cheaper DEX
            confidence=min(0.95, net_spread / 5),  # Higher spread = higher confidence
            strategy=self.name,
            symbol=symbol,
            price=buy_price,
            metadata={
                "buy_dex": buy_dex,
                "buy_price": buy_price,
                "sell_dex": sell_dex,
                "sell_price": sell_price,
                "gross_spread_pct": round(spread_pct, 3),
                "net_spread_pct": round(net_spread, 3),
                "reason": f"Arb: Buy on {buy_dex}, Sell on {sell_dex}"
            }
        )


class SentimentAnalyzer(BaseStrategy):
    """
    Sentiment Analysis Strategy (hooks for NLP integration).
    
    Designed to integrate with the Life OS router for AI-powered sentiment.
    """
    
    name = "SentimentAnalyzer"
    
    def __init__(self, bullish_threshold: float = 0.6, bearish_threshold: float = 0.4):
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold
        self._last_sentiment: Optional[Dict[str, Any]] = None
    
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        """
        Use analyze_with_sentiment for full functionality.
        """
        return TradeSignal(
            action="HOLD",
            confidence=0.0,
            strategy=self.name,
            symbol=symbol,
            price=prices[-1] if prices else 0.0,
            metadata={"reason": "Call analyze_with_sentiment with sentiment data"}
        )
    
    def analyze_with_sentiment(
        self,
        prices: List[float],
        symbol: str,
        sentiment_score: float,  # -1.0 (bearish) to 1.0 (bullish)
        sentiment_sources: Optional[Dict[str, float]] = None
    ) -> TradeSignal:
        """
        Analyze with sentiment data.
        
        Args:
            prices: Historical prices
            symbol: Trading pair
            sentiment_score: Aggregate sentiment (-1 to 1)
            sentiment_sources: Optional breakdown by source
        """
        current_price = prices[-1] if prices else 0.0
        
        # Normalize to 0-1 range
        normalized = (sentiment_score + 1) / 2
        
        action = "HOLD"
        confidence = 0.0
        
        if normalized > self.bullish_threshold:
            action = "BUY"
            confidence = min(0.8, (normalized - self.bullish_threshold) * 2)
        elif normalized < self.bearish_threshold:
            action = "SELL"
            confidence = min(0.8, (self.bearish_threshold - normalized) * 2)
        
        self._last_sentiment = {
            "score": sentiment_score,
            "normalized": normalized,
            "sources": sentiment_sources or {}
        }
        
        return TradeSignal(
            action=action,
            confidence=confidence,
            strategy=self.name,
            symbol=symbol,
            price=current_price,
            metadata={
                "sentiment_score": round(sentiment_score, 3),
                "sentiment_normalized": round(normalized, 3),
                "sources": sentiment_sources or {},
                "reason": f"Sentiment: {sentiment_score:.2f}"
            }
        )


# ============================================================================
# Strategy Ensemble
# ============================================================================

class StrategyEnsemble:
    """
    Combine multiple strategies with weighted voting.
    """
    
    def __init__(self, strategies: Optional[List[Tuple[BaseStrategy, float]]] = None):
        """
        Args:
            strategies: List of (strategy, weight) tuples
        """
        self.strategies = strategies or []
    
    def add_strategy(self, strategy: BaseStrategy, weight: float = 1.0) -> None:
        self.strategies.append((strategy, weight))
    
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        """Get weighted consensus from all strategies."""
        if not self.strategies:
            return TradeSignal(
                action="HOLD",
                confidence=0.0,
                strategy="Ensemble",
                symbol=symbol,
                price=prices[-1] if prices else 0.0,
                metadata={"reason": "No strategies configured"}
            )
        
        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0
        signals = []
        
        for strategy, weight in self.strategies:
            signal = strategy.analyze(prices, symbol)
            signals.append(signal.to_dict())
            
            if signal.action == "BUY":
                buy_score += signal.confidence * weight
            elif signal.action == "SELL":
                sell_score += signal.confidence * weight
            
            total_weight += weight
        
        # Determine consensus
        if total_weight > 0:
            buy_score /= total_weight
            sell_score /= total_weight
        
        if buy_score > sell_score and buy_score > 0.3:
            action = "BUY"
            confidence = buy_score
        elif sell_score > buy_score and sell_score > 0.3:
            action = "SELL"
            confidence = sell_score
        else:
            action = "HOLD"
            confidence = 1.0 - max(buy_score, sell_score)
        
        return TradeSignal(
            action=action,
            confidence=confidence,
            strategy="Ensemble",
            symbol=symbol,
            price=prices[-1] if prices else 0.0,
            metadata={
                "buy_score": round(buy_score, 3),
                "sell_score": round(sell_score, 3),
                "component_signals": signals
            }
        )


# ============================================================================
# Factory and utilities
# ============================================================================

def create_default_ensemble() -> StrategyEnsemble:
    """Create a default ensemble with common strategies."""
    ensemble = StrategyEnsemble()
    ensemble.add_strategy(TrendFollower(short_period=9, long_period=21), weight=1.0)
    ensemble.add_strategy(MeanReversion(), weight=0.8)
    return ensemble


if __name__ == "__main__":
    # Demo
    import random
    
    # Generate sample price data with trend
    prices = [100.0]
    for _ in range(50):
        change = random.uniform(-2, 2.5)  # Slight upward bias
        prices.append(prices[-1] + change)
    
    print("=== Trading Strategies Demo ===\n")
    
    # Test each strategy
    strategies = [
        TrendFollower(),
        MeanReversion(),
        DCABot(interval_hours=0.001),  # Immediate for demo
        ArbitrageScanner(),
    ]
    
    for strategy in strategies:
        signal = strategy.analyze(prices, symbol="BTC/USDT")
        print(f"{strategy.name}:")
        print(f"  Action: {signal.action}, Confidence: {signal.confidence:.2f}")
        print(f"  Metadata: {signal.metadata}\n")
    
    # Test arbitrage scanner
    print("=== Arbitrage Scanner Demo ===")
    arb = ArbitrageScanner()
    dex_prices = {
        "Uniswap": 2000.00,
        "Sushiswap": 2015.50,
        "Curve": 2002.00
    }
    arb_signal = arb.scan_multi_dex("ETH/USDC", dex_prices)
    if arb_signal:
        print(f"  Opportunity found!")
        print(f"  {arb_signal.metadata}")
    
    # Test ensemble
    print("\n=== Ensemble Demo ===")
    ensemble = create_default_ensemble()
    signal = ensemble.analyze(prices, symbol="BTC/USDT")
    print(f"Ensemble: {signal.action}, Confidence: {signal.confidence:.2f}")
