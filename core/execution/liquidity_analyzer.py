"""
Liquidity Depth Analyzer

Analyzes pool liquidity and recommends the appropriate execution algorithm.

Usage:
    from core.execution.liquidity_analyzer import LiquidityAnalyzer

    analyzer = LiquidityAnalyzer(jupiter_client)
    rec = analyzer.recommend_algorithm(order_size=1000, pool_liquidity=500_000)
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class AlgorithmRecommendation:
    """Recommendation for execution algorithm."""
    algorithm: str  # "MARKET", "TWAP", "VWAP", "ICEBERG"
    reason: str
    estimated_duration_mins: float = 0.0
    suggested_intervals: int = 1
    estimated_slippage_bps: float = 0.0
    confidence: float = 1.0


class LiquidityAnalyzer:
    """
    Analyzes liquidity and recommends execution algorithms.

    Considers:
    - Order size relative to pool liquidity
    - 24h trading volume
    - Volume pattern predictability
    - Urgency requirements
    """

    # Thresholds
    MARKET_IMPACT_THRESHOLD = 0.001  # 0.1% - below this, use MARKET
    TWAP_IMPACT_THRESHOLD = 0.01     # 1% - below this, use TWAP
    VWAP_PREDICTABILITY_THRESHOLD = 0.6  # Volume predictability score

    # Default durations
    DEFAULT_TWAP_DURATION = 30  # 30 minutes
    DEFAULT_VWAP_DURATION = 60  # 1 hour
    DEFAULT_ICEBERG_DURATION = 120  # 2 hours

    def __init__(self, jupiter_client: Any):
        """
        Initialize the analyzer.

        Args:
            jupiter_client: Jupiter API client for price/liquidity data
        """
        self.jupiter = jupiter_client

    async def _fetch_pool_liquidity(self, token_mint: str) -> float:
        """
        Fetch pool liquidity for a token.

        Args:
            token_mint: Token mint address

        Returns:
            Pool liquidity in USD
        """
        try:
            # This would typically call an external API
            # For now, return a placeholder
            logger.debug(f"Fetching liquidity for {token_mint[:8]}...")
            return 0.0
        except Exception as e:
            logger.warning(f"Failed to fetch liquidity: {e}")
            return 0.0

    async def get_pool_liquidity(self, token_mint: str) -> float:
        """
        Get pool liquidity for a token.

        Args:
            token_mint: Token mint address

        Returns:
            Pool liquidity in USD
        """
        return await self._fetch_pool_liquidity(token_mint)

    def calculate_impact(
        self,
        order_size_usd: float,
        pool_liquidity_usd: float,
    ) -> float:
        """
        Calculate order impact on pool.

        Args:
            order_size_usd: Order size in USD
            pool_liquidity_usd: Pool liquidity in USD

        Returns:
            Impact as a decimal (0.01 = 1%)
        """
        if pool_liquidity_usd <= 0:
            return 1.0  # Maximum impact
        return order_size_usd / pool_liquidity_usd

    async def get_volume_predictability(self, token_mint: str) -> float:
        """
        Assess how predictable the volume pattern is.

        Args:
            token_mint: Token mint address

        Returns:
            Predictability score (0.0 to 1.0)
        """
        # This would analyze historical volume patterns
        # For now, return a default
        return 0.5

    def recommend_algorithm(
        self,
        order_size_usd: float,
        pool_liquidity_usd: float,
        urgency: str = "medium",
        volume_24h: float = 0.0,
    ) -> AlgorithmRecommendation:
        """
        Recommend an execution algorithm.

        Args:
            order_size_usd: Order size in USD
            pool_liquidity_usd: Pool liquidity in USD
            urgency: "low", "medium", or "high"
            volume_24h: 24-hour trading volume in USD

        Returns:
            AlgorithmRecommendation
        """
        # High urgency always uses market order
        if urgency == "high":
            return AlgorithmRecommendation(
                algorithm="MARKET",
                reason="High urgency requires immediate execution",
                estimated_duration_mins=0.1,
                suggested_intervals=1,
            )

        # Calculate impact
        impact = self.calculate_impact(order_size_usd, pool_liquidity_usd)

        # Very small impact - use market order
        if impact <= self.MARKET_IMPACT_THRESHOLD:
            return AlgorithmRecommendation(
                algorithm="MARKET",
                reason=f"Order impact ({impact*100:.2f}%) is below threshold",
                estimated_duration_mins=0.1,
                suggested_intervals=1,
            )

        # Check volume impact if 24h volume is available
        volume_impact = 0.0
        if volume_24h > 0:
            volume_impact = order_size_usd / volume_24h

        # Large impact - use ICEBERG
        if impact > self.TWAP_IMPACT_THRESHOLD:
            # Calculate duration based on impact
            duration_factor = min(4.0, impact / self.TWAP_IMPACT_THRESHOLD)
            duration = self.DEFAULT_ICEBERG_DURATION * duration_factor
            intervals = max(10, int(impact / self.MARKET_IMPACT_THRESHOLD))

            return AlgorithmRecommendation(
                algorithm="ICEBERG",
                reason=f"Large order ({impact*100:.2f}% of pool) requires iceberg execution",
                estimated_duration_mins=duration,
                suggested_intervals=intervals,
                estimated_slippage_bps=impact * 100,  # Rough estimate
            )

        # Medium impact with low urgency - use TWAP
        if urgency == "low":
            duration = self.DEFAULT_TWAP_DURATION
            intervals = max(5, int(impact / self.MARKET_IMPACT_THRESHOLD * 10))

            return AlgorithmRecommendation(
                algorithm="TWAP",
                reason=f"Medium impact ({impact*100:.2f}%) with low urgency - TWAP recommended",
                estimated_duration_mins=duration,
                suggested_intervals=intervals,
                estimated_slippage_bps=impact * 50,
            )

        # Default to TWAP for medium urgency
        return AlgorithmRecommendation(
            algorithm="TWAP",
            reason=f"Medium impact ({impact*100:.2f}%) - TWAP recommended",
            estimated_duration_mins=self.DEFAULT_TWAP_DURATION / 2,
            suggested_intervals=5,
            estimated_slippage_bps=impact * 75,
        )

    async def recommend_algorithm_async(
        self,
        order_size_usd: float,
        pool_liquidity_usd: float,
        token_mint: str,
        urgency: str = "medium",
    ) -> AlgorithmRecommendation:
        """
        Recommend an algorithm with async data fetching.

        Args:
            order_size_usd: Order size in USD
            pool_liquidity_usd: Pool liquidity in USD
            token_mint: Token mint address
            urgency: "low", "medium", or "high"

        Returns:
            AlgorithmRecommendation
        """
        # Check volume predictability
        predictability = await self.get_volume_predictability(token_mint)

        # If volume is highly predictable and urgency is low, consider VWAP
        if predictability >= self.VWAP_PREDICTABILITY_THRESHOLD and urgency == "low":
            impact = self.calculate_impact(order_size_usd, pool_liquidity_usd)

            # Only use VWAP for medium-sized orders
            if self.MARKET_IMPACT_THRESHOLD < impact <= self.TWAP_IMPACT_THRESHOLD:
                return AlgorithmRecommendation(
                    algorithm="VWAP",
                    reason=f"High volume predictability ({predictability:.2f}) enables VWAP",
                    estimated_duration_mins=self.DEFAULT_VWAP_DURATION,
                    suggested_intervals=12,  # Hourly for 12 hours
                    confidence=predictability,
                )

        # Fall back to sync recommendation
        return self.recommend_algorithm(order_size_usd, pool_liquidity_usd, urgency)
