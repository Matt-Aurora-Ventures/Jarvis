"""
BotTestCase Base Class

Provides base test case class for testing Telegram bots with
convenient helper methods for message simulation and assertions.
"""

import asyncio
import unittest
from typing import Any, Dict, List, Optional, Callable, Union
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MockUser:
    """Mock Telegram user for testing."""
    id: int
    username: Optional[str] = None
    first_name: str = "Test"
    last_name: Optional[str] = "User"
    is_bot: bool = False
    language_code: str = "en"


@dataclass
class MockChat:
    """Mock Telegram chat for testing."""
    id: int
    type: str = "private"
    title: Optional[str] = None
    username: Optional[str] = None


@dataclass
class MockMessage:
    """Mock Telegram message for testing."""
    message_id: int
    date: datetime
    chat: MockChat
    from_user: MockUser
    text: Optional[str] = None
    reply_to_message: Optional['MockMessage'] = None
    entities: List[Dict] = field(default_factory=list)

    # Convenience property
    @property
    def from_(self):
        """Alias for from_user (Telegram API uses 'from')."""
        return self.from_user


@dataclass
class MockCallbackQuery:
    """Mock Telegram callback query for testing."""
    id: str
    from_user: MockUser
    chat_instance: str
    data: Optional[str] = None
    message: Optional[MockMessage] = None


