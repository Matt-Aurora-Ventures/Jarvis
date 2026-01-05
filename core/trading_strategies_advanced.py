"""
Advanced Trading Strategies Module for Life OS Bot
===================================================

Extends core trading strategies with advanced algorithms:
- TriangularArbitrage: Cross-rate exploitation (BTC→ETH→USDT→BTC)
- GridTrader: Range-bound strategy for sideways markets
- BreakoutTrader: Support/resistance breakout with volume confirmation
- MarketMaker: Bid-ask spread capture with inventory management

Phase 1 Implementation per Quant Analyst specification.

Usage:
    from core.trading_strategies_advanced import TriangularArbitrage, GridTrader
    
    arb = TriangularArbitrage(min_profit_pct=0.1)
    opportunity = arb.scan_triangle("BTC", "ETH", "USDT", prices)
"""

import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Import base classes from existing trading strategies
from core.trading_strategies import BaseStrategy, TradeSignal
from core import fee_model


# ============================================================================
# Triangular Arbitrage
# ============================================================================

@dataclass
class TriangleOpportunity:
    """Represents a triangular arbitrage opportunity."""
    path: List[str]  # e.g., ["BTC", "ETH", "USDT", "BTC"]
    rates: List[float]  # Exchange rates at each step
    gross_profit_pct: float
    net_profit_pct: float  # After fees
    required_capital: float
    expected_profit: float
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "rates": self.rates,
            "gross_profit_pct": round(self.gross_profit_pct, 4),
            "net_profit_pct": round(self.net_profit_pct, 4),
            "required_capital": round(self.required_capital, 2),
            "expected_profit": round(self.expected_profit, 4),
            "timestamp": self.timestamp,
        }


