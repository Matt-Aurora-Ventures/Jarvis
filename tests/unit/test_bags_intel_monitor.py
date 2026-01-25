"""
Comprehensive unit tests for bots/bags_intel/monitor.py

Tests cover:
- WebSocket connection to Bitquery
- Authentication with API key
- Connection error handling
- Reconnection logic with backoff
- Graduation detection and parsing
- Message processing
- Polling fallback functionality
- Error recovery scenarios

Coverage target: 60%+
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from datetime import datetime
from typing import Optional

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.bags_intel.monitor import (
    GraduationMonitor,
    PollingFallback,
    GRADUATION_SUBSCRIPTION,
)
from bots.bags_intel.config import BagsIntelConfig


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def config():
    """Create a basic BagsIntelConfig for testing."""
    return BagsIntelConfig(
        bitquery_api_key="test-api-key-12345",
        bitquery_ws_url="wss://test.bitquery.io/graphql",
        telegram_bot_token="test-token",
        telegram_chat_id="test-chat-id",
    )


@pytest.fixture
def config_no_api_key():
    """Create config without Bitquery API key."""
    return BagsIntelConfig(
        bitquery_api_key="",
        telegram_bot_token="test-token",
        telegram_chat_id="test-chat-id",
    )


@pytest.fixture
def monitor(config):
    """Create a GraduationMonitor instance."""
    return GraduationMonitor(config=config)


@pytest.fixture
def monitor_with_callback(config):
    """Create a GraduationMonitor with a graduation callback."""
    callback = AsyncMock()
    return GraduationMonitor(config=config, on_graduation=callback), callback


@pytest.fixture
def polling_fallback(config):
    """Create a PollingFallback instance."""
    return PollingFallback(config=config, poll_interval=1)


@pytest.fixture
def polling_with_callback(config):
    """Create a PollingFallback with a graduation callback."""
    callback = AsyncMock()
    return PollingFallback(config=config, on_graduation=callback, poll_interval=1), callback


@pytest.fixture
def sample_graduation_payload():
    """Create a sample graduation event payload from Bitquery."""
    return {
        "data": {
            "Solana": {
                "Instructions": [
                    {
                        "Block": {
                            "Time": "2026-01-25T10:30:00Z",
                            "Slot": 123456789
                        },
                        "Transaction": {
                            "Signature": "5KtP9UcJZH1234567890abcdefghijklmnopqrstuvwxyz",
                            "Signer": "CreatorWallet111111111111111111111111111111111"
                        },
                        "Instruction": {
                            "Program": {
                                "Method": "migrate_meteora_damm"
                            },
                            "Accounts": [
                                {
                                    "Address": "Account1111111111111111111111111111111111",
                                    "IsWritable": True,
                                    "Token": {
                                        "Mint": "TokenMint11111111111111111111111111111111111",
                                        "Owner": "Owner11111111111111111111111111111111111111"
                                    }
                                },
                                {
                                    "Address": "Account2222222222222222222222222222222222",
                                    "IsWritable": False,
                                    "Token": None
                                }
                            ]
                        }
                    }
                ]
            }
        }
    }


@pytest.fixture
def sample_dexscreener_response():
    """Create a sample DexScreener API response."""
    # Create timestamp for a recent pair (within last hour)
    recent_time = int((datetime.utcnow().timestamp() - 1800) * 1000)  # 30 min ago
    old_time = int((datetime.utcnow().timestamp() - 7200) * 1000)  # 2 hours ago

    return {
        "pairs": [
            {
                "baseToken": {
                    "address": "RecentToken1111111111111111111111111111111111",
                    "name": "Recent Token",
                    "symbol": "RECENT"
                },
                "pairCreatedAt": recent_time
            },
            {
                "baseToken": {
                    "address": "OldToken1111111111111111111111111111111111111",
                    "name": "Old Token",
                    "symbol": "OLD"
                },
                "pairCreatedAt": old_time
            }
        ]
    }


# =============================================================================
# WebSocket Connection Tests
# =============================================================================

class TestWebSocketConnection:
    """Tests for WebSocket connection functionality."""

    @pytest.mark.asyncio
    async def test_connect_success(self, config):
        """Test successful WebSocket connection."""
        monitor = GraduationMonitor(config=config)

        with patch("bots.bags_intel.monitor.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "connection_ack"}))
            mock_connect.return_value = mock_ws

            ws = await monitor.connect()

            # Verify connection was made with correct parameters
            mock_connect.assert_called_once()
            call_args = mock_connect.call_args
            assert call_args[0][0] == config.bitquery_ws_url
            assert "Authorization" in call_args[1]["additional_headers"]
            assert f"Bearer {config.bitquery_api_key}" in call_args[1]["additional_headers"]["Authorization"]

            # Verify connection_init was sent
            mock_ws.send.assert_called_once()
            sent_msg = json.loads(mock_ws.send.call_args[0][0])
            assert sent_msg["type"] == "connection_init"

    @pytest.mark.asyncio
    async def test_connect_no_api_key_raises_error(self, config_no_api_key):
        """Test that connect raises ValueError when API key is missing."""
        monitor = GraduationMonitor(config=config_no_api_key)

        with pytest.raises(ValueError, match="BITQUERY_API_KEY not configured"):
            await monitor.connect()

    @pytest.mark.asyncio
    async def test_connect_ack_failure(self, config):
        """Test connection failure when ack is not received."""
        monitor = GraduationMonitor(config=config)

        with patch("bots.bags_intel.monitor.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            # Return error instead of ack
            mock_ws.recv = AsyncMock(return_value=json.dumps({
                "type": "error",
                "payload": "Authentication failed"
            }))
            mock_connect.return_value = mock_ws

            with pytest.raises(ConnectionError, match="Connection not acknowledged"):
                await monitor.connect()

    @pytest.mark.asyncio
    async def test_connect_with_correct_headers(self, config):
        """Test that connection includes correct headers."""
        monitor = GraduationMonitor(config=config)

        with patch("bots.bags_intel.monitor.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "connection_ack"}))
            mock_connect.return_value = mock_ws

            await monitor.connect()

            call_kwargs = mock_connect.call_args[1]
            headers = call_kwargs["additional_headers"]

            assert headers["Authorization"] == f"Bearer {config.bitquery_api_key}"
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_connect_with_correct_subprotocol(self, config):
        """Test that connection uses graphql-ws subprotocol."""
        monitor = GraduationMonitor(config=config)

        with patch("bots.bags_intel.monitor.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "connection_ack"}))
            mock_connect.return_value = mock_ws

            await monitor.connect()

            call_kwargs = mock_connect.call_args[1]
            assert "graphql-ws" in call_kwargs["subprotocols"]

    @pytest.mark.asyncio
    async def test_connect_ping_settings(self, config):
        """Test that connection includes ping interval and timeout."""
        monitor = GraduationMonitor(config=config)

        with patch("bots.bags_intel.monitor.websockets.connect", new_callable=AsyncMock) as mock_connect:
            mock_ws = AsyncMock()
            mock_ws.recv = AsyncMock(return_value=json.dumps({"type": "connection_ack"}))
            mock_connect.return_value = mock_ws

            await monitor.connect()

            call_kwargs = mock_connect.call_args[1]
            assert call_kwargs["ping_interval"] == 30
            assert call_kwargs["ping_timeout"] == 10


# =============================================================================
# Subscribe Tests
# =============================================================================

class TestSubscribe:
    """Tests for subscription functionality."""

    @pytest.mark.asyncio
    async def test_subscribe_sends_correct_message(self, monitor):
        """Test that subscribe sends correct GraphQL subscription."""
        mock_ws = AsyncMock()

        await monitor.subscribe(mock_ws)

        mock_ws.send.assert_called_once()
        sent_msg = json.loads(mock_ws.send.call_args[0][0])

        assert sent_msg["id"] == "graduations"
        assert sent_msg["type"] == "subscribe"
        assert "query" in sent_msg["payload"]
        assert "BagsGraduations" in sent_msg["payload"]["query"]

    @pytest.mark.asyncio
    async def test_subscribe_includes_graduation_query(self, monitor):
        """Test that subscription includes the graduation query."""
        mock_ws = AsyncMock()

        await monitor.subscribe(mock_ws)

        sent_msg = json.loads(mock_ws.send.call_args[0][0])
        query = sent_msg["payload"]["query"]

        # Verify key parts of the query
        assert "Solana" in query
        assert "Instructions" in query
        assert "migrate_meteora_damm" in query
        assert "migration_damm_v2" in query


# =============================================================================
# Message Processing Tests
# =============================================================================

class TestMessageProcessing:
    """Tests for _process_message method."""

    @pytest.mark.asyncio
    async def test_process_next_message(self, monitor_with_callback, sample_graduation_payload):
        """Test processing a 'next' type message with graduation data."""
        monitor, callback = monitor_with_callback

        message = json.dumps({
            "type": "next",
            "payload": sample_graduation_payload
        })

        await monitor._process_message(message)

        # Callback should have been called with graduation event
        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert event["mint_address"] == "TokenMint11111111111111111111111111111111111"

    @pytest.mark.asyncio
    async def test_process_error_message(self, monitor):
        """Test processing an 'error' type message."""
        message = json.dumps({
            "type": "error",
            "payload": {"message": "Subscription error"}
        })

        # Should not raise, just log
        await monitor._process_message(message)

    @pytest.mark.asyncio
    async def test_process_invalid_json(self, monitor):
        """Test processing invalid JSON message."""
        invalid_message = "not valid json {"

        # Should not raise, just log
        await monitor._process_message(invalid_message)

    @pytest.mark.asyncio
    async def test_process_unknown_message_type(self, monitor):
        """Test processing unknown message type."""
        message = json.dumps({
            "type": "unknown_type",
            "payload": {}
        })

        # Should not raise, just ignore
        await monitor._process_message(message)

    @pytest.mark.asyncio
    async def test_process_message_without_payload(self, monitor):
        """Test processing message without payload."""
        message = json.dumps({
            "type": "next"
            # No payload
        })

        # Should not raise
        await monitor._process_message(message)

    @pytest.mark.asyncio
    async def test_process_message_exception_handling(self, monitor_with_callback):
        """Test that exceptions during processing are caught."""
        monitor, callback = monitor_with_callback
        callback.side_effect = Exception("Callback error")

        message = json.dumps({
            "type": "next",
            "payload": {
                "data": {
                    "Solana": {
                        "Instructions": [{
                            "Block": {"Time": "2026-01-25T10:00:00Z", "Slot": 123},
                            "Transaction": {"Signature": "sig123", "Signer": "creator123"},
                            "Instruction": {
                                "Accounts": [{
                                    "Token": {"Mint": "TestMint123"}
                                }]
                            }
                        }]
                    }
                }
            }
        })

        # Should not raise even with callback error
        await monitor._process_message(message)


# =============================================================================
# Graduation Event Handling Tests
# =============================================================================

class TestGraduationEventHandling:
    """Tests for _handle_graduation_event method."""

    @pytest.mark.asyncio
    async def test_handle_graduation_extracts_token_mint(
        self, monitor_with_callback, sample_graduation_payload
    ):
        """Test that graduation event correctly extracts token mint."""
        monitor, callback = monitor_with_callback

        await monitor._handle_graduation_event(sample_graduation_payload)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert event["mint_address"] == "TokenMint11111111111111111111111111111111111"

    @pytest.mark.asyncio
    async def test_handle_graduation_extracts_signature(
        self, monitor_with_callback, sample_graduation_payload
    ):
        """Test that graduation event correctly extracts transaction signature."""
        monitor, callback = monitor_with_callback

        await monitor._handle_graduation_event(sample_graduation_payload)

        event = callback.call_args[0][0]
        assert event["signature"] == "5KtP9UcJZH1234567890abcdefghijklmnopqrstuvwxyz"

    @pytest.mark.asyncio
    async def test_handle_graduation_extracts_creator(
        self, monitor_with_callback, sample_graduation_payload
    ):
        """Test that graduation event correctly extracts creator address."""
        monitor, callback = monitor_with_callback

        await monitor._handle_graduation_event(sample_graduation_payload)

        event = callback.call_args[0][0]
        assert event["creator"] == "CreatorWallet111111111111111111111111111111111"

    @pytest.mark.asyncio
    async def test_handle_graduation_extracts_timestamp(
        self, monitor_with_callback, sample_graduation_payload
    ):
        """Test that graduation event correctly extracts timestamp."""
        monitor, callback = monitor_with_callback

        await monitor._handle_graduation_event(sample_graduation_payload)

        event = callback.call_args[0][0]
        assert event["timestamp"] == "2026-01-25T10:30:00Z"

    @pytest.mark.asyncio
    async def test_handle_graduation_extracts_slot(
        self, monitor_with_callback, sample_graduation_payload
    ):
        """Test that graduation event correctly extracts slot number."""
        monitor, callback = monitor_with_callback

        await monitor._handle_graduation_event(sample_graduation_payload)

        event = callback.call_args[0][0]
        assert event["slot"] == 123456789

    @pytest.mark.asyncio
    async def test_handle_graduation_skips_duplicate_mints(
        self, monitor_with_callback, sample_graduation_payload
    ):
        """Test that duplicate token mints are skipped."""
        monitor, callback = monitor_with_callback

        # Process same graduation twice
        await monitor._handle_graduation_event(sample_graduation_payload)
        await monitor._handle_graduation_event(sample_graduation_payload)

        # Callback should only be called once
        assert callback.call_count == 1

    @pytest.mark.asyncio
    async def test_handle_graduation_tracks_processed_mints(
        self, monitor_with_callback, sample_graduation_payload
    ):
        """Test that processed mints are tracked in set."""
        monitor, callback = monitor_with_callback

        assert len(monitor._processed_mints) == 0

        await monitor._handle_graduation_event(sample_graduation_payload)

        assert "TokenMint11111111111111111111111111111111111" in monitor._processed_mints

    @pytest.mark.asyncio
    async def test_handle_graduation_skips_no_token_mint(self, monitor_with_callback):
        """Test that events without token mint are skipped."""
        monitor, callback = monitor_with_callback

        payload = {
            "data": {
                "Solana": {
                    "Instructions": [{
                        "Block": {"Time": "2026-01-25T10:00:00Z", "Slot": 123},
                        "Transaction": {"Signature": "sig123", "Signer": "creator123"},
                        "Instruction": {
                            "Accounts": [
                                {"Address": "addr1", "Token": None},
                                {"Address": "addr2", "Token": None}
                            ]
                        }
                    }]
                }
            }
        }

        await monitor._handle_graduation_event(payload)

        # No callback should be made
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_graduation_empty_instructions(self, monitor_with_callback):
        """Test handling of payload with empty instructions."""
        monitor, callback = monitor_with_callback

        payload = {
            "data": {
                "Solana": {
                    "Instructions": []
                }
            }
        }

        await monitor._handle_graduation_event(payload)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_graduation_missing_solana_key(self, monitor_with_callback):
        """Test handling of payload missing Solana key."""
        monitor, callback = monitor_with_callback

        payload = {
            "data": {}
        }

        # Should not raise
        await monitor._handle_graduation_event(payload)
        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_graduation_no_callback(self, config, sample_graduation_payload):
        """Test graduation handling when no callback is set."""
        monitor = GraduationMonitor(config=config, on_graduation=None)

        # Should not raise even without callback
        await monitor._handle_graduation_event(sample_graduation_payload)

        # Mint should still be tracked
        assert "TokenMint11111111111111111111111111111111111" in monitor._processed_mints

    @pytest.mark.asyncio
    async def test_handle_graduation_multiple_instructions(self, monitor_with_callback):
        """Test handling payload with multiple instructions."""
        monitor, callback = monitor_with_callback

        payload = {
            "data": {
                "Solana": {
                    "Instructions": [
                        {
                            "Block": {"Time": "2026-01-25T10:00:00Z", "Slot": 123},
                            "Transaction": {"Signature": "sig1", "Signer": "creator1"},
                            "Instruction": {
                                "Accounts": [{"Token": {"Mint": "Mint1"}}]
                            }
                        },
                        {
                            "Block": {"Time": "2026-01-25T10:01:00Z", "Slot": 124},
                            "Transaction": {"Signature": "sig2", "Signer": "creator2"},
                            "Instruction": {
                                "Accounts": [{"Token": {"Mint": "Mint2"}}]
                            }
                        }
                    ]
                }
            }
        }

        await monitor._handle_graduation_event(payload)

        # Both should be processed
        assert callback.call_count == 2
        assert "Mint1" in monitor._processed_mints
        assert "Mint2" in monitor._processed_mints

    @pytest.mark.asyncio
    async def test_handle_graduation_finds_mint_in_later_account(self, monitor_with_callback):
        """Test that mint is found even if not in first account."""
        monitor, callback = monitor_with_callback

        payload = {
            "data": {
                "Solana": {
                    "Instructions": [{
                        "Block": {"Time": "2026-01-25T10:00:00Z", "Slot": 123},
                        "Transaction": {"Signature": "sig123", "Signer": "creator123"},
                        "Instruction": {
                            "Accounts": [
                                {"Address": "acc1", "Token": None},
                                {"Address": "acc2", "Token": {"Mint": "FoundMint123"}},
                                {"Address": "acc3", "Token": None}
                            ]
                        }
                    }]
                }
            }
        }

        await monitor._handle_graduation_event(payload)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert event["mint_address"] == "FoundMint123"


# =============================================================================
# Run Loop Tests
# =============================================================================

class TestRunLoop:
    """Tests for the run() method."""

    @pytest.mark.asyncio
    async def test_run_connects_and_subscribes(self, config):
        """Test that run() connects and subscribes."""
        monitor = GraduationMonitor(config=config)

        with patch.object(monitor, "connect") as mock_connect, \
             patch.object(monitor, "subscribe") as mock_subscribe:

            mock_ws = AsyncMock()
            mock_ws.__aiter__ = AsyncMock(return_value=iter([]))
            mock_connect.return_value = mock_ws

            # Run briefly then stop
            async def stop_after_delay():
                await asyncio.sleep(0.05)
                monitor._running = False

            await asyncio.gather(
                monitor.run(),
                stop_after_delay()
            )

            mock_connect.assert_called()
            mock_subscribe.assert_called_with(mock_ws)

    @pytest.mark.asyncio
    async def test_run_processes_messages(self, config):
        """Test that run() processes incoming messages."""
        monitor = GraduationMonitor(config=config)

        messages = [
            json.dumps({"type": "next", "payload": {"data": {}}}),
        ]

        with patch.object(monitor, "connect") as mock_connect, \
             patch.object(monitor, "subscribe"), \
             patch.object(monitor, "_process_message") as mock_process:

            mock_ws = AsyncMock()

            async def message_generator():
                for msg in messages:
                    yield msg
                monitor._running = False

            mock_ws.__aiter__ = lambda self: message_generator()
            mock_connect.return_value = mock_ws

            await monitor.run()

            mock_process.assert_called()

    @pytest.mark.asyncio
    async def test_run_reconnects_on_connection_closed(self, config):
        """Test that run() reconnects when connection is closed."""
        import websockets

        monitor = GraduationMonitor(config=config)
        connect_count = 0

        with patch.object(monitor, "connect") as mock_connect, \
             patch.object(monitor, "subscribe"), \
             patch("asyncio.sleep") as mock_sleep:

            async def connect_side_effect():
                nonlocal connect_count
                connect_count += 1
                if connect_count == 1:
                    raise websockets.exceptions.ConnectionClosed(None, None)
                elif connect_count == 2:
                    # Second attempt - create mock that stops
                    mock_ws = AsyncMock()
                    mock_ws.__aiter__ = AsyncMock(return_value=iter([]))
                    monitor._running = False
                    return mock_ws

            mock_connect.side_effect = connect_side_effect
            mock_sleep.return_value = None

            await monitor.run()

            assert connect_count == 2
            mock_sleep.assert_called()

    @pytest.mark.asyncio
    async def test_run_reconnects_on_general_error(self, config):
        """Test that run() reconnects on general errors."""
        monitor = GraduationMonitor(config=config)
        connect_count = 0

        with patch.object(monitor, "connect") as mock_connect, \
             patch.object(monitor, "subscribe"), \
             patch("asyncio.sleep") as mock_sleep:

            async def connect_side_effect():
                nonlocal connect_count
                connect_count += 1
                if connect_count == 1:
                    raise Exception("Network error")
                else:
                    mock_ws = AsyncMock()
                    mock_ws.__aiter__ = AsyncMock(return_value=iter([]))
                    monitor._running = False
                    return mock_ws

            mock_connect.side_effect = connect_side_effect
            mock_sleep.return_value = None

            await monitor.run()

            assert connect_count == 2

    @pytest.mark.asyncio
    async def test_run_uses_reconnect_delay(self, config):
        """Test that reconnect uses the configured delay."""
        monitor = GraduationMonitor(config=config)
        monitor._reconnect_delay = 10  # Set delay

        with patch.object(monitor, "connect") as mock_connect, \
             patch.object(monitor, "subscribe"), \
             patch("asyncio.sleep") as mock_sleep:

            connect_count = 0

            async def connect_side_effect():
                nonlocal connect_count
                connect_count += 1
                if connect_count == 1:
                    raise Exception("Error")
                else:
                    mock_ws = AsyncMock()
                    mock_ws.__aiter__ = AsyncMock(return_value=iter([]))
                    monitor._running = False
                    return mock_ws

            mock_connect.side_effect = connect_side_effect
            mock_sleep.return_value = None

            await monitor.run()

            mock_sleep.assert_called_with(10)

    @pytest.mark.asyncio
    async def test_run_stops_on_running_false(self, config):
        """Test that run() stops when _running is False."""
        monitor = GraduationMonitor(config=config)

        with patch.object(monitor, "connect") as mock_connect, \
             patch.object(monitor, "subscribe"):

            mock_ws = AsyncMock()

            async def message_generator():
                # Stop after yielding one message
                monitor._running = False
                yield json.dumps({"type": "ping"})

            mock_ws.__aiter__ = lambda self: message_generator()
            mock_connect.return_value = mock_ws

            await monitor.run()

            # Should have stopped
            assert not monitor._running


# =============================================================================
# Stop Tests
# =============================================================================

class TestStop:
    """Tests for the stop() method."""

    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, monitor):
        """Test that stop() sets _running to False."""
        monitor._running = True

        await monitor.stop()

        assert monitor._running is False

    @pytest.mark.asyncio
    async def test_stop_closes_websocket(self, monitor):
        """Test that stop() closes the WebSocket connection."""
        mock_ws = AsyncMock()
        monitor._ws = mock_ws
        monitor._running = True

        await monitor.stop()

        mock_ws.close.assert_called_once()
        assert monitor._ws is None

    @pytest.mark.asyncio
    async def test_stop_handles_no_websocket(self, monitor):
        """Test that stop() handles case when no WebSocket exists."""
        monitor._ws = None
        monitor._running = True

        # Should not raise
        await monitor.stop()

        assert monitor._running is False


# =============================================================================
# Polling Fallback Tests
# =============================================================================

class TestPollingFallback:
    """Tests for PollingFallback class."""

    @pytest.mark.asyncio
    async def test_polling_run_starts(self, polling_fallback):
        """Test that polling run() starts properly."""
        with patch("aiohttp.ClientSession") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

            async def stop_after_delay():
                await asyncio.sleep(0.05)
                polling_fallback._running = False

            with patch.object(polling_fallback, "_poll_dexscreener"):
                await asyncio.gather(
                    polling_fallback.run(),
                    stop_after_delay()
                )

                assert polling_fallback._running is False

    @pytest.mark.asyncio
    async def test_polling_stop(self, polling_fallback):
        """Test that stop() sets _running to False."""
        polling_fallback._running = True

        await polling_fallback.stop()

        assert polling_fallback._running is False

    @pytest.mark.asyncio
    async def test_poll_dexscreener_success(
        self, polling_with_callback, sample_dexscreener_response
    ):
        """Test successful DexScreener polling."""
        fallback, callback = polling_with_callback

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=sample_dexscreener_response)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        await fallback._poll_dexscreener(mock_session)

        # Should have called callback for recent token
        callback.assert_called()
        event = callback.call_args[0][0]
        assert event["mint_address"] == "RecentToken1111111111111111111111111111111111"

    @pytest.mark.asyncio
    async def test_poll_dexscreener_non_200_status(self, polling_with_callback):
        """Test handling of non-200 status from DexScreener."""
        fallback, callback = polling_with_callback

        mock_response = AsyncMock()
        mock_response.status = 500

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        await fallback._poll_dexscreener(mock_session)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_dexscreener_skips_duplicates(self, polling_with_callback):
        """Test that polling skips already-seen tokens."""
        fallback, callback = polling_with_callback

        # Add token to already-checked set
        fallback._last_checked.add("RecentToken1111111111111111111111111111111111")

        recent_time = int((datetime.utcnow().timestamp() - 1800) * 1000)
        response = {
            "pairs": [{
                "baseToken": {"address": "RecentToken1111111111111111111111111111111111"},
                "pairCreatedAt": recent_time
            }]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        await fallback._poll_dexscreener(mock_session)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_dexscreener_skips_old_tokens(self, polling_with_callback):
        """Test that polling skips tokens older than 1 hour."""
        fallback, callback = polling_with_callback

        old_time = int((datetime.utcnow().timestamp() - 7200) * 1000)  # 2 hours ago
        response = {
            "pairs": [{
                "baseToken": {"address": "OldToken123"},
                "pairCreatedAt": old_time
            }]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        await fallback._poll_dexscreener(mock_session)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_dexscreener_handles_exception(self, polling_with_callback):
        """Test that polling handles exceptions gracefully."""
        fallback, callback = polling_with_callback

        mock_session = AsyncMock()
        mock_session.get.side_effect = Exception("Network error")

        # Should not raise
        await fallback._poll_dexscreener(mock_session)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_dexscreener_no_pairs(self, polling_with_callback):
        """Test handling of response with no pairs."""
        fallback, callback = polling_with_callback

        response = {"pairs": []}

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        await fallback._poll_dexscreener(mock_session)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_dexscreener_missing_address(self, polling_with_callback):
        """Test handling of pairs missing base token address."""
        fallback, callback = polling_with_callback

        recent_time = int((datetime.utcnow().timestamp() - 1800) * 1000)
        response = {
            "pairs": [{
                "baseToken": {},  # Missing address
                "pairCreatedAt": recent_time
            }]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        await fallback._poll_dexscreener(mock_session)

        callback.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_dexscreener_no_callback(self, config):
        """Test polling when no callback is set."""
        fallback = PollingFallback(config=config, on_graduation=None)

        recent_time = int((datetime.utcnow().timestamp() - 1800) * 1000)
        response = {
            "pairs": [{
                "baseToken": {"address": "TokenAddress123"},
                "pairCreatedAt": recent_time
            }]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        # Should not raise even without callback
        await fallback._poll_dexscreener(mock_session)

    @pytest.mark.asyncio
    async def test_poll_dexscreener_zero_created_at(self, polling_with_callback):
        """Test handling of pairs with zero pairCreatedAt."""
        fallback, callback = polling_with_callback

        response = {
            "pairs": [{
                "baseToken": {"address": "Token123"},
                "pairCreatedAt": 0
            }]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=response)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_response),
            __aexit__=AsyncMock(return_value=None)
        ))

        await fallback._poll_dexscreener(mock_session)

        callback.assert_not_called()


# =============================================================================
# Initialization Tests
# =============================================================================

class TestMonitorInitialization:
    """Tests for GraduationMonitor initialization."""

    def test_init_with_config(self, config):
        """Test initialization with config."""
        monitor = GraduationMonitor(config=config)

        assert monitor.config == config
        assert monitor._running is False
        assert monitor._ws is None
        assert len(monitor._processed_mints) == 0
        assert monitor._reconnect_delay == 5

    def test_init_with_callback(self, config):
        """Test initialization with callback."""
        callback = AsyncMock()
        monitor = GraduationMonitor(config=config, on_graduation=callback)

        assert monitor.on_graduation == callback

    def test_init_without_callback(self, config):
        """Test initialization without callback."""
        monitor = GraduationMonitor(config=config)

        assert monitor.on_graduation is None


class TestPollingFallbackInitialization:
    """Tests for PollingFallback initialization."""

    def test_init_with_config(self, config):
        """Test initialization with config."""
        fallback = PollingFallback(config=config)

        assert fallback.config == config
        assert fallback._running is False
        assert fallback.poll_interval == 30  # Default
        assert len(fallback._last_checked) == 0

    def test_init_with_custom_interval(self, config):
        """Test initialization with custom poll interval."""
        fallback = PollingFallback(config=config, poll_interval=60)

        assert fallback.poll_interval == 60

    def test_init_with_callback(self, config):
        """Test initialization with callback."""
        callback = AsyncMock()
        fallback = PollingFallback(config=config, on_graduation=callback)

        assert fallback.on_graduation == callback


# =============================================================================
# GraphQL Query Tests
# =============================================================================

class TestGraduationSubscription:
    """Tests for the GRADUATION_SUBSCRIPTION constant."""

    def test_subscription_contains_solana(self):
        """Test that subscription query contains Solana."""
        assert "Solana" in GRADUATION_SUBSCRIPTION

    def test_subscription_contains_program_address(self):
        """Test that subscription contains the Meteora DBC program address."""
        assert "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN" in GRADUATION_SUBSCRIPTION

    def test_subscription_contains_migrate_methods(self):
        """Test that subscription contains migration methods."""
        assert "migrate_meteora_damm" in GRADUATION_SUBSCRIPTION
        assert "migration_damm_v2" in GRADUATION_SUBSCRIPTION

    def test_subscription_contains_required_fields(self):
        """Test that subscription requests required fields."""
        assert "Block" in GRADUATION_SUBSCRIPTION
        assert "Time" in GRADUATION_SUBSCRIPTION
        assert "Slot" in GRADUATION_SUBSCRIPTION
        assert "Transaction" in GRADUATION_SUBSCRIPTION
        assert "Signature" in GRADUATION_SUBSCRIPTION
        assert "Signer" in GRADUATION_SUBSCRIPTION
        assert "Token" in GRADUATION_SUBSCRIPTION
        assert "Mint" in GRADUATION_SUBSCRIPTION


# =============================================================================
# Error Recovery Tests
# =============================================================================

class TestErrorRecovery:
    """Tests for error recovery scenarios."""

    @pytest.mark.asyncio
    async def test_continues_after_malformed_message(self, monitor_with_callback):
        """Test that monitor continues after malformed message."""
        monitor, callback = monitor_with_callback

        # Process malformed message
        await monitor._process_message("not json")

        # Should still be able to process valid messages
        valid_message = json.dumps({
            "type": "next",
            "payload": {
                "data": {
                    "Solana": {
                        "Instructions": [{
                            "Block": {"Time": "2026-01-25T10:00:00Z", "Slot": 123},
                            "Transaction": {"Signature": "sig123", "Signer": "creator123"},
                            "Instruction": {
                                "Accounts": [{"Token": {"Mint": "ValidMint123"}}]
                            }
                        }]
                    }
                }
            }
        })

        await monitor._process_message(valid_message)

        callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_callback_exception(self, config):
        """Test that callback exceptions are handled gracefully."""
        callback = AsyncMock(side_effect=Exception("Callback failed"))
        monitor = GraduationMonitor(config=config, on_graduation=callback)

        payload = {
            "data": {
                "Solana": {
                    "Instructions": [{
                        "Block": {"Time": "2026-01-25T10:00:00Z", "Slot": 123},
                        "Transaction": {"Signature": "sig123", "Signer": "creator123"},
                        "Instruction": {
                            "Accounts": [{"Token": {"Mint": "ExceptionMint"}}]
                        }
                    }]
                }
            }
        }

        # Should not raise
        await monitor._handle_graduation_event(payload)

    @pytest.mark.asyncio
    async def test_handles_missing_nested_keys(self, monitor_with_callback):
        """Test handling of payload with missing nested keys."""
        monitor, callback = monitor_with_callback

        # Payload missing various nested keys
        payloads = [
            {"data": None},
            {"data": {"Solana": None}},
            {"data": {"Solana": {"Instructions": None}}},
            {},
        ]

        for payload in payloads:
            # Should not raise
            await monitor._handle_graduation_event(payload)

        callback.assert_not_called()


# =============================================================================
# Concurrent Access Tests
# =============================================================================

class TestConcurrentAccess:
    """Tests for concurrent access scenarios."""

    @pytest.mark.asyncio
    async def test_processed_mints_concurrent_access(self, config):
        """Test that processed_mints handles concurrent access."""
        callback = AsyncMock()
        monitor = GraduationMonitor(config=config, on_graduation=callback)

        # Create multiple payloads with same mint
        payload = {
            "data": {
                "Solana": {
                    "Instructions": [{
                        "Block": {"Time": "2026-01-25T10:00:00Z", "Slot": 123},
                        "Transaction": {"Signature": "sig123", "Signer": "creator123"},
                        "Instruction": {
                            "Accounts": [{"Token": {"Mint": "ConcurrentMint123"}}]
                        }
                    }]
                }
            }
        }

        # Process same payload concurrently
        await asyncio.gather(
            monitor._handle_graduation_event(payload),
            monitor._handle_graduation_event(payload),
            monitor._handle_graduation_event(payload),
        )

        # Should only be called once due to deduplication
        assert callback.call_count == 1


# =============================================================================
# Configuration Edge Cases
# =============================================================================

class TestConfigurationEdgeCases:
    """Tests for configuration edge cases."""

    def test_monitor_with_empty_string_api_key(self):
        """Test monitor initialization with empty string API key."""
        config = BagsIntelConfig(bitquery_api_key="")
        monitor = GraduationMonitor(config=config)

        assert monitor.config.bitquery_api_key == ""

    def test_monitor_with_custom_ws_url(self):
        """Test monitor with custom WebSocket URL."""
        config = BagsIntelConfig(
            bitquery_api_key="key123",
            bitquery_ws_url="wss://custom.bitquery.io/graphql"
        )
        monitor = GraduationMonitor(config=config)

        assert monitor.config.bitquery_ws_url == "wss://custom.bitquery.io/graphql"

    def test_polling_with_short_interval(self):
        """Test polling fallback with very short interval."""
        config = BagsIntelConfig()
        fallback = PollingFallback(config=config, poll_interval=1)

        assert fallback.poll_interval == 1

    def test_polling_with_long_interval(self):
        """Test polling fallback with long interval."""
        config = BagsIntelConfig()
        fallback = PollingFallback(config=config, poll_interval=3600)

        assert fallback.poll_interval == 3600
