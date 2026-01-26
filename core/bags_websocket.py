"""
Bags.fm WebSocket Client - Real-time Price Feeds and Graduation Monitoring

REQ-004: WebSocket price feed integration for bags.fm

Features:
- Real-time token price updates
- Graduation monitoring (bonding curve completion)
- Auto-reconnection with exponential backoff
- Price history caching for charts
- Connection statistics

Usage:
    from core.bags_websocket import get_bags_websocket

    client = get_bags_websocket()
    client.on_price_update = my_price_handler
    client.on_graduation = my_graduation_handler

    await client.connect()
    await client.subscribe("TokenMint123")
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class PriceData:
    """Price data from WebSocket feed."""
    mint: str
    price: float
    price_usd: float
    volume_24h: float
    timestamp: datetime
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraduationEvent:
    """Token graduation event (bonding curve complete)."""
    mint: str
    raydium_pool: str
    bonding_curve_complete: bool
    timestamp: datetime
    raw: Dict[str, Any] = field(default_factory=dict)


class BagsWebSocketClient:
    """
    WebSocket client for Bags.fm real-time price feeds.

    Provides:
    - Real-time token price updates
    - Graduation event monitoring
    - Auto-reconnection with backoff
    - Price caching and history
    """

    DEFAULT_WS_URL = "wss://public-api-v2.bags.fm/ws"

    def __init__(
        self,
        ws_url: Optional[str] = None,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
        history_limit: int = 100,
    ):
        """
        Initialize WebSocket client.

        Args:
            ws_url: WebSocket URL (default: bags.fm public API)
            auto_reconnect: Auto-reconnect on disconnect
            max_reconnect_attempts: Max reconnection attempts
            reconnect_delay: Initial reconnect delay (seconds)
            max_reconnect_delay: Max reconnect delay (seconds)
            history_limit: Max price history entries per token
        """
        self.ws_url = ws_url or os.environ.get("BAGS_WS_URL", self.DEFAULT_WS_URL)
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay
        self.history_limit = history_limit

        # Connection state
        self._ws = None
        self._connected = False
        self._should_reconnect = True
        self._reconnect_attempts = 0
        self._receive_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

        # Subscriptions
        self.subscriptions: Set[str] = set()
        self._graduation_subscribed = False

        # Price caching
        self._price_cache: Dict[str, Dict[str, Any]] = {}
        self._price_history: Dict[str, List[Dict[str, Any]]] = {}
        self._enable_history = False

        # Statistics
        self._messages_received = 0
        self._reconnect_count = 0
        self._connected_at: Optional[datetime] = None
        self._last_message_at: Optional[datetime] = None

        # Callbacks
        self.on_price_update: Optional[Callable[[Dict], Any]] = None
        self.on_graduation: Optional[Callable[[Dict], Any]] = None
        self.on_connect: Optional[Callable[[], Any]] = None
        self.on_disconnect: Optional[Callable[[], Any]] = None

    @property
    def connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected and self._ws is not None

    async def connect(self) -> bool:
        """
        Establish WebSocket connection.

        Returns:
            True if connected successfully
        """
        async with self._lock:
            if self._connected:
                return True

            self._should_reconnect = True

            try:
                import websockets

                logger.info(f"Connecting to Bags.fm WebSocket: {self.ws_url}")

                self._ws = await websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                )

                self._connected = True
                self._connected_at = datetime.now(timezone.utc)
                self._reconnect_attempts = 0

                logger.info("Bags.fm WebSocket connected")

                # Call on_connect callback
                if self.on_connect:
                    try:
                        result = self.on_connect()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"on_connect callback error: {e}")

                # Re-subscribe to tokens
                for mint in list(self.subscriptions):
                    await self._send_subscribe(mint)

                # Re-subscribe to graduations
                if self._graduation_subscribed:
                    await self._send_graduation_subscribe()

                # Start receive loop
                self._receive_task = asyncio.create_task(self._receive_loop())

                return True

            except ImportError:
                logger.error("websockets package not installed: pip install websockets")
                return False
            except Exception as e:
                logger.error(f"WebSocket connection failed: {e}")
                self._connected = False

                if self.auto_reconnect:
                    asyncio.create_task(self._reconnect())

                return False

    async def disconnect(self):
        """Gracefully disconnect WebSocket."""
        self._should_reconnect = False
        self._connected = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        logger.info("Bags.fm WebSocket disconnected")

    async def subscribe(self, mint: str):
        """
        Subscribe to price updates for a token.

        Args:
            mint: Token mint address
        """
        self.subscriptions.add(mint)

        if self._connected:
            await self._send_subscribe(mint)

    async def unsubscribe(self, mint: str):
        """
        Unsubscribe from price updates.

        Args:
            mint: Token mint address
        """
        self.subscriptions.discard(mint)

        if self._connected:
            await self._send_unsubscribe(mint)

    async def subscribe_graduations(self):
        """Subscribe to token graduation events."""
        self._graduation_subscribed = True

        if self._connected:
            await self._send_graduation_subscribe()

    async def _send_subscribe(self, mint: str):
        """Send subscription message."""
        if self._ws:
            try:
                await self._ws.send(json.dumps({
                    "type": "subscribe",
                    "channel": "price",
                    "mint": mint,
                }))
            except Exception as e:
                logger.error(f"Failed to subscribe to {mint}: {e}")

    async def _send_unsubscribe(self, mint: str):
        """Send unsubscription message."""
        if self._ws:
            try:
                await self._ws.send(json.dumps({
                    "type": "unsubscribe",
                    "channel": "price",
                    "mint": mint,
                }))
            except Exception as e:
                logger.error(f"Failed to unsubscribe from {mint}: {e}")

    async def _send_graduation_subscribe(self):
        """Send graduation subscription message."""
        if self._ws:
            try:
                await self._ws.send(json.dumps({
                    "type": "subscribe",
                    "channel": "graduations",
                }))
            except Exception as e:
                logger.error(f"Failed to subscribe to graduations: {e}")

    async def _receive_loop(self):
        """Receive and process WebSocket messages."""
        try:
            while self._connected and self._ws:
                try:
                    message = await self._ws.recv()

                    # Parse message
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue

                    # Handle message (increments counter internally)
                    await self._handle_message(data)

                except Exception as e:
                    if self._connected:
                        logger.warning(f"WebSocket receive error: {e}")
                    break

        except asyncio.CancelledError:
            pass
        finally:
            if self._should_reconnect and self.auto_reconnect:
                asyncio.create_task(self._on_disconnect())

    async def _handle_message(self, data: Dict[str, Any]):
        """
        Handle incoming WebSocket message.

        Args:
            data: Parsed message data
        """
        # Increment message counter (for direct _handle_message calls in tests)
        self._messages_received += 1
        self._last_message_at = datetime.now(timezone.utc)

        msg_type = data.get("type", "")

        # Price update
        if msg_type == "price" or "price" in data:
            mint = data.get("mint", "")
            if mint:
                price_info = {
                    "price": float(data.get("price", 0)),
                    "price_usd": float(data.get("price_usd", data.get("priceUsd", 0))),
                    "volume_24h": float(data.get("volume_24h", data.get("volume24h", 0))),
                    "timestamp": datetime.now(timezone.utc),
                }

                # Update cache
                self._price_cache[mint] = price_info

                # Update history if enabled
                if self._enable_history:
                    if mint not in self._price_history:
                        self._price_history[mint] = []
                    self._price_history[mint].append({
                        **price_info,
                        "timestamp": price_info["timestamp"].timestamp(),
                    })
                    # Limit history size
                    if len(self._price_history[mint]) > self.history_limit:
                        self._price_history[mint] = self._price_history[mint][-self.history_limit:]

                # Call callback
                if self.on_price_update:
                    try:
                        result = self.on_price_update({**data, **price_info, "mint": mint})
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"on_price_update callback error: {e}")

        # Graduation event
        elif msg_type == "graduation" or data.get("bonding_curve_complete"):
            if self.on_graduation:
                try:
                    result = self.on_graduation(data)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"on_graduation callback error: {e}")

    async def _on_disconnect(self):
        """Handle disconnection and attempt reconnect."""
        self._connected = False

        # Call on_disconnect callback
        if self.on_disconnect:
            try:
                result = self.on_disconnect()
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"on_disconnect callback error: {e}")

        # Attempt reconnect
        if self._should_reconnect and self.auto_reconnect:
            await self._reconnect()

    async def _reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        if not self._should_reconnect:
            return

        while self._reconnect_attempts < self.max_reconnect_attempts:
            self._reconnect_attempts += 1
            self._reconnect_count += 1

            delay = min(
                self.reconnect_delay * (2 ** (self._reconnect_attempts - 1)),
                self.max_reconnect_delay,
            )

            logger.info(
                f"Reconnecting in {delay:.1f}s "
                f"(attempt {self._reconnect_attempts}/{self.max_reconnect_attempts})"
            )

            await asyncio.sleep(delay)

            if not self._should_reconnect:
                return

            if await self.connect():
                logger.info("Reconnected successfully")
                return

        logger.error("Max reconnection attempts reached")

    def get_latest_price(self, mint: str) -> Optional[Dict[str, Any]]:
        """
        Get latest cached price for a token.

        Args:
            mint: Token mint address

        Returns:
            Price data dict or None if not cached
        """
        return self._price_cache.get(mint)

    def get_price_history(self, mint: str) -> List[Dict[str, Any]]:
        """
        Get price history for a token.

        Args:
            mint: Token mint address

        Returns:
            List of price data points
        """
        return self._price_history.get(mint, [])

    def enable_history(self, enabled: bool = True):
        """Enable or disable price history tracking."""
        self._enable_history = enabled

    def get_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics.

        Returns:
            Dict with connection stats
        """
        uptime = 0.0
        if self._connected_at and self._connected:
            uptime = (datetime.now(timezone.utc) - self._connected_at).total_seconds()

        return {
            "connected": self._connected,
            "ws_url": self.ws_url,
            "subscriptions": list(self.subscriptions),
            "subscription_count": len(self.subscriptions),
            "graduation_subscribed": self._graduation_subscribed,
            "messages_received": self._messages_received,
            "reconnect_count": self._reconnect_count,
            "connected_at": self._connected_at.isoformat() if self._connected_at else None,
            "last_message_at": self._last_message_at.isoformat() if self._last_message_at else None,
            "uptime_seconds": uptime,
            "cached_prices": len(self._price_cache),
        }


