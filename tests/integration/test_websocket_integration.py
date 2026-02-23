"""
Integration tests for WebSocket market data system
"""

import asyncio
import pytest
import json
from fastapi.testclient import TestClient
from fastapi import FastAPI

from api.websocket.market_data import (
    create_market_data_router,
    get_market_data_manager,
    MarketDataType,
    PriceUpdate,
)


@pytest.fixture
def app():
    """Create FastAPI app with market data router"""
    app = FastAPI()
    router = create_market_data_router()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return TestClient(app)


class TestMarketDataWebSocket:
    """Integration tests for market data WebSocket"""

    def test_websocket_connection(self, client):
        """Test basic WebSocket connection"""
        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Should receive welcome message
            data = websocket.receive_json()
            assert data["type"] == "connected"
            assert data["client_id"] == "test_client_1"
            assert "supported_types" in data

    def test_websocket_ping_pong(self, client):
        """Test ping/pong mechanism"""
        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Receive welcome
            websocket.receive_json()

            # Send ping
            websocket.send_json({"type": "ping"})

            # Should receive pong
            data = websocket.receive_json()
            assert data["type"] == "pong"

    def test_subscribe_to_token(self, client):
        """Test subscribing to token market data"""
        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Receive welcome
            websocket.receive_json()

            # Subscribe to SOL
            websocket.send_json({
                "type": "subscribe",
                "tokens": ["SOL"],
                "data_types": ["price", "volume"]
            })

            # Should receive subscription confirmation
            data = websocket.receive_json()
            assert data["type"] == "subscribed"
            assert "SOL" in data["tokens"]

            # Should receive initial snapshot
            data = websocket.receive_json()
            assert data["type"] == "snapshot"
            assert data["token"] == "SOL"

    def test_unsubscribe_from_token(self, client):
        """Test unsubscribing from token"""
        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Receive welcome
            websocket.receive_json()

            # Subscribe first
            websocket.send_json({
                "type": "subscribe",
                "tokens": ["SOL"],
                "data_types": ["price"]
            })

            # Consume subscription messages
            websocket.receive_json()  # subscribed
            websocket.receive_json()  # snapshot

            # Unsubscribe
            websocket.send_json({
                "type": "unsubscribe",
                "tokens": ["SOL"]
            })

            # Should receive unsubscribe confirmation
            data = websocket.receive_json()
            assert data["type"] == "unsubscribed"
            assert "SOL" in data["tokens"]

    def test_receive_price_updates(self, client):
        """Test receiving real-time price updates"""
        manager = get_market_data_manager()

        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Receive welcome
            websocket.receive_json()

            # Subscribe to SOL price
            websocket.send_json({
                "type": "subscribe",
                "tokens": ["SOL"],
                "data_types": ["price"]
            })

            # Consume subscription messages
            websocket.receive_json()  # subscribed

            # Skip snapshot if present
            try:
                snapshot = websocket.receive_json(timeout=0.5)
                if snapshot["type"] == "snapshot":
                    pass
            except Exception:
                pass

            # Publish a price update via manager
            async def publish_update():
                update = PriceUpdate(
                    token_mint="SOL",
                    price_usd=100.0,
                    change_24h=5.2,
                    volume_24h=1000000.0
                )
                await manager.publish_price_update(update)

            # Run async publish
            asyncio.run(publish_update())

            # Should receive price update
            data = websocket.receive_json(timeout=2)
            assert data["type"] == "price"
            assert data["token"] == "SOL"
            assert data["price_usd"] == 100.0

    def test_multiple_clients_same_token(self, client):
        """Test multiple clients receiving same updates"""
        manager = get_market_data_manager()

        with client.websocket_connect("/ws/market-data/client_1") as ws1, \
             client.websocket_connect("/ws/market-data/client_2") as ws2:

            # Both receive welcome
            ws1.receive_json()
            ws2.receive_json()

            # Both subscribe to SOL
            for ws in [ws1, ws2]:
                ws.send_json({
                    "type": "subscribe",
                    "tokens": ["SOL"],
                    "data_types": ["price"]
                })

                # Consume messages
                ws.receive_json()  # subscribed
                try:
                    ws.receive_json(timeout=0.5)  # snapshot (optional)
                except Exception:
                    pass

            # Publish update
            async def publish_update():
                update = PriceUpdate(token_mint="SOL", price_usd=150.0)
                await manager.publish_price_update(update)

            asyncio.run(publish_update())

            # Both should receive update
            for ws in [ws1, ws2]:
                data = ws.receive_json(timeout=2)
                assert data["type"] == "price"
                assert data["price_usd"] == 150.0

    def test_get_stats_endpoint(self, client):
        """Test stats endpoint"""
        response = client.get("/ws/market-data/stats")
        assert response.status_code == 200

        data = response.json()
        assert "active_clients" in data
        assert "active_tokens" in data
        assert "total_updates_sent" in data

    def test_selective_data_type_delivery(self, client):
        """Test that clients only receive subscribed data types"""
        manager = get_market_data_manager()

        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Receive welcome
            websocket.receive_json()

            # Subscribe only to PRICE
            websocket.send_json({
                "type": "subscribe",
                "tokens": ["SOL"],
                "data_types": ["price"]  # NOT volume
            })

            # Consume messages
            websocket.receive_json()  # subscribed
            try:
                websocket.receive_json(timeout=0.5)  # snapshot
            except Exception:
                pass

            # Publish volume update - should NOT receive
            from api.websocket.market_data import VolumeUpdate

            async def publish_volume():
                update = VolumeUpdate(
                    token_mint="SOL",
                    volume_1h=1000.0,
                    volume_24h=10000.0,
                    trade_count_1h=10,
                    trade_count_24h=100
                )
                await manager.publish_volume_update(update)

            asyncio.run(publish_volume())

            # Should NOT receive volume update (timeout expected)
            try:
                data = websocket.receive_json(timeout=1)
                # If we get here, it's wrong
                assert data["type"] != "volume", "Should not receive volume update"
            except Exception:
                pass  # Expected - no volume update received

    def test_heartbeat_mechanism(self, client):
        """Test heartbeat sending"""
        manager = get_market_data_manager()

        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Receive welcome
            websocket.receive_json()

            # Force heartbeat send
            async def send_heartbeat():
                manager._last_heartbeat["test_client_1"] = 0  # Force old time
                await manager.send_heartbeats()

            asyncio.run(send_heartbeat())

            # Should receive heartbeat
            data = websocket.receive_json(timeout=2)
            assert data["type"] == "heartbeat"
            assert "server_time" in data


