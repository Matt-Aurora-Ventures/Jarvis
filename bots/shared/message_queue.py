"""JSON-backed inter-bot message queue."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4


DEFAULT_QUEUE_FILE = "/tmp/clawdbot-message-queue.json"
_global_queue: Optional["MessageQueue"] = None


class Priority(IntEnum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Message:
    id: str
    from_bot: str
    to_bot: str
    content: str
    priority: Priority = Priority.NORMAL
    acknowledged: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: Optional[str] = None
    topic: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "from_bot": self.from_bot,
            "to_bot": self.to_bot,
            "content": self.content,
            "priority": int(self.priority),
            "acknowledged": self.acknowledged,
            "timestamp": self.timestamp,
            "acknowledged_at": self.acknowledged_at,
            "topic": self.topic,
        }

    @staticmethod
    def from_dict(data: Dict[str, object]) -> "Message":
        return Message(
            id=str(data["id"]),
            from_bot=str(data["from_bot"]),
            to_bot=str(data["to_bot"]),
            content=str(data["content"]),
            priority=Priority(int(data.get("priority", Priority.NORMAL.value))),
            acknowledged=bool(data.get("acknowledged", False)),
            timestamp=str(data.get("timestamp", datetime.now(timezone.utc).isoformat())),
            acknowledged_at=(str(data["acknowledged_at"]) if data.get("acknowledged_at") else None),
            topic=(str(data["topic"]) if data.get("topic") else None),
        )


@dataclass
class QueueStats:
    total_messages: int
    pending_count: int
    acknowledged_count: int
    messages_by_recipient: Dict[str, int] = field(default_factory=dict)
    messages_by_priority: Dict[Priority, int] = field(default_factory=dict)


class MessageQueue:
    def __init__(self, queue_file: str = DEFAULT_QUEUE_FILE):
        self.queue_file = str(queue_file)
        self._lock = threading.Lock()
        self._init_storage()

    def _init_storage(self) -> None:
        path = Path(self.queue_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            self._write_payload({"messages": [], "subscriptions": {}})
            return
        try:
            payload = self._read_payload()
            payload.setdefault("messages", [])
            payload.setdefault("subscriptions", {})
            self._write_payload(payload)
        except Exception:
            self._write_payload({"messages": [], "subscriptions": {}})

    def _read_payload(self) -> Dict[str, object]:
        with open(self.queue_file, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        if not isinstance(raw, dict):
            return {"messages": [], "subscriptions": {}}
        return raw

    def _write_payload(self, payload: Dict[str, object]) -> None:
        with open(self.queue_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def send_message(
        self,
        from_bot: str,
        to_bot: str,
        message: str,
        priority: Priority = Priority.NORMAL,
        topic: Optional[str] = None,
    ) -> str:
        msg_id = f"msg_{uuid4().hex[:10]}"
        msg = Message(
            id=msg_id,
            from_bot=from_bot,
            to_bot=to_bot,
            content=message,
            priority=priority,
            topic=topic,
        )
        with self._lock:
            payload = self._read_payload()
            messages = payload.get("messages", [])
            if not isinstance(messages, list):
                messages = []
            messages.append(msg.to_dict())
            payload["messages"] = messages
            self._write_payload(payload)
        return msg_id

    def receive_messages(self, bot: str, limit: int = 50) -> List[Message]:
        if limit <= 0:
            return []
        payload = self._read_payload()
        messages_raw = payload.get("messages", [])
        if not isinstance(messages_raw, list):
            return []
        messages = [Message.from_dict(item) for item in messages_raw]
        filtered = [m for m in messages if m.to_bot == bot and not m.acknowledged]
        filtered.sort(key=lambda m: (-int(m.priority), m.timestamp))
        return filtered[:limit]

    def acknowledge_message(self, message_id: str) -> bool:
        with self._lock:
            payload = self._read_payload()
            messages_raw = payload.get("messages", [])
            if not isinstance(messages_raw, list):
                return False
            updated = False
            now = datetime.now(timezone.utc).isoformat()
            for idx, item in enumerate(messages_raw):
                msg = Message.from_dict(item)
                if msg.id == message_id:
                    msg.acknowledged = True
                    msg.acknowledged_at = now
                    messages_raw[idx] = msg.to_dict()
                    updated = True
                    break
            if updated:
                payload["messages"] = messages_raw
                self._write_payload(payload)
            return updated

    def get_queue_stats(self) -> QueueStats:
        payload = self._read_payload()
        messages_raw = payload.get("messages", [])
        if not isinstance(messages_raw, list):
            messages_raw = []
        messages = [Message.from_dict(item) for item in messages_raw]
        by_recipient: Dict[str, int] = {}
        by_priority: Dict[Priority, int] = {p: 0 for p in Priority}
        pending = 0
        acknowledged = 0
        for msg in messages:
            by_recipient[msg.to_bot] = by_recipient.get(msg.to_bot, 0) + 1
            by_priority[msg.priority] = by_priority.get(msg.priority, 0) + 1
            if msg.acknowledged:
                acknowledged += 1
            else:
                pending += 1
        return QueueStats(
            total_messages=len(messages),
            pending_count=pending,
            acknowledged_count=acknowledged,
            messages_by_recipient=by_recipient,
            messages_by_priority=by_priority,
        )

    # Topic subscriptions
    def subscribe_topic(self, bot: str, topic: str) -> bool:
        with self._lock:
            payload = self._read_payload()
            subs = payload.get("subscriptions", {})
            if not isinstance(subs, dict):
                subs = {}
            recipients = list(subs.get(topic, []))
            if bot not in recipients:
                recipients.append(bot)
            subs[topic] = sorted(set(recipients))
            payload["subscriptions"] = subs
            self._write_payload(payload)
        return True

    def unsubscribe_topic(self, bot: str, topic: str) -> bool:
        with self._lock:
            payload = self._read_payload()
            subs = payload.get("subscriptions", {})
            if not isinstance(subs, dict):
                subs = {}
            recipients = [name for name in list(subs.get(topic, [])) if name != bot]
            subs[topic] = recipients
            payload["subscriptions"] = subs
            self._write_payload(payload)
        return True

    def get_topic_subscribers(self, topic: str) -> List[str]:
        payload = self._read_payload()
        subs = payload.get("subscriptions", {})
        if not isinstance(subs, dict):
            return []
        return list(subs.get(topic, []))

    def get_bot_subscriptions(self, bot: str) -> List[str]:
        payload = self._read_payload()
        subs = payload.get("subscriptions", {})
        if not isinstance(subs, dict):
            return []
        topics = [topic for topic, members in subs.items() if bot in list(members)]
        return sorted(topics)

    def publish_topic(
        self,
        topic: str,
        message: str,
        from_bot: str = "system",
        priority: Priority = Priority.NORMAL,
    ) -> List[str]:
        recipients = self.get_topic_subscribers(topic)
        message_ids: List[str] = []
        for recipient in recipients:
            message_ids.append(
                self.send_message(
                    from_bot=from_bot,
                    to_bot=recipient,
                    message=message,
                    priority=priority,
                    topic=topic,
                )
            )
        return message_ids


def _get_global_queue() -> MessageQueue:
    global _global_queue
    if _global_queue is None or _global_queue.queue_file != DEFAULT_QUEUE_FILE:
        _global_queue = MessageQueue(queue_file=DEFAULT_QUEUE_FILE)
    return _global_queue


def send_message(from_bot: str, to_bot: str, message: str, priority: Priority = Priority.NORMAL) -> str:
    return _get_global_queue().send_message(from_bot, to_bot, message, priority=priority)


def receive_messages(bot: str, limit: int = 50) -> List[Message]:
    return _get_global_queue().receive_messages(bot, limit=limit)


def acknowledge_message(message_id: str) -> bool:
    return _get_global_queue().acknowledge_message(message_id)


def get_queue_stats() -> QueueStats:
    return _get_global_queue().get_queue_stats()


def subscribe_topic(bot: str, topic: str) -> bool:
    return _get_global_queue().subscribe_topic(bot, topic)


def publish_topic(topic: str, message: str, priority: Priority = Priority.NORMAL) -> List[str]:
    return _get_global_queue().publish_topic(topic, message, priority=priority)

