"""
Free Trending Tokens API - No API keys required.
Uses DexScreener and GeckoTerminal free endpoints.
Supports multiple chains: Solana, Ethereum, Base, BSC, Arbitrum
"""

import asyncio
import aiohttp
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from core.cache.memory_cache import LRUCache
from core.utils.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)

# Cache trending data for 5 minutes
_trending_cache = LRUCache(maxsize=100, ttl=300)

# Supported chains for multi-chain trending
SUPPORTED_CHAINS = ["solana", "ethereum", "base", "bsc", "arbitrum"]

# Chain name mappings for display
CHAIN_DISPLAY_NAMES = {
    "solana": "Solana",
    "ethereum": "ETH",
    "base": "Base",
    "bsc": "BSC",
    "arbitrum": "Arbitrum"
}


@dataclass
class TrendingToken:
    """Trending token data."""
    address: str
    symbol: str
    name: str
    price_usd: float
    volume_24h: float
    liquidity: float
    price_change_24h: float
    chain: str = "solana"
    source: str = "unknown"
    rank: int = 0


class FreeTrendingAPI:
    """
    Free trending tokens aggregator.
    
    Sources (all free, no API key):
    1. DexScreener Boosted - Shows promoted tokens
    2. DexScreener Gainers - Top price gainers
    3. GeckoTerminal Trending - Network trending
    """
    
    DEXSCREENER_API = "https://api.dexscreener.com"
    GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_trending(self, limit: int = 10) -> List[TrendingToken]:
        """Get trending tokens with fallback."""
        # Check cache
        cached = _trending_cache.get("trending:multi")
        if cached:
            return cached[:limit]

        # Prefer GeckoTerminal as it has full symbol/name data
        tokens = await self._get_geckoterminal_trending()

        # Fallback to DexScreener if GeckoTerminal fails
        if not tokens:
            tokens = await self._get_dexscreener_gainers()
            # Filter out tokens without symbols
            tokens = [t for t in tokens if t.symbol]

        if tokens:
            _trending_cache.set("trending:multi", tokens)

        return tokens[:limit]
    
    async def get_gainers(self, limit: int = 10) -> List[TrendingToken]:
        """Get top price gainers."""
        cached = _trending_cache.get("gainers:multi")
        if cached:
            return cached[:limit]

        # Prefer GeckoTerminal as it has full symbol/name/price data
        tokens = await self._get_geckoterminal_trending()

        # Fallback to DexScreener
        if not tokens:
            tokens = await self._get_dexscreener_gainers()
            tokens = [t for t in tokens if t.symbol]

        if tokens:
            _trending_cache.set("gainers:multi", tokens)
        
        return tokens[:limit]
    
    async def get_new_pairs(self, limit: int = 10) -> List[TrendingToken]:
        """Get newly created trading pairs."""
        cached = _trending_cache.get("new_pairs:solana")
        if cached:
            return cached[:limit]
        
        tokens = await self._get_dexscreener_new_pairs()
        
        if tokens:
            _trending_cache.set("new_pairs:solana", tokens)
        
        return tokens[:limit]
    
    async def _get_dexscreener_trending(self) -> List[TrendingToken]:
        """Get DexScreener boosted/trending tokens."""
        try:
            await get_rate_limiter().wait_and_acquire("dexscreener")
            session = await self._get_session()
            # Get token profiles which shows popular tokens
            url = f"{self.DEXSCREENER_API}/token-profiles/latest/v1"
            
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                
                data = await resp.json()
                tokens = []

                for i, item in enumerate(data[:30]):
                    chain_id = item.get("chainId", "unknown")
                    if chain_id not in SUPPORTED_CHAINS:
                        continue

                    tokens.append(TrendingToken(
                        address=item.get("tokenAddress", ""),
                        symbol=item.get("symbol", ""),
                        name=item.get("name", ""),
                        price_usd=0,  # Not in this endpoint
                        volume_24h=0,
                        liquidity=0,
                        price_change_24h=0,
                        chain=chain_id,
                        source="dexscreener",
                        rank=len(tokens) + 1
                    ))

                    if len(tokens) >= 20:
                        break

                return tokens
        except Exception as e:
            logger.debug(f"DexScreener trending failed: {e}")
            return []
    
    async def _get_dexscreener_gainers(self) -> List[TrendingToken]:
        """Get DexScreener top gainers across multiple chains."""
        try:
            await get_rate_limiter().wait_and_acquire("dexscreener")
            session = await self._get_session()
            # Get boosted tokens which are more likely to be trending
            url = f"{self.DEXSCREENER_API}/token-boosts/top/v1"

            async with session.get(url) as resp:
                if resp.status != 200:
                    return []

                data = await resp.json()

                # Filter to supported chains and sort by any available metric
                multi_chain_tokens = [p for p in data if p.get("chainId") in SUPPORTED_CHAINS]
                multi_chain_tokens = multi_chain_tokens[:30]  # Limit to process
                
                tokens = []
                seen = set()

                for item in multi_chain_tokens:
                    addr = item.get("tokenAddress", "")
                    chain_id = item.get("chainId", "unknown")

                    if addr in seen:
                        continue
                    seen.add(addr)

                    tokens.append(TrendingToken(
                        address=addr,
                        symbol=item.get("symbol", ""),
                        name=item.get("name", ""),
                        price_usd=0,  # Not available in this endpoint
                        volume_24h=0,
                        liquidity=0,
                        price_change_24h=0,
                        chain=chain_id,
                        source="dexscreener",
                        rank=len(tokens) + 1
                    ))

                    if len(tokens) >= 20:
                        break

                return tokens
        except Exception as e:
            logger.debug(f"DexScreener gainers failed: {e}")
            return []
    
    async def _get_dexscreener_new_pairs(self) -> List[TrendingToken]:
        """Get newly created Solana pairs."""
        try:
            await get_rate_limiter().wait_and_acquire("dexscreener")
            session = await self._get_session()
            url = f"{self.DEXSCREENER_API}/latest/dex/pairs/solana"
            
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                
                data = await resp.json()
                pairs = data.get("pairs", [])
                
                tokens = []
                seen = set()
                
                for pair in pairs[:20]:
                    base = pair.get("baseToken", {})
                    addr = base.get("address", "")
                    
                    if addr in seen:
                        continue
                    seen.add(addr)
                    
                    tokens.append(TrendingToken(
                        address=addr,
                        symbol=base.get("symbol", ""),
                        name=base.get("name", ""),
                        price_usd=float(pair.get("priceUsd", 0) or 0),
                        volume_24h=float(pair.get("volume", {}).get("h24", 0) or 0),
                        liquidity=float(pair.get("liquidity", {}).get("usd", 0) or 0),
                        price_change_24h=float(pair.get("priceChange", {}).get("h24", 0) or 0),
                        source="dexscreener",
                        rank=len(tokens) + 1
                    ))
                
                return tokens
        except Exception as e:
            logger.debug(f"DexScreener new pairs failed: {e}")
            return []
    
    async def _get_geckoterminal_trending(self) -> List[TrendingToken]:
        """Get GeckoTerminal trending tokens across multiple chains."""
        # GeckoTerminal network names for supported chains
        gecko_networks = {
            "solana": "solana",
            "ethereum": "eth",
            "base": "base",
            "bsc": "bsc",
            "arbitrum": "arbitrum"
        }

        all_tokens = []
        seen = set()

        # Query each chain (prioritize Solana but include others)
        for chain, network in list(gecko_networks.items())[:3]:  # Top 3 chains
            try:
                await get_rate_limiter().wait_and_acquire("geckoterminal")
                session = await self._get_session()
                url = f"{self.GECKOTERMINAL_API}/networks/{network}/trending_pools"

                headers = {"Accept": "application/json"}
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        continue

                    data = await resp.json()
                    pools = data.get("data", [])

                    for pool in pools[:8]:  # Top 8 per chain
                        attrs = pool.get("attributes", {})
                        # Get base token
                        name = attrs.get("name", "").split(" / ")[0] if attrs.get("name") else ""
                        token_id = pool.get("relationships", {}).get("base_token", {}).get("data", {}).get("id", "")
                        addr = token_id.replace(f"{network}_", "")

                        if addr in seen or not addr:
                            continue
                        seen.add(addr)

                        all_tokens.append(TrendingToken(
                            address=addr,
                            symbol=name,
                            name=name,
                            price_usd=float(attrs.get("base_token_price_usd", 0) or 0),
                            volume_24h=float(attrs.get("volume_usd", {}).get("h24", 0) or 0),
                            liquidity=float(attrs.get("reserve_in_usd", 0) or 0),
                            price_change_24h=float(attrs.get("price_change_percentage", {}).get("h24", 0) or 0),
                            chain=chain,
                            source="geckoterminal",
                            rank=len(all_tokens) + 1
                        ))
            except Exception as e:
                logger.debug(f"GeckoTerminal {chain} failed: {e}")
                continue

        return all_tokens


# Singleton
_instance: Optional[FreeTrendingAPI] = None


def get_free_trending_api() -> FreeTrendingAPI:
    """Get singleton instance."""
    global _instance
    if _instance is None:
        _instance = FreeTrendingAPI()
    return _instance


async def get_trending_tokens(limit: int = 10) -> List[TrendingToken]:
    """Convenience function for trending tokens."""
    api = get_free_trending_api()
    return await api.get_trending(limit)


async def get_top_gainers(limit: int = 10) -> List[TrendingToken]:
    """Convenience function for top gainers."""
    api = get_free_trending_api()
    return await api.get_gainers(limit)
