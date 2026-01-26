"""
Tests for core/bags_websocket.py - Bags.fm WebSocket Price Feed

TDD: Write failing tests first, then implement.

REQ-004: WebSocket price feed integration for real-time prices
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestBagsWebSocketClient:
    """Test BagsWebSocketClient class."""

    def test_bags_websocket_has_default_url(self):
        """WebSocket client should have default bags.fm URL."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()
        assert "bags" in client.ws_url.lower() or "wss://" in client.ws_url

    def test_bags_websocket_configurable_url(self):
        """WebSocket client should accept custom URL."""
        from core.bags_websocket import BagsWebSocketClient

        custom_url = "wss://custom.bags.fm/ws"
        client = BagsWebSocketClient(ws_url=custom_url)
        assert client.ws_url == custom_url

    def test_bags_websocket_initial_state(self):
        """WebSocket client should start disconnected."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()
        assert client.connected is False
        assert len(client.subscriptions) == 0

    @pytest.mark.asyncio
    async def test_subscribe_adds_token_to_subscriptions(self):
        """subscribe() should add token to subscriptions list."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()
        token_mint = "TokenMint123"

        await client.subscribe(token_mint)

        assert token_mint in client.subscriptions

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_token(self):
        """unsubscribe() should remove token from subscriptions."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()
        token_mint = "TokenMint123"

        await client.subscribe(token_mint)
        await client.unsubscribe(token_mint)

        assert token_mint not in client.subscriptions

    @pytest.mark.asyncio
    async def test_on_price_update_callback(self):
        """on_price_update callback should be called with price data."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()
        received_data = []

        def callback(data):
            received_data.append(data)

        client.on_price_update = callback

        # Simulate receiving a price update
        price_data = {
            "mint": "TokenMint123",
            "price": 0.00123,
            "price_usd": 0.28,
            "volume_24h": 50000,
            "timestamp": 1700000000,
        }
        await client._handle_message(price_data)

        assert len(received_data) == 1
        assert received_data[0]["mint"] == "TokenMint123"
        assert received_data[0]["price"] == 0.00123

    @pytest.mark.asyncio
    async def test_get_latest_price_returns_cached_price(self):
        """get_latest_price() should return cached price for subscribed token."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()

        # Simulate cached price
        client._price_cache["TokenMint123"] = {
            "price": 0.00456,
            "price_usd": 1.05,
            "timestamp": datetime.now(),
        }

        price = client.get_latest_price("TokenMint123")

        assert price is not None
        assert price["price"] == 0.00456

    def test_get_latest_price_returns_none_for_unknown(self):
        """get_latest_price() should return None for unknown tokens."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()

        price = client.get_latest_price("UnknownToken")

        assert price is None


class TestBagsWebSocketReconnection:
    """Test WebSocket reconnection behavior."""

    @pytest.mark.asyncio
    async def test_auto_reconnect_on_disconnect(self):
        """Client should auto-reconnect on unexpected disconnect."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient(auto_reconnect=True)
        client._reconnect_attempts = 0

        # Mock the connect method
        connect_calls = []

        async def mock_connect():
            connect_calls.append(1)
            return True

        client.connect = mock_connect

        # Simulate disconnect handler
        await client._on_disconnect()

        # Should have attempted reconnect
        assert len(connect_calls) >= 1 or client._reconnect_attempts >= 1

    def test_max_reconnect_attempts_configurable(self):
        """Max reconnect attempts should be configurable."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient(max_reconnect_attempts=5)
        assert client.max_reconnect_attempts == 5


class TestBagsWebSocketGraduationMonitor:
    """Test graduation monitoring via WebSocket."""

    @pytest.mark.asyncio
    async def test_on_graduation_callback(self):
        """on_graduation callback should be called when token graduates."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()
        graduated_tokens = []

        def callback(data):
            graduated_tokens.append(data)

        client.on_graduation = callback

        # Simulate graduation event
        graduation_data = {
            "type": "graduation",
            "mint": "GraduatedToken123",
            "bonding_curve_complete": True,
            "raydium_pool": "PoolAddress123",
            "timestamp": 1700000000,
        }
        await client._handle_message(graduation_data)

        assert len(graduated_tokens) == 1
        assert graduated_tokens[0]["mint"] == "GraduatedToken123"

    @pytest.mark.asyncio
    async def test_subscribe_graduations(self):
        """subscribe_graduations() should enable graduation events."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()

        await client.subscribe_graduations()

        assert client._graduation_subscribed is True


class TestBagsWebSocketStats:
    """Test WebSocket statistics tracking."""

    def test_get_stats_returns_connection_info(self):
        """get_stats() should return connection statistics."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()

        stats = client.get_stats()

        assert "connected" in stats
        assert "subscriptions" in stats
        assert "messages_received" in stats
        assert "reconnect_count" in stats

    @pytest.mark.asyncio
    async def test_message_counter_increments(self):
        """Message counter should increment on each message."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()
        initial_count = client._messages_received

        # Simulate receiving messages
        await client._handle_message({"type": "heartbeat"})
        await client._handle_message({"type": "price", "mint": "Token1"})

        assert client._messages_received == initial_count + 2


class TestPriceFeedIntegration:
    """Test integration between WebSocket and price retrieval."""

    @pytest.mark.asyncio
    async def test_price_cache_updates_on_message(self):
        """Price cache should update when price message received."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()

        # Simulate price update
        price_msg = {
            "type": "price",
            "mint": "TestToken",
            "price": 0.001234,
            "price_usd": 0.285,
            "volume_24h": 100000,
        }
        await client._handle_message(price_msg)

        cached = client.get_latest_price("TestToken")
        assert cached is not None
        assert cached["price"] == 0.001234

    @pytest.mark.asyncio
    async def test_price_history_maintained(self):
        """Price history should be maintained for charting."""
        from core.bags_websocket import BagsWebSocketClient

        client = BagsWebSocketClient()
        client._enable_history = True

        # Simulate multiple price updates
        for i in range(5):
            await client._handle_message({
                "type": "price",
                "mint": "HistoryToken",
                "price": 0.001 + (i * 0.0001),
                "timestamp": 1700000000 + i,
            })

        history = client.get_price_history("HistoryToken")
        assert len(history) == 5
        assert history[-1]["price"] > history[0]["price"]


class TestFactoryFunction:
    """Test singleton factory function."""

    def test_get_bags_websocket_returns_singleton(self):
        """get_bags_websocket() should return singleton instance."""
        from core.bags_websocket import get_bags_websocket

        client1 = get_bags_websocket()
        client2 = get_bags_websocket()

        assert client1 is client2

    def test_get_bags_websocket_is_correct_type(self):
        """get_bags_websocket() should return BagsWebSocketClient."""
        from core.bags_websocket import get_bags_websocket, BagsWebSocketClient

        client = get_bags_websocket()
        assert isinstance(client, BagsWebSocketClient)
