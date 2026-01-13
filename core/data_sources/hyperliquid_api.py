"""
Hyperliquid Advanced API Client

Comprehensive module for Hyperliquid/Alchemy data layer integration.
Features:
- Real-time order book and trade data
- Liquidation monitoring and prediction
- Whale tracking and position analysis
- Historical data for backtesting
- Funding rate analysis

CRITICAL: API key is loaded from environment. Never commit credentials.
"""

import os
import json
import time
import asyncio
import aiohttp
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Load API key from environment
HYPERLIQUID_API_KEY = os.getenv("HYPERLIQUID_API_KEY", "")
HYPERLIQUID_DATA_API = os.getenv("HYPERLIQUID_DATA_API", "https://api.hyperliquid.xyz")

# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "hyperliquid"


class TimeFrame(Enum):
    """Supported candle timeframes."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


@dataclass
class OrderBookLevel:
    """Single order book level."""
    price: float
    size: float
    side: str  # 'bid' or 'ask'


@dataclass
class Trade:
    """Single trade record."""
    timestamp: int
    price: float
    size: float
    side: str  # 'buy' or 'sell'
    liquidation: bool = False


@dataclass
class Position:
    """Trader position data."""
    address: str
    symbol: str
    size: float
    entry_price: float
    unrealized_pnl: float
    leverage: float
    liquidation_price: Optional[float] = None


@dataclass
class FundingRate:
    """Funding rate data."""
    symbol: str
    rate: float
    timestamp: int
    predicted_rate: Optional[float] = None


@dataclass
class LiquidationEvent:
    """Liquidation event data."""
    timestamp: int
    symbol: str
    side: str
    size: float
    price: float
    address: str


class HyperliquidClient:
    """
    Advanced Hyperliquid API client.

    Provides access to:
    - Real-time market data
    - Order book depth
    - Trade history
    - Liquidation events
    - Funding rates
    - Whale position tracking
    """

    # Public endpoints (no auth required)
    PUBLIC_API = "https://api.hyperliquid.xyz/info"

    # Rate limiting
    REQUESTS_PER_SECOND = 10
    _last_request_time = 0.0

    def __init__(self, api_key: str = None):
        """
        Initialize client.

        Args:
            api_key: Optional API key for enhanced data access
        """
        self.api_key = api_key or HYPERLIQUID_API_KEY
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._cache_ttl = 5.0  # 5 second cache

        # Ensure cache directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def _rate_limit(self):
        """Enforce rate limiting."""
        now = time.time()
        min_interval = 1.0 / self.REQUESTS_PER_SECOND
        elapsed = now - self._last_request_time
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request_time = time.time()

    async def _post(self, payload: Dict[str, Any], use_cache: bool = True) -> Any:
        """
        Make POST request to Hyperliquid API.

        Args:
            payload: Request payload
            use_cache: Whether to use response caching

        Returns:
            API response data
        """
        await self._rate_limit()

        # Check cache
        cache_key = json.dumps(payload, sort_keys=True)
        if use_cache and cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if time.time() - cached_time < self._cache_ttl:
                return cached_data

        session = await self._get_session()
        try:
            async with session.post(self.PUBLIC_API, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"Hyperliquid API error {resp.status}: {error_text}")
                    return None
                data = await resp.json()

                # Update cache
                if use_cache:
                    self._cache[cache_key] = (time.time(), data)

                return data
        except Exception as e:
            logger.error(f"Hyperliquid request failed: {e}")
            return None

    async def close(self):
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()

    # ==================== Market Data ====================

    async def get_all_mids(self) -> Dict[str, float]:
        """
        Get mid prices for all perpetual markets.

        Returns:
            Dict mapping symbol to mid price
        """
        data = await self._post({"type": "allMids"})
        if not data or not isinstance(data, dict):
            return {}

        mids = {}
        for symbol, price in data.items():
            try:
                mids[symbol] = float(price)
            except (TypeError, ValueError):
                continue
        return mids

    async def get_mid_price(self, symbol: str) -> Optional[float]:
        """Get mid price for a single symbol."""
        mids = await self.get_all_mids()
        return mids.get(symbol.upper())

    async def get_meta(self) -> Optional[Dict[str, Any]]:
        """
        Get exchange metadata (all available markets).

        Returns:
            Market metadata including symbols, decimals, etc.
        """
        return await self._post({"type": "meta"})

    async def get_order_book(self, symbol: str, depth: int = 20) -> Dict[str, List[OrderBookLevel]]:
        """
        Get order book for a symbol.

        Args:
            symbol: Market symbol (e.g., "BTC", "ETH")
            depth: Number of levels on each side

        Returns:
            Dict with 'bids' and 'asks' lists
        """
        data = await self._post({
            "type": "l2Book",
            "coin": symbol.upper()
        }, use_cache=False)

        if not data:
            return {"bids": [], "asks": []}

        levels = data.get("levels", [[], []])
        bids = []
        asks = []

        for level in levels[0][:depth]:  # Bids
            bids.append(OrderBookLevel(
                price=float(level.get("px", 0)),
                size=float(level.get("sz", 0)),
                side="bid"
            ))

        for level in levels[1][:depth]:  # Asks
            asks.append(OrderBookLevel(
                price=float(level.get("px", 0)),
                size=float(level.get("sz", 0)),
                side="ask"
            ))

        return {"bids": bids, "asks": asks}

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Trade]:
        """
        Get recent trades for a symbol.

        Args:
            symbol: Market symbol
            limit: Maximum trades to return

        Returns:
            List of Trade objects
        """
        data = await self._post({
            "type": "recentTrades",
            "coin": symbol.upper()
        }, use_cache=False)

        if not data or not isinstance(data, list):
            return []

        trades = []
        for t in data[:limit]:
            trades.append(Trade(
                timestamp=int(t.get("time", 0)),
                price=float(t.get("px", 0)),
                size=float(t.get("sz", 0)),
                side=t.get("side", "unknown"),
                liquidation=t.get("liquidation", False)
            ))
        return trades

    # ==================== Candles & Historical ====================

    async def get_candles(
        self,
        symbol: str,
        interval: TimeFrame,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Get historical candle data.

        Args:
            symbol: Market symbol
            interval: Candle interval (TimeFrame enum)
            start_time: Start timestamp in ms
            end_time: End timestamp in ms
            limit: Maximum candles to return

        Returns:
            List of candle dicts with OHLCV data
        """
        if end_time is None:
            end_time = int(time.time() * 1000)
        if start_time is None:
            # Default to last 7 days
            start_time = end_time - (7 * 24 * 60 * 60 * 1000)

        data = await self._post({
            "type": "candleSnapshot",
            "req": {
                "coin": symbol.upper(),
                "interval": interval.value,
                "startTime": start_time,
                "endTime": end_time
            }
        }, use_cache=False)

        if not data or not isinstance(data, list):
            return []

        return data[:limit]

    async def fetch_historical_data(
        self,
        symbol: str,
        interval: TimeFrame,
        days: int = 30,
        save_to_disk: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Fetch extended historical data with chunking.

        Args:
            symbol: Market symbol
            interval: Candle interval
            days: Number of days to fetch
            save_to_disk: Whether to save to cache directory

        Returns:
            List of all candles
        """
        end_time = int(time.time() * 1000)
        start_time = end_time - (days * 24 * 60 * 60 * 1000)

        all_candles = []
        chunk_days = 7
        chunk_ms = chunk_days * 24 * 60 * 60 * 1000

        cursor = start_time
        while cursor < end_time:
            chunk_end = min(cursor + chunk_ms, end_time)
            candles = await self.get_candles(
                symbol, interval,
                start_time=cursor,
                end_time=chunk_end
            )
            all_candles.extend(candles)
            cursor = chunk_end
            await asyncio.sleep(0.1)  # Rate limit

        # Sort and deduplicate
        all_candles.sort(key=lambda c: c.get("t", 0))

        if save_to_disk:
            filename = f"{symbol.lower()}_{interval.value}_{start_time}_{end_time}.json"
            path = CACHE_DIR / filename
            with open(path, "w") as f:
                json.dump({
                    "symbol": symbol,
                    "interval": interval.value,
                    "start_time": start_time,
                    "end_time": end_time,
                    "candles": all_candles
                }, f, indent=2)
            logger.info(f"Saved {len(all_candles)} candles to {path}")

        return all_candles

    # ==================== Funding Rates ====================

    async def get_funding_rates(self) -> Dict[str, FundingRate]:
        """
        Get current funding rates for all markets.

        Returns:
            Dict mapping symbol to FundingRate
        """
        meta = await self.get_meta()
        if not meta:
            return {}

        rates = {}
        universe = meta.get("universe", [])

        for market in universe:
            symbol = market.get("name", "")
            funding = market.get("funding", {})

            if funding:
                rates[symbol] = FundingRate(
                    symbol=symbol,
                    rate=float(funding.get("fundingRate", 0)),
                    timestamp=int(time.time() * 1000),
                    predicted_rate=float(funding.get("predictedFunding", 0)) if funding.get("predictedFunding") else None
                )

        return rates

    async def get_funding_history(
        self,
        symbol: str,
        start_time: int,
        end_time: Optional[int] = None
    ) -> List[FundingRate]:
        """
        Get historical funding rates.

        Args:
            symbol: Market symbol
            start_time: Start timestamp in ms
            end_time: End timestamp in ms (default: now)

        Returns:
            List of historical FundingRate objects
        """
        if end_time is None:
            end_time = int(time.time() * 1000)

        data = await self._post({
            "type": "fundingHistory",
            "coin": symbol.upper(),
            "startTime": start_time,
            "endTime": end_time
        })

        if not data or not isinstance(data, list):
            return []

        history = []
        for f in data:
            history.append(FundingRate(
                symbol=symbol,
                rate=float(f.get("fundingRate", 0)),
                timestamp=int(f.get("time", 0))
            ))
        return history

    # ==================== Liquidations ====================

    async def get_liquidations(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[LiquidationEvent]:
        """
        Get recent liquidation events.

        Args:
            symbol: Optional filter by symbol
            limit: Maximum events to return

        Returns:
            List of LiquidationEvent objects
        """
        # Get recent trades and filter for liquidations
        trades = await self.get_recent_trades(symbol or "BTC", limit * 10)

        liquidations = []
        for trade in trades:
            if trade.liquidation:
                liquidations.append(LiquidationEvent(
                    timestamp=trade.timestamp,
                    symbol=symbol or "BTC",
                    side=trade.side,
                    size=trade.size,
                    price=trade.price,
                    address=""  # Not available in public API
                ))

        return liquidations[:limit]

    async def estimate_liquidation_price(
        self,
        symbol: str,
        entry_price: float,
        leverage: float,
        side: str
    ) -> float:
        """
        Estimate liquidation price for a position.

        Args:
            symbol: Market symbol
            entry_price: Position entry price
            leverage: Leverage used
            side: 'long' or 'short'

        Returns:
            Estimated liquidation price
        """
        # Maintenance margin is typically 0.5% on Hyperliquid
        maintenance_margin = 0.005

        if side.lower() == "long":
            # Long liquidation: entry * (1 - 1/leverage + maintenance)
            liq_price = entry_price * (1 - (1 / leverage) + maintenance_margin)
        else:
            # Short liquidation: entry * (1 + 1/leverage - maintenance)
            liq_price = entry_price * (1 + (1 / leverage) - maintenance_margin)

        return liq_price

    # ==================== Whale Tracking ====================

    async def get_clearinghouse_state(self, address: str) -> Optional[Dict[str, Any]]:
        """
        Get clearinghouse state for an address (positions + margin).

        Args:
            address: Ethereum address

        Returns:
            Account state including all positions
        """
        data = await self._post({
            "type": "clearinghouseState",
            "user": address
        }, use_cache=False)

        return data

    async def get_user_positions(self, address: str) -> List[Position]:
        """
        Get all positions for a user.

        Args:
            address: User's Ethereum address

        Returns:
            List of Position objects
        """
        state = await self.get_clearinghouse_state(address)
        if not state:
            return []

        positions = []
        asset_positions = state.get("assetPositions", [])

        for pos in asset_positions:
            position = pos.get("position", {})
            if not position:
                continue

            size = float(position.get("szi", 0))
            if size == 0:
                continue

            entry_price = float(position.get("entryPx", 0))
            unrealized_pnl = float(position.get("unrealizedPnl", 0))
            leverage = float(position.get("leverage", {}).get("value", 1))
            liq_price = float(position.get("liquidationPx", 0)) if position.get("liquidationPx") else None

            positions.append(Position(
                address=address,
                symbol=position.get("coin", ""),
                size=size,
                entry_price=entry_price,
                unrealized_pnl=unrealized_pnl,
                leverage=leverage,
                liquidation_price=liq_price
            ))

        return positions

    async def get_user_fills(
        self,
        address: str,
        start_time: Optional[int] = None
    ) -> List[Trade]:
        """
        Get trade fills for a user.

        Args:
            address: User's Ethereum address
            start_time: Optional start timestamp

        Returns:
            List of user's trades
        """
        payload = {
            "type": "userFills",
            "user": address
        }
        if start_time:
            payload["startTime"] = start_time

        data = await self._post(payload, use_cache=False)

        if not data or not isinstance(data, list):
            return []

        fills = []
        for f in data:
            fills.append(Trade(
                timestamp=int(f.get("time", 0)),
                price=float(f.get("px", 0)),
                size=float(f.get("sz", 0)),
                side=f.get("side", "unknown"),
                liquidation=f.get("liquidation", False)
            ))
        return fills

    # ==================== Analysis & Backtesting ====================

    async def calculate_liquidity_depth(
        self,
        symbol: str,
        price_range_pct: float = 2.0
    ) -> Dict[str, float]:
        """
        Calculate liquidity depth within a price range.

        Args:
            symbol: Market symbol
            price_range_pct: Price range as percentage

        Returns:
            Dict with bid/ask liquidity in USD
        """
        book = await self.get_order_book(symbol, depth=50)
        mid_price = await self.get_mid_price(symbol)

        if not mid_price:
            return {"bid_liquidity": 0, "ask_liquidity": 0}

        lower = mid_price * (1 - price_range_pct / 100)
        upper = mid_price * (1 + price_range_pct / 100)

        bid_liquidity = sum(
            level.price * level.size
            for level in book["bids"]
            if level.price >= lower
        )

        ask_liquidity = sum(
            level.price * level.size
            for level in book["asks"]
            if level.price <= upper
        )

        return {
            "bid_liquidity": bid_liquidity,
            "ask_liquidity": ask_liquidity,
            "total_liquidity": bid_liquidity + ask_liquidity,
            "imbalance": (bid_liquidity - ask_liquidity) / (bid_liquidity + ask_liquidity) if (bid_liquidity + ask_liquidity) > 0 else 0
        }

    async def detect_large_orders(
        self,
        symbol: str,
        threshold_usd: float = 100000
    ) -> List[Dict[str, Any]]:
        """
        Detect large orders in the order book.

        Args:
            symbol: Market symbol
            threshold_usd: Minimum order size in USD

        Returns:
            List of large orders with details
        """
        book = await self.get_order_book(symbol, depth=100)
        large_orders = []

        for level in book["bids"] + book["asks"]:
            order_value = level.price * level.size
            if order_value >= threshold_usd:
                large_orders.append({
                    "side": level.side,
                    "price": level.price,
                    "size": level.size,
                    "value_usd": order_value
                })

        return sorted(large_orders, key=lambda x: x["value_usd"], reverse=True)

    def backtest_simple_ma(
        self,
        candles: List[Dict[str, Any]],
        fast_period: int = 5,
        slow_period: int = 20
    ) -> Dict[str, Any]:
        """
        Run simple moving average crossover backtest.

        Args:
            candles: Historical candle data
            fast_period: Fast MA period
            slow_period: Slow MA period

        Returns:
            Backtest results
        """
        closes = []
        for c in candles:
            close = c.get("c") or c.get("close")
            if close:
                closes.append(float(close))

        if len(closes) < slow_period + 2:
            return {"error": "Insufficient data", "trades": 0, "roi": 0}

        def calc_ma(idx: int, period: int) -> float:
            start = max(0, idx - period + 1)
            window = closes[start:idx + 1]
            return sum(window) / len(window)

        position = 0
        entry_price = 0.0
        total_pnl = 0.0
        trades = 0
        wins = 0

        for i in range(slow_period, len(closes)):
            fast_ma = calc_ma(i, fast_period)
            slow_ma = calc_ma(i, slow_period)
            price = closes[i]

            if position == 0 and fast_ma > slow_ma:
                position = 1
                entry_price = price
                trades += 1
            elif position == 1 and fast_ma < slow_ma:
                pnl = price - entry_price
                total_pnl += pnl
                if pnl > 0:
                    wins += 1
                position = 0

        # Close open position
        if position == 1:
            total_pnl += closes[-1] - entry_price

        initial_price = closes[0]
        roi = total_pnl / initial_price if initial_price else 0
        win_rate = wins / trades if trades > 0 else 0

        return {
            "trades": trades,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "total_pnl": round(total_pnl, 4),
            "roi": round(roi, 4),
            "roi_pct": round(roi * 100, 2),
            "fast_period": fast_period,
            "slow_period": slow_period
        }


# Singleton client instance
_client: Optional[HyperliquidClient] = None


def get_client() -> HyperliquidClient:
    """Get or create the singleton client instance."""
    global _client
    if _client is None:
        _client = HyperliquidClient()
    return _client


async def cleanup():
    """Cleanup client resources."""
    global _client
    if _client:
        await _client.close()
        _client = None
