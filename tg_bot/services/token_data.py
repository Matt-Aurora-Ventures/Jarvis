"""
Token Data Service.

Aggregates token data from multiple sources:
- Birdeye API
- DexScreener API
- Jupiter API (fallback)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)

# Common Solana token addresses
KNOWN_TOKENS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
    "SAMO": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
    "STEP": "StepAscQoEioFxxWGnh2sLBDFp9d8rvKz2Yp39iDpyT",
}


@dataclass
class TokenData:
    """Token market data."""

    address: str
    symbol: str
    price_usd: float
    price_change_1h: float
    price_change_24h: float
    volume_24h: float
    liquidity: float
    holder_count: int
    top_holders_pct: float
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "address": self.address,
            "symbol": self.symbol,
            "price_usd": self.price_usd,
            "price_change_1h": self.price_change_1h,
            "price_change_24h": self.price_change_24h,
            "volume_24h": self.volume_24h,
            "liquidity": self.liquidity,
            "holder_count": self.holder_count,
            "top_holders_pct": self.top_holders_pct,
            "last_updated": self.last_updated.isoformat(),
        }


class TokenDataService:
    """Service for fetching token data from multiple sources."""

    def __init__(
        self,
        birdeye_key: Optional[str] = None,
        cache_ttl: int = 60,
    ):
        self.birdeye_key = birdeye_key
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, tuple] = {}  # {token: (data, timestamp)}
        self._session: Optional[aiohttp.ClientSession] = None
        self._healthy = True

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """Close the session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._healthy

    def _resolve_token(self, token: str) -> str:
        """Resolve token symbol to address."""
        token_upper = token.upper()
        if token_upper in KNOWN_TOKENS:
            return KNOWN_TOKENS[token_upper]
        # Assume it's already an address
        return token

    def _get_cached(self, token: str) -> Optional[TokenData]:
        """Get cached token data if still valid."""
        if token in self._cache:
            data, timestamp = self._cache[token]
            if time.time() - timestamp < self.cache_ttl:
                return data
        return None

    def _set_cached(self, token: str, data: TokenData):
        """Cache token data."""
        self._cache[token] = (data, time.time())

    async def get_token_data(self, token: str) -> Optional[TokenData]:
        """
        Get token data from available sources.

        Tries in order: Birdeye -> DexScreener -> Mock
        """
        # Check cache first
        cached = self._get_cached(token)
        if cached:
            return cached

        address = self._resolve_token(token)
        symbol = token.upper() if token.upper() in KNOWN_TOKENS else token[:6]

        # Try Birdeye first
        if self.birdeye_key:
            data = await self._fetch_birdeye(address, symbol)
            if data:
                self._set_cached(token, data)
                return data

        # Try DexScreener
        data = await self._fetch_dexscreener(address, symbol)
        if data:
            self._set_cached(token, data)
            return data

        # Return mock data for development
        data = self._get_mock_data(address, symbol)
        self._set_cached(token, data)
        return data

    async def _fetch_birdeye(self, address: str, symbol: str) -> Optional[TokenData]:
        """Fetch data from Birdeye API."""
        try:
            session = await self._get_session()
            headers = {"X-API-KEY": self.birdeye_key}

            url = f"https://public-api.birdeye.so/defi/token_overview?address={address}"
            async with session.get(url, headers=headers, timeout=10) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                if not data.get("success") or not data.get("data"):
                    return None

                d = data["data"]
                return TokenData(
                    address=address,
                    symbol=symbol,
                    price_usd=float(d.get("price", 0)),
                    price_change_1h=float(d.get("priceChange1hPercent", 0)),
                    price_change_24h=float(d.get("priceChange24hPercent", 0)),
                    volume_24h=float(d.get("v24hUSD", 0)),
                    liquidity=float(d.get("liquidity", 0)),
                    holder_count=int(d.get("holder", 0)),
                    top_holders_pct=float(d.get("top10HolderPercent", 0)) * 100,
                )

        except Exception as e:
            logger.warning(f"Birdeye fetch error: {e}")
            return None

    async def _fetch_dexscreener(self, address: str, symbol: str) -> Optional[TokenData]:
        """Fetch data from DexScreener API."""
        try:
            session = await self._get_session()
            url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"

            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return None

                data = await resp.json()
                pairs = data.get("pairs", [])
                if not pairs:
                    return None

                # Use the pair with highest liquidity
                pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0)))

                return TokenData(
                    address=address,
                    symbol=symbol,
                    price_usd=float(pair.get("priceUsd", 0)),
                    price_change_1h=float(pair.get("priceChange", {}).get("h1", 0)),
                    price_change_24h=float(pair.get("priceChange", {}).get("h24", 0)),
                    volume_24h=float(pair.get("volume", {}).get("h24", 0)),
                    liquidity=float(pair.get("liquidity", {}).get("usd", 0)),
                    holder_count=0,  # DexScreener doesn't provide this
                    top_holders_pct=0,
                )

        except Exception as e:
            logger.warning(f"DexScreener fetch error: {e}")
            return None

    def _get_mock_data(self, address: str, symbol: str) -> TokenData:
        """Generate mock data for development."""
        import hashlib

        # Deterministic "random" based on symbol
        h = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)

        return TokenData(
            address=address,
            symbol=symbol,
            price_usd=round((h % 10000) / 100, 4),
            price_change_1h=round(((h % 200) - 100) / 10, 2),
            price_change_24h=round(((h % 400) - 200) / 10, 2),
            volume_24h=round((h % 10000000), 0),
            liquidity=round((h % 5000000), 0),
            holder_count=h % 100000,
            top_holders_pct=round((h % 50) + 10, 2),
        )

    async def get_trending(self, limit: int = 5) -> List[TokenData]:
        """Get trending tokens on Solana."""
        # For now, return top known tokens with data
        trending_symbols = ["SOL", "BONK", "WIF", "JUP", "PYTH"][:limit]
        results = []

        for symbol in trending_symbols:
            data = await self.get_token_data(symbol)
            if data:
                results.append(data)

        # Sort by 24h volume
        results.sort(key=lambda x: x.volume_24h, reverse=True)
        return results[:limit]

    async def get_blue_chips(self, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Get established Solana blue chip tokens sorted by 24h volume.
        Returns full token data including market cap and addresses.
        """
        # Expanded list of established Solana blue chips
        BLUE_CHIP_TOKENS = [
            ("SOL", "So11111111111111111111111111111111111111112"),
            ("JUP", "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN"),
            ("RAY", "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"),
            ("BONK", "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),
            ("WIF", "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"),
            ("PYTH", "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3"),
            ("JTO", "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL"),
            ("ORCA", "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE"),
            ("MNGO", "MangoCzJ36AjZyKwVj3VnYU4GTonjfVEnJmvvWaxLac"),
            ("FIDA", "EchesyfXePKdLtoiZSL8pBe8Myagyy8ZRqsACNCFGnvp"),
            ("SAMO", "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"),
            ("STEP", "StepAscQoEioFxxWGnh2sLBDFp9d8rvKz2Yp39iDpyT"),
            ("SRM", "SRMuApVNdxXokk5GT7XD5cUUgXMBCoAz2LHeuAoKWRt"),
            ("MSOL", "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So"),
            ("STSOL", "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj"),
        ]

        results = []
        
        # Try to fetch real data from Birdeye trending endpoint first
        if self.birdeye_key:
            try:
                session = await self._get_session()
                headers = {"X-API-KEY": self.birdeye_key}
                
                # Fetch trending tokens by volume
                url = "https://public-api.birdeye.so/defi/token_trending?sort_by=volume24hUSD&sort_type=desc&offset=0&limit=30"
                async with session.get(url, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("success") and data.get("data", {}).get("items"):
                            for item in data["data"]["items"][:limit]:
                                results.append({
                                    "symbol": item.get("symbol", "???"),
                                    "address": item.get("address", ""),
                                    "price": float(item.get("price", 0)),
                                    "change_24h": float(item.get("priceChange24hPercent", 0)),
                                    "volume_24h": float(item.get("v24hUSD", 0)),
                                    "market_cap": float(item.get("mc", 0)),
                                    "liquidity": float(item.get("liquidity", 0)),
                                    "holder_count": int(item.get("holder", 0)),
                                })
            except Exception as e:
                logger.warning(f"Birdeye trending fetch error: {e}")

        # If we didn't get enough from trending, supplement with known blue chips
        if len(results) < limit:
            existing_addresses = {r["address"] for r in results}
            
            for symbol, address in BLUE_CHIP_TOKENS:
                if address in existing_addresses:
                    continue
                    
                data = await self.get_token_data(symbol)
                if data:
                    results.append({
                        "symbol": data.symbol,
                        "address": data.address,
                        "price": data.price_usd,
                        "change_24h": data.price_change_24h,
                        "volume_24h": data.volume_24h,
                        "market_cap": data.volume_24h * 10,  # Estimate if not available
                        "liquidity": data.liquidity,
                        "holder_count": data.holder_count,
                    })
                    
                if len(results) >= limit:
                    break

        # Sort by 24h volume (highest first)
        results.sort(key=lambda x: x.get("volume_24h", 0), reverse=True)
        return results[:limit]
