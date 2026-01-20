"""
Order Book Analyzer - Advanced analysis of order book data.

Provides:
- Depth analysis at percentage levels
- Bid/ask spread calculations
- Liquidity quality scoring
- Wall detection (support/resistance)
- Imbalance indicators
- Slippage estimation
- VWAP calculations
- Pressure analysis
"""

import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Any
from enum import Enum
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class LiquidityGrade(Enum):
    """Liquidity quality grade."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    ILLIQUID = "illiquid"


@dataclass
class OrderBookSnapshot:
    """
    Snapshot of order book data for analysis.

    Attributes:
        symbol: Trading pair symbol (e.g., "SOL/USDC")
        bids: List of (price, size) tuples, sorted high to low
        asks: List of (price, size) tuples, sorted low to high
        timestamp: ISO format timestamp
    """
    symbol: str
    bids: List[Tuple[float, float]]  # (price, size)
    asks: List[Tuple[float, float]]  # (price, size)
    timestamp: str

    def __post_init__(self):
        # Filter out zero-size levels
        self.bids = [(p, s) for p, s in self.bids if s > 0]
        self.asks = [(p, s) for p, s in self.asks if s > 0]

        # Sort bids high to low, asks low to high
        self.bids = sorted(self.bids, key=lambda x: x[0], reverse=True)
        self.asks = sorted(self.asks, key=lambda x: x[0])

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OrderBookSnapshot':
        """Create snapshot from dictionary."""
        return cls(
            symbol=data.get('symbol', ''),
            bids=data.get('bids', []),
            asks=data.get('asks', []),
            timestamp=data.get('timestamp', datetime.now(timezone.utc).isoformat())
        )


@dataclass
class Wall:
    """Represents a large order wall (support/resistance)."""
    price: float
    size: float
    value_usd: float
    wall_type: str  # "support" or "resistance"
    strength: float  # Ratio vs surrounding average
    distance_from_mid_pct: float


@dataclass
class SlippageEstimate:
    """Estimated slippage for an order."""
    side: str  # "buy" or "sell"
    order_size_usd: float
    avg_price: float
    best_price: float
    slippage_bps: float
    filled_amount: float
    filled_pct: float
    unfilled_amount: float
    levels_consumed: int


@dataclass
class OrderBookAnalysis:
    """
    Complete analysis result for an order book snapshot.
    """
    # Identifiers
    symbol: str
    timestamp: str

    # Basic metrics
    mid_price: float = 0.0
    spread: float = 0.0
    spread_bps: float = 0.0
    is_valid: bool = True

    # Depth analysis
    depth_1pct_bid: float = 0.0
    depth_1pct_ask: float = 0.0
    depth_5pct_bid: float = 0.0
    depth_5pct_ask: float = 0.0
    total_bid_depth: float = 0.0
    total_ask_depth: float = 0.0

    # Liquidity scoring
    liquidity_score: float = 0.0
    liquidity_grade: LiquidityGrade = LiquidityGrade.ILLIQUID
    liquidity_factors: Dict[str, float] = field(default_factory=dict)

    # Walls
    bid_walls: List[Wall] = field(default_factory=list)
    ask_walls: List[Wall] = field(default_factory=list)

    # Imbalance
    imbalance: float = 0.0  # -1 to 1, positive = bid heavy
    imbalance_signal: str = "neutral"
    imbalance_1pct: float = 0.0
    imbalance_5pct: float = 0.0

    # VWAP
    vwap_bid: float = 0.0
    vwap_ask: float = 0.0

    # Pressure
    buying_pressure: float = 0.5
    selling_pressure: float = 0.5

    # Microstructure
    bid_levels: int = 0
    ask_levels: int = 0
    bid_density: float = 0.0  # Levels per percent
    ask_density: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp,
            'mid_price': self.mid_price,
            'spread': self.spread,
            'spread_bps': self.spread_bps,
            'is_valid': self.is_valid,
            'depth_1pct_bid': self.depth_1pct_bid,
            'depth_1pct_ask': self.depth_1pct_ask,
            'depth_5pct_bid': self.depth_5pct_bid,
            'depth_5pct_ask': self.depth_5pct_ask,
            'total_bid_depth': self.total_bid_depth,
            'total_ask_depth': self.total_ask_depth,
            'liquidity_score': self.liquidity_score,
            'liquidity_grade': self.liquidity_grade.value,
            'liquidity_factors': self.liquidity_factors,
            'bid_walls': [
                {
                    'price': w.price,
                    'size': w.size,
                    'value_usd': w.value_usd,
                    'wall_type': w.wall_type,
                    'strength': w.strength,
                    'distance_from_mid_pct': w.distance_from_mid_pct
                }
                for w in self.bid_walls
            ],
            'ask_walls': [
                {
                    'price': w.price,
                    'size': w.size,
                    'value_usd': w.value_usd,
                    'wall_type': w.wall_type,
                    'strength': w.strength,
                    'distance_from_mid_pct': w.distance_from_mid_pct
                }
                for w in self.ask_walls
            ],
            'imbalance': self.imbalance,
            'imbalance_signal': self.imbalance_signal,
            'imbalance_1pct': self.imbalance_1pct,
            'imbalance_5pct': self.imbalance_5pct,
            'vwap_bid': self.vwap_bid,
            'vwap_ask': self.vwap_ask,
            'buying_pressure': self.buying_pressure,
            'selling_pressure': self.selling_pressure,
            'bid_levels': self.bid_levels,
            'ask_levels': self.ask_levels,
            'bid_density': self.bid_density,
            'ask_density': self.ask_density,
        }


class OrderBookAnalyzer:
    """
    Analyzer for order book data.

    Provides comprehensive analysis of order book snapshots including:
    - Spread and mid-price calculations
    - Depth analysis at multiple levels
    - Liquidity quality scoring
    - Wall detection for support/resistance
    - Order flow imbalance indicators
    - Slippage estimation

    Usage:
        analyzer = OrderBookAnalyzer()
        snapshot = OrderBookSnapshot(
            symbol="SOL/USDC",
            bids=[(100.0, 10.0), (99.0, 20.0)],
            asks=[(101.0, 15.0), (102.0, 25.0)],
            timestamp="2026-01-19T12:00:00Z"
        )
        analysis = analyzer.analyze(snapshot)
        print(f"Spread: {analysis.spread_bps} bps")
        print(f"Liquidity: {analysis.liquidity_grade}")
    """

    # Configuration thresholds
    WALL_THRESHOLD_MULTIPLIER = 5.0  # Times avg to be considered wall
    EXCELLENT_LIQUIDITY_THRESHOLD = 0.8
    GOOD_LIQUIDITY_THRESHOLD = 0.6
    FAIR_LIQUIDITY_THRESHOLD = 0.4
    POOR_LIQUIDITY_THRESHOLD = 0.2

    def __init__(
        self,
        wall_threshold: float = 5.0,
        depth_levels: List[float] = None
    ):
        """
        Initialize analyzer.

        Args:
            wall_threshold: Multiplier for wall detection (default 5x average)
            depth_levels: Percentage levels for depth analysis (default [1, 2, 5, 10])
        """
        self.wall_threshold = wall_threshold
        self.depth_levels = depth_levels or [1.0, 2.0, 5.0, 10.0]

    def analyze(self, snapshot: OrderBookSnapshot) -> OrderBookAnalysis:
        """
        Perform comprehensive analysis of order book snapshot.

        Args:
            snapshot: Order book snapshot to analyze

        Returns:
            OrderBookAnalysis with all computed metrics
        """
        # Handle empty order book
        if not snapshot.bids and not snapshot.asks:
            return OrderBookAnalysis(
                symbol=snapshot.symbol,
                timestamp=snapshot.timestamp,
                is_valid=False
            )

        # Get best prices
        best_bid = snapshot.bids[0][0] if snapshot.bids else 0
        best_ask = snapshot.asks[0][0] if snapshot.asks else 0

        # Check for crossed/invalid book
        is_valid = True
        if best_bid > 0 and best_ask > 0 and best_bid >= best_ask:
            is_valid = False

        # Calculate mid price and spread
        mid_price = 0.0
        spread = 0.0
        spread_bps = 0.0

        if best_bid > 0 and best_ask > 0:
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            spread_bps = (spread / mid_price) * 10000 if mid_price > 0 else 0
        elif best_bid > 0:
            mid_price = best_bid
        elif best_ask > 0:
            mid_price = best_ask

        # Calculate depths
        depth_1pct_bid, depth_1pct_ask = self._calculate_depth_at_level(
            snapshot, mid_price, 1.0
        )
        depth_5pct_bid, depth_5pct_ask = self._calculate_depth_at_level(
            snapshot, mid_price, 5.0
        )

        total_bid_depth = sum(p * s for p, s in snapshot.bids)
        total_ask_depth = sum(p * s for p, s in snapshot.asks)

        # Calculate imbalances
        imbalance, imbalance_signal = self._calculate_imbalance(
            total_bid_depth, total_ask_depth
        )
        imbalance_1pct, _ = self._calculate_imbalance(depth_1pct_bid, depth_1pct_ask)
        imbalance_5pct, _ = self._calculate_imbalance(depth_5pct_bid, depth_5pct_ask)

        # Calculate VWAP
        vwap_bid = self._calculate_vwap(snapshot.bids)
        vwap_ask = self._calculate_vwap(snapshot.asks)

        # Detect walls
        bid_walls = self._detect_walls(snapshot.bids, mid_price, "support")
        ask_walls = self._detect_walls(snapshot.asks, mid_price, "resistance")

        # Calculate liquidity score
        liquidity_score, liquidity_factors = self._calculate_liquidity_score(
            spread_bps,
            total_bid_depth,
            total_ask_depth,
            len(snapshot.bids),
            len(snapshot.asks)
        )
        liquidity_grade = self._get_liquidity_grade(liquidity_score)

        # Calculate pressure
        buying_pressure, selling_pressure = self._calculate_pressure(
            snapshot, mid_price
        )

        # Calculate density
        bid_density = self._calculate_density(snapshot.bids, mid_price)
        ask_density = self._calculate_density(snapshot.asks, mid_price)

        return OrderBookAnalysis(
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            mid_price=mid_price,
            spread=spread,
            spread_bps=spread_bps,
            is_valid=is_valid,
            depth_1pct_bid=depth_1pct_bid,
            depth_1pct_ask=depth_1pct_ask,
            depth_5pct_bid=depth_5pct_bid,
            depth_5pct_ask=depth_5pct_ask,
            total_bid_depth=total_bid_depth,
            total_ask_depth=total_ask_depth,
            liquidity_score=liquidity_score,
            liquidity_grade=liquidity_grade,
            liquidity_factors=liquidity_factors,
            bid_walls=bid_walls,
            ask_walls=ask_walls,
            imbalance=imbalance,
            imbalance_signal=imbalance_signal,
            imbalance_1pct=imbalance_1pct,
            imbalance_5pct=imbalance_5pct,
            vwap_bid=vwap_bid,
            vwap_ask=vwap_ask,
            buying_pressure=buying_pressure,
            selling_pressure=selling_pressure,
            bid_levels=len(snapshot.bids),
            ask_levels=len(snapshot.asks),
            bid_density=bid_density,
            ask_density=ask_density,
        )

    def estimate_slippage(
        self,
        snapshot: OrderBookSnapshot,
        side: str,
        size_usd: float
    ) -> SlippageEstimate:
        """
        Estimate slippage for a given order size.

        Args:
            snapshot: Order book snapshot
            side: "buy" or "sell"
            size_usd: Order size in USD

        Returns:
            SlippageEstimate with detailed breakdown
        """
        # Buy orders eat asks, sell orders eat bids
        levels = snapshot.asks if side.lower() == "buy" else snapshot.bids

        if not levels:
            return SlippageEstimate(
                side=side,
                order_size_usd=size_usd,
                avg_price=0,
                best_price=0,
                slippage_bps=0,
                filled_amount=0,
                filled_pct=0,
                unfilled_amount=size_usd,
                levels_consumed=0
            )

        best_price = levels[0][0]
        remaining = size_usd
        total_cost = 0.0
        total_size = 0.0
        levels_consumed = 0

        for price, size in levels:
            level_value = price * size
            levels_consumed += 1

            if level_value >= remaining:
                # Partial fill at this level
                fill_size = remaining / price
                total_cost += remaining
                total_size += fill_size
                remaining = 0
                break
            else:
                # Full fill at this level
                total_cost += level_value
                total_size += size
                remaining -= level_value

        if total_size == 0:
            return SlippageEstimate(
                side=side,
                order_size_usd=size_usd,
                avg_price=0,
                best_price=best_price,
                slippage_bps=0,
                filled_amount=0,
                filled_pct=0,
                unfilled_amount=size_usd,
                levels_consumed=0
            )

        avg_price = total_cost / total_size
        slippage = abs(avg_price - best_price) / best_price
        slippage_bps = slippage * 10000
        filled_amount = size_usd - remaining
        filled_pct = (filled_amount / size_usd) * 100

        return SlippageEstimate(
            side=side,
            order_size_usd=size_usd,
            avg_price=avg_price,
            best_price=best_price,
            slippage_bps=slippage_bps,
            filled_amount=filled_amount,
            filled_pct=filled_pct,
            unfilled_amount=remaining,
            levels_consumed=levels_consumed
        )

    def _calculate_depth_at_level(
        self,
        snapshot: OrderBookSnapshot,
        mid_price: float,
        pct_level: float
    ) -> Tuple[float, float]:
        """Calculate depth within a percentage of mid price."""
        if mid_price <= 0:
            return 0.0, 0.0

        bid_depth = 0.0
        ask_depth = 0.0

        lower_bound = mid_price * (1 - pct_level / 100)
        upper_bound = mid_price * (1 + pct_level / 100)

        for price, size in snapshot.bids:
            if price >= lower_bound:
                bid_depth += price * size

        for price, size in snapshot.asks:
            if price <= upper_bound:
                ask_depth += price * size

        return bid_depth, ask_depth

    def _calculate_imbalance(
        self,
        bid_depth: float,
        ask_depth: float
    ) -> Tuple[float, str]:
        """Calculate imbalance ratio and signal."""
        total = bid_depth + ask_depth

        if total == 0:
            return 0.0, "neutral"

        imbalance = (bid_depth - ask_depth) / total

        if imbalance > 0.3:
            signal = "bullish"
        elif imbalance < -0.3:
            signal = "bearish"
        else:
            signal = "neutral"

        return imbalance, signal

    def _calculate_vwap(self, levels: List[Tuple[float, float]]) -> float:
        """Calculate volume-weighted average price."""
        if not levels:
            return 0.0

        total_value = sum(price * size for price, size in levels)
        total_volume = sum(size for _, size in levels)

        if total_volume == 0:
            return 0.0

        return total_value / total_volume

    def _detect_walls(
        self,
        levels: List[Tuple[float, float]],
        mid_price: float,
        wall_type: str
    ) -> List[Wall]:
        """Detect large walls in order book."""
        if len(levels) < 3:  # Need at least 3 levels to detect walls
            return []

        # Calculate average size (excluding outliers)
        sizes = [size for _, size in levels]
        if not sizes:
            return []

        avg_size = sum(sizes) / len(sizes)
        if avg_size == 0:
            return []

        walls = []

        for i, (price, size) in enumerate(levels):
            # Calculate local average (surrounding levels)
            start = max(0, i - 2)
            end = min(len(levels), i + 3)
            surrounding = [levels[j][1] for j in range(start, end) if j != i]

            if not surrounding:
                continue

            local_avg = sum(surrounding) / len(surrounding)
            if local_avg == 0:
                local_avg = avg_size

            strength = size / local_avg

            if strength >= self.wall_threshold:
                distance_pct = 0.0
                if mid_price > 0:
                    distance_pct = abs(price - mid_price) / mid_price * 100

                walls.append(Wall(
                    price=price,
                    size=size,
                    value_usd=price * size,
                    wall_type=wall_type,
                    strength=strength,
                    distance_from_mid_pct=distance_pct
                ))

        # Sort by strength descending
        walls.sort(key=lambda w: w.strength, reverse=True)

        return walls[:5]  # Return top 5 walls

    def _calculate_liquidity_score(
        self,
        spread_bps: float,
        bid_depth: float,
        ask_depth: float,
        bid_levels: int,
        ask_levels: int
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculate liquidity quality score (0-1).

        Components:
        - Spread score: Tighter spread = higher score
        - Depth score: More depth = higher score
        - Balance score: More balanced = higher score
        """
        # Spread score (inverse relationship)
        # 0-10 bps = 1.0, 10-50 bps = 0.8-1.0, 50-200 bps = 0.4-0.8, >200 = 0-0.4
        if spread_bps <= 10:
            spread_score = 1.0
        elif spread_bps <= 50:
            spread_score = 0.8 + 0.2 * (50 - spread_bps) / 40
        elif spread_bps <= 200:
            spread_score = 0.4 + 0.4 * (200 - spread_bps) / 150
        elif spread_bps <= 1000:
            spread_score = 0.1 + 0.3 * (1000 - spread_bps) / 800
        else:
            spread_score = max(0, 0.1 - (spread_bps - 1000) / 10000)

        # Depth score (logarithmic)
        total_depth = bid_depth + ask_depth
        # $1M depth = 1.0, $100k = 0.8, $10k = 0.6, $1k = 0.4
        if total_depth >= 1_000_000:
            depth_score = 1.0
        elif total_depth >= 100_000:
            depth_score = 0.8 + 0.2 * (total_depth - 100_000) / 900_000
        elif total_depth >= 10_000:
            depth_score = 0.6 + 0.2 * (total_depth - 10_000) / 90_000
        elif total_depth >= 1_000:
            depth_score = 0.4 + 0.2 * (total_depth - 1_000) / 9_000
        elif total_depth > 0:
            depth_score = 0.4 * total_depth / 1_000
        else:
            depth_score = 0.0

        # Balance score (how even is bid/ask)
        if bid_depth + ask_depth > 0:
            balance = min(bid_depth, ask_depth) / max(bid_depth, ask_depth)
            balance_score = balance
        else:
            balance_score = 0.0

        # Level count score
        total_levels = bid_levels + ask_levels
        if total_levels >= 40:
            level_score = 1.0
        elif total_levels >= 20:
            level_score = 0.7 + 0.3 * (total_levels - 20) / 20
        elif total_levels >= 10:
            level_score = 0.4 + 0.3 * (total_levels - 10) / 10
        else:
            level_score = 0.4 * total_levels / 10

        # Weighted average
        weights = {
            'spread_score': 0.35,
            'depth_score': 0.35,
            'balance_score': 0.15,
            'level_score': 0.15
        }

        factors = {
            'spread_score': spread_score,
            'depth_score': depth_score,
            'balance_score': balance_score,
            'level_score': level_score
        }

        total_score = sum(
            factors[k] * weights[k] for k in factors
        )

        return total_score, factors

    def _get_liquidity_grade(self, score: float) -> LiquidityGrade:
        """Convert score to grade."""
        if score >= self.EXCELLENT_LIQUIDITY_THRESHOLD:
            return LiquidityGrade.EXCELLENT
        elif score >= self.GOOD_LIQUIDITY_THRESHOLD:
            return LiquidityGrade.GOOD
        elif score >= self.FAIR_LIQUIDITY_THRESHOLD:
            return LiquidityGrade.FAIR
        elif score >= self.POOR_LIQUIDITY_THRESHOLD:
            return LiquidityGrade.POOR
        else:
            return LiquidityGrade.ILLIQUID

    def _calculate_pressure(
        self,
        snapshot: OrderBookSnapshot,
        mid_price: float
    ) -> Tuple[float, float]:
        """
        Calculate buying and selling pressure.

        Based on depth concentration near the spread.
        """
        if mid_price <= 0:
            return 0.5, 0.5

        # Calculate depth within 2% of mid
        near_bid_depth = 0.0
        near_ask_depth = 0.0

        lower_bound = mid_price * 0.98
        upper_bound = mid_price * 1.02

        for price, size in snapshot.bids:
            if price >= lower_bound:
                near_bid_depth += price * size

        for price, size in snapshot.asks:
            if price <= upper_bound:
                near_ask_depth += price * size

        total = near_bid_depth + near_ask_depth

        if total == 0:
            return 0.5, 0.5

        buying_pressure = near_bid_depth / total
        selling_pressure = near_ask_depth / total

        return buying_pressure, selling_pressure

    def _calculate_density(
        self,
        levels: List[Tuple[float, float]],
        mid_price: float
    ) -> float:
        """Calculate order book density (levels per percent)."""
        if not levels or mid_price <= 0:
            return 0.0

        prices = [p for p, _ in levels]
        price_range = max(prices) - min(prices)

        if price_range <= 0:
            return 0.0

        # Range as percentage of mid
        range_pct = (price_range / mid_price) * 100

        if range_pct <= 0:
            return 0.0

        return len(levels) / range_pct


# Singleton instance
_analyzer: Optional[OrderBookAnalyzer] = None


def get_order_book_analyzer() -> OrderBookAnalyzer:
    """Get singleton order book analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = OrderBookAnalyzer()
    return _analyzer
