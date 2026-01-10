"""
Pricing Engine
Prompts #71-73: Dynamic pricing, price comparison, and APY calculations
"""

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import statistics

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Fee bounds (basis points)
MIN_FEE_BPS = 10      # 0.1% minimum
MAX_FEE_BPS = 500     # 5% maximum
BASE_FEE_BPS = 100    # 1% base

# Dynamic pricing factors
VOLUME_WEIGHT = 0.3
VOLATILITY_WEIGHT = 0.3
DEMAND_WEIGHT = 0.2
COMPETITION_WEIGHT = 0.2

# APY calculation constants
SECONDS_PER_YEAR = 31536000
BLOCKS_PER_YEAR = 15768000  # ~2 sec blocks

# Price feed staleness threshold
PRICE_STALENESS_SECONDS = 60


# =============================================================================
# MODELS
# =============================================================================

class PriceSource(str, Enum):
    JUPITER = "jupiter"
    RAYDIUM = "raydium"
    ORCA = "orca"
    BIRDEYE = "birdeye"
    PYTH = "pyth"
    SWITCHBOARD = "switchboard"


class FeeType(str, Enum):
    SWAP = "swap"
    STAKE = "stake"
    UNSTAKE = "unstake"
    CLAIM = "claim"
    TRANSFER = "transfer"
    BRIDGE = "bridge"


@dataclass
class PriceData:
    """Price data from a source"""
    source: PriceSource
    token_mint: str
    price_usd: Decimal
    price_sol: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0
    volume_24h: Optional[Decimal] = None
    liquidity: Optional[Decimal] = None


@dataclass
class PriceQuote:
    """A price quote for an operation"""
    input_token: str
    output_token: str
    input_amount: int
    output_amount: int
    price_impact_bps: int
    fee_amount: int
    fee_bps: int
    route: List[str]
    expires_at: datetime
    source: PriceSource


@dataclass
class APYBreakdown:
    """Breakdown of APY components"""
    base_apy: float
    boost_apy: float
    rewards_apy: float
    lp_fees_apy: float
    total_apy: float
    time_multiplier: float
    tier_multiplier: float


@dataclass
class DynamicFeeResult:
    """Result of dynamic fee calculation"""
    fee_bps: int
    base_fee_bps: int
    volume_adjustment: int
    volatility_adjustment: int
    demand_adjustment: int
    tier_discount_bps: int
    final_fee_bps: int
    reasoning: str


# =============================================================================
# DYNAMIC PRICING ENGINE
# =============================================================================

