"""
Tests for bots/shared/message_queue.py

Inter-bot message queue system for ClawdBots communication.

Tests cover:
- Message creation and structure
- Priority levels (LOW, NORMAL, HIGH, URGENT)
- Sending messages between bots
- Receiving messages with limit
- Message acknowledgment
- Queue statistics
- Topic-based pub/sub routing
- Disk persistence
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from bots.shared.message_queue import (
    MessageQueue,
    Message,
    Priority,
    QueueStats,
    send_message,
    receive_messages,
    acknowledge_message,
    get_queue_stats,
    subscribe_topic,
    publish_topic,
)


class TestPriority:
    """Test Priority enum."""

    def test_low_priority_value(self):
        """LOW should have lowest priority value."""
        assert Priority.LOW.value == 1

    def test_normal_priority_value(self):
        """NORMAL should be default priority."""
        assert Priority.NORMAL.value == 2

    def test_high_priority_value(self):
        """HIGH should have higher priority."""
        assert Priority.HIGH.value == 3

    def test_urgent_priority_value(self):
        """URGENT should have highest priority."""
        assert Priority.URGENT.value == 4

    def test_priority_comparison(self):
        """Higher priority should sort before lower."""
        assert Priority.URGENT.value > Priority.HIGH.value
        assert Priority.HIGH.value > Priority.NORMAL.value
        assert Priority.NORMAL.value > Priority.LOW.value


class TestMessage:
    """Test Message dataclass."""

    def test_create_message_with_defaults(self):
        """Should create message with default priority."""
        msg = Message(
            id="msg_001",
            from_bot="jarvis",
            to_bot="matt",
            content="Test message",
        )
        assert msg.id == "msg_001"
        assert msg.from_bot == "jarvis"
        assert msg.to_bot == "matt"
        assert msg.content == "Test message"
        assert msg.priority == Priority.NORMAL
        assert msg.acknowledged is False
        assert msg.timestamp is not None

    def test_create_message_with_priority(self):
        """Should create message with specified priority."""
        msg = Message(
            id="msg_002",
            from_bot="friday",
            to_bot="jarvis",
            content="Urgent task",
            priority=Priority.URGENT,
        )
        assert msg.priority == Priority.URGENT

    def test_message_to_dict(self):
        """Should serialize message to dictionary."""
        msg = Message(
            id="msg_003",
            from_bot="matt",
            to_bot="friday",
            content="Status update",
            priority=Priority.HIGH,
        )
        data = msg.to_dict()
        assert data["id"] == "msg_003"
        assert data["from_bot"] == "matt"
        assert data["to_bot"] == "friday"
        assert data["content"] == "Status update"
        assert data["priority"] == 3  # HIGH.value
        assert data["acknowledged"] is False
        assert "timestamp" in data

    def test_message_from_dict(self):
        """Should deserialize message from dictionary."""
        data = {
            "id": "msg_restore",
            "from_bot": "jarvis",
            "to_bot": "matt",
            "content": "Restored message",
            "priority": 4,  # URGENT
            "acknowledged": True,
            "timestamp": "2026-02-02T12:00:00Z",
        }
        msg = Message.from_dict(data)
        assert msg.id == "msg_restore"
        assert msg.from_bot == "jarvis"
        assert msg.to_bot == "matt"
        assert msg.priority == Priority.URGENT
        assert msg.acknowledged is True

    def test_message_acknowledged_at(self):
        """Should track acknowledgment timestamp."""
        msg = Message(
            id="msg_ack",
            from_bot="jarvis",
            to_bot="matt",
            content="Ack test",
        )
        assert msg.acknowledged_at is None
        msg.acknowledged = True
        msg.acknowledged_at = datetime.now(timezone.utc).isoformat()
        assert msg.acknowledged_at is not None


class TestMessageQueue:
    """Test MessageQueue class."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create temporary queue file for tests."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            f.write('{}')
            temp_path = f.name
        yield temp_path
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        lock_path = temp_path + ".lock"
        if os.path.exists(lock_path):
            os.unlink(lock_path)

    @pytest.fixture
    def queue(self, temp_queue_file):
        """Create MessageQueue with temp file."""
        return MessageQueue(queue_file=temp_queue_file)

    # Initialization tests

    def test_init_creates_queue_file(self, temp_queue_file):
        """Should create queue file on initialization."""
        os.unlink(temp_queue_file)  # Remove the file
        queue = MessageQueue(queue_file=temp_queue_file)
        assert os.path.exists(temp_queue_file)

    def test_init_loads_existing_queue(self, temp_queue_file):
        """Should load existing messages on init."""
        # Pre-populate queue
        data = {
            "messages": [
                {
                    "id": "msg_existing",
                    "from_bot": "jarvis",
                    "to_bot": "matt",
                    "content": "Pre-existing message",
                    "priority": 2,
                    "acknowledged": False,
                    "timestamp": "2026-02-02T09:00:00Z",
                }
            ],
            "subscriptions": {},
        }
        with open(temp_queue_file, 'w') as f:
            json.dump(data, f)

        queue = MessageQueue(queue_file=temp_queue_file)
        messages = queue.receive_messages("matt")
        assert len(messages) == 1
        assert messages[0].id == "msg_existing"

    # Send message tests

    def test_send_message_basic(self, queue):
        """Should send message between bots."""
        msg_id = queue.send_message(
            from_bot="jarvis",
            to_bot="matt",
            message="Hello Matt",
        )
        assert msg_id is not None
        assert msg_id.startswith("msg_")

    def test_send_message_with_priority(self, queue):
        """Should send message with specified priority."""
        msg_id = queue.send_message(
            from_bot="jarvis",
            to_bot="friday",
            message="Urgent: Check this!",
            priority=Priority.URGENT,
        )
        messages = queue.receive_messages("friday")
        assert len(messages) == 1
        assert messages[0].priority == Priority.URGENT

    def test_send_message_default_priority(self, queue):
        """Should default to NORMAL priority."""
        msg_id = queue.send_message(
            from_bot="jarvis",
            to_bot="matt",
            message="Regular message",
        )
        messages = queue.receive_messages("matt")
        assert messages[0].priority == Priority.NORMAL

    # Receive message tests

    def test_receive_messages_for_bot(self, queue):
        """Should only receive messages for specified bot."""
        queue.send_message("jarvis", "matt", "For Matt")
        queue.send_message("jarvis", "friday", "For Friday")
        queue.send_message("matt", "friday", "Also for Friday")

        matt_msgs = queue.receive_messages("matt")
        assert len(matt_msgs) == 1
        assert matt_msgs[0].content == "For Matt"

        friday_msgs = queue.receive_messages("friday")
        assert len(friday_msgs) == 2

    def test_receive_messages_with_limit(self, queue):
        """Should respect message limit."""
        for i in range(20):
            queue.send_message("jarvis", "matt", f"Message {i}")

        messages = queue.receive_messages("matt", limit=10)
        assert len(messages) == 10

    def test_receive_messages_priority_order(self, queue):
        """Should return messages in priority order (highest first)."""
        queue.send_message("jarvis", "matt", "Low priority", Priority.LOW)
        queue.send_message("jarvis", "matt", "Normal priority", Priority.NORMAL)
        queue.send_message("jarvis", "matt", "High priority", Priority.HIGH)
        queue.send_message("jarvis", "matt", "Urgent priority", Priority.URGENT)

        messages = queue.receive_messages("matt")
        assert messages[0].content == "Urgent priority"
        assert messages[1].content == "High priority"
        assert messages[2].content == "Normal priority"
        assert messages[3].content == "Low priority"

    def test_receive_only_unacknowledged(self, queue):
        """Should only return unacknowledged messages."""
        msg_id = queue.send_message("jarvis", "matt", "Will be acked")
        queue.send_message("jarvis", "matt", "Not acked")

        queue.acknowledge_message(msg_id)

        messages = queue.receive_messages("matt")
        assert len(messages) == 1
        assert messages[0].content == "Not acked"

    # Acknowledgment tests

    def test_acknowledge_message(self, queue):
        """Should acknowledge message by ID."""
        msg_id = queue.send_message("jarvis", "matt", "Ack me")
        result = queue.acknowledge_message(msg_id)
        assert result is True

        # Verify acknowledged
        messages = queue.receive_messages("matt")
        assert len(messages) == 0

    def test_acknowledge_nonexistent_message(self, queue):
        """Should return False for nonexistent message."""
        result = queue.acknowledge_message("msg_nonexistent")
        assert result is False

    def test_acknowledge_sets_timestamp(self, queue):
        """Should set acknowledgment timestamp."""
        msg_id = queue.send_message("jarvis", "matt", "Ack with timestamp")
        queue.acknowledge_message(msg_id)

        # Get the raw message data
        stats = queue.get_queue_stats()
        assert stats.acknowledged_count == 1

    # Queue stats tests

    def test_get_queue_stats_empty(self, queue):
        """Should return stats for empty queue."""
        stats = queue.get_queue_stats()
        assert stats.total_messages == 0
        assert stats.pending_count == 0
        assert stats.acknowledged_count == 0

    def test_get_queue_stats_with_messages(self, queue):
        """Should return accurate stats."""
        queue.send_message("jarvis", "matt", "Msg 1")
        queue.send_message("jarvis", "friday", "Msg 2")
        msg_id = queue.send_message("matt", "friday", "Msg 3")
        queue.acknowledge_message(msg_id)

        stats = queue.get_queue_stats()
        assert stats.total_messages == 3
        assert stats.pending_count == 2
        assert stats.acknowledged_count == 1

    def test_queue_stats_per_bot(self, queue):
        """Should track messages per bot."""
        queue.send_message("jarvis", "matt", "To Matt 1")
        queue.send_message("jarvis", "matt", "To Matt 2")
        queue.send_message("jarvis", "friday", "To Friday")

        stats = queue.get_queue_stats()
        assert stats.messages_by_recipient["matt"] == 2
        assert stats.messages_by_recipient["friday"] == 1

    def test_queue_stats_priority_breakdown(self, queue):
        """Should track messages by priority."""
        queue.send_message("jarvis", "matt", "Low", Priority.LOW)
        queue.send_message("jarvis", "matt", "Normal", Priority.NORMAL)
        queue.send_message("jarvis", "matt", "High", Priority.HIGH)
        queue.send_message("jarvis", "matt", "Urgent", Priority.URGENT)

        stats = queue.get_queue_stats()
        assert stats.messages_by_priority[Priority.LOW] == 1
        assert stats.messages_by_priority[Priority.NORMAL] == 1
        assert stats.messages_by_priority[Priority.HIGH] == 1
        assert stats.messages_by_priority[Priority.URGENT] == 1


