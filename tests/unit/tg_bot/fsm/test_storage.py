"""
Tests for FSM Redis storage backend.

TDD Phase 1: Define expected behaviors before implementation.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


class TestRedisStorage:
    """Test Redis storage for FSM state persistence."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.setex = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.exists = AsyncMock(return_value=0)
        mock.keys = AsyncMock(return_value=[])
        mock.expire = AsyncMock(return_value=True)
        mock.ping = AsyncMock(return_value=True)
        mock.scan = AsyncMock(return_value=(0, []))
        return mock

    @pytest.mark.asyncio
    async def test_storage_initialization(self):
        """Test Redis storage initializes with correct defaults."""
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(
            redis_url="redis://localhost:6379/0",
            key_prefix="jarvis:fsm:"
        )

        assert storage.redis_url == "redis://localhost:6379/0"
        assert storage.key_prefix == "jarvis:fsm:"
        assert storage.session_ttl == 3600  # Default 1 hour

    @pytest.mark.asyncio
    async def test_storage_custom_ttl(self):
        """Test Redis storage with custom TTL."""
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(
            redis_url="redis://localhost:6379/0",
            session_ttl=7200  # 2 hours
        )

        assert storage.session_ttl == 7200

    @pytest.mark.asyncio
    async def test_save_state(self, mock_redis):
        """Test saving FSM state to Redis."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import TradingStates

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            user_id = 123456
            chat_id = 789012

            await storage.set_state(
                user_id=user_id,
                chat_id=chat_id,
                state=TradingStates.waiting_for_token
            )

            # Verify Redis setex was called
            mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_load_state(self, mock_redis):
        """Test loading FSM state from Redis."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import TradingStates

        # Setup mock to return stored state
        stored_data = {
            "state": "TradingStates:waiting_for_token",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(stored_data))

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            state = await storage.get_state(user_id=123456, chat_id=789012)

            assert state == TradingStates.waiting_for_token

    @pytest.mark.asyncio
    async def test_load_state_missing(self, mock_redis):
        """Test loading state returns None when not found."""
        from tg_bot.fsm.storage import RedisFSMStorage

        mock_redis.get = AsyncMock(return_value=None)

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            state = await storage.get_state(user_id=123456, chat_id=789012)

            assert state is None

    @pytest.mark.asyncio
    async def test_save_session_data(self, mock_redis):
        """Test saving session data to Redis."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import SessionData

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            data = SessionData(
                user_id=123456,
                chat_id=789012,
                token_address="TokenABC",
                amount=1.5
            )

            await storage.set_data(
                user_id=123456,
                chat_id=789012,
                data=data
            )

            # Verify setex was called with correct TTL
            mock_redis.setex.assert_called()

    @pytest.mark.asyncio
    async def test_load_session_data(self, mock_redis):
        """Test loading session data from Redis."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import SessionData

        stored_data = {
            "user_id": 123456,
            "chat_id": 789012,
            "token_address": "TokenABC",
            "amount": 1.5,
            "wallet_address": None,
            "token_symbol": None,
            "slippage": None,
            "take_profit": None,
            "stop_loss": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(stored_data))

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            data = await storage.get_data(user_id=123456, chat_id=789012)

            assert data is not None
            assert data.token_address == "TokenABC"
            assert data.amount == 1.5

    @pytest.mark.asyncio
    async def test_clear_session(self, mock_redis):
        """Test clearing a session from Redis."""
        from tg_bot.fsm.storage import RedisFSMStorage

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            await storage.clear(user_id=123456, chat_id=789012)

            # Verify delete was called for both state and data keys
            assert mock_redis.delete.call_count >= 1

    @pytest.mark.asyncio
    async def test_state_ttl_refresh(self, mock_redis):
        """Test that TTL is refreshed on state update."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import TradingStates

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage(session_ttl=3600)

            await storage.set_state(
                user_id=123456,
                chat_id=789012,
                state=TradingStates.waiting_for_amount
            )

            # Verify TTL was set to 3600 seconds
            call_args = mock_redis.setex.call_args
            assert call_args[0][1] == 3600  # TTL argument


class TestWalletIsolation:
    """Test wallet-per-session isolation."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.ping = AsyncMock(return_value=True)
        return mock

    @pytest.mark.asyncio
    async def test_wallet_per_session(self, mock_redis):
        """Test each session has isolated wallet state."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import SessionData

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            # User 1 session
            data1 = SessionData(
                user_id=111,
                chat_id=1000,
                wallet_address="Wallet111"
            )
            await storage.set_data(user_id=111, chat_id=1000, data=data1)

            # User 2 session
            data2 = SessionData(
                user_id=222,
                chat_id=2000,
                wallet_address="Wallet222"
            )
            await storage.set_data(user_id=222, chat_id=2000, data=data2)

            # Verify separate keys were used
            calls = mock_redis.setex.call_args_list
            assert len(calls) == 2

            # Keys should be different (user-specific)
            key1 = calls[0][0][0]
            key2 = calls[1][0][0]
            assert key1 != key2
            assert "111" in key1
            assert "222" in key2

    @pytest.mark.asyncio
    async def test_session_key_format(self, mock_redis):
        """Test session key includes user and chat IDs."""
        from tg_bot.fsm.storage import RedisFSMStorage

        storage = RedisFSMStorage(key_prefix="test:")

        key = storage._make_state_key(user_id=123, chat_id=456)

        assert "123" in key
        assert "456" in key
        assert key.startswith("test:")


class TestSessionRecovery:
    """Test session recovery on bot restart."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock.setex = AsyncMock(return_value=True)
        mock.ping = AsyncMock(return_value=True)
        mock.scan = AsyncMock(return_value=(0, []))
        return mock

    @pytest.mark.asyncio
    async def test_recover_active_sessions(self, mock_redis):
        """Test recovering sessions from Redis on startup."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import TradingStates

        # Setup mock to return stored sessions
        stored_state = {
            "state": "TradingStates:waiting_for_confirmation",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        mock_redis.get = AsyncMock(return_value=json.dumps(stored_state))
        mock_redis.scan = AsyncMock(return_value=(0, [
            "jarvis:fsm:state:123:456",
            "jarvis:fsm:state:789:012"
        ]))

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            sessions = await storage.get_active_sessions()

            assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_session_survives_reconnect(self, mock_redis):
        """Test state persists through Redis reconnection."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import TradingStates

        stored_state = {
            "state": "TradingStates:waiting_for_amount",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            # Save state
            await storage.set_state(
                user_id=123,
                chat_id=456,
                state=TradingStates.waiting_for_amount
            )

            # Simulate reconnection by resetting client
            storage._redis = None

            # Load state (should reconnect)
            mock_redis.get = AsyncMock(return_value=json.dumps(stored_state))
            state = await storage.get_state(user_id=123, chat_id=456)

            assert state == TradingStates.waiting_for_amount


class TestMemoryFallback:
    """Test in-memory fallback when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_fallback_to_memory(self):
        """Test storage falls back to memory when Redis fails."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import TradingStates

        # Create storage that will fail to connect
        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")

        # Should not raise, but use memory fallback
        await storage.set_state(
            user_id=123,
            chat_id=456,
            state=TradingStates.waiting_for_token
        )

        state = await storage.get_state(user_id=123, chat_id=456)
        assert state == TradingStates.waiting_for_token

    @pytest.mark.asyncio
    async def test_memory_state_isolation(self):
        """Test memory fallback maintains isolation."""
        from tg_bot.fsm.storage import RedisFSMStorage
        from tg_bot.fsm.states import TradingStates, SessionData

        storage = RedisFSMStorage(redis_url="redis://invalid:6379/0")

        # User 1
        await storage.set_state(123, 1000, TradingStates.waiting_for_token)
        data1 = SessionData(user_id=123, chat_id=1000, amount=1.0)
        await storage.set_data(123, 1000, data1)

        # User 2
        await storage.set_state(456, 2000, TradingStates.waiting_for_amount)
        data2 = SessionData(user_id=456, chat_id=2000, amount=2.0)
        await storage.set_data(456, 2000, data2)

        # Verify isolation
        state1 = await storage.get_state(123, 1000)
        state2 = await storage.get_state(456, 2000)

        assert state1 == TradingStates.waiting_for_token
        assert state2 == TradingStates.waiting_for_amount


class TestSessionCleanup:
    """Test session cleanup functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = AsyncMock()
        mock.delete = AsyncMock(return_value=1)
        mock.ping = AsyncMock(return_value=True)
        mock.scan = AsyncMock(return_value=(0, []))
        return mock

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions(self, mock_redis):
        """Test automatic cleanup of expired sessions."""
        from tg_bot.fsm.storage import RedisFSMStorage

        # Return keys for expired sessions
        mock_redis.scan = AsyncMock(return_value=(0, [
            "jarvis:fsm:state:old_user:123"
        ]))

        with patch.object(RedisFSMStorage, '_get_redis', return_value=mock_redis):
            storage = RedisFSMStorage()

            # Redis handles TTL-based expiration automatically
            # This test verifies scan/cleanup logic
            count = await storage.cleanup_expired()

            # Should return count of cleaned sessions
            assert isinstance(count, int)