class APICallTracker:
    """Tracks API calls made during tests."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    def record(self, provider: str, method: str, **kwargs) -> None:
        """Record an API call."""
        self.calls.append({
            "provider": provider,
            "method": method,
            "timestamp": datetime.utcnow(),
            "kwargs": kwargs,
        })

    def get_calls(self, provider: Optional[str] = None, method: Optional[str] = None) -> List[Dict]:
        """Get recorded calls, optionally filtered."""
        result = self.calls
        if provider:
            result = [c for c in result if c["provider"] == provider]
        if method:
            result = [c for c in result if c["method"] == method]
        return result

    def was_called(self, provider: str, method: str) -> bool:
        """Check if a specific API method was called."""
        return len(self.get_calls(provider, method)) > 0

    def call_count(self, provider: str, method: str) -> int:
        """Get count of calls to a specific API method."""
        return len(self.get_calls(provider, method))

    def reset(self) -> None:
        """Clear all recorded calls."""
        self.calls.clear()


class ResponseCapture:
    """Captures bot responses during tests."""

    def __init__(self):
        self.responses: List[Dict[str, Any]] = []
        self.edited_messages: List[Dict[str, Any]] = []

    def capture_send(self, chat_id: int, text: str, **kwargs) -> Dict:
        """Capture a sent message."""
        msg = {
            "chat_id": chat_id,
            "text": text,
            "timestamp": datetime.utcnow(),
            **kwargs,
        }
        self.responses.append(msg)
        return msg

    def capture_edit(self, chat_id: int, message_id: int, text: str, **kwargs) -> Dict:
        """Capture an edited message."""
        msg = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "timestamp": datetime.utcnow(),
            **kwargs,
        }
        self.edited_messages.append(msg)
        return msg

    def get_last_response(self) -> Optional[Dict]:
        """Get the last captured response."""
        return self.responses[-1] if self.responses else None

    def get_all_text(self) -> List[str]:
        """Get all response texts."""
        return [r["text"] for r in self.responses]

    def reset(self) -> None:
        """Clear all captured responses."""
        self.responses.clear()
        self.edited_messages.clear()


class BotTestCase(unittest.TestCase):
    """
    Base test case for ClawdBot testing.

    Provides helper methods for:
    - Creating mock messages and callbacks
    - Asserting bot responses
    - Tracking API calls

    Usage:
        class TestMyBot(BotTestCase):
            def setUp(self):
                super().setUp()
                self.bot = MyBot()

            def test_help_command(self):
                message = self.mock_message("/help", user_id=12345)
                await self.bot.handle_help(message)
                self.assert_response_contains("Commands:")
    """

    _sequence: int = 0

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.api_tracker = APICallTracker()
        self.response_capture = ResponseCapture()
        self._patches: List[Any] = []
        BotTestCase._sequence = 0

    def tearDown(self) -> None:
        """Clean up test fixtures."""
        for p in self._patches:
            p.stop()
        self._patches.clear()
        self.api_tracker.reset()
        self.response_capture.reset()

    @classmethod
    def _next_id(cls) -> int:
        """Generate next sequential ID."""
        cls._sequence += 1
        return cls._sequence

    def mock_user(
        self,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        first_name: str = "Test",
        last_name: Optional[str] = "User",
        is_bot: bool = False,
    ) -> MockUser:
        """Create a mock user."""
        return MockUser(
            id=user_id or 100000000 + self._next_id(),
            username=username or f"testuser{self._sequence}",
            first_name=first_name,
            last_name=last_name,
            is_bot=is_bot,
        )

    def mock_chat(
        self,
        chat_id: Optional[int] = None,
        chat_type: str = "private",
        title: Optional[str] = None,
    ) -> MockChat:
        """Create a mock chat."""
        return MockChat(
            id=chat_id or 100000000 + self._next_id(),
            type=chat_type,
            title=title,
        )

    def mock_message(
        self,
        text: str,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        user: Optional[MockUser] = None,
        chat: Optional[MockChat] = None,
        reply_to: Optional[MockMessage] = None,
    ) -> MockMessage:
        """
        Create a mock Telegram message.

        Args:
            text: Message text
            user_id: Optional user ID (generates one if not provided)
            chat_id: Optional chat ID (uses user_id if not provided)
            message_id: Optional message ID (generates one if not provided)
            user: Optional MockUser instance
            chat: Optional MockChat instance
            reply_to: Optional message being replied to

        Returns:
            MockMessage instance ready for testing
        """
        if user is None:
            user = self.mock_user(user_id=user_id)
        if chat is None:
            chat = self.mock_chat(chat_id=chat_id or user.id)

        # Parse command entities
        entities = []
        if text.startswith("/"):
            # Find end of command
            space_idx = text.find(" ")
            cmd_end = space_idx if space_idx > 0 else len(text)
            entities.append({
                "type": "bot_command",
                "offset": 0,
                "length": cmd_end,
            })

        return MockMessage(
            message_id=message_id or self._next_id(),
            date=datetime.utcnow(),
            chat=chat,
            from_user=user,
            text=text,
            reply_to_message=reply_to,
            entities=entities,
        )

    def mock_callback(
        self,
        data: str,
        user_id: Optional[int] = None,
        message: Optional[MockMessage] = None,
    ) -> MockCallbackQuery:
        """
        Create a mock callback query (button press).

        Args:
            data: Callback data string
            user_id: Optional user ID
            message: Optional message the callback is attached to

        Returns:
            MockCallbackQuery instance
        """
        user = self.mock_user(user_id=user_id)

        if message is None:
            message = self.mock_message("Previous message", user=user)

        return MockCallbackQuery(
            id=f"callback_{self._next_id()}",
            from_user=user,
            chat_instance=str(message.chat.id),
            data=data,
            message=message,
        )

    def assert_response_contains(
        self,
        text: str,
        case_sensitive: bool = True,
    ) -> None:
        """
        Assert that a bot response contains specific text.

        Args:
            text: Text to look for in responses
            case_sensitive: Whether to do case-sensitive matching
        """
        responses = self.response_capture.get_all_text()

        if not responses:
            self.fail(f"No responses captured. Expected response containing: {text}")

        search_text = text if case_sensitive else text.lower()

        for response in responses:
            check_text = response if case_sensitive else response.lower()
            if search_text in check_text:
                return

        self.fail(
            f"No response contains '{text}'. "
            f"Captured responses: {responses}"
        )

    def assert_response_equals(self, expected: str) -> None:
        """Assert that the last response exactly equals expected text."""
        last_response = self.response_capture.get_last_response()

        if last_response is None:
            self.fail(f"No responses captured. Expected: {expected}")

        self.assertEqual(last_response["text"], expected)

    def assert_response_matches(self, pattern: str) -> None:
        """Assert that a response matches a regex pattern."""
        import re
        responses = self.response_capture.get_all_text()

        if not responses:
            self.fail(f"No responses captured. Expected pattern: {pattern}")

        for response in responses:
            if re.search(pattern, response):
                return

        self.fail(
            f"No response matches pattern '{pattern}'. "
            f"Captured responses: {responses}"
        )

    def assert_no_response(self) -> None:
        """Assert that no response was sent."""
        if self.response_capture.responses:
            self.fail(
                f"Expected no response but got: "
                f"{self.response_capture.get_all_text()}"
            )

    def assert_api_called(
        self,
        provider: str,
        method: str,
        times: Optional[int] = None,
    ) -> None:
        """
        Assert that an API method was called.

        Args:
            provider: API provider name (e.g., "telegram", "llm", "storage")
            method: Method name (e.g., "send_message", "generate")
            times: Optional exact number of times to expect
        """
        was_called = self.api_tracker.was_called(provider, method)

        if not was_called:
            self.fail(
                f"API {provider}.{method} was not called. "
                f"Recorded calls: {self.api_tracker.calls}"
            )

        if times is not None:
            actual = self.api_tracker.call_count(provider, method)
            self.assertEqual(
                actual, times,
                f"Expected {provider}.{method} to be called {times} times, "
                f"but was called {actual} times"
            )

    def assert_api_not_called(self, provider: str, method: str) -> None:
        """Assert that an API method was NOT called."""
        if self.api_tracker.was_called(provider, method):
            self.fail(
                f"API {provider}.{method} was called but shouldn't have been. "
                f"Recorded calls: {self.api_tracker.get_calls(provider, method)}"
            )

    def assert_response_count(self, expected: int) -> None:
        """Assert the number of responses sent."""
        actual = len(self.response_capture.responses)
        self.assertEqual(
            actual, expected,
            f"Expected {expected} responses, got {actual}"
        )


class AsyncBotTestCase(BotTestCase):
    """
    Async-aware bot test case.

    Use this when testing async bot handlers.
    """

    def setUp(self) -> None:
        super().setUp()
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self) -> None:
        super().tearDown()
        self.loop.close()

    def run_async(self, coro) -> Any:
        """Run an async coroutine in the test loop."""
        return self.loop.run_until_complete(coro)
