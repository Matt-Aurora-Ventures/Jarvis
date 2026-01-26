"""
Tests for Yellowstone gRPC (Geyser) client.

Tests cover:
- Client initialization and configuration
- Connection establishment and reconnection
- Account subscriptions (DEX pools, wallets)
- Message parsing and event emission
- Error handling and circuit breaker patterns
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# Import the module under test (will fail until implemented)
try:
    from core.streaming.geyser_client import (
        GeyserClient,
        GeyserConfig,
        GeyserConnectionState,
        AccountUpdate,
        SubscriptionFilter,
        GeyserError,
        GeyserConnectionError,
        GeyserSubscriptionError,
    )
    HAS_GEYSER = True
except ImportError:
    HAS_GEYSER = False
    # Create mock classes for test discovery
    GeyserClient = None
    GeyserConfig = None
    GeyserConnectionState = None
    AccountUpdate = None
    SubscriptionFilter = None
    GeyserError = Exception
    GeyserConnectionError = Exception
    GeyserSubscriptionError = Exception


pytestmark = pytest.mark.skipif(not HAS_GEYSER, reason="geyser_client not implemented yet")


class TestGeyserConfig:
    """Tests for GeyserConfig dataclass."""

    def test_config_defaults(self):
        """Config should have sensible defaults."""
        config = GeyserConfig(endpoint="grpc.helius.xyz:443")

        assert config.endpoint == "grpc.helius.xyz:443"
        assert config.api_key is None
        assert config.use_tls is True
        assert config.reconnect_enabled is True
        assert config.max_reconnect_attempts == 10
        assert config.reconnect_delay_seconds == 1.0
        assert config.max_reconnect_delay_seconds == 60.0
        assert config.ping_interval_seconds == 30.0
        assert config.commitment == "confirmed"

    def test_config_custom_values(self):
        """Config should accept custom values."""
        config = GeyserConfig(
            endpoint="custom.endpoint:443",
            api_key="test-key",
            use_tls=False,
            reconnect_enabled=False,
            max_reconnect_attempts=5,
            commitment="finalized",
        )

        assert config.endpoint == "custom.endpoint:443"
        assert config.api_key == "test-key"
        assert config.use_tls is False
        assert config.reconnect_enabled is False
        assert config.max_reconnect_attempts == 5
        assert config.commitment == "finalized"

    def test_config_from_env(self):
        """Config should support loading from environment variables."""
        with patch.dict("os.environ", {
            "GEYSER_ENDPOINT": "env.endpoint:443",
            "GEYSER_API_KEY": "env-api-key",
        }):
            config = GeyserConfig.from_env()

            assert config.endpoint == "env.endpoint:443"
            assert config.api_key == "env-api-key"


class TestSubscriptionFilter:
    """Tests for subscription filter creation."""

    def test_account_filter(self):
        """Should create filter for specific accounts."""
        accounts = ["Account1...", "Account2..."]
        filter = SubscriptionFilter.accounts(accounts)

        assert filter.account_keys == accounts
        assert filter.owner is None
        assert filter.data_slice is None

    def test_program_filter(self):
        """Should create filter for program-owned accounts."""
        program_id = "RaydiumProgramId..."
        filter = SubscriptionFilter.program(program_id)

        assert filter.owner == program_id
        assert filter.account_keys == []

    def test_data_slice_filter(self):
        """Should support data slice for partial account data."""
        filter = SubscriptionFilter.accounts(
            ["Account1..."],
            data_slice_offset=0,
            data_slice_length=128,
        )

        assert filter.data_slice is not None
        assert filter.data_slice["offset"] == 0
        assert filter.data_slice["length"] == 128

    def test_filter_with_commitment(self):
        """Should support commitment level override."""
        filter = SubscriptionFilter.accounts(
            ["Account1..."],
            commitment="finalized",
        )

        assert filter.commitment == "finalized"


class TestGeyserConnectionState:
    """Tests for connection state enum."""

    def test_connection_states(self):
        """Should have all expected connection states."""
        assert GeyserConnectionState.DISCONNECTED is not None
        assert GeyserConnectionState.CONNECTING is not None
        assert GeyserConnectionState.CONNECTED is not None
        assert GeyserConnectionState.RECONNECTING is not None
        assert GeyserConnectionState.FAILED is not None


class TestAccountUpdate:
    """Tests for AccountUpdate dataclass."""

    def test_account_update_creation(self):
        """Should create account update with required fields."""
        update = AccountUpdate(
            pubkey="TestPubkey...",
            slot=12345678,
            lamports=1000000,
            owner="OwnerProgram...",
            data=b"account data bytes",
            executable=False,
            rent_epoch=100,
            write_version=999,
        )

        assert update.pubkey == "TestPubkey..."
        assert update.slot == 12345678
        assert update.lamports == 1000000
        assert update.owner == "OwnerProgram..."
        assert update.data == b"account data bytes"
        assert update.executable is False
        assert update.write_version == 999

    def test_account_update_timestamp(self):
        """Should include receive timestamp."""
        update = AccountUpdate(
            pubkey="TestPubkey...",
            slot=12345678,
            lamports=1000000,
            owner="OwnerProgram...",
            data=b"",
            executable=False,
            rent_epoch=100,
            write_version=999,
        )

        assert update.received_at is not None
        assert isinstance(update.received_at, float)


class TestGeyserClientInit:
    """Tests for GeyserClient initialization."""

    def test_init_with_config(self):
        """Should initialize with config object."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)

        assert client.config == config
        assert client.state == GeyserConnectionState.DISCONNECTED

    def test_init_with_endpoint_string(self):
        """Should initialize with just endpoint string."""
        client = GeyserClient.from_endpoint("test.endpoint:443", api_key="key")

        assert client.config.endpoint == "test.endpoint:443"
        assert client.config.api_key == "key"

    def test_init_helius_preset(self):
        """Should have preset for Helius Geyser."""
        with patch.dict("os.environ", {"HELIUS_API_KEY": "test-helius-key"}):
            client = GeyserClient.helius()

            assert "helius" in client.config.endpoint.lower()
            assert client.config.api_key == "test-helius-key"

    def test_init_quicknode_preset(self):
        """Should have preset for QuickNode Geyser."""
        with patch.dict("os.environ", {"QUICKNODE_GEYSER_URL": "qn.endpoint:443"}):
            client = GeyserClient.quicknode()

            assert client.config.endpoint == "qn.endpoint:443"


