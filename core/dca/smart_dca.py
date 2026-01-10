"""
Smart DCA System

Intelligent DCA that adjusts buy amounts based on market conditions,
price trends, and volatility metrics.

Prompts #113-116: DCA Automation
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from enum import Enum

logger = logging.getLogger(__name__)


class MarketCondition(str, Enum):
    """Market condition classifications"""
    EXTREME_FEAR = "extreme_fear"
    FEAR = "fear"
    NEUTRAL = "neutral"
    GREED = "greed"
    EXTREME_GREED = "extreme_greed"


class TrendDirection(str, Enum):
    """Price trend direction"""
    STRONG_UP = "strong_up"
    UP = "up"
    SIDEWAYS = "sideways"
    DOWN = "down"
    STRONG_DOWN = "strong_down"


@dataclass
class SmartDCAConfig:
    """Configuration for smart DCA"""
    # Base settings
    base_amount: float = 100.0  # Base DCA amount in USD

    # Adjustment factors
    fear_multiplier: float = 1.5      # Buy more in fear
    greed_multiplier: float = 0.5     # Buy less in greed
    dip_multiplier: float = 2.0       # Buy more on dips
    pump_multiplier: float = 0.3      # Buy less on pumps

    # Thresholds
    dip_threshold_pct: float = 10.0   # Consider it a dip if price down X%
    pump_threshold_pct: float = 15.0  # Consider it a pump if price up X%
    volatility_high_threshold: float = 50.0  # High volatility if > X%

    # Risk limits
    max_single_buy: float = 500.0     # Max single purchase
    min_single_buy: float = 10.0      # Min single purchase
    skip_on_extreme_greed: bool = True
    skip_on_pump: bool = True

    # Moving averages
    use_sma_timing: bool = True
    sma_period: int = 50
    buy_below_sma: bool = True  # Only buy if below SMA

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "base_amount": self.base_amount,
            "fear_multiplier": self.fear_multiplier,
            "greed_multiplier": self.greed_multiplier,
            "dip_multiplier": self.dip_multiplier,
            "pump_multiplier": self.pump_multiplier,
            "dip_threshold_pct": self.dip_threshold_pct,
            "pump_threshold_pct": self.pump_threshold_pct,
            "volatility_high_threshold": self.volatility_high_threshold,
            "max_single_buy": self.max_single_buy,
            "min_single_buy": self.min_single_buy,
            "skip_on_extreme_greed": self.skip_on_extreme_greed,
            "skip_on_pump": self.skip_on_pump,
            "use_sma_timing": self.use_sma_timing,
            "sma_period": self.sma_period,
            "buy_below_sma": self.buy_below_sma
        }


@dataclass
class MarketSnapshot:
    """Current market state for a token"""
    token: str
    current_price: float
    price_24h_ago: float = 0.0
    price_7d_ago: float = 0.0
    price_30d_ago: float = 0.0
    sma_50: float = 0.0
    sma_200: float = 0.0
    volatility_30d: float = 0.0
    fear_greed_index: int = 50  # 0-100
    volume_24h: float = 0.0
    volume_avg_7d: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def change_24h_pct(self) -> float:
        """24h price change percentage"""
        if self.price_24h_ago > 0:
            return ((self.current_price - self.price_24h_ago) / self.price_24h_ago) * 100
        return 0.0

    @property
    def change_7d_pct(self) -> float:
        """7d price change percentage"""
        if self.price_7d_ago > 0:
            return ((self.current_price - self.price_7d_ago) / self.price_7d_ago) * 100
        return 0.0

    @property
    def distance_from_sma50_pct(self) -> float:
        """Distance from 50-day SMA as percentage"""
        if self.sma_50 > 0:
            return ((self.current_price - self.sma_50) / self.sma_50) * 100
        return 0.0

    @property
    def market_condition(self) -> MarketCondition:
        """Classify market condition from fear/greed index"""
        if self.fear_greed_index <= 20:
            return MarketCondition.EXTREME_FEAR
        elif self.fear_greed_index <= 40:
            return MarketCondition.FEAR
        elif self.fear_greed_index <= 60:
            return MarketCondition.NEUTRAL
        elif self.fear_greed_index <= 80:
            return MarketCondition.GREED
        else:
            return MarketCondition.EXTREME_GREED

    @property
    def trend(self) -> TrendDirection:
        """Classify current trend"""
        change = self.change_7d_pct
        if change > 20:
            return TrendDirection.STRONG_UP
        elif change > 5:
            return TrendDirection.UP
        elif change < -20:
            return TrendDirection.STRONG_DOWN
        elif change < -5:
            return TrendDirection.DOWN
        else:
            return TrendDirection.SIDEWAYS


@dataclass
class SmartDCADecision:
    """Decision from smart DCA analysis"""
    should_buy: bool
    amount: float
    reasoning: List[str]
    adjustments: Dict[str, float]
    market_snapshot: MarketSnapshot
    config: SmartDCAConfig

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "should_buy": self.should_buy,
            "amount": self.amount,
            "reasoning": self.reasoning,
            "adjustments": self.adjustments,
            "market_condition": self.market_snapshot.market_condition.value,
            "trend": self.market_snapshot.trend.value,
            "price_change_24h": self.market_snapshot.change_24h_pct,
            "price_change_7d": self.market_snapshot.change_7d_pct
        }


class SmartDCA:
    """
    Intelligent DCA system that adjusts purchase amounts
    based on market conditions.

    Implements value averaging and contrarian buying strategies.
    """

    def __init__(self, config: Optional[SmartDCAConfig] = None):
        self.config = config or SmartDCAConfig()

    async def analyze_and_decide(
        self,
        snapshot: MarketSnapshot
    ) -> SmartDCADecision:
        """
        Analyze market conditions and decide on DCA amount

        Returns a decision with the recommended buy amount and reasoning.
        """
        config = self.config
        reasoning = []
        adjustments = {}

        # Start with base amount
        amount = config.base_amount
        reasoning.append(f"Base amount: ${config.base_amount}")

        # Check for skip conditions first
        if config.skip_on_extreme_greed and snapshot.market_condition == MarketCondition.EXTREME_GREED:
            reasoning.append("Skipping: Extreme greed detected")
            return SmartDCADecision(
                should_buy=False,
                amount=0,
                reasoning=reasoning,
                adjustments={},
                market_snapshot=snapshot,
                config=config
            )

        if config.skip_on_pump and snapshot.change_7d_pct > config.pump_threshold_pct:
            reasoning.append(f"Skipping: Pump detected ({snapshot.change_7d_pct:.1f}% in 7d)")
            return SmartDCADecision(
                should_buy=False,
                amount=0,
                reasoning=reasoning,
                adjustments={},
                market_snapshot=snapshot,
                config=config
            )

        # Apply fear/greed adjustment
        fear_greed_adj = self._calculate_fear_greed_adjustment(snapshot)
        if fear_greed_adj != 1.0:
            old_amount = amount
            amount *= fear_greed_adj
            adjustments["fear_greed"] = fear_greed_adj
            reasoning.append(
                f"Fear/Greed adjustment ({snapshot.market_condition.value}): "
                f"${old_amount:.2f} -> ${amount:.2f} ({fear_greed_adj:.2f}x)"
            )

        # Apply dip/pump adjustment
        dip_pump_adj = self._calculate_dip_pump_adjustment(snapshot)
        if dip_pump_adj != 1.0:
            old_amount = amount
            amount *= dip_pump_adj
            adjustments["dip_pump"] = dip_pump_adj
            direction = "dip" if dip_pump_adj > 1 else "rally"
            reasoning.append(
                f"Price {direction} adjustment ({snapshot.change_7d_pct:.1f}% 7d): "
                f"${old_amount:.2f} -> ${amount:.2f} ({dip_pump_adj:.2f}x)"
            )

        # Apply volatility adjustment
        vol_adj = self._calculate_volatility_adjustment(snapshot)
        if vol_adj != 1.0:
            old_amount = amount
            amount *= vol_adj
            adjustments["volatility"] = vol_adj
            reasoning.append(
                f"Volatility adjustment ({snapshot.volatility_30d:.1f}%): "
                f"${old_amount:.2f} -> ${amount:.2f} ({vol_adj:.2f}x)"
            )

        # Apply SMA timing
        if config.use_sma_timing and snapshot.sma_50 > 0:
            sma_adj = self._calculate_sma_adjustment(snapshot)
            if sma_adj != 1.0:
                old_amount = amount
                amount *= sma_adj
                adjustments["sma"] = sma_adj
                above_below = "above" if snapshot.current_price > snapshot.sma_50 else "below"
                reasoning.append(
                    f"SMA adjustment (price {snapshot.distance_from_sma50_pct:.1f}% {above_below} SMA50): "
                    f"${old_amount:.2f} -> ${amount:.2f} ({sma_adj:.2f}x)"
                )

        # Apply limits
        original_amount = amount
        amount = max(config.min_single_buy, min(amount, config.max_single_buy))
        if amount != original_amount:
            reasoning.append(f"Capped to limits: ${amount:.2f}")

        return SmartDCADecision(
            should_buy=amount >= config.min_single_buy,
            amount=amount,
            reasoning=reasoning,
            adjustments=adjustments,
            market_snapshot=snapshot,
            config=config
        )

    def _calculate_fear_greed_adjustment(self, snapshot: MarketSnapshot) -> float:
        """Calculate adjustment based on fear/greed index"""
        condition = snapshot.market_condition

        if condition == MarketCondition.EXTREME_FEAR:
            return self.config.fear_multiplier * 1.2
        elif condition == MarketCondition.FEAR:
            return self.config.fear_multiplier
        elif condition == MarketCondition.NEUTRAL:
            return 1.0
        elif condition == MarketCondition.GREED:
            return self.config.greed_multiplier
        else:  # EXTREME_GREED
            return self.config.greed_multiplier * 0.5

    def _calculate_dip_pump_adjustment(self, snapshot: MarketSnapshot) -> float:
        """Calculate adjustment based on recent price change"""
        change = snapshot.change_7d_pct

        if change <= -self.config.dip_threshold_pct:
            # Big dip - buy more
            dip_magnitude = abs(change) / self.config.dip_threshold_pct
            return min(self.config.dip_multiplier, 1 + (dip_magnitude * 0.5))

        elif change >= self.config.pump_threshold_pct:
            # Big pump - buy less
            pump_magnitude = change / self.config.pump_threshold_pct
            return max(self.config.pump_multiplier, 1 - (pump_magnitude * 0.3))

        elif change < 0:
            # Small dip - slightly more
            return 1 + (abs(change) / 100)

        elif change > 0:
            # Small pump - slightly less
            return 1 - (change / 200)

        return 1.0

    def _calculate_volatility_adjustment(self, snapshot: MarketSnapshot) -> float:
        """Calculate adjustment based on volatility"""
        vol = snapshot.volatility_30d

        if vol > self.config.volatility_high_threshold:
            # High volatility - reduce position size
            return 0.7
        elif vol > self.config.volatility_high_threshold * 0.7:
            # Medium-high volatility
            return 0.85
        elif vol < 20:
            # Low volatility - can be slightly more aggressive
            return 1.1

        return 1.0

    def _calculate_sma_adjustment(self, snapshot: MarketSnapshot) -> float:
        """Calculate adjustment based on SMA positioning"""
        distance = snapshot.distance_from_sma50_pct

        if self.config.buy_below_sma:
            if distance < -10:
                # Significantly below SMA - buy more
                return 1.3
            elif distance < 0:
                # Below SMA - normal or slightly more
                return 1.1
            elif distance > 10:
                # Significantly above SMA - buy less
                return 0.7
            elif distance > 0:
                # Above SMA - slightly less
                return 0.9

        return 1.0

    async def get_value_averaging_amount(
        self,
        token: str,
        target_value: float,
        current_holdings: float,
        current_price: float
    ) -> float:
        """
        Calculate amount needed for value averaging

        Value averaging aims to grow portfolio by a fixed dollar amount
        each period, buying more when prices are low and less when high.
        """
        current_value = current_holdings * current_price
        needed_value = target_value - current_value

        if needed_value <= 0:
            # Already at or above target - no purchase needed
            return 0.0

        # Cap at max single buy
        return min(needed_value, self.config.max_single_buy)

    async def backtest_strategy(
        self,
        price_history: List[Dict[str, Any]],
        config: Optional[SmartDCAConfig] = None
    ) -> Dict[str, Any]:
        """
        Backtest the smart DCA strategy on historical data

        Args:
            price_history: List of {timestamp, price, volume, fear_greed} dicts
            config: Config to use (or self.config)
        """
        cfg = config or self.config
        old_config = self.config
        self.config = cfg

        # Track results
        purchases = []
        total_invested = 0.0
        total_tokens = 0.0
        skipped = 0

        for i, data in enumerate(price_history):
            # Create snapshot from historical data
            snapshot = MarketSnapshot(
                token="BACKTEST",
                current_price=data["price"],
                price_7d_ago=price_history[max(0, i-7)]["price"] if i >= 7 else data["price"],
                price_30d_ago=price_history[max(0, i-30)]["price"] if i >= 30 else data["price"],
                fear_greed_index=data.get("fear_greed", 50),
                volatility_30d=data.get("volatility", 30),
                sma_50=sum(p["price"] for p in price_history[max(0,i-50):i+1]) / min(i+1, 50) if i > 0 else data["price"]
            )

            decision = await self.analyze_and_decide(snapshot)

            if decision.should_buy:
                tokens = decision.amount / data["price"]
                total_invested += decision.amount
                total_tokens += tokens
                purchases.append({
                    "timestamp": data.get("timestamp"),
                    "price": data["price"],
                    "amount": decision.amount,
                    "tokens": tokens
                })
            else:
                skipped += 1

        # Calculate results
        avg_price = total_invested / total_tokens if total_tokens > 0 else 0
        final_price = price_history[-1]["price"] if price_history else 0
        final_value = total_tokens * final_price
        pnl = final_value - total_invested
        pnl_pct = (pnl / total_invested * 100) if total_invested > 0 else 0

        # Compare to basic DCA
        basic_invested = len(price_history) * cfg.base_amount
        basic_tokens = sum(cfg.base_amount / p["price"] for p in price_history)
        basic_avg_price = basic_invested / basic_tokens if basic_tokens > 0 else 0
        basic_final_value = basic_tokens * final_price
        basic_pnl_pct = ((basic_final_value - basic_invested) / basic_invested * 100) if basic_invested > 0 else 0

        self.config = old_config

        return {
            "strategy": "smart_dca",
            "total_periods": len(price_history),
            "purchases_made": len(purchases),
            "purchases_skipped": skipped,
            "total_invested": total_invested,
            "total_tokens": total_tokens,
            "average_price": avg_price,
            "final_value": final_value,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "comparison": {
                "basic_dca_invested": basic_invested,
                "basic_dca_tokens": basic_tokens,
                "basic_dca_avg_price": basic_avg_price,
                "basic_dca_pnl_pct": basic_pnl_pct,
                "outperformance_pct": pnl_pct - basic_pnl_pct
            }
        }


# Testing
if __name__ == "__main__":
    async def test():
        smart_dca = SmartDCA(SmartDCAConfig(
            base_amount=100,
            fear_multiplier=1.5,
            greed_multiplier=0.5
        ))

        # Test with fear market
        fear_snapshot = MarketSnapshot(
            token="SOL",
            current_price=100,
            price_7d_ago=120,  # -16.7%
            fear_greed_index=20,  # Extreme fear
            volatility_30d=40,
            sma_50=110
        )

        decision = await smart_dca.analyze_and_decide(fear_snapshot)
        print("Fear Market Decision:")
        print(f"  Should buy: {decision.should_buy}")
        print(f"  Amount: ${decision.amount:.2f}")
        print("  Reasoning:")
        for reason in decision.reasoning:
            print(f"    - {reason}")

        # Test with greed market
        greed_snapshot = MarketSnapshot(
            token="SOL",
            current_price=200,
            price_7d_ago=160,  # +25%
            fear_greed_index=85,  # Extreme greed
            volatility_30d=60,
            sma_50=170
        )

        decision = await smart_dca.analyze_and_decide(greed_snapshot)
        print("\nGreed Market Decision:")
        print(f"  Should buy: {decision.should_buy}")
        print(f"  Amount: ${decision.amount:.2f}")
        print("  Reasoning:")
        for reason in decision.reasoning:
            print(f"    - {reason}")

    asyncio.run(test())