class TriangularArbitrage(BaseStrategy):
    """
    Triangular Arbitrage Strategy.
    
    Exploits price discrepancies between three trading pairs.
    Example: Start with USDT → Buy BTC → Swap to ETH → Sell for USDT
    
    If the product of exchange rates > 1.0 (after fees), profit exists.
    
    Execution Flow:
        1. Monitor 3 pairs: A/B, B/C, C/A
        2. Calculate cross-rate product
        3. If product > 1 + fees, execute atomically
        4. For DeFi: Use flash loans for risk-free capital
    
    Note: Requires atomic execution or flash loans to be risk-free.
    """
    
    name = "TriangularArbitrage"
    
    def __init__(
        self,
        min_profit_pct: float = 0.1,  # Minimum 0.1% net profit to trade
        fee_per_trade_pct: float = 0.1,  # 0.1% per swap (0.3% total for 3 trades)
        max_slippage_pct: float = 0.05,  # Slippage tolerance per leg
        use_flash_loan: bool = False,  # Enable flash loan mode (DeFi)
    ):
        self.min_profit_pct = min_profit_pct
        self.fee_per_trade_pct = fee_per_trade_pct
        self.max_slippage_pct = max_slippage_pct
        self.use_flash_loan = use_flash_loan
        self.total_fee_pct = fee_per_trade_pct * 3  # 3 trades in triangle
    
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        """
        For single-price analysis. Use scan_triangle for full functionality.
        """
        return TradeSignal(
            action="HOLD",
            confidence=0.0,
            strategy=self.name,
            symbol=symbol,
            price=prices[-1] if prices else 0.0,
            metadata={"reason": "Use scan_triangle with 3-pair price data"}
        )
    
    def scan_triangle(
        self,
        base: str,  # e.g., "BTC"
        quote1: str,  # e.g., "ETH"
        quote2: str,  # e.g., "USDT" (settlement currency)
        prices: Dict[str, float],  # {"BTC/USDT": 42000, "ETH/USDT": 2200, "ETH/BTC": 0.052}
        capital: float = 1000.0,  # Starting capital in quote2
    ) -> Optional[TriangleOpportunity]:
        """
        Scan for triangular arbitrage opportunity.
        
        Args:
            base: Base asset (e.g., "BTC")
            quote1: Intermediate asset (e.g., "ETH")
            quote2: Settlement currency (e.g., "USDT")
            prices: Dict of pair prices
            capital: Starting capital in quote2
            
        Returns:
            TriangleOpportunity if profitable, None otherwise
            
        Triangle Paths:
            Path A: USDT → BTC → ETH → USDT
            Path B: USDT → ETH → BTC → USDT (reverse)
        """
        # Extract prices (handle both directions)
        base_quote2 = prices.get(f"{base}/{quote2}") or prices.get(f"{base}-{quote2}")
        quote1_quote2 = prices.get(f"{quote1}/{quote2}") or prices.get(f"{quote1}-{quote2}")
        quote1_base = prices.get(f"{quote1}/{base}") or prices.get(f"{quote1}-{base}")
        
        if not all([base_quote2, quote1_quote2, quote1_base]):
            return None
        
        # Path A: USDT → BTC → ETH → USDT
        # 1. Buy BTC with USDT: capital / BTC_USDT = BTC amount
        # 2. Swap BTC to ETH: BTC * (1/ETH_BTC) = ETH amount
        # 3. Sell ETH for USDT: ETH * ETH_USDT = final USDT
        path_a_product = (1 / base_quote2) * (1 / quote1_base) * quote1_quote2
        
        # Path B: USDT → ETH → BTC → USDT (reverse)
        path_b_product = (1 / quote1_quote2) * quote1_base * base_quote2
        
        # Find best path
        if path_a_product > path_b_product:
            best_product = path_a_product
            path = [quote2, base, quote1, quote2]
            rates = [1/base_quote2, 1/quote1_base, quote1_quote2]
        else:
            best_product = path_b_product
            path = [quote2, quote1, base, quote2]
            rates = [1/quote1_quote2, quote1_base, base_quote2]
        
        # Calculate profit
        gross_profit_pct = (best_product - 1) * 100
        net_profit_pct = gross_profit_pct - self.total_fee_pct - (self.max_slippage_pct * 3)
        
        if net_profit_pct < self.min_profit_pct:
            return None
        
        expected_profit = capital * (net_profit_pct / 100)
        
        return TriangleOpportunity(
            path=path,
            rates=rates,
            gross_profit_pct=gross_profit_pct,
            net_profit_pct=net_profit_pct,
            required_capital=capital,
            expected_profit=expected_profit,
        )
    
    def find_all_triangles(
        self,
        prices: Dict[str, float],
        base_currency: str = "USDT",
        capital: float = 1000.0,
    ) -> List[TriangleOpportunity]:
        """
        Find all profitable triangular arbitrage opportunities.
        
        Args:
            prices: Dict of all pair prices
            base_currency: Settlement currency
            capital: Starting capital
            
        Returns:
            List of profitable opportunities sorted by net profit
        """
        opportunities = []
        
        # Extract all unique assets from pairs
        assets = set()
        for pair in prices.keys():
            parts = pair.replace("-", "/").split("/")
            assets.update(parts)
        
        assets.discard(base_currency)
        assets_list = list(assets)
        
        # Check all 2-asset combinations with base currency
        for i, asset1 in enumerate(assets_list):
            for asset2 in assets_list[i+1:]:
                opp = self.scan_triangle(
                    base=asset1,
                    quote1=asset2,
                    quote2=base_currency,
                    prices=prices,
                    capital=capital,
                )
                if opp:
                    opportunities.append(opp)
        
        # Sort by net profit descending
        return sorted(opportunities, key=lambda x: x.net_profit_pct, reverse=True)


# ============================================================================
# Grid Trading
# ============================================================================

@dataclass
class GridLevel:
    """Represents a single grid level."""
    price: float
    side: str  # "BUY" or "SELL"
    quantity: float
    filled: bool = False
    fill_price: Optional[float] = None
    fill_time: Optional[float] = None


