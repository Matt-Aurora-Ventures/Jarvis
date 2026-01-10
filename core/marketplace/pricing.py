"""
Dynamic Pricing System
Prompt #95: Dynamic pricing for data packages

Calculates prices based on data value and market conditions.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.marketplace.packager import DataCategory

logger = logging.getLogger("jarvis.marketplace.pricing")


# =============================================================================
# MODELS
# =============================================================================

class PricingTier(Enum):
    """Pricing tiers"""
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"


@dataclass
class PriceQuote:
    """A price quote for a data package"""
    base_price_sol: float
    category_multiplier: float
    volume_multiplier: float
    quality_multiplier: float
    freshness_multiplier: float
    demand_multiplier: float
    final_price_sol: float
    tier: PricingTier
    valid_until: datetime
    breakdown: Dict[str, float] = field(default_factory=dict)


@dataclass
class PricingConfig:
    """Pricing configuration"""
    base_price_per_record: float = 0.00001  # SOL per record
    min_price: float = 0.01  # Minimum price in SOL
    max_price: float = 100.0  # Maximum price in SOL
    freshness_decay_days: int = 30  # Days until data is "stale"


# =============================================================================
# CATEGORY MULTIPLIERS
# =============================================================================

CATEGORY_MULTIPLIERS = {
    DataCategory.TRADE_PATTERNS: 1.5,
    DataCategory.STRATEGY_SIGNALS: 2.0,
    DataCategory.MARKET_TIMING: 1.8,
    DataCategory.TOKEN_ANALYSIS: 1.2,
    DataCategory.AGGREGATE_METRICS: 1.0,
}


# =============================================================================
# DYNAMIC PRICER
# =============================================================================

class DynamicPricer:
    """
    Calculates dynamic prices for data packages.

    Factors:
    - Data category (strategy signals worth more)
    - Data volume (bulk discounts)
    - Data quality (higher quality = higher price)
    - Data freshness (recent data worth more)
    - Market demand (popular packages cost more)
    """

    def __init__(self, config: PricingConfig = None):
        self.config = config or PricingConfig()

    # =========================================================================
    # PRICE CALCULATION
    # =========================================================================

    def calculate_price(
        self,
        record_count: int,
        category: DataCategory,
        quality_score: float = 0.8,
        data_age_days: int = 0,
        purchase_count: int = 0,
    ) -> PriceQuote:
        """
        Calculate price for a data package.

        Args:
            record_count: Number of data records
            category: Data category
            quality_score: Quality score 0-1
            data_age_days: Age of data in days
            purchase_count: Number of prior purchases

        Returns:
            PriceQuote with price breakdown
        """
        # Base price
        base_price = record_count * self.config.base_price_per_record

        # Category multiplier
        category_mult = CATEGORY_MULTIPLIERS.get(category, 1.0)

        # Volume multiplier (bulk discount)
        volume_mult = self._calculate_volume_multiplier(record_count)

        # Quality multiplier
        quality_mult = self._calculate_quality_multiplier(quality_score)

        # Freshness multiplier
        freshness_mult = self._calculate_freshness_multiplier(data_age_days)

        # Demand multiplier
        demand_mult = self._calculate_demand_multiplier(purchase_count)

        # Calculate final price
        final_price = (
            base_price *
            category_mult *
            volume_mult *
            quality_mult *
            freshness_mult *
            demand_mult
        )

        # Apply min/max bounds
        final_price = max(self.config.min_price, min(final_price, self.config.max_price))

        # Determine tier
        tier = self._determine_tier(final_price)

        return PriceQuote(
            base_price_sol=base_price,
            category_multiplier=category_mult,
            volume_multiplier=volume_mult,
            quality_multiplier=quality_mult,
            freshness_multiplier=freshness_mult,
            demand_multiplier=demand_mult,
            final_price_sol=round(final_price, 4),
            tier=tier,
            valid_until=datetime.now(timezone.utc),
            breakdown={
                "base": base_price,
                "after_category": base_price * category_mult,
                "after_volume": base_price * category_mult * volume_mult,
                "after_quality": base_price * category_mult * volume_mult * quality_mult,
                "after_freshness": base_price * category_mult * volume_mult * quality_mult * freshness_mult,
                "final": final_price,
            },
        )

    def _calculate_volume_multiplier(self, record_count: int) -> float:
        """
        Calculate volume-based multiplier.

        Bulk discount: more records = lower per-record price
        """
        if record_count <= 100:
            return 1.0
        elif record_count <= 1000:
            return 0.9
        elif record_count <= 10000:
            return 0.75
        elif record_count <= 100000:
            return 0.6
        else:
            return 0.5

    def _calculate_quality_multiplier(self, quality_score: float) -> float:
        """
        Calculate quality-based multiplier.

        Higher quality = higher price
        """
        # Ensure score is in range
        score = max(0.0, min(1.0, quality_score))

        # Linear scaling: 0.5 -> 0.7x, 0.8 -> 1.0x, 1.0 -> 1.3x
        return 0.4 + (score * 0.9)

    def _calculate_freshness_multiplier(self, data_age_days: int) -> float:
        """
        Calculate freshness-based multiplier.

        Newer data is worth more, decays over time
        """
        if data_age_days <= 0:
            return 1.2  # Very fresh

        # Exponential decay
        decay = math.exp(-data_age_days / self.config.freshness_decay_days)

        # Range: 0.5 to 1.2
        return 0.5 + (0.7 * decay)

    def _calculate_demand_multiplier(self, purchase_count: int) -> float:
        """
        Calculate demand-based multiplier.

        Popular packages can command higher prices
        """
        if purchase_count <= 0:
            return 1.0
        elif purchase_count <= 10:
            return 1.05
        elif purchase_count <= 50:
            return 1.1
        elif purchase_count <= 100:
            return 1.15
        else:
            return 1.2

    def _determine_tier(self, price: float) -> PricingTier:
        """Determine pricing tier from price"""
        if price < 0.1:
            return PricingTier.BASIC
        elif price < 1.0:
            return PricingTier.STANDARD
        elif price < 10.0:
            return PricingTier.PREMIUM
        else:
            return PricingTier.ENTERPRISE

    # =========================================================================
    # SUBSCRIPTION PRICING
    # =========================================================================

    def calculate_subscription_price(
        self,
        categories: List[DataCategory],
        access_level: str = "standard",
    ) -> float:
        """
        Calculate subscription price for category access.

        Args:
            categories: Categories to access
            access_level: "basic", "standard", or "premium"

        Returns:
            Monthly subscription price in SOL
        """
        # Base prices per category
        category_prices = {
            DataCategory.TRADE_PATTERNS: 0.5,
            DataCategory.STRATEGY_SIGNALS: 1.0,
            DataCategory.MARKET_TIMING: 0.8,
            DataCategory.TOKEN_ANALYSIS: 0.3,
            DataCategory.AGGREGATE_METRICS: 0.2,
        }

        # Access level multipliers
        level_mult = {
            "basic": 0.5,
            "standard": 1.0,
            "premium": 2.0,
        }

        base_price = sum(category_prices.get(c, 0.2) for c in categories)
        multiplier = level_mult.get(access_level, 1.0)

        return round(base_price * multiplier, 2)

    # =========================================================================
    # CONTRIBUTOR PAYOUT RATES
    # =========================================================================

    def calculate_contributor_rate(
        self,
        contribution_pct: float,
        package_price: float,
    ) -> float:
        """
        Calculate payout for a contributor.

        Contributors get 70% of package price, distributed by contribution
        """
        CONTRIBUTOR_SHARE = 0.70  # 70% to contributors

        return package_price * CONTRIBUTOR_SHARE * (contribution_pct / 100)


# =============================================================================
# SINGLETON
# =============================================================================

_pricer: Optional[DynamicPricer] = None


def get_dynamic_pricer() -> DynamicPricer:
    """Get or create the dynamic pricer singleton"""
    global _pricer
    if _pricer is None:
        _pricer = DynamicPricer()
    return _pricer