class DynamicPricingEngine:
    """Calculates dynamic fees based on market conditions"""

    def __init__(self):
        self.volume_history: List[Tuple[datetime, Decimal]] = []
        self.price_history: Dict[str, List[Tuple[datetime, Decimal]]] = {}
        self.demand_metrics: Dict[str, int] = {}

    async def calculate_fee(
        self,
        fee_type: FeeType,
        amount: int,
        token_mint: str,
        user_tier: str = "free",
        current_volume_24h: Decimal = Decimal("0"),
        volatility_24h: float = 0.0
    ) -> DynamicFeeResult:
        """Calculate dynamic fee for an operation"""

        # Base fee by type
        base_fees = {
            FeeType.SWAP: 30,      # 0.3%
            FeeType.STAKE: 10,     # 0.1%
            FeeType.UNSTAKE: 20,   # 0.2%
            FeeType.CLAIM: 5,      # 0.05%
            FeeType.TRANSFER: 10,  # 0.1%
            FeeType.BRIDGE: 50,    # 0.5%
        }
        base_fee = base_fees.get(fee_type, BASE_FEE_BPS)

        # Volume adjustment: Higher volume = lower fees (economies of scale)
        volume_adjustment = self._calculate_volume_adjustment(current_volume_24h)

        # Volatility adjustment: Higher volatility = higher fees (risk premium)
        volatility_adjustment = self._calculate_volatility_adjustment(volatility_24h)

        # Demand adjustment: Higher demand = slightly higher fees
        demand_adjustment = self._calculate_demand_adjustment(token_mint)

        # Tier discount
        tier_discounts = {
            "free": 0,
            "starter": 10,   # 0.1% off
            "pro": 20,       # 0.2% off
            "enterprise": 35,# 0.35% off
            "whale": 50      # 0.5% off
        }
        tier_discount = tier_discounts.get(user_tier, 0)

        # Calculate final fee
        raw_fee = (
            base_fee
            + volume_adjustment
            + volatility_adjustment
            + demand_adjustment
            - tier_discount
        )

        # Clamp to bounds
        final_fee = max(MIN_FEE_BPS, min(MAX_FEE_BPS, raw_fee))

        # Build reasoning
        adjustments = []
        if volume_adjustment != 0:
            adjustments.append(f"volume {'+' if volume_adjustment > 0 else ''}{volume_adjustment}bps")
        if volatility_adjustment != 0:
            adjustments.append(f"volatility +{volatility_adjustment}bps")
        if demand_adjustment != 0:
            adjustments.append(f"demand +{demand_adjustment}bps")
        if tier_discount > 0:
            adjustments.append(f"tier discount -{tier_discount}bps")

        reasoning = f"Base {base_fee}bps"
        if adjustments:
            reasoning += f" ({', '.join(adjustments)})"

        return DynamicFeeResult(
            fee_bps=base_fee,
            base_fee_bps=base_fee,
            volume_adjustment=volume_adjustment,
            volatility_adjustment=volatility_adjustment,
            demand_adjustment=demand_adjustment,
            tier_discount_bps=tier_discount,
            final_fee_bps=final_fee,
            reasoning=reasoning
        )

    def _calculate_volume_adjustment(self, volume_24h: Decimal) -> int:
        """Calculate volume-based fee adjustment"""
        # Higher volume = lower fees
        # $0-$10K: 0 adjustment
        # $10K-$100K: -5 bps
        # $100K-$1M: -10 bps
        # $1M+: -15 bps
        if volume_24h >= 1_000_000:
            return -15
        elif volume_24h >= 100_000:
            return -10
        elif volume_24h >= 10_000:
            return -5
        return 0

    def _calculate_volatility_adjustment(self, volatility_24h: float) -> int:
        """Calculate volatility-based fee adjustment"""
        # Higher volatility = higher fees (risk premium)
        # < 2%: 0 adjustment
        # 2-5%: +5 bps
        # 5-10%: +10 bps
        # 10%+: +20 bps
        if volatility_24h >= 0.10:
            return 20
        elif volatility_24h >= 0.05:
            return 10
        elif volatility_24h >= 0.02:
            return 5
        return 0

    def _calculate_demand_adjustment(self, token_mint: str) -> int:
        """Calculate demand-based fee adjustment"""
        requests = self.demand_metrics.get(token_mint, 0)
        # Track requests in last hour
        if requests > 1000:
            return 10
        elif requests > 500:
            return 5
        return 0

    def record_request(self, token_mint: str):
        """Record a request for demand tracking"""
        self.demand_metrics[token_mint] = self.demand_metrics.get(token_mint, 0) + 1


# =============================================================================
# PRICE COMPARISON ENGINE
# =============================================================================

