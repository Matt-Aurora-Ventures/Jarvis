"""
Tests for BotRegistry.

Tests:
- Getting bots by name
- Listing all bots
- Getting bot capabilities
- Singleton pattern
"""

import pytest
from unittest.mock import MagicMock


class TestBotRegistry:
    """Tests for BotRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry for each test."""
        from core.orchestrator.registry import BotRegistry
        # Create new instance, bypassing singleton for testing
        return BotRegistry.__new__(BotRegistry)

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot instance."""
        bot = MagicMock()
        bot.name = "test_bot"
        bot.capabilities = ["trading", "analysis"]
        return bot

    def test_register_and_get_bot(self, registry):
        """Test registering and getting a bot."""
        registry._bots = {}
        bot = MagicMock()

        registry.register("my_bot", bot)
        retrieved = registry.get_bot("my_bot")

        assert retrieved is bot

    def test_get_nonexistent_bot_returns_none(self, registry):
        """Test that getting a nonexistent bot returns None."""
        registry._bots = {}

        result = registry.get_bot("nonexistent")

        assert result is None

    def test_list_bots(self, registry):
        """Test listing all registered bots."""
        registry._bots = {}
        registry.register("bot1", MagicMock())
        registry.register("bot2", MagicMock())
        registry.register("bot3", MagicMock())

        bot_names = registry.list_bots()

        assert len(bot_names) == 3
        assert "bot1" in bot_names
        assert "bot2" in bot_names
        assert "bot3" in bot_names

    def test_list_bots_empty(self, registry):
        """Test listing bots when none are registered."""
        registry._bots = {}

        bot_names = registry.list_bots()

        assert bot_names == []

    def test_get_bot_capabilities(self, registry, mock_bot):
        """Test getting capabilities for a bot."""
        registry._bots = {}
        registry._capabilities = {}
        registry.register("test_bot", mock_bot, capabilities=["trading", "analysis"])

        caps = registry.get_bot_capabilities("test_bot")

        assert "trading" in caps
        assert "analysis" in caps

    def test_get_bot_capabilities_nonexistent(self, registry):
        """Test getting capabilities for nonexistent bot returns empty list."""
        registry._bots = {}
        registry._capabilities = {}

        caps = registry.get_bot_capabilities("nonexistent")

        assert caps == []

    def test_unregister_bot(self, registry, mock_bot):
        """Test unregistering a bot."""
        registry._bots = {}
        registry._capabilities = {}
        registry.register("test_bot", mock_bot, capabilities=["trading"])

        registry.unregister("test_bot")

        assert "test_bot" not in registry._bots
        assert "test_bot" not in registry._capabilities

    def test_find_bots_by_capability(self, registry):
        """Test finding bots that have a specific capability."""
        registry._bots = {}
        registry._capabilities = {}

        registry.register("bot1", MagicMock(), capabilities=["trading", "swaps"])
        registry.register("bot2", MagicMock(), capabilities=["analysis", "sentiment"])
        registry.register("bot3", MagicMock(), capabilities=["trading", "analysis"])

        trading_bots = registry.find_bots_by_capability("trading")
        analysis_bots = registry.find_bots_by_capability("analysis")

        assert len(trading_bots) == 2
        assert "bot1" in trading_bots
        assert "bot3" in trading_bots

        assert len(analysis_bots) == 2
        assert "bot2" in analysis_bots
        assert "bot3" in analysis_bots

    def test_has_bot(self, registry, mock_bot):
        """Test checking if a bot is registered."""
        registry._bots = {}
        registry.register("test_bot", mock_bot)

        assert registry.has_bot("test_bot") is True
        assert registry.has_bot("nonexistent") is False


class TestBotRegistrySingleton:
    """Test singleton pattern for registry."""

    def test_get_registry_returns_singleton(self):
        """Test that get_registry returns the same instance."""
        from core.orchestrator.registry import get_registry

        reg1 = get_registry()
        reg2 = get_registry()

        assert reg1 is reg2

    def test_registry_persists_state(self):
        """Test that registry state persists across get_registry calls."""
        from core.orchestrator.registry import get_registry

        reg1 = get_registry()
        reg1.register("persistent_bot", MagicMock())

        reg2 = get_registry()

        assert reg2.has_bot("persistent_bot") is True


class TestBotMetadata:
    """Tests for bot metadata storage."""

    @pytest.fixture
    def registry(self):
        from core.orchestrator.registry import BotRegistry
        reg = BotRegistry.__new__(BotRegistry)
        reg._bots = {}
        reg._capabilities = {}
        reg._metadata = {}
        return reg

    def test_store_and_retrieve_metadata(self, registry):
        """Test storing and retrieving bot metadata."""
        registry.register(
            "test_bot",
            MagicMock(),
            capabilities=["trading"],
            metadata={"version": "1.0", "author": "test"}
        )

        metadata = registry.get_bot_metadata("test_bot")

        assert metadata["version"] == "1.0"
        assert metadata["author"] == "test"

    def test_get_metadata_nonexistent(self, registry):
        """Test getting metadata for nonexistent bot returns empty dict."""
        metadata = registry.get_bot_metadata("nonexistent")

        assert metadata == {}

    def test_update_metadata(self, registry):
        """Test updating bot metadata."""
        registry.register("test_bot", MagicMock(), metadata={"version": "1.0"})

        registry.update_metadata("test_bot", {"version": "2.0", "new_field": "value"})

        metadata = registry.get_bot_metadata("test_bot")
        assert metadata["version"] == "2.0"
        assert metadata["new_field"] == "value"
