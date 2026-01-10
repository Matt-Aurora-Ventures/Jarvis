"""
Real-Time Staking Updates
Prompt #46: WebSocket server for live staking data
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
import uuid
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter
import redis.asyncio as redis

logger = logging.getLogger(__name__)


# =============================================================================
# EVENT TYPES
# =============================================================================

class EventType(str, Enum):
    # Pool events
    POOL_UPDATED = "pool.updated"
    POOL_TVL_CHANGED = "pool.tvl_changed"
    POOL_APY_CHANGED = "pool.apy_changed"

    # Staking events
    STAKE_CREATED = "stake.created"
    STAKE_UPDATED = "stake.updated"
    STAKE_WITHDRAWN = "stake.withdrawn"

    # Reward events
    REWARDS_ACCRUED = "rewards.accrued"
    REWARDS_CLAIMED = "rewards.claimed"

    # Price events
    PRICE_UPDATED = "price.updated"
    TOKEN_PRICE = "token.price"

    # Trade events
    TRADE_EXECUTED = "trade.executed"
    TRADE_FAILED = "trade.failed"

    # Governance events
    PROPOSAL_CREATED = "proposal.created"
    PROPOSAL_UPDATED = "proposal.updated"
    VOTE_CAST = "vote.cast"

    # System events
    SYSTEM_ALERT = "system.alert"
    MAINTENANCE = "system.maintenance"


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class WebSocketClient:
    """Connected WebSocket client"""
    id: str
    websocket: WebSocket
    wallet: Optional[str] = None
    subscriptions: Set[str] = field(default_factory=set)
    connected_at: datetime = field(default_factory=datetime.utcnow)
    last_ping: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """An event to broadcast"""
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    target_wallets: Optional[List[str]] = None  # None = broadcast to all
    channel: str = "global"  # Channel for filtering


# =============================================================================
# CONNECTION MANAGER
# =============================================================================

class ConnectionManager:
    """Manages WebSocket connections and message routing"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self.clients: Dict[str, WebSocketClient] = {}
        self.wallet_clients: Dict[str, Set[str]] = {}  # wallet -> client_ids
        self.channel_clients: Dict[str, Set[str]] = {}  # channel -> client_ids

        # Event handlers
        self._handlers: Dict[EventType, List[Callable]] = {}

        # Stats
        self.total_connections = 0
        self.total_messages_sent = 0

    async def connect(self):
        """Initialize Redis connection"""
        self._redis = await redis.from_url(self.redis_url)
        logger.info("WebSocket connection manager initialized")

    async def disconnect(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()

    # =========================================================================
    # CLIENT MANAGEMENT
    # =========================================================================

    async def add_client(
        self,
        websocket: WebSocket,
        wallet: Optional[str] = None
    ) -> WebSocketClient:
        """Add a new client connection"""
        client_id = str(uuid.uuid4())

        client = WebSocketClient(
            id=client_id,
            websocket=websocket,
            wallet=wallet
        )

        self.clients[client_id] = client
        self.total_connections += 1

        # Track by wallet
        if wallet:
            if wallet not in self.wallet_clients:
                self.wallet_clients[wallet] = set()
            self.wallet_clients[wallet].add(client_id)

        logger.info(f"Client {client_id} connected (wallet: {wallet})")

        # Send welcome message
        await self.send_to_client(client_id, {
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat()
        })

        return client

    async def remove_client(self, client_id: str):
        """Remove a client connection"""
        client = self.clients.get(client_id)
        if not client:
            return

        # Remove from wallet tracking
        if client.wallet and client.wallet in self.wallet_clients:
            self.wallet_clients[client.wallet].discard(client_id)
            if not self.wallet_clients[client.wallet]:
                del self.wallet_clients[client.wallet]

        # Remove from channels
        for channel, clients in self.channel_clients.items():
            clients.discard(client_id)

        del self.clients[client_id]
        logger.info(f"Client {client_id} disconnected")

    async def authenticate_client(
        self,
        client_id: str,
        wallet: str,
        signature: str
    ) -> bool:
        """Authenticate a client with wallet signature"""
        client = self.clients.get(client_id)
        if not client:
            return False

        # Verify signature (in production, verify against message)
        if not await self._verify_signature(wallet, signature):
            return False

        client.wallet = wallet

        if wallet not in self.wallet_clients:
            self.wallet_clients[wallet] = set()
        self.wallet_clients[wallet].add(client_id)

        await self.send_to_client(client_id, {
            "type": "authenticated",
            "wallet": wallet
        })

        logger.info(f"Client {client_id} authenticated as {wallet}")
        return True

    # =========================================================================
    # SUBSCRIPTIONS
    # =========================================================================

    async def subscribe(
        self,
        client_id: str,
        channels: List[str]
    ):
        """Subscribe client to channels"""
        client = self.clients.get(client_id)
        if not client:
            return

        for channel in channels:
            client.subscriptions.add(channel)

            if channel not in self.channel_clients:
                self.channel_clients[channel] = set()
            self.channel_clients[channel].add(client_id)

        await self.send_to_client(client_id, {
            "type": "subscribed",
            "channels": channels
        })

        logger.debug(f"Client {client_id} subscribed to {channels}")

    async def unsubscribe(
        self,
        client_id: str,
        channels: List[str]
    ):
        """Unsubscribe client from channels"""
        client = self.clients.get(client_id)
        if not client:
            return

        for channel in channels:
            client.subscriptions.discard(channel)
            if channel in self.channel_clients:
                self.channel_clients[channel].discard(client_id)

        await self.send_to_client(client_id, {
            "type": "unsubscribed",
            "channels": channels
        })

    # =========================================================================
    # MESSAGING
    # =========================================================================

    async def send_to_client(
        self,
        client_id: str,
        message: Dict[str, Any]
    ):
        """Send message to a specific client"""
        client = self.clients.get(client_id)
        if not client:
            return

        try:
            await client.websocket.send_json(message)
            self.total_messages_sent += 1
        except Exception as e:
            logger.error(f"Failed to send to client {client_id}: {e}")
            await self.remove_client(client_id)

    async def send_to_wallet(
        self,
        wallet: str,
        message: Dict[str, Any]
    ):
        """Send message to all connections for a wallet"""
        client_ids = self.wallet_clients.get(wallet, set())
        for client_id in list(client_ids):
            await self.send_to_client(client_id, message)

    async def send_to_channel(
        self,
        channel: str,
        message: Dict[str, Any]
    ):
        """Send message to all subscribers of a channel"""
        client_ids = self.channel_clients.get(channel, set())
        for client_id in list(client_ids):
            await self.send_to_client(client_id, message)

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        for client_id in list(self.clients.keys()):
            await self.send_to_client(client_id, message)

    async def publish_event(self, event: Event):
        """Publish an event to appropriate recipients"""
        message = {
            "type": event.type.value,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
            "channel": event.channel
        }

        # If target wallets specified, send only to them
        if event.target_wallets:
            for wallet in event.target_wallets:
                await self.send_to_wallet(wallet, message)
        else:
            # Send to channel subscribers
            await self.send_to_channel(event.channel, message)

        # Also publish to Redis for multi-instance support
        await self._publish_to_redis(event)

        # Call registered handlers
        await self._call_handlers(event)

    async def _publish_to_redis(self, event: Event):
        """Publish event to Redis for cross-instance communication"""
        if not self._redis:
            return

        await self._redis.publish(
            f"ws:events:{event.channel}",
            json.dumps({
                "type": event.type.value,
                "data": event.data,
                "timestamp": event.timestamp.isoformat(),
                "target_wallets": event.target_wallets
            })
        )

    async def _call_handlers(self, event: Event):
        """Call registered event handlers"""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")

    # =========================================================================
    # HANDLER REGISTRATION
    # =========================================================================

    def on_event(self, event_type: EventType, handler: Callable):
        """Register an event handler"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    # =========================================================================
    # MESSAGE HANDLING
    # =========================================================================

    async def handle_message(
        self,
        client_id: str,
        message: Dict[str, Any]
    ):
        """Handle incoming message from client"""
        msg_type = message.get("type")

        if msg_type == "ping":
            await self._handle_ping(client_id)

        elif msg_type == "authenticate":
            wallet = message.get("wallet")
            signature = message.get("signature")
            await self.authenticate_client(client_id, wallet, signature)

        elif msg_type == "subscribe":
            channels = message.get("channels", [])
            await self.subscribe(client_id, channels)

        elif msg_type == "unsubscribe":
            channels = message.get("channels", [])
            await self.unsubscribe(client_id, channels)

        else:
            logger.warning(f"Unknown message type: {msg_type}")

    async def _handle_ping(self, client_id: str):
        """Handle ping message"""
        client = self.clients.get(client_id)
        if client:
            client.last_ping = datetime.utcnow()
            await self.send_to_client(client_id, {"type": "pong"})

    # =========================================================================
    # HELPERS
    # =========================================================================

    async def _verify_signature(
        self,
        wallet: str,
        signature: str
    ) -> bool:
        """Verify wallet signature"""
        # In production, verify against expected message
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        return {
            "total_connections": self.total_connections,
            "active_connections": len(self.clients),
            "authenticated_wallets": len(self.wallet_clients),
            "channels": list(self.channel_clients.keys()),
            "total_messages_sent": self.total_messages_sent
        }


# =============================================================================
# STAKING EVENT PUBLISHER
# =============================================================================

class StakingEventPublisher:
    """Publishes staking-related events"""

    def __init__(self, manager: ConnectionManager):
        self.manager = manager

    async def publish_stake_created(
        self,
        wallet: str,
        pool_id: str,
        amount: int,
        signature: str
    ):
        """Publish stake created event"""
        event = Event(
            type=EventType.STAKE_CREATED,
            data={
                "wallet": wallet,
                "pool_id": pool_id,
                "amount": amount,
                "signature": signature
            },
            target_wallets=[wallet],
            channel=f"pool:{pool_id}"
        )
        await self.manager.publish_event(event)

        # Also publish pool update
        await self.publish_pool_tvl_changed(pool_id)

    async def publish_stake_withdrawn(
        self,
        wallet: str,
        pool_id: str,
        amount: int,
        rewards_claimed: int,
        signature: str
    ):
        """Publish stake withdrawn event"""
        event = Event(
            type=EventType.STAKE_WITHDRAWN,
            data={
                "wallet": wallet,
                "pool_id": pool_id,
                "amount": amount,
                "rewards_claimed": rewards_claimed,
                "signature": signature
            },
            target_wallets=[wallet],
            channel=f"pool:{pool_id}"
        )
        await self.manager.publish_event(event)

        await self.publish_pool_tvl_changed(pool_id)

    async def publish_rewards_accrued(
        self,
        wallet: str,
        pool_id: str,
        pending_rewards: int
    ):
        """Publish rewards accrued event"""
        event = Event(
            type=EventType.REWARDS_ACCRUED,
            data={
                "wallet": wallet,
                "pool_id": pool_id,
                "pending_rewards": pending_rewards
            },
            target_wallets=[wallet]
        )
        await self.manager.publish_event(event)

    async def publish_rewards_claimed(
        self,
        wallet: str,
        pool_id: str,
        amount: int,
        signature: str
    ):
        """Publish rewards claimed event"""
        event = Event(
            type=EventType.REWARDS_CLAIMED,
            data={
                "wallet": wallet,
                "pool_id": pool_id,
                "amount": amount,
                "signature": signature
            },
            target_wallets=[wallet]
        )
        await self.manager.publish_event(event)

    async def publish_pool_tvl_changed(self, pool_id: str):
        """Publish pool TVL change event"""
        # Get updated pool info (would query from staking program)
        pool_info = await self._get_pool_info(pool_id)

        event = Event(
            type=EventType.POOL_TVL_CHANGED,
            data={
                "pool_id": pool_id,
                "tvl": pool_info.get("tvl", 0),
                "stakers": pool_info.get("stakers", 0)
            },
            channel=f"pool:{pool_id}"
        )
        await self.manager.publish_event(event)

    async def publish_pool_apy_changed(
        self,
        pool_id: str,
        new_apy: int
    ):
        """Publish pool APY change event"""
        event = Event(
            type=EventType.POOL_APY_CHANGED,
            data={
                "pool_id": pool_id,
                "apy": new_apy
            },
            channel=f"pool:{pool_id}"
        )
        await self.manager.publish_event(event)

    async def publish_price_update(
        self,
        token_mint: str,
        price_usd: float,
        change_24h: float
    ):
        """Publish token price update"""
        event = Event(
            type=EventType.TOKEN_PRICE,
            data={
                "token": token_mint,
                "price_usd": price_usd,
                "change_24h": change_24h
            },
            channel="prices"
        )
        await self.manager.publish_event(event)

    async def publish_trade_executed(
        self,
        wallet: str,
        input_token: str,
        output_token: str,
        input_amount: int,
        output_amount: int,
        signature: str
    ):
        """Publish trade executed event"""
        event = Event(
            type=EventType.TRADE_EXECUTED,
            data={
                "wallet": wallet,
                "input_token": input_token,
                "output_token": output_token,
                "input_amount": input_amount,
                "output_amount": output_amount,
                "signature": signature
            },
            target_wallets=[wallet],
            channel="trades"
        )
        await self.manager.publish_event(event)

    async def _get_pool_info(self, pool_id: str) -> Dict[str, Any]:
        """Get pool info (placeholder)"""
        return {"tvl": 0, "stakers": 0}


# =============================================================================
# FASTAPI WEBSOCKET ROUTES
# =============================================================================

def create_websocket_routes(manager: ConnectionManager) -> APIRouter:
    """Create WebSocket routes"""
    router = APIRouter()

    @router.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        """Main WebSocket endpoint"""
        await websocket.accept()

        # Get wallet from query params if provided
        wallet = websocket.query_params.get("wallet")

        client = await manager.add_client(websocket, wallet)

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                await manager.handle_message(client.id, data)

        except WebSocketDisconnect:
            await manager.remove_client(client.id)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await manager.remove_client(client.id)

    @router.get("/ws/stats")
    async def get_stats():
        """Get WebSocket connection stats"""
        return manager.get_stats()

    return router


# =============================================================================
# REACT HOOKS (TypeScript)
# =============================================================================

REACT_HOOKS = """
import { useEffect, useState, useCallback, useRef } from 'react';

interface WebSocketMessage {
  type: string;
  data: any;
  timestamp: string;
  channel?: string;
}

interface UseStakingWebSocketOptions {
  wallet?: string;
  channels?: string[];
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export function useStakingWebSocket(options: UseStakingWebSocketOptions = {}) {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    const wsUrl = new URL('/ws', window.location.href);
    wsUrl.protocol = wsUrl.protocol.replace('http', 'ws');

    if (options.wallet) {
      wsUrl.searchParams.set('wallet', options.wallet);
    }

    const ws = new WebSocket(wsUrl.toString());

    ws.onopen = () => {
      setIsConnected(true);
      options.onConnect?.();

      // Subscribe to channels
      if (options.channels?.length) {
        ws.send(JSON.stringify({
          type: 'subscribe',
          channels: options.channels
        }));
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      options.onDisconnect?.();

      // Reconnect after 5 seconds
      reconnectTimeoutRef.current = setTimeout(connect, 5000);
    };

    ws.onerror = (error) => {
      options.onError?.(error);
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        setLastMessage(message);
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e);
      }
    };

    wsRef.current = ws;
  }, [options.wallet, options.channels]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const send = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  }, []);

  const subscribe = useCallback((channels: string[]) => {
    send({ type: 'subscribe', channels });
  }, [send]);

  const unsubscribe = useCallback((channels: string[]) => {
    send({ type: 'unsubscribe', channels });
  }, [send]);

  return {
    isConnected,
    lastMessage,
    send,
    subscribe,
    unsubscribe
  };
}