class PriceComparisonEngine:
    """Compares prices across multiple sources"""

    def __init__(self):
        self.price_cache: Dict[str, List[PriceData]] = {}
        self.source_reliability: Dict[PriceSource, float] = {
            PriceSource.PYTH: 0.95,
            PriceSource.SWITCHBOARD: 0.90,
            PriceSource.JUPITER: 0.85,
            PriceSource.BIRDEYE: 0.80,
            PriceSource.RAYDIUM: 0.75,
            PriceSource.ORCA: 0.75,
        }

    async def get_best_price(
        self,
        token_mint: str,
        sources: List[PriceSource] = None
    ) -> Optional[PriceData]:
        """Get the best price from available sources"""
        sources = sources or list(PriceSource)
        prices = await self.fetch_prices(token_mint, sources)

        if not prices:
            return None

        # Filter stale prices
        fresh_prices = [
            p for p in prices
            if (datetime.utcnow() - p.timestamp).seconds < PRICE_STALENESS_SECONDS
        ]

        if not fresh_prices:
            # Fall back to most recent if all stale
            fresh_prices = prices

        # Weight by reliability and confidence
        def price_score(p: PriceData) -> float:
            reliability = self.source_reliability.get(p.source, 0.5)
            return reliability * p.confidence

        best = max(fresh_prices, key=price_score)
        return best

    async def fetch_prices(
        self,
        token_mint: str,
        sources: List[PriceSource]
    ) -> List[PriceData]:
        """Fetch prices from multiple sources"""
        # In production, fetch from actual APIs
        # Mock implementation for now
        prices = []

        for source in sources:
            if source == PriceSource.PYTH:
                prices.append(PriceData(
                    source=source,
                    token_mint=token_mint,
                    price_usd=Decimal("1.00"),
                    confidence=0.95
                ))
            elif source == PriceSource.JUPITER:
                prices.append(PriceData(
                    source=source,
                    token_mint=token_mint,
                    price_usd=Decimal("1.01"),
                    confidence=0.90,
                    volume_24h=Decimal("1000000")
                ))

        self.price_cache[token_mint] = prices
        return prices

    async def get_price_deviation(
        self,
        token_mint: str
    ) -> Dict[str, Any]:
        """Get price deviation across sources"""
        prices = self.price_cache.get(token_mint, [])

        if len(prices) < 2:
            return {"deviation": 0, "sources": len(prices)}

        price_values = [float(p.price_usd) for p in prices]
        mean_price = statistics.mean(price_values)
        std_dev = statistics.stdev(price_values) if len(price_values) > 1 else 0

        return {
            "mean_price": mean_price,
            "std_deviation": std_dev,
            "deviation_percent": (std_dev / mean_price * 100) if mean_price > 0 else 0,
            "min_price": min(price_values),
            "max_price": max(price_values),
            "spread_percent": (
                (max(price_values) - min(price_values)) / mean_price * 100
                if mean_price > 0 else 0
            ),
            "sources": len(prices)
        }

    async def get_quote_comparison(
        self,
        input_token: str,
        output_token: str,
        amount: int
    ) -> List[PriceQuote]:
        """Get and compare quotes from multiple DEXs"""
        quotes = []

        # Mock quotes from different sources
        sources = [
            (PriceSource.JUPITER, 0.997),
            (PriceSource.RAYDIUM, 0.995),
            (PriceSource.ORCA, 0.996),
        ]

        for source, rate in sources:
            output_amount = int(amount * rate)
            fee_bps = 30  # 0.3%
            fee_amount = amount * fee_bps // 10000

            quotes.append(PriceQuote(
                input_token=input_token,
                output_token=output_token,
                input_amount=amount,
                output_amount=output_amount,
                price_impact_bps=int((1 - rate) * 10000),
                fee_amount=fee_amount,
                fee_bps=fee_bps,
                route=[input_token, output_token],
                expires_at=datetime.utcnow() + timedelta(seconds=30),
                source=source
            ))

        # Sort by output amount (best first)
        quotes.sort(key=lambda q: q.output_amount, reverse=True)
        return quotes


# =============================================================================
# APY CALCULATOR
# =============================================================================

