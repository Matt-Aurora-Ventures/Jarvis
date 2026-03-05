"""
Multi-Venue Trade Routing
Prompt #37: Smart routing between Bags.fm and Jupiter for best execution
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import aiohttp
from aiohttp import ClientTimeout

from core.data.asset_registry import AssetClass
from core.events.market_events import EventUrgency, MarketEvent, MarketEventType
from core.events.trading_pipeline import PipelineAction, TradingPipeline

logger = logging.getLogger(__name__)
SOL_MINT = "So11111111111111111111111111111111111111112"
DEFAULT_SOL_PRICE_USD = 150.0
DEFAULT_POOL_LIQUIDITY_USD = {
    AssetClass.NATIVE_SOLANA: 5_000_000.0,
    AssetClass.BAGS_BONDING_CURVE: 30_000.0,
    AssetClass.BAGS_GRADUATED: 100_000.0,
    AssetClass.MEMECOIN: 100_000.0,
}


# =============================================================================
# VENUE DEFINITIONS
# =============================================================================

class Venue(str, Enum):
    """Trading venues"""
    BAGS = "bags"
    JUPITER = "jupiter"
    RAYDIUM = "raydium"
    ORCA = "orca"


@dataclass
class Quote:
    """Quote from a venue"""
    venue: Venue
    input_mint: str
    output_mint: str
    input_amount: int
    output_amount: int
    price_impact: float
    fees: int
    partner_fee_earned: int  # Fee we earn as partner
    route: List[str]
    expires_at: int
    quote_data: Dict[str, Any]  # Raw quote for execution


@dataclass
class RoutingDecision:
    """Decision on where to route trade"""
    selected_venue: Venue
    quotes: Dict[Venue, Quote]
    reason: str
    effective_price: Decimal
    partner_fee_opportunity: int
    savings_vs_worst: int


# =============================================================================
# MULTI-VENUE ROUTER
# =============================================================================

class MultiVenueRouter:
    """Smart router comparing Bags vs Jupiter for best execution"""

    # Partner fee share (25% of Bags platform fee)
    BAGS_PARTNER_FEE_SHARE = 0.25
    # Bags platform fee rate
    BAGS_PLATFORM_FEE_BPS = 100  # 1%

    def __init__(
        self,
        bags_api_key: str,
        jupiter_api_key: Optional[str] = None,
        prefer_bags_threshold_bps: int = 50,  # Prefer Bags if within 0.5%
        redis_url: str = "redis://localhost:6379"
    ):
        self.bags_api_key = bags_api_key
        self.jupiter_api_key = jupiter_api_key
        self.prefer_bags_threshold_bps = prefer_bags_threshold_bps
        self.redis_url = redis_url
        self._session: Optional[aiohttp.ClientSession] = None
        self.execution_pipeline = TradingPipeline()

        # Analytics tracking
        self.routing_stats = {
            "bags_wins": 0,
            "jupiter_wins": 0,
            "bags_by_preference": 0,
            "total_partner_fees_earned": 0,
        }

    async def connect(self):
        """Initialize connections"""
        # Configure timeouts: 60s total, 30s connect (for venue API calls)
        timeout = ClientTimeout(total=60, connect=30)
        self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self):
        """Close connections"""
        if self._session:
            await self._session.close()

    # =========================================================================
    # QUOTE FETCHING
    # =========================================================================

    async def get_bags_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 100
    ) -> Optional[Quote]:
        """Get quote from Bags.fm"""
        try:
            async with self._session.post(
                "https://public-api-v2.bags.fm/api/v1/trade/quote",
                headers={"x-api-key": self.bags_api_key},
                json={
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": amount,
                    "slippageMode": "auto",
                    "slippageBps": slippage_bps
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.warning(f"Bags quote failed: {response.status}")
                    return None

                data = await response.json()

                # Calculate partner fee earned
                platform_fee = int(amount * self.BAGS_PLATFORM_FEE_BPS / 10000)
                partner_fee = int(platform_fee * self.BAGS_PARTNER_FEE_SHARE)

                return Quote(
                    venue=Venue.BAGS,
                    input_mint=input_mint,
                    output_mint=output_mint,
                    input_amount=amount,
                    output_amount=data.get("outAmount", 0),
                    price_impact=data.get("priceImpact", 0),
                    fees=data.get("fees", 0),
                    partner_fee_earned=partner_fee,
                    route=data.get("route", []),
                    expires_at=data.get("expiresAt", 0),
                    quote_data=data
                )

        except Exception as e:
            logger.error(f"Bags quote error: {e}")
            return None

    async def get_jupiter_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 100
    ) -> Optional[Quote]:
        """Get quote from Jupiter"""
        try:
            async with self._session.get(
                "https://quote-api.jup.ag/v6/quote",
                params={
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": amount,
                    "slippageBps": slippage_bps,
                    "onlyDirectRoutes": False
                },
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    logger.warning(f"Jupiter quote failed: {response.status}")
                    return None

                data = await response.json()

                return Quote(
                    venue=Venue.JUPITER,
                    input_mint=input_mint,
                    output_mint=output_mint,
                    input_amount=amount,
                    output_amount=int(data.get("outAmount", 0)),
                    price_impact=float(data.get("priceImpactPct", 0)),
                    fees=sum(
                        fee.get("amount", 0)
                        for fee in data.get("routePlan", [{}])[0].get("swapInfo", {}).get("feeAmount", [])
                    ),
                    partner_fee_earned=0,  # No partner fees on Jupiter
                    route=[step.get("swapInfo", {}).get("label", "")
                           for step in data.get("routePlan", [])],
                    expires_at=0,
                    quote_data=data
                )

        except Exception as e:
            logger.error(f"Jupiter quote error: {e}")
            return None

    async def get_all_quotes(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 100
    ) -> Dict[Venue, Quote]:
        """Get quotes from all venues concurrently"""
        tasks = [
            self.get_bags_quote(input_mint, output_mint, amount, slippage_bps),
            self.get_jupiter_quote(input_mint, output_mint, amount, slippage_bps),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        quotes = {}
        for result in results:
            if isinstance(result, Quote):
                quotes[result.venue] = result

        return quotes

    # =========================================================================
    # ROUTING DECISION
    # =========================================================================

    def calculate_effective_price(
        self,
        quote: Quote,
        include_partner_fee: bool = True
    ) -> Decimal:
        """
        Calculate effective price including all costs.
        If include_partner_fee is True, we subtract the fee we earn
        (effectively making Bags cheaper for us)
        """
        if quote.output_amount == 0:
            return Decimal("inf")

        # Base price
        price = Decimal(quote.input_amount) / Decimal(quote.output_amount)

        # Subtract partner fee benefit (makes Bags more attractive)
        if include_partner_fee and quote.partner_fee_earned > 0:
            fee_benefit = Decimal(quote.partner_fee_earned) / Decimal(quote.output_amount)
            price -= fee_benefit

        return price

    def decide_venue(
        self,
        quotes: Dict[Venue, Quote]
    ) -> RoutingDecision:
        """Decide which venue to use"""
        if not quotes:
            raise ValueError("No quotes available")

        # Calculate effective prices
        prices = {
            venue: self.calculate_effective_price(quote, include_partner_fee=True)
            for venue, quote in quotes.items()
        }

        # Find best venue by effective price
        best_venue = min(prices.keys(), key=lambda v: prices[v])
        worst_venue = max(prices.keys(), key=lambda v: prices[v])

        # Check if Bags is close enough to prefer (for partner fees)
        bags_quote = quotes.get(Venue.BAGS)
        jupiter_quote = quotes.get(Venue.JUPITER)

        reason = f"Best effective price: {best_venue.value}"

        if bags_quote and jupiter_quote:
            # Calculate price difference in bps
            bags_price_raw = self.calculate_effective_price(bags_quote, False)
            jupiter_price_raw = self.calculate_effective_price(jupiter_quote, False)

            if jupiter_price_raw > 0:
                diff_bps = int(
                    abs(bags_price_raw - jupiter_price_raw)
                    / jupiter_price_raw * 10000
                )

                # If Bags is within threshold, prefer it for partner fees
                if (best_venue == Venue.JUPITER and
                    diff_bps <= self.prefer_bags_threshold_bps):
                    best_venue = Venue.BAGS
                    reason = f"Bags preferred (within {diff_bps}bps, earning partner fees)"
                    self.routing_stats["bags_by_preference"] += 1

        # Update stats
        if best_venue == Venue.BAGS:
            self.routing_stats["bags_wins"] += 1
            self.routing_stats["total_partner_fees_earned"] += quotes[Venue.BAGS].partner_fee_earned
        else:
            self.routing_stats["jupiter_wins"] += 1

        # Calculate savings
        best_quote = quotes[best_venue]
        worst_quote = quotes.get(worst_venue)
        savings = 0
        if worst_quote and best_quote:
            savings = worst_quote.output_amount - best_quote.output_amount

        return RoutingDecision(
            selected_venue=best_venue,
            quotes=quotes,
            reason=reason,
            effective_price=prices[best_venue],
            partner_fee_opportunity=bags_quote.partner_fee_earned if bags_quote else 0,
            savings_vs_worst=abs(savings)
        )

    # =========================================================================
    # TRADE EXECUTION
    # =========================================================================

    async def route_and_execute(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        wallet_keypair: Any,  # Keypair for signing
        slippage_bps: int = 100
    ) -> Dict[str, Any]:
        """Get quotes, decide venue, and execute trade"""
        # Get all quotes
        quotes = await self.get_all_quotes(
            input_mint, output_mint, amount, slippage_bps
        )

        if not quotes:
            raise ValueError("No quotes available from any venue")

        # Decide venue
        decision = self.decide_venue(quotes)
        selected_quote = quotes[decision.selected_venue]

        logger.info(
            f"Routing {amount} {input_mint} -> {output_mint} via {decision.selected_venue.value}: "
            f"{decision.reason}"
        )

        gate_result = self._evaluate_execution_gate(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            selected_quote=selected_quote,
            selected_venue=decision.selected_venue,
        )
        if gate_result.action != PipelineAction.ENTER:
            reason = gate_result.rejection_reason.value if gate_result.rejection_reason else "unknown"
            detail = gate_result.rejection_detail or "trade rejected"
            raise ValueError(f"Execution gate rejected ({reason}): {detail}")

        # Execute on selected venue
        if decision.selected_venue == Venue.BAGS:
            result = await self._execute_bags_swap(selected_quote, wallet_keypair)
        else:
            result = await self._execute_jupiter_swap(selected_quote, wallet_keypair)

        return {
            "venue": decision.selected_venue.value,
            "quote": selected_quote.__dict__,
            "decision": decision.__dict__,
            "execution": result
        }

    async def _execute_bags_swap(
        self,
        quote: Quote,
        wallet_keypair: Any
    ) -> Dict[str, Any]:
        """Execute swap on Bags.fm"""
        async with self._session.post(
            "https://public-api-v2.bags.fm/api/v1/trade/swap",
            headers={"x-api-key": self.bags_api_key},
            json={
                "quote": quote.quote_data,
                "userPublicKey": str(wallet_keypair.pubkey()),
            }
        ) as response:
            data = await response.json()

            if response.status != 200:
                raise ValueError(f"Bags swap failed: {data}")

            # Sign and send transaction
            # ... (actual signing logic)

            return data

    async def _execute_jupiter_swap(
        self,
        quote: Quote,
        wallet_keypair: Any
    ) -> Dict[str, Any]:
        """Execute swap on Jupiter"""
        async with self._session.post(
            "https://quote-api.jup.ag/v6/swap",
            json={
                "quoteResponse": quote.quote_data,
                "userPublicKey": str(wallet_keypair.pubkey()),
                "wrapAndUnwrapSol": True
            }
        ) as response:
            data = await response.json()

            if response.status != 200:
                raise ValueError(f"Jupiter swap failed: {data}")

            # Sign and send transaction
            # ... (actual signing logic)

            return data

    def _evaluate_execution_gate(
        self,
        *,
        input_mint: str,
        output_mint: str,
        amount: int,
        selected_quote: Quote,
        selected_venue: Venue,
    ):
        """Evaluate a routed quote against the event-driven execution gate."""
        event, trade_size_usd = self._build_market_event(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            selected_quote=selected_quote,
            selected_venue=selected_venue,
        )
        return self.execution_pipeline.evaluate(
            event,
            trade_size_usd=trade_size_usd,
            entry_price=event.current_price,
            pool_liquidity_usd=event.pool_liquidity_usd,
        )

    def _build_market_event(
        self,
        *,
        input_mint: str,
        output_mint: str,
        amount: int,
        selected_quote: Quote,
        selected_venue: Venue,
    ) -> Tuple[MarketEvent, float]:
        """Construct a conservative market event from the routed quote."""
        asset_class = self._infer_asset_class(
            input_mint=input_mint,
            output_mint=output_mint,
            selected_venue=selected_venue,
        )
        trade_size_usd = self._estimate_trade_size_usd(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            selected_quote=selected_quote,
        )
        pool_liquidity_usd = self._estimate_pool_liquidity_usd(
            asset_class=asset_class,
            trade_size_usd=trade_size_usd,
            price_impact_pct=float(selected_quote.price_impact or 0.0),
        )

        event_type = MarketEventType.PRICE_BREAKOUT
        urgency = EventUrgency.FAST
        if asset_class == AssetClass.BAGS_BONDING_CURVE:
            event_type = MarketEventType.TOKEN_LAUNCH
            urgency = EventUrgency.IMMEDIATE
        elif asset_class == AssetClass.BAGS_GRADUATED:
            event_type = MarketEventType.GRADUATION
            urgency = EventUrgency.IMMEDIATE

        trade_mint = output_mint if input_mint == SOL_MINT else input_mint
        symbol = trade_mint[:8].upper()
        return (
            MarketEvent(
                event_type=event_type,
                urgency=urgency,
                timestamp=datetime.now(timezone.utc),
                mint_address=trade_mint,
                symbol=symbol,
                asset_class=asset_class,
                current_price=0.0,
                pool_liquidity_usd=pool_liquidity_usd,
            ),
            trade_size_usd,
        )

    def _infer_asset_class(
        self,
        *,
        input_mint: str,
        output_mint: str,
        selected_venue: Venue,
    ) -> AssetClass:
        """Infer asset class from route direction and venue."""
        if input_mint == SOL_MINT and output_mint == SOL_MINT:
            return AssetClass.NATIVE_SOLANA

        if selected_venue == Venue.BAGS and input_mint == SOL_MINT:
            return AssetClass.BAGS_BONDING_CURVE

        if selected_venue == Venue.BAGS and output_mint == SOL_MINT:
            return AssetClass.BAGS_GRADUATED

        if input_mint == SOL_MINT or output_mint == SOL_MINT:
            return AssetClass.MEMECOIN

        return AssetClass.MEMECOIN

    def _estimate_trade_size_usd(
        self,
        *,
        input_mint: str,
        output_mint: str,
        amount: int,
        selected_quote: Quote,
    ) -> float:
        """Estimate USD notional conservatively from the SOL side of the route."""
        if input_mint == SOL_MINT:
            return max((amount / 1_000_000_000) * DEFAULT_SOL_PRICE_USD, 0.0)

        if output_mint == SOL_MINT:
            return max((selected_quote.output_amount / 1_000_000_000) * DEFAULT_SOL_PRICE_USD, 0.0)

        return 500.0

    def _estimate_pool_liquidity_usd(
        self,
        *,
        asset_class: AssetClass,
        trade_size_usd: float,
        price_impact_pct: float,
    ) -> float:
        """Estimate pool depth from price impact, with conservative fallbacks."""
        if price_impact_pct > 0 and trade_size_usd > 0:
            estimated = trade_size_usd / (2 * price_impact_pct)
            if estimated > 0:
                return estimated

        return DEFAULT_POOL_LIQUIDITY_USD.get(asset_class, 50_000.0)

    # =========================================================================
    # ANALYTICS
    # =========================================================================

    def get_routing_analytics(self) -> Dict[str, Any]:
        """Get routing analytics"""
        total = self.routing_stats["bags_wins"] + self.routing_stats["jupiter_wins"]

        return {
            "total_trades": total,
            "bags_wins": self.routing_stats["bags_wins"],
            "bags_win_rate": (
                self.routing_stats["bags_wins"] / total * 100 if total > 0 else 0
            ),
            "jupiter_wins": self.routing_stats["jupiter_wins"],
            "jupiter_win_rate": (
                self.routing_stats["jupiter_wins"] / total * 100 if total > 0 else 0
            ),
            "bags_by_preference": self.routing_stats["bags_by_preference"],
            "total_partner_fees_earned": self.routing_stats["total_partner_fees_earned"],
            "avg_partner_fee_per_bags_trade": (
                self.routing_stats["total_partner_fees_earned"] /
                self.routing_stats["bags_wins"]
                if self.routing_stats["bags_wins"] > 0 else 0
            )
        }


# =============================================================================
# API ENDPOINTS
# =============================================================================

def create_router_endpoints(router: MultiVenueRouter):
    """Create API endpoints for routing"""
    from fastapi import APIRouter
    api = APIRouter(prefix="/api/routing", tags=["Trade Routing"])

    @api.post("/quote")
    async def get_best_quote(
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 100
    ):
        """Get quotes from all venues and recommend best route"""
        quotes = await router.get_all_quotes(
            input_mint, output_mint, amount, slippage_bps
        )

        if not quotes:
            return {"error": "No quotes available"}

        decision = router.decide_venue(quotes)

        return {
            "recommended_venue": decision.selected_venue.value,
            "reason": decision.reason,
            "effective_price": str(decision.effective_price),
            "partner_fee_opportunity": decision.partner_fee_opportunity,
            "savings_vs_worst": decision.savings_vs_worst,
            "quotes": {
                venue.value: {
                    "output_amount": quote.output_amount,
                    "price_impact": quote.price_impact,
                    "fees": quote.fees,
                    "partner_fee_earned": quote.partner_fee_earned,
                    "route": quote.route
                }
                for venue, quote in decision.quotes.items()
            }
        }

    @api.get("/analytics")
    async def get_analytics():
        """Get routing analytics"""
        return router.get_routing_analytics()

    return api
