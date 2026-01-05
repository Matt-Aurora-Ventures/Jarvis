"""
Data Ingestion Layer for Jarvis Trading Bot
=============================================

The "Eyes" of the trading system - real-time market data streaming.

Features:
- WebSocket connections for low-latency data (Binance, Kraken, Hyperliquid)
- CCXT library integration for exchange normalization
- Ring buffer for tick-level data storage
- OHLCV candle aggregation from tick data
- Multi-exchange price comparison for arbitrage detection

Phase 3 Implementation per Quant Analyst specification.

Usage:
    from core.data_ingestion import DataIngestionLayer, ExchangeConfig
    
    layer = DataIngestionLayer()
    layer.add_exchange(ExchangeConfig(name="binance", symbols=["BTC/USDT"]))
    await layer.start()
"""

import asyncio
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

# Optional imports - gracefully handle missing dependencies
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    websockets = None

try:
    import ccxt
    import ccxt.async_support as ccxt_async
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False
    ccxt = None
    ccxt_async = None


logger = logging.getLogger(__name__)


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class Tick:
    """Single price tick from exchange."""
    symbol: str
    exchange: str
    price: float
    volume: float
    timestamp: float  # Unix timestamp in seconds
    side: Optional[str] = None  # "buy" or "sell"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "price": self.price,
            "volume": self.volume,
            "timestamp": self.timestamp,
            "side": self.side,
        }


@dataclass
class OHLCV:
    """OHLCV candle data."""
    symbol: str
    exchange: str
    timestamp: float  # Candle open time
    open: float
    high: float
    low: float
    close: float
    volume: float
    interval: str  # e.g., "1m", "5m", "1h"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "interval": self.interval,
        }