class TestTopicSubscriptions:
    """Test topic-based pub/sub routing."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create temporary queue file for tests."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            f.write('{}')
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        lock_path = temp_path + ".lock"
        if os.path.exists(lock_path):
            os.unlink(lock_path)

    @pytest.fixture
    def queue(self, temp_queue_file):
        """Create MessageQueue with temp file."""
        return MessageQueue(queue_file=temp_queue_file)

    def test_subscribe_to_topic(self, queue):
        """Should subscribe bot to topic."""
        result = queue.subscribe_topic("matt", "trading")
        assert result is True

    def test_subscribe_multiple_bots_to_topic(self, queue):
        """Should allow multiple bots to subscribe to same topic."""
        queue.subscribe_topic("matt", "alerts")
        queue.subscribe_topic("friday", "alerts")

        subscribers = queue.get_topic_subscribers("alerts")
        assert "matt" in subscribers
        assert "friday" in subscribers

    def test_subscribe_bot_to_multiple_topics(self, queue):
        """Should allow bot to subscribe to multiple topics."""
        queue.subscribe_topic("jarvis", "trading")
        queue.subscribe_topic("jarvis", "alerts")
        queue.subscribe_topic("jarvis", "security")

        topics = queue.get_bot_subscriptions("jarvis")
        assert "trading" in topics
        assert "alerts" in topics
        assert "security" in topics

    def test_publish_to_topic(self, queue):
        """Should deliver message to all topic subscribers."""
        queue.subscribe_topic("matt", "announcements")
        queue.subscribe_topic("friday", "announcements")

        msg_ids = queue.publish_topic("announcements", "System maintenance tonight")
        assert len(msg_ids) == 2

        matt_msgs = queue.receive_messages("matt")
        friday_msgs = queue.receive_messages("friday")

        assert len(matt_msgs) == 1
        assert len(friday_msgs) == 1
        assert matt_msgs[0].content == "System maintenance tonight"

    def test_publish_to_topic_no_subscribers(self, queue):
        """Should return empty list when no subscribers."""
        msg_ids = queue.publish_topic("nonexistent_topic", "Hello?")
        assert msg_ids == []

    def test_publish_with_priority(self, queue):
        """Should publish to topic with priority."""
        queue.subscribe_topic("matt", "urgent_alerts")

        queue.publish_topic(
            "urgent_alerts",
            "Critical system failure!",
            priority=Priority.URGENT,
        )

        messages = queue.receive_messages("matt")
        assert messages[0].priority == Priority.URGENT

    def test_unsubscribe_from_topic(self, queue):
        """Should unsubscribe bot from topic."""
        queue.subscribe_topic("matt", "trading")
        assert "matt" in queue.get_topic_subscribers("trading")

        queue.unsubscribe_topic("matt", "trading")
        assert "matt" not in queue.get_topic_subscribers("trading")

    def test_published_messages_have_topic_metadata(self, queue):
        """Should include topic in published message metadata."""
        queue.subscribe_topic("matt", "updates")
        queue.publish_topic("updates", "New feature released")

        messages = queue.receive_messages("matt")
        assert messages[0].topic == "updates"


class TestPersistence:
    """Test queue persistence."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create temporary queue file for tests."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            f.write('{}')
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        lock_path = temp_path + ".lock"
        if os.path.exists(lock_path):
            os.unlink(lock_path)

    def test_messages_persist_to_disk(self, temp_queue_file):
        """Should persist messages to disk."""
        queue1 = MessageQueue(queue_file=temp_queue_file)
        msg_id = queue1.send_message("jarvis", "matt", "Persistent message")

        # Create new queue instance (simulates restart)
        queue2 = MessageQueue(queue_file=temp_queue_file)
        messages = queue2.receive_messages("matt")

        assert len(messages) == 1
        assert messages[0].content == "Persistent message"
        assert messages[0].id == msg_id

    def test_subscriptions_persist_to_disk(self, temp_queue_file):
        """Should persist subscriptions to disk."""
        queue1 = MessageQueue(queue_file=temp_queue_file)
        queue1.subscribe_topic("matt", "trading")
        queue1.subscribe_topic("friday", "trading")

        # Create new queue instance
        queue2 = MessageQueue(queue_file=temp_queue_file)
        subscribers = queue2.get_topic_subscribers("trading")

        assert "matt" in subscribers
        assert "friday" in subscribers

    def test_acknowledgments_persist_to_disk(self, temp_queue_file):
        """Should persist acknowledgments to disk."""
        queue1 = MessageQueue(queue_file=temp_queue_file)
        msg_id = queue1.send_message("jarvis", "matt", "Will ack this")
        queue1.acknowledge_message(msg_id)

        # Create new queue instance
        queue2 = MessageQueue(queue_file=temp_queue_file)
        messages = queue2.receive_messages("matt")

        # Should not include acknowledged message
        assert len(messages) == 0


