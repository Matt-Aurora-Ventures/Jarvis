"""
BirdEye Market Data Service Adapter

Provides async interface to BirdEye's Solana token data API.
Wraps the existing core.birdeye module with the MarketDataService interface.

Features:
- Async wrappers for all API calls
- Rate limiting and caching (delegated to core module)
- OHLCV data normalization
- Health checks

Usage:
    adapter = BirdEyeMarketAdapter()
    price = await adapter.get_price("SOL")
    print(f"SOL: ${price.price_usd}")
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

from lifeos.services.interfaces import (
    MarketDataService,
    TokenPrice,
    TokenInfo,
    LiquidityInfo,
    OHLCVCandle,
    ServiceError,
    ServiceHealth,
    ServiceStatus,
)

logger = logging.getLogger(__name__)

# Common Solana token addresses
KNOWN_TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "WSOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "RNDR": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",
}


class BirdEyeMarketAdapter(MarketDataService):
    """
    BirdEye market data service adapter.

    Implements the MarketDataService interface for BirdEye's API.
    Delegates actual API calls to core.birdeye module.
    """

    def __init__(self, chain: str = "solana"):
        """
        Initialize BirdEye adapter.

        Args:
            chain: Default blockchain to query
        """
        self._default_chain = chain
        self._birdeye = None

    @property
    def service_name(self) -> str:
        return "birdeye"

    @property
    def supported_chains(self) -> List[str]:
        return ["solana"]

    def _get_birdeye(self):
        """Lazy load birdeye module."""
        if self._birdeye is None:
            try:
                from core import birdeye
                self._birdeye = birdeye
            except ImportError as e:
                raise ServiceError(
                    service_name=self.service_name,
                    operation="import",
                    message="core.birdeye module not available",
                    original_error=e,
                    retryable=False,
                )
        return self._birdeye

    def _resolve_address(self, symbol_or_address: str) -> str:
        """Resolve a symbol to its token address."""
        # If it looks like an address (base58, 32-44 chars), use directly
        if len(symbol_or_address) >= 32 and len(symbol_or_address) <= 44:
            return symbol_or_address

        # Try to resolve symbol
        symbol = symbol_or_address.upper()
        if symbol in KNOWN_TOKENS:
            return KNOWN_TOKENS[symbol]

        # Assume it's an address
        return symbol_or_address

    async def get_price(self, token: str, chain: str = "solana") -> TokenPrice:
        """Get current price for a token."""
        birdeye = self._get_birdeye()
        address = self._resolve_address(token)

        try:
            result = await asyncio.to_thread(
                birdeye.fetch_token_price_safe,
                address,
                chain=chain,
            )

            if not result.success:
                raise ServiceError(
                    service_name=self.service_name,
                    operation="get_price",
                    message=result.error or "Unknown error",
                    retryable=result.retryable,
                )

            data = result.data.get("data", {})

            return TokenPrice(
                symbol=token.upper(),
                address=address,
                price_usd=float(data.get("value", 0)),
                change_24h=float(data.get("priceChange24h", 0)) if data.get("priceChange24h") else None,
                source="birdeye",
            )

        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="get_price",
                message=str(e),
                original_error=e,
                retryable=True,
            )

    async def get_token_info(self, token: str, chain: str = "solana") -> TokenInfo:
        """Get token information and metadata."""
        birdeye = self._get_birdeye()
        address = self._resolve_address(token)

        try:
            result = await asyncio.to_thread(
                birdeye.fetch_token_overview,
                address,
                chain=chain,
            )

            if not result:
                raise ServiceError(
                    service_name=self.service_name,
                    operation="get_token_info",
                    message="Failed to fetch token overview",
                    retryable=True,
                )

            data = result.get("data", {})
            extensions = data.get("extensions", {})

            return TokenInfo(
                symbol=data.get("symbol", token.upper()),
                name=data.get("name", "Unknown"),
                address=address,
                decimals=data.get("decimals", 9),
                chain=chain,
                logo_url=data.get("logoURI"),
                website=extensions.get("website"),
                twitter=extensions.get("twitter"),
                telegram=extensions.get("telegram"),
                description=extensions.get("description"),
            )

        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="get_token_info",
                message=str(e),
                original_error=e,
                retryable=True,
            )

    async def get_liquidity(self, token: str, chain: str = "solana") -> LiquidityInfo:
        """Get liquidity information for a token."""
        birdeye = self._get_birdeye()
        address = self._resolve_address(token)

        try:
            result = await asyncio.to_thread(
                birdeye.fetch_token_overview,
                address,
                chain=chain,
            )

            if not result:
                raise ServiceError(
                    service_name=self.service_name,
                    operation="get_liquidity",
                    message="Failed to fetch token data",
                    retryable=True,
                )

            data = result.get("data", {})

            return LiquidityInfo(
                token_address=address,
                total_liquidity_usd=float(data.get("liquidity", 0)),
                pools=[],
                main_pool_address=None,
                main_pool_dex=None,
            )

        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="get_liquidity",
                message=str(e),
                original_error=e,
                retryable=True,
            )

    async def get_ohlcv(
        self,
        token: str,
        interval: str = "1h",
        limit: int = 100,
        chain: str = "solana",
    ) -> List[OHLCVCandle]:
        """Get OHLCV candle data."""
        birdeye = self._get_birdeye()
        address = self._resolve_address(token)

        # Map common interval formats to BirdEye format
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "1H", "4h": "4H", "1d": "1D", "1w": "1W",
        }
        be_interval = interval_map.get(interval.lower(), interval.upper())

        try:
            result = await asyncio.to_thread(
                birdeye.fetch_ohlcv_safe,
                address,
                timeframe=be_interval,
                chain=chain,
                limit=limit,
            )

            if not result.success:
                raise ServiceError(
                    service_name=self.service_name,
                    operation="get_ohlcv",
                    message=result.error or "Unknown error",
                    retryable=result.retryable,
                )

            candles = birdeye.normalize_ohlcv(result.data)

            return [
                OHLCVCandle(
                    timestamp=datetime.fromtimestamp(candle["timestamp"]),
                    open=candle["open"],
                    high=candle["high"],
                    low=candle["low"],
                    close=candle["close"],
                    volume=candle["volume"],
                )
                for candle in candles
            ]

        except ServiceError:
            raise
        except Exception as e:
            raise ServiceError(
                service_name=self.service_name,
                operation="get_ohlcv",
                message=str(e),
                original_error=e,
                retryable=True,
            )

    async def search_tokens(
        self,
        query: str,
        chain: str = "solana",
        limit: int = 10,
    ) -> List[TokenInfo]:
        """Search for tokens by name or symbol."""
        query_lower = query.lower()
        results = []

        for symbol, address in KNOWN_TOKENS.items():
            if query_lower in symbol.lower():
                try:
                    info = await self.get_token_info(address, chain)
                    results.append(info)
                    if len(results) >= limit:
                        break
                except ServiceError:
                    continue

        return results

    async def health_check(self) -> ServiceHealth:
        """Check BirdEye API availability."""
        start_time = time.time()

        try:
            birdeye = self._get_birdeye()
            status = birdeye.get_api_status()

            if not status.get("has_api_key"):
                return ServiceHealth(
                    status=ServiceStatus.UNAVAILABLE,
                    message="No BirdEye API key configured",
                    metadata=status,
                )

            sol_address = KNOWN_TOKENS["SOL"]
            result = await asyncio.to_thread(
                birdeye.fetch_token_price_safe,
                sol_address,
            )

            latency = (time.time() - start_time) * 1000

            if result.success:
                return ServiceHealth(
                    status=ServiceStatus.HEALTHY,
                    latency_ms=latency,
                    message="OK",
                    metadata=status,
                )
            else:
                return ServiceHealth(
                    status=ServiceStatus.DEGRADED if result.retryable else ServiceStatus.UNAVAILABLE,
                    latency_ms=latency,
                    message=result.error or "Unknown error",
                    metadata=status,
                )

        except ServiceError as e:
            return ServiceHealth(
                status=ServiceStatus.UNAVAILABLE,
                latency_ms=(time.time() - start_time) * 1000,
                message=e.message,
            )
        except Exception as e:
            return ServiceHealth(
                status=ServiceStatus.UNAVAILABLE,
                latency_ms=(time.time() - start_time) * 1000,
                message=str(e),
            )
