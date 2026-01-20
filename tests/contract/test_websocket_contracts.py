"""WebSocket contract tests to ensure frontend/backend compatibility.

These tests validate the message formats and protocols used in WebSocket
communication to ensure frontend and backend remain compatible.
"""
import pytest
import json
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


# =============================================================================
# Contract Definitions
# =============================================================================

class MessageType(str, Enum):
    """Valid WebSocket message types."""
    # Server -> Client
    CONNECTED = "connected"
    PRICE_UPDATE = "price_update"
    SUBSCRIBED = "subscribed"
    UNSUBSCRIBED = "unsubscribed"
    HEARTBEAT = "heartbeat"
    PONG = "pong"
    ERROR = "error"
    BATCH = "batch"

    # Client -> Server
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    PING = "ping"


class ConnectionState(str, Enum):
    """WebSocket connection states (for lifecycle events)."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class MessageContract:
    """Base contract for all WebSocket messages."""
    type: str

    # Optional fields that may be present
    channel: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None
    message: Optional[str] = None


@dataclass
class HeartbeatContract:
    """Contract for heartbeat messages."""
    type: str  # Must be "heartbeat"
    timestamp: float  # Unix timestamp
    server_time: int  # Unix timestamp in milliseconds


@dataclass
class PriceUpdateContract:
    """Contract for price update messages."""
    type: str  # Must be "price_update"
    data: Dict[str, Any]  # Contains token, price, etc.


@dataclass
class ErrorContract:
    """Contract for error messages."""
    type: str  # Must be "error"
    message: str  # Human-readable error message
    code: Optional[str] = None  # Machine-readable error code


@dataclass
class SubscriptionContract:
    """Contract for subscription request messages."""
    type: str  # Must be "subscribe" or "unsubscribe"
    tokens: List[str]  # List of token addresses


@dataclass
class SubscriptionResponseContract:
    """Contract for subscription response messages."""
    type: str  # "subscribed" or "unsubscribed"
    tokens: List[str]  # Current list of subscribed tokens


# =============================================================================
# Contract Validators
# =============================================================================

class ContractValidator:
    """Validates messages against their contracts."""

    @staticmethod
    def validate_base_message(msg: Dict[str, Any], allow_string_timestamp: bool = False) -> List[str]:
        """Validate basic message structure. Returns list of errors.

        Args:
            msg: The message to validate
            allow_string_timestamp: If True, allows ISO format string timestamps
        """
        errors = []

        if not isinstance(msg, dict):
            errors.append("Message must be a dictionary")
            return errors

        if "type" not in msg:
            errors.append("Missing required field: type")
        elif not isinstance(msg["type"], str):
            errors.append("Field 'type' must be a string")

        # Validate optional fields if present
        if "channel" in msg and not isinstance(msg["channel"], str):
            errors.append("Field 'channel' must be a string if present")

        if "timestamp" in msg:
            if allow_string_timestamp:
                if not isinstance(msg["timestamp"], (int, float, str)):
                    errors.append("Field 'timestamp' must be a number or ISO string if present")
            else:
                if not isinstance(msg["timestamp"], (int, float)):
                    errors.append("Field 'timestamp' must be a number if present")

        return errors

    @staticmethod
    def validate_heartbeat(msg: Dict[str, Any]) -> List[str]:
        """Validate heartbeat message."""
        errors = ContractValidator.validate_base_message(msg)

        if msg.get("type") != "heartbeat":
            errors.append("Heartbeat message type must be 'heartbeat'")

        if "timestamp" not in msg:
            errors.append("Heartbeat missing required field: timestamp")
        elif not isinstance(msg["timestamp"], (int, float)):
            errors.append("Heartbeat timestamp must be a number")

        if "server_time" not in msg:
            errors.append("Heartbeat missing required field: server_time")
        elif not isinstance(msg["server_time"], int):
            errors.append("Heartbeat server_time must be an integer (milliseconds)")

        return errors

    @staticmethod
    def validate_price_update(msg: Dict[str, Any]) -> List[str]:
        """Validate price update message."""
        errors = ContractValidator.validate_base_message(msg)

        if msg.get("type") != "price_update":
            errors.append("Price update message type must be 'price_update'")

        if "data" not in msg:
            errors.append("Price update missing required field: data")
        elif not isinstance(msg["data"], dict):
            errors.append("Price update data must be a dictionary")
        else:
            data = msg["data"]
            required_data_fields = ["token", "price"]
            for field in required_data_fields:
                if field not in data:
                    errors.append(f"Price update data missing field: {field}")

            if "price" in data and not isinstance(data["price"], (int, float)):
                errors.append("Price must be a number")

            if "token" in data and not isinstance(data["token"], str):
                errors.append("Token must be a string")

        return errors

    @staticmethod
    def validate_error(msg: Dict[str, Any]) -> List[str]:
        """Validate error message."""
        errors = ContractValidator.validate_base_message(msg)

        if msg.get("type") != "error":
            errors.append("Error message type must be 'error'")

        if "message" not in msg:
            errors.append("Error missing required field: message")
        elif not isinstance(msg["message"], str):
            errors.append("Error message must be a string")

        if "code" in msg and not isinstance(msg["code"], str):
            errors.append("Error code must be a string if present")

        return errors

    @staticmethod
    def validate_subscription_request(msg: Dict[str, Any]) -> List[str]:
        """Validate subscription request message."""
        errors = ContractValidator.validate_base_message(msg)

        if msg.get("type") not in ["subscribe", "unsubscribe"]:
            errors.append("Subscription request type must be 'subscribe' or 'unsubscribe'")

        if "tokens" not in msg:
            errors.append("Subscription request missing required field: tokens")
        elif not isinstance(msg["tokens"], list):
            # Also accept single string
            if not isinstance(msg["tokens"], str):
                errors.append("Subscription tokens must be a list or string")
        else:
            for token in msg["tokens"]:
                if not isinstance(token, str):
                    errors.append("Each token in tokens list must be a string")
                    break

        return errors

    @staticmethod
    def validate_subscription_response(msg: Dict[str, Any]) -> List[str]:
        """Validate subscription response message."""
        errors = ContractValidator.validate_base_message(msg)

        if msg.get("type") not in ["subscribed", "unsubscribed"]:
            errors.append("Subscription response type must be 'subscribed' or 'unsubscribed'")

        if "tokens" not in msg:
            errors.append("Subscription response missing required field: tokens")
        elif not isinstance(msg["tokens"], list):
            errors.append("Subscription response tokens must be a list")

        return errors

    @staticmethod
    def validate_connected(msg: Dict[str, Any]) -> List[str]:
        """Validate connection established message.

        Note: Connected messages use ISO format string timestamps, not numeric.
        """
        errors = ContractValidator.validate_base_message(msg, allow_string_timestamp=True)

        if msg.get("type") != "connected":
            errors.append("Connected message type must be 'connected'")

        # timestamp is optional but if present should be ISO format string
        if "timestamp" in msg:
            if not isinstance(msg["timestamp"], str):
                errors.append("Connected timestamp should be ISO format string")

        return errors

    @staticmethod
    def validate_batch(msg: Dict[str, Any]) -> List[str]:
        """Validate batch message.

        Note: Batch messages have a different structure - they don't have a 'type' field,
        just a 'batch' array containing the messages.
        """
        errors = []

        if not isinstance(msg, dict):
            errors.append("Message must be a dictionary")
            return errors

        if "batch" not in msg:
            errors.append("Batch message missing required field: batch")
        elif not isinstance(msg["batch"], list):
            errors.append("Batch field must be a list")
        else:
            for i, item in enumerate(msg["batch"]):
                if not isinstance(item, dict):
                    errors.append(f"Batch item {i} must be a dictionary")

        return errors


# =============================================================================
# Test Classes
# =============================================================================

class TestMessageFormatContract:
    """Contract tests for WebSocket message formats."""

    def test_all_message_types_are_strings(self):
        """All message types must be string values."""
        for msg_type in MessageType:
            assert isinstance(msg_type.value, str)

    def test_base_message_requires_type(self):
        """Base message must have a type field."""
        validator = ContractValidator()

        # Missing type
        errors = validator.validate_base_message({})
        assert "Missing required field: type" in errors

        # Valid with just type
        errors = validator.validate_base_message({"type": "test"})
        assert len(errors) == 0

    def test_base_message_type_must_be_string(self):
        """Message type must be a string."""
        validator = ContractValidator()

        errors = validator.validate_base_message({"type": 123})
        assert "Field 'type' must be a string" in errors

    def test_channel_field_format(self):
        """Channel field must be string if present."""
        validator = ContractValidator()

        # Valid channel
        errors = validator.validate_base_message({
            "type": "update",
            "channel": "trading"
        })
        assert len(errors) == 0

        # Invalid channel type
        errors = validator.validate_base_message({
            "type": "update",
            "channel": 123
        })
        assert "Field 'channel' must be a string if present" in errors

    def test_timestamp_field_format(self):
        """Timestamp field must be numeric if present."""
        validator = ContractValidator()

        # Valid timestamp (float)
        errors = validator.validate_base_message({
            "type": "update",
            "timestamp": 1234567890.123
        })
        assert len(errors) == 0

        # Valid timestamp (int)
        errors = validator.validate_base_message({
            "type": "update",
            "timestamp": 1234567890
        })
        assert len(errors) == 0

        # Invalid timestamp type
        errors = validator.validate_base_message({
            "type": "update",
            "timestamp": "not-a-number"
        })
        assert "Field 'timestamp' must be a number if present" in errors

    def test_timestamp_string_allowed_when_specified(self):
        """String timestamp allowed when allow_string_timestamp is True."""
        validator = ContractValidator()

        # ISO timestamp should fail without flag
        errors = validator.validate_base_message({
            "type": "update",
            "timestamp": "2024-01-15T12:00:00Z"
        })
        assert "Field 'timestamp' must be a number if present" in errors

        # ISO timestamp should pass with flag
        errors = validator.validate_base_message({
            "type": "update",
            "timestamp": "2024-01-15T12:00:00Z"
        }, allow_string_timestamp=True)
        assert len(errors) == 0

    def test_standard_message_structure(self):
        """Test complete standard message structure."""
        valid_message = {
            "type": "update",
            "channel": "trading",
            "data": {"price": 100.5},
            "timestamp": 1234567890.123
        }

        errors = ContractValidator.validate_base_message(valid_message)
        assert len(errors) == 0


class TestHeartbeatContract:
    """Contract tests for heartbeat messages."""

    def test_heartbeat_from_optimizer(self):
        """Heartbeat from WebSocketOptimizer must follow contract."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer()
        heartbeat = optimizer.get_heartbeat_message()

        errors = ContractValidator.validate_heartbeat(heartbeat)
        assert len(errors) == 0, f"Heartbeat validation errors: {errors}"

    def test_heartbeat_requires_type(self):
        """Heartbeat must have type 'heartbeat'."""
        errors = ContractValidator.validate_heartbeat({
            "timestamp": time.time(),
            "server_time": int(time.time() * 1000)
        })
        assert "Missing required field: type" in errors

    def test_heartbeat_type_value(self):
        """Heartbeat type must be 'heartbeat'."""
        errors = ContractValidator.validate_heartbeat({
            "type": "ping",  # Wrong type
            "timestamp": time.time(),
            "server_time": int(time.time() * 1000)
        })
        assert "Heartbeat message type must be 'heartbeat'" in errors

    def test_heartbeat_requires_timestamp(self):
        """Heartbeat must have timestamp."""
        errors = ContractValidator.validate_heartbeat({
            "type": "heartbeat",
            "server_time": int(time.time() * 1000)
        })
        assert "Heartbeat missing required field: timestamp" in errors

    def test_heartbeat_requires_server_time(self):
        """Heartbeat must have server_time in milliseconds."""
        errors = ContractValidator.validate_heartbeat({
            "type": "heartbeat",
            "timestamp": time.time()
        })
        assert "Heartbeat missing required field: server_time" in errors

    def test_heartbeat_server_time_is_milliseconds(self):
        """Heartbeat server_time must be integer milliseconds."""
        errors = ContractValidator.validate_heartbeat({
            "type": "heartbeat",
            "timestamp": time.time(),
            "server_time": time.time()  # Seconds, not milliseconds (float)
        })
        assert "Heartbeat server_time must be an integer (milliseconds)" in errors

    def test_valid_heartbeat(self):
        """Valid heartbeat message passes validation."""
        heartbeat = {
            "type": "heartbeat",
            "timestamp": time.time(),
            "server_time": int(time.time() * 1000)
        }

        errors = ContractValidator.validate_heartbeat(heartbeat)
        assert len(errors) == 0


