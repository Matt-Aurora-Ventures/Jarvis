"""
Enhanced Market Data WebSocket System
Provides real-time price, volume, trade, and order book updates via WebSocket
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from core.performance.websocket_optimizer import WebSocketOptimizer, ws_optimizer

logger = logging.getLogger(__name__)


# =============================================================================
# MARKET DATA TYPES
# =============================================================================

class MarketDataType(str, Enum):
    """Types of market data updates"""
    PRICE = "price"
    VOLUME = "volume"
    TRADE = "trade"
    ORDER_BOOK = "order_book"
    TICKER = "ticker"
    CANDLE = "candle"
    LIQUIDATION = "liquidation"


@dataclass
class PriceUpdate:
    """Real-time price update"""
    token_mint: str
    price_usd: float
    price_sol: Optional[float] = None
    change_24h: float = 0.0
    volume_24h: float = 0.0
    market_cap: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "jupiter"


@dataclass
class VolumeUpdate:
    """Real-time volume update"""
    token_mint: str
    volume_1h: float
    volume_24h: float
    trade_count_1h: int
    trade_count_24h: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TradeUpdate:
    """Individual trade execution"""
    token_mint: str
    side: str  # "buy" or "sell"
    price: float
    amount: float
    value_usd: float
    signature: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OrderBookUpdate:
    """Order book snapshot or update"""
    token_mint: str
    bids: List[List[float]]  # [[price, size], ...]
    asks: List[List[float]]  # [[price, size], ...]
    spread: float
    mid_price: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# =============================================================================
# MARKET DATA MANAGER
# =============================================================================

class MarketDataManager:
    """Manages market data subscriptions and streaming"""

    def __init__(self, optimizer: Optional[WebSocketOptimizer] = None):
        self.optimizer = optimizer or ws_optimizer

        # Client subscriptions: {client_id: {token_mint: {data_types}}}
        self._subscriptions: Dict[str, Dict[str, Set[MarketDataType]]] = {}

        # Active clients: {client_id: WebSocket}
        self._clients: Dict[str, WebSocket] = {}

        # Token subscribers: {token_mint: {client_ids}}
        self._token_subscribers: Dict[str, Set[str]] = {}

        # Last known prices (for diffing)
        self._last_prices: Dict[str, float] = {}

        # Price fetch tasks
        self._price_tasks: Dict[str, asyncio.Task] = {}

        # Stats
        self.total_connections = 0
        self.total_updates_sent = 0

        # Heartbeat tracking
        self._last_heartbeat: Dict[str, float] = {}
        self._heartbeat_interval = 30.0  # seconds

        # Reconnection tracking
        self._reconnect_counts: Dict[str, int] = {}
        self._max_reconnects = 5

    # =========================================================================
    # CLIENT MANAGEMENT
    # =========================================================================

    async def add_client(self, client_id: str, websocket: WebSocket):
        """Add new WebSocket client"""
        self._clients[client_id] = websocket
        self._subscriptions[client_id] = {}
        self.total_connections += 1
        self._last_heartbeat[client_id] = time.time()

        logger.info(f"Market data client connected: {client_id}")

        # Send welcome message
        await self._send_to_client(client_id, {
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "supported_types": [t.value for t in MarketDataType]
        })

    async def remove_client(self, client_id: str):
        """Remove WebSocket client and cleanup subscriptions"""
        if client_id not in self._clients:
            return

        # Unsubscribe from all tokens
        if client_id in self._subscriptions:
            for token_mint in list(self._subscriptions[client_id].keys()):
                await self._unsubscribe_token(client_id, token_mint)
            del self._subscriptions[client_id]

        # Remove client
        del self._clients[client_id]
        self._last_heartbeat.pop(client_id, None)
        self._reconnect_counts.pop(client_id, None)

        logger.info(f"Market data client disconnected: {client_id}")

    # =========================================================================
    # SUBSCRIPTION MANAGEMENT
    # =========================================================================

    async def subscribe(
        self,
        client_id: str,
        token_mints: List[str],
        data_types: Optional[List[MarketDataType]] = None
    ):
        """Subscribe client to token market data"""
        if client_id not in self._clients:
            return

        # Default to all data types
        if not data_types:
            data_types = [MarketDataType.PRICE, MarketDataType.VOLUME, MarketDataType.TRADE]

        for token_mint in token_mints:
            # Initialize subscription
            if token_mint not in self._subscriptions[client_id]:
                self._subscriptions[client_id][token_mint] = set()

            # Add data types
            self._subscriptions[client_id][token_mint].update(data_types)

            # Track token subscribers
            if token_mint not in self._token_subscribers:
                self._token_subscribers[token_mint] = set()
            self._token_subscribers[token_mint].add(client_id)

            # Start price feed for this token if not already running
            await self._ensure_price_feed(token_mint)

        await self._send_to_client(client_id, {
            "type": "subscribed",
            "tokens": token_mints,
            "data_types": [dt.value for dt in data_types],
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        # Send initial snapshot
        for token_mint in token_mints:
            await self._send_initial_snapshot(client_id, token_mint)

    async def unsubscribe(
        self,
        client_id: str,
        token_mints: List[str],
        data_types: Optional[List[MarketDataType]] = None
    ):
        """Unsubscribe client from token market data"""
        if client_id not in self._subscriptions:
            return

        for token_mint in token_mints:
            if token_mint not in self._subscriptions[client_id]:
                continue

            if data_types:
                # Remove specific data types
                self._subscriptions[client_id][token_mint] -= set(data_types)
                if not self._subscriptions[client_id][token_mint]:
                    await self._unsubscribe_token(client_id, token_mint)
            else:
                # Remove entire token subscription
                await self._unsubscribe_token(client_id, token_mint)

        await self._send_to_client(client_id, {
            "type": "unsubscribed",
            "tokens": token_mints,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

    async def _unsubscribe_token(self, client_id: str, token_mint: str):
        """Internal: Unsubscribe client from a specific token"""
        if token_mint in self._subscriptions.get(client_id, {}):
            del self._subscriptions[client_id][token_mint]

        # Remove from token subscribers
        if token_mint in self._token_subscribers:
            self._token_subscribers[token_mint].discard(client_id)

            # Stop price feed if no more subscribers
            if not self._token_subscribers[token_mint]:
                await self._stop_price_feed(token_mint)
                del self._token_subscribers[token_mint]

    # =========================================================================
    # MARKET DATA PUBLISHING
    # =========================================================================

    async def publish_price_update(self, update: PriceUpdate):
        """Publish price update to subscribers"""
        token_mint = update.token_mint

        # Check if price changed significantly (avoid spam)
        last_price = self._last_prices.get(token_mint, 0)
        price_change_pct = abs(update.price_usd - last_price) / last_price * 100 if last_price > 0 else 100

        if price_change_pct < 0.1 and last_price > 0:
            # Skip insignificant updates (< 0.1% change)
            return

        self._last_prices[token_mint] = update.price_usd

        message = {
            "type": MarketDataType.PRICE.value,
            "token": token_mint,
            "price_usd": update.price_usd,
            "price_sol": update.price_sol,
            "change_24h": update.change_24h,
            "volume_24h": update.volume_24h,
            "market_cap": update.market_cap,
            "source": update.source,
            "timestamp": update.timestamp.isoformat()
        }

        await self._broadcast_to_subscribers(token_mint, MarketDataType.PRICE, message)

    async def publish_volume_update(self, update: VolumeUpdate):
        """Publish volume update to subscribers"""
        message = {
            "type": MarketDataType.VOLUME.value,
            "token": update.token_mint,
            "volume_1h": update.volume_1h,
            "volume_24h": update.volume_24h,
            "trade_count_1h": update.trade_count_1h,
            "trade_count_24h": update.trade_count_24h,
            "timestamp": update.timestamp.isoformat()
        }

        await self._broadcast_to_subscribers(update.token_mint, MarketDataType.VOLUME, message)

    async def publish_trade_update(self, update: TradeUpdate):
        """Publish individual trade to subscribers"""
        message = {
            "type": MarketDataType.TRADE.value,
            "token": update.token_mint,
            "side": update.side,
            "price": update.price,
            "amount": update.amount,
            "value_usd": update.value_usd,
            "signature": update.signature,
            "timestamp": update.timestamp.isoformat()
        }

        await self._broadcast_to_subscribers(update.token_mint, MarketDataType.TRADE, message)

    async def publish_orderbook_update(self, update: OrderBookUpdate):
        """Publish order book update to subscribers"""
        message = {
            "type": MarketDataType.ORDER_BOOK.value,
            "token": update.token_mint,
            "bids": update.bids,
            "asks": update.asks,
            "spread": update.spread,
            "mid_price": update.mid_price,
            "timestamp": update.timestamp.isoformat()
        }

        await self._broadcast_to_subscribers(update.token_mint, MarketDataType.ORDER_BOOK, message)

    # =========================================================================
    # HEARTBEAT & RECONNECTION
    # =========================================================================

    async def send_heartbeats(self):
        """Send heartbeat to all clients that need it"""
        now = time.time()

        for client_id in list(self._clients.keys()):
            last_hb = self._last_heartbeat.get(client_id, 0)

            if now - last_hb >= self._heartbeat_interval:
                await self._send_heartbeat(client_id)
                self._last_heartbeat[client_id] = now

    async def _send_heartbeat(self, client_id: str):
        """Send heartbeat to specific client"""
        await self._send_to_client(client_id, {
            "type": "heartbeat",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "server_time": int(time.time() * 1000)
        })

    async def handle_pong(self, client_id: str):
        """Handle pong response from client"""
        self._last_heartbeat[client_id] = time.time()

    def track_reconnection(self, client_id: str) -> bool:
        """Track client reconnection attempts, return True if allowed"""
        count = self._reconnect_counts.get(client_id, 0) + 1
        self._reconnect_counts[client_id] = count

        if count > self._max_reconnects:
            logger.warning(f"Client {client_id} exceeded max reconnection attempts")
            return False

        return True

    def reset_reconnection_count(self, client_id: str):
        """Reset reconnection count after successful connection"""
        self._reconnect_counts[client_id] = 0

    # =========================================================================
    # PRICE FEED MANAGEMENT
    # =========================================================================

    async def _ensure_price_feed(self, token_mint: str):
        """Ensure price feed task is running for token"""
        if token_mint in self._price_tasks:
            return  # Already running

        task = asyncio.create_task(self._price_feed_loop(token_mint))
        self._price_tasks[token_mint] = task
        logger.info(f"Started price feed for {token_mint}")

    async def _stop_price_feed(self, token_mint: str):
        """Stop price feed task for token"""
        if token_mint not in self._price_tasks:
            return

        task = self._price_tasks[token_mint]
        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass

        del self._price_tasks[token_mint]
        logger.info(f"Stopped price feed for {token_mint}")

    async def _price_feed_loop(self, token_mint: str):
        """Background loop to fetch and publish price updates"""
        while True:
            try:
                # Fetch price data
                price_data = await self._fetch_price(token_mint)

                if price_data:
                    update = PriceUpdate(**price_data)
                    await self.publish_price_update(update)

                # Wait before next update (10 seconds)
                await asyncio.sleep(10)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Price feed error for {token_mint}: {e}")
                await asyncio.sleep(30)  # Back off on error

    async def _fetch_price(self, token_mint: str) -> Optional[Dict[str, Any]]:
        """Fetch current price for token"""
        try:
            # Try to import price fetcher
            from core.price.resilient_fetcher import get_token_price

            price_info = await get_token_price(token_mint)

            if price_info:
                return {
                    "token_mint": token_mint,
                    "price_usd": price_info.get("price_usd", 0),
                    "price_sol": price_info.get("price_sol"),
                    "change_24h": price_info.get("change_24h", 0),
                    "volume_24h": price_info.get("volume_24h", 0),
                    "market_cap": price_info.get("market_cap"),
                    "source": price_info.get("source", "unknown")
                }
        except ImportError:
            logger.warning("Price fetcher not available")
        except Exception as e:
            logger.error(f"Failed to fetch price for {token_mint}: {e}")

        return None

    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================

    async def _send_to_client(self, client_id: str, message: Dict[str, Any]):
        """Send message to specific client"""
        if client_id not in self._clients:
            return

        websocket = self._clients[client_id]

        try:
            await websocket.send_json(message)
            self.total_updates_sent += 1
        except Exception as e:
            logger.error(f"Failed to send to client {client_id}: {e}")
            await self.remove_client(client_id)

    async def _broadcast_to_subscribers(
        self,
        token_mint: str,
        data_type: MarketDataType,
        message: Dict[str, Any]
    ):
        """Broadcast message to all subscribers of token/data_type"""
        if token_mint not in self._token_subscribers:
            return

        for client_id in list(self._token_subscribers[token_mint]):
            # Check if client is subscribed to this data type
            if client_id in self._subscriptions:
                client_types = self._subscriptions[client_id].get(token_mint, set())
                if data_type in client_types:
                    await self._send_to_client(client_id, message)

    async def _send_initial_snapshot(self, client_id: str, token_mint: str):
        """Send initial data snapshot to newly subscribed client"""
        try:
            price_data = await self._fetch_price(token_mint)

            if price_data:
                await self._send_to_client(client_id, {
                    "type": "snapshot",
                    "token": token_mint,
                    "price": price_data,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
        except Exception as e:
            logger.error(f"Failed to send snapshot for {token_mint}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        return {
            "total_connections": self.total_connections,
            "active_clients": len(self._clients),
            "active_tokens": len(self._token_subscribers),
            "total_subscriptions": sum(
                len(tokens) for tokens in self._subscriptions.values()
            ),
            "total_updates_sent": self.total_updates_sent,
            "active_price_feeds": len(self._price_tasks)
        }


# =============================================================================
# GLOBAL MANAGER INSTANCE
# =============================================================================

_market_data_manager: Optional[MarketDataManager] = None


def get_market_data_manager() -> MarketDataManager:
    """Get or create market data manager singleton"""
    global _market_data_manager
    if _market_data_manager is None:
        _market_data_manager = MarketDataManager()
    return _market_data_manager


# =============================================================================
# WEBSOCKET ENDPOINT
# =============================================================================

async def market_data_websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for market data streaming"""
    manager = get_market_data_manager()

    await websocket.accept()
    await manager.add_client(client_id, websocket)

    try:
        while True:
            # Receive and handle client messages
            data = await websocket.receive_json()

            msg_type = data.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                await manager.handle_pong(client_id)

            elif msg_type == "subscribe":
                tokens = data.get("tokens", [])
                data_types_raw = data.get("data_types", [])
                data_types = [MarketDataType(dt) for dt in data_types_raw]
                await manager.subscribe(client_id, tokens, data_types)

            elif msg_type == "unsubscribe":
                tokens = data.get("tokens", [])
                data_types_raw = data.get("data_types")
                data_types = [MarketDataType(dt) for dt in data_types_raw] if data_types_raw else None
                await manager.unsubscribe(client_id, tokens, data_types)

            elif msg_type == "get_stats":
                stats = manager.get_stats()
                await websocket.send_json({"type": "stats", "data": stats})

    except WebSocketDisconnect:
        await manager.remove_client(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        await manager.remove_client(client_id)


# =============================================================================
# FASTAPI ROUTER
# =============================================================================

def create_market_data_router() -> APIRouter:
    """Create FastAPI router for market data WebSocket"""
    router = APIRouter()

    @router.websocket("/ws/market-data/{client_id}")
    async def websocket_market_data(websocket: WebSocket, client_id: str):
        """WebSocket endpoint for real-time market data"""
        await market_data_websocket_endpoint(websocket, client_id)

    @router.get("/ws/market-data/stats")
    async def get_market_data_stats():
        """Get market data WebSocket statistics"""
        manager = get_market_data_manager()
        return manager.get_stats()

    return router


# =============================================================================
# BACKGROUND HEARTBEAT TASK
# =============================================================================

async def start_heartbeat_task():
    """Start background task to send heartbeats"""
    manager = get_market_data_manager()

    while True:
        try:
            await manager.send_heartbeats()
            await asyncio.sleep(10)  # Check every 10 seconds
        except Exception as e:
            logger.error(f"Heartbeat task error: {e}")
            await asyncio.sleep(10)
