"""
Mock Helpers

Provides mock implementations of common services for testing.
"""

from typing import Any, Dict, List, Optional, Callable, Union
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class MockResponse:
    """Mock HTTP response."""
    status_code: int = 200
    json_data: Optional[Dict] = None
    text: str = ""
    headers: Dict[str, str] = field(default_factory=dict)

    def json(self) -> Dict:
        return self.json_data or {}

    @property
    def content(self) -> bytes:
        return self.text.encode()

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def create_mock_response(
    status_code: int = 200,
    json_data: Optional[Dict] = None,
    text: str = "",
    headers: Optional[Dict[str, str]] = None
) -> MockResponse:
    """Create a mock HTTP response."""
    return MockResponse(
        status_code=status_code,
        json_data=json_data,
        text=text,
        headers=headers or {},
    )


class MockProvider:
    """
    Mock LLM provider for testing.

    Usage:
        provider = MockProvider(response="Test response")
        result = await provider.generate("prompt")
    """

    def __init__(
        self,
        response: str = "Mock response",
        tokens: int = 100,
        should_fail: bool = False,
        failure_rate: float = 0.0
    ):
        self.response = response
        self.tokens = tokens
        self.should_fail = should_fail
        self.failure_rate = failure_rate
        self.calls: List[Dict] = []
        self._call_count = 0

    async def generate(
        self,
        prompt: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate mock LLM response."""
        self._call_count += 1
        self.calls.append({
            "prompt": prompt,
            "kwargs": kwargs,
            "timestamp": datetime.utcnow(),
        })

        if self.should_fail:
            raise Exception("Mock provider failure")

        import random
        if random.random() < self.failure_rate:
            raise Exception("Random mock failure")

        return {
            "text": self.response,
            "tokens": self.tokens,
            "model": kwargs.get("model", "mock-model"),
        }

    async def health_check(self) -> bool:
        """Mock health check."""
        return not self.should_fail

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset(self) -> None:
        """Reset mock state."""
        self.calls.clear()
        self._call_count = 0


class MockDatabase:
    """
    Mock database for testing.

    Usage:
        db = MockDatabase()
        await db.insert("users", {"id": 1, "name": "Test"})
        users = await db.query("users", {"id": 1})
    """

    def __init__(self):
        self.tables: Dict[str, List[Dict]] = {}
        self.queries: List[Dict] = []
        self._connected = True

    async def connect(self) -> None:
        """Mock connection."""
        self._connected = True

    async def disconnect(self) -> None:
        """Mock disconnection."""
        self._connected = False

    async def insert(self, table: str, data: Dict) -> Dict:
        """Insert data into mock table."""
        if table not in self.tables:
            self.tables[table] = []

        self.tables[table].append(data)
        self.queries.append({
            "type": "insert",
            "table": table,
            "data": data,
        })
        return data

    async def query(
        self,
        table: str,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """Query mock table."""
        self.queries.append({
            "type": "select",
            "table": table,
            "filters": filters,
        })

        if table not in self.tables:
            return []

        if not filters:
            return self.tables[table].copy()

        return [
            row for row in self.tables[table]
            if all(row.get(k) == v for k, v in filters.items())
        ]

    async def update(
        self,
        table: str,
        filters: Dict,
        data: Dict
    ) -> int:
        """Update mock table rows."""
        self.queries.append({
            "type": "update",
            "table": table,
            "filters": filters,
            "data": data,
        })

        if table not in self.tables:
            return 0

        count = 0
        for row in self.tables[table]:
            if all(row.get(k) == v for k, v in filters.items()):
                row.update(data)
                count += 1

        return count

    async def delete(self, table: str, filters: Dict) -> int:
        """Delete from mock table."""
        self.queries.append({
            "type": "delete",
            "table": table,
            "filters": filters,
        })

        if table not in self.tables:
            return 0

        original_len = len(self.tables[table])
        self.tables[table] = [
            row for row in self.tables[table]
            if not all(row.get(k) == v for k, v in filters.items())
        ]

        return original_len - len(self.tables[table])

    def reset(self) -> None:
        """Reset all mock data."""
        self.tables.clear()
        self.queries.clear()


class MockCache:
    """
    Mock cache for testing.

    Usage:
        cache = MockCache()
        await cache.set("key", "value", ttl=60)
        value = await cache.get("key")
    """

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._ttls: Dict[str, float] = {}
        self.operations: List[Dict] = []

    async def get(self, key: str) -> Optional[Any]:
        """Get cached value."""
        self.operations.append({"type": "get", "key": key})
        return self._data.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """Set cached value."""
        self.operations.append({
            "type": "set",
            "key": key,
            "value": value,
            "ttl": ttl,
        })
        self._data[key] = value
        if ttl:
            import time
            self._ttls[key] = time.time() + ttl

    async def delete(self, key: str) -> bool:
        """Delete cached value."""
        self.operations.append({"type": "delete", "key": key})
        if key in self._data:
            del self._data[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        return key in self._data

    async def clear(self) -> None:
        """Clear all cached values."""
        self._data.clear()
        self._ttls.clear()

    def reset(self) -> None:
        """Reset mock state."""
        self._data.clear()
        self._ttls.clear()
        self.operations.clear()


class MockHTTPClient:
    """
    Mock HTTP client for testing.

    Usage:
        client = MockHTTPClient()
        client.add_response("GET", "/api/test", {"data": "value"})
        response = await client.get("/api/test")
    """

    def __init__(self):
        self._responses: Dict[str, MockResponse] = {}
        self.requests: List[Dict] = []

    def add_response(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict] = None,
        status_code: int = 200,
        text: str = "",
        headers: Optional[Dict] = None
    ) -> None:
        """Add a mock response."""
        key = f"{method.upper()}:{url}"
        self._responses[key] = MockResponse(
            status_code=status_code,
            json_data=json_data,
            text=text,
            headers=headers or {},
        )

    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> MockResponse:
        """Make a mock request."""
        self.requests.append({
            "method": method,
            "url": url,
            "kwargs": kwargs,
        })

        key = f"{method.upper()}:{url}"
        if key in self._responses:
            return self._responses[key]

        return MockResponse(status_code=404, json_data={"error": "Not found"})

    async def get(self, url: str, **kwargs) -> MockResponse:
        return await self._make_request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> MockResponse:
        return await self._make_request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> MockResponse:
        return await self._make_request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> MockResponse:
        return await self._make_request("DELETE", url, **kwargs)

    def reset(self) -> None:
        """Reset mock state."""
        self._responses.clear()
        self.requests.clear()


class MockWebSocket:
    """
    Mock WebSocket for testing.

    Usage:
        ws = MockWebSocket()
        await ws.send("message")
        received = await ws.receive()
    """

    def __init__(self):
        self.sent_messages: List[str] = []
        self.receive_queue: List[str] = []
        self.closed = False

    async def send(self, message: Union[str, Dict]) -> None:
        """Send a message."""
        if isinstance(message, dict):
            message = json.dumps(message)
        self.sent_messages.append(message)

    async def receive(self) -> str:
        """Receive a message."""
        if self.receive_queue:
            return self.receive_queue.pop(0)
        raise Exception("No messages to receive")

    def add_message(self, message: Union[str, Dict]) -> None:
        """Add a message to receive queue."""
        if isinstance(message, dict):
            message = json.dumps(message)
        self.receive_queue.append(message)

    async def close(self) -> None:
        """Close the connection."""
        self.closed = True


class MockTelegramBot:
    """Mock Telegram bot for testing."""

    def __init__(self):
        self.sent_messages: List[Dict] = []
        self.edited_messages: List[Dict] = []

    async def send_message(
        self,
        chat_id: int,
        text: str,
        **kwargs
    ) -> Dict:
        """Send a message."""
        msg = {
            "chat_id": chat_id,
            "text": text,
            **kwargs,
        }
        self.sent_messages.append(msg)
        return msg

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        **kwargs
    ) -> Dict:
        """Edit a message."""
        msg = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            **kwargs,
        }
        self.edited_messages.append(msg)
        return msg

    def reset(self) -> None:
        """Reset mock state."""
        self.sent_messages.clear()
        self.edited_messages.clear()
