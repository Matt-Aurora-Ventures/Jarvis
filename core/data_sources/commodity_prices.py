"""
Live Commodity Price Data Source

Provides real-time prices for precious metals and commodities.
This module was created after discovering Grok's training data had
outdated prices (e.g., Gold at $2,050 when actual price was ~$4,600).

Per GROK_COMPLIANCE_REGULATORY_GUIDE.md:
"Use live API feeds for critical price data"
"""

import asyncio
import aiohttp
from aiohttp import ClientTimeout
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import os

logger = logging.getLogger(__name__)


@dataclass
class CommodityPrice:
    """Represents a commodity price."""
    symbol: str
    name: str
    price_usd: float
    change_24h: float  # Percentage
    last_updated: datetime
    source: str

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'name': self.name,
            'price_usd': self.price_usd,
            'change_24h': self.change_24h,
            'last_updated': self.last_updated.isoformat(),
            'source': self.source
        }


class CommodityPriceClient:
    """
    Live commodity price client with multiple fallback sources.

    Supported commodities:
    - XAU (Gold)
    - XAG (Silver)
    - XPT (Platinum)
    - XPD (Palladium)
    - Crude Oil (WTI/Brent)
    - Natural Gas
    """

    # Free APIs for commodity data
    METALS_API = "https://metals-api.com/api/latest"  # Requires API key
    GOLD_API = "https://www.goldapi.io/api"  # Requires API key
    COINGECKO_API = "https://api.coingecko.com/api/v3"  # Free, has some commodities
    YAHOO_FINANCE_SYMBOLS = {
        'gold': 'GC=F',
        'silver': 'SI=F',
        'platinum': 'PL=F',
        'palladium': 'PA=F',
        'crude_oil': 'CL=F',
        'natural_gas': 'NG=F',
    }
    YAHOO_FINANCE_BY_SYMBOL = {
        'XAU': 'GC=F',
        'XAG': 'SI=F',
        'XPT': 'PL=F',
        'XPD': 'PA=F',
    }

    # Cache duration
    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self, metals_api_key: str = None, gold_api_key: str = None):
        """
        Initialize with optional API keys for premium data sources.

        Args:
            metals_api_key: API key for metals-api.com
            gold_api_key: API key for goldapi.io
        """
        self.metals_api_key = metals_api_key or os.environ.get('METALS_API_KEY')
        self.gold_api_key = gold_api_key or os.environ.get('GOLD_API_KEY')
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, CommodityPrice] = {}
        self._cache_time: Dict[str, datetime] = {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            # Configure timeouts: 60s total, 30s connect (for commodity price API calls)
            timeout = ClientTimeout(total=60, connect=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()

    def _is_cached(self, symbol: str) -> bool:
        """Check if a price is cached and still valid."""
        if symbol not in self._cache_time:
            return False
        cache_age = datetime.utcnow() - self._cache_time[symbol]
        return cache_age.total_seconds() < self.CACHE_TTL_SECONDS

    async def get_gold_price(self) -> Optional[CommodityPrice]:
        """Get current gold price."""
        return await self.get_price('XAU', 'Gold')

    async def get_silver_price(self) -> Optional[CommodityPrice]:
        """Get current silver price."""
        return await self.get_price('XAG', 'Silver')

    async def get_platinum_price(self) -> Optional[CommodityPrice]:
        """Get current platinum price."""
        return await self.get_price('XPT', 'Platinum')

    async def get_price(self, symbol: str, name: str) -> Optional[CommodityPrice]:
        """
        Get commodity price with caching and fallback sources.

        Args:
            symbol: Commodity symbol (XAU, XAG, XPT, etc.)
            name: Human-readable name

        Returns:
            CommodityPrice or None if all sources fail
        """
        # Check cache first
        if self._is_cached(symbol):
            return self._cache[symbol]

        # Try sources in order of preference
        price = None

        # 1. Try GoldAPI (if key available)
        if self.gold_api_key and symbol in ['XAU', 'XAG', 'XPT', 'XPD']:
            price = await self._fetch_goldapi(symbol, name)

        # 2. Try MetalsAPI (if key available)
        if price is None and self.metals_api_key:
            price = await self._fetch_metalsapi(symbol, name)

        # 3. Fallback to CoinGecko (commodities via search)
        if price is None:
            price = await self._fetch_coingecko_commodity(symbol, name)

        # 4. Final fallback: Yahoo Finance chart API
        if price is None:
            price = await self._fetch_yahoo_finance(symbol, name)

        # 5. Final fallback: no data available
        if price is None:
            logger.warning(f"All API sources failed for {symbol}, price data unavailable")

        # Cache successful result
        if price:
            self._cache[symbol] = price
            self._cache_time[symbol] = datetime.utcnow()

        return price

    async def _fetch_goldapi(self, symbol: str, name: str) -> Optional[CommodityPrice]:
        """Fetch from GoldAPI.io."""
        session = await self._get_session()

        try:
            headers = {'x-access-token': self.gold_api_key}
            async with session.get(
                f"{self.GOLD_API}/{symbol}/USD",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return CommodityPrice(
                        symbol=symbol,
                        name=name,
                        price_usd=data.get('price', 0),
                        change_24h=data.get('ch', 0),
                        last_updated=datetime.utcnow(),
                        source='goldapi.io'
                    )
        except Exception as e:
            logger.debug(f"GoldAPI failed for {symbol}: {e}")

        return None

    async def _fetch_metalsapi(self, symbol: str, name: str) -> Optional[CommodityPrice]:
        """Fetch from Metals-API.com."""
        session = await self._get_session()

        try:
            params = {'access_key': self.metals_api_key, 'base': 'USD', 'symbols': symbol}
            async with session.get(self.METALS_API, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('success') and symbol in data.get('rates', {}):
                        # MetalsAPI returns inverse rate (USD per unit)
                        rate = data['rates'][symbol]
                        price = 1 / rate if rate > 0 else 0
                        return CommodityPrice(
                            symbol=symbol,
                            name=name,
                            price_usd=price,
                            change_24h=0,  # MetalsAPI doesn't provide change
                            last_updated=datetime.utcnow(),
                            source='metals-api.com'
                        )
        except Exception as e:
            logger.debug(f"MetalsAPI failed for {symbol}: {e}")

        return None

    async def _fetch_coingecko_commodity(self, symbol: str, name: str) -> Optional[CommodityPrice]:
        """
        Fetch from CoinGecko - they have tokenized gold (PAXG, XAUT).
        Uses these as proxy for real gold prices.
        """
        session = await self._get_session()

        # Map to CoinGecko IDs for tokenized commodities
        coingecko_map = {
            'XAU': 'pax-gold',  # PAXG tracks gold price
            'XAG': None,  # No good silver token
        }

        cg_id = coingecko_map.get(symbol)
        if not cg_id:
            return None

        try:
            async with session.get(
                f"{self.COINGECKO_API}/simple/price",
                params={'ids': cg_id, 'vs_currencies': 'usd', 'include_24hr_change': 'true'}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if cg_id in data:
                        return CommodityPrice(
                            symbol=symbol,
                            name=name,
                            price_usd=data[cg_id].get('usd', 0),
                            change_24h=data[cg_id].get('usd_24h_change', 0),
                            last_updated=datetime.utcnow(),
                            source='coingecko (PAXG proxy)'
                        )
        except Exception as e:
            logger.debug(f"CoinGecko failed for {symbol}: {e}")

        return None

    async def _fetch_yahoo_finance(self, symbol: str, name: str) -> Optional[CommodityPrice]:
        """Fetch commodity price from Yahoo Finance chart API."""
        session = await self._get_session()

        ticker = self.YAHOO_FINANCE_BY_SYMBOL.get(symbol)
        if not ticker:
            return None

        try:
            urls = [
                f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}",
            ]
            params = {"interval": "1d", "range": "5d"}
            headers = {"User-Agent": "Mozilla/5.0 (compatible; JarvisBot/1.0)"}

            for url in urls:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    result = (data.get("chart", {}) or {}).get("result")
                    if not result:
                        continue
                    meta = result[0].get("meta", {})
                    price = meta.get("regularMarketPrice")
                    change_pct = meta.get("regularMarketChangePercent", 0.0)
                    if price is None:
                        continue
                    return CommodityPrice(
                        symbol=symbol,
                        name=name,
                        price_usd=float(price),
                        change_24h=float(change_pct or 0.0),
                        last_updated=datetime.utcnow(),
                        source="yahoo finance",
                    )
        except Exception as e:
            logger.debug(f"Yahoo Finance failed for {symbol}: {e}")
            return None

    async def get_all_precious_metals(self) -> Dict[str, CommodityPrice]:
        """Get all precious metals prices."""
        results = {}

        metals = [
            ('XAU', 'Gold'),
            ('XAG', 'Silver'),
            ('XPT', 'Platinum'),
            ('XPD', 'Palladium'),
        ]

        for symbol, name in metals:
            price = await self.get_price(symbol, name)
            if price:
                results[symbol] = price

        return results

    async def format_for_report(self) -> str:
        """Format precious metals for sentiment report."""
        metals = await self.get_all_precious_metals()

        if not metals:
            return "_Precious metals data unavailable - API keys not configured_"

        lines = ["*PRECIOUS METALS* (Live Data)"]

        for symbol, price in metals.items():
            trend = "+" if price.change_24h > 0 else ""
            lines.append(f"{price.name}: ${price.price_usd:,.2f} ({trend}{price.change_24h:.1f}%)")

        lines.append(f"_Source: {list(metals.values())[0].source if metals else 'N/A'}_")
        lines.append(f"_Updated: {datetime.utcnow().strftime('%H:%M')} UTC_")

        return "\n".join(lines)


# Singleton instance
_commodity_client: Optional[CommodityPriceClient] = None


def get_commodity_client() -> CommodityPriceClient:
    """Get or create the commodity price client singleton."""
    global _commodity_client
    if _commodity_client is None:
        _commodity_client = CommodityPriceClient()
    return _commodity_client


async def get_live_gold_price() -> Optional[float]:
    """Quick helper to get current gold price."""
    client = get_commodity_client()
    price = await client.get_gold_price()
    return price.price_usd if price else None


async def get_live_silver_price() -> Optional[float]:
    """Quick helper to get current silver price."""
    client = get_commodity_client()
    price = await client.get_silver_price()
    return price.price_usd if price else None
