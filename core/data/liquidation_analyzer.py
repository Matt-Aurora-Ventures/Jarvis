"""
Liquidation Analyzer - Support/Resistance and Liquidation Level Analysis
=========================================================================

Analyzes liquidation levels and price support/resistance:
- Support wall detection (buy pressure)
- Resistance wall detection (sell pressure)
- Liquidation heatmap generation
- Integration with Solend/Marinade lending data (future)

Key Concepts:
- Support: Price levels where buy orders cluster (floor)
- Resistance: Price levels where sell orders cluster (ceiling)
- Liquidation: Forced position closes at specific prices

Usage:
    from core.data.liquidation_analyzer import get_liquidation_analyzer

    analyzer = get_liquidation_analyzer()
    analysis = await analyzer.analyze_liquidation_levels("SOL")
    heatmap = await analyzer.get_liquidation_heatmap("SOL")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try importing price API
try:
    from core.data.free_price_api import get_free_price_api, FreePriceAPI
    HAS_PRICE_API = True
except ImportError:
    HAS_PRICE_API = False

# Common support/resistance levels (Fibonacci retracements)
FIBONACCI_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]

# Psychological price levels (round numbers)
PSYCHOLOGICAL_DIVISORS = [1, 5, 10, 25, 50, 100]


@dataclass
class LiquidationLevel:
    """A single liquidation/support/resistance level."""
    price: float
    amount_usd: float = 0.0
    level_type: str = "support"  # "support", "resistance", "liquidation"
    strength: float = 0.0  # 0.0 to 1.0
    source: str = "calculated"  # "calculated", "orderbook", "lending"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LiquidationAnalysis:
    """Complete liquidation level analysis."""
    token: str
    current_price: float = 0.0
    support_walls: List[LiquidationLevel] = field(default_factory=list)
    resistance_walls: List[LiquidationLevel] = field(default_factory=list)
    conviction: float = 0.0  # 0.0 to 1.0 - confidence in the analysis
    nearest_support: Optional[float] = None
    nearest_resistance: Optional[float] = None
    risk_reward_ratio: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

        # Calculate nearest levels
        if self.support_walls and self.current_price > 0:
            valid_supports = [s for s in self.support_walls if s.price < self.current_price]
            if valid_supports:
                self.nearest_support = max(s.price for s in valid_supports)

        if self.resistance_walls and self.current_price > 0:
            valid_resistances = [r for r in self.resistance_walls if r.price > self.current_price]
            if valid_resistances:
                self.nearest_resistance = min(r.price for r in valid_resistances)

        # Calculate risk/reward ratio
        if self.nearest_support and self.nearest_resistance and self.current_price > 0:
            risk = self.current_price - self.nearest_support
            reward = self.nearest_resistance - self.current_price
            if risk > 0:
                self.risk_reward_ratio = round(reward / risk, 2)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "token": self.token,
            "current_price": self.current_price,
            "support_walls": [s.to_dict() for s in self.support_walls],
            "resistance_walls": [r.to_dict() for r in self.resistance_walls],
            "conviction": self.conviction,
            "nearest_support": self.nearest_support,
            "nearest_resistance": self.nearest_resistance,
            "risk_reward_ratio": self.risk_reward_ratio,
            "timestamp": self.timestamp,
        }
        return result


class LiquidationAnalyzer:
    """
    Analyzes liquidation levels and support/resistance.

    Methods:
    - analyze_liquidation_levels: Complete level analysis
    - get_liquidation_heatmap: Visual heatmap data
    - _calculate_support_levels: Fibonacci + psychological supports
    - _calculate_resistance_levels: Fibonacci + psychological resistances
    """

    _instance: Optional["LiquidationAnalyzer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._price_api = get_free_price_api() if HAS_PRICE_API else None
        self._initialized = True
        logger.info("LiquidationAnalyzer initialized")

    async def _get_price_data(self, token: str) -> Dict[str, Any]:
        """
        Get current price data for token.

        Args:
            token: Token symbol or address

        Returns:
            Price data dict with price, high, low
        """
        if not self._price_api:
            return {"price": 0.0, "24h_high": 0.0, "24h_low": 0.0}

        try:
            # Try to get price from free API
            price_info = await self._price_api.get_price(token)
            if price_info:
                return {
                    "price": price_info.price,
                    "24h_high": price_info.high_24h or price_info.price * 1.05,
                    "24h_low": price_info.low_24h or price_info.price * 0.95,
                }
        except Exception as e:
            logger.warning(f"Failed to get price data: {e}")

        return {"price": 0.0, "24h_high": 0.0, "24h_low": 0.0}

    def _calculate_support_levels(
        self,
        current_price: float,
        low_24h: Optional[float] = None,
    ) -> List[LiquidationLevel]:
        """
        Calculate support levels using Fibonacci and psychological levels.

        Args:
            current_price: Current token price
            low_24h: 24-hour low price

        Returns:
            List of support LiquidationLevel
        """
        supports = []

        if current_price <= 0:
            return supports

        # Use 24h low as reference, or estimate
        reference_low = low_24h or current_price * 0.90

        # Calculate Fibonacci retracement levels from low to current
        price_range = current_price - reference_low
        for fib in FIBONACCI_LEVELS:
            fib_price = current_price - (price_range * fib)
            if fib_price > 0 and fib_price < current_price:
                supports.append(LiquidationLevel(
                    price=round(fib_price, 4),
                    amount_usd=0,  # Would need orderbook data
                    level_type="support",
                    strength=fib,  # Higher fib = stronger support
                    source="fibonacci",
                ))

        # Add psychological levels (round numbers)
        base_price = int(current_price)
        for divisor in PSYCHOLOGICAL_DIVISORS:
            if divisor > base_price:
                continue
            psych_price = (base_price // divisor) * divisor
            if psych_price > 0 and psych_price < current_price:
                # Check if already in list
                existing = [s for s in supports if abs(s.price - psych_price) < 0.01]
                if not existing:
                    supports.append(LiquidationLevel(
                        price=float(psych_price),
                        amount_usd=0,
                        level_type="support",
                        strength=0.5,
                        source="psychological",
                    ))

        # Sort by price descending (nearest support first)
        supports.sort(key=lambda x: x.price, reverse=True)

        return supports[:5]  # Return top 5 supports

    def _calculate_resistance_levels(
        self,
        current_price: float,
        high_24h: Optional[float] = None,
    ) -> List[LiquidationLevel]:
        """
        Calculate resistance levels using Fibonacci and psychological levels.

        Args:
            current_price: Current token price
            high_24h: 24-hour high price

        Returns:
            List of resistance LiquidationLevel
        """
        resistances = []

        if current_price <= 0:
            return resistances

        # Use 24h high as reference, or estimate
        reference_high = high_24h or current_price * 1.10

        # Calculate Fibonacci extension levels from current to high
        price_range = reference_high - current_price
        for fib in FIBONACCI_LEVELS:
            fib_price = current_price + (price_range * fib)
            if fib_price > current_price:
                resistances.append(LiquidationLevel(
                    price=round(fib_price, 4),
                    amount_usd=0,
                    level_type="resistance",
                    strength=1 - fib,  # Lower fib = stronger resistance (closer)
                    source="fibonacci",
                ))

        # Add psychological levels (round numbers)
        base_price = int(current_price) + 1
        for divisor in PSYCHOLOGICAL_DIVISORS:
            psych_price = ((base_price // divisor) + 1) * divisor
            if psych_price > current_price:
                # Check if already in list
                existing = [r for r in resistances if abs(r.price - psych_price) < 0.01]
                if not existing:
                    resistances.append(LiquidationLevel(
                        price=float(psych_price),
                        amount_usd=0,
                        level_type="resistance",
                        strength=0.5,
                        source="psychological",
                    ))

        # Sort by price ascending (nearest resistance first)
        resistances.sort(key=lambda x: x.price)

        return resistances[:5]  # Return top 5 resistances

    async def analyze_liquidation_levels(
        self,
        token: str,
    ) -> LiquidationAnalysis:
        """
        Analyze liquidation levels for a token.

        Args:
            token: Token symbol or address

        Returns:
            LiquidationAnalysis with support/resistance walls
        """
        # Get price data
        price_data = await self._get_price_data(token)
        current_price = price_data.get("price", 0)

        if current_price <= 0:
            logger.warning(f"Could not get price for {token}")
            return LiquidationAnalysis(
                token=token,
                current_price=0,
                conviction=0.0,
            )

        # Calculate support and resistance levels
        supports = self._calculate_support_levels(
            current_price,
            low_24h=price_data.get("24h_low"),
        )

        resistances = self._calculate_resistance_levels(
            current_price,
            high_24h=price_data.get("24h_high"),
        )

        # Calculate conviction based on data quality
        conviction = 0.5  # Base conviction for calculated levels
        if price_data.get("24h_high") and price_data.get("24h_low"):
            conviction = 0.7  # Higher if we have actual range data

        return LiquidationAnalysis(
            token=token,
            current_price=current_price,
            support_walls=supports,
            resistance_walls=resistances,
            conviction=conviction,
        )

    async def get_liquidation_heatmap(
        self,
        token: str,
        price_range_pct: float = 10.0,
        num_levels: int = 20,
    ) -> Dict[str, Any]:
        """
        Generate liquidation heatmap data.

        Args:
            token: Token symbol or address
            price_range_pct: Price range to analyze (%)
            num_levels: Number of price levels in heatmap

        Returns:
            Heatmap data dict
        """
        # Get analysis
        analysis = await self.analyze_liquidation_levels(token)

        if analysis.current_price <= 0:
            return {
                "token": token,
                "levels": [],
                "error": "Could not get price data",
            }

        # Generate heatmap levels
        price_step = (analysis.current_price * price_range_pct / 100) / (num_levels / 2)
        min_price = analysis.current_price * (1 - price_range_pct / 100)
        max_price = analysis.current_price * (1 + price_range_pct / 100)

        heatmap_levels = []
        current = min_price

        while current <= max_price:
            # Determine intensity based on proximity to S/R levels
            intensity = 0.0

            # Check if near support
            for support in analysis.support_walls:
                if abs(current - support.price) / analysis.current_price < 0.01:
                    intensity = max(intensity, support.strength)

            # Check if near resistance
            for resistance in analysis.resistance_walls:
                if abs(current - resistance.price) / analysis.current_price < 0.01:
                    intensity = max(intensity, resistance.strength)

            heatmap_levels.append({
                "price": round(current, 4),
                "intensity": round(intensity, 2),
                "type": "support" if current < analysis.current_price else "resistance",
            })

            current += price_step

        return {
            "token": token,
            "current_price": analysis.current_price,
            "levels": heatmap_levels,
            "conviction": analysis.conviction,
            "timestamp": analysis.timestamp,
        }

    def get_trading_signal(
        self,
        analysis: LiquidationAnalysis,
    ) -> Dict[str, Any]:
        """
        Generate trading signal from liquidation analysis.

        Args:
            analysis: LiquidationAnalysis result

        Returns:
            Trading signal dict
        """
        signal = {
            "token": analysis.token,
            "direction": "neutral",
            "strength": 0.0,
            "stop_loss": None,
            "take_profit": None,
            "conviction": analysis.conviction,
        }

        if analysis.current_price <= 0:
            return signal

        # Determine signal based on risk/reward ratio
        if analysis.risk_reward_ratio >= 2.0:
            signal["direction"] = "long"
            signal["strength"] = min(1.0, analysis.risk_reward_ratio / 3.0)
            signal["stop_loss"] = analysis.nearest_support
            signal["take_profit"] = analysis.nearest_resistance
        elif analysis.risk_reward_ratio <= 0.5:
            signal["direction"] = "short"
            signal["strength"] = min(1.0, 1.0 / (analysis.risk_reward_ratio + 0.1))
            signal["stop_loss"] = analysis.nearest_resistance
            signal["take_profit"] = analysis.nearest_support

        return signal


# Singleton accessor
def get_liquidation_analyzer() -> LiquidationAnalyzer:
    """Get the LiquidationAnalyzer singleton instance."""
    return LiquidationAnalyzer()


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)

    async def test():
        print("=== Liquidation Analyzer Test ===")

        analyzer = get_liquidation_analyzer()

        # Test analysis
        print("\n--- Analyzing SOL ---")
        analysis = await analyzer.analyze_liquidation_levels("SOL")
        print(f"Current Price: ${analysis.current_price:.2f}")
        print(f"Conviction: {analysis.conviction:.2f}")

        print("\nSupport Walls:")
        for s in analysis.support_walls[:3]:
            print(f"  ${s.price:.2f} (strength: {s.strength:.2f}, source: {s.source})")

        print("\nResistance Walls:")
        for r in analysis.resistance_walls[:3]:
            print(f"  ${r.price:.2f} (strength: {r.strength:.2f}, source: {r.source})")

        print(f"\nNearest Support: ${analysis.nearest_support:.2f if analysis.nearest_support else 'N/A'}")
        print(f"Nearest Resistance: ${analysis.nearest_resistance:.2f if analysis.nearest_resistance else 'N/A'}")
        print(f"Risk/Reward Ratio: {analysis.risk_reward_ratio:.2f}")

        # Get trading signal
        signal = analyzer.get_trading_signal(analysis)
        print(f"\nTrading Signal: {signal['direction']} (strength: {signal['strength']:.2f})")

    asyncio.run(test())
