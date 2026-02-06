"""
Conversation Context Tests

Tests for:
- ConversationContext creation and data storage
- TTL expiration
- Serialization/deserialization

Run with: pytest tests/unit/state/test_context.py -v
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, Any


class TestConversationContextCreation:
    """Tests for ConversationContext initialization."""

    def test_create_context_with_ids(self):
        """ConversationContext requires user_id and chat_id."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")

        assert ctx.user_id == "user123"
        assert ctx.chat_id == "chat456"

    def test_context_has_initial_state(self):
        """ConversationContext has initial state."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")

        assert ctx.state is None  # Default is None

    def test_context_with_initial_state(self):
        """ConversationContext can be created with initial state."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(
            user_id="user123", chat_id="chat456", state="awaiting_input"
        )

        assert ctx.state == "awaiting_input"

    def test_context_has_timestamps(self):
        """ConversationContext has created_at and updated_at timestamps."""
        from core.state.context import ConversationContext

        before = datetime.utcnow()
        ctx = ConversationContext(user_id="user123", chat_id="chat456")
        after = datetime.utcnow()

        assert before <= ctx.created_at <= after
        assert before <= ctx.updated_at <= after


class TestConversationContextData:
    """Tests for context data storage."""

    def test_empty_data_dict(self):
        """Context has empty data dict by default."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")

        assert ctx.data == {}

    def test_set_and_get_data(self):
        """Can set and get data values."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")

        ctx.data["token"] = "SOL"
        ctx.data["amount"] = 100

        assert ctx.data["token"] == "SOL"
        assert ctx.data["amount"] == 100

    def test_update_data(self):
        """Can update data values."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")
        ctx.data["step"] = 1

        ctx.data["step"] = 2

        assert ctx.data["step"] == 2

    def test_data_with_complex_types(self):
        """Can store complex data types."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")

        ctx.data["tokens"] = ["SOL", "ETH", "BTC"]
        ctx.data["config"] = {"max_amount": 100, "slippage": 0.5}

        assert ctx.data["tokens"] == ["SOL", "ETH", "BTC"]
        assert ctx.data["config"]["slippage"] == 0.5


class TestConversationContextState:
    """Tests for state management in context."""

    def test_change_state(self):
        """Can change context state."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")
        ctx.state = "awaiting_confirmation"

        assert ctx.state == "awaiting_confirmation"

    def test_state_change_updates_timestamp(self):
        """Changing state updates the updated_at timestamp."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")
        original_updated = ctx.updated_at

        time.sleep(0.01)  # Small delay
        ctx.set_state("new_state")

        assert ctx.updated_at > original_updated


class TestConversationContextTTL:
    """Tests for TTL (time-to-live) functionality."""

    def test_default_ttl(self):
        """Default TTL is set."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")

        assert ctx.ttl_seconds == 3600  # 1 hour default

    def test_custom_ttl(self):
        """Can set custom TTL."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(
            user_id="user123", chat_id="chat456", ttl_seconds=300  # 5 minutes
        )

        assert ctx.ttl_seconds == 300

    def test_is_expired_false_when_fresh(self):
        """Context is not expired when fresh."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(
            user_id="user123", chat_id="chat456", ttl_seconds=3600
        )

        assert ctx.is_expired() is False

    def test_is_expired_true_after_ttl(self):
        """Context is expired after TTL passes."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(
            user_id="user123", chat_id="chat456", ttl_seconds=0  # Immediate expiry
        )

        time.sleep(0.01)
        assert ctx.is_expired() is True

    def test_touch_resets_expiry(self):
        """Touching context resets expiry timer."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(
            user_id="user123", chat_id="chat456", ttl_seconds=1
        )

        time.sleep(0.5)  # Half of TTL
        ctx.touch()
        time.sleep(0.6)  # Would have expired if not touched

        assert ctx.is_expired() is False


class TestConversationContextSerialization:
    """Tests for context serialization/deserialization."""

    def test_to_dict(self):
        """Context can be serialized to dict."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(
            user_id="user123",
            chat_id="chat456",
            state="processing",
            ttl_seconds=600,
        )
        ctx.data["key"] = "value"

        result = ctx.to_dict()

        assert result["user_id"] == "user123"
        assert result["chat_id"] == "chat456"
        assert result["state"] == "processing"
        assert result["data"]["key"] == "value"
        assert result["ttl_seconds"] == 600
        assert "created_at" in result
        assert "updated_at" in result

    def test_from_dict(self):
        """Context can be deserialized from dict."""
        from core.state.context import ConversationContext

        data = {
            "user_id": "user123",
            "chat_id": "chat456",
            "state": "processing",
            "data": {"key": "value"},
            "ttl_seconds": 600,
            "created_at": "2025-01-01T00:00:00",
            "updated_at": "2025-01-01T00:01:00",
        }

        ctx = ConversationContext.from_dict(data)

        assert ctx.user_id == "user123"
        assert ctx.chat_id == "chat456"
        assert ctx.state == "processing"
        assert ctx.data["key"] == "value"
        assert ctx.ttl_seconds == 600

    def test_round_trip_serialization(self):
        """Context survives round-trip serialization."""
        from core.state.context import ConversationContext

        original = ConversationContext(
            user_id="user123",
            chat_id="chat456",
            state="test_state",
            ttl_seconds=1234,
        )
        original.data["tokens"] = ["SOL", "ETH"]

        serialized = original.to_dict()
        restored = ConversationContext.from_dict(serialized)

        assert restored.user_id == original.user_id
        assert restored.chat_id == original.chat_id
        assert restored.state == original.state
        assert restored.data == original.data
        assert restored.ttl_seconds == original.ttl_seconds


class TestConversationContextKey:
    """Tests for context key generation."""

    def test_unique_key(self):
        """Context generates unique key from user_id and chat_id."""
        from core.state.context import ConversationContext

        ctx = ConversationContext(user_id="user123", chat_id="chat456")

        key = ctx.key

        assert "user123" in key
        assert "chat456" in key

    def test_same_ids_same_key(self):
        """Same user_id and chat_id produce same key."""
        from core.state.context import ConversationContext

        ctx1 = ConversationContext(user_id="user123", chat_id="chat456")
        ctx2 = ConversationContext(user_id="user123", chat_id="chat456")

        assert ctx1.key == ctx2.key

    def test_different_ids_different_key(self):
        """Different IDs produce different keys."""
        from core.state.context import ConversationContext

        ctx1 = ConversationContext(user_id="user123", chat_id="chat456")
        ctx2 = ConversationContext(user_id="user999", chat_id="chat456")

        assert ctx1.key != ctx2.key
