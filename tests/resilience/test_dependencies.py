"""
JARVIS Dependency Failure Tests

Tests system behavior when external dependencies fail.

Dependencies Tested:
- Jupiter API (DEX)
- Grok API (AI content)
- Telegram API
- Solscan/Birdeye API

Expected Behavior:
- Graceful degradation
- Fallback to cached data
- Queue for later retry

Usage:
    pytest tests/resilience/test_dependencies.py -v
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@dataclass
class DependencyStatus:
    """Status of a dependency."""
    name: str
    available: bool = True
    last_success: Optional[float] = None
    last_failure: Optional[float] = None
    failure_count: int = 0
    cached_data: Optional[Any] = None
    cache_timestamp: Optional[float] = None

    @property
    def cache_age_seconds(self) -> float:
        if self.cache_timestamp is None:
            return float("inf")
        return time.time() - self.cache_timestamp

    def mark_success(self, data: Any = None):
        """Mark a successful call."""
        self.available = True
        self.last_success = time.time()
        self.failure_count = 0
        if data is not None:
            self.cached_data = data
            self.cache_timestamp = time.time()

    def mark_failure(self):
        """Mark a failed call."""
        self.failure_count += 1
        self.last_failure = time.time()
        if self.failure_count >= 3:
            self.available = False


class DependencyManager:
    """Manage external dependencies with fallbacks."""

    def __init__(self):
        self.dependencies: Dict[str, DependencyStatus] = {}
        self.fallback_handlers: Dict[str, Callable] = {}
        self.message_queue: List[Dict[str, Any]] = []

    def register_dependency(
        self,
        name: str,
        fallback: Callable = None,
        initial_cache: Any = None,
    ):
        """Register a dependency."""
        self.dependencies[name] = DependencyStatus(
            name=name,
            cached_data=initial_cache,
            cache_timestamp=time.time() if initial_cache else None,
        )
        if fallback:
            self.fallback_handlers[name] = fallback

    async def call_with_fallback(
        self,
        name: str,
        operation: Callable,
        args: tuple = (),
        kwargs: dict = None,
        cache_ttl_seconds: float = 300,
    ) -> Any:
        """
        Call a dependency with automatic fallback.

        Priority:
        1. Try the operation
        2. Use cached data if available and fresh
        3. Use fallback handler if registered
        4. Raise exception
        """
        kwargs = kwargs or {}
        dep = self.dependencies.get(name)

        if not dep:
            raise ValueError(f"Unknown dependency: {name}")

        try:
            result = await operation(*args, **kwargs)
            dep.mark_success(result)
            return result

        except Exception as e:
            dep.mark_failure()

            # Try cached data
            if dep.cached_data is not None and dep.cache_age_seconds < cache_ttl_seconds:
                return dep.cached_data

            # Try fallback
            if name in self.fallback_handlers:
                fallback = self.fallback_handlers[name]
                if asyncio.iscoroutinefunction(fallback):
                    return await fallback(*args, **kwargs)
                return fallback(*args, **kwargs)

            raise

    def queue_for_retry(self, name: str, operation_data: Dict[str, Any]):
        """Queue an operation for later retry."""
        self.message_queue.append({
            "dependency": name,
            "data": operation_data,
            "queued_at": time.time(),
        })

    def get_queue_size(self) -> int:
        """Get the current queue size."""
        return len(self.message_queue)

    async def process_queue(self, operation: Callable, max_items: int = 10) -> int:
        """Process queued items."""
        processed = 0
        items_to_process = self.message_queue[:max_items]

        for item in items_to_process:
            try:
                await operation(item["data"])
                self.message_queue.remove(item)
                processed += 1
            except Exception:
                # Keep in queue for later
                pass

        return processed

    def get_dependency_status(self, name: str) -> Optional[DependencyStatus]:
        """Get status of a dependency."""
        return self.dependencies.get(name)

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all dependencies."""
        return {
            name: {
                "available": dep.available,
                "failure_count": dep.failure_count,
                "has_cache": dep.cached_data is not None,
                "cache_age_seconds": dep.cache_age_seconds if dep.cached_data else None,
            }
            for name, dep in self.dependencies.items()
        }


# =============================================================================
# Mock External Services
# =============================================================================