class APYCalculator:
    """Calculates and projects APY for staking and LP positions"""

    def __init__(self):
        self.historical_rates: Dict[str, List[Tuple[datetime, float]]] = {}

    def calculate_staking_apy(
        self,
        base_rate: float,
        stake_duration_days: int,
        user_tier: str = "free",
        bonus_multiplier: float = 1.0
    ) -> APYBreakdown:
        """Calculate staking APY with all multipliers"""

        # Time multiplier (1.0x to 2.5x over 365 days)
        time_multiplier = min(2.5, 1.0 + (stake_duration_days / 365) * 1.5)

        # Tier multiplier
        tier_multipliers = {
            "free": 1.0,
            "starter": 1.1,
            "pro": 1.25,
            "enterprise": 1.5,
            "whale": 2.0
        }
        tier_multiplier = tier_multipliers.get(user_tier, 1.0)

        # Base APY with multipliers
        effective_base = base_rate * time_multiplier * tier_multiplier

        # Boost APY from NFTs or other sources
        boost_apy = (bonus_multiplier - 1.0) * base_rate

        # Total APY
        total_apy = effective_base + boost_apy

        return APYBreakdown(
            base_apy=base_rate,
            boost_apy=boost_apy,
            rewards_apy=0,
            lp_fees_apy=0,
            total_apy=total_apy,
            time_multiplier=time_multiplier,
            tier_multiplier=tier_multiplier
        )

    def calculate_lp_apy(
        self,
        pool_tvl: Decimal,
        volume_24h: Decimal,
        fee_rate: float,
        rewards_per_day: Decimal,
        reward_price_usd: Decimal
    ) -> APYBreakdown:
        """Calculate LP position APY"""

        # Trading fee APY
        if pool_tvl > 0:
            daily_fees = float(volume_24h) * fee_rate
            fee_apy = (daily_fees * 365 / float(pool_tvl)) * 100
        else:
            fee_apy = 0

        # Rewards APY
        if pool_tvl > 0:
            daily_rewards_usd = float(rewards_per_day * reward_price_usd)
            rewards_apy = (daily_rewards_usd * 365 / float(pool_tvl)) * 100
        else:
            rewards_apy = 0

        total_apy = fee_apy + rewards_apy

        return APYBreakdown(
            base_apy=0,
            boost_apy=0,
            rewards_apy=rewards_apy,
            lp_fees_apy=fee_apy,
            total_apy=total_apy,
            time_multiplier=1.0,
            tier_multiplier=1.0
        )

    def calculate_compound_apy(
        self,
        apr: float,
        compounds_per_year: int = 365
    ) -> float:
        """Convert APR to APY with compounding"""
        if compounds_per_year <= 0:
            return apr
        apy = (1 + apr / compounds_per_year) ** compounds_per_year - 1
        return apy * 100

    def project_earnings(
        self,
        principal: Decimal,
        apy: float,
        days: int,
        additional_deposits: List[Tuple[int, Decimal]] = None
    ) -> Dict[str, Any]:
        """Project earnings over time"""
        additional_deposits = additional_deposits or []

        # Daily rate
        daily_rate = (1 + apy / 100) ** (1 / 365) - 1

        balance = float(principal)
        daily_balances = []
        total_deposited = float(principal)

        for day in range(days):
            # Apply interest
            balance *= (1 + daily_rate)

            # Check for additional deposits
            for deposit_day, amount in additional_deposits:
                if deposit_day == day:
                    balance += float(amount)
                    total_deposited += float(amount)

            daily_balances.append(balance)

        total_earnings = balance - total_deposited

        return {
            "final_balance": balance,
            "total_deposited": total_deposited,
            "total_earnings": total_earnings,
            "earnings_percent": (total_earnings / total_deposited * 100) if total_deposited > 0 else 0,
            "daily_balances": daily_balances[-30:],  # Last 30 days
            "effective_apy": apy
        }

    def calculate_impermanent_loss(
        self,
        initial_price_ratio: float,
        current_price_ratio: float
    ) -> float:
        """Calculate impermanent loss for an LP position"""
        # IL formula: IL = 2 * sqrt(price_change) / (1 + price_change) - 1
        price_change = current_price_ratio / initial_price_ratio

        if price_change <= 0:
            return 0

        il = 2 * math.sqrt(price_change) / (1 + price_change) - 1
        return abs(il) * 100  # Return as percentage


# =============================================================================
# ANTI-GOUGING SYSTEM
# =============================================================================

