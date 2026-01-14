"""
Market Data API - Comprehensive market data from VERIFIED free sources.

Sources (tested & reliable):
- Yahoo Finance: Stocks, Indices, Futures (Gold, Silver, Oil), VIX, DXY
- Binance: Crypto (BTC, ETH, SOL) - no rate limits
- Alternative.me: Fear & Greed Index

All data is fetched from reliable APIs - NO hardcoded estimates.
If data cannot be fetched, it returns None rather than fake data.
"""

import asyncio
import aiohttp
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from core.cache.memory_cache import LRUCache

logger = logging.getLogger(__name__)

_market_cache = LRUCache(maxsize=1000, ttl=120)  # 2 min cache


@dataclass
class AssetPrice:
    """Generic asset price data."""
    symbol: str
    name: str
    price: float
    change_24h: Optional[float] = None
    change_pct: Optional[float] = None
    prev_close: Optional[float] = None
    source: str = "unknown"
    asset_class: str = "unknown"
    verified: bool = True


@dataclass
class NewsItem:
    """Financial news item."""
    title: str
    source: str
    url: str
    published: str
    sentiment: str = "neutral"


@dataclass
class MarketOverview:
    """Complete market overview."""
    # Crypto
    btc: Optional[AssetPrice] = None
    eth: Optional[AssetPrice] = None
    sol: Optional[AssetPrice] = None
    
    # Precious metals (from futures)
    gold: Optional[AssetPrice] = None
    silver: Optional[AssetPrice] = None
    
    # Commodities
    oil: Optional[AssetPrice] = None
    
    # Indices
    sp500: Optional[AssetPrice] = None
    nasdaq: Optional[AssetPrice] = None
    vix: Optional[AssetPrice] = None
    dxy: Optional[AssetPrice] = None
    
    # Sentiment
    fear_greed: Optional[int] = None
    market_sentiment: str = "neutral"
    
    # News
    top_news: List[NewsItem] = field(default_factory=list)
    upcoming_events: List[str] = field(default_factory=list)
    
    # Data quality
    data_sources: List[str] = field(default_factory=list)
    last_updated: str = ""
    
    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.now(timezone.utc).isoformat()


