"""
Bags.fm API Client.

Provides low-level API integration with Bags.fm for:
- Quote requests
- Swap execution
- Partner fee tracking

API Endpoints:
- GET /v1/quote - Get swap quote
- POST /v1/swap - Execute swap transaction
- GET /v1/partner/stats - Get partner statistics
"""

import asyncio
import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger("jarvis.integrations.bags")


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class BagsConfig:
    """Configuration for Bags.fm API client."""

    # API settings
    api_url: str = "https://api.bags.fm"
    partner_id: str = field(default_factory=lambda: os.getenv("BAGS_PARTNER_ID", ""))
    api_key: str = field(default_factory=lambda: os.getenv("BAGS_API_KEY", ""))
    api_secret: str = field(default_factory=lambda: os.getenv("BAGS_API_SECRET", ""))

    # Request settings
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0

    # Fee settings (basis points)
    platform_fee_bps: int = 100  # 1%
    partner_share_pct: float = 0.25  # 25% of platform fee

    # Slippage defaults
    default_slippage_bps: int = 50  # 0.5%


@dataclass
class Quote:
    """Swap quote from Bags.fm."""

    quote_id: str
    input_mint: str
    output_mint: str
    input_amount: int
    output_amount: int
    price_impact_pct: float
    platform_fee: int
    partner_fee: int
    route: List[str]
    expires_at: datetime
    raw_response: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def effective_price(self) -> float:
        if self.input_amount == 0:
            return 0
        return self.output_amount / self.input_amount

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quote_id": self.quote_id,
            "input_mint": self.input_mint,
            "output_mint": self.output_mint,
            "input_amount": self.input_amount,
            "output_amount": self.output_amount,
            "price_impact_pct": self.price_impact_pct,
            "platform_fee": self.platform_fee,
            "partner_fee": self.partner_fee,
            "route": self.route,
            "expires_at": self.expires_at.isoformat(),
        }


@dataclass
class SwapResult:
    """Result of a swap execution."""

    success: bool
    signature: str
    input_amount: int
    output_amount: int
    platform_fee: int
    partner_fee: int
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "signature": self.signature,
            "input_amount": self.input_amount,
            "output_amount": self.output_amount,
            "platform_fee": self.platform_fee,
            "partner_fee": self.partner_fee,
            "error": self.error,
        }


@dataclass
class PartnerStats:
    """Partner statistics from Bags.fm."""

    partner_id: str
    total_volume: int
    total_trades: int
    total_fees_earned: int
    period_start: datetime
    period_end: datetime
    top_pairs: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "partner_id": self.partner_id,
            "total_volume": self.total_volume,
            "total_trades": self.total_trades,
            "total_fees_earned": self.total_fees_earned,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "top_pairs": self.top_pairs,
        }


# =============================================================================
# Bags.fm Client
# =============================================================================