# =============================================================================
# Price Feed Manager (High-level interface)
# =============================================================================


class BagsPriceFeedManager:
    """
    High-level manager for Bags.fm price feeds.

    Provides:
    - Multi-token price monitoring
    - Price change alerts
    - Integration with trading systems
    """

    def __init__(self, ws_client: Optional[BagsWebSocketClient] = None):
        self.ws = ws_client or BagsWebSocketClient()
        self._price_alerts: Dict[str, Dict] = {}
        self._alert_callbacks: List[Callable] = []

        # Set up price handler
        self.ws.on_price_update = self._on_price_update

    async def start(self):
        """Start price feed monitoring."""
        await self.ws.connect()

    async def stop(self):
        """Stop price feed monitoring."""
        await self.ws.disconnect()

    async def watch(self, mint: str):
        """
        Start watching a token's price.

        Args:
            mint: Token mint address
        """
        await self.ws.subscribe(mint)

    async def unwatch(self, mint: str):
        """
        Stop watching a token's price.

        Args:
            mint: Token mint address
        """
        await self.ws.unsubscribe(mint)

    def set_alert(
        self,
        mint: str,
        above: Optional[float] = None,
        below: Optional[float] = None,
        callback: Optional[Callable] = None,
    ):
        """
        Set price alert for a token.

        Args:
            mint: Token mint address
            above: Alert when price goes above this
            below: Alert when price goes below this
            callback: Optional callback for this specific alert
        """
        self._price_alerts[mint] = {
            "above": above,
            "below": below,
            "callback": callback,
            "triggered_above": False,
            "triggered_below": False,
        }

    def on_alert(self, callback: Callable):
        """Register a callback for price alerts."""
        self._alert_callbacks.append(callback)

    def _on_price_update(self, data: Dict):
        """Handle price update and check alerts."""
        mint = data.get("mint", "")
        price = data.get("price", 0)

        if mint in self._price_alerts:
            alert = self._price_alerts[mint]

            # Check above threshold
            if alert.get("above") and price >= alert["above"] and not alert.get("triggered_above"):
                alert["triggered_above"] = True
                self._trigger_alert(mint, "above", price, alert["above"])

            # Check below threshold
            if alert.get("below") and price <= alert["below"] and not alert.get("triggered_below"):
                alert["triggered_below"] = True
                self._trigger_alert(mint, "below", price, alert["below"])

    def _trigger_alert(self, mint: str, direction: str, price: float, threshold: float):
        """Trigger price alert callbacks."""
        alert_data = {
            "mint": mint,
            "direction": direction,
            "price": price,
            "threshold": threshold,
            "timestamp": datetime.now(timezone.utc),
        }

        # Call specific callback
        alert_config = self._price_alerts.get(mint, {})
        if alert_config.get("callback"):
            try:
                alert_config["callback"](alert_data)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

        # Call global callbacks
        for callback in self._alert_callbacks:
            try:
                callback(alert_data)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def get_price(self, mint: str) -> Optional[float]:
        """Get latest price for a token."""
        data = self.ws.get_latest_price(mint)
        return data.get("price") if data else None