class TestGeyserClientConnection:
    """Tests for GeyserClient connection management."""

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Should establish gRPC connection successfully."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)

        with patch.object(client, "_create_channel", new_callable=AsyncMock) as mock_channel:
            mock_channel.return_value = MagicMock()

            await client.connect()

            assert client.state == GeyserConnectionState.CONNECTED
            mock_channel.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure_retries(self):
        """Should retry on connection failure."""
        config = GeyserConfig(
            endpoint="test.endpoint:443",
            max_reconnect_attempts=3,
            reconnect_delay_seconds=0.01,
        )
        client = GeyserClient(config)

        with patch.object(client, "_create_channel", new_callable=AsyncMock) as mock_channel:
            mock_channel.side_effect = GeyserConnectionError("Connection refused")

            with pytest.raises(GeyserConnectionError):
                await client.connect()

            # Should attempt max_reconnect_attempts times
            assert mock_channel.call_count == 3

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Should cleanly disconnect."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)
        mock_channel = MagicMock()
        mock_channel.close = AsyncMock()
        client._channel = mock_channel
        client.state = GeyserConnectionState.CONNECTED

        await client.disconnect()

        assert client.state == GeyserConnectionState.DISCONNECTED
        # Channel is set to None after disconnect, check before disconnect
        mock_channel.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_on_disconnect(self):
        """Should auto-reconnect when connection drops."""
        config = GeyserConfig(
            endpoint="test.endpoint:443",
            reconnect_enabled=True,
            reconnect_delay_seconds=0.01,
        )
        client = GeyserClient(config)

        connect_calls = []

        async def mock_connect():
            connect_calls.append(1)
            if len(connect_calls) == 1:
                raise GeyserConnectionError("Dropped")
            client.state = GeyserConnectionState.CONNECTED

        with patch.object(client, "connect", side_effect=mock_connect):
            with patch.object(client, "_handle_reconnect", new_callable=AsyncMock):
                # Simulate connection drop
                await client._on_connection_lost()

                assert client.state in [
                    GeyserConnectionState.RECONNECTING,
                    GeyserConnectionState.CONNECTED,
                ]