class GridTrader(BaseStrategy):
    """
    Grid Trading Strategy for Sideways Markets.
    
    Places buy orders below current price and sell orders above,
    profiting from price oscillations within a range.
    
    Best for:
        - Ranging/sideways markets (low trend strength)
        - Assets with predictable volatility
        - Stable price channels
    
    Risk:
        - Strong trends will cause losses on one side
        - Requires sufficient capital for all grid levels
    
    Grid Setup:
        Upper bound: $105 ─── SELL orders
        Current:     $100
        Lower bound: $95  ─── BUY orders
        Grid spacing: e.g., 10 levels = $1 apart
    """
    
    name = "GridTrader"
    
    def __init__(
        self,
        upper_bound: float = 0.0,  # Upper price boundary
        lower_bound: float = 0.0,  # Lower price boundary
        num_grids: int = 10,  # Number of grid levels
        capital_per_grid: float = 100.0,  # Capital allocated per level
        trigger_on_touch: bool = True,  # Trigger when price touches level
    ):
        self.upper_bound = upper_bound
        self.lower_bound = lower_bound
        self.num_grids = num_grids
        self.capital_per_grid = capital_per_grid
        self.trigger_on_touch = trigger_on_touch
        self.grid_levels: List[GridLevel] = []
        self.is_initialized = False
        self._last_price: Optional[float] = None
    
    def initialize_grid(self, current_price: float) -> List[GridLevel]:
        """
        Initialize grid levels based on current price.
        
        Creates buy orders below current price and sell orders above.
        """
        if self.upper_bound == 0.0:
            # Auto-set bounds at ±5% if not specified
            self.upper_bound = current_price * 1.05
            self.lower_bound = current_price * 0.95
        
        grid_spacing = (self.upper_bound - self.lower_bound) / self.num_grids
        self.grid_levels = []
        
        for i in range(self.num_grids + 1):
            level_price = self.lower_bound + (i * grid_spacing)
            
            # Determine side based on position relative to current price
            if level_price < current_price:
                side = "BUY"
            elif level_price > current_price:
                side = "SELL"
            else:
                continue  # Skip level at current price
            
            quantity = self.capital_per_grid / level_price
            
            self.grid_levels.append(GridLevel(
                price=round(level_price, 4),
                side=side,
                quantity=round(quantity, 6),
            ))
        
        self.is_initialized = True
        return self.grid_levels
    
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        """
        Analyze price movement and trigger grid orders.
        """
        if not prices:
            return TradeSignal(
                action="HOLD",
                confidence=0.0,
                strategy=self.name,
                symbol=symbol,
                price=0.0,
                metadata={"reason": "No price data"}
            )
        
        current_price = prices[-1]
        
        # Initialize grid if first run
        if not self.is_initialized:
            self.initialize_grid(current_price)
            return TradeSignal(
                action="HOLD",
                confidence=0.0,
                strategy=self.name,
                symbol=symbol,
                price=current_price,
                metadata={
                    "reason": "Grid initialized",
                    "grid_levels": len(self.grid_levels),
                    "upper_bound": self.upper_bound,
                    "lower_bound": self.lower_bound,
                }
            )
        
        # Check if price crossed any unfilled grid levels
        triggered_levels = []
        
        for level in self.grid_levels:
            if level.filled:
                continue
            
            # Check for level trigger
            triggered = False
            if self._last_price is not None:
                if level.side == "BUY":
                    # Buy triggers when price drops to or below level
                    triggered = self._last_price > level.price >= current_price
                else:
                    # Sell triggers when price rises to or above level
                    triggered = self._last_price < level.price <= current_price
            
            if triggered:
                level.filled = True
                level.fill_price = current_price
                level.fill_time = time.time()
                triggered_levels.append(level)
                
                # Create opposite order (buy triggers future sell, vice versa)
                opposite_side = "SELL" if level.side == "BUY" else "BUY"
                # The opposite order is typically 1 grid level away
        
        self._last_price = current_price
        
        if triggered_levels:
            # Return the most recent triggered level
            level = triggered_levels[-1]
            return TradeSignal(
                action=level.side,
                confidence=0.8,
                strategy=self.name,
                symbol=symbol,
                price=current_price,
                metadata={
                    "level_price": level.price,
                    "quantity": level.quantity,
                    "triggered_count": len(triggered_levels),
                    "reason": f"Grid level triggered at {level.price}",
                }
            )
        
        # Check if price is outside grid bounds
        if current_price > self.upper_bound:
            return TradeSignal(
                action="HOLD",
                confidence=0.2,
                strategy=self.name,
                symbol=symbol,
                price=current_price,
                metadata={"reason": "Price above grid - consider expanding upper bound"}
            )
        elif current_price < self.lower_bound:
            return TradeSignal(
                action="HOLD",
                confidence=0.2,
                strategy=self.name,
                symbol=symbol,
                price=current_price,
                metadata={"reason": "Price below grid - consider expanding lower bound"}
            )
        
        return TradeSignal(
            action="HOLD",
            confidence=0.5,
            strategy=self.name,
            symbol=symbol,
            price=current_price,
            metadata={
                "reason": "Within grid, no levels triggered",
                "unfilled_levels": sum(1 for l in self.grid_levels if not l.filled),
            }
        )
    
    def get_grid_status(self) -> Dict[str, Any]:
        """Get current grid status."""
        if not self.is_initialized:
            return {"status": "not_initialized"}
        
        filled_buys = sum(1 for l in self.grid_levels if l.filled and l.side == "BUY")
        filled_sells = sum(1 for l in self.grid_levels if l.filled and l.side == "SELL")
        
        return {
            "status": "active",
            "upper_bound": self.upper_bound,
            "lower_bound": self.lower_bound,
            "total_levels": len(self.grid_levels),
            "filled_buys": filled_buys,
            "filled_sells": filled_sells,
            "unfilled": len(self.grid_levels) - filled_buys - filled_sells,
            "last_price": self._last_price,
        }


