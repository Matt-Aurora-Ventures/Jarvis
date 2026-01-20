"""
Unit tests for WebSocket market data streaming
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocket

from api.websocket.market_data import (
    MarketDataManager,
    MarketDataType,
    PriceUpdate,
    VolumeUpdate,
    TradeUpdate,
    OrderBookUpdate,
)


@pytest.fixture
def manager():
    """Create fresh MarketDataManager for each test"""
    return MarketDataManager()


@pytest.fixture
def mock_websocket():
    """Create mock WebSocket"""
    ws = MagicMock(spec=WebSocket)
    ws.send_json = AsyncMock()
    return ws


class TestMarketDataManager:
    """Test MarketDataManager functionality"""

    @pytest.mark.asyncio
    async def test_add_remove_client(self, manager, mock_websocket):
        """Test adding and removing clients"""
        client_id = "test_client_1"

        # Add client
        await manager.add_client(client_id, mock_websocket)

        assert client_id in manager._clients
        assert client_id in manager._subscriptions
        assert manager.total_connections == 1

        # Verify welcome message sent
        mock_websocket.send_json.assert_called_once()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "connected"
        assert call_args["client_id"] == client_id

        # Remove client
        await manager.remove_client(client_id)

        assert client_id not in manager._clients
        assert client_id not in manager._subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_to_tokens(self, manager, mock_websocket):
        """Test subscribing to token market data"""
        client_id = "test_client_1"
        tokens = ["SOL", "KR8TIV"]
        data_types = [MarketDataType.PRICE, MarketDataType.VOLUME]

        await manager.add_client(client_id, mock_websocket)
        mock_websocket.send_json.reset_mock()

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock) as mock_feed:
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                await manager.subscribe(client_id, tokens, data_types)

        # Verify subscriptions created
        assert "SOL" in manager._subscriptions[client_id]
        assert "KR8TIV" in manager._subscriptions[client_id]
        assert MarketDataType.PRICE in manager._subscriptions[client_id]["SOL"]
        assert MarketDataType.VOLUME in manager._subscriptions[client_id]["SOL"]

        # Verify token subscribers tracked
        assert client_id in manager._token_subscribers["SOL"]
        assert client_id in manager._token_subscribers["KR8TIV"]

        # Verify price feed started
        assert mock_feed.call_count == 2

        # Verify subscription confirmation sent
        mock_websocket.send_json.assert_called()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "subscribed"
        assert set(call_args["tokens"]) == set(tokens)

    @pytest.mark.asyncio
    async def test_unsubscribe_from_tokens(self, manager, mock_websocket):
        """Test unsubscribing from token market data"""
        client_id = "test_client_1"
        tokens = ["SOL"]

        await manager.add_client(client_id, mock_websocket)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock):
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                await manager.subscribe(client_id, tokens, [MarketDataType.PRICE])

        mock_websocket.send_json.reset_mock()

        with patch.object(manager, '_stop_price_feed', new_callable=AsyncMock) as mock_stop:
            await manager.unsubscribe(client_id, tokens)

        # Verify subscription removed
        assert "SOL" not in manager._subscriptions[client_id]
        assert client_id not in manager._token_subscribers.get("SOL", set())

        # Verify price feed stopped
        mock_stop.assert_called_once_with("SOL")

        # Verify unsubscribe confirmation sent
        mock_websocket.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_publish_price_update(self, manager, mock_websocket):
        """Test publishing price updates to subscribers"""
        client_id = "test_client_1"
        token = "SOL"

        await manager.add_client(client_id, mock_websocket)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock):
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                await manager.subscribe(client_id, [token], [MarketDataType.PRICE])

        mock_websocket.send_json.reset_mock()

        # Publish price update
        update = PriceUpdate(
            token_mint=token,
            price_usd=100.0,
            price_sol=1.0,
            change_24h=5.2,
            volume_24h=1000000.0
        )

        await manager.publish_price_update(update)

        # Verify update sent to subscriber
        mock_websocket.send_json.assert_called()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == MarketDataType.PRICE.value
        assert call_args["token"] == token
        assert call_args["price_usd"] == 100.0
        assert call_args["change_24h"] == 5.2

    @pytest.mark.asyncio
    async def test_price_update_filtering(self, manager, mock_websocket):
        """Test that insignificant price changes are filtered"""
        client_id = "test_client_1"
        token = "SOL"

        await manager.add_client(client_id, mock_websocket)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock):
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                await manager.subscribe(client_id, [token], [MarketDataType.PRICE])

        mock_websocket.send_json.reset_mock()

        # First update - should send
        update1 = PriceUpdate(token_mint=token, price_usd=100.0)
        await manager.publish_price_update(update1)
        assert mock_websocket.send_json.call_count == 1

        mock_websocket.send_json.reset_mock()

        # Second update - tiny change, should be filtered
        update2 = PriceUpdate(token_mint=token, price_usd=100.05)  # 0.05% change
        await manager.publish_price_update(update2)
        assert mock_websocket.send_json.call_count == 0

        # Third update - significant change, should send
        update3 = PriceUpdate(token_mint=token, price_usd=101.0)  # 1% change
        await manager.publish_price_update(update3)
        assert mock_websocket.send_json.call_count == 1

    @pytest.mark.asyncio
    async def test_publish_volume_update(self, manager, mock_websocket):
        """Test publishing volume updates"""
        client_id = "test_client_1"
        token = "SOL"

        await manager.add_client(client_id, mock_websocket)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock):
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                await manager.subscribe(client_id, [token], [MarketDataType.VOLUME])

        mock_websocket.send_json.reset_mock()

        update = VolumeUpdate(
            token_mint=token,
            volume_1h=50000.0,
            volume_24h=1000000.0,
            trade_count_1h=100,
            trade_count_24h=2000
        )

        await manager.publish_volume_update(update)

        mock_websocket.send_json.assert_called()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == MarketDataType.VOLUME.value
        assert call_args["volume_24h"] == 1000000.0
        assert call_args["trade_count_1h"] == 100

    @pytest.mark.asyncio
    async def test_publish_trade_update(self, manager, mock_websocket):
        """Test publishing individual trade updates"""
        client_id = "test_client_1"
        token = "SOL"

        await manager.add_client(client_id, mock_websocket)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock):
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                await manager.subscribe(client_id, [token], [MarketDataType.TRADE])

        mock_websocket.send_json.reset_mock()

        update = TradeUpdate(
            token_mint=token,
            side="buy",
            price=100.0,
            amount=10.0,
            value_usd=1000.0,
            signature="test_sig"
        )

        await manager.publish_trade_update(update)

        mock_websocket.send_json.assert_called()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == MarketDataType.TRADE.value
        assert call_args["side"] == "buy"
        assert call_args["price"] == 100.0
        assert call_args["amount"] == 10.0

    @pytest.mark.asyncio
    async def test_publish_orderbook_update(self, manager, mock_websocket):
        """Test publishing order book updates"""
        client_id = "test_client_1"
        token = "SOL"

        await manager.add_client(client_id, mock_websocket)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock):
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                await manager.subscribe(client_id, [token], [MarketDataType.ORDER_BOOK])

        mock_websocket.send_json.reset_mock()

        update = OrderBookUpdate(
            token_mint=token,
            bids=[[100.0, 10.0], [99.0, 20.0]],
            asks=[[101.0, 15.0], [102.0, 25.0]],
            spread=1.0,
            mid_price=100.5
        )

        await manager.publish_orderbook_update(update)

        mock_websocket.send_json.assert_called()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == MarketDataType.ORDER_BOOK.value
        assert len(call_args["bids"]) == 2
        assert len(call_args["asks"]) == 2
        assert call_args["spread"] == 1.0

    @pytest.mark.asyncio
    async def test_heartbeat_sending(self, manager, mock_websocket):
        """Test heartbeat mechanism"""
        client_id = "test_client_1"

        await manager.add_client(client_id, mock_websocket)
        mock_websocket.send_json.reset_mock()

        # Force heartbeat interval to be passed
        manager._last_heartbeat[client_id] = 0

        await manager.send_heartbeats()

        # Verify heartbeat sent
        mock_websocket.send_json.assert_called()
        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["type"] == "heartbeat"
        assert "server_time" in call_args

    @pytest.mark.asyncio
    async def test_handle_pong(self, manager, mock_websocket):
        """Test pong response handling"""
        client_id = "test_client_1"

        await manager.add_client(client_id, mock_websocket)

        # Set old heartbeat time
        manager._last_heartbeat[client_id] = 0

        # Handle pong
        await manager.handle_pong(client_id)

        # Verify heartbeat time updated
        assert manager._last_heartbeat[client_id] > 0

    @pytest.mark.asyncio
    async def test_reconnection_tracking(self, manager):
        """Test reconnection attempt tracking"""
        client_id = "test_client_1"

        # First few reconnects should be allowed
        for i in range(5):
            assert manager.track_reconnection(client_id) is True
            assert manager._reconnect_counts[client_id] == i + 1

        # Exceeding max should be denied
        assert manager.track_reconnection(client_id) is False

        # Reset should clear count
        manager.reset_reconnection_count(client_id)
        assert manager._reconnect_counts[client_id] == 0

    @pytest.mark.asyncio
    async def test_multiple_clients_same_token(self, manager):
        """Test multiple clients subscribing to same token"""
        ws1 = MagicMock(spec=WebSocket)
        ws1.send_json = AsyncMock()
        ws2 = MagicMock(spec=WebSocket)
        ws2.send_json = AsyncMock()

        client1 = "client_1"
        client2 = "client_2"
        token = "SOL"

        # Add both clients
        await manager.add_client(client1, ws1)
        await manager.add_client(client2, ws2)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock) as mock_feed:
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                # Subscribe both to same token
                await manager.subscribe(client1, [token], [MarketDataType.PRICE])
                await manager.subscribe(client2, [token], [MarketDataType.PRICE])

        # Verify only one price feed started
        assert mock_feed.call_count == 2  # Called once per subscribe, but should dedupe internally

        # Verify both clients in subscribers
        assert client1 in manager._token_subscribers[token]
        assert client2 in manager._token_subscribers[token]

        ws1.send_json.reset_mock()
        ws2.send_json.reset_mock()

        # Publish update - should go to both
        update = PriceUpdate(token_mint=token, price_usd=100.0)
        await manager.publish_price_update(update)

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscription_filtering_by_data_type(self, manager, mock_websocket):
        """Test that clients only receive subscribed data types"""
        client_id = "test_client_1"
        token = "SOL"

        await manager.add_client(client_id, mock_websocket)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock):
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                # Subscribe only to PRICE, not VOLUME
                await manager.subscribe(client_id, [token], [MarketDataType.PRICE])

        mock_websocket.send_json.reset_mock()

        # Publish price update - should receive
        price_update = PriceUpdate(token_mint=token, price_usd=100.0)
        await manager.publish_price_update(price_update)
        assert mock_websocket.send_json.call_count == 1

        mock_websocket.send_json.reset_mock()

        # Publish volume update - should NOT receive
        volume_update = VolumeUpdate(
            token_mint=token,
            volume_1h=1000.0,
            volume_24h=10000.0,
            trade_count_1h=10,
            trade_count_24h=100
        )
        await manager.publish_volume_update(volume_update)
        assert mock_websocket.send_json.call_count == 0

    @pytest.mark.asyncio
    async def test_get_stats(self, manager, mock_websocket):
        """Test statistics retrieval"""
        client_id = "test_client_1"

        await manager.add_client(client_id, mock_websocket)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock):
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                await manager.subscribe(client_id, ["SOL", "KR8TIV"], [MarketDataType.PRICE])

        stats = manager.get_stats()

        assert stats["active_clients"] == 1
        assert stats["active_tokens"] == 2
        assert stats["total_subscriptions"] == 2
        assert stats["total_connections"] == 1

    @pytest.mark.asyncio
    async def test_client_error_handling(self, manager, mock_websocket):
        """Test handling of client send errors"""
        client_id = "test_client_1"
        token = "SOL"

        await manager.add_client(client_id, mock_websocket)

        with patch.object(manager, '_ensure_price_feed', new_callable=AsyncMock):
            with patch.object(manager, '_send_initial_snapshot', new_callable=AsyncMock):
                await manager.subscribe(client_id, [token], [MarketDataType.PRICE])

        # Make send_json raise an exception
        mock_websocket.send_json.side_effect = Exception("Connection lost")

        # Publish update - should handle error gracefully
        update = PriceUpdate(token_mint=token, price_usd=100.0)
        await manager.publish_price_update(update)

        # Verify client was removed after error
        assert client_id not in manager._clients


class TestPriceUpdates:
    """Test PriceUpdate data class"""

    def test_price_update_creation(self):
        """Test creating PriceUpdate"""
        update = PriceUpdate(
            token_mint="SOL",
            price_usd=100.0,
            price_sol=1.0,
            change_24h=5.2,
            volume_24h=1000000.0,
            market_cap=5000000000.0
        )

        assert update.token_mint == "SOL"
        assert update.price_usd == 100.0
        assert update.change_24h == 5.2
        assert isinstance(update.timestamp, datetime)

    def test_price_update_defaults(self):
        """Test PriceUpdate with defaults"""
        update = PriceUpdate(token_mint="SOL", price_usd=100.0)

        assert update.change_24h == 0.0
        assert update.volume_24h == 0.0
        assert update.price_sol is None
        assert update.source == "jupiter"


class TestVolumeUpdates:
    """Test VolumeUpdate data class"""

    def test_volume_update_creation(self):
        """Test creating VolumeUpdate"""
        update = VolumeUpdate(
            token_mint="SOL",
            volume_1h=50000.0,
            volume_24h=1000000.0,
            trade_count_1h=100,
            trade_count_24h=2000
        )

        assert update.token_mint == "SOL"
        assert update.volume_24h == 1000000.0
        assert update.trade_count_1h == 100


class TestTradeUpdates:
    """Test TradeUpdate data class"""

    def test_trade_update_creation(self):
        """Test creating TradeUpdate"""
        update = TradeUpdate(
            token_mint="SOL",
            side="buy",
            price=100.0,
            amount=10.0,
            value_usd=1000.0,
            signature="test_signature"
        )

        assert update.side == "buy"
        assert update.price == 100.0
        assert update.amount == 10.0
        assert update.value_usd == 1000.0


class TestOrderBookUpdates:
    """Test OrderBookUpdate data class"""

    def test_orderbook_update_creation(self):
        """Test creating OrderBookUpdate"""
        update = OrderBookUpdate(
            token_mint="SOL",
            bids=[[100.0, 10.0], [99.0, 20.0]],
            asks=[[101.0, 15.0], [102.0, 25.0]],
            spread=1.0,
            mid_price=100.5
        )

        assert len(update.bids) == 2
        assert len(update.asks) == 2
        assert update.spread == 1.0
        assert update.mid_price == 100.5