class TestGeyserClientSubscriptions:
    """Tests for GeyserClient subscription management."""

    @pytest.mark.asyncio
    async def test_subscribe_accounts(self):
        """Should subscribe to account updates."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)
        client.state = GeyserConnectionState.CONNECTED
        client._stub = MagicMock()
        client._stub.Subscribe = MagicMock(return_value=AsyncMock())

        accounts = ["Account1...", "Account2..."]
        subscription_id = await client.subscribe_accounts(accounts)

        assert subscription_id is not None
        assert subscription_id in client._subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_program(self):
        """Should subscribe to program-owned accounts."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)
        client.state = GeyserConnectionState.CONNECTED
        client._stub = MagicMock()
        client._stub.Subscribe = MagicMock(return_value=AsyncMock())

        # Raydium AMM program
        program_id = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"
        subscription_id = await client.subscribe_program(program_id)

        assert subscription_id is not None
        assert subscription_id in client._subscriptions

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Should unsubscribe from a subscription."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)
        client.state = GeyserConnectionState.CONNECTED
        client._subscriptions = {"sub-1": MagicMock()}

        await client.unsubscribe("sub-1")

        assert "sub-1" not in client._subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_requires_connection(self):
        """Should raise error if not connected."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)
        client.state = GeyserConnectionState.DISCONNECTED

        with pytest.raises(GeyserSubscriptionError, match="not connected"):
            await client.subscribe_accounts(["Account1..."])


class TestGeyserClientEventHandling:
    """Tests for GeyserClient event handling."""

    @pytest.mark.asyncio
    async def test_on_account_update_callback(self):
        """Should call registered callback on account update."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)

        received_updates = []

        async def handler(update: AccountUpdate):
            received_updates.append(update)

        client.on_account_update(handler)

        # Simulate receiving an update
        mock_update = AccountUpdate(
            pubkey="TestPubkey...",
            slot=12345678,
            lamports=1000000,
            owner="OwnerProgram...",
            data=b"test data",
            executable=False,
            rent_epoch=100,
            write_version=999,
        )
        await client._emit_account_update(mock_update)

        assert len(received_updates) == 1
        assert received_updates[0].pubkey == "TestPubkey..."

    @pytest.mark.asyncio
    async def test_multiple_callbacks(self):
        """Should support multiple callbacks."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)

        calls_1 = []
        calls_2 = []

        async def handler1(update):
            calls_1.append(update)

        async def handler2(update):
            calls_2.append(update)

        client.on_account_update(handler1)
        client.on_account_update(handler2)

        mock_update = AccountUpdate(
            pubkey="Test...",
            slot=1,
            lamports=0,
            owner="",
            data=b"",
            executable=False,
            rent_epoch=0,
            write_version=1,
        )
        await client._emit_account_update(mock_update)

        assert len(calls_1) == 1
        assert len(calls_2) == 1

    @pytest.mark.asyncio
    async def test_callback_error_isolation(self):
        """Should not crash if one callback raises."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)

        calls = []

        async def bad_handler(update):
            raise ValueError("Handler error")

        async def good_handler(update):
            calls.append(update)

        client.on_account_update(bad_handler)
        client.on_account_update(good_handler)

        mock_update = AccountUpdate(
            pubkey="Test...",
            slot=1,
            lamports=0,
            owner="",
            data=b"",
            executable=False,
            rent_epoch=0,
            write_version=1,
        )

        # Should not raise
        await client._emit_account_update(mock_update)

        # Good handler should still be called
        assert len(calls) == 1


class TestGeyserClientMetrics:
    """Tests for GeyserClient metrics and monitoring."""

    def test_get_stats(self):
        """Should return connection statistics."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)
        client.state = GeyserConnectionState.CONNECTED
        client._messages_received = 100
        client._bytes_received = 50000
        client._reconnect_count = 2

        stats = client.get_stats()

        assert stats["state"] == "connected"
        assert stats["messages_received"] == 100
        assert stats["bytes_received"] == 50000
        assert stats["reconnect_count"] == 2

    def test_latency_tracking(self):
        """Should track message latency."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)

        # Simulate latency measurements
        client._record_latency(5.0)  # 5ms
        client._record_latency(8.0)  # 8ms
        client._record_latency(3.0)  # 3ms

        stats = client.get_stats()

        assert stats["avg_latency_ms"] is not None
        assert 3.0 <= stats["avg_latency_ms"] <= 8.0


class TestGeyserClientContextManager:
    """Tests for async context manager protocol."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Should support async context manager."""
        config = GeyserConfig(endpoint="test.endpoint:443")

        with patch.object(GeyserClient, "connect", new_callable=AsyncMock):
            with patch.object(GeyserClient, "disconnect", new_callable=AsyncMock):
                async with GeyserClient(config) as client:
                    assert client is not None

                client.disconnect.assert_called_once()


class TestGeyserClientErrorHandling:
    """Tests for error handling and circuit breaker."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens(self):
        """Should open circuit after repeated failures."""
        config = GeyserConfig(
            endpoint="test.endpoint:443",
            circuit_breaker_threshold=3,
            circuit_breaker_timeout_seconds=60,
        )
        client = GeyserClient(config)

        # Simulate 3 consecutive failures
        for _ in range(3):
            client._record_failure()

        assert client._circuit_open is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open(self):
        """Should allow test request after timeout."""
        config = GeyserConfig(
            endpoint="test.endpoint:443",
            circuit_breaker_threshold=3,
            circuit_breaker_timeout_seconds=0.01,  # Very short for test
        )
        client = GeyserClient(config)

        # Open circuit
        for _ in range(3):
            client._record_failure()

        assert client._circuit_open is True

        # Wait for timeout
        await asyncio.sleep(0.02)

        # Should allow test
        assert client._should_allow_request() is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_on_success(self):
        """Should close circuit after successful request."""
        config = GeyserConfig(endpoint="test.endpoint:443")
        client = GeyserClient(config)
        client._circuit_open = True
        client._failure_count = 3

        client._record_success()

        assert client._circuit_open is False
        assert client._failure_count == 0
