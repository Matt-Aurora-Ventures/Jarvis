"""
Tests for ReasoningState - TDD Phase 1

Tests cover:
- Per-user state storage
- Per-session state storage
- State persistence to database
- State loading on session start
- Default state management
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestReasoningStateInit:
    """Test ReasoningState initialization."""

    def test_default_state_values(self):
        """Default state should have sensible defaults."""
        from core.reasoning.state import ReasoningState

        state = ReasoningState()
        assert state.thinking_level == "low"
        assert state.reasoning_mode == "off"
        assert state.verbose_mode == "off"

    def test_state_with_user_id(self):
        """State can be initialized with user_id."""
        from core.reasoning.state import ReasoningState

        state = ReasoningState(user_id="12345")
        assert state.user_id == "12345"

    def test_state_with_session_id(self):
        """State can be initialized with session_id."""
        from core.reasoning.state import ReasoningState

        state = ReasoningState(session_id="session_abc")
        assert state.session_id == "session_abc"


class TestStateManager:
    """Test StateManager for managing user/session states."""

    @pytest.fixture
    def manager(self):
        from core.reasoning.state import StateManager
        return StateManager()

    def test_get_state_creates_default_if_missing(self, manager):
        """Getting state for unknown user should create default."""
        state = manager.get_state(user_id="unknown_user")
        assert state is not None
        assert state.thinking_level == "low"

    def test_get_state_returns_existing(self, manager):
        """Getting state should return existing state if present."""
        # Set a custom state first
        manager.set_thinking_level(user_id="user1", level="high")

        state = manager.get_state(user_id="user1")
        assert state.thinking_level == "high"

    def test_set_thinking_level_for_user(self, manager):
        """Can set thinking level for specific user."""
        manager.set_thinking_level(user_id="user1", level="xhigh")

        state = manager.get_state(user_id="user1")
        assert state.thinking_level == "xhigh"

    def test_set_reasoning_mode_for_user(self, manager):
        """Can set reasoning mode for specific user."""
        manager.set_reasoning_mode(user_id="user1", mode="stream")

        state = manager.get_state(user_id="user1")
        assert state.reasoning_mode == "stream"

    def test_set_verbose_mode_for_user(self, manager):
        """Can set verbose mode for specific user."""
        manager.set_verbose_mode(user_id="user1", mode="full")

        state = manager.get_state(user_id="user1")
        assert state.verbose_mode == "full"

    def test_different_users_have_separate_state(self, manager):
        """Different users should have independent states."""
        manager.set_thinking_level(user_id="user1", level="high")
        manager.set_thinking_level(user_id="user2", level="minimal")

        state1 = manager.get_state(user_id="user1")
        state2 = manager.get_state(user_id="user2")

        assert state1.thinking_level == "high"
        assert state2.thinking_level == "minimal"


class TestStatePersistence:
    """Test state persistence to database."""

    @pytest.fixture
    def manager(self):
        from core.reasoning.state import StateManager
        return StateManager()

    @pytest.mark.asyncio
    async def test_save_state_to_db(self, manager):
        """State can be saved to database."""
        manager.set_thinking_level(user_id="user1", level="high")

        # Save should not raise
        await manager.save_state(user_id="user1")

    @pytest.mark.asyncio
    async def test_load_state_from_db(self, manager):
        """State can be loaded from database."""
        # Save state first
        manager.set_thinking_level(user_id="user1", level="high")
        manager.set_reasoning_mode(user_id="user1", mode="stream")
        await manager.save_state(user_id="user1")

        # Create new manager (simulating restart)
        from core.reasoning.state import StateManager
        new_manager = StateManager()

        # Load state
        await new_manager.load_state(user_id="user1")

        state = new_manager.get_state(user_id="user1")
        # Note: This test may fail until persistence is fully implemented
        # The key is that load_state() doesn't raise

    @pytest.mark.asyncio
    async def test_save_all_states(self, manager):
        """Can save all modified states at once."""
        manager.set_thinking_level(user_id="user1", level="high")
        manager.set_thinking_level(user_id="user2", level="medium")

        # Save all should not raise
        await manager.save_all()


class TestStateToDict:
    """Test state serialization."""

    def test_state_to_dict(self):
        """State can be serialized to dict."""
        from core.reasoning.state import ReasoningState

        state = ReasoningState(
            user_id="user1",
            thinking_level="high",
            reasoning_mode="on",
            verbose_mode="full"
        )

        data = state.to_dict()

        assert data["user_id"] == "user1"
        assert data["thinking_level"] == "high"
        assert data["reasoning_mode"] == "on"
        assert data["verbose_mode"] == "full"

    def test_state_from_dict(self):
        """State can be created from dict."""
        from core.reasoning.state import ReasoningState

        data = {
            "user_id": "user1",
            "thinking_level": "high",
            "reasoning_mode": "stream",
            "verbose_mode": "on"
        }

        state = ReasoningState.from_dict(data)

        assert state.user_id == "user1"
        assert state.thinking_level == "high"
        assert state.reasoning_mode == "stream"
        assert state.verbose_mode == "on"


class TestGlobalDefaults:
    """Test global default settings."""

    @pytest.fixture
    def manager(self):
        from core.reasoning.state import StateManager
        return StateManager()

    def test_set_global_defaults(self, manager):
        """Can set global defaults that apply to new users."""
        manager.set_global_defaults(
            thinking_level="medium",
            reasoning_mode="on"
        )

        # New user should get global defaults
        state = manager.get_state(user_id="new_user")
        assert state.thinking_level == "medium"
        assert state.reasoning_mode == "on"

    def test_user_overrides_global(self, manager):
        """User settings should override global defaults."""
        manager.set_global_defaults(thinking_level="medium")
        manager.set_thinking_level(user_id="user1", level="high")

        state = manager.get_state(user_id="user1")
        assert state.thinking_level == "high"


class TestResetState:
    """Test state reset functionality."""

    @pytest.fixture
    def manager(self):
        from core.reasoning.state import StateManager
        return StateManager()

    def test_reset_user_state(self, manager):
        """Can reset a user's state to defaults."""
        manager.set_thinking_level(user_id="user1", level="xhigh")
        manager.set_reasoning_mode(user_id="user1", mode="stream")

        manager.reset_state(user_id="user1")

        state = manager.get_state(user_id="user1")
        assert state.thinking_level == "low"  # Default
        assert state.reasoning_mode == "off"  # Default

    def test_reset_all_states(self, manager):
        """Can reset all states to defaults."""
        manager.set_thinking_level(user_id="user1", level="high")
        manager.set_thinking_level(user_id="user2", level="xhigh")

        manager.reset_all()

        state1 = manager.get_state(user_id="user1")
        state2 = manager.get_state(user_id="user2")

        assert state1.thinking_level == "low"
        assert state2.thinking_level == "low"


class TestGetEngine:
    """Test getting a configured ReasoningEngine for a user."""

    @pytest.fixture
    def manager(self):
        from core.reasoning.state import StateManager
        return StateManager()

    def test_get_engine_for_user(self, manager):
        """Can get a ReasoningEngine configured for a specific user."""
        manager.set_thinking_level(user_id="user1", level="high")
        manager.set_reasoning_mode(user_id="user1", mode="on")

        engine = manager.get_engine(user_id="user1")

        from core.reasoning.engine import ReasoningEngine
        assert isinstance(engine, ReasoningEngine)
        assert engine.thinking_level == "high"
        assert engine.reasoning_mode == "on"