class TestSubscriptionProtocolContract:
    """Contract tests for subscription/unsubscription protocols."""

    def test_subscribe_request_format(self):
        """Subscribe request must follow contract."""
        valid_request = {
            "type": "subscribe",
            "tokens": ["SOL123", "ETH456"]
        }

        errors = ContractValidator.validate_subscription_request(valid_request)
        assert len(errors) == 0

    def test_subscribe_single_token_string_allowed(self):
        """Subscribe can accept single token as string."""
        # The server handles both list and string
        request = {
            "type": "subscribe",
            "tokens": "SOL123"  # Single string, not list
        }

        errors = ContractValidator.validate_subscription_request(request)
        assert len(errors) == 0

    def test_subscribe_requires_tokens(self):
        """Subscribe request must have tokens field."""
        request = {
            "type": "subscribe"
        }

        errors = ContractValidator.validate_subscription_request(request)
        assert "Subscription request missing required field: tokens" in errors

    def test_unsubscribe_request_format(self):
        """Unsubscribe request must follow contract."""
        valid_request = {
            "type": "unsubscribe",
            "tokens": ["SOL123"]
        }

        errors = ContractValidator.validate_subscription_request(valid_request)
        assert len(errors) == 0

    def test_subscription_response_subscribed(self):
        """Subscribed response must follow contract."""
        response = {
            "type": "subscribed",
            "tokens": ["SOL123", "ETH456"]
        }

        errors = ContractValidator.validate_subscription_response(response)
        assert len(errors) == 0

    def test_subscription_response_unsubscribed(self):
        """Unsubscribed response must follow contract."""
        response = {
            "type": "unsubscribed",
            "tokens": ["SOL123"]
        }

        errors = ContractValidator.validate_subscription_response(response)
        assert len(errors) == 0

    def test_subscription_response_requires_tokens_list(self):
        """Subscription response tokens must be a list."""
        response = {
            "type": "subscribed",
            "tokens": "SOL123"  # Should be list
        }

        errors = ContractValidator.validate_subscription_response(response)
        assert "Subscription response tokens must be a list" in errors


