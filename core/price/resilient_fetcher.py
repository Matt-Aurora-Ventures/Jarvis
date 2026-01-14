"""
Resilient Price Fetcher - Multi-source price fetching with caching and fallbacks.

Prioritizes working APIs and caches results to reduce API calls.
"""
import asyncio
import logging
import time
from typing import Dict, Optional, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class PriceResult:
    """Result of a price fetch."""
    price: float
    source: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cached: bool = False


@dataclass
class SourceHealth:
    """Track health of a price source."""
    name: str
    success_count: int = 0
    failure_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    disabled_until: Optional[datetime] = None

    @property
    def is_healthy(self) -> bool:
        """Check if source is currently healthy."""
        if self.disabled_until and datetime.utcnow() < self.disabled_until:
            return False
        return self.consecutive_failures < 5

    def record_success(self):
        """Record successful fetch."""
        self.success_count += 1
        self.last_success = datetime.utcnow()
        self.consecutive_failures = 0
        self.disabled_until = None

    def record_failure(self):
        """Record failed fetch."""
        self.failure_count += 1
        self.last_failure = datetime.utcnow()
        self.consecutive_failures += 1

        # Disable source after 5 consecutive failures
        if self.consecutive_failures >= 5:
            # Exponential backoff: 30s, 60s, 120s, 240s, max 5min
            backoff = min(30 * (2 ** (self.consecutive_failures - 5)), 300)
            self.disabled_until = datetime.utcnow() + timedelta(seconds=backoff)
            logger.warning(f"Source {self.name} disabled for {backoff}s after {self.consecutive_failures} failures")


class ResilientPriceFetcher:
    """
    Fetches prices from multiple sources with automatic failover.

    Features:
    - LRU cache with TTL
    - Automatic source health tracking
    - Priority ordering based on reliability
    - Circuit breaker for failing sources
    """

    DEXSCREENER_API = "https://api.dexscreener.com/latest"
    JUPITER_PRICE_API = "https://price.jup.ag/v6"
    COINGECKO_API = "https://api.coingecko.com/api/v3/simple/price"
    BIRDEYE_API = "https://public-api.birdeye.so/public"

    # Known stablecoin mints
    STABLECOINS = {
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": 1.0,  # USDC
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": 1.0,  # USDT
    }

    SOL_MINT = "So11111111111111111111111111111111111111112"

    def __init__(
        self,
        cache_ttl: int = 30,  # Cache prices for 30 seconds
        max_cache_size: int = 1000,
    ):
        self.cache_ttl = cache_ttl
        self.max_cache_size = max_cache_size

        self._cache: Dict[str, PriceResult] = {}
        self._session: Optional[aiohttp.ClientSession] = None

        # Track source health
        self._source_health: Dict[str, SourceHealth] = {
            "dexscreener": SourceHealth("dexscreener"),
            "jupiter": SourceHealth("jupiter"),
            "coingecko": SourceHealth("coingecko"),
            "birdeye": SourceHealth("birdeye"),
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_cached(self, mint: str) -> Optional[PriceResult]:
        """Get cached price if still valid."""
        if mint in self._cache:
            result = self._cache[mint]
            age = (datetime.utcnow() - result.timestamp).total_seconds()
            if age < self.cache_ttl:
                return PriceResult(
                    price=result.price,
                    source=result.source,
                    timestamp=result.timestamp,
                    cached=True
                )
        return None

    def _set_cached(self, mint: str, result: PriceResult):
        """Cache a price result."""
        self._cache[mint] = result

        # Evict old entries if cache is too large
        if len(self._cache) > self.max_cache_size:
            # Remove oldest 10%
            entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].timestamp
            )
            for key, _ in entries[:len(entries) // 10]:
                del self._cache[key]

    async def _fetch_dexscreener(self, mint: str) -> Optional[float]:
        """Fetch price from DexScreener."""
        session = await self._get_session()
        url = f"{self.DEXSCREENER_API}/dex/tokens/{mint}"

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                pairs = data.get("pairs") or []

                # Filter to Solana pairs
                sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]
                if not sol_pairs:
                    return None

                # Pick highest liquidity pair
                best = max(sol_pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                price = float(best.get("priceUsd") or 0)
                return price if price > 0 else None

        except Exception:
            return None

    async def _fetch_jupiter(self, mint: str) -> Optional[float]:
        """Fetch price from Jupiter."""
        session = await self._get_session()

        try:
            async with session.get(
                f"{self.JUPITER_PRICE_API}/price",
                params={"ids": mint}
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                price = data.get("data", {}).get(mint, {}).get("price")
                return float(price) if price else None

        except Exception:
            return None

    async def _fetch_coingecko_sol(self) -> Optional[float]:
        """Fetch SOL price from CoinGecko."""
        session = await self._get_session()

        try:
            async with session.get(
                self.COINGECKO_API,
                params={"ids": "solana", "vs_currencies": "usd"}
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return data.get("solana", {}).get("usd")

        except Exception:
            return None

    async def get_price(self, mint: str) -> PriceResult:
        """
        Get price for a token mint address.

        Returns cached result if available, otherwise fetches from multiple sources.
        """
        # Check stablecoins first
        if mint in self.STABLECOINS:
            return PriceResult(price=self.STABLECOINS[mint], source="stablecoin")

        # Check cache
        cached = self._get_cached(mint)
        if cached:
            return cached

        # Try sources in health-based order
        sources = [
            ("dexscreener", self._fetch_dexscreener),
            ("jupiter", self._fetch_jupiter),
        ]

        # Sort by health (healthy first, then by success rate)
        def source_priority(item):
            name, _ = item
            health = self._source_health[name]
            if not health.is_healthy:
                return (1, -health.success_count)
            return (0, -health.success_count)

        sources.sort(key=source_priority)

        # SOL special case
        if mint == self.SOL_MINT:
            sol_price = await self._fetch_coingecko_sol()
            if sol_price:
                result = PriceResult(price=sol_price, source="coingecko")
                self._set_cached(mint, result)
                self._source_health["coingecko"].record_success()
                return result

        # Try each source
        for source_name, fetch_fn in sources:
            health = self._source_health[source_name]
            if not health.is_healthy:
                continue

            price = await fetch_fn(mint)
            if price and price > 0:
                result = PriceResult(price=price, source=source_name)
                self._set_cached(mint, result)
                health.record_success()
                return result
            else:
                health.record_failure()

        # All sources failed
        return PriceResult(price=0.0, source="none")

    def get_health_status(self) -> Dict[str, dict]:
        """Get health status of all sources."""
        return {
            name: {
                "healthy": health.is_healthy,
                "success_count": health.success_count,
                "failure_count": health.failure_count,
                "consecutive_failures": health.consecutive_failures,
                "disabled_until": health.disabled_until.isoformat() if health.disabled_until else None,
            }
            for name, health in self._source_health.items()
        }


# Global instance
_price_fetcher: Optional[ResilientPriceFetcher] = None


def get_price_fetcher() -> ResilientPriceFetcher:
    """Get or create the global price fetcher."""
    global _price_fetcher
    if _price_fetcher is None:
        _price_fetcher = ResilientPriceFetcher()
    return _price_fetcher


async def get_token_price(mint: str) -> float:
    """Convenience function to get a token price."""
    fetcher = get_price_fetcher()
    result = await fetcher.get_price(mint)
    return result.price