class AntiGougingMonitor:
    """Monitors for price gouging and fee exploitation"""

    def __init__(self, max_fee_bps: int = MAX_FEE_BPS):
        self.max_fee_bps = max_fee_bps
        self.fee_history: List[Tuple[datetime, int, str]] = []
        self.alerts: List[Dict[str, Any]] = []

    def check_fee(
        self,
        fee_bps: int,
        operation: str,
        context: Dict[str, Any] = None
    ) -> Tuple[bool, Optional[str]]:
        """Check if a fee is within acceptable bounds"""

        # Absolute maximum check
        if fee_bps > self.max_fee_bps:
            reason = f"Fee {fee_bps}bps exceeds maximum {self.max_fee_bps}bps"
            self._record_alert("max_exceeded", fee_bps, operation, reason)
            return False, reason

        # Check for sudden spikes
        recent_fees = [
            f for t, f, _ in self.fee_history
            if (datetime.utcnow() - t).seconds < 300  # Last 5 minutes
        ]

        if recent_fees:
            avg_recent = sum(recent_fees) / len(recent_fees)
            if fee_bps > avg_recent * 2:  # More than 2x average
                reason = f"Fee {fee_bps}bps is {fee_bps/avg_recent:.1f}x recent average"
                self._record_alert("spike_detected", fee_bps, operation, reason)
                # Allow but warn
                return True, reason

        # Record fee
        self.fee_history.append((datetime.utcnow(), fee_bps, operation))

        # Trim old history
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.fee_history = [
            (t, f, o) for t, f, o in self.fee_history if t > cutoff
        ]

        return True, None

    def _record_alert(
        self,
        alert_type: str,
        fee_bps: int,
        operation: str,
        reason: str
    ):
        """Record a gouging alert"""
        self.alerts.append({
            "type": alert_type,
            "fee_bps": fee_bps,
            "operation": operation,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        })
        logger.warning(f"Anti-gouging alert: {reason}")

    def get_fee_statistics(self) -> Dict[str, Any]:
        """Get fee statistics"""
        if not self.fee_history:
            return {"no_data": True}

        fees = [f for _, f, _ in self.fee_history]

        return {
            "count": len(fees),
            "min_bps": min(fees),
            "max_bps": max(fees),
            "avg_bps": sum(fees) / len(fees),
            "alerts_24h": len([
                a for a in self.alerts
                if datetime.fromisoformat(a["timestamp"]) > datetime.utcnow() - timedelta(hours=24)
            ])
        }


# =============================================================================
# TRANSPARENCY DASHBOARD
# =============================================================================