# ============================================================================
# Breakout Trading
# ============================================================================

class BreakoutTrader(BaseStrategy):
    """
    Breakout Trading Strategy.
    
    Detects when price breaks through support/resistance levels
    with volume confirmation for trend initiation.
    
    Entry Logic:
        - Price breaks above resistance (bullish breakout)
        - Price breaks below support (bearish breakout)
        - Volume must be higher than average (confirmation)
    
    Exit Logic:
        - Trailing stop or fixed take-profit
        - False breakout detection (quick reversal)
    
    Best for:
        - Trending markets after consolidation
        - High-volume breakout candles
        - Range breakouts with catalyst
    """
    
    name = "BreakoutTrader"
    
    def __init__(
        self,
        lookback_period: int = 20,  # Candles to find support/resistance
        breakout_threshold_pct: float = 0.5,  # Min % move beyond level
        volume_multiplier: float = 1.5,  # Volume must be 1.5x average
        confirmation_candles: int = 2,  # Candles to confirm breakout
    ):
        self.lookback_period = lookback_period
        self.breakout_threshold_pct = breakout_threshold_pct
        self.volume_multiplier = volume_multiplier
        self.confirmation_candles = confirmation_candles
        self._resistance: Optional[float] = None
        self._support: Optional[float] = None
        self._breakout_candles: int = 0
        self._breakout_direction: Optional[str] = None
    
    def _find_support_resistance(
        self, prices: List[float]
    ) -> Tuple[float, float]:
        """
        Find support and resistance levels from recent price action.
        
        Uses simple high/low of lookback period.
        More sophisticated methods: pivot points, Fibonacci, volume profile.
        """
        if len(prices) < self.lookback_period:
            lookback = prices
        else:
            lookback = prices[-self.lookback_period:]
        
        resistance = max(lookback)
        support = min(lookback)
        
        return support, resistance
    
    def analyze(
        self,
        prices: List[float],
        symbol: str = "UNKNOWN",
        volumes: Optional[List[float]] = None,
    ) -> TradeSignal:
        """
        Analyze for breakout signals.
        
        Args:
            prices: Historical prices
            symbol: Trading pair
            volumes: Optional volume data for confirmation
        """
        if len(prices) < self.lookback_period:
            return TradeSignal(
                action="HOLD",
                confidence=0.0,
                strategy=self.name,
                symbol=symbol,
                price=prices[-1] if prices else 0.0,
                metadata={"reason": f"Need {self.lookback_period} candles"}
            )
        
        current_price = prices[-1]
        previous_price = prices[-2] if len(prices) > 1 else current_price
        
        # Calculate support/resistance from prior period (excluding current)
        support, resistance = self._find_support_resistance(prices[:-1])
        self._support = support
        self._resistance = resistance
        
        # Check volume confirmation if provided
        volume_confirmed = True
        if volumes and len(volumes) >= self.lookback_period:
            avg_volume = sum(volumes[-self.lookback_period:-1]) / (self.lookback_period - 1)
            current_volume = volumes[-1]
            volume_confirmed = current_volume >= avg_volume * self.volume_multiplier
        
        # Calculate breakout thresholds
        resistance_break = resistance * (1 + self.breakout_threshold_pct / 100)
        support_break = support * (1 - self.breakout_threshold_pct / 100)
        
        action = "HOLD"
        confidence = 0.0
        reason = "No breakout detected"
        
        # Bullish breakout: price breaks above resistance
        if current_price > resistance_break and previous_price <= resistance:
            if volume_confirmed:
                self._breakout_direction = "BULLISH"
                self._breakout_candles = 1
                action = "BUY"
                confidence = 0.75
                reason = f"Bullish breakout above {resistance:.2f}"
            else:
                reason = "Breakout without volume confirmation"
                confidence = 0.3
        
        # Bearish breakout: price breaks below support
        elif current_price < support_break and previous_price >= support:
            if volume_confirmed:
                self._breakout_direction = "BEARISH"
                self._breakout_candles = 1
                action = "SELL"
                confidence = 0.75
                reason = f"Bearish breakout below {support:.2f}"
            else:
                reason = "Breakout without volume confirmation"
                confidence = 0.3
        
        # Continuation of existing breakout
        elif self._breakout_direction:
            # Check if breakout is holding
            if self._breakout_direction == "BULLISH" and current_price > resistance:
                self._breakout_candles += 1
                if self._breakout_candles >= self.confirmation_candles:
                    action = "HOLD"  # Already in position
                    confidence = 0.8
                    reason = f"Bullish breakout confirmed ({self._breakout_candles} candles)"
            elif self._breakout_direction == "BEARISH" and current_price < support:
                self._breakout_candles += 1
                if self._breakout_candles >= self.confirmation_candles:
                    action = "HOLD"
                    confidence = 0.8
                    reason = f"Bearish breakout confirmed ({self._breakout_candles} candles)"
            else:
                # Failed breakout (price returned to range)
                self._breakout_direction = None
                self._breakout_candles = 0
                reason = "False breakout - price returned to range"
        
        return TradeSignal(
            action=action,
            confidence=confidence,
            strategy=self.name,
            symbol=symbol,
            price=current_price,
            metadata={
                "support": round(support, 4),
                "resistance": round(resistance, 4),
                "breakout_direction": self._breakout_direction,
                "breakout_candles": self._breakout_candles,
                "volume_confirmed": volume_confirmed,
                "reason": reason,
            }
        )


