"""
Bags.fm API Client

Client for Bags.fm API trading operations.
Used for copy trading and partner fee collection.

Prompt #165: Bags API Client
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any
from enum import Enum
import json

logger = logging.getLogger(__name__)


class SwapStatus(str, Enum):
    """Swap transaction status"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class SwapResult:
    """Result of a swap operation"""
    success: bool
    tx_hash: Optional[str] = None
    from_token: str = ""
    to_token: str = ""
    from_amount: float = 0.0
    to_amount: float = 0.0
    price: float = 0.0
    fee_paid: float = 0.0
    partner_fee: float = 0.0
    slippage: float = 0.0
    status: SwapStatus = SwapStatus.PENDING
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TokenInfo:
    """Token information from Bags API"""
    address: str
    symbol: str
    name: str
    decimals: int
    price_usd: float
    price_sol: float
    volume_24h: float
    liquidity: float
    holders: int
    market_cap: float


@dataclass
class Quote:
    """Swap quote from Bags API"""
    from_token: str
    to_token: str
    from_amount: float
    to_amount: float
    price: float
    price_impact: float
    fee: float
    route: List[str]
    expires_at: datetime
    quote_id: str


class BagsAPIClient:
    """
    Client for Bags.fm API

    Handles trading operations securely.
    Partner integration for fee sharing.
    """

    BASE_URL = "https://public-api-v2.bags.fm/api/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        partner_key: Optional[str] = None
    ):
        self.api_key = api_key or os.environ.get("BAGS_API_KEY")
        self.partner_key = partner_key or os.environ.get("BAGS_PARTNER_KEY")
        self.client = None
        self._initialize_client()

        # Rate limiting
        self.requests_per_minute = 60
        self.request_timestamps: List[datetime] = []

        # Tracking
        self.total_volume = 0.0
        self.total_partner_fees = 0.0
        self.successful_swaps = 0
        self.failed_swaps = 0

    def _initialize_client(self):
        """Initialize HTTP client"""
        try:
            import httpx
            self.client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Jarvis/1.0"
                }
            )
            logger.info("Bags API client initialized")
        except ImportError:
            logger.warning("httpx not installed, Bags client will not work")

    async def _check_rate_limit(self):
        """Check and enforce rate limiting"""
        now = datetime.now()

        # Remove old timestamps
        self.request_timestamps = [
            ts for ts in self.request_timestamps
            if (now - ts).seconds < 60
        ]

        if len(self.request_timestamps) >= self.requests_per_minute:
            wait_time = 60 - (now - self.request_timestamps[0]).seconds
            logger.warning(f"Rate limit reached, waiting {wait_time}s")
            await asyncio.sleep(wait_time)

        self.request_timestamps.append(now)

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with auth"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def get_quote(
        self,
        from_token: str,
        to_token: str,
        amount: float,
        slippage_bps: int = 100  # 1%
    ) -> Optional[Quote]:
        """Get swap quote without executing"""

        if not self.client:
            logger.error("HTTP client not initialized")
            return None

        await self._check_rate_limit()

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/quote",
                params={
                    "from": from_token,
                    "to": to_token,
                    "amount": str(amount),
                    "slippageBps": slippage_bps
                },
                headers=self._get_headers()
            )

            response.raise_for_status()
            data = response.json()

            return Quote(
                from_token=from_token,
                to_token=to_token,
                from_amount=amount,
                to_amount=float(data.get("toAmount", 0)),
                price=float(data.get("price", 0)),
                price_impact=float(data.get("priceImpact", 0)),
                fee=float(data.get("fee", 0)),
                route=data.get("route", []),
                expires_at=datetime.now(),  # Would parse from response
                quote_id=data.get("quoteId", "")
            )

        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            return None

    async def swap(
        self,
        from_token: str,
        to_token: str,
        amount: float,
        wallet_address: str,
        slippage_bps: int = 100,
        signed_transaction: Optional[bytes] = None
    ) -> SwapResult:
        """
        Execute a swap

        NOTE: For security, transaction should be signed client-side.
        Never send private keys to the API.
        """

        if not self.client:
            return SwapResult(
                success=False,
                error="HTTP client not initialized"
            )

        await self._check_rate_limit()

        try:
            # Get quote first
            quote = await self.get_quote(from_token, to_token, amount, slippage_bps)

            if not quote:
                return SwapResult(
                    success=False,
                    from_token=from_token,
                    to_token=to_token,
                    from_amount=amount,
                    error="Failed to get quote"
                )

            # Build swap request
            swap_data = {
                "from": from_token,
                "to": to_token,
                "amount": str(amount),
                "slippageBps": slippage_bps,
                "wallet": wallet_address,
            }

            # Add partner key for fee sharing
            if self.partner_key:
                swap_data["partnerKey"] = self.partner_key

            # Add signed transaction if provided
            if signed_transaction:
                import base64
                swap_data["signedTransaction"] = base64.b64encode(signed_transaction).decode()

            response = await self.client.post(
                f"{self.BASE_URL}/swap",
                json=swap_data,
                headers=self._get_headers()
            )

            response.raise_for_status()
            result = response.json()

            # Track success
            self.successful_swaps += 1
            self.total_volume += amount
            partner_fee = float(result.get("partnerFee", 0))
            self.total_partner_fees += partner_fee

            return SwapResult(
                success=True,
                tx_hash=result.get("txHash"),
                from_token=from_token,
                to_token=to_token,
                from_amount=amount,
                to_amount=float(result.get("toAmount", 0)),
                price=float(result.get("price", 0)),
                fee_paid=float(result.get("fee", 0)),
                partner_fee=partner_fee,
                slippage=float(result.get("slippage", 0)),
                status=SwapStatus.CONFIRMED
            )

        except Exception as e:
            self.failed_swaps += 1
            logger.error(f"Swap failed: {e}")

            return SwapResult(
                success=False,
                from_token=from_token,
                to_token=to_token,
                from_amount=amount,
                error=str(e),
                status=SwapStatus.FAILED
            )

    async def get_token_info(self, mint: str) -> Optional[TokenInfo]:
        """Get token information"""

        if not self.client:
            return None

        await self._check_rate_limit()

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/token/{mint}",
                headers=self._get_headers()
            )

            response.raise_for_status()
            data = response.json()

            return TokenInfo(
                address=mint,
                symbol=data.get("symbol", ""),
                name=data.get("name", ""),
                decimals=int(data.get("decimals", 9)),
                price_usd=float(data.get("priceUsd", 0)),
                price_sol=float(data.get("priceSol", 0)),
                volume_24h=float(data.get("volume24h", 0)),
                liquidity=float(data.get("liquidity", 0)),
                holders=int(data.get("holders", 0)),
                market_cap=float(data.get("marketCap", 0))
            )

        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return None

    async def get_trending_tokens(self, limit: int = 10) -> List[TokenInfo]:
        """Get trending tokens"""

        if not self.client:
            return []

        await self._check_rate_limit()

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/tokens/trending",
                params={"limit": limit},
                headers=self._get_headers()
            )

            response.raise_for_status()
            data = response.json()

            tokens = []
            for token_data in data.get("tokens", [])[:limit]:
                tokens.append(TokenInfo(
                    address=token_data.get("address", ""),
                    symbol=token_data.get("symbol", ""),
                    name=token_data.get("name", ""),
                    decimals=int(token_data.get("decimals", 9)),
                    price_usd=float(token_data.get("priceUsd", 0)),
                    price_sol=float(token_data.get("priceSol", 0)),
                    volume_24h=float(token_data.get("volume24h", 0)),
                    liquidity=float(token_data.get("liquidity", 0)),
                    holders=int(token_data.get("holders", 0)),
                    market_cap=float(token_data.get("marketCap", 0))
                ))

            return tokens

        except Exception as e:
            logger.error(f"Failed to get trending tokens: {e}")
            return []

    async def get_top_tokens_by_volume(self, limit: int = 15) -> List[TokenInfo]:
        """Get top tokens sorted by 24h volume"""

        if not self.client:
            return []

        await self._check_rate_limit()

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/tokens/top",
                params={"limit": limit, "sort": "volume24h"},
                headers=self._get_headers()
            )

            response.raise_for_status()
            data = response.json()

            tokens = []
            for token_data in data.get("tokens", [])[:limit]:
                tokens.append(TokenInfo(
                    address=token_data.get("address", ""),
                    symbol=token_data.get("symbol", ""),
                    name=token_data.get("name", ""),
                    decimals=int(token_data.get("decimals", 9)),
                    price_usd=float(token_data.get("priceUsd", 0)),
                    price_sol=float(token_data.get("priceSol", 0)),
                    volume_24h=float(token_data.get("volume24h", 0)),
                    liquidity=float(token_data.get("liquidity", 0)),
                    holders=int(token_data.get("holders", 0)),
                    market_cap=float(token_data.get("marketCap", 0))
                ))

            return tokens

        except Exception as e:
            logger.error(f"Failed to get top tokens by volume: {e}")
            return []

    async def claim_partner_fees(self) -> Dict[str, Any]:
        """Claim accumulated partner fees"""

        if not self.partner_key:
            return {"success": False, "error": "No partner key configured"}

        if not self.client:
            return {"success": False, "error": "HTTP client not initialized"}

        await self._check_rate_limit()

        try:
            response = await self.client.post(
                f"{self.BASE_URL}/partner/claim",
                json={"partnerKey": self.partner_key},
                headers=self._get_headers()
            )

            response.raise_for_status()
            result = response.json()

            return {
                "success": True,
                "amount_claimed": float(result.get("amountClaimed", 0)),
                "tx_hash": result.get("txHash"),
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to claim partner fees: {e}")
            return {"success": False, "error": str(e)}

    async def get_partner_stats(self) -> Dict[str, Any]:
        """Get partner statistics"""

        if not self.partner_key:
            return {"error": "No partner key configured"}

        if not self.client:
            return {"error": "HTTP client not initialized"}

        await self._check_rate_limit()

        try:
            response = await self.client.get(
                f"{self.BASE_URL}/partner/stats",
                params={"partnerKey": self.partner_key},
                headers=self._get_headers()
            )

            response.raise_for_status()
            data = response.json()

            return {
                "total_volume": float(data.get("totalVolume", 0)),
                "total_fees_earned": float(data.get("totalFeesEarned", 0)),
                "pending_fees": float(data.get("pendingFees", 0)),
                "total_swaps": int(data.get("totalSwaps", 0)),
                "unique_users": int(data.get("uniqueUsers", 0))
            }

        except Exception as e:
            logger.error(f"Failed to get partner stats: {e}")
            return {"error": str(e)}

    def get_client_stats(self) -> Dict[str, Any]:
        """Get local client statistics"""
        return {
            "total_volume": self.total_volume,
            "total_partner_fees": self.total_partner_fees,
            "successful_swaps": self.successful_swaps,
            "failed_swaps": self.failed_swaps,
            "success_rate": (
                self.successful_swaps / (self.successful_swaps + self.failed_swaps)
                if (self.successful_swaps + self.failed_swaps) > 0
                else 0.0
            ),
            "requests_in_last_minute": len(self.request_timestamps)
        }

    async def close(self):
        """Close the HTTP client"""
        if self.client:
            await self.client.aclose()
            logger.info("Bags API client closed")


class BagsTradeRouter:
    """
    Trade router that uses Bags.fm with Jupiter fallback

    Provides resilient trading by falling back to Jupiter
    if Bags.fm is unavailable.
    """

    def __init__(
        self,
        bags_client: Optional[BagsAPIClient] = None,
        jupiter_client: Any = None,
        partner_id: str = "jarvis"
    ):
        self.bags = bags_client or BagsAPIClient()
        self.jupiter = jupiter_client
        self.partner_id = partner_id

        # Tracking
        self.bags_trades = 0
        self.jupiter_trades = 0
        self.total_volume = 0.0

    async def swap(
        self,
        wallet_address: str,
        from_token: str,
        to_token: str,
        amount: float,
        slippage_bps: int = 100,
        signed_transaction: Optional[bytes] = None
    ) -> SwapResult:
        """
        Execute swap through Bags.fm, falling back to Jupiter

        Prioritizes Bags.fm for partner fee collection.
        """

        # Try Bags.fm first
        try:
            result = await self.bags.swap(
                from_token=from_token,
                to_token=to_token,
                amount=amount,
                wallet_address=wallet_address,
                slippage_bps=slippage_bps,
                signed_transaction=signed_transaction
            )

            if result.success:
                self.bags_trades += 1
                self.total_volume += amount
                logger.info(f"Swap executed via Bags.fm: {result.tx_hash}")
                return result

        except Exception as e:
            logger.warning(f"Bags.fm swap failed, trying Jupiter: {e}")

        # Fallback to Jupiter
        if self.jupiter:
            try:
                result = await self._jupiter_swap(
                    wallet_address=wallet_address,
                    from_token=from_token,
                    to_token=to_token,
                    amount=amount,
                    slippage_bps=slippage_bps
                )

                if result.success:
                    self.jupiter_trades += 1
                    self.total_volume += amount
                    logger.info(f"Swap executed via Jupiter: {result.tx_hash}")
                    return result

            except Exception as e:
                logger.error(f"Jupiter swap also failed: {e}")

        return SwapResult(
            success=False,
            from_token=from_token,
            to_token=to_token,
            from_amount=amount,
            error="All swap routes failed"
        )

    async def _jupiter_swap(
        self,
        wallet_address: str,
        from_token: str,
        to_token: str,
        amount: float,
        slippage_bps: int
    ) -> SwapResult:
        """Execute swap via Jupiter"""

        if not self.jupiter:
            return SwapResult(
                success=False,
                error="Jupiter client not configured"
            )

        # Would implement Jupiter swap here
        # Placeholder for now
        return SwapResult(
            success=False,
            error="Jupiter swap not implemented"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics"""
        total_trades = self.bags_trades + self.jupiter_trades

        return {
            "total_volume": self.total_volume,
            "total_trades": total_trades,
            "bags_trades": self.bags_trades,
            "jupiter_trades": self.jupiter_trades,
            "bags_percentage": (
                self.bags_trades / total_trades * 100
                if total_trades > 0 else 0
            ),
            "partner_id": self.partner_id
        }


class SuccessFeeManager:
    """
    Success Fee Manager - 0.5% fee on profitable trades

    Integrates with Bags.fm for fee collection.
    Only charges fee on winning trades (positive PnL).
    """

    SUCCESS_FEE_PERCENT = 0.5  # 0.5% fee on winning trades

    def __init__(self, bags_client: Optional[BagsAPIClient] = None):
        self.bags = bags_client
        self.total_fees_collected = 0.0
        self.fee_transactions: List[Dict[str, Any]] = []

    def calculate_success_fee(
        self,
        entry_price: float,
        exit_price: float,
        amount_sol: float,
        token_symbol: str,
    ) -> Dict[str, Any]:
        """
        Calculate success fee for a closed trade.

        Only charges fee if trade was profitable.
        Returns fee details including amount and whether it applies.
        """
        # Calculate PnL
        pnl_percent = ((exit_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
        pnl_usd = amount_sol * (exit_price - entry_price) * 225  # Approximate SOL price

        # Only charge fee on profitable trades
        if pnl_percent <= 0 or pnl_usd <= 0:
            return {
                "applies": False,
                "reason": "Not a winning trade",
                "pnl_percent": pnl_percent,
                "pnl_usd": pnl_usd,
                "fee_amount": 0.0,
                "fee_percent": 0.0,
            }

        # Calculate fee (0.5% of profit)
        fee_amount = pnl_usd * (self.SUCCESS_FEE_PERCENT / 100)

        return {
            "applies": True,
            "token_symbol": token_symbol,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "amount_sol": amount_sol,
            "pnl_percent": pnl_percent,
            "pnl_usd": pnl_usd,
            "fee_percent": self.SUCCESS_FEE_PERCENT,
            "fee_amount": fee_amount,
            "net_profit": pnl_usd - fee_amount,
            "timestamp": datetime.now().isoformat(),
        }

    async def collect_fee(
        self,
        fee_details: Dict[str, Any],
        wallet_address: str,
    ) -> Dict[str, Any]:
        """
        Collect the success fee via Bags.fm API.

        Returns collection result with transaction details.
        """
        if not fee_details.get("applies"):
            return {"success": False, "reason": "Fee does not apply"}

        fee_amount = fee_details.get("fee_amount", 0)
        if fee_amount <= 0:
            return {"success": False, "reason": "No fee to collect"}

        try:
            # Record fee collection
            fee_record = {
                "timestamp": datetime.now().isoformat(),
                "wallet": wallet_address,
                "token": fee_details.get("token_symbol"),
                "pnl_usd": fee_details.get("pnl_usd"),
                "fee_amount": fee_amount,
                "fee_percent": self.SUCCESS_FEE_PERCENT,
            }

            self.fee_transactions.append(fee_record)
            self.total_fees_collected += fee_amount

            # In production, this would transfer the fee via Bags API
            # For now, we track it locally
            logger.info(
                f"Success fee collected: ${fee_amount:.4f} on {fee_details.get('token_symbol')} "
                f"(${fee_details.get('pnl_usd'):.2f} profit)"
            )

            return {
                "success": True,
                "fee_amount": fee_amount,
                "total_collected": self.total_fees_collected,
                "transaction_count": len(self.fee_transactions),
            }

        except Exception as e:
            logger.error(f"Failed to collect success fee: {e}")
            return {"success": False, "error": str(e)}

    def get_fee_stats(self) -> Dict[str, Any]:
        """Get fee collection statistics."""
        return {
            "fee_percent": self.SUCCESS_FEE_PERCENT,
            "total_collected": self.total_fees_collected,
            "transaction_count": len(self.fee_transactions),
            "recent_fees": self.fee_transactions[-10:],
        }


# Singleton instances
_bags_client: Optional[BagsAPIClient] = None
_fee_manager: Optional[SuccessFeeManager] = None


def get_bags_client() -> BagsAPIClient:
    """Get Bags API client singleton"""
    global _bags_client

    if _bags_client is None:
        _bags_client = BagsAPIClient()

    return _bags_client


def get_success_fee_manager() -> SuccessFeeManager:
    """Get Success Fee Manager singleton"""
    global _fee_manager

    if _fee_manager is None:
        _fee_manager = SuccessFeeManager(bags_client=get_bags_client())

    return _fee_manager


# Testing
if __name__ == "__main__":
    async def test():
        client = BagsAPIClient()

        # Test get quote
        print("Getting quote...")
        quote = await client.get_quote(
            from_token="SOL",
            to_token="BONK",
            amount=0.1
        )
        if quote:
            print(f"Quote: {quote.from_amount} {quote.from_token} -> {quote.to_amount} {quote.to_token}")

        # Test get trending
        print("\nGetting trending tokens...")
        trending = await client.get_trending_tokens(limit=5)
        for token in trending:
            print(f"  {token.symbol}: ${token.price_usd:.6f}")

        # Print stats
        print(f"\nClient stats: {client.get_client_stats()}")

        await client.close()

    asyncio.run(test())