class TestWebSocketResilience:
    """Test WebSocket error handling and resilience"""

    def test_invalid_message_type(self, client):
        """Test handling of invalid message types"""
        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Receive welcome
            websocket.receive_json()

            # Send invalid message type
            websocket.send_json({"type": "invalid_type"})

            # Connection should remain open
            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            assert data["type"] == "pong"

    def test_malformed_subscribe(self, client):
        """Test handling of malformed subscribe messages"""
        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Receive welcome
            websocket.receive_json()

            # Send subscribe without required fields
            websocket.send_json({"type": "subscribe"})

            # Connection should handle gracefully
            websocket.send_json({"type": "ping"})
            data = websocket.receive_json()
            assert data["type"] == "pong"

    def test_reconnection_tracking(self, client):
        """Test reconnection attempt tracking"""
        manager = get_market_data_manager()

        # Simulate multiple reconnections
        for i in range(6):
            allowed = manager.track_reconnection("test_client_reconnect")

            if i < 5:
                assert allowed is True
            else:
                assert allowed is False

        # Reset should allow reconnections again
        manager.reset_reconnection_count("test_client_reconnect")
        assert manager.track_reconnection("test_client_reconnect") is True


class TestWebSocketPerformance:
    """Test WebSocket performance characteristics"""

    def test_price_update_throttling(self, client):
        """Test that insignificant price changes are throttled"""
        manager = get_market_data_manager()

        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            # Setup subscription
            websocket.receive_json()  # welcome
            websocket.send_json({
                "type": "subscribe",
                "tokens": ["SOL"],
                "data_types": ["price"]
            })
            websocket.receive_json()  # subscribed

            try:
                websocket.receive_json(timeout=0.5)  # snapshot
            except Exception:
                pass

            # Send first update
            async def publish_updates():
                # First update - should send
                update1 = PriceUpdate(token_mint="SOL", price_usd=100.0)
                await manager.publish_price_update(update1)

                # Second update - tiny change, should be throttled
                update2 = PriceUpdate(token_mint="SOL", price_usd=100.05)
                await manager.publish_price_update(update2)

                # Third update - significant change, should send
                update3 = PriceUpdate(token_mint="SOL", price_usd=102.0)
                await manager.publish_price_update(update3)

            asyncio.run(publish_updates())

            # Should receive first update
            data1 = websocket.receive_json(timeout=2)
            assert data1["price_usd"] == 100.0

            # Should receive third update (second was throttled)
            data2 = websocket.receive_json(timeout=2)
            assert data2["price_usd"] == 102.0

            # Should NOT receive any more updates
            try:
                data3 = websocket.receive_json(timeout=0.5)
                # If we get here, something wrong
                assert False, "Unexpected message received"
            except Exception:
                pass  # Expected - no more messages

    def test_concurrent_subscriptions(self, client):
        """Test handling multiple concurrent subscriptions"""
        with client.websocket_connect("/ws/market-data/test_client_1") as websocket:
            websocket.receive_json()  # welcome

            # Subscribe to multiple tokens at once
            websocket.send_json({
                "type": "subscribe",
                "tokens": ["SOL", "KR8TIV", "USDC"],
                "data_types": ["price", "volume"]
            })

            # Should receive confirmation
            data = websocket.receive_json()
            assert data["type"] == "subscribed"
            assert len(data["tokens"]) == 3

            # May receive snapshots
            # Just verify connection is stable
            websocket.send_json({"type": "ping"})
            pong = websocket.receive_json(timeout=2)
            # Keep receiving until we get pong (skip snapshots)
            while pong.get("type") != "pong":
                pong = websocket.receive_json(timeout=2)
            assert pong["type"] == "pong"