# ============================================================================
# Market Maker (Bid-Ask Spread Capture)
# ============================================================================

class MarketMaker(BaseStrategy):
    """
    Market Making Strategy.
    
    Profits from the bid-ask spread by providing liquidity on both sides.
    Places limit orders at bid and ask, capturing the spread on each fill.
    
    Risk: Inventory risk during trending markets (accumulating one side).
    
    Mitigation:
        - Inventory skew: Adjust quotes based on current position
        - Max inventory: Hard limit on position size
        - Volatility scaling: Widen spread in volatile conditions
    """
    
    name = "MarketMaker"
    
    def __init__(
        self,
        base_spread_pct: float = 0.1,  # 0.1% spread (0.05% each side)
        max_inventory: float = 1000.0,  # Max position in quote currency
        inventory_skew_factor: float = 0.5,  # How much to skew on imbalance
        volatility_multiplier: float = 2.0,  # Spread multiplier in high vol
        min_spread_bps: Optional[float] = None,  # Guardrail after fees
        asset_type: str = "crypto",
        issuer: str = "",
    ):
        self.base_spread_pct = base_spread_pct
        self.max_inventory = max_inventory
        self.inventory_skew_factor = inventory_skew_factor
        self.volatility_multiplier = volatility_multiplier
        self.min_spread_bps = min_spread_bps
        self.asset_type = asset_type
        self.issuer = issuer
        self.current_inventory: float = 0.0  # Positive = long, negative = short
    
    def analyze(self, prices: List[float], symbol: str = "UNKNOWN") -> TradeSignal:
        """
        Generate market making quotes.
        """
        if not prices:
            return TradeSignal(
                action="HOLD",
                confidence=0.0,
                strategy=self.name,
                symbol=symbol,
                price=0.0,
                metadata={"reason": "No price data"}
            )
        
        mid_price = prices[-1]
        
        # Calculate volatility (simple: range of last 20 prices)
        if len(prices) >= 20:
            recent = prices[-20:]
            volatility = (max(recent) - min(recent)) / mid_price
        else:
            volatility = 0.02  # Default 2%
        
        # Adjust spread based on volatility
        spread_pct = self.base_spread_pct
        if volatility > 0.03:  # High volatility threshold
            spread_pct *= self.volatility_multiplier

        # Fee-aware guardrail to prevent negative spread after fees
        min_spread_bps = self.min_spread_bps
        if min_spread_bps is None:
            profile = fee_model.get_fee_profile(self.asset_type, self.issuer)
            roundtrip_fee_bps = (
                profile.amm_fee_bps
                + profile.aggregator_fee_bps
                + profile.issuer_fee_bps
                + profile.conversion_bps
            ) * 2
            min_spread_bps = roundtrip_fee_bps
        spread_bps = spread_pct * 100
        if spread_bps < min_spread_bps:
            spread_bps = min_spread_bps
            spread_pct = spread_bps / 100
        
        half_spread = spread_pct / 2 / 100
        
        # Calculate inventory skew
        inventory_ratio = self.current_inventory / self.max_inventory if self.max_inventory > 0 else 0
        skew = inventory_ratio * self.inventory_skew_factor * half_spread
        
        # Generate quotes (skewed away from inventory direction)
        bid_price = mid_price * (1 - half_spread + skew)
        ask_price = mid_price * (1 + half_spread + skew)
        
        # Check inventory limits
        if abs(self.current_inventory) >= self.max_inventory:
            # Only quote the side that reduces inventory
            if self.current_inventory > 0:
                return TradeSignal(
                    action="SELL",
                    confidence=0.9,
                    strategy=self.name,
                    symbol=symbol,
                    price=ask_price,
                    metadata={
                        "reason": "Max inventory reached - sell only",
                        "inventory": self.current_inventory,
                    }
                )
            else:
                return TradeSignal(
                    action="BUY",
                    confidence=0.9,
                    strategy=self.name,
                    symbol=symbol,
                    price=bid_price,
                    metadata={
                        "reason": "Max inventory reached - buy only",
                        "inventory": self.current_inventory,
                    }
                )
        
        return TradeSignal(
            action="HOLD",  # Market makers don't take directional positions
            confidence=0.7,
            strategy=self.name,
            symbol=symbol,
            price=mid_price,
            metadata={
                "bid": round(bid_price, 4),
                "ask": round(ask_price, 4),
                "spread_pct": round(spread_pct, 4),
                "spread_bps": round(spread_bps, 2),
                "min_spread_bps": round(min_spread_bps, 2),
                "spread_after_fees_bps": round(spread_bps - min_spread_bps, 2),
                "inventory": self.current_inventory,
                "volatility": round(volatility, 4),
                "reason": "Quoting both sides",
            }
        )
    
    def update_inventory(self, side: str, quantity: float, price: float):
        """Update inventory after a fill."""
        if side == "BUY":
            self.current_inventory += quantity * price
        else:
            self.current_inventory -= quantity * price