@dataclass
class OrderBook:
    """Order book snapshot."""
    symbol: str
    exchange: str
    timestamp: float
    bids: List[List[float]]  # [[price, quantity], ...]
    asks: List[List[float]]
    
    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0][0] if self.bids else None
    
    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0][0] if self.asks else None
    
    @property
    def spread(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None
    
    @property
    def spread_pct(self) -> Optional[float]:
        if self.best_bid and self.spread:
            return (self.spread / self.best_bid) * 100
        return None


@dataclass
class ExchangeConfig:
    """Configuration for an exchange connection."""
    name: str  # e.g., "binance", "kraken", "hyperliquid"
    symbols: List[str]  # e.g., ["BTC/USDT", "ETH/USDT"]
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    sandbox: bool = False
    websocket_url: Optional[str] = None  # Custom WS URL
    rate_limit_ms: int = 100  # Rate limit between requests


# ============================================================================
# Ring Buffer for Tick Data
# ============================================================================

class TickBuffer:
    """
    Ring buffer for storing recent tick data.
    
    Efficiently maintains a fixed-size window of recent ticks
    for real-time analysis and candle aggregation.
    """
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._buffer: deque = deque(maxlen=max_size)
        self._by_symbol: Dict[str, deque] = {}
    
    def add(self, tick: Tick):
        """Add a tick to the buffer."""
        self._buffer.append(tick)
        
        # Also index by symbol for fast lookup
        if tick.symbol not in self._by_symbol:
            self._by_symbol[tick.symbol] = deque(maxlen=self.max_size // 10)
        self._by_symbol[tick.symbol].append(tick)
    
    def get_recent(self, count: int = 100) -> List[Tick]:
        """Get the N most recent ticks."""
        return list(self._buffer)[-count:]
    
    def get_symbol(self, symbol: str, count: int = 100) -> List[Tick]:
        """Get recent ticks for a specific symbol."""
        if symbol not in self._by_symbol:
            return []
        return list(self._by_symbol[symbol])[-count:]
    
    def get_prices(self, symbol: str, count: int = 100) -> List[float]:
        """Get recent prices for a symbol."""
        ticks = self.get_symbol(symbol, count)
        return [t.price for t in ticks]
    
    def aggregate_ohlcv(
        self,
        symbol: str,
        interval_seconds: int = 60,
        count: int = 20,
    ) -> List[OHLCV]:
        """
        Aggregate ticks into OHLCV candles.
        
        Args:
            symbol: Trading pair
            interval_seconds: Candle interval in seconds
            count: Number of candles to return
        """
        ticks = self.get_symbol(symbol, count * 100)  # Get enough ticks
        if not ticks:
            return []
        
        # Group ticks by interval
        candles: Dict[int, List[Tick]] = {}
        for tick in ticks:
            bucket = int(tick.timestamp // interval_seconds) * interval_seconds
            if bucket not in candles:
                candles[bucket] = []
            candles[bucket].append(tick)
        
        # Build OHLCV from each bucket
        ohlcv_list = []
        for timestamp, bucket_ticks in sorted(candles.items()):
            if not bucket_ticks:
                continue
            
            prices = [t.price for t in bucket_ticks]
            volumes = [t.volume for t in bucket_ticks]
            
            ohlcv = OHLCV(
                symbol=symbol,
                exchange=bucket_ticks[0].exchange,
                timestamp=float(timestamp),
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume=sum(volumes),
                interval=f"{interval_seconds}s",
            )
            ohlcv_list.append(ohlcv)
        
        return ohlcv_list[-count:]
    
    def clear(self):
        """Clear all data."""
        self._buffer.clear()
        self._by_symbol.clear()
    
    @property
    def size(self) -> int:
        return len(self._buffer)


# ============================================================================
# WebSocket Handlers for Major Exchanges
# ============================================================================

class BinanceWSHandler:
    """WebSocket handler for Binance."""
    
    WS_URL = "wss://stream.binance.com:9443/ws"
    
    def __init__(self, symbols: List[str], on_tick: Callable[[Tick], None]):
        self.symbols = symbols
        self.on_tick = on_tick
        self._ws = None
        self._running = False
    
    def _symbol_to_stream(self, symbol: str) -> str:
        """Convert CCXT symbol to Binance stream name."""
        # BTC/USDT -> btcusdt@trade
        clean = symbol.replace("/", "").lower()
        return f"{clean}@trade"
    
    async def connect(self):
        """Connect to Binance WebSocket."""
        if not HAS_WEBSOCKETS:
            logger.error("websockets library not installed")
            return
        
        streams = [self._symbol_to_stream(s) for s in self.symbols]
        url = f"{self.WS_URL}/{'/'.join(streams)}"
        
        self._running = True
        retry_delay = 1.0
        heartbeat_timeout = 30.0
        while self._running:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=10,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    logger.info(f"Connected to Binance WS: {len(streams)} streams")
                    retry_delay = 1.0
                    
                    # Subscribe to streams
                    subscribe_msg = {
                        "method": "SUBSCRIBE",
                        "params": streams,
                        "id": 1,
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    
                    while self._running:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=heartbeat_timeout)
                        except asyncio.TimeoutError:
                            logger.warning("Binance WS heartbeat timeout; forcing reconnect")
                            break
                        except Exception as exc:
                            logger.error(f"Binance WS recv error: {exc}")
                            break
                        await self._handle_message(message)
                        
            except Exception as e:
                logger.error(f"Binance WS error: {e}")
            
            if self._running:
                logger.warning("Binance WS disconnected; reconnecting in %.1fs", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)
    
    async def _handle_message(self, message: str):
        """Parse Binance trade message."""
        try:
            data = json.loads(message)
            
            if "e" not in data or data["e"] != "trade":
                return  # Not a trade message
            
            # Extract trade data
            # s: symbol, p: price, q: quantity, T: timestamp, m: is buyer maker
            symbol = data.get("s", "")
            # Convert binance symbol back to CCXT format
            # BTCUSDT -> BTC/USDT (simplified heuristic)
            if "USDT" in symbol:
                symbol = symbol.replace("USDT", "/USDT")
            elif "BTC" in symbol and symbol != "BTC":
                symbol = symbol.replace("BTC", "/BTC")
            
            tick = Tick(
                symbol=symbol,
                exchange="binance",
                price=float(data["p"]),
                volume=float(data["q"]),
                timestamp=float(data["T"]) / 1000,  # ms to seconds
                side="sell" if data.get("m", False) else "buy",
            )
            
            self.on_tick(tick)
            
        except Exception as e:
            logger.warning(f"Failed to parse Binance message: {e}")
    
    async def disconnect(self):
        """Disconnect from WebSocket."""
        self._running = False
        if self._ws:
            await self._ws.close()


class KrakenWSHandler:
    """WebSocket handler for Kraken."""
    
    WS_URL = "wss://ws.kraken.com"
    
    def __init__(self, symbols: List[str], on_tick: Callable[[Tick], None]):
        self.symbols = symbols
        self.on_tick = on_tick
        self._ws = None
        self._running = False
    
    def _symbol_to_kraken(self, symbol: str) -> str:
        """Convert CCXT symbol to Kraken pair."""
        # BTC/USDT -> XBT/USDT (Kraken uses XBT for Bitcoin)
        return symbol.replace("BTC", "XBT")
    
    async def connect(self):
        """Connect to Kraken WebSocket."""
        if not HAS_WEBSOCKETS:
            logger.error("websockets library not installed")
            return
        
        self._running = True
        retry_delay = 1.0
        heartbeat_timeout = 30.0
        while self._running:
            try:
                async with websockets.connect(
                    self.WS_URL,
                    ping_interval=10,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    logger.info(f"Connected to Kraken WS")
                    retry_delay = 1.0
                    
                    # Subscribe to trades
                    pairs = [self._symbol_to_kraken(s) for s in self.symbols]
                    subscribe_msg = {
                        "event": "subscribe",
                        "pair": pairs,
                        "subscription": {"name": "trade"},
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    
                    while self._running:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=heartbeat_timeout)
                        except asyncio.TimeoutError:
                            logger.warning("Kraken WS heartbeat timeout; forcing reconnect")
                            break
                        except Exception as exc:
                            logger.error(f"Kraken WS recv error: {exc}")
                            break
                        await self._handle_message(message)
                        
            except Exception as e:
                logger.error(f"Kraken WS error: {e}")
            
            if self._running:
                logger.warning("Kraken WS disconnected; reconnecting in %.1fs", retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30.0)
    
    async def _handle_message(self, message: str):
        """Parse Kraken trade message."""
        try:
            data = json.loads(message)
            
            # Kraken sends array for trade updates
            if not isinstance(data, list) or len(data) < 4:
                return
            
            trades = data[1]
            pair = data[3]
            
            # Convert back to CCXT format
            symbol = pair.replace("XBT", "BTC")
            
            for trade in trades:
                # [price, volume, time, side, orderType, misc]
                tick = Tick(
                    symbol=symbol,
                    exchange="kraken",
                    price=float(trade[0]),
                    volume=float(trade[1]),
                    timestamp=float(trade[2]),
                    side="buy" if trade[3] == "b" else "sell",
                )
                self.on_tick(tick)
                
        except Exception as e:
            logger.warning(f"Failed to parse Kraken message: {e}")
    
    async def disconnect(self):
        """Disconnect from WebSocket."""
        self._running = False
        if self._ws:
            await self._ws.close()


# ============================================================================
# CCXT Exchange Normalizer
# ============================================================================

class CCXTNormalizer:
    """
    CCXT-based exchange data normalizer.
    
    Provides a unified interface for fetching data from multiple exchanges
    using the CCXT library for normalization.
    """
    
    def __init__(self):
        self._exchanges: Dict[str, Any] = {}
    
    async def add_exchange(self, config: ExchangeConfig) -> bool:
        """Add and initialize an exchange."""
        if not HAS_CCXT:
            logger.error("CCXT library not installed")
            return False
        
        try:
            exchange_class = getattr(ccxt_async, config.name, None)
            if not exchange_class:
                logger.error(f"Exchange {config.name} not supported by CCXT")
                return False
            
            exchange_config = {
                "enableRateLimit": True,
                "rateLimit": config.rate_limit_ms,
            }
            
            if config.api_key:
                exchange_config["apiKey"] = config.api_key
            if config.api_secret:
                exchange_config["secret"] = config.api_secret
            if config.sandbox:
                exchange_config["sandbox"] = True
            
            exchange = exchange_class(exchange_config)
            await exchange.load_markets()
            
            self._exchanges[config.name] = exchange
            logger.info(f"Added exchange: {config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add exchange {config.name}: {e}")
            return False
    
    async def fetch_ticker(self, exchange: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch current ticker for a symbol."""
        if exchange not in self._exchanges:
            return None
        
        try:
            return await self._exchanges[exchange].fetch_ticker(symbol)
        except Exception as e:
            logger.warning(f"Failed to fetch ticker {symbol} from {exchange}: {e}")
            return None
    
    async def fetch_ohlcv(
        self,
        exchange: str,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 100,
    ) -> List[OHLCV]:
        """Fetch OHLCV candles."""
        if exchange not in self._exchanges:
            return []
        
        try:
            raw = await self._exchanges[exchange].fetch_ohlcv(
                symbol, timeframe, limit=limit
            )
            
            return [
                OHLCV(
                    symbol=symbol,
                    exchange=exchange,
                    timestamp=candle[0] / 1000,  # ms to seconds
                    open=candle[1],
                    high=candle[2],
                    low=candle[3],
                    close=candle[4],
                    volume=candle[5],
                    interval=timeframe,
                )
                for candle in raw
            ]
        except Exception as e:
            logger.warning(f"Failed to fetch OHLCV {symbol} from {exchange}: {e}")
            return []
    
    async def fetch_order_book(
        self,
        exchange: str,
        symbol: str,
        limit: int = 20,
    ) -> Optional[OrderBook]:
        """Fetch order book."""
        if exchange not in self._exchanges:
            return None
        
        try:
            raw = await self._exchanges[exchange].fetch_order_book(symbol, limit)
            
            return OrderBook(
                symbol=symbol,
                exchange=exchange,
                timestamp=raw.get("timestamp", time.time() * 1000) / 1000,
                bids=raw.get("bids", []),
                asks=raw.get("asks", []),
            )
        except Exception as e:
            logger.warning(f"Failed to fetch order book {symbol} from {exchange}: {e}")
            return None
    
    async def fetch_multi_exchange_prices(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """
        Fetch current price for a symbol across multiple exchanges.
        
        Useful for spatial arbitrage detection.
        """
        exchanges = exchanges or list(self._exchanges.keys())
        prices = {}
        
        tasks = [
            self.fetch_ticker(ex, symbol)
            for ex in exchanges
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for exchange, result in zip(exchanges, results):
            if isinstance(result, dict) and "last" in result:
                prices[exchange] = result["last"]
        
        return prices
    
    async def close_all(self):
        """Close all exchange connections."""
        for exchange in self._exchanges.values():
            await exchange.close()
        self._exchanges.clear()


# ============================================================================
# Main Data Ingestion Layer
# ============================================================================

class DataIngestionLayer:
    """
    The "Eyes" - Unified data ingestion layer.
    
    Manages WebSocket connections and CCXT for multi-exchange data access.
    Provides a unified interface for real-time and historical data.
    """
    
    def __init__(self, buffer_size: int = 10000):
        self.tick_buffer = TickBuffer(max_size=buffer_size)
        self.normalizer = CCXTNormalizer()
        self._ws_handlers: List[Any] = []
        self._callbacks: List[Callable[[Tick], None]] = []
        self._running = False
    
    def add_tick_callback(self, callback: Callable[[Tick], None]):
        """Add a callback to be called on each new tick."""
        self._callbacks.append(callback)
    
    def _on_tick(self, tick: Tick):
        """Internal tick handler."""
        self.tick_buffer.add(tick)
        for callback in self._callbacks:
            try:
                callback(tick)
            except Exception as e:
                logger.warning(f"Tick callback error: {e}")
    
    async def add_exchange(
        self,
        config: ExchangeConfig,
        use_websocket: bool = True,
    ) -> bool:
        """
        Add an exchange for data ingestion.
        
        Args:
            config: Exchange configuration
            use_websocket: Whether to use WebSocket for real-time data
        """
        # Add to CCXT normalizer for REST access
        success = await self.normalizer.add_exchange(config)
        
        # Add WebSocket handler if requested
        if use_websocket and HAS_WEBSOCKETS:
            if config.name == "binance":
                handler = BinanceWSHandler(config.symbols, self._on_tick)
                self._ws_handlers.append(handler)
            elif config.name == "kraken":
                handler = KrakenWSHandler(config.symbols, self._on_tick)
                self._ws_handlers.append(handler)
            else:
                logger.warning(f"No WebSocket handler for {config.name}")
        
        return success
    
    async def start(self):
        """Start all WebSocket connections."""
        if not self._ws_handlers:
            logger.warning("No WebSocket handlers configured")
            return
        
        self._running = True
        tasks = [handler.connect() for handler in self._ws_handlers]
        await asyncio.gather(*tasks)
    
    async def stop(self):
        """Stop all connections."""
        self._running = False
        
        for handler in self._ws_handlers:
            await handler.disconnect()
        
        await self.normalizer.close_all()
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get the latest price for a symbol from buffer."""
        ticks = self.tick_buffer.get_symbol(symbol, 1)
        return ticks[0].price if ticks else None
    
    def get_price_history(self, symbol: str, count: int = 100) -> List[float]:
        """Get price history for a symbol."""
        return self.tick_buffer.get_prices(symbol, count)
    
    def get_ohlcv(
        self,
        symbol: str,
        interval_seconds: int = 60,
        count: int = 20,
    ) -> List[OHLCV]:
        """Get OHLCV candles from tick buffer."""
        return self.tick_buffer.aggregate_ohlcv(symbol, interval_seconds, count)
    
    async def get_arbitrage_prices(
        self,
        symbol: str,
        exchanges: Optional[List[str]] = None,
    ) -> Dict[str, float]:
        """Get prices across exchanges for arbitrage detection."""
        return await self.normalizer.fetch_multi_exchange_prices(symbol, exchanges)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of the data layer."""
        return {
            "running": self._running,
            "buffer_size": self.tick_buffer.size,
            "ws_handlers": len(self._ws_handlers),
            "exchanges": list(self.normalizer._exchanges.keys()),
        }


# ============================================================================
# Demo
# ============================================================================

if __name__ == "__main__":
    import random
    
    print("=== Data Ingestion Layer Demo ===\n")
    
    # Create layer
    layer = DataIngestionLayer(buffer_size=1000)
    
    # Simulate ticks (since we may not have websockets installed)
    print("Simulating tick data...")
    base_price = 42000.0
    
    for i in range(100):
        change = random.uniform(-50, 50)
        tick = Tick(
            symbol="BTC/USDT",
            exchange="binance",
            price=base_price + change,
            volume=random.uniform(0.1, 2.0),
            timestamp=time.time() - (100 - i),
            side=random.choice(["buy", "sell"]),
        )
        layer.tick_buffer.add(tick)
        base_price += change * 0.1  # Slight drift
    
    print(f"Buffer size: {layer.tick_buffer.size}")
    
    # Get recent prices
    prices = layer.get_price_history("BTC/USDT", 10)
    print(f"\nLast 10 prices: {[f'${p:.2f}' for p in prices[-5:]]}")
    
    # Aggregate to OHLCV
    candles = layer.get_ohlcv("BTC/USDT", interval_seconds=20, count=5)
    print(f"\nAggregated {len(candles)} candles:")
    for c in candles[-3:]:
        print(f"  O:{c.open:.2f} H:{c.high:.2f} L:{c.low:.2f} C:{c.close:.2f} V:{c.volume:.2f}")
    
    # Status
    print(f"\nStatus: {layer.get_status()}")
    
    print("\n✓ Data ingestion layer ready for WebSocket integration")
    print("  Install: pip install websockets ccxt")
