"""
Free Price API - Lightweight price fetching with fallback chains.
Prioritizes free APIs: DexScreener, GeckoTerminal, Jupiter.
No API keys required for basic functionality.
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime, timezone
from core.cache.memory_cache import LRUCache

logger = logging.getLogger(__name__)

# Shared cache for all price data (5 minute TTL for prices)
_price_cache = LRUCache(maxsize=5000, ttl=300)


@dataclass
class TokenPrice:
    """Token price data."""
    address: str
    symbol: str
    name: str
    price_usd: float
    price_sol: Optional[float] = None
    volume_24h: Optional[float] = None
    liquidity: Optional[float] = None
    price_change_24h: Optional[float] = None
    source: str = "unknown"
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class FreePriceAPI:
    """
    Free price data aggregator with fallback chain.
    
    Priority:
    1. DexScreener (free, no key) - Best for Solana tokens
    2. GeckoTerminal (free, no key) - Good coverage
    3. Jupiter Price API (free, no key) - Solana native
    """
    
    DEXSCREENER_API = "https://api.dexscreener.com/latest/dex"
    GECKOTERMINAL_API = "https://api.geckoterminal.com/api/v2"
    JUPITER_PRICE_API = "https://price.jup.ag/v6"
    
    # SOL mint for price conversions
    SOL_MINT = "So11111111111111111111111111111111111111112"
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._sol_price: Optional[float] = None
        self._sol_price_time: Optional[datetime] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=10)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_price(self, token_address: str) -> Optional[TokenPrice]:
        """
        Get token price with fallback chain.
        Tries DexScreener -> GeckoTerminal -> Jupiter.
        """
        # Check cache first
        cached = _price_cache.get(f"price:{token_address}")
        if cached:
            return cached
        
        # Try each source in order
        price = await self._try_dexscreener(token_address)
        if not price:
            price = await self._try_geckoterminal(token_address)
        if not price:
            price = await self._try_jupiter(token_address)
        
        if price:
            _price_cache.set(f"price:{token_address}", price)
        
        return price
    
    async def get_sol_price(self) -> float:
        """Get SOL price in USD (cached for 1 minute)."""
        now = datetime.now(timezone.utc)
        if self._sol_price and self._sol_price_time:
            age = (now - self._sol_price_time).total_seconds()
            if age < 60:
                return self._sol_price
        
        price = await self.get_price(self.SOL_MINT)
        if price:
            self._sol_price = price.price_usd
            self._sol_price_time = now
            return self._sol_price
        
        return 0.0
    
    async def get_multiple_prices(self, addresses: List[str]) -> Dict[str, TokenPrice]:
        """Get prices for multiple tokens concurrently."""
        tasks = [self.get_price(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        prices = {}
        for addr, result in zip(addresses, results):
            if isinstance(result, TokenPrice):
                prices[addr] = result
        
        return prices
    
    async def _try_dexscreener(self, token_address: str) -> Optional[TokenPrice]:
        """Try DexScreener API (free, no key required)."""
        try:
            session = await self._get_session()
            url = f"{self.DEXSCREENER_API}/tokens/{token_address}"
            
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                pairs = data.get("pairs", [])
                
                if not pairs:
                    return None
                
                # Use the pair with highest liquidity
                best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))
                
                base_token = best_pair.get("baseToken", {})
                
                return TokenPrice(
                    address=token_address,
                    symbol=base_token.get("symbol", ""),
                    name=base_token.get("name", ""),
                    price_usd=float(best_pair.get("priceUsd", 0) or 0),
                    volume_24h=float(best_pair.get("volume", {}).get("h24", 0) or 0),
                    liquidity=float(best_pair.get("liquidity", {}).get("usd", 0) or 0),
                    price_change_24h=float(best_pair.get("priceChange", {}).get("h24", 0) or 0),
                    source="dexscreener"
                )
        except Exception as e:
            logger.debug(f"DexScreener failed for {token_address}: {e}")
            return None
    
    async def _try_geckoterminal(self, token_address: str) -> Optional[TokenPrice]:
        """Try GeckoTerminal API (free, no key required)."""
        try:
            session = await self._get_session()
            url = f"{self.GECKOTERMINAL_API}/networks/solana/tokens/{token_address}"
            
            headers = {"Accept": "application/json"}
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                token_data = data.get("data", {}).get("attributes", {})
                
                if not token_data:
                    return None
                
                return TokenPrice(
                    address=token_address,
                    symbol=token_data.get("symbol", ""),
                    name=token_data.get("name", ""),
                    price_usd=float(token_data.get("price_usd", 0) or 0),
                    volume_24h=float(token_data.get("volume_usd", {}).get("h24", 0) or 0),
                    source="geckoterminal"
                )
        except Exception as e:
            logger.debug(f"GeckoTerminal failed for {token_address}: {e}")
            return None
    
    async def _try_jupiter(self, token_address: str) -> Optional[TokenPrice]:
        """Try Jupiter Price API (free, no key required)."""
        try:
            session = await self._get_session()
            url = f"{self.JUPITER_PRICE_API}/price?ids={token_address}"
            
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                price_data = data.get("data", {}).get(token_address)
                
                if not price_data:
                    return None
                
                return TokenPrice(
                    address=token_address,
                    symbol=price_data.get("mintSymbol", ""),
                    name=price_data.get("mintSymbol", ""),
                    price_usd=float(price_data.get("price", 0) or 0),
                    source="jupiter"
                )
        except Exception as e:
            logger.debug(f"Jupiter failed for {token_address}: {e}")
            return None


# Singleton instance
_instance: Optional[FreePriceAPI] = None


def get_free_price_api() -> FreePriceAPI:
    """Get singleton FreePriceAPI instance."""
    global _instance
    if _instance is None:
        _instance = FreePriceAPI()
    return _instance


async def get_token_price(token_address: str) -> Optional[TokenPrice]:
    """Convenience function to get token price."""
    api = get_free_price_api()
    return await api.get_price(token_address)


async def get_sol_price() -> float:
    """Convenience function to get SOL price."""
    api = get_free_price_api()
    return await api.get_sol_price()
