"""
Bags.fm Trade Adapter for Jarvis.

Drop-in replacement for existing trading modules that routes trades through Bags.fm.
Maintains same interface as core/jito_executor.py while earning partner fees.

Features:
- Same execute_swap interface as existing executor
- Automatic quote -> swap flow
- Partner fee tracking
- Jupiter fallback on failure
- Trade attribution logging
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from core.feature_manager import is_enabled_default
from core.security.emergency_shutdown import is_emergency_shutdown
from core.secrets import get_key

logger = logging.getLogger("jarvis.trading.bags_adapter")

_KILL_SWITCH_VALUES = ("1", "true", "yes", "on")


def _kill_switch_active() -> bool:
    """Check if the global kill switch is active via environment flags."""
    return (
        os.getenv("LIFEOS_KILL_SWITCH", "").lower() in _KILL_SWITCH_VALUES
        or os.getenv("KILL_SWITCH", "").lower() in _KILL_SWITCH_VALUES
    )


# =============================================================================
# Types
# =============================================================================


class TradeSource(Enum):
    """Trade execution source."""
    BAGS = "bags"
    JUPITER = "jupiter"
    RAYDIUM = "raydium"


@dataclass
class SwapResult:
    """Result of a swap execution."""
    signature: str
    input_mint: str
    output_mint: str
    input_amount: int
    output_amount: int
    source: TradeSource
    partner_fee_earned: float = 0.0
    price_impact: float = 0.0
    slippage_bps: int = 0
    execution_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signature": self.signature,
            "input_mint": self.input_mint,
            "output_mint": self.output_mint,
            "input_amount": self.input_amount,
            "output_amount": self.output_amount,
            "source": self.source.value,
            "partner_fee_earned": self.partner_fee_earned,
            "price_impact": self.price_impact,
            "slippage_bps": self.slippage_bps,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class QuoteResult:
    """Result of a quote request."""
    input_mint: str
    output_mint: str
    input_amount: int
    output_amount: int
    price_impact: float
    minimum_received: int
    route_plan: List[Dict]
    source: TradeSource


# =============================================================================
# Bags Client Wrapper
# =============================================================================


class BagsTradeClient:
    """
    Client for Bags.fm trading API.

    Handles:
    - Quote fetching
    - Swap execution
    - Partner fee tracking
    """

    LAMPORTS_PER_SOL = 1_000_000_000
    PARTNER_FEE_RATE = 0.0025  # 0.25% of volume (25% of 1% platform fee)

    def __init__(
        self,
        partner_code: str = None,
        api_url: str = None,
        referral_wallet: str = None,
    ):
        self.partner_code = partner_code or os.getenv("BAGS_PARTNER_CODE", "")
        if not self.partner_code:
            self.partner_code = (
                get_key("bags_partner_key", "BAGS_PARTNER_KEY")
                or get_key("bags_partner", "BAGS_PARTNER_KEY")
                or ""
            )
        self.api_url = api_url or os.getenv("BAGS_API_URL", "https://api.bags.fm")
        self.referral_wallet = referral_wallet or os.getenv("BAGS_REFERRAL_WALLET", "")

        self._session = None
        self._stats = {
            "total_volume_sol": 0.0,
            "total_fees_earned": 0.0,
            "trade_count": 0,
        }

    async def _get_session(self):
        """Get or create HTTP session."""
        if self._session is None:
            try:
                import aiohttp
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30)
                )
            except ImportError:
                raise RuntimeError("aiohttp required: pip install aiohttp")
        return self._session

    async def close(self):
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> QuoteResult:
        """
        Get swap quote from Bags.fm.

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest units (lamports)
            slippage_bps: Slippage tolerance in basis points

        Returns:
            QuoteResult with route and amounts
        """
        session = await self._get_session()

        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps,
            "partnerCode": self.partner_code,
        }

        try:
            async with session.get(
                f"{self.api_url}/v1/quote",
                params=params,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Quote failed: {resp.status} - {text}")

                data = await resp.json()

                return QuoteResult(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    input_amount=amount,
                    output_amount=int(data.get("outAmount", 0)),
                    price_impact=float(data.get("priceImpactPct", 0)),
                    minimum_received=int(data.get("otherAmountThreshold", 0)),
                    route_plan=data.get("routePlan", []),
                    source=TradeSource.BAGS,
                )

        except Exception as e:
            logger.error(f"Bags quote failed: {e}")
            raise

    async def execute_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
        wallet_keypair=None,
    ) -> SwapResult:
        """
        Execute a swap through Bags.fm.

        Args:
            input_mint: Input token mint
            output_mint: Output token mint
            amount: Amount in smallest units
            slippage_bps: Slippage tolerance
            wallet_keypair: Wallet keypair for signing

        Returns:
            SwapResult with transaction details
        """
        start_time = time.time()

        # Get quote
        quote = await self.get_quote(input_mint, output_mint, amount, slippage_bps)

        session = await self._get_session()

        # Build swap transaction
        swap_request = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps,
            "partnerCode": self.partner_code,
            "referralWallet": self.referral_wallet,
        }

        if wallet_keypair:
            swap_request["userPublicKey"] = str(wallet_keypair.pubkey())

        try:
            async with session.post(
                f"{self.api_url}/v1/swap",
                json=swap_request,
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Swap failed: {resp.status} - {text}")

                data = await resp.json()

                # Sign and send transaction
                signature = await self._sign_and_send(
                    data.get("swapTransaction"),
                    wallet_keypair,
                )

                execution_time = (time.time() - start_time) * 1000

                # Calculate partner fee earned
                volume_sol = amount / self.LAMPORTS_PER_SOL
                fee_earned = volume_sol * self.PARTNER_FEE_RATE

                # Update stats
                self._stats["total_volume_sol"] += volume_sol
                self._stats["total_fees_earned"] += fee_earned
                self._stats["trade_count"] += 1

                return SwapResult(
                    signature=signature,
                    input_mint=input_mint,
                    output_mint=output_mint,
                    input_amount=amount,
                    output_amount=quote.output_amount,
                    source=TradeSource.BAGS,
                    partner_fee_earned=fee_earned,
                    price_impact=quote.price_impact,
                    slippage_bps=slippage_bps,
                    execution_time_ms=execution_time,
                )

        except Exception as e:
            logger.error(f"Bags swap failed: {e}")
            raise

    async def _sign_and_send(
        self,
        transaction_base64: str,
        wallet_keypair,
    ) -> str:
        """Sign and send transaction to Solana."""
        # In production, use solana-py to sign and send
        # from solana.transaction import Transaction
        # import base64
        #
        # tx_bytes = base64.b64decode(transaction_base64)
        # tx = Transaction.deserialize(tx_bytes)
        # tx.sign(wallet_keypair)
        #
        # client = AsyncClient(SOLANA_RPC_URL)
        # result = await client.send_transaction(tx)
        # return str(result.value)

        # Mock for development
        import hashlib
        mock_sig = hashlib.sha256(
            f"{transaction_base64}{time.time()}".encode()
        ).hexdigest()[:88]

        logger.info(f"[MOCK] Transaction signed and sent: {mock_sig[:16]}...")
        return mock_sig

    def get_stats(self) -> Dict[str, Any]:
        """Get trading statistics."""
        return {
            **self._stats,
            "avg_fee_per_trade": (
                self._stats["total_fees_earned"] / max(1, self._stats["trade_count"])
            ),
        }


# =============================================================================
# Jupiter Fallback Client
# =============================================================================


class JupiterFallbackClient:
    """
    Jupiter DEX aggregator fallback.

    Used when Bags.fm is unavailable.
    """

    def __init__(self, api_url: str = None):
        self.api_url = api_url or os.getenv(
            "JUPITER_API_URL", "https://quote-api.jup.ag/v6"
        )
        self._session = None

    async def _get_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> QuoteResult:
        """Get quote from Jupiter."""
        session = await self._get_session()

        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": slippage_bps,
        }

        async with session.get(f"{self.api_url}/quote", params=params) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Jupiter quote failed: {resp.status}")

            data = await resp.json()

            return QuoteResult(
                input_mint=input_mint,
                output_mint=output_mint,
                input_amount=amount,
                output_amount=int(data.get("outAmount", 0)),
                price_impact=float(data.get("priceImpactPct", 0)),
                minimum_received=int(data.get("otherAmountThreshold", 0)),
                route_plan=data.get("routePlan", []),
                source=TradeSource.JUPITER,
            )

    async def execute_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
        wallet_keypair=None,
    ) -> SwapResult:
        """Execute swap through Jupiter."""
        start_time = time.time()

        quote = await self.get_quote(input_mint, output_mint, amount, slippage_bps)

        # Build and execute swap (simplified)
        # In production, would call /swap endpoint and sign transaction

        execution_time = (time.time() - start_time) * 1000

        import hashlib
        mock_sig = hashlib.sha256(
            f"jupiter_{input_mint}_{amount}_{time.time()}".encode()
        ).hexdigest()[:88]

        return SwapResult(
            signature=mock_sig,
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=amount,
            output_amount=quote.output_amount,
            source=TradeSource.JUPITER,
            partner_fee_earned=0,  # No partner fees through Jupiter
            price_impact=quote.price_impact,
            slippage_bps=slippage_bps,
            execution_time_ms=execution_time,
        )


# =============================================================================
# Trade Adapter (Drop-in Replacement)
# =============================================================================


class BagsTradeAdapter:
    """
    Drop-in replacement for existing Jarvis trading.

    Same interface as core/jito_executor.py but routes through Bags.fm.

    Features:
    - execute_swap(input_mint, output_mint, amount, slippage) -> signature, amount_out
    - Automatic Bags -> Jupiter fallback
    - Partner fee tracking
    - Trade logging with source attribution
    """

    def __init__(
        self,
        partner_code: str = None,
        enable_fallback: bool = True,
        wallet_keypair=None,
    ):
        self.bags = BagsTradeClient(partner_code=partner_code)
        self.jupiter = JupiterFallbackClient() if enable_fallback else None
        self.wallet = wallet_keypair
        self.enable_fallback = enable_fallback

        self._trade_history: List[SwapResult] = []

    async def execute_swap(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage: float = 0.5,  # Percentage, e.g., 0.5 = 0.5%
    ) -> Tuple[str, int]:
        """
        Execute a token swap.

        Compatible with existing Jarvis trading interface.

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest units (lamports)
            slippage: Slippage tolerance as percentage

        Returns:
            Tuple of (signature, amount_out)
        """
        if _kill_switch_active():
            logger.warning("Swap blocked: kill switch active")
            raise RuntimeError("Kill switch active")

        if is_emergency_shutdown():
            logger.error("Swap blocked: emergency shutdown active")
            raise RuntimeError("Emergency shutdown active")

        if not is_enabled_default("LIVE_TRADING_ENABLED", default=True):
            logger.warning("Swap blocked: LIVE_TRADING_ENABLED=false")
            raise RuntimeError("Live trading disabled by feature flag")

        slippage_bps = int(slippage * 100)  # Convert % to bps

        try:
            # Try Bags.fm first
            result = await self.bags.execute_swap(
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                slippage_bps=slippage_bps,
                wallet_keypair=self.wallet,
            )

            self._log_trade(result)

            logger.info(
                f"Swap executed via Bags: {result.signature[:16]}... "
                f"(fee earned: {result.partner_fee_earned:.6f} SOL)"
            )

            return result.signature, result.output_amount

        except Exception as bags_error:
            logger.warning(f"Bags swap failed: {bags_error}")

            if not self.enable_fallback or not self.jupiter:
                raise

            # Fallback to Jupiter
            logger.info("Falling back to Jupiter...")

            try:
                result = await self.jupiter.execute_swap(
                    input_mint=input_mint,
                    output_mint=output_mint,
                    amount=amount,
                    slippage_bps=slippage_bps,
                    wallet_keypair=self.wallet,
                )

                self._log_trade(result)

                logger.info(
                    f"Swap executed via Jupiter fallback: {result.signature[:16]}..."
                )

                return result.signature, result.output_amount

            except Exception as jupiter_error:
                logger.error(f"Jupiter fallback also failed: {jupiter_error}")
                raise RuntimeError(
                    f"All swap attempts failed. Bags: {bags_error}, Jupiter: {jupiter_error}"
                )

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage: float = 0.5,
    ) -> Dict[str, Any]:
        """Get swap quote."""
        slippage_bps = int(slippage * 100)

        try:
            quote = await self.bags.get_quote(
                input_mint, output_mint, amount, slippage_bps
            )
        except Exception:
            if self.jupiter:
                quote = await self.jupiter.get_quote(
                    input_mint, output_mint, amount, slippage_bps
                )
            else:
                raise

        return {
            "input_amount": quote.input_amount,
            "output_amount": quote.output_amount,
            "price_impact": quote.price_impact,
            "minimum_received": quote.minimum_received,
            "source": quote.source.value,
        }

    def _log_trade(self, result: SwapResult):
        """Log trade for history and analytics."""
        self._trade_history.append(result)

        # Keep last 1000 trades in memory
        if len(self._trade_history) > 1000:
            self._trade_history = self._trade_history[-1000:]

    def get_trade_history(self, limit: int = 50) -> List[Dict]:
        """Get recent trade history."""
        return [t.to_dict() for t in self._trade_history[-limit:]]

    def get_stats(self) -> Dict[str, Any]:
        """Get trading statistics."""
        bags_stats = self.bags.get_stats()

        total_trades = len(self._trade_history)
        bags_trades = sum(1 for t in self._trade_history if t.source == TradeSource.BAGS)
        jupiter_trades = sum(1 for t in self._trade_history if t.source == TradeSource.JUPITER)

        return {
            **bags_stats,
            "total_trades": total_trades,
            "bags_trades": bags_trades,
            "jupiter_trades": jupiter_trades,
            "bags_success_rate": bags_trades / max(1, total_trades),
            "total_volume_sol": bags_stats["total_volume_sol"],
            "total_fees_earned": bags_stats["total_fees_earned"],
        }

    async def close(self):
        """Clean up resources."""
        await self.bags.close()
        if self.jupiter:
            await self.jupiter.close()


# =============================================================================
# Factory Function
# =============================================================================


_adapter: Optional[BagsTradeAdapter] = None


def get_trade_adapter() -> BagsTradeAdapter:
    """Get singleton trade adapter."""
    global _adapter
    if _adapter is None:
        _adapter = BagsTradeAdapter()
    return _adapter


# =============================================================================
# Compatibility Layer
# =============================================================================


async def execute_swap(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage: float = 0.5,
) -> Tuple[str, int]:
    """
    Execute swap - compatible with existing jito_executor interface.

    This function can be used as a drop-in replacement:
        from core.trading.bags_adapter import execute_swap

    Instead of:
        from core.jito_executor import execute_swap
    """
    adapter = get_trade_adapter()
    return await adapter.execute_swap(input_mint, output_mint, amount, slippage)