class TestErrorMessageContract:
    """Contract tests for error message formats."""

    def test_error_message_format(self):
        """Error message must follow contract."""
        error = {
            "type": "error",
            "message": "Invalid JSON"
        }

        errors = ContractValidator.validate_error(error)
        assert len(errors) == 0

    def test_error_requires_message(self):
        """Error must have message field."""
        error = {
            "type": "error"
        }

        errors = ContractValidator.validate_error(error)
        assert "Error missing required field: message" in errors

    def test_error_with_code(self):
        """Error can optionally include code."""
        error = {
            "type": "error",
            "message": "Rate limit exceeded",
            "code": "RATE_LIMIT"
        }

        errors = ContractValidator.validate_error(error)
        assert len(errors) == 0

    def test_error_code_must_be_string(self):
        """Error code must be string if present."""
        error = {
            "type": "error",
            "message": "Error",
            "code": 123
        }

        errors = ContractValidator.validate_error(error)
        assert "Error code must be a string if present" in errors

    def test_invalid_json_error_format(self):
        """Invalid JSON error follows expected format."""
        # This is what the server sends for invalid JSON
        error = {
            "type": "error",
            "message": "Invalid JSON"
        }

        errors = ContractValidator.validate_error(error)
        assert len(errors) == 0

    def test_unknown_message_type_error_format(self):
        """Unknown message type error follows expected format."""
        # This is what the server sends for unknown message types
        error = {
            "type": "error",
            "message": "Unknown message type: foobar"
        }

        errors = ContractValidator.validate_error(error)
        assert len(errors) == 0


