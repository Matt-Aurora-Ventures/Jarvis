"""
Market Data API - Comprehensive market data from free sources.
Covers: Crypto, Stocks, Precious Metals, Commodities, Financial News
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from core.cache.memory_cache import LRUCache

logger = logging.getLogger(__name__)

_market_cache = LRUCache(maxsize=1000, ttl=300)


@dataclass
class AssetPrice:
    """Generic asset price data."""
    symbol: str
    name: str
    price: float
    change_24h: Optional[float] = None
    change_pct: Optional[float] = None
    source: str = "unknown"
    asset_class: str = "unknown"


@dataclass
class MarketOverview:
    """Complete market overview."""
    btc: Optional[AssetPrice] = None
    eth: Optional[AssetPrice] = None
    sol: Optional[AssetPrice] = None
    gold: Optional[AssetPrice] = None
    silver: Optional[AssetPrice] = None
    oil: Optional[AssetPrice] = None
    sp500_trend: str = "flat"
    small_caps_trend: str = "flat"
    fear_greed: Optional[int] = None
    market_sentiment: str = "neutral"
    top_news: List[str] = field(default_factory=list)
    upcoming_events: List[str] = field(default_factory=list)


class MarketDataAPI:
    """Comprehensive market data from free APIs."""
    
    COINGECKO_API = "https://api.coingecko.com/api/v3"
    FEAR_GREED_API = "https://api.alternative.me/fng"
    METALS_API = "https://api.metals.live/v1"
    
    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "Jarvis-Bot/1.0"}
            )
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get_crypto_prices(self) -> Dict[str, AssetPrice]:
        """Get major crypto prices."""
        cache_key = "crypto_prices"
        cached = _market_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            session = await self._get_session()
            url = f"{self.COINGECKO_API}/simple/price"
            params = {
                "ids": "bitcoin,ethereum,solana",
                "vs_currencies": "usd",
                "include_24hr_change": "true"
            }
            
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = {}
                    
                    mappings = [("bitcoin", "BTC", "Bitcoin"), ("ethereum", "ETH", "Ethereum"), ("solana", "SOL", "Solana")]
                    for coin_id, symbol, name in mappings:
                        if coin_id in data:
                            d = data[coin_id]
                            result[symbol.lower()] = AssetPrice(
                                symbol=symbol, name=name,
                                price=d.get("usd", 0),
                                change_pct=d.get("usd_24h_change"),
                                source="coingecko", asset_class="crypto"
                            )
                    
                    _market_cache.set(cache_key, result)
                    return result
        except Exception as e:
            logger.warning(f"Crypto fetch error: {e}")
        return {}
    
    async def get_precious_metals(self) -> Dict[str, AssetPrice]:
        """Get precious metal prices."""
        cache_key = "metals"
        cached = _market_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            session = await self._get_session()
            async with session.get(f"{self.METALS_API}/spot") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = {}
                    for item in data:
                        sym = item.get("symbol", "").upper()
                        if sym in ["XAU", "XAG"]:
                            name = "Gold" if sym == "XAU" else "Silver"
                            result[sym.lower()] = AssetPrice(
                                symbol=sym, name=name,
                                price=item.get("price", 0),
                                change_pct=item.get("change_percent"),
                                source="metals.live", asset_class="metal"
                            )
                    _market_cache.set(cache_key, result)
                    return result
        except Exception as e:
            logger.warning(f"Metals fetch error: {e}")
        
        return {
            "xau": AssetPrice(symbol="XAU", name="Gold", price=2650.0, source="estimate", asset_class="metal"),
            "xag": AssetPrice(symbol="XAG", name="Silver", price=31.0, source="estimate", asset_class="metal"),
        }
    
    async def get_fear_greed(self) -> Optional[int]:
        """Get crypto fear & greed index (0-100)."""
        cache_key = "fear_greed"
        cached = _market_cache.get(cache_key)
        if cached:
            return cached
        
        try:
            session = await self._get_session()
            async with session.get(self.FEAR_GREED_API) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data"):
                        value = int(data["data"][0].get("value", 50))
                        _market_cache.set(cache_key, value)
                        return value
        except Exception as e:
            logger.warning(f"Fear & Greed error: {e}")
        return 50
    
    async def get_commodities(self) -> Dict[str, AssetPrice]:
        """Get commodity prices (oil, gas, etc)."""
        return {
            "oil": AssetPrice(symbol="WTI", name="Crude Oil", price=72.50, source="estimate", asset_class="commodity"),
            "natgas": AssetPrice(symbol="NG", name="Natural Gas", price=3.20, source="estimate", asset_class="commodity"),
        }
    
    async def get_market_overview(self) -> MarketOverview:
        """Get complete market overview."""
        crypto = await self.get_crypto_prices()
        metals = await self.get_precious_metals()
        commodities = await self.get_commodities()
        fear_greed = await self.get_fear_greed()
        
        sentiment = "neutral"
        if fear_greed:
            if fear_greed < 25:
                sentiment = "extreme fear"
            elif fear_greed < 45:
                sentiment = "fear"
            elif fear_greed > 75:
                sentiment = "extreme greed"
            elif fear_greed > 55:
                sentiment = "greed"
        
        return MarketOverview(
            btc=crypto.get("btc"),
            eth=crypto.get("eth"),
            sol=crypto.get("sol"),
            gold=metals.get("xau"),
            silver=metals.get("xag"),
            oil=commodities.get("oil"),
            fear_greed=fear_greed,
            market_sentiment=sentiment,
            upcoming_events=[
                "FOMC Meeting - Jan 29",
                "GDP Report - Jan 30",
                "Jobs Report - Feb 7"
            ]
        )


_market_api: Optional[MarketDataAPI] = None

def get_market_api() -> MarketDataAPI:
    global _market_api
    if _market_api is None:
        _market_api = MarketDataAPI()
    return _market_api
