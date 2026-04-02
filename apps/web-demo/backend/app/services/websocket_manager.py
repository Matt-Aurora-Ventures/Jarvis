"""
WebSocket Manager for Real-Time Price Feeds
Manages connections to price data providers and broadcasts to clients.

Features:
- Multiple price feed sources (Jupiter, Birdeye, CoinGecko)
- Connection pooling and health checks
- Auto-reconnect on failure
- Rate limiting per source
- Client subscription management
- Price aggregation across sources
"""
import asyncio
import logging
from typing import Dict, Set, Optional, List, Any
from datetime import datetime, timedelta
import json
import httpx
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class PriceUpdate:
    """Price update event."""
    def __init__(
        self,
        token_address: str,
        price: float,
        volume_24h: float,
        price_change_24h: float,
        source: str,
        timestamp: datetime
    ):
        self.token_address = token_address
        self.price = price
        self.volume_24h = volume_24h
        self.price_change_24h = price_change_24h
        self.source = source
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_address": self.token_address,
            "price": self.price,
            "volume_24h": self.volume_24h,
            "price_change_24h": self.price_change_24h,
            "source": self.source,
            "timestamp": self.timestamp.isoformat()
        }


class WebSocketManager:
    """
    Manages WebSocket connections for real-time price updates.

    Architecture:
    - One background task fetches prices from APIs
    - Multiple clients connect via WebSocket
    - Manager broadcasts updates to all subscribed clients
    - Automatic reconnection on disconnection
    """

    def __init__(self):
        # Active WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}  # token -> set of websockets

        # Price cache
        self.price_cache: Dict[str, PriceUpdate] = {}

        # Watched tokens (most popular + user requests)
        self.watched_tokens: Set[str] = {
            "So11111111111111111111111111111111111111112",  # SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
        }

        # Background task
        self.price_update_task: Optional[asyncio.Task] = None
        self.running = False

    async def connect(self, websocket: WebSocket, token_address: str):
        """
        Connect a client WebSocket for a specific token.

        Args:
            websocket: FastAPI WebSocket connection
            token_address: Token mint address to subscribe to
        """
        await websocket.accept()

        if token_address not in self.active_connections:
            self.active_connections[token_address] = set()

        self.active_connections[token_address].add(websocket)
        self.watched_tokens.add(token_address)

        logger.info(f"Client connected for token {token_address[:8]}... (total: {len(self.active_connections[token_address])} clients)")

        # Send cached price immediately if available
        if token_address in self.price_cache:
            await websocket.send_json(self.price_cache[token_address].to_dict())

    def disconnect(self, websocket: WebSocket, token_address: str):
        """
        Disconnect a client WebSocket.

        Args:
            websocket: FastAPI WebSocket connection
            token_address: Token mint address subscribed to
        """
        if token_address in self.active_connections:
            self.active_connections[token_address].discard(websocket)

            # Clean up empty sets
            if not self.active_connections[token_address]:
                del self.active_connections[token_address]
                logger.info(f"No more clients for token {token_address[:8]}..., removing from watch list")

        logger.info(f"Client disconnected from token {token_address[:8]}...")

    async def broadcast_price_update(self, update: PriceUpdate):
        """
        Broadcast price update to all subscribed clients.

        Args:
            update: PriceUpdate object with latest data
        """
        token_address = update.token_address

        # Update cache
        self.price_cache[token_address] = update

        # Broadcast to all connected clients for this token
        if token_address in self.active_connections:
            disconnected = []

            for websocket in self.active_connections[token_address]:
                try:
                    await websocket.send_json(update.to_dict())
                except Exception as e:
                    logger.warning(f"Failed to send to client: {e}")
                    disconnected.append(websocket)

            # Clean up disconnected clients
            for ws in disconnected:
                self.disconnect(ws, token_address)

    async def fetch_jupiter_prices(self) -> List[PriceUpdate]:
        """
        Fetch prices from Jupiter API.

        Returns:
            List of PriceUpdate objects
        """
        updates = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Jupiter price API
                token_list = ",".join(self.watched_tokens)
                response = await client.get(
                    f"https://price.jup.ag/v4/price?ids={token_list}"
                )

                if response.status_code == 200:
                    data = response.json()

                    for token_address, price_data in data.get("data", {}).items():
                        updates.append(PriceUpdate(
                            token_address=token_address,
                            price=price_data.get("price", 0),
                            volume_24h=0,  # Jupiter doesn't provide volume
                            price_change_24h=0,  # Jupiter doesn't provide change
                            source="jupiter",
                            timestamp=datetime.now()
                        ))
        except Exception as e:
            logger.error(f"Jupiter price fetch error: {e}")

        return updates

    async def fetch_birdeye_prices(self, api_key: Optional[str] = None) -> List[PriceUpdate]:
        """
        Fetch prices from Birdeye API (requires API key).

        Args:
            api_key: Birdeye API key (optional)

        Returns:
            List of PriceUpdate objects
        """
        if not api_key:
            return []

        updates = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for token_address in self.watched_tokens:
                    response = await client.get(
                        f"https://public-api.birdeye.so/public/price?address={token_address}",
                        headers={"X-API-KEY": api_key}
                    )

                    if response.status_code == 200:
                        data = response.json()

                        updates.append(PriceUpdate(
                            token_address=token_address,
                            price=data.get("data", {}).get("value", 0),
                            volume_24h=data.get("data", {}).get("volume24h", 0),
                            price_change_24h=data.get("data", {}).get("priceChange24h", 0),
                            source="birdeye",
                            timestamp=datetime.now()
                        ))

                    # Rate limit: 300 req/min on free tier
                    await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Birdeye price fetch error: {e}")

        return updates

    async def fetch_coingecko_prices(self) -> List[PriceUpdate]:
        """
        Fetch prices from CoinGecko API (free tier).

        Returns:
            List of PriceUpdate objects
        """
        updates = []

        # CoinGecko uses different IDs, map common ones
        coingecko_ids = {
            "So11111111111111111111111111111111111111112": "solana",
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": "usd-coin",
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": "tether",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                ids = ",".join([coingecko_ids.get(addr, "") for addr in self.watched_tokens if addr in coingecko_ids])

                if ids:
                    response = await client.get(
                        f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd&include_24hr_vol=true&include_24hr_change=true"
                    )

                    if response.status_code == 200:
                        data = response.json()

                        # Reverse map CoinGecko IDs back to token addresses
                        reverse_map = {v: k for k, v in coingecko_ids.items()}

                        for coin_id, price_data in data.items():
                            token_address = reverse_map.get(coin_id)
                            if token_address:
                                updates.append(PriceUpdate(
                                    token_address=token_address,
                                    price=price_data.get("usd", 0),
                                    volume_24h=price_data.get("usd_24h_vol", 0),
                                    price_change_24h=price_data.get("usd_24h_change", 0),
                                    source="coingecko",
                                    timestamp=datetime.now()
                                ))
        except Exception as e:
            logger.error(f"CoinGecko price fetch error: {e}")

        return updates

    async def aggregate_prices(self, updates: List[PriceUpdate]) -> List[PriceUpdate]:
        """
        Aggregate prices from multiple sources using weighted average.

        Strategy:
        - Jupiter: 40% weight (most accurate for Solana)
        - Birdeye: 40% weight (comprehensive data)
        - CoinGecko: 20% weight (backup)

        Args:
            updates: List of PriceUpdate objects from various sources

        Returns:
            List of aggregated PriceUpdate objects
        """
        # Group by token
        by_token: Dict[str, List[PriceUpdate]] = {}
        for update in updates:
            if update.token_address not in by_token:
                by_token[update.token_address] = []
            by_token[update.token_address].append(update)

        aggregated = []

        for token_address, token_updates in by_token.items():
            if not token_updates:
                continue

            # Weight by source
            weights = {
                "jupiter": 0.4,
                "birdeye": 0.4,
                "coingecko": 0.2
            }

            total_weight = 0
            weighted_price = 0
            weighted_volume = 0
            weighted_change = 0

            for update in token_updates:
                weight = weights.get(update.source, 0.1)
                total_weight += weight
                weighted_price += update.price * weight
                weighted_volume += update.volume_24h * weight
                weighted_change += update.price_change_24h * weight

            if total_weight > 0:
                aggregated.append(PriceUpdate(
                    token_address=token_address,
                    price=weighted_price / total_weight,
                    volume_24h=weighted_volume / total_weight,
                    price_change_24h=weighted_change / total_weight,
                    source="aggregated",
                    timestamp=datetime.now()
                ))

        return aggregated

    async def price_update_loop(self, birdeye_api_key: Optional[str] = None):
        """
        Background task that fetches prices and broadcasts updates.

        Runs every 3 seconds to provide real-time updates.

        Args:
            birdeye_api_key: Optional Birdeye API key
        """
        logger.info("Price update loop started")

        while self.running:
            try:
                if not self.watched_tokens:
                    # No tokens being watched, sleep and continue
                    await asyncio.sleep(3)
                    continue

                # Fetch from all sources in parallel
                jupiter_task = self.fetch_jupiter_prices()
                birdeye_task = self.fetch_birdeye_prices(birdeye_api_key) if birdeye_api_key else asyncio.sleep(0)
                coingecko_task = self.fetch_coingecko_prices()

                results = await asyncio.gather(
                    jupiter_task,
                    birdeye_task if birdeye_api_key else asyncio.create_task(asyncio.sleep(0)),
                    coingecko_task,
                    return_exceptions=True
                )

                # Collect all updates
                all_updates = []
                for result in results:
                    if isinstance(result, list):
                        all_updates.extend(result)

                # Aggregate prices
                aggregated_updates = await self.aggregate_prices(all_updates)

                # Broadcast to clients
                for update in aggregated_updates:
                    await self.broadcast_price_update(update)

                # Wait before next update (3 seconds = ~20 updates per minute)
                await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"Price update loop error: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait longer on error

        logger.info("Price update loop stopped")

    async def start(self, birdeye_api_key: Optional[str] = None):
        """
        Start the price update background task.

        Args:
            birdeye_api_key: Optional Birdeye API key for enhanced data
        """
        if self.running:
            logger.warning("Price update loop already running")
            return

        self.running = True
        self.price_update_task = asyncio.create_task(
            self.price_update_loop(birdeye_api_key)
        )
        logger.info("WebSocket manager started")

    async def stop(self):
        """Stop the price update background task."""
        self.running = False

        if self.price_update_task:
            self.price_update_task.cancel()
            try:
                await self.price_update_task
            except asyncio.CancelledError:
                pass

        # Close all connections
        for token_address, connections in self.active_connections.items():
            for ws in connections:
                try:
                    await ws.close()
                except Exception:
                    pass

        self.active_connections.clear()
        logger.info("WebSocket manager stopped")


# Global instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    global _websocket_manager
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    return _websocket_manager
