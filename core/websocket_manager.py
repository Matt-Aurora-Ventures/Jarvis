"""
WebSocket Connection Manager - Centralized WebSocket handling with auto-reconnect.
"""

import asyncio
import logging
import json
import time
from typing import Dict, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class ConnectionConfig:
    """Configuration for a WebSocket connection."""
    name: str
    url: str
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 10
    reconnect_delay: float = 1.0
    max_reconnect_delay: float = 60.0
    ping_interval: float = 30.0
    ping_timeout: float = 10.0
    message_handler: Optional[Callable] = None
    on_connect: Optional[Callable] = None
    on_disconnect: Optional[Callable] = None
    headers: Dict[str, str] = field(default_factory=dict)
    subscriptions: list = field(default_factory=list)


@dataclass
class ConnectionStats:
    """Statistics for a connection."""
    name: str
    state: ConnectionState
    connected_at: Optional[str] = None
    disconnected_at: Optional[str] = None
    reconnect_count: int = 0
    messages_received: int = 0
    messages_sent: int = 0
    last_message_at: Optional[str] = None
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0


class WebSocketConnection:
    """
    Managed WebSocket connection with auto-reconnect.

    Usage:
        config = ConnectionConfig(
            name="helius",
            url="wss://atlas-mainnet.helius-rpc.com",
            message_handler=handle_message
        )
        conn = WebSocketConnection(config)
        await conn.connect()
    """

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._reconnect_count = 0
        self._connected_at: Optional[datetime] = None
        self._message_count = 0
        self._sent_count = 0
        self._last_message_time: Optional[datetime] = None
        self._last_error: Optional[str] = None
        self._should_reconnect = True
        self._lock = asyncio.Lock()
        self._receive_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

    async def connect(self) -> bool:
        """Establish WebSocket connection."""
        async with self._lock:
            if self.state == ConnectionState.CONNECTED:
                return True

            self.state = ConnectionState.CONNECTING
            self._should_reconnect = True

            try:
                self.ws = await websockets.connect(
                    self.config.url,
                    extra_headers=self.config.headers,
                    ping_interval=self.config.ping_interval,
                    ping_timeout=self.config.ping_timeout
                )

                self.state = ConnectionState.CONNECTED
                self._connected_at = datetime.now(timezone.utc)
                self._reconnect_count = 0

                logger.info(f"WebSocket {self.config.name} connected to {self.config.url}")

                # Call on_connect callback
                if self.config.on_connect:
                    try:
                        await self.config.on_connect(self)
                    except Exception as e:
                        logger.error(f"on_connect callback failed: {e}")

                # Send any subscriptions
                for sub in self.config.subscriptions:
                    await self.send(sub)

                # Start receive loop
                self._receive_task = asyncio.create_task(self._receive_loop())

                return True

            except Exception as e:
                self._last_error = str(e)
                logger.error(f"WebSocket {self.config.name} connection failed: {e}")
                self.state = ConnectionState.FAILED

                if self.config.auto_reconnect:
                    asyncio.create_task(self._reconnect())

                return False

    async def disconnect(self):
        """Gracefully disconnect."""
        self._should_reconnect = False
        self.state = ConnectionState.DISCONNECTED

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ping_task:
            self._ping_task.cancel()

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

        if self.config.on_disconnect:
            try:
                await self.config.on_disconnect(self)
            except Exception as e:
                logger.error(f"on_disconnect callback failed: {e}")

        logger.info(f"WebSocket {self.config.name} disconnected")

    async def send(self, message: Any) -> bool:
        """Send a message."""
        if self.state != ConnectionState.CONNECTED or not self.ws:
            logger.warning(f"Cannot send - {self.config.name} not connected")
            return False

        try:
            if isinstance(message, dict):
                message = json.dumps(message)

            await self.ws.send(message)
            self._sent_count += 1
            return True

        except Exception as e:
            logger.error(f"Send failed on {self.config.name}: {e}")
            self._last_error = str(e)
            return False

    async def subscribe(self, subscription: dict):
        """Add and send a subscription."""
        self.config.subscriptions.append(subscription)
        if self.state == ConnectionState.CONNECTED:
            await self.send(subscription)

    async def _receive_loop(self):
        """Receive and handle messages."""
        try:
            while self.state == ConnectionState.CONNECTED and self.ws:
                try:
                    message = await self.ws.recv()
                    self._message_count += 1
                    self._last_message_time = datetime.now(timezone.utc)

                    # Parse JSON if possible
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        data = message

                    # Call message handler
                    if self.config.message_handler:
                        try:
                            result = self.config.message_handler(data)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception as e:
                            logger.error(f"Message handler error: {e}")

                except ConnectionClosed as e:
                    logger.warning(f"WebSocket {self.config.name} closed: {e}")
                    break

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Receive loop error on {self.config.name}: {e}")
            self._last_error = str(e)

        finally:
            if self._should_reconnect and self.config.auto_reconnect:
                asyncio.create_task(self._reconnect())

    async def _reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        if not self._should_reconnect:
            return

        self.state = ConnectionState.RECONNECTING

        while self._reconnect_count < self.config.max_reconnect_attempts:
            self._reconnect_count += 1

            delay = min(
                self.config.reconnect_delay * (2 ** (self._reconnect_count - 1)),
                self.config.max_reconnect_delay
            )

            logger.info(
                f"WebSocket {self.config.name} reconnecting in {delay:.1f}s "
                f"(attempt {self._reconnect_count}/{self.config.max_reconnect_attempts})"
            )

            await asyncio.sleep(delay)

            if not self._should_reconnect:
                return

            if await self.connect():
                return

        logger.error(f"WebSocket {self.config.name} max reconnect attempts reached")
        self.state = ConnectionState.FAILED

    def get_stats(self) -> ConnectionStats:
        """Get connection statistics."""
        uptime = 0.0
        if self._connected_at and self.state == ConnectionState.CONNECTED:
            uptime = (datetime.now(timezone.utc) - self._connected_at).total_seconds()

        return ConnectionStats(
            name=self.config.name,
            state=self.state,
            connected_at=self._connected_at.isoformat() if self._connected_at else None,
            reconnect_count=self._reconnect_count,
            messages_received=self._message_count,
            messages_sent=self._sent_count,
            last_message_at=self._last_message_time.isoformat() if self._last_message_time else None,
            last_error=self._last_error,
            uptime_seconds=uptime
        )