// Hook for pool-specific updates
export function usePoolUpdates(poolId: string) {
  const [tvl, setTvl] = useState<number>(0);
  const [apy, setApy] = useState<number>(0);
  const [stakers, setStakers] = useState<number>(0);

  const { lastMessage } = useStakingWebSocket({
    channels: [`pool:${poolId}`]
  });

  useEffect(() => {
    if (!lastMessage) return;

    switch (lastMessage.type) {
      case 'pool.tvl_changed':
        setTvl(lastMessage.data.tvl);
        setStakers(lastMessage.data.stakers);
        break;
      case 'pool.apy_changed':
        setApy(lastMessage.data.apy);
        break;
    }
  }, [lastMessage]);

  return { tvl, apy, stakers };
}

// Hook for user stake updates
export function useStakeUpdates(wallet: string, poolId: string) {
  const [pendingRewards, setPendingRewards] = useState<number>(0);
  const [lastClaim, setLastClaim] = useState<Date | null>(null);

  const { lastMessage } = useStakingWebSocket({
    wallet,
    channels: [`pool:${poolId}`]
  });

  useEffect(() => {
    if (!lastMessage) return;

    switch (lastMessage.type) {
      case 'rewards.accrued':
        if (lastMessage.data.wallet === wallet) {
          setPendingRewards(lastMessage.data.pending_rewards);
        }
        break;
      case 'rewards.claimed':
        if (lastMessage.data.wallet === wallet) {
          setPendingRewards(0);
          setLastClaim(new Date());
        }
        break;
    }
  }, [lastMessage, wallet]);

  return { pendingRewards, lastClaim };
}