class TestConnectionLifecycleContract:
    """Contract tests for connection lifecycle events."""

    def test_connected_message_format(self):
        """Connected message must follow contract."""
        connected = {
            "type": "connected",
            "message": "Connected to Jarvis Price Stream",
            "timestamp": "2024-01-15T12:00:00+00:00"
        }

        errors = ContractValidator.validate_connected(connected)
        assert len(errors) == 0, f"Connected validation errors: {errors}"

    def test_connected_minimal(self):
        """Connected message can be minimal."""
        connected = {
            "type": "connected"
        }

        errors = ContractValidator.validate_connected(connected)
        assert len(errors) == 0

    def test_connected_timestamp_must_be_iso_string(self):
        """Connected timestamp should be ISO format string, not number."""
        # Numeric timestamp should fail for connected messages
        connected = {
            "type": "connected",
            "timestamp": 1234567890.123  # Wrong - should be string
        }

        errors = ContractValidator.validate_connected(connected)
        assert "Connected timestamp should be ISO format string" in errors

    def test_ping_pong_contract(self):
        """Ping message should receive pong response."""
        ping = {"type": "ping"}
        expected_pong = {"type": "pong"}

        # Validate ping
        errors = ContractValidator.validate_base_message(ping)
        assert len(errors) == 0
        assert ping["type"] == "ping"

        # Validate expected pong response
        errors = ContractValidator.validate_base_message(expected_pong)
        assert len(errors) == 0
        assert expected_pong["type"] == "pong"

    def test_connection_states_are_valid(self):
        """All connection states are valid strings."""
        for state in ConnectionState:
            assert isinstance(state.value, str)
            assert len(state.value) > 0