class MockJupiterAPI:
    """Mock Jupiter DEX API."""

    def __init__(self, available: bool = True):
        self.available = available
        self.call_count = 0

    async def get_price(self, token_mint: str) -> Dict[str, Any]:
        """Get token price."""
        self.call_count += 1
        if not self.available:
            raise ConnectionError("Jupiter API unavailable")

        return {
            "mint": token_mint,
            "price": 1.5,
            "timestamp": time.time(),
        }

    async def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
    ) -> Dict[str, Any]:
        """Get swap quote."""
        self.call_count += 1
        if not self.available:
            raise ConnectionError("Jupiter API unavailable")

        return {
            "input_mint": input_mint,
            "output_mint": output_mint,
            "in_amount": amount,
            "out_amount": int(amount * 0.98),  # 2% slippage
            "price_impact": 0.5,
        }


class MockGrokAPI:
    """Mock Grok/xAI API."""

    def __init__(self, available: bool = True):
        self.available = available
        self.call_count = 0

    async def generate_content(self, prompt: str) -> Dict[str, Any]:
        """Generate content."""
        self.call_count += 1
        if not self.available:
            raise ConnectionError("Grok API unavailable")

        return {
            "content": f"Generated content for: {prompt[:50]}...",
            "tokens_used": 150,
        }


class MockClaudeAPI:
    """Mock Claude API as Grok fallback."""

    def __init__(self, available: bool = True):
        self.available = available
        self.call_count = 0

    async def generate_content(self, prompt: str) -> Dict[str, Any]:
        """Generate content as fallback."""
        self.call_count += 1
        if not self.available:
            raise ConnectionError("Claude API unavailable")

        return {
            "content": f"Claude fallback content for: {prompt[:50]}...",
            "tokens_used": 200,
            "source": "claude_fallback",
        }


class MockTelegramAPI:
    """Mock Telegram API."""

    def __init__(self, available: bool = True):
        self.available = available
        self.sent_messages: List[Dict[str, Any]] = []
        self.queued_messages: List[Dict[str, Any]] = []

    async def send_message(self, chat_id: str, text: str) -> Dict[str, Any]:
        """Send a message."""
        if not self.available:
            # Queue for later
            self.queued_messages.append({
                "chat_id": chat_id,
                "text": text,
                "queued_at": time.time(),
            })
            raise ConnectionError("Telegram API unavailable")

        message = {
            "chat_id": chat_id,
            "text": text,
            "sent_at": time.time(),
        }
        self.sent_messages.append(message)
        return message


class MockSolscanAPI:
    """Mock Solscan API."""

    def __init__(self, available: bool = True):
        self.available = available

    async def get_token_info(self, mint: str) -> Dict[str, Any]:
        """Get token information."""
        if not self.available:
            raise ConnectionError("Solscan API unavailable")

        return {
            "mint": mint,
            "name": "Test Token",
            "symbol": "TEST",
            "holders": 1000,
            "decimals": 9,
        }


class MockBirdeyeAPI:
    """Mock Birdeye API as Solscan fallback."""

    def __init__(self, available: bool = True):
        self.available = available

    async def get_token_info(self, mint: str) -> Dict[str, Any]:
        """Get token information."""
        if not self.available:
            raise ConnectionError("Birdeye API unavailable")

        return {
            "address": mint,
            "name": "Test Token",
            "symbol": "TEST",
            "holder_count": 1000,
            "decimals": 9,
            "source": "birdeye",
        }


# =============================================================================
# Dependency Failure Test Scenarios
# =============================================================================

