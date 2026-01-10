"""
Trade Router for JARVIS.

Routes trades through Bags.fm with Jupiter fallback:
- Primary: Bags.fm (earn partner fees)
- Fallback: Jupiter (reliability)
- Unified interface for trading modules
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

from .client import BagsClient, Quote, SwapResult, get_bags_client

logger = logging.getLogger("jarvis.integrations.bags.trade_router")


# =============================================================================
# Configuration
# =============================================================================


class RouteProvider(Enum):
    """Trade route provider."""
    BAGS = "bags"
    JUPITER = "jupiter"


@dataclass
class TradeRouterConfig:
    """Configuration for trade router."""

    # Provider settings
    primary_provider: RouteProvider = RouteProvider.BAGS
    enable_fallback: bool = True

    # Jupiter settings
    jupiter_url: str = "https://quote-api.jup.ag/v6"

    # Routing settings
    max_slippage_bps: int = 100  # 1%
    default_slippage_bps: int = 50  # 0.5%

    # Timeout settings
    quote_timeout: int = 10
    swap_timeout: int = 30


@dataclass
class TradeResult:
    """Result of a trade execution."""

    success: bool
    provider: RouteProvider
    signature: str
    input_mint: str
    output_mint: str
    input_amount: int
    output_amount: int
    price_impact_pct: float
    fees: Dict[str, int]
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "provider": self.provider.value,
            "signature": self.signature,
            "input_mint": self.input_mint,
            "output_mint": self.output_mint,
            "input_amount": self.input_amount,
            "output_amount": self.output_amount,
            "price_impact_pct": self.price_impact_pct,
            "fees": self.fees,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Trade Router
# =============================================================================


class TradeRouter:
    """
    Routes trades through Bags.fm with Jupiter fallback.

    Features:
    - Automatic provider selection
    - Fallback on failure
    - Unified quote/swap interface
    - Fee tracking
    """

    LAMPORTS_PER_SOL = 1_000_000_000

    def __init__(
        self,
        config: TradeRouterConfig = None,
        bags_client: BagsClient = None,
    ):
        self.config = config or TradeRouterConfig()
        self._bags = bags_client or get_bags_client()
        self._http: Optional[aiohttp.ClientSession] = None

        # Statistics
        self._trade_history: List[TradeResult] = []
        self._bags_trades = 0
        self._jupiter_trades = 0
        self._total_volume = 0

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Start the router."""
        await self._bags.start()
        self._http = aiohttp.ClientSession()

    async def close(self):
        """Close the router."""
        await self._bags.close()
        if self._http:
            await self._http.close()

    # =========================================================================
    # Quote Methods
    # =========================================================================

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = None,
        provider: RouteProvider = None,
    ) -> Dict[str, Any]:
        """
        Get a swap quote.

        Args:
            input_mint: Input token mint
            output_mint: Output token mint
            amount: Amount in smallest units
            slippage_bps: Slippage tolerance
            provider: Specific provider (or auto)

        Returns:
            Quote data with provider info
        """
        if slippage_bps is None:
            slippage_bps = self.config.default_slippage_bps

        if provider is None:
            provider = self.config.primary_provider

        # Try primary provider
        try:
            if provider == RouteProvider.BAGS:
                quote = await self._get_bags_quote(input_mint, output_mint, amount, slippage_bps)
                return {
                    "provider": RouteProvider.BAGS.value,
                    "quote": quote.to_dict(),
                    "raw_quote": quote,
                }
        except Exception as e:
            logger.warning(f"Bags quote failed: {e}")
            if not self.config.enable_fallback:
                raise

        # Fallback to Jupiter
        try:
            quote = await self._get_jupiter_quote(input_mint, output_mint, amount, slippage_bps)
            return {
                "provider": RouteProvider.JUPITER.value,
                "quote": quote,
                "raw_quote": quote,
            }
        except Exception as e:
            logger.error(f"Jupiter quote failed: {e}")
            raise

    async def _get_bags_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int,
    ) -> Quote:
        """Get quote from Bags.fm."""
        return await self._bags.get_quote(input_mint, output_mint, amount, slippage_bps)

    async def _get_jupiter_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int,
    ) -> Dict[str, Any]:
        """Get quote from Jupiter."""
        if self._http is None:
            self._http = aiohttp.ClientSession()

        url = f"{self.config.jupiter_url}/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(slippage_bps),
        }

        async with self._http.get(url, params=params, timeout=self.config.quote_timeout) as resp:
            if resp.status != 200:
                raise Exception(f"Jupiter API error: {resp.status}")
            return await resp.json()

    # =========================================================================
    # Swap Methods
    # =========================================================================

    async def execute_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        user_public_key: str,
        signed_transaction: str = None,
        slippage_bps: int = None,
    ) -> TradeResult:
        """
        Execute a swap.

        Args:
            input_mint: Input token mint
            output_mint: Output token mint
            amount: Amount in smallest units
            user_public_key: User's wallet
            signed_transaction: Pre-signed transaction (optional)
            slippage_bps: Slippage tolerance

        Returns:
            TradeResult with execution details
        """
        if slippage_bps is None:
            slippage_bps = self.config.default_slippage_bps

        # Try Bags first
        try:
            result = await self._execute_bags_swap(
                input_mint, output_mint, amount, user_public_key,
                signed_transaction, slippage_bps
            )
            if result.success:
                self._record_trade(result)
                return result
        except Exception as e:
            logger.warning(f"Bags swap failed: {e}")
            if not self.config.enable_fallback:
                return TradeResult(
                    success=False,
                    provider=RouteProvider.BAGS,
                    signature="",
                    input_mint=input_mint,
                    output_mint=output_mint,
                    input_amount=amount,
                    output_amount=0,
                    price_impact_pct=0,
                    fees={},
                    error=str(e),
                )

        # Fallback to Jupiter
        try:
            result = await self._execute_jupiter_swap(
                input_mint, output_mint, amount, user_public_key,
                signed_transaction, slippage_bps
            )
            self._record_trade(result)
            return result
        except Exception as e:
            logger.error(f"Jupiter swap failed: {e}")
            return TradeResult(
                success=False,
                provider=RouteProvider.JUPITER,
                signature="",
                input_mint=input_mint,
                output_mint=output_mint,
                input_amount=amount,
                output_amount=0,
                price_impact_pct=0,
                fees={},
                error=str(e),
            )

    async def _execute_bags_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        user_public_key: str,
        signed_transaction: str,
        slippage_bps: int,
    ) -> TradeResult:
        """Execute swap through Bags.fm."""
        # Get quote
        quote = await self._bags.get_quote(input_mint, output_mint, amount, slippage_bps)

        # Execute swap
        swap_result = await self._bags.execute_swap(quote, user_public_key, signed_transaction)

        return TradeResult(
            success=swap_result.success,
            provider=RouteProvider.BAGS,
            signature=swap_result.signature,
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=amount,
            output_amount=swap_result.output_amount,
            price_impact_pct=quote.price_impact_pct,
            fees={
                "platform_fee": swap_result.platform_fee,
                "partner_fee": swap_result.partner_fee,
            },
            error=swap_result.error,
        )

    async def _execute_jupiter_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        user_public_key: str,
        signed_transaction: str,
        slippage_bps: int,
    ) -> TradeResult:
        """Execute swap through Jupiter."""
        if self._http is None:
            self._http = aiohttp.ClientSession()

        # Get quote
        quote = await self._get_jupiter_quote(input_mint, output_mint, amount, slippage_bps)

        # Get swap transaction
        swap_url = f"{self.config.jupiter_url}/swap"
        swap_body = {
            "quoteResponse": quote,
            "userPublicKey": user_public_key,
        }

        async with self._http.post(swap_url, json=swap_body, timeout=self.config.swap_timeout) as resp:
            if resp.status != 200:
                raise Exception(f"Jupiter swap API error: {resp.status}")
            swap_data = await resp.json()

        # Note: In production, this would need to be signed and sent to Solana
        # For now, we return the transaction data
        return TradeResult(
            success=True,
            provider=RouteProvider.JUPITER,
            signature=swap_data.get("signature", "pending"),
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=amount,
            output_amount=int(quote.get("outAmount", 0)),
            price_impact_pct=float(quote.get("priceImpactPct", 0)),
            fees={
                "platform_fee": int(quote.get("platformFee", {}).get("amount", 0)),
            },
        )

    def _record_trade(self, result: TradeResult):
        """Record trade for statistics."""
        self._trade_history.append(result)
        self._total_volume += result.input_amount

        if result.provider == RouteProvider.BAGS:
            self._bags_trades += 1
        else:
            self._jupiter_trades += 1

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        total_trades = self._bags_trades + self._jupiter_trades

        return {
            "total_trades": total_trades,
            "bags_trades": self._bags_trades,
            "jupiter_trades": self._jupiter_trades,
            "bags_ratio": self._bags_trades / max(1, total_trades),
            "total_volume_lamports": self._total_volume,
            "total_volume_sol": self._total_volume / self.LAMPORTS_PER_SOL,
        }

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get recent trade history."""
        return [t.to_dict() for t in self._trade_history[-limit:]]


# =============================================================================
# Singleton
# =============================================================================

_router: Optional[TradeRouter] = None


def get_trade_router() -> TradeRouter:
    """Get singleton trade router."""
    global _router
    if _router is None:
        _router = TradeRouter()
    return _router


# =============================================================================
# Drop-in Replacement Interface
# =============================================================================


async def execute_trade(
    input_mint: str,
    output_mint: str,
    amount: int,
    wallet: str,
    slippage: float = 0.005,
) -> Dict[str, Any]:
    """
    Drop-in replacement for existing trade execution.

    This function maintains the same interface as the existing
    jito_executor but routes through Bags.fm.

    Args:
        input_mint: Input token mint address
        output_mint: Output token mint address
        amount: Amount in smallest units
        wallet: User wallet address
        slippage: Slippage tolerance (decimal, e.g., 0.005 = 0.5%)

    Returns:
        Trade result dictionary
    """
    router = get_trade_router()
    slippage_bps = int(slippage * 10000)

    result = await router.execute_swap(
        input_mint=input_mint,
        output_mint=output_mint,
        amount=amount,
        user_public_key=wallet,
        slippage_bps=slippage_bps,
    )

    return {
        "success": result.success,
        "signature": result.signature,
        "amount_in": result.input_amount,
        "amount_out": result.output_amount,
        "price_impact": result.price_impact_pct,
        "provider": result.provider.value,
        "error": result.error,
    }