class TestPriceUpdateContract:
    """Contract tests for price update messages."""

    def test_price_update_format(self):
        """Price update must follow contract."""
        update = {
            "type": "price_update",
            "data": {
                "token": "SOL123abc",
                "price": 100.50,
                "priceChange1h": 2.5,
                "priceChange24h": -1.2,
                "volume24h": 1000000,
                "liquidity": 500000,
                "timestamp": "2024-01-15T12:00:00Z"
            }
        }

        errors = ContractValidator.validate_price_update(update)
        assert len(errors) == 0

    def test_price_update_requires_data(self):
        """Price update must have data field."""
        update = {
            "type": "price_update"
        }

        errors = ContractValidator.validate_price_update(update)
        assert "Price update missing required field: data" in errors

    def test_price_update_data_requires_token(self):
        """Price update data must have token field."""
        update = {
            "type": "price_update",
            "data": {
                "price": 100.50
            }
        }

        errors = ContractValidator.validate_price_update(update)
        assert "Price update data missing field: token" in errors

    def test_price_update_data_requires_price(self):
        """Price update data must have price field."""
        update = {
            "type": "price_update",
            "data": {
                "token": "SOL123"
            }
        }

        errors = ContractValidator.validate_price_update(update)
        assert "Price update data missing field: price" in errors

    def test_price_update_price_must_be_number(self):
        """Price in price update must be numeric."""
        update = {
            "type": "price_update",
            "data": {
                "token": "SOL123",
                "price": "100.50"  # String, not number
            }
        }

        errors = ContractValidator.validate_price_update(update)
        assert "Price must be a number" in errors

    def test_price_update_from_dataclass(self):
        """PriceUpdate dataclass produces valid message."""
        from core.websocket_server import PriceUpdate

        price_update = PriceUpdate(
            token_address="SOL123abc",
            price=100.50,
            price_change_1h=2.5,
            price_change_24h=-1.2,
            volume_24h=1000000,
            liquidity=500000,
            timestamp="2024-01-15T12:00:00Z"
        )

        message = price_update.to_dict()

        # Should have correct structure
        assert message["type"] == "price_update"
        assert "data" in message
        assert message["data"]["token"] == "SOL123abc"
        assert message["data"]["price"] == 100.50

        # Validate against contract
        errors = ContractValidator.validate_price_update(message)
        assert len(errors) == 0