# ============================================================================
# Demo
# ============================================================================

if __name__ == "__main__":
    import random
    
    print("=== Advanced Trading Strategies Demo ===\n")
    
    # Generate sample price data (ranging market)
    prices = [100.0]
    for _ in range(50):
        change = random.uniform(-1.5, 1.5)  # Sideways movement
        prices.append(max(95, min(105, prices[-1] + change)))
    
    # 1. Triangular Arbitrage
    print("1. Triangular Arbitrage")
    print("-" * 40)
    arb = TriangularArbitrage(min_profit_pct=0.05)
    
    # Simulated prices with slight imbalance
    pair_prices = {
        "BTC/USDT": 42000.0,
        "ETH/USDT": 2200.0,
        "ETH/BTC": 0.0523,  # Slight mispricing (should be ~0.0524)
    }
    
    opportunity = arb.scan_triangle("BTC", "ETH", "USDT", pair_prices, capital=10000)
    if opportunity:
        print(f"  Opportunity found!")
        print(f"  Path: {' -> '.join(opportunity.path)}")
        print(f"  Net Profit: {opportunity.net_profit_pct:.4f}%")
        print(f"  Expected: ${opportunity.expected_profit:.2f}")
    else:
        print("  No profitable opportunity (spread too small)")
    
    # 2. Grid Trading
    print("\n2. Grid Trading")
    print("-" * 40)
    grid = GridTrader(
        upper_bound=105,
        lower_bound=95,
        num_grids=10,
        capital_per_grid=100,
    )
    
    # Simulate price movement through grid
    for i, price in enumerate(prices[:10]):
        signal = grid.analyze([price], symbol="BTC/USDT")
        if signal.action != "HOLD" or i == 0:
            print(f"  Price ${price:.2f}: {signal.action} - {signal.metadata.get('reason', '')}")
    
    status = grid.get_grid_status()
    print(f"  Grid Status: {status['unfilled']} unfilled levels")
    
    # 3. Breakout Trading
    print("\n3. Breakout Trading")
    print("-" * 40)
    
    # Generate data with a breakout
    breakout_prices = [100.0] * 20  # Consolidation
    for i in range(10):
        breakout_prices.append(100 + i * 0.5)  # Gradual breakout
    breakout_prices.append(108)  # Strong breakout candle
    
    breakout = BreakoutTrader(
        lookback_period=20,
        breakout_threshold_pct=2.0,
        volume_multiplier=1.5,
    )
    
    # Simulate with mock volume
    volumes = [1000.0] * len(breakout_prices)
    volumes[-1] = 2500.0  # High volume on breakout
    
    signal = breakout.analyze(breakout_prices, symbol="ETH/USDT", volumes=volumes)
    print(f"  Signal: {signal.action}, Confidence: {signal.confidence:.2f}")
    print(f"  {signal.metadata.get('reason', '')}")
    print(f"  Support: ${signal.metadata.get('support', 0):.2f}")
    print(f"  Resistance: ${signal.metadata.get('resistance', 0):.2f}")
    
    # 4. Market Maker
    print("\n4. Market Maker")
    print("-" * 40)
    mm = MarketMaker(
        base_spread_pct=0.1,
        max_inventory=10000,
    )
    
    signal = mm.analyze(prices, symbol="SOL/USDT")
    print(f"  Bid: ${signal.metadata.get('bid', 0):.4f}")
    print(f"  Ask: ${signal.metadata.get('ask', 0):.4f}")
    print(f"  Spread: {signal.metadata.get('spread_pct', 0):.4f}%")
    print(f"  Inventory: ${signal.metadata.get('inventory', 0):.2f}")
