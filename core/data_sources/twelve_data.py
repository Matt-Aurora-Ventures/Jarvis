"""
Twelve Data API Client

Free-tier integration for traditional market data:
- Stocks (US/Global)
- Forex
- ETFs
- Crypto
- Commodities
- 100+ technical indicators

Free tier: ~8 requests/minute, 8 symbols WebSocket

CRITICAL: API key loaded from environment. Never commit credentials.
"""

import os
import json
import time
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Load API key from environment
TWELVE_DATA_API_KEY = os.getenv("TWELVE_DATA_API_KEY", "")

# API endpoints
BASE_URL = "https://api.twelvedata.com"
WS_URL = "wss://ws.twelvedata.com/v1/quotes/price"

# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "twelve_data"


class Interval(Enum):
    """Supported time intervals."""
    M1 = "1min"
    M5 = "5min"
    M15 = "15min"
    M30 = "30min"
    M45 = "45min"
    H1 = "1h"
    H2 = "2h"
    H4 = "4h"
    D1 = "1day"
    W1 = "1week"
    MO1 = "1month"


@dataclass
class Quote:
    """Real-time quote data."""
    symbol: str
    name: Optional[str]
    exchange: Optional[str]
    price: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    change: float
    change_pct: float
    timestamp: int


@dataclass
class OHLCV:
    """Single OHLCV candle."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class TechnicalIndicator:
    """Technical indicator value."""
    timestamp: int
    value: float
    indicator: str
    symbol: str


class TwelveDataClient:
    """
    Twelve Data API client.

    Provides access to:
    - Real-time quotes
    - Historical time series (OHLCV)
    - Technical indicators (100+ built-in)
    - Fundamental data
    - Forex and crypto data
    """

    # Rate limiting (free tier: 8 req/min, 800/day)
    REQUESTS_PER_MINUTE = 8
    _request_times: List[float] = []

    def __init__(self, api_key: str = None):
        """
        Initialize client.

        Args:
            api_key: Twelve Data API key (defaults to env var)
        """
        self.api_key = api_key or TWELVE_DATA_API_KEY
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, tuple] = {}  # (timestamp, data)
        self._cache_ttl = 60.0  # 1 minute cache for quotes

        if not self.api_key:
            logger.warning("TWELVE_DATA_API_KEY not set - API calls will fail")

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _rate_limit(self):
        """Enforce rate limiting."""
        now = time.time()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]

        if len(self._request_times) >= self.REQUESTS_PER_MINUTE:
            # Wait until oldest request is >1 minute old
            wait_time = 60 - (now - self._request_times[0])
            if wait_time > 0:
                logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)

        self._request_times.append(time.time())

    async def _get(
        self,
        endpoint: str,
        params: Dict[str, Any],
        use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Make GET request to Twelve Data API.

        Args:
            endpoint: API endpoint
            params: Query parameters
            use_cache: Whether to use response caching

        Returns:
            API response data
        """
        await self._rate_limit()

        params["apikey"] = self.api_key

        # Check cache
        cache_key = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        if use_cache and cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data

        url = f"{BASE_URL}/{endpoint}"
        session = await self._get_session()

        try:
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Twelve Data API error {resp.status}: {error_text}")
                    return None

                data = await resp.json()

                # Check for API error
                if data.get("status") == "error":
                    logger.error(f"Twelve Data error: {data.get('message')}")
                    return None

                # Update cache
                if use_cache:
                    self._cache[cache_key] = (time.time(), data)

                return data
        except Exception as e:
            logger.error(f"Twelve Data request failed: {e}")
            return None

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()

    # ==================== Real-time Data ====================

    async def get_quote(self, symbol: str) -> Optional[Quote]:
        """
        Get real-time quote for a symbol.

        Args:
            symbol: Ticker symbol (e.g., "AAPL", "EUR/USD", "BTC/USD")

        Returns:
            Quote object with current market data
        """
        data = await self._get("quote", {"symbol": symbol})
        if not data:
            return None

        try:
            return Quote(
                symbol=data.get("symbol", symbol),
                name=data.get("name"),
                exchange=data.get("exchange"),
                price=float(data.get("close", 0)),
                open=float(data.get("open", 0)),
                high=float(data.get("high", 0)),
                low=float(data.get("low", 0)),
                close=float(data.get("close", 0)),
                volume=int(data.get("volume", 0)),
                change=float(data.get("change", 0)),
                change_pct=float(data.get("percent_change", 0)),
                timestamp=int(data.get("timestamp", time.time()))
            )
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to parse quote for {symbol}: {e}")
            return None

    async def get_price(self, symbol: str) -> Optional[float]:
        """Get latest price for a symbol."""
        data = await self._get("price", {"symbol": symbol})
        if data and "price" in data:
            return float(data["price"])
        return None

    async def get_quotes_batch(self, symbols: List[str]) -> Dict[str, Quote]:
        """
        Get quotes for multiple symbols (uses single API call).

        Args:
            symbols: List of ticker symbols

        Returns:
            Dict mapping symbol to Quote
        """
        symbol_str = ",".join(symbols)
        data = await self._get("quote", {"symbol": symbol_str})

        if not data:
            return {}

        quotes = {}
        # Handle both single and multiple response formats
        if isinstance(data, dict) and "symbol" in data:
            # Single symbol response
            quote = await self.get_quote(symbols[0])
            if quote:
                quotes[quote.symbol] = quote
        elif isinstance(data, list):
            # Multiple symbols response
            for item in data:
                try:
                    quotes[item["symbol"]] = Quote(
                        symbol=item.get("symbol"),
                        name=item.get("name"),
                        exchange=item.get("exchange"),
                        price=float(item.get("close", 0)),
                        open=float(item.get("open", 0)),
                        high=float(item.get("high", 0)),
                        low=float(item.get("low", 0)),
                        close=float(item.get("close", 0)),
                        volume=int(item.get("volume", 0)),
                        change=float(item.get("change", 0)),
                        change_pct=float(item.get("percent_change", 0)),
                        timestamp=int(item.get("timestamp", time.time()))
                    )
                except (TypeError, ValueError, KeyError):
                    continue

        return quotes

    # ==================== Historical Data ====================

    async def get_time_series(
        self,
        symbol: str,
        interval: Union[Interval, str] = Interval.D1,
        outputsize: int = 30,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[OHLCV]:
        """
        Get historical time series data.

        Args:
            symbol: Ticker symbol
            interval: Time interval (Interval enum or string)
            outputsize: Number of data points (max 5000)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of OHLCV candles
        """
        params = {
            "symbol": symbol,
            "interval": interval.value if isinstance(interval, Interval) else interval,
            "outputsize": min(outputsize, 5000)
        }

        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = await self._get("time_series", params, use_cache=False)
        if not data or "values" not in data:
            return []

        candles = []
        for v in data["values"]:
            try:
                candles.append(OHLCV(
                    timestamp=int(datetime.fromisoformat(v["datetime"].replace("Z", "+00:00")).timestamp()),
                    open=float(v["open"]),
                    high=float(v["high"]),
                    low=float(v["low"]),
                    close=float(v["close"]),
                    volume=int(v.get("volume", 0))
                ))
            except (TypeError, ValueError, KeyError):
                continue

        return candles

    # ==================== Technical Indicators ====================

    async def get_sma(
        self,
        symbol: str,
        interval: Union[Interval, str] = Interval.D1,
        time_period: int = 20,
        outputsize: int = 30
    ) -> List[TechnicalIndicator]:
        """
        Get Simple Moving Average.

        Args:
            symbol: Ticker symbol
            interval: Time interval
            time_period: SMA period
            outputsize: Number of data points

        Returns:
            List of SMA values
        """
        return await self._get_indicator("sma", symbol, interval, time_period, outputsize)

    async def get_ema(
        self,
        symbol: str,
        interval: Union[Interval, str] = Interval.D1,
        time_period: int = 20,
        outputsize: int = 30
    ) -> List[TechnicalIndicator]:
        """Get Exponential Moving Average."""
        return await self._get_indicator("ema", symbol, interval, time_period, outputsize)

    async def get_rsi(
        self,
        symbol: str,
        interval: Union[Interval, str] = Interval.D1,
        time_period: int = 14,
        outputsize: int = 30
    ) -> List[TechnicalIndicator]:
        """Get Relative Strength Index."""
        return await self._get_indicator("rsi", symbol, interval, time_period, outputsize)

    async def get_macd(
        self,
        symbol: str,
        interval: Union[Interval, str] = Interval.D1,
        outputsize: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get MACD (Moving Average Convergence Divergence).

        Returns list of dicts with 'macd', 'macd_signal', 'macd_hist'.
        """
        params = {
            "symbol": symbol,
            "interval": interval.value if isinstance(interval, Interval) else interval,
            "outputsize": outputsize
        }

        data = await self._get("macd", params, use_cache=False)
        if not data or "values" not in data:
            return []

        results = []
        for v in data["values"]:
            try:
                results.append({
                    "timestamp": int(datetime.fromisoformat(v["datetime"].replace("Z", "+00:00")).timestamp()),
                    "macd": float(v.get("macd", 0)),
                    "signal": float(v.get("macd_signal", 0)),
                    "histogram": float(v.get("macd_hist", 0))
                })
            except (TypeError, ValueError, KeyError):
                continue

        return results

    async def get_bbands(
        self,
        symbol: str,
        interval: Union[Interval, str] = Interval.D1,
        time_period: int = 20,
        outputsize: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get Bollinger Bands.

        Returns list of dicts with 'upper', 'middle', 'lower'.
        """
        params = {
            "symbol": symbol,
            "interval": interval.value if isinstance(interval, Interval) else interval,
            "time_period": time_period,
            "outputsize": outputsize
        }

        data = await self._get("bbands", params, use_cache=False)
        if not data or "values" not in data:
            return []

        results = []
        for v in data["values"]:
            try:
                results.append({
                    "timestamp": int(datetime.fromisoformat(v["datetime"].replace("Z", "+00:00")).timestamp()),
                    "upper": float(v.get("upper_band", 0)),
                    "middle": float(v.get("middle_band", 0)),
                    "lower": float(v.get("lower_band", 0))
                })
            except (TypeError, ValueError, KeyError):
                continue

        return results

    async def _get_indicator(
        self,
        indicator: str,
        symbol: str,
        interval: Union[Interval, str],
        time_period: int,
        outputsize: int
    ) -> List[TechnicalIndicator]:
        """Generic technical indicator fetcher."""
        params = {
            "symbol": symbol,
            "interval": interval.value if isinstance(interval, Interval) else interval,
            "time_period": time_period,
            "outputsize": outputsize
        }

        data = await self._get(indicator, params, use_cache=False)
        if not data or "values" not in data:
            return []

        results = []
        for v in data["values"]:
            try:
                results.append(TechnicalIndicator(
                    timestamp=int(datetime.fromisoformat(v["datetime"].replace("Z", "+00:00")).timestamp()),
                    value=float(v.get(indicator, 0)),
                    indicator=indicator.upper(),
                    symbol=symbol
                ))
            except (TypeError, ValueError, KeyError):
                continue

        return results

    # ==================== Fundamentals ====================

    async def get_profile(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get company profile.

        Returns:
            Company profile with sector, industry, description, etc.
        """
        return await self._get("profile", {"symbol": symbol})

    async def get_statistics(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get key statistics.

        Returns:
            Market cap, P/E ratio, 52-week high/low, etc.
        """
        return await self._get("statistics", {"symbol": symbol})

    async def get_dividends(self, symbol: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get dividend history.

        Returns:
            List of dividend payments
        """
        data = await self._get("dividends", {"symbol": symbol})
        if data and "dividends" in data:
            return data["dividends"]
        return None

    # ==================== Forex & Crypto ====================

    async def get_forex_pairs(self) -> List[Dict[str, str]]:
        """Get list of available forex pairs."""
        data = await self._get("forex_pairs", {})
        if data and "data" in data:
            return data["data"]
        return []

    async def get_crypto_exchanges(self) -> List[str]:
        """Get list of supported crypto exchanges."""
        data = await self._get("cryptocurrencies", {})
        if data and "data" in data:
            exchanges = set()
            for item in data["data"]:
                exchanges.update(item.get("available_exchanges", []))
            return list(exchanges)
        return []

    async def get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Get forex exchange rate.

        Args:
            from_currency: Source currency (e.g., "USD")
            to_currency: Target currency (e.g., "EUR")

        Returns:
            Exchange rate
        """
        symbol = f"{from_currency}/{to_currency}"
        price = await self.get_price(symbol)
        return price


# Singleton client instance
_client: Optional[TwelveDataClient] = None


def get_client() -> TwelveDataClient:
    """Get or create the singleton client instance."""
    global _client
    if _client is None:
        _client = TwelveDataClient()
    return _client


async def cleanup():
    """Cleanup client resources."""
    global _client
    if _client:
        await _client.close()
        _client = None
