"""
CoinGlass API Client

Fetches liquidation data for trading signal generation.

API Documentation: https://docs.coinglass.com/

Note: Requires API key from CoinGlass.
Free tier: Limited requests
Pro tier: Higher limits, more data
"""

import os
import logging
import asyncio
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class TimeInterval(Enum):
    """Supported time intervals."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


@dataclass
class LiquidationData:
    """Aggregated liquidation data."""
    symbol: str
    timestamp: datetime
    long_liquidations: float  # USD value
    short_liquidations: float  # USD value
    long_count: int
    short_count: int
    largest_single: float  # Largest single liquidation
    interval: str

    @property
    def total_liquidations(self) -> float:
        return self.long_liquidations + self.short_liquidations

    @property
    def imbalance_ratio(self) -> float:
        if self.short_liquidations == 0:
            return float('inf') if self.long_liquidations > 0 else 1.0
        return self.long_liquidations / self.short_liquidations

    @property
    def direction_bias(self) -> str:
        """Returns 'long' if more longs liquidated, 'short' if more shorts."""
        if self.long_liquidations > self.short_liquidations * 1.5:
            return 'long'  # More longs liquidated = potential long entry
        elif self.short_liquidations > self.long_liquidations * 1.5:
            return 'short'
        return 'neutral'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'long_liquidations': self.long_liquidations,
            'short_liquidations': self.short_liquidations,
            'long_count': self.long_count,
            'short_count': self.short_count,
            'total_liquidations': self.total_liquidations,
            'imbalance_ratio': self.imbalance_ratio,
            'direction_bias': self.direction_bias,
            'largest_single': self.largest_single,
            'interval': self.interval,
        }


@dataclass
class WhaleLiquidation:
    """Large liquidation event ($5M+)."""
    symbol: str
    timestamp: datetime
    side: str  # 'long' or 'short'
    value_usd: float
    price: float
    exchange: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'timestamp': self.timestamp.isoformat(),
            'side': self.side,
            'value_usd': self.value_usd,
            'price': self.price,
            'exchange': self.exchange,
        }


class CoinGlassClient:
    """
    Client for CoinGlass API.

    Provides liquidation data for:
    - Aggregated liquidations by time interval
    - Real-time large liquidations
    - Historical liquidation data

    Usage:
        client = CoinGlassClient(api_key="your_key")
        data = await client.get_liquidations("BTC", interval="5m")
    """

    BASE_URL = "https://open-api.coinglass.com/public/v2"

    def __init__(
        self,
        api_key: Optional[str] = None,
        whale_threshold: float = 5_000_000,
        request_timeout: int = 30,
    ):
        self.api_key = api_key or os.getenv("COINGLASS_API_KEY")
        self.whale_threshold = whale_threshold
        self.request_timeout = request_timeout

        # Cache for rate limiting
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 60  # seconds

        # Session (created on first request)
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.api_key:
            logger.warning(
                "CoinGlass API key not provided. "
                "Set COINGLASS_API_KEY env var or pass api_key parameter."
            )

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {
                "accept": "application/json",
                "coinglassSecret": self.api_key or "",
            }
            timeout = aiohttp.ClientTimeout(total=self.request_timeout)
            self._session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an API request."""
        # Check cache
        cache_key = f"{endpoint}:{str(params)}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.utcnow() - cached_time).total_seconds() < self._cache_ttl:
                return cached_data

        session = await self._get_session()
        url = f"{self.BASE_URL}/{endpoint}"

        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self._cache[cache_key] = (datetime.utcnow(), data)
                    return data
                elif response.status == 429:
                    logger.warning("CoinGlass rate limit hit, waiting...")
                    await asyncio.sleep(60)
                    return await self._request(endpoint, params)
                else:
                    error_text = await response.text()
                    logger.error(f"CoinGlass API error {response.status}: {error_text}")
                    return {"code": response.status, "data": None, "msg": error_text}

        except asyncio.TimeoutError:
            logger.error(f"CoinGlass request timeout: {endpoint}")
            return {"code": 408, "data": None, "msg": "Request timeout"}
        except Exception as e:
            logger.error(f"CoinGlass request error: {e}")
            return {"code": 500, "data": None, "msg": str(e)}

    async def get_liquidations(
        self,
        symbol: str = "BTC",
        interval: str = "5m",
        limit: int = 100,
    ) -> List[LiquidationData]:
        """
        Get aggregated liquidation data.

        Args:
            symbol: Trading symbol (BTC, ETH, etc.)
            interval: Time interval (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Number of periods to fetch

        Returns:
            List of LiquidationData objects
        """
        params = {
            "symbol": symbol.upper(),
            "interval": interval,
            "limit": limit,
        }

        response = await self._request("liquidation/history", params)

        if response.get("code") != "0" or not response.get("data"):
            logger.warning(f"Failed to get liquidations: {response.get('msg')}")
            return []

        results = []
        for item in response["data"]:
            try:
                results.append(LiquidationData(
                    symbol=symbol.upper(),
                    timestamp=datetime.fromtimestamp(item.get("t", 0) / 1000),
                    long_liquidations=float(item.get("longLiquidationUsd", 0)),
                    short_liquidations=float(item.get("shortLiquidationUsd", 0)),
                    long_count=int(item.get("longLiquidationCount", 0)),
                    short_count=int(item.get("shortLiquidationCount", 0)),
                    largest_single=float(item.get("largestSingleLiquidation", 0)),
                    interval=interval,
                ))
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse liquidation data: {e}")
                continue

        return results

    async def get_recent_whale_liquidations(
        self,
        symbol: str = "BTC",
        hours: int = 24,
    ) -> List[WhaleLiquidation]:
        """
        Get recent large liquidations ($5M+).

        Args:
            symbol: Trading symbol
            hours: Hours of history to fetch

        Returns:
            List of WhaleLiquidation events
        """
        params = {
            "symbol": symbol.upper(),
            "limit": 500,
        }

        response = await self._request("liquidation/large", params)

        if response.get("code") != "0" or not response.get("data"):
            return []

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        results = []

        for item in response["data"]:
            try:
                ts = datetime.fromtimestamp(item.get("time", 0) / 1000)
                if ts < cutoff:
                    continue

                value = float(item.get("usd", 0))
                if value < self.whale_threshold:
                    continue

                results.append(WhaleLiquidation(
                    symbol=symbol.upper(),
                    timestamp=ts,
                    side='long' if item.get("side") == "SELL" else 'short',
                    value_usd=value,
                    price=float(item.get("price", 0)),
                    exchange=item.get("exchangeName", "unknown"),
                ))
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse whale liquidation: {e}")
                continue

        return results

    async def get_liquidation_summary(
        self,
        symbol: str = "BTC",
    ) -> Dict[str, Any]:
        """
        Get 24h liquidation summary.

        Returns summary with total long/short liquidations,
        counts, and largest events.
        """
        # Get 5-minute intervals for past 24 hours
        data = await self.get_liquidations(symbol, interval="5m", limit=288)

        if not data:
            return {
                "symbol": symbol,
                "period": "24h",
                "total_long_usd": 0,
                "total_short_usd": 0,
                "long_count": 0,
                "short_count": 0,
                "largest_single": 0,
                "imbalance_ratio": 1.0,
                "bias": "neutral",
            }

        total_long = sum(d.long_liquidations for d in data)
        total_short = sum(d.short_liquidations for d in data)
        long_count = sum(d.long_count for d in data)
        short_count = sum(d.short_count for d in data)
        largest = max(d.largest_single for d in data)

        imbalance = total_long / total_short if total_short > 0 else float('inf')

        if imbalance > 1.5:
            bias = "long"  # More longs liquidated = potential long
        elif imbalance < 0.67:
            bias = "short"
        else:
            bias = "neutral"

        return {
            "symbol": symbol,
            "period": "24h",
            "total_long_usd": total_long,
            "total_short_usd": total_short,
            "total_usd": total_long + total_short,
            "long_count": long_count,
            "short_count": short_count,
            "largest_single": largest,
            "imbalance_ratio": imbalance,
            "bias": bias,
        }

    async def get_multi_symbol_liquidations(
        self,
        symbols: List[str] = None,
        interval: str = "5m",
    ) -> Dict[str, LiquidationData]:
        """
        Get liquidations for multiple symbols.

        Args:
            symbols: List of symbols (defaults to major coins)
            interval: Time interval

        Returns:
            Dict mapping symbol to latest LiquidationData
        """
        if symbols is None:
            symbols = ["BTC", "ETH", "SOL", "BNB", "XRP"]

        results = {}
        tasks = [self.get_liquidations(s, interval, limit=1) for s in symbols]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for symbol, response in zip(symbols, responses):
            if isinstance(response, Exception):
                logger.warning(f"Error fetching {symbol}: {response}")
                continue
            if response:
                results[symbol] = response[0]

        return results


# Factory function
def get_coinglass_client(
    api_key: Optional[str] = None,
) -> CoinGlassClient:
    """Create a CoinGlass client instance."""
    return CoinGlassClient(api_key=api_key)