class TransparencyDashboard:
    """Provides transparency into pricing and fees"""

    def __init__(
        self,
        pricing_engine: DynamicPricingEngine,
        comparison_engine: PriceComparisonEngine,
        apy_calculator: APYCalculator,
        anti_gouging: AntiGougingMonitor
    ):
        self.pricing = pricing_engine
        self.comparison = comparison_engine
        self.apy = apy_calculator
        self.anti_gouging = anti_gouging

    async def get_transparency_report(self) -> Dict[str, Any]:
        """Generate a full transparency report"""
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "fee_statistics": self.anti_gouging.get_fee_statistics(),
            "recent_alerts": self.anti_gouging.alerts[-10:],
            "fee_bounds": {
                "min_bps": MIN_FEE_BPS,
                "max_bps": MAX_FEE_BPS,
                "base_bps": BASE_FEE_BPS
            },
            "tier_discounts": {
                "free": "0%",
                "starter": "0.1%",
                "pro": "0.2%",
                "enterprise": "0.35%",
                "whale": "0.5%"
            },
            "dynamic_factors": {
                "volume_weight": VOLUME_WEIGHT,
                "volatility_weight": VOLATILITY_WEIGHT,
                "demand_weight": DEMAND_WEIGHT,
                "competition_weight": COMPETITION_WEIGHT
            }
        }

    async def get_fee_breakdown(
        self,
        fee_type: FeeType,
        amount: int,
        token_mint: str,
        user_tier: str
    ) -> Dict[str, Any]:
        """Get detailed fee breakdown for an operation"""
        fee_result = await self.pricing.calculate_fee(
            fee_type=fee_type,
            amount=amount,
            token_mint=token_mint,
            user_tier=user_tier
        )

        fee_amount = amount * fee_result.final_fee_bps // 10000

        return {
            "input_amount": amount,
            "fee_amount": fee_amount,
            "net_amount": amount - fee_amount,
            "fee_bps": fee_result.final_fee_bps,
            "fee_percent": fee_result.final_fee_bps / 100,
            "breakdown": {
                "base_fee_bps": fee_result.base_fee_bps,
                "volume_adjustment": fee_result.volume_adjustment,
                "volatility_adjustment": fee_result.volatility_adjustment,
                "demand_adjustment": fee_result.demand_adjustment,
                "tier_discount": fee_result.tier_discount_bps
            },
            "reasoning": fee_result.reasoning
        }


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_pricing_endpoints(
    pricing_engine: DynamicPricingEngine,
    comparison_engine: PriceComparisonEngine,
    apy_calculator: APYCalculator,
    transparency: TransparencyDashboard
):
    """Create pricing API endpoints"""
    from fastapi import APIRouter, Query
    from pydantic import BaseModel

    router = APIRouter(prefix="/api/pricing", tags=["Pricing"])

    class FeeRequest(BaseModel):
        fee_type: str
        amount: int
        token_mint: str
        user_tier: str = "free"

    class APYRequest(BaseModel):
        base_rate: float
        stake_duration_days: int
        user_tier: str = "free"
        bonus_multiplier: float = 1.0

    class ProjectionRequest(BaseModel):
        principal: float
        apy: float
        days: int

    @router.post("/fee/calculate")
    async def calculate_fee(request: FeeRequest):
        """Calculate dynamic fee"""
        result = await pricing_engine.calculate_fee(
            fee_type=FeeType(request.fee_type),
            amount=request.amount,
            token_mint=request.token_mint,
            user_tier=request.user_tier
        )
        return {
            "fee_bps": result.final_fee_bps,
            "fee_amount": request.amount * result.final_fee_bps // 10000,
            "reasoning": result.reasoning
        }

    @router.get("/fee/breakdown")
    async def get_fee_breakdown(
        fee_type: str,
        amount: int,
        token_mint: str,
        user_tier: str = "free"
    ):
        """Get detailed fee breakdown"""
        return await transparency.get_fee_breakdown(
            FeeType(fee_type), amount, token_mint, user_tier
        )

    @router.get("/price/{token_mint}")
    async def get_price(token_mint: str):
        """Get best price for a token"""
        price = await comparison_engine.get_best_price(token_mint)
        if not price:
            return {"error": "No price data"}
        return {
            "price_usd": str(price.price_usd),
            "source": price.source.value,
            "confidence": price.confidence,
            "timestamp": price.timestamp.isoformat()
        }

    @router.get("/price/{token_mint}/deviation")
    async def get_price_deviation(token_mint: str):
        """Get price deviation across sources"""
        return await comparison_engine.get_price_deviation(token_mint)

    @router.get("/quotes")
    async def get_quotes(
        input_token: str,
        output_token: str,
        amount: int
    ):
        """Get and compare quotes from multiple DEXs"""
        quotes = await comparison_engine.get_quote_comparison(
            input_token, output_token, amount
        )
        return [
            {
                "source": q.source.value,
                "input_amount": q.input_amount,
                "output_amount": q.output_amount,
                "price_impact_bps": q.price_impact_bps,
                "fee_bps": q.fee_bps
            }
            for q in quotes
        ]

    @router.post("/apy/calculate")
    async def calculate_apy(request: APYRequest):
        """Calculate staking APY"""
        breakdown = apy_calculator.calculate_staking_apy(
            base_rate=request.base_rate,
            stake_duration_days=request.stake_duration_days,
            user_tier=request.user_tier,
            bonus_multiplier=request.bonus_multiplier
        )
        return {
            "total_apy": breakdown.total_apy,
            "base_apy": breakdown.base_apy,
            "time_multiplier": breakdown.time_multiplier,
            "tier_multiplier": breakdown.tier_multiplier,
            "boost_apy": breakdown.boost_apy
        }

    @router.post("/apy/project")
    async def project_earnings(request: ProjectionRequest):
        """Project earnings over time"""
        return apy_calculator.project_earnings(
            principal=Decimal(str(request.principal)),
            apy=request.apy,
            days=request.days
        )

    @router.get("/transparency")
    async def get_transparency_report():
        """Get full transparency report"""
        return await transparency.get_transparency_report()

    @router.get("/il/calculate")
    async def calculate_il(
        initial_ratio: float = Query(..., description="Initial price ratio"),
        current_ratio: float = Query(..., description="Current price ratio")
    ):
        """Calculate impermanent loss"""
        il = apy_calculator.calculate_impermanent_loss(initial_ratio, current_ratio)
        return {
            "impermanent_loss_percent": il,
            "price_change_ratio": current_ratio / initial_ratio
        }

    return router