class WebSocketManager:
    """
    Centralized manager for multiple WebSocket connections.

    Usage:
        manager = WebSocketManager()

        manager.register("helius", ConnectionConfig(
            name="helius",
            url="wss://atlas-mainnet.helius-rpc.com",
            message_handler=handle_helius_message
        ))

        await manager.connect_all()
    """

    def __init__(self):
        self.connections: Dict[str, WebSocketConnection] = {}
        self._running = False

    def register(self, name: str, config: ConnectionConfig):
        """Register a new WebSocket connection."""
        if name in self.connections:
            logger.warning(f"Connection {name} already registered, replacing")

        self.connections[name] = WebSocketConnection(config)
        logger.info(f"Registered WebSocket connection: {name}")

    def unregister(self, name: str):
        """Unregister a connection."""
        if name in self.connections:
            del self.connections[name]

    async def connect(self, name: str) -> bool:
        """Connect a specific WebSocket."""
        if name not in self.connections:
            logger.error(f"Unknown connection: {name}")
            return False

        return await self.connections[name].connect()

    async def connect_all(self):
        """Connect all registered WebSockets."""
        self._running = True
        tasks = [conn.connect() for conn in self.connections.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def disconnect(self, name: str):
        """Disconnect a specific WebSocket."""
        if name in self.connections:
            await self.connections[name].disconnect()

    async def disconnect_all(self):
        """Disconnect all WebSockets."""
        self._running = False
        tasks = [conn.disconnect() for conn in self.connections.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def send(self, name: str, message: Any) -> bool:
        """Send a message to a specific WebSocket."""
        if name not in self.connections:
            logger.error(f"Unknown connection: {name}")
            return False

        return await self.connections[name].send(message)

    async def broadcast(self, message: Any) -> Dict[str, bool]:
        """Send a message to all connected WebSockets."""
        results = {}
        for name, conn in self.connections.items():
            results[name] = await conn.send(message)
        return results

    def get_connection(self, name: str) -> Optional[WebSocketConnection]:
        """Get a specific connection."""
        return self.connections.get(name)

    def get_all_stats(self) -> Dict[str, ConnectionStats]:
        """Get stats for all connections."""
        return {name: conn.get_stats() for name, conn in self.connections.items()}

    def get_status_summary(self) -> Dict:
        """Get a summary of all connection statuses."""
        stats = self.get_all_stats()

        connected = sum(1 for s in stats.values() if s.state == ConnectionState.CONNECTED)
        total = len(stats)
        total_messages = sum(s.messages_received for s in stats.values())

        return {
            'total_connections': total,
            'connected': connected,
            'disconnected': total - connected,
            'total_messages_received': total_messages,
            'connections': {
                name: {
                    'state': s.state.value,
                    'uptime_seconds': s.uptime_seconds,
                    'messages_received': s.messages_received
                }
                for name, s in stats.items()
            }
        }


# === HELIUS WEBSOCKET HELPER ===

def create_helius_config(
    api_key: str,
    accounts: list[str],
    message_handler: Callable,
    on_connect: Callable = None
) -> ConnectionConfig:
    """Create a Helius WebSocket configuration."""

    async def _on_connect(conn: WebSocketConnection):
        # Subscribe to account changes
        for account in accounts:
            await conn.send({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "accountSubscribe",
                "params": [
                    account,
                    {"encoding": "jsonParsed", "commitment": "confirmed"}
                ]
            })

        if on_connect:
            await on_connect(conn)

    return ConnectionConfig(
        name="helius",
        url=f"wss://atlas-mainnet.helius-rpc.com/?api-key={api_key}",
        message_handler=message_handler,
        on_connect=_on_connect,
        auto_reconnect=True,
        max_reconnect_attempts=20,
        ping_interval=30.0
    )


# === SINGLETON ===

_manager: Optional[WebSocketManager] = None

def get_websocket_manager() -> WebSocketManager:
    """Get singleton WebSocket manager."""
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager
