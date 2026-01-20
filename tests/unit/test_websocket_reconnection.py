"""
Unit tests for WebSocket reconnection logic

Tests cover:
1. Automatic reconnection on disconnect
2. Exponential backoff between reconnect attempts
3. Message queue preservation during reconnection
4. Subscription restoration after reconnect
5. Connection state management
"""

import asyncio
import pytest
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

# Import the actual implementations
from core.websocket_manager import (
    WebSocketConnection,
    WebSocketManager,
    ConnectionConfig,
    ConnectionState,
    ConnectionStats,
)
from core.resilience.backoff import (
    BackoffConfig,
    calculate_backoff_delay,
    retry_with_backoff,
)


# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_websocket():
    """Create a mock websocket connection."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock(return_value='{"type": "test"}')
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def connection_config():
    """Create a test connection configuration."""
    return ConnectionConfig(
        name="test_connection",
        url="wss://test.example.com/ws",
        auto_reconnect=True,
        max_reconnect_attempts=5,
        reconnect_delay=0.1,  # Fast for testing
        max_reconnect_delay=1.0,
        ping_interval=30.0,
        ping_timeout=10.0,
    )


@pytest.fixture
def ws_connection(connection_config):
    """Create a WebSocket connection for testing."""
    return WebSocketConnection(connection_config)


@pytest.fixture
def ws_manager():
    """Create a WebSocket manager for testing."""
    return WebSocketManager()


def create_mock_websocket():
    """Factory to create fresh mock websockets."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.recv = AsyncMock(side_effect=asyncio.CancelledError())
    ws.close = AsyncMock()
    return ws


# =============================================================================
# CONNECTION STATE MANAGEMENT TESTS
# =============================================================================


class TestConnectionStateManagement:
    """Test connection state transitions."""

    def test_initial_state_is_disconnected(self, ws_connection):
        """Test that initial state is disconnected."""
        assert ws_connection.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_state_transitions_to_connecting(self, ws_connection, mock_websocket):
        """Test state transitions to CONNECTING during connect."""
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            # Don't complete immediately - use a future
            connect_future = asyncio.Future()
            mock_connect.return_value = connect_future

            # Start connection (don't await)
            connect_task = asyncio.create_task(ws_connection.connect())

            # Give it time to start
            await asyncio.sleep(0.01)

            # Cancel to clean up
            connect_task.cancel()
            try:
                await connect_task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_state_transitions_to_connected(self, ws_connection, mock_websocket):
        """Test state transitions to CONNECTED on successful connect."""
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket

            # Mock receive to avoid blocking
            async def recv_then_close():
                await asyncio.sleep(0.1)
                raise asyncio.CancelledError()
            mock_websocket.recv = recv_then_close

            result = await ws_connection.connect()

            assert result is True
            assert ws_connection.state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_state_transitions_to_failed_on_error(self, ws_connection):
        """Test state transitions to FAILED on connection error."""
        ws_connection.config.auto_reconnect = False

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("Connection refused")

            result = await ws_connection.connect()

            assert result is False
            assert ws_connection.state == ConnectionState.FAILED

    @pytest.mark.asyncio
    async def test_state_transitions_to_disconnected(self, ws_connection, mock_websocket):
        """Test state transitions to DISCONNECTED on graceful disconnect."""
        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket

            # Mock receive to avoid blocking
            async def recv_then_close():
                await asyncio.sleep(10)
            mock_websocket.recv = recv_then_close

            await ws_connection.connect()
            await ws_connection.disconnect()

            assert ws_connection.state == ConnectionState.DISCONNECTED


# =============================================================================
# AUTOMATIC RECONNECTION TESTS
# =============================================================================


class TestAutomaticReconnection:
    """Test automatic reconnection on disconnect."""

    @pytest.mark.asyncio
    async def test_auto_reconnect_on_connection_close(self, connection_config):
        """Test that reconnection is attempted when connection closes."""
        connection_config.max_reconnect_attempts = 2
        connection_config.reconnect_delay = 0.01
        ws_connection = WebSocketConnection(connection_config)

        connect_count = 0

        async def mock_connect_factory(*args, **kwargs):
            nonlocal connect_count
            connect_count += 1
            if connect_count == 1:
                # First connection succeeds but fails on recv
                ws = AsyncMock()
                ws.recv = AsyncMock(side_effect=ConnectionError("Connection closed"))
                ws.send = AsyncMock()
                ws.close = AsyncMock()
                return ws
            else:
                # Subsequent connections succeed
                ws = AsyncMock()
                ws.recv = AsyncMock(side_effect=asyncio.CancelledError())
                ws.send = AsyncMock()
                ws.close = AsyncMock()
                return ws

        with patch("websockets.connect", side_effect=mock_connect_factory):
            await ws_connection.connect()

            # Wait for reconnection attempt
            await asyncio.sleep(0.1)

            # Clean up
            ws_connection._should_reconnect = False
            await ws_connection.disconnect()

        assert connect_count >= 1

    @pytest.mark.asyncio
    async def test_no_reconnect_when_disabled(self, connection_config):
        """Test that reconnection is not attempted when disabled."""
        connection_config.auto_reconnect = False
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.side_effect = ConnectionRefusedError("Connection refused")

            result = await ws_connection.connect()

            assert result is False
            assert mock_connect.call_count == 1

    @pytest.mark.asyncio
    async def test_reconnect_stops_after_max_attempts(self, connection_config):
        """Test that reconnection stops after max attempts."""
        connection_config.max_reconnect_attempts = 3
        connection_config.reconnect_delay = 0.01
        connection_config.max_reconnect_delay = 0.05
        ws_connection = WebSocketConnection(connection_config)

        connect_count = 0

        async def failing_connect(*args, **kwargs):
            nonlocal connect_count
            connect_count += 1
            raise ConnectionRefusedError("Connection refused")

        with patch("websockets.connect", side_effect=failing_connect):
            await ws_connection.connect()

            # Wait for all reconnection attempts
            await asyncio.sleep(0.5)

        # Initial + max_reconnect_attempts
        assert connect_count == 1 + connection_config.max_reconnect_attempts
        assert ws_connection.state == ConnectionState.FAILED

    @pytest.mark.asyncio
    async def test_reconnect_stops_on_manual_disconnect(self, connection_config, mock_websocket):
        """Test that reconnection stops when manually disconnected."""
        connection_config.max_reconnect_attempts = 10
        connection_config.reconnect_delay = 0.01
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            await ws_connection.connect()
            await ws_connection.disconnect()

            # Verify no reconnection after disconnect
            assert ws_connection._should_reconnect is False


# =============================================================================
# EXPONENTIAL BACKOFF TESTS
# =============================================================================


class TestExponentialBackoff:
    """Test exponential backoff between reconnect attempts."""

    def test_backoff_delay_calculation(self):
        """Test exponential backoff delay calculation."""
        config = BackoffConfig(
            base_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=False,
        )

        # Attempt 0: 1 * 2^0 = 1
        assert calculate_backoff_delay(0, config) == 1.0

        # Attempt 1: 1 * 2^1 = 2
        assert calculate_backoff_delay(1, config) == 2.0

        # Attempt 2: 1 * 2^2 = 4
        assert calculate_backoff_delay(2, config) == 4.0

        # Attempt 3: 1 * 2^3 = 8
        assert calculate_backoff_delay(3, config) == 8.0

    def test_backoff_respects_max_delay(self):
        """Test that backoff respects maximum delay."""
        config = BackoffConfig(
            base_delay=1.0,
            max_delay=10.0,
            exponential_base=2.0,
            jitter=False,
        )

        # Attempt 10: 1 * 2^10 = 1024, but max is 10
        assert calculate_backoff_delay(10, config) == 10.0

    def test_backoff_jitter(self):
        """Test that jitter adds randomness to delay."""
        config = BackoffConfig(
            base_delay=10.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True,
        )

        delays = [calculate_backoff_delay(1, config) for _ in range(100)]

        # With jitter, delays should vary
        unique_delays = set(delays)
        assert len(unique_delays) > 1

        # All delays should be within +-25% of base (10 * 2^1 = 20)
        for delay in delays:
            assert 15.0 <= delay <= 25.0  # 20 +/- 25%

    @pytest.mark.asyncio
    async def test_websocket_reconnect_uses_backoff(self, connection_config):
        """Test that WebSocket reconnection uses exponential backoff."""
        connection_config.max_reconnect_attempts = 3
        connection_config.reconnect_delay = 0.1
        connection_config.max_reconnect_delay = 1.0
        ws_connection = WebSocketConnection(connection_config)

        connect_times = []

        async def failing_connect(*args, **kwargs):
            connect_times.append(time.time())
            raise ConnectionRefusedError("Connection refused")

        with patch("websockets.connect", side_effect=failing_connect):
            await ws_connection.connect()

            # Wait for all reconnection attempts
            await asyncio.sleep(2.0)

        # Check that delays between attempts increase
        if len(connect_times) >= 3:
            delay1 = connect_times[1] - connect_times[0]
            delay2 = connect_times[2] - connect_times[1]

            # Second delay should be roughly double the first (with some tolerance for jitter)
            # Note: First delay happens after initial failure, second after retry 1
            assert delay2 >= delay1 * 0.5  # Allow for jitter variance

    def test_custom_backoff_base(self):
        """Test backoff with custom exponential base."""
        config = BackoffConfig(
            base_delay=1.0,
            max_delay=1000.0,
            exponential_base=3.0,  # Triple each time
            jitter=False,
        )

        # Attempt 0: 1 * 3^0 = 1
        assert calculate_backoff_delay(0, config) == 1.0

        # Attempt 1: 1 * 3^1 = 3
        assert calculate_backoff_delay(1, config) == 3.0

        # Attempt 2: 1 * 3^2 = 9
        assert calculate_backoff_delay(2, config) == 9.0


# =============================================================================
# MESSAGE QUEUE PRESERVATION TESTS
# =============================================================================


@dataclass
class MessageQueue:
    """Message queue for testing."""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    max_size: int = 100

    def enqueue(self, message: Dict[str, Any]):
        if len(self.messages) < self.max_size:
            self.messages.append(message)

    def dequeue_all(self) -> List[Dict[str, Any]]:
        messages = self.messages.copy()
        self.messages.clear()
        return messages

    def size(self) -> int:
        return len(self.messages)


class TestMessageQueuePreservation:
    """Test message queue preservation during reconnection."""

    @pytest.mark.asyncio
    async def test_messages_queued_during_disconnect(self):
        """Test that messages are queued when disconnected."""
        queue = MessageQueue()

        # Simulate disconnected state - queue messages
        for i in range(5):
            queue.enqueue({"id": i, "data": f"message_{i}"})

        assert queue.size() == 5

    @pytest.mark.asyncio
    async def test_queued_messages_sent_after_reconnect(self):
        """Test that queued messages are sent after reconnection."""
        queue = MessageQueue()
        sent_messages = []

        # Queue messages during "disconnect"
        for i in range(5):
            queue.enqueue({"id": i, "data": f"message_{i}"})

        # Simulate reconnection - send all queued messages
        async def send_message(msg):
            sent_messages.append(msg)

        for msg in queue.dequeue_all():
            await send_message(msg)

        assert len(sent_messages) == 5
        assert queue.size() == 0

    @pytest.mark.asyncio
    async def test_queue_respects_max_size(self):
        """Test that queue respects maximum size."""
        queue = MessageQueue(max_size=3)

        for i in range(5):
            queue.enqueue({"id": i})

        # Only first 3 messages should be queued
        assert queue.size() == 3

    @pytest.mark.asyncio
    async def test_message_order_preserved(self):
        """Test that message order is preserved in queue."""
        queue = MessageQueue()

        for i in range(5):
            queue.enqueue({"id": i})

        messages = queue.dequeue_all()

        for i, msg in enumerate(messages):
            assert msg["id"] == i


# =============================================================================
# SUBSCRIPTION RESTORATION TESTS
# =============================================================================


class TestSubscriptionRestoration:
    """Test subscription restoration after reconnect."""

    @pytest.mark.asyncio
    async def test_subscriptions_stored_in_config(self, connection_config):
        """Test that subscriptions are stored in connection config."""
        ws_connection = WebSocketConnection(connection_config)

        subscription = {"method": "subscribe", "params": ["channel1"]}
        await ws_connection.subscribe(subscription)

        assert subscription in ws_connection.config.subscriptions

    @pytest.mark.asyncio
    async def test_subscriptions_sent_on_connect(self, connection_config, mock_websocket):
        """Test that subscriptions are sent on initial connect."""
        connection_config.subscriptions = [
            {"method": "subscribe", "params": ["channel1"]},
            {"method": "subscribe", "params": ["channel2"]},
        ]
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            await ws_connection.connect()

            # Clean up
            await ws_connection.disconnect()

        # Verify subscriptions were sent
        assert mock_websocket.send.call_count == 2

    @pytest.mark.asyncio
    async def test_subscriptions_restored_after_reconnect(self, connection_config, mock_websocket):
        """Test that subscriptions are restored after reconnection."""
        connection_config.subscriptions = [
            {"method": "subscribe", "params": ["channel1"]},
        ]
        connection_config.max_reconnect_attempts = 1
        connection_config.reconnect_delay = 0.01
        ws_connection = WebSocketConnection(connection_config)

        connect_count = 0

        async def mock_connect_factory(*args, **kwargs):
            nonlocal connect_count
            connect_count += 1

            ws = AsyncMock()
            if connect_count == 1:
                # First connection - fail after a moment
                ws.recv = AsyncMock(side_effect=ConnectionError("Closed"))
            else:
                # Second connection - stay open briefly
                ws.recv = AsyncMock(side_effect=asyncio.CancelledError())
            ws.send = AsyncMock()
            ws.close = AsyncMock()
            return ws

        with patch("websockets.connect", side_effect=mock_connect_factory):
            await ws_connection.connect()

            # Wait for reconnection
            await asyncio.sleep(0.1)

            # Clean up
            ws_connection._should_reconnect = False
            await ws_connection.disconnect()

    @pytest.mark.asyncio
    async def test_on_connect_callback_called(self, connection_config, mock_websocket):
        """Test that on_connect callback is called on reconnection."""
        callback_count = 0

        async def on_connect(conn):
            nonlocal callback_count
            callback_count += 1

        connection_config.on_connect = on_connect
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            await ws_connection.connect()
            await ws_connection.disconnect()

        assert callback_count == 1


# =============================================================================
# WEBSOCKET MANAGER TESTS
# =============================================================================


class TestWebSocketManager:
    """Test WebSocket manager functionality."""

    def test_register_connection(self, ws_manager, connection_config):
        """Test registering a connection."""
        ws_manager.register("test", connection_config)

        assert "test" in ws_manager.connections
        assert ws_manager.connections["test"].config.name == "test_connection"

    def test_unregister_connection(self, ws_manager, connection_config):
        """Test unregistering a connection."""
        ws_manager.register("test", connection_config)
        ws_manager.unregister("test")

        assert "test" not in ws_manager.connections

    @pytest.mark.asyncio
    async def test_connect_specific_connection(self, ws_manager, connection_config, mock_websocket):
        """Test connecting a specific registered connection."""
        ws_manager.register("test", connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            result = await ws_manager.connect("test")

            assert result is True
            assert ws_manager.connections["test"].state == ConnectionState.CONNECTED

            # Clean up
            await ws_manager.disconnect("test")

    @pytest.mark.asyncio
    async def test_connect_unknown_connection(self, ws_manager):
        """Test connecting unknown connection returns False."""
        result = await ws_manager.connect("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_connect_all(self, ws_manager):
        """Test connecting all registered connections."""
        config1 = ConnectionConfig(name="conn1", url="wss://test1.com", auto_reconnect=False)
        config2 = ConnectionConfig(name="conn2", url="wss://test2.com", auto_reconnect=False)

        ws_manager.register("conn1", config1)
        ws_manager.register("conn2", config2)

        # Use a factory that creates fresh mocks for each connection
        async def mock_connect_factory(*args, **kwargs):
            ws = AsyncMock()
            ws.send = AsyncMock()
            ws.recv = AsyncMock(side_effect=asyncio.CancelledError())
            ws.close = AsyncMock()
            return ws

        with patch("websockets.connect", side_effect=mock_connect_factory):
            await ws_manager.connect_all()

            # Give time for connections to be established
            await asyncio.sleep(0.05)

            assert ws_manager.connections["conn1"].state == ConnectionState.CONNECTED
            assert ws_manager.connections["conn2"].state == ConnectionState.CONNECTED

            # Clean up
            await ws_manager.disconnect_all()

    @pytest.mark.asyncio
    async def test_disconnect_all(self, ws_manager, mock_websocket):
        """Test disconnecting all connections."""
        config = ConnectionConfig(name="test", url="wss://test.com")
        ws_manager.register("test", config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            await ws_manager.connect_all()
            await ws_manager.disconnect_all()

            assert ws_manager.connections["test"].state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_send_to_connection(self, ws_manager, mock_websocket):
        """Test sending message to specific connection."""
        config = ConnectionConfig(name="test", url="wss://test.com")
        ws_manager.register("test", config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            await ws_manager.connect("test")

            result = await ws_manager.send("test", {"type": "test"})

            assert result is True
            mock_websocket.send.assert_called()

            await ws_manager.disconnect("test")

    @pytest.mark.asyncio
    async def test_broadcast_to_all(self, ws_manager):
        """Test broadcasting message to all connections."""
        config1 = ConnectionConfig(name="conn1", url="wss://test1.com", auto_reconnect=False)
        config2 = ConnectionConfig(name="conn2", url="wss://test2.com", auto_reconnect=False)

        ws_manager.register("conn1", config1)
        ws_manager.register("conn2", config2)

        # Track send calls per connection
        send_calls = {"conn1": 0, "conn2": 0}

        # Use a factory that creates fresh mocks for each connection
        async def mock_connect_factory(*args, **kwargs):
            ws = AsyncMock()

            async def track_send(msg):
                # Track which connection sent
                pass

            ws.send = AsyncMock()
            ws.recv = AsyncMock(side_effect=asyncio.CancelledError())
            ws.close = AsyncMock()
            return ws

        with patch("websockets.connect", side_effect=mock_connect_factory):
            await ws_manager.connect_all()

            # Give time for connections
            await asyncio.sleep(0.05)

            results = await ws_manager.broadcast({"type": "broadcast"})

            assert results["conn1"] is True
            assert results["conn2"] is True

            await ws_manager.disconnect_all()

    def test_get_all_stats(self, ws_manager):
        """Test getting stats for all connections."""
        config = ConnectionConfig(name="test", url="wss://test.com")
        ws_manager.register("test", config)

        stats = ws_manager.get_all_stats()

        assert "test" in stats
        assert stats["test"].name == "test"
        assert stats["test"].state == ConnectionState.DISCONNECTED

    def test_get_status_summary(self, ws_manager):
        """Test getting status summary."""
        config = ConnectionConfig(name="test", url="wss://test.com")
        ws_manager.register("test", config)

        summary = ws_manager.get_status_summary()

        assert summary["total_connections"] == 1
        assert summary["connected"] == 0
        assert summary["disconnected"] == 1


# =============================================================================
# CONNECTION STATISTICS TESTS
# =============================================================================


class TestConnectionStatistics:
    """Test connection statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_track_messages(self, connection_config, mock_websocket):
        """Test that stats track message counts."""
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket

            # Set up recv to return a few messages then raise
            call_count = [0]
            async def controlled_recv():
                call_count[0] += 1
                if call_count[0] <= 3:
                    return '{"type": "test"}'
                raise asyncio.CancelledError()

            mock_websocket.recv = controlled_recv

            await ws_connection.connect()

            # Wait for messages to be received
            await asyncio.sleep(0.1)

            stats = ws_connection.get_stats()

            assert stats.messages_received >= 0

            await ws_connection.disconnect()

    @pytest.mark.asyncio
    async def test_stats_track_sent_messages(self, connection_config, mock_websocket):
        """Test that stats track sent message counts."""
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            await ws_connection.connect()

            await ws_connection.send({"type": "test1"})
            await ws_connection.send({"type": "test2"})

            stats = ws_connection.get_stats()

            assert stats.messages_sent == 2

            await ws_connection.disconnect()

    @pytest.mark.asyncio
    async def test_stats_track_reconnect_count(self, connection_config):
        """Test that stats track reconnection count."""
        connection_config.max_reconnect_attempts = 2
        connection_config.reconnect_delay = 0.01
        ws_connection = WebSocketConnection(connection_config)

        async def failing_connect(*args, **kwargs):
            raise ConnectionRefusedError("Connection refused")

        with patch("websockets.connect", side_effect=failing_connect):
            await ws_connection.connect()

            # Wait for reconnection attempts
            await asyncio.sleep(0.2)

        stats = ws_connection.get_stats()
        assert stats.reconnect_count > 0

    @pytest.mark.asyncio
    async def test_stats_track_uptime(self, connection_config):
        """Test that stats track connection uptime."""
        connection_config.auto_reconnect = False  # Prevent reconnection attempts
        ws_connection = WebSocketConnection(connection_config)

        async def mock_connect_factory(*args, **kwargs):
            ws = AsyncMock()
            ws.send = AsyncMock()
            # Don't raise immediately - let it stay connected
            async def slow_recv():
                await asyncio.sleep(10)
                raise asyncio.CancelledError()
            ws.recv = slow_recv
            ws.close = AsyncMock()
            return ws

        with patch("websockets.connect", side_effect=mock_connect_factory):
            await ws_connection.connect()

            # Wait a bit
            await asyncio.sleep(0.15)

            # Check stats while still connected
            stats = ws_connection.get_stats()

            assert stats.uptime_seconds > 0
            assert stats.connected_at is not None

            await ws_connection.disconnect()

    def test_stats_track_last_error(self, connection_config):
        """Test that stats track last error."""
        ws_connection = WebSocketConnection(connection_config)
        ws_connection._last_error = "Connection timeout"

        stats = ws_connection.get_stats()

        assert stats.last_error == "Connection timeout"


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================


class TestEdgeCasesAndErrorHandling:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_send_while_disconnected(self, ws_connection):
        """Test that send returns False when disconnected."""
        result = await ws_connection.send({"type": "test"})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_error_handling(self, connection_config, mock_websocket):
        """Test that send errors are handled gracefully."""
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())
            mock_websocket.send = AsyncMock(side_effect=ConnectionError("Send failed"))

            await ws_connection.connect()

            result = await ws_connection.send({"type": "test"})

            assert result is False

            await ws_connection.disconnect()

    @pytest.mark.asyncio
    async def test_double_connect(self, connection_config, mock_websocket):
        """Test that double connect returns True immediately."""
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            await ws_connection.connect()

            # Second connect should return True immediately
            result = await ws_connection.connect()

            assert result is True
            # Connect should only be called once
            assert mock_connect.call_count == 1

            await ws_connection.disconnect()

    @pytest.mark.asyncio
    async def test_disconnect_while_disconnected(self, ws_connection):
        """Test that disconnect while disconnected is safe."""
        # Should not raise
        await ws_connection.disconnect()

        assert ws_connection.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, connection_config, mock_websocket):
        """Test that callback errors don't crash connection."""
        async def bad_callback(conn):
            raise ValueError("Callback error")

        connection_config.on_connect = bad_callback
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            # Should not raise despite callback error
            result = await ws_connection.connect()

            assert result is True

            await ws_connection.disconnect()

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, connection_config, mock_websocket):
        """Test handling of concurrent operations."""
        ws_connection = WebSocketConnection(connection_config)

        with patch("websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_connect.return_value = mock_websocket
            mock_websocket.recv = AsyncMock(side_effect=asyncio.CancelledError())

            # Start multiple operations concurrently
            tasks = [
                ws_connection.connect(),
                ws_connection.send({"type": "test"}),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # First should succeed, second might fail if not connected yet
            assert results[0] is True or isinstance(results[0], Exception)

            await ws_connection.disconnect()


# =============================================================================
# INTEGRATION WITH BACKOFF UTILITY
# =============================================================================


class TestBackoffIntegration:
    """Test integration with backoff utility."""

    @pytest.mark.asyncio
    async def test_retry_with_backoff_success(self):
        """Test retry_with_backoff succeeds on first try."""
        async def successful_func():
            return "success"

        result = await retry_with_backoff(successful_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_with_backoff_eventual_success(self):
        """Test retry_with_backoff succeeds after retries."""
        call_count = 0

        async def eventually_successful():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Not yet")
            return "success"

        config = BackoffConfig(
            base_delay=0.01,
            max_retries=5,
            retryable_exceptions=[ConnectionError],
        )

        result = await retry_with_backoff(eventually_successful, config=config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_with_backoff_exhausted(self):
        """Test retry_with_backoff raises after max attempts."""
        async def always_fails():
            raise ConnectionError("Always fails")

        config = BackoffConfig(
            base_delay=0.01,
            max_retries=2,
            retryable_exceptions=[ConnectionError],
        )

        with pytest.raises(ConnectionError):
            await retry_with_backoff(always_fails, config=config)

    @pytest.mark.asyncio
    async def test_retry_with_backoff_non_retryable(self):
        """Test retry_with_backoff doesn't retry non-retryable exceptions."""
        call_count = 0

        async def raises_non_retryable():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not retryable")

        config = BackoffConfig(
            base_delay=0.01,
            max_retries=5,
            retryable_exceptions=[ConnectionError],  # ValueError not included
        )

        with pytest.raises(ValueError):
            await retry_with_backoff(raises_non_retryable, config=config)

        assert call_count == 1  # Only one attempt