class TestJupiterAPIFailure:
    """Tests for Jupiter API dependency failure."""

    @pytest.fixture
    def dep_manager(self):
        return DependencyManager()

    @pytest.fixture
    def jupiter_api(self):
        return MockJupiterAPI(available=True)

    @pytest.mark.asyncio
    async def test_jupiter_down_uses_cached_prices(
        self,
        dep_manager: DependencyManager,
        jupiter_api: MockJupiterAPI
    ):
        """
        Scenario: Jupiter API down.

        Expected: System uses cached prices.
        """
        # Register with initial cache
        cached_price = {"mint": "token_123", "price": 1.2, "timestamp": time.time() - 60}
        dep_manager.register_dependency("jupiter", initial_cache=cached_price)

        # First call succeeds and updates cache
        result1 = await dep_manager.call_with_fallback(
            "jupiter",
            jupiter_api.get_price,
            args=("token_123",),
        )
        assert result1["price"] == 1.5

        # Jupiter goes down
        jupiter_api.available = False

        # Second call uses cache
        result2 = await dep_manager.call_with_fallback(
            "jupiter",
            jupiter_api.get_price,
            args=("token_123",),
            cache_ttl_seconds=300,
        )

        assert result2["price"] == 1.5  # From cache
        status = dep_manager.get_dependency_status("jupiter")
        assert status.failure_count > 0

        print(f"\n[Jupiter API Down Test]")
        print(f"  Cache age: {status.cache_age_seconds:.2f}s")
        print(f"  Failure count: {status.failure_count}")

    @pytest.mark.asyncio
    async def test_jupiter_down_stale_cache(
        self,
        dep_manager: DependencyManager,
        jupiter_api: MockJupiterAPI
    ):
        """
        Scenario: Jupiter down with stale cache.

        Expected: Raises exception (no fresh data available).
        """
        # Register with very old cache
        dep_manager.register_dependency("jupiter")
        dep_manager.dependencies["jupiter"].cached_data = {"price": 1.0}
        dep_manager.dependencies["jupiter"].cache_timestamp = time.time() - 1000

        jupiter_api.available = False

        # Should fail with no fresh cache
        with pytest.raises(ConnectionError):
            await dep_manager.call_with_fallback(
                "jupiter",
                jupiter_api.get_price,
                args=("token_123",),
                cache_ttl_seconds=60,  # Cache is older than TTL
            )


class TestGrokAPIFailure:
    """Tests for Grok API dependency failure."""

    @pytest.fixture
    def dep_manager(self):
        return DependencyManager()

    @pytest.fixture
    def grok_api(self):
        return MockGrokAPI(available=True)

    @pytest.fixture
    def claude_api(self):
        return MockClaudeAPI(available=True)

    @pytest.mark.asyncio
    async def test_grok_down_uses_claude_fallback(
        self,
        dep_manager: DependencyManager,
        grok_api: MockGrokAPI,
        claude_api: MockClaudeAPI
    ):
        """
        Scenario: Grok API down.

        Expected: Falls back to Claude API.
        """
        # Register with Claude as async fallback
        async def claude_fallback(prompt: str):
            return await claude_api.generate_content(prompt)

        dep_manager.register_dependency(
            "grok",
            fallback=claude_fallback,
        )

        # Grok is down
        grok_api.available = False

        result = await dep_manager.call_with_fallback(
            "grok",
            grok_api.generate_content,
            args=("Generate a tweet about SOL",),
        )

        assert "Claude fallback" in result["content"]
        assert result["source"] == "claude_fallback"

        print(f"\n[Grok API Down - Claude Fallback Test]")
        print(f"  Grok calls: {grok_api.call_count}")
        print(f"  Claude calls: {claude_api.call_count}")

    @pytest.mark.asyncio
    async def test_grok_down_claude_down_uses_template(
        self,
        dep_manager: DependencyManager,
        grok_api: MockGrokAPI,
        claude_api: MockClaudeAPI
    ):
        """
        Scenario: Both Grok and Claude down.

        Expected: Falls back to template response.
        """
        def template_fallback(prompt: str) -> Dict[str, Any]:
            return {
                "content": "Market update: Check back later for AI insights.",
                "source": "template",
            }

        # Both APIs down
        grok_api.available = False
        claude_api.available = False

        # Fallback chain: Claude -> Template
        async def fallback_chain(prompt: str):
            try:
                return await claude_api.generate_content(prompt)
            except ConnectionError:
                return template_fallback(prompt)

        dep_manager.register_dependency("grok", fallback=fallback_chain)

        result = await dep_manager.call_with_fallback(
            "grok",
            grok_api.generate_content,
            args=("Generate market analysis",),
        )

        assert result["source"] == "template"
        assert "Check back later" in result["content"]