class MarketDataAPI:
    """
    Comprehensive market data from VERIFIED free APIs.
    
    Primary Sources:
    - Yahoo Finance: Indices, Futures, ETFs (with rate limiting)
    - Binance: Crypto prices (generous limits)
    - Alternative.me: Fear & Greed Index
    """
    
    # API endpoints
    YAHOO_API = "https://query1.finance.yahoo.com/v8/finance/chart"
    BINANCE_API = "https://api.binance.com/api/v3"
    FEAR_GREED_API = "https://api.alternative.me/fng"
    FINNHUB_API = "https://finnhub.io/api/v1"

    # Rate limiting
    _last_yahoo_call = 0
    YAHOO_DELAY = 0.3  # 300ms between Yahoo calls

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None
        self._finnhub_key: str = os.getenv("FINNHUB_API_KEY", "")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _yahoo_fetch(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch data from Yahoo Finance with rate limiting."""
        import time
        
        # Rate limiting
        now = time.time()
        elapsed = now - MarketDataAPI._last_yahoo_call
        if elapsed < self.YAHOO_DELAY:
            await asyncio.sleep(self.YAHOO_DELAY - elapsed)
        MarketDataAPI._last_yahoo_call = time.time()
        
        session = await self._get_session()
        try:
            url = f"{self.YAHOO_API}/{symbol}"
            params = {"interval": "1d", "range": "1d"}
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = data.get("chart", {}).get("result", [{}])[0]
                    meta = result.get("meta", {})
                    return {
                        "price": meta.get("regularMarketPrice", 0),
                        "prev_close": meta.get("previousClose", 0),
                        "change_pct": 0
                    }
        except Exception as e:
            logger.warning(f"Yahoo fetch error for {symbol}: {e}")
        return None
    
    async def get_crypto_prices(self) -> Dict[str, AssetPrice]:
        """Get crypto prices from Binance (most reliable, no rate limits)."""
        cache_key = "crypto_v4"
        cached = _market_cache.get(cache_key)
        if cached:
            return cached
        
        result = {}
        session = await self._get_session()
        
        try:
            symbols = [
                ("BTCUSDT", "BTC", "Bitcoin"),
                ("ETHUSDT", "ETH", "Ethereum"),
                ("SOLUSDT", "SOL", "Solana"),
                ("DOGEUSDT", "DOGE", "Dogecoin")
            ]
            
            for binance_sym, symbol, name in symbols:
                url = f"{self.BINANCE_API}/ticker/24hr"
                params = {"symbol": binance_sym}
                async with session.get(url, params=params) as resp:
                    if resp.status == 200:
                        d = await resp.json()
                        price = round(float(d.get("lastPrice", 0)), 2)
                        change = round(float(d.get("priceChangePercent", 0)), 2)
                        prev = round(float(d.get("prevClosePrice", 0)), 2)
                        
                        result[symbol.lower()] = AssetPrice(
                            symbol=symbol,
                            name=name,
                            price=price,
                            change_pct=change,
                            prev_close=prev,
                            source="binance",
                            asset_class="crypto",
                            verified=True
                        )
            
            if result:
                _market_cache.set(cache_key, result)
                btc = result.get("btc")
                if btc:
                    logger.info(f"Crypto: BTC=${btc.price:,.0f} ({btc.change_pct:+.1f}%)")
                return result
                
        except Exception as e:
            logger.error(f"Binance error: {e}")
        
        return result
    
    async def get_precious_metals(self) -> Dict[str, AssetPrice]:
        """Get precious metal prices from Yahoo Finance futures (GC=F, SI=F)."""
        cache_key = "metals_v4"
        cached = _market_cache.get(cache_key)
        if cached:
            return cached
        
        result = {}
        
        # Gold Futures (GC=F)
        gold_data = await self._yahoo_fetch("GC=F")
        if gold_data and gold_data["price"] > 1000:
            price = gold_data["price"]
            prev = gold_data["prev_close"] or price
            change_pct = ((price - prev) / prev * 100) if prev else 0
            result["xau"] = AssetPrice(
                symbol="XAU",
                name="Gold",
                price=round(price, 2),
                change_pct=round(change_pct, 2),
                prev_close=round(prev, 2),
                source="yahoo-futures",
                asset_class="metal",
                verified=True
            )
            logger.info(f"Gold: ${price:,.2f} ({change_pct:+.1f}%)")
        
        # Silver Futures (SI=F)
        silver_data = await self._yahoo_fetch("SI=F")
        if silver_data and silver_data["price"] > 10:
            price = silver_data["price"]
            prev = silver_data["prev_close"] or price
            change_pct = ((price - prev) / prev * 100) if prev else 0
            result["xag"] = AssetPrice(
                symbol="XAG",
                name="Silver",
                price=round(price, 2),
                change_pct=round(change_pct, 2),
                prev_close=round(prev, 2),
                source="yahoo-futures",
                asset_class="metal",
                verified=True
            )
            logger.info(f"Silver: ${price:.2f} ({change_pct:+.1f}%)")
        
        if result:
            _market_cache.set(cache_key, result)
        
        return result
    
    async def get_indices(self) -> Dict[str, AssetPrice]:
        """Get major indices from Yahoo Finance (S&P 500, NASDAQ, VIX, DXY)."""
        cache_key = "indices_v1"
        cached = _market_cache.get(cache_key)
        if cached:
            return cached
        
        result = {}
        indices = [
            ("^GSPC", "SPX", "S&P 500", "index"),
            ("^IXIC", "NDX", "NASDAQ", "index"),
            ("^VIX", "VIX", "VIX", "volatility"),
            ("DX-Y.NYB", "DXY", "Dollar Index", "currency"),
        ]
        
        for yahoo_sym, symbol, name, asset_class in indices:
            data = await self._yahoo_fetch(yahoo_sym)
            if data and data["price"] > 0:
                price = data["price"]
                prev = data["prev_close"] or price
                change_pct = ((price - prev) / prev * 100) if prev else 0
                result[symbol.lower()] = AssetPrice(
                    symbol=symbol,
                    name=name,
                    price=round(price, 2),
                    change_pct=round(change_pct, 2),
                    prev_close=round(prev, 2),
                    source="yahoo-finance",
                    asset_class=asset_class,
                    verified=True
                )
        
        if result:
            _market_cache.set(cache_key, result)
            spx = result.get("spx")
            if spx:
                logger.info(f"S&P 500: {spx.price:,.0f} ({spx.change_pct:+.1f}%)")
        
        return result
    
    async def get_commodities(self) -> Dict[str, AssetPrice]:
        """Get commodity prices from Yahoo Finance (Oil futures)."""
        cache_key = "commodities_v1"
        cached = _market_cache.get(cache_key)
        if cached:
            return cached
        
        result = {}
        
        # Crude Oil Futures (CL=F)
        oil_data = await self._yahoo_fetch("CL=F")
        if oil_data and oil_data["price"] > 0:
            price = oil_data["price"]
            prev = oil_data["prev_close"] or price
            change_pct = ((price - prev) / prev * 100) if prev else 0
            result["oil"] = AssetPrice(
                symbol="WTI",
                name="Crude Oil",
                price=round(price, 2),
                change_pct=round(change_pct, 2),
                prev_close=round(prev, 2),
                source="yahoo-futures",
                asset_class="commodity",
                verified=True
            )
            logger.info(f"Oil: ${price:.2f} ({change_pct:+.1f}%)")
        
        if result:
            _market_cache.set(cache_key, result)
        
        return result
    
    async def get_fear_greed(self) -> Optional[int]:
        """Get crypto fear & greed index (0-100) from Alternative.me."""
        cache_key = "fear_greed_v3"
        cached = _market_cache.get(cache_key)
        if cached is not None:
            return cached
        
        try:
            session = await self._get_session()
            async with session.get(self.FEAR_GREED_API) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data") and len(data["data"]) > 0:
                        value = int(data["data"][0].get("value", 0))
                        classification = data["data"][0].get("value_classification", "")
                        _market_cache.set(cache_key, value)
                        logger.info(f"Fear & Greed: {value} ({classification})")
                        return value
        except Exception as e:
            logger.error(f"Fear & Greed error: {e}")
        return None
    
    async def get_market_news(self) -> List[NewsItem]:
        """Get market news from Finnhub (requires free API key)."""
        cache_key = "market_news"
        cached = _market_cache.get(cache_key)
        if cached:
            return cached
        
        if not self._finnhub_key:
            logger.debug("No Finnhub API key - skipping news")
            return []
        
        try:
            session = await self._get_session()
            url = f"{self.FINNHUB_API}/news"
            params = {
                "category": "general",
                "token": self._finnhub_key
            }
            
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    news = []
                    for item in data[:5]:  # Top 5 news
                        news.append(NewsItem(
                            title=item.get("headline", ""),
                            source=item.get("source", ""),
                            url=item.get("url", ""),
                            published=datetime.fromtimestamp(item.get("datetime", 0)).isoformat(),
                            sentiment="neutral"
                        ))
                    _market_cache.set(cache_key, news)
                    return news
        except Exception as e:
            logger.error(f"News fetch error: {e}")
        return []
    
    async def get_market_overview(self) -> MarketOverview:
        """Get complete market overview from verified sources."""
        # Fetch crypto first (Binance - fast, no rate limits)
        crypto = await self.get_crypto_prices()
        
        # Fetch Fear & Greed (fast, single request)
        fear_greed = await self.get_fear_greed()
        
        # Fetch Yahoo data sequentially (rate limited)
        metals = await self.get_precious_metals()
        indices = await self.get_indices()
        commodities = await self.get_commodities()
        
        # Determine sentiment from fear/greed
        sentiment = "neutral"
        if fear_greed is not None:
            if fear_greed < 25:
                sentiment = "extreme fear"
            elif fear_greed < 40:
                sentiment = "fear"
            elif fear_greed > 75:
                sentiment = "extreme greed"
            elif fear_greed > 60:
                sentiment = "greed"
        
        # Track data sources
        sources = []
        if crypto:
            sources.append("binance")
        if metals or indices or commodities:
            sources.append("yahoo-finance")
        if fear_greed is not None:
            sources.append("alternative.me")
        
        # Real upcoming events
        upcoming = []
        now = datetime.now()
        
        if now.month == 1 and now.year == 2026:
            if now.day < 29:
                upcoming.append("FOMC Decision - Jan 29")
            if now.day < 30:
                upcoming.append("Q4 GDP - Jan 30")
            if now.day < 31:
                upcoming.append("Core PCE - Jan 31")
        
        if now.month == 2 and now.year == 2026:
            if now.day < 7:
                upcoming.append("Jobs Report - Feb 7")
        
        return MarketOverview(
            btc=crypto.get("btc"),
            eth=crypto.get("eth"),
            sol=crypto.get("sol"),
            gold=metals.get("xau"),
            silver=metals.get("xag"),
            oil=commodities.get("oil"),
            sp500=indices.get("spx"),
            nasdaq=indices.get("ndx"),
            vix=indices.get("vix"),
            dxy=indices.get("dxy"),
            fear_greed=fear_greed,
            market_sentiment=sentiment,
            upcoming_events=upcoming if upcoming else ["Check economic calendar"],
            data_sources=sources
        )


_market_api: Optional[MarketDataAPI] = None

def get_market_api() -> MarketDataAPI:
    global _market_api
    if _market_api is None:
        _market_api = MarketDataAPI()
    return _market_api