class TestBatchMessageContract:
    """Contract tests for batch message format.

    Note: Batch messages have a unique structure - they only contain a 'batch' array
    and do NOT have a 'type' field like other messages.
    """

    def test_batch_message_format(self):
        """Batch message must follow contract (no type field needed)."""
        batch = {
            "batch": [
                {"type": "price_update", "data": {"token": "A", "price": 1}},
                {"type": "price_update", "data": {"token": "B", "price": 2}}
            ]
        }

        errors = ContractValidator.validate_batch(batch)
        assert len(errors) == 0, f"Batch validation errors: {errors}"

    def test_batch_requires_batch_field(self):
        """Batch message must have batch field."""
        batch = {
            "messages": []  # Wrong field name
        }

        errors = ContractValidator.validate_batch(batch)
        assert "Batch message missing required field: batch" in errors

    def test_batch_field_must_be_list(self):
        """Batch field must be a list."""
        batch = {
            "batch": {"message": "not a list"}
        }

        errors = ContractValidator.validate_batch(batch)
        assert "Batch field must be a list" in errors

    def test_batch_items_must_be_dicts(self):
        """Each batch item must be a dictionary."""
        batch = {
            "batch": [
                {"type": "update"},
                "not a dict"
            ]
        }

        errors = ContractValidator.validate_batch(batch)
        assert "Batch item 1 must be a dictionary" in errors

    def test_batch_from_optimizer(self):
        """Batch from MessageBatch follows contract."""
        from core.performance.websocket_optimizer import MessageBatch

        batch = MessageBatch()
        batch.add({"type": "price_update", "data": {"token": "A", "price": 1}})
        batch.add({"type": "price_update", "data": {"token": "B", "price": 2}})

        payload = batch.get_payload()
        message = json.loads(payload.decode())

        errors = ContractValidator.validate_batch(message)
        assert len(errors) == 0, f"MessageBatch validation errors: {errors}"

    def test_batch_can_be_empty(self):
        """Empty batch is valid."""
        batch = {"batch": []}

        errors = ContractValidator.validate_batch(batch)
        assert len(errors) == 0