class TestTelegramAPIFailure:
    """Tests for Telegram API dependency failure."""

    @pytest.fixture
    def dep_manager(self):
        return DependencyManager()

    @pytest.fixture
    def telegram_api(self):
        return MockTelegramAPI(available=True)

    @pytest.mark.asyncio
    async def test_telegram_down_queues_messages(
        self,
        dep_manager: DependencyManager,
        telegram_api: MockTelegramAPI
    ):
        """
        Scenario: Telegram API down.

        Expected: Messages are queued for later delivery.
        """
        dep_manager.register_dependency("telegram")

        # Telegram is down
        telegram_api.available = False

        # Try to send messages - they should be queued
        messages_to_send = [
            {"chat_id": "123", "text": "Message 1"},
            {"chat_id": "123", "text": "Message 2"},
            {"chat_id": "456", "text": "Message 3"},
        ]

        for msg in messages_to_send:
            try:
                await telegram_api.send_message(msg["chat_id"], msg["text"])
            except ConnectionError:
                dep_manager.queue_for_retry("telegram", msg)

        # Verify messages are queued
        assert len(telegram_api.queued_messages) == 3
        assert dep_manager.get_queue_size() == 3

        print(f"\n[Telegram Down - Queue Test]")
        print(f"  Messages queued: {dep_manager.get_queue_size()}")

    @pytest.mark.asyncio
    async def test_telegram_recovery_sends_queued(
        self,
        dep_manager: DependencyManager,
        telegram_api: MockTelegramAPI
    ):
        """
        Scenario: Telegram recovers after downtime.

        Expected: Queued messages are sent.
        """
        dep_manager.register_dependency("telegram")

        # Telegram is down - queue messages
        telegram_api.available = False
        for i in range(5):
            dep_manager.queue_for_retry("telegram", {
                "chat_id": "123",
                "text": f"Queued message {i}",
            })

        assert dep_manager.get_queue_size() == 5

        # Telegram recovers
        telegram_api.available = True

        # Process queue
        async def send_queued(data):
            await telegram_api.send_message(data["chat_id"], data["text"])

        processed = await dep_manager.process_queue(send_queued)

        print(f"\n[Telegram Recovery Test]")
        print(f"  Processed: {processed}")
        print(f"  Sent messages: {len(telegram_api.sent_messages)}")
        print(f"  Remaining in queue: {dep_manager.get_queue_size()}")

        assert processed == 5
        assert len(telegram_api.sent_messages) == 5


class TestSolscanAPIFailure:
    """Tests for Solscan API dependency failure."""

    @pytest.fixture
    def dep_manager(self):
        return DependencyManager()

    @pytest.fixture
    def solscan_api(self):
        return MockSolscanAPI(available=True)

    @pytest.fixture
    def birdeye_api(self):
        return MockBirdeyeAPI(available=True)

    @pytest.mark.asyncio
    async def test_solscan_down_uses_birdeye(
        self,
        dep_manager: DependencyManager,
        solscan_api: MockSolscanAPI,
        birdeye_api: MockBirdeyeAPI
    ):
        """
        Scenario: Solscan down.

        Expected: Falls back to Birdeye API.
        """
        dep_manager.register_dependency(
            "solscan",
            fallback=birdeye_api.get_token_info,
        )

        # Solscan is down
        solscan_api.available = False

        result = await dep_manager.call_with_fallback(
            "solscan",
            solscan_api.get_token_info,
            args=("token_mint_123",),
        )

        assert result["source"] == "birdeye"
        assert result["symbol"] == "TEST"

        print(f"\n[Solscan Down - Birdeye Fallback]")
        print(f"  Result source: {result.get('source', 'solscan')}")


class TestDependencyStatusTracking:
    """Tests for dependency status tracking."""

    @pytest.fixture
    def dep_manager(self):
        return DependencyManager()

    def test_failure_count_tracking(self, dep_manager: DependencyManager):
        """Test that failure counts are tracked correctly."""
        dep_manager.register_dependency("test_service")
        status = dep_manager.get_dependency_status("test_service")

        assert status.available
        assert status.failure_count == 0

        # Record failures
        for _ in range(3):
            status.mark_failure()

        assert status.failure_count == 3
        assert not status.available  # Should be marked unavailable

    def test_success_resets_failure_count(self, dep_manager: DependencyManager):
        """Test that success resets failure count."""
        dep_manager.register_dependency("test_service")
        status = dep_manager.get_dependency_status("test_service")

        # Record failures
        for _ in range(2):
            status.mark_failure()

        assert status.failure_count == 2

        # Success resets
        status.mark_success({"data": "test"})

        assert status.failure_count == 0
        assert status.available
        assert status.cached_data is not None

    def test_all_status_report(self, dep_manager: DependencyManager):
        """Test getting status of all dependencies."""
        dep_manager.register_dependency("jupiter")
        dep_manager.register_dependency("grok")
        dep_manager.register_dependency("telegram")

        status = dep_manager.get_all_status()

        assert "jupiter" in status
        assert "grok" in status
        assert "telegram" in status
        assert all(s["available"] for s in status.values())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