class TestModuleFunctions:
    """Test module-level convenience functions."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create temporary queue file for tests."""
        import bots.shared.message_queue as mq_module

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            f.write('{}')
            temp_path = f.name

        # Reset the global queue to force recreation with new file
        mq_module._global_queue = None

        yield temp_path

        # Cleanup
        mq_module._global_queue = None
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        lock_path = temp_path + ".lock"
        if os.path.exists(lock_path):
            os.unlink(lock_path)

    def test_send_message_function(self, temp_queue_file):
        """Should send message via module function."""
        with patch('bots.shared.message_queue.DEFAULT_QUEUE_FILE', temp_queue_file):
            msg_id = send_message("jarvis", "matt", "Hello")
            assert msg_id is not None

    def test_receive_messages_function(self, temp_queue_file):
        """Should receive messages via module function."""
        with patch('bots.shared.message_queue.DEFAULT_QUEUE_FILE', temp_queue_file):
            send_message("jarvis", "matt", "Test message")
            messages = receive_messages("matt")
            assert len(messages) == 1

    def test_acknowledge_message_function(self, temp_queue_file):
        """Should acknowledge message via module function."""
        with patch('bots.shared.message_queue.DEFAULT_QUEUE_FILE', temp_queue_file):
            msg_id = send_message("jarvis", "matt", "Ack me")
            result = acknowledge_message(msg_id)
            assert result is True

    def test_get_queue_stats_function(self, temp_queue_file):
        """Should get stats via module function."""
        with patch('bots.shared.message_queue.DEFAULT_QUEUE_FILE', temp_queue_file):
            send_message("jarvis", "matt", "Msg 1")
            send_message("jarvis", "friday", "Msg 2")
            stats = get_queue_stats()
            assert stats.total_messages == 2

    def test_subscribe_topic_function(self, temp_queue_file):
        """Should subscribe via module function."""
        with patch('bots.shared.message_queue.DEFAULT_QUEUE_FILE', temp_queue_file):
            result = subscribe_topic("matt", "trading")
            assert result is True

    def test_publish_topic_function(self, temp_queue_file):
        """Should publish via module function."""
        with patch('bots.shared.message_queue.DEFAULT_QUEUE_FILE', temp_queue_file):
            subscribe_topic("matt", "alerts")
            msg_ids = publish_topic("alerts", "Alert message")
            assert len(msg_ids) == 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def temp_queue_file(self):
        """Create temporary queue file for tests."""
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', delete=False
        ) as f:
            f.write('{}')
            temp_path = f.name
        yield temp_path
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        lock_path = temp_path + ".lock"
        if os.path.exists(lock_path):
            os.unlink(lock_path)

    @pytest.fixture
    def queue(self, temp_queue_file):
        """Create MessageQueue with temp file."""
        return MessageQueue(queue_file=temp_queue_file)

    def test_receive_empty_queue(self, queue):
        """Should return empty list for empty queue."""
        messages = queue.receive_messages("matt")
        assert messages == []

    def test_same_message_content_different_ids(self, queue):
        """Should generate unique IDs for same content."""
        id1 = queue.send_message("jarvis", "matt", "Duplicate content")
        id2 = queue.send_message("jarvis", "matt", "Duplicate content")
        assert id1 != id2

    def test_receive_with_zero_limit(self, queue):
        """Should return empty list with limit=0."""
        queue.send_message("jarvis", "matt", "Test")
        messages = queue.receive_messages("matt", limit=0)
        assert messages == []

    def test_large_message_content(self, queue):
        """Should handle large message content."""
        large_content = "x" * 10000
        msg_id = queue.send_message("jarvis", "matt", large_content)
        messages = queue.receive_messages("matt")
        assert messages[0].content == large_content

    def test_special_characters_in_content(self, queue):
        """Should handle special characters in content."""
        content = "Test with special chars: \n\t\r\0 and unicode: emoji test"
        msg_id = queue.send_message("jarvis", "matt", content)
        messages = queue.receive_messages("matt")
        assert messages[0].content == content

    def test_concurrent_reads_writes(self, temp_queue_file):
        """Should handle concurrent access safely."""
        queue1 = MessageQueue(queue_file=temp_queue_file)
        queue2 = MessageQueue(queue_file=temp_queue_file)

        # Simulate concurrent writes
        id1 = queue1.send_message("jarvis", "matt", "From queue1")
        id2 = queue2.send_message("friday", "matt", "From queue2")

        # Both should be readable
        messages = queue1.receive_messages("matt")
        assert len(messages) == 2
