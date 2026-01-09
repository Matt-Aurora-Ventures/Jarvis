"""
WebSocket Server for Real-Time Price Streaming.

Provides real-time token price updates via WebSocket.
Supports multiple clients subscribing to different tokens.
"""

import asyncio
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Set

logger = logging.getLogger(__name__)

# Default WebSocket port
WS_PORT = 8766


@dataclass
class Subscription:
    """Represents a client's subscription to a token."""
    token_address: str
    last_price: Optional[float] = None
    subscribed_at: float = field(default_factory=time.time)


@dataclass
class PriceUpdate:
    """Price update message."""
    token_address: str
    price: float
    price_change_1h: float
    price_change_24h: float
    volume_24h: float
    liquidity: float
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "price_update",
            "data": {
                "token": self.token_address,
                "price": self.price,
                "priceChange1h": self.price_change_1h,
                "priceChange24h": self.price_change_24h,
                "volume24h": self.volume_24h,
                "liquidity": self.liquidity,
                "timestamp": self.timestamp,
            }
        }


class WebSocketPriceServer:
    """
    WebSocket server for real-time price streaming.

    Features:
    - Multi-client support
    - Per-token subscriptions
    - Efficient batch price fetching
    - Automatic reconnection handling
    """

    def __init__(self, port: int = WS_PORT, update_interval: float = 2.0):
        """
        Initialize the WebSocket server.

        Args:
            port: WebSocket server port
            update_interval: How often to fetch and broadcast prices (seconds)
        """
        self.port = port
        self.update_interval = update_interval
        self._clients: Dict[Any, Set[str]] = {}  # websocket -> set of subscribed tokens
        self._token_subscriptions: Dict[str, Set[Any]] = {}  # token -> set of subscribers
        self._last_prices: Dict[str, PriceUpdate] = {}
        self._running = False
        self._server = None
        self._price_task = None

    async def start(self) -> None:
        """Start the WebSocket server."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets library not installed: pip install websockets")
            return

        self._running = True

        # Start price update task
        self._price_task = asyncio.create_task(self._price_update_loop())

        # Start WebSocket server
        self._server = await websockets.serve(
            self._handle_client,
            "0.0.0.0",
            self.port,
            ping_interval=30,
            ping_timeout=10,
        )

        logger.info(f"WebSocket price server started on port {self.port}")

    async def stop(self) -> None:
        """Stop the WebSocket server."""
        self._running = False

        if self._price_task:
            self._price_task.cancel()
            try:
                await self._price_task
            except asyncio.CancelledError:
                pass

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        logger.info("WebSocket price server stopped")

    async def _handle_client(self, websocket, path) -> None:
        """Handle a WebSocket client connection."""
        client_id = id(websocket)
        self._clients[websocket] = set()

        logger.info(f"Client {client_id} connected")

        try:
            # Send welcome message
            await websocket.send(json.dumps({
                "type": "connected",
                "message": "Connected to Jarvis Price Stream",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))

            async for message in websocket:
                await self._handle_message(websocket, message)

        except Exception as e:
            logger.debug(f"Client {client_id} disconnected: {e}")
        finally:
            # Clean up subscriptions
            for token in self._clients.get(websocket, set()):
                if token in self._token_subscriptions:
                    self._token_subscriptions[token].discard(websocket)
                    if not self._token_subscriptions[token]:
                        del self._token_subscriptions[token]

            self._clients.pop(websocket, None)
            logger.info(f"Client {client_id} cleaned up")

    async def _handle_message(self, websocket, message: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid JSON"
            }))
            return

        msg_type = data.get("type")

        if msg_type == "subscribe":
            await self._handle_subscribe(websocket, data)
        elif msg_type == "unsubscribe":
            await self._handle_unsubscribe(websocket, data)
        elif msg_type == "ping":
            await websocket.send(json.dumps({"type": "pong"}))
        else:
            await websocket.send(json.dumps({
                "type": "error",
                "message": f"Unknown message type: {msg_type}"
            }))

    async def _handle_subscribe(self, websocket, data: Dict) -> None:
        """Handle subscription request."""
        tokens = data.get("tokens", [])
        if isinstance(tokens, str):
            tokens = [tokens]

        for token in tokens:
            if not token:
                continue

            token = token.strip()

            # Add to client's subscriptions
            self._clients[websocket].add(token)

            # Add to token's subscribers
            if token not in self._token_subscriptions:
                self._token_subscriptions[token] = set()
            self._token_subscriptions[token].add(websocket)

            # Send current price if available
            if token in self._last_prices:
                await websocket.send(json.dumps(self._last_prices[token].to_dict()))

        await websocket.send(json.dumps({
            "type": "subscribed",
            "tokens": list(self._clients[websocket]),
        }))

    async def _handle_unsubscribe(self, websocket, data: Dict) -> None:
        """Handle unsubscribe request."""
        tokens = data.get("tokens", [])
        if isinstance(tokens, str):
            tokens = [tokens]

        for token in tokens:
            if not token:
                continue

            token = token.strip()

            # Remove from client's subscriptions
            self._clients[websocket].discard(token)

            # Remove from token's subscribers
            if token in self._token_subscriptions:
                self._token_subscriptions[token].discard(websocket)
                if not self._token_subscriptions[token]:
                    del self._token_subscriptions[token]

        await websocket.send(json.dumps({
            "type": "unsubscribed",
            "tokens": list(self._clients[websocket]),
        }))

    async def _price_update_loop(self) -> None:
        """Main loop for fetching and broadcasting price updates."""
        while self._running:
            try:
                # Get all subscribed tokens
                tokens = list(self._token_subscriptions.keys())

                if tokens:
                    # Fetch prices
                    prices = await self._fetch_prices(tokens)

                    # Broadcast to subscribers
                    for token, price_data in prices.items():
                        if token in self._token_subscriptions:
                            self._last_prices[token] = price_data
                            message = json.dumps(price_data.to_dict())

                            # Send to all subscribers
                            for ws in list(self._token_subscriptions.get(token, [])):
                                try:
                                    await ws.send(message)
                                except Exception:
                                    pass  # Client disconnected

                await asyncio.sleep(self.update_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Price update error: {e}")
                await asyncio.sleep(5.0)

    async def _fetch_prices(self, tokens: list[str]) -> Dict[str, PriceUpdate]:
        """Fetch prices for tokens from DexScreener."""
        result = {}

        try:
            from core import dexscreener

            for token in tokens:
                try:
                    # Use DexScreener to get token data
                    pair_data = dexscreener.search_token(token)

                    if pair_data and pair_data.success and pair_data.data:
                        pairs = pair_data.data.get("pairs", [])
                        if pairs:
                            # Get the most liquid pair
                            best_pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0))

                            price_change = best_pair.get("priceChange", {})
                            liquidity = best_pair.get("liquidity", {})
                            volume = best_pair.get("volume", {})

                            result[token] = PriceUpdate(
                                token_address=token,
                                price=float(best_pair.get("priceUsd", 0) or 0),
                                price_change_1h=float(price_change.get("h1", 0) or 0),
                                price_change_24h=float(price_change.get("h24", 0) or 0),
                                volume_24h=float(volume.get("h24", 0) or 0),
                                liquidity=float(liquidity.get("usd", 0) or 0),
                                timestamp=datetime.now(timezone.utc).isoformat(),
                            )
                except Exception as e:
                    logger.debug(f"Failed to fetch price for {token}: {e}")

        except ImportError:
            logger.warning("DexScreener module not available")

        return result


# Global server instance
_server: Optional[WebSocketPriceServer] = None
_server_thread: Optional[threading.Thread] = None


async def _run_server(port: int, update_interval: float) -> None:
    """Run the WebSocket server in an event loop."""
    global _server
    _server = WebSocketPriceServer(port=port, update_interval=update_interval)
    await _server.start()

    # Keep running until stopped
    while _server._running:
        await asyncio.sleep(1)


def start_server(port: int = WS_PORT, update_interval: float = 2.0) -> bool:
    """
    Start the WebSocket price server in a background thread.

    Args:
        port: WebSocket server port
        update_interval: Price update interval in seconds

    Returns:
        True if started successfully
    """
    global _server_thread

    if _server_thread and _server_thread.is_alive():
        logger.warning("WebSocket server already running")
        return True

    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_run_server(port, update_interval))
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
        finally:
            loop.close()

    _server_thread = threading.Thread(target=run, daemon=True)
    _server_thread.start()

    logger.info(f"WebSocket price server starting on port {port}")
    return True


def stop_server() -> None:
    """Stop the WebSocket price server."""
    global _server

    if _server:
        # Signal the server to stop
        _server._running = False

    logger.info("WebSocket price server stopping")


def is_running() -> bool:
    """Check if the server is running."""
    return _server is not None and _server._running


# CLI entry point for testing
if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    port = int(sys.argv[1]) if len(sys.argv) > 1 else WS_PORT

    print(f"Starting WebSocket price server on port {port}")
    print("Press Ctrl+C to stop")

    async def main():
        server = WebSocketPriceServer(port=port)
        await server.start()

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await server.stop()

    asyncio.run(main())