class BagsClient:
    """
    Bags.fm API client for swap routing.

    Features:
    - Quote requests with partner attribution
    - Swap execution with signature
    - Partner fee tracking
    - Automatic retries with exponential backoff
    """

    LAMPORTS_PER_SOL = 1_000_000_000

    def __init__(self, config: BagsConfig = None):
        self.config = config or BagsConfig()
        self._session: Optional[aiohttp.ClientSession] = None

        # Statistics
        self._total_volume = 0
        self._total_trades = 0
        self._total_partner_fees = 0

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Start the client session."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout)
            )

    async def close(self):
        """Close the client session."""
        if self._session:
            await self._session.close()
            self._session = None

    # =========================================================================
    # Authentication
    # =========================================================================

    def _generate_signature(self, timestamp: int, method: str, path: str, body: str = "") -> str:
        """Generate HMAC signature for API request."""
        message = f"{timestamp}{method}{path}{body}"
        signature = hmac.new(
            self.config.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _get_auth_headers(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Get authentication headers for API request."""
        timestamp = int(time.time() * 1000)
        signature = self._generate_signature(timestamp, method, path, body)

        return {
            "X-Partner-ID": self.config.partner_id,
            "X-API-Key": self.config.api_key,
            "X-Timestamp": str(timestamp),
            "X-Signature": signature,
            "Content-Type": "application/json",
        }

    # =========================================================================
    # API Methods
    # =========================================================================

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = None,
    ) -> Quote:
        """
        Get a swap quote.

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest units (lamports for SOL)
            slippage_bps: Slippage tolerance in basis points

        Returns:
            Quote object with swap details
        """
        if slippage_bps is None:
            slippage_bps = self.config.default_slippage_bps

        path = "/v1/quote"
        params = {
            "inputMint": input_mint,
            "outputMint": output_mint,
            "amount": str(amount),
            "slippageBps": str(slippage_bps),
            "partnerId": self.config.partner_id,
        }

        response = await self._request("GET", path, params=params)

        return Quote(
            quote_id=response.get("quoteId", ""),
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=amount,
            output_amount=int(response.get("outAmount", 0)),
            price_impact_pct=float(response.get("priceImpactPct", 0)),
            platform_fee=int(response.get("platformFee", 0)),
            partner_fee=int(response.get("partnerFee", 0)),
            route=response.get("routePlan", []),
            expires_at=datetime.fromisoformat(
                response.get("expiresAt", datetime.now(timezone.utc).isoformat())
            ),
            raw_response=response,
        )

    async def execute_swap(
        self,
        quote: Quote,
        user_public_key: str,
        signed_transaction: str,
    ) -> SwapResult:
        """
        Execute a swap transaction.

        Args:
            quote: Quote obtained from get_quote
            user_public_key: User's wallet public key
            signed_transaction: Base64-encoded signed transaction

        Returns:
            SwapResult with execution details
        """
        if quote.is_expired:
            return SwapResult(
                success=False,
                signature="",
                input_amount=quote.input_amount,
                output_amount=0,
                platform_fee=0,
                partner_fee=0,
                error="Quote expired",
            )

        path = "/v1/swap"
        body = {
            "quoteId": quote.quote_id,
            "userPublicKey": user_public_key,
            "signedTransaction": signed_transaction,
        }

        try:
            response = await self._request("POST", path, json=body)

            result = SwapResult(
                success=response.get("success", False),
                signature=response.get("signature", ""),
                input_amount=quote.input_amount,
                output_amount=int(response.get("outAmount", quote.output_amount)),
                platform_fee=int(response.get("platformFee", 0)),
                partner_fee=int(response.get("partnerFee", 0)),
            )

            # Update statistics
            if result.success:
                self._total_volume += quote.input_amount
                self._total_trades += 1
                self._total_partner_fees += result.partner_fee

            return result

        except Exception as e:
            logger.error(f"Swap execution failed: {e}")
            return SwapResult(
                success=False,
                signature="",
                input_amount=quote.input_amount,
                output_amount=0,
                platform_fee=0,
                partner_fee=0,
                error=str(e),
            )

    async def get_partner_stats(self) -> Dict[str, Any]:
        """Get partner statistics from Bags.fm."""
        path = "/v1/partner/stats"

        try:
            response = await self._request("GET", path)
            return {
                "total_volume": response.get("totalVolume", 0),
                "total_trades": response.get("totalTrades", 0),
                "total_fees_earned": response.get("totalFeesEarned", 0),
                "pending_fees": response.get("pendingFees", 0),
                "claimed_fees": response.get("claimedFees", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get partner stats: {e}")
            return {}

    async def claim_fees(self, destination_wallet: str) -> Dict[str, Any]:
        """
        Claim accumulated partner fees.

        Args:
            destination_wallet: Wallet to receive fees

        Returns:
            Claim result with signature
        """
        path = "/v1/partner/claim"
        body = {
            "destinationWallet": destination_wallet,
        }

        try:
            response = await self._request("POST", path, json=body)
            return {
                "success": response.get("success", False),
                "signature": response.get("signature", ""),
                "amount": response.get("amount", 0),
            }
        except Exception as e:
            logger.error(f"Fee claim failed: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # HTTP Helper
    # =========================================================================

    async def _request(
        self,
        method: str,
        path: str,
        params: Dict[str, str] = None,
        json: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Make an authenticated API request."""
        if self._session is None:
            await self.start()

        url = f"{self.config.api_url}{path}"
        body = ""
        if json:
            import json as json_lib
            body = json_lib.dumps(json)

        headers = self._get_auth_headers(method, path, body)

        for attempt in range(self.config.max_retries):
            try:
                async with self._session.request(
                    method,
                    url,
                    params=params,
                    json=json,
                    headers=headers,
                ) as response:
                    data = await response.json()

                    if response.status >= 400:
                        error = data.get("error", f"HTTP {response.status}")
                        raise Exception(f"API error: {error}")

                    return data

            except aiohttp.ClientError as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(self.config.retry_delay * (2 ** attempt))
                else:
                    raise

        raise Exception("Max retries exceeded")

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_local_stats(self) -> Dict[str, Any]:
        """Get local client statistics."""
        return {
            "total_volume_lamports": self._total_volume,
            "total_volume_sol": self._total_volume / self.LAMPORTS_PER_SOL,
            "total_trades": self._total_trades,
            "total_partner_fees_lamports": self._total_partner_fees,
            "total_partner_fees_sol": self._total_partner_fees / self.LAMPORTS_PER_SOL,
        }

    def reset_stats(self):
        """Reset local statistics."""
        self._total_volume = 0
        self._total_trades = 0
        self._total_partner_fees = 0


# =============================================================================
# Singleton
# =============================================================================

_client: Optional[BagsClient] = None


def get_bags_client() -> BagsClient:
    """Get singleton Bags.fm client."""
    global _client
    if _client is None:
        _client = BagsClient()
    return _client