// Hook for price updates
export function usePriceUpdates(tokenMint: string) {
  const [price, setPrice] = useState<number>(0);
  const [change24h, setChange24h] = useState<number>(0);

  const { lastMessage } = useStakingWebSocket({
    channels: ['prices']
  });

  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === 'token.price' && lastMessage.data.token === tokenMint) {
      setPrice(lastMessage.data.price_usd);
      setChange24h(lastMessage.data.change_24h);
    }
  }, [lastMessage, tokenMint]);

  return { price, change24h };
}

// Hook for trade notifications
export function useTradeNotifications(wallet: string) {
  const [trades, setTrades] = useState<any[]>([]);

  const { lastMessage } = useStakingWebSocket({
    wallet,
    channels: ['trades']
  });

  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === 'trade.executed' && lastMessage.data.wallet === wallet) {
      setTrades(prev => [lastMessage.data, ...prev.slice(0, 9)]);
    }
  }, [lastMessage, wallet]);

  return { trades };
}
"""


# =============================================================================
# PRICE FEED PUBLISHER
# =============================================================================

class PriceFeedPublisher:
    """Publishes real-time price updates"""

    def __init__(
        self,
        manager: ConnectionManager,
        update_interval: int = 10
    ):
        self.manager = manager
        self.update_interval = update_interval
        self._running = False

    async def start(self):
        """Start price feed publishing"""
        self._running = True
        asyncio.create_task(self._price_loop())
        logger.info("Price feed publisher started")

    async def stop(self):
        """Stop price feed publishing"""
        self._running = False

    async def _price_loop(self):
        """Background loop for price updates"""
        while self._running:
            try:
                prices = await self._fetch_prices()
                for token, data in prices.items():
                    event = Event(
                        type=EventType.TOKEN_PRICE,
                        data={
                            "token": token,
                            "price_usd": data["price"],
                            "change_24h": data["change_24h"]
                        },
                        channel="prices"
                    )
                    await self.manager.publish_event(event)

            except Exception as e:
                logger.error(f"Price feed error: {e}")

            await asyncio.sleep(self.update_interval)

    async def _fetch_prices(self) -> Dict[str, Dict[str, float]]:
        """Fetch current prices"""
        # In production, fetch from price oracle or DEX
        return {
            "KR8TIV": {"price": 0.001, "change_24h": 5.2},
            "SOL": {"price": 100.0, "change_24h": 2.1}
        }