# =============================================================================
# Singleton Factory
# =============================================================================


_bags_websocket: Optional[BagsWebSocketClient] = None
_bags_price_feed: Optional[BagsPriceFeedManager] = None


def get_bags_websocket() -> BagsWebSocketClient:
    """Get singleton WebSocket client."""
    global _bags_websocket
    if _bags_websocket is None:
        _bags_websocket = BagsWebSocketClient()
    return _bags_websocket


def get_bags_price_feed() -> BagsPriceFeedManager:
    """Get singleton price feed manager."""
    global _bags_price_feed
    if _bags_price_feed is None:
        _bags_price_feed = BagsPriceFeedManager()
    return _bags_price_feed


# =============================================================================
# Testing
# =============================================================================


if __name__ == "__main__":
    async def test():
        """Test WebSocket connection."""
        client = BagsWebSocketClient()

        def on_price(data):
            print(f"Price update: {data}")

        def on_grad(data):
            print(f"Graduation: {data}")

        client.on_price_update = on_price
        client.on_graduation = on_grad

        if await client.connect():
            print("Connected!")
            await client.subscribe_graduations()
            print(f"Stats: {client.get_stats()}")

            # Keep running for a bit
            await asyncio.sleep(30)

        await client.disconnect()

    asyncio.run(test())
