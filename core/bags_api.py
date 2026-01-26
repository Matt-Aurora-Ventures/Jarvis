"""
Bags.fm API Client - Simplified wrapper

US-005: bags.fm + Jupiter Backup with TP/SL

This is a clean, focused API wrapper for Bags.fm trading operations.
For the full-featured client with partner integration, see core/trading/bags_client.py
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BagsAPI:
    """
    Simple Bags.fm API client for swap operations.

    Usage:
        api = BagsAPI()
        result = await api.swap(
            from_token="SOL",
            to_token="TOKEN_MINT",
            amount_lamports=500000000,  # 0.5 SOL
            wallet_address="...",
            slippage=0.01
        )
    """

    BASE_URL = "https://api.bags.fm/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        partner_key: Optional[str] = None,
    ):
        """
        Initialize Bags API client.

        Args:
            api_key: Bags.fm API key (defaults to BAGS_API_KEY env var)
            partner_key: Partner key for fee sharing (defaults to BAGS_PARTNER_KEY env var)
        """
        self.api_key = api_key or os.environ.get("BAGS_API_KEY")
        self.partner_key = partner_key or os.environ.get("BAGS_PARTNER_KEY")
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize HTTP client lazily (reused across requests)."""
        try:
            import httpx
            # Reusable client - reduces 50-100ms overhead per request
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Jarvis/1.0",
                },
            )
        except ImportError:
            logger.warning("httpx not installed, BagsAPI will not work")

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    async def swap(
        self,
        from_token: str,
        to_token: str,
        amount_lamports: int,
        wallet_address: str,
        slippage: float = 0.01,
    ) -> Dict[str, Any]:
        """
        Execute a token swap via Bags.fm.

        Args:
            from_token: Source token mint address (or "SOL")
            to_token: Destination token mint address
            amount_lamports: Amount in lamports (smallest unit)
            wallet_address: User's wallet address
            slippage: Slippage tolerance (0.01 = 1%)

        Returns:
            Dict with success, tx_hash, amount_out, or error
        """
        if not self._client:
            return {"success": False, "error": "HTTP client not initialized"}

        try:
            swap_data = {
                "from": from_token,
                "to": to_token,
                "amount": str(amount_lamports),
                "slippageBps": int(slippage * 10000),  # Convert to basis points
                "wallet": wallet_address,
            }

            if self.partner_key:
                swap_data["partnerKey"] = self.partner_key

            response = await self._client.post(
                f"{self.BASE_URL}/swap",
                json=swap_data,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            result = response.json()

            return {
                "success": True,
                "tx_hash": result.get("txHash"),
                "amount_out": float(result.get("outputAmount", 0)),
                "price": float(result.get("price", 0)),
                "source": "bags_fm",
            }

        except Exception as e:
            logger.error(f"Bags.fm swap failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def get_token_info(self, mint: str) -> Optional[Dict[str, Any]]:
        """
        Get token information from Bags.fm.

        Args:
            mint: Token mint address

        Returns:
            Token info dict or None if not found
        """
        if not self._client:
            return None

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/token/{mint}",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            return {
                "symbol": data.get("symbol", ""),
                "name": data.get("name", ""),
                "decimals": int(data.get("decimals", 9)),
                "price": float(data.get("price", 0)),
                "price_usd": float(data.get("priceUsd", 0)),
                "liquidity": float(data.get("liquidity", 0)),
                "volume_24h": float(data.get("volume24h", 0)),
                "market_cap": float(data.get("marketCap", 0)),
            }

        except Exception as e:
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status == 404:
                logger.debug(f"Token not found on Bags.fm: {mint}")
            else:
                logger.error(f"Failed to get token info: {e}")
            return None

    async def get_chart_data(
        self,
        mint: str,
        interval: str = "1h",
        limit: int = 100,
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get price chart data for a token.

        Args:
            mint: Token mint address
            interval: Candle interval (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of candles to fetch (max 1000)

        Returns:
            List of candle dicts or None on error
        """
        if not self._client:
            return None

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/chart/{mint}",
                params={
                    "interval": interval,
                    "limit": min(limit, 1000),
                },
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            candles = data.get("candles", data if isinstance(data, list) else [])
            return [
                {
                    "timestamp": c.get("timestamp", c.get("t", 0)),
                    "open": float(c.get("open", c.get("o", 0))),
                    "high": float(c.get("high", c.get("h", 0))),
                    "low": float(c.get("low", c.get("l", 0))),
                    "close": float(c.get("close", c.get("c", 0))),
                    "volume": float(c.get("volume", c.get("v", 0))),
                }
                for c in candles
            ]

        except Exception as e:
            logger.error(f"Failed to get chart data: {e}")
            return None

    async def get_quote(
        self,
        from_token: str,
        to_token: str,
        amount_lamports: int,
        slippage: float = 0.01,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a swap quote without executing.

        Args:
            from_token: Source token mint
            to_token: Destination token mint
            amount_lamports: Amount in lamports
            slippage: Slippage tolerance

        Returns:
            Quote dict or None on error
        """
        if not self._client:
            return None

        try:
            response = await self._client.get(
                f"{self.BASE_URL}/quote",
                params={
                    "from": from_token,
                    "to": to_token,
                    "amount": str(amount_lamports),
                    "slippageBps": int(slippage * 10000),
                },
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            return {
                "from_token": from_token,
                "to_token": to_token,
                "in_amount": amount_lamports,
                "out_amount": int(data.get("outputAmount", 0)),
                "price": float(data.get("price", 0)),
                "price_impact": float(data.get("priceImpact", 0)),
                "fee": float(data.get("fee", 0)),
            }

        except Exception as e:
            logger.error(f"Failed to get quote: {e}")
            return None

    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()


# Singleton instance
_bags_api: Optional[BagsAPI] = None


def get_bags_api() -> BagsAPI:
    """Get singleton BagsAPI instance."""
    global _bags_api
    if _bags_api is None:
        _bags_api = BagsAPI()
    return _bags_api