class TestOptimizerContract:
    """Contract tests for WebSocketOptimizer behavior."""

    def test_optimizer_heartbeat_interval(self):
        """Optimizer heartbeat follows configured interval."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer(heartbeat_interval=1.0)

        # First call should need heartbeat
        assert optimizer.needs_heartbeat("client1") is True

        # Immediate second call should not
        assert optimizer.needs_heartbeat("client1") is False

    def test_optimizer_subscription_tracking(self):
        """Optimizer tracks subscriptions correctly."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer()

        # Subscribe
        optimizer.subscribe("client1", "channel1")
        assert "client1" in optimizer.get_subscribers("channel1")

        # Unsubscribe
        optimizer.unsubscribe("client1", "channel1")
        assert "client1" not in optimizer.get_subscribers("channel1")

    def test_optimizer_unsubscribe_all(self):
        """Optimizer can unsubscribe client from all channels."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer()

        # Subscribe to multiple channels
        optimizer.subscribe("client1", "channel1")
        optimizer.subscribe("client1", "channel2")
        optimizer.subscribe("client1", "channel3")

        # Unsubscribe all
        optimizer.unsubscribe_all("client1")

        # Should be removed from all channels
        assert "client1" not in optimizer.get_subscribers("channel1")
        assert "client1" not in optimizer.get_subscribers("channel2")
        assert "client1" not in optimizer.get_subscribers("channel3")

    def test_optimizer_stats_contract(self):
        """Optimizer stats follow expected structure."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer()
        stats = optimizer.get_stats()

        # Required fields
        assert "active_channels" in stats
        assert "total_subscribers" in stats
        assert "pending_batches" in stats
        assert "dedup_cache_size" in stats

        # All must be integers
        assert isinstance(stats["active_channels"], int)
        assert isinstance(stats["total_subscribers"], int)
        assert isinstance(stats["pending_batches"], int)
        assert isinstance(stats["dedup_cache_size"], int)

    def test_optimizer_dedup_contract(self):
        """Optimizer deduplication follows expected behavior."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer()

        # First message should not be duplicate
        assert optimizer.is_duplicate("msg1") is False

        # Same message ID should be duplicate
        assert optimizer.is_duplicate("msg1") is True

        # Different message ID should not be duplicate
        assert optimizer.is_duplicate("msg2") is False

    def test_optimizer_compression_threshold(self):
        """Optimizer compression follows threshold."""
        from core.performance.websocket_optimizer import WebSocketOptimizer

        optimizer = WebSocketOptimizer(compression_threshold=100)

        # Small data should not compress
        small_data = b"x" * 50
        assert optimizer.should_compress(small_data) is False

        # Large data should compress
        large_data = b"x" * 200
        assert optimizer.should_compress(large_data) is True


class TestConnectionManagerContract:
    """Contract tests for WebSocketConnection and ConnectionConfig."""

    def test_connection_state_values(self):
        """Connection states are valid enum values."""
        from core.websocket_manager import ConnectionState as WsConnectionState

        expected_states = ["disconnected", "connecting", "connected", "reconnecting", "failed"]
        actual_states = [s.value for s in WsConnectionState]

        for expected in expected_states:
            assert expected in actual_states

    def test_connection_config_defaults(self):
        """ConnectionConfig has sensible defaults."""
        from core.websocket_manager import ConnectionConfig

        config = ConnectionConfig(
            name="test",
            url="wss://example.com"
        )

        # Check defaults
        assert config.auto_reconnect is True
        assert config.max_reconnect_attempts == 10
        assert config.reconnect_delay == 1.0
        assert config.max_reconnect_delay == 60.0
        assert config.ping_interval == 30.0
        assert config.ping_timeout == 10.0
        assert isinstance(config.headers, dict)
        assert isinstance(config.subscriptions, list)

    def test_connection_stats_contract(self):
        """ConnectionStats has expected fields."""
        from core.websocket_manager import ConnectionStats, ConnectionState as WsConnectionState

        stats = ConnectionStats(
            name="test",
            state=WsConnectionState.CONNECTED
        )

        # Required fields
        assert stats.name == "test"
        assert stats.state == WsConnectionState.CONNECTED

        # Optional fields with defaults
        assert stats.connected_at is None
        assert stats.disconnected_at is None
        assert stats.reconnect_count == 0
        assert stats.messages_received == 0
        assert stats.messages_sent == 0
        assert stats.last_message_at is None
        assert stats.last_error is None
        assert stats.uptime_seconds == 0.0


class TestJSONSerializationContract:
    """Contract tests for JSON serialization compatibility."""

    def test_all_messages_are_json_serializable(self):
        """All message types must be JSON serializable."""
        messages = [
            {"type": "heartbeat", "timestamp": time.time(), "server_time": int(time.time() * 1000)},
            {"type": "connected", "message": "Welcome", "timestamp": "2024-01-15T12:00:00Z"},
            {"type": "price_update", "data": {"token": "SOL", "price": 100.5}},
            {"type": "subscribed", "tokens": ["SOL", "ETH"]},
            {"type": "unsubscribed", "tokens": []},
            {"type": "error", "message": "Test error", "code": "ERR001"},
            {"type": "pong"},
            {"batch": [{"type": "update"}, {"type": "update"}]}
        ]

        for msg in messages:
            # Should not raise
            serialized = json.dumps(msg)
            assert isinstance(serialized, str)

            # Should round-trip
            deserialized = json.loads(serialized)
            assert deserialized == msg

    def test_unicode_in_messages(self):
        """Messages with unicode characters must serialize correctly."""
        msg = {
            "type": "error",
            "message": "Unicode test: \u00e9\u00e8\u00ea \u4e2d\u6587 \U0001f600"
        }

        serialized = json.dumps(msg)
        deserialized = json.loads(serialized)

        assert deserialized["message"] == msg["message"]

    def test_large_numbers(self):
        """Large numbers in prices must serialize correctly."""
        msg = {
            "type": "price_update",
            "data": {
                "token": "TEST",
                "price": 0.00000001,  # Very small
                "volume24h": 1000000000000  # Very large
            }
        }

        serialized = json.dumps(msg)
        deserialized = json.loads(serialized)

        assert deserialized["data"]["price"] == 0.00000001
        assert deserialized["data"]["volume24h"] == 1000000000000

    def test_special_float_values(self):
        """Special float values should be handled."""
        # Note: JSON doesn't support Infinity or NaN natively
        # This test documents expected behavior

        # Regular floats should work
        msg = {
            "type": "price_update",
            "data": {
                "token": "TEST",
                "price": 0.0,
                "change": -0.0
            }
        }

        serialized = json.dumps(msg)
        deserialized = json.loads(serialized)
        assert deserialized["data"]["price"] == 0.0


class TestBackwardsCompatibilityContract:
    """Tests to ensure backwards compatibility with existing clients."""

    def test_old_subscribe_format_still_works(self):
        """Old subscribe format with single token string should work."""
        # Old format: {"type": "subscribe", "tokens": "SOL123"}
        old_format = {"type": "subscribe", "tokens": "SOL123"}

        # Should be valid
        errors = ContractValidator.validate_subscription_request(old_format)
        assert len(errors) == 0

    def test_price_update_camelcase_fields(self):
        """Price update uses camelCase for frontend compatibility."""
        from core.websocket_server import PriceUpdate

        update = PriceUpdate(
            token_address="SOL123",
            price=100.0,
            price_change_1h=1.0,
            price_change_24h=2.0,
            volume_24h=1000,
            liquidity=500,
            timestamp="2024-01-15T12:00:00Z"
        )

        data = update.to_dict()["data"]

        # Should use camelCase
        assert "priceChange1h" in data
        assert "priceChange24h" in data
        assert "volume24h" in data

        # Not snake_case
        assert "price_change_1h" not in data
        assert "price_change_24h" not in data
        assert "volume_24h" not in data

    def test_minimal_messages_accepted(self):
        """Minimal valid messages should be accepted."""
        # Minimal ping
        errors = ContractValidator.validate_base_message({"type": "ping"})
        assert len(errors) == 0

        # Minimal pong
        errors = ContractValidator.validate_base_message({"type": "pong"})
        assert len(errors) == 0

        # Minimal error
        errors = ContractValidator.validate_error({"type": "error", "message": "err"})
        assert len(errors) == 0

        # Minimal connected
        errors = ContractValidator.validate_connected({"type": "connected"})
        assert len(errors) == 0
