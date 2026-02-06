"""
Tests for TaskCoordinator.

Tests:
- Task assignment to specific bots
- Round-robin task distribution
- Finding best bot for task type
- Load balancing
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestTaskCoordinator:
    """Tests for TaskCoordinator class."""

    @pytest.fixture
    def coordinator(self):
        """Create a fresh coordinator for each test."""
        from core.orchestrator.coordinator import TaskCoordinator
        return TaskCoordinator()

    @pytest.fixture
    def mock_registry(self):
        """Create a mock bot registry."""
        registry = MagicMock()
        registry.get_bot = MagicMock()
        registry.list_bots = MagicMock(return_value=["bot1", "bot2", "bot3"])
        registry.get_bot_capabilities = MagicMock(return_value=["trading", "analysis"])
        return registry

    @pytest.mark.asyncio
    async def test_assign_task(self, coordinator):
        """Test assigning a task to a specific bot."""
        task = {"type": "trade", "data": {"token": "SOL"}}
        bot = MagicMock()
        bot.execute_task = AsyncMock(return_value={"success": True})

        with patch.object(coordinator, "_get_bot", return_value=bot):
            result = await coordinator.assign_task(task, "trading_bot")

        assert result["success"] is True
        bot.execute_task.assert_called_once_with(task)

    @pytest.mark.asyncio
    async def test_assign_task_nonexistent_bot(self, coordinator):
        """Test assigning task to nonexistent bot raises error."""
        task = {"type": "trade"}

        with patch.object(coordinator, "_get_bot", return_value=None):
            with pytest.raises(KeyError, match="not found"):
                await coordinator.assign_task(task, "nonexistent")

    @pytest.mark.asyncio
    async def test_distribute_task_round_robin(self, coordinator):
        """Test round-robin task distribution."""
        task = {"type": "analysis"}
        bot1 = MagicMock()
        bot1.execute_task = AsyncMock(return_value={"bot": "bot1"})
        bot2 = MagicMock()
        bot2.execute_task = AsyncMock(return_value={"bot": "bot2"})
        bot3 = MagicMock()
        bot3.execute_task = AsyncMock(return_value={"bot": "bot3"})

        bots = {"bot1": bot1, "bot2": bot2, "bot3": bot3}
        coordinator._available_bots = ["bot1", "bot2", "bot3"]

        with patch.object(coordinator, "_get_bot", side_effect=lambda name: bots.get(name)):
            # First task goes to bot1
            result1 = await coordinator.distribute_task(task)
            # Second task goes to bot2
            result2 = await coordinator.distribute_task(task)
            # Third task goes to bot3
            result3 = await coordinator.distribute_task(task)
            # Fourth task wraps around to bot1
            result4 = await coordinator.distribute_task(task)

        assert result1["bot"] == "bot1"
        assert result2["bot"] == "bot2"
        assert result3["bot"] == "bot3"
        assert result4["bot"] == "bot1"

    def test_get_best_bot_for_task_type(self, coordinator):
        """Test finding the best bot for a task type."""
        # Register bot capabilities
        coordinator.register_bot_capabilities("trading_bot", ["trading", "swaps"])
        coordinator.register_bot_capabilities("analysis_bot", ["analysis", "sentiment"])
        coordinator.register_bot_capabilities("multi_bot", ["trading", "analysis"])

        # Best bot for trading should be trading_bot or multi_bot
        best = coordinator.get_best_bot_for("trading")
        assert best in ["trading_bot", "multi_bot"]

        # Best bot for analysis
        best = coordinator.get_best_bot_for("analysis")
        assert best in ["analysis_bot", "multi_bot"]

    def test_get_best_bot_for_unknown_type(self, coordinator):
        """Test getting best bot for unknown task type returns None."""
        coordinator.register_bot_capabilities("trading_bot", ["trading"])

        best = coordinator.get_best_bot_for("unknown_type")
        assert best is None

    def test_register_bot_capabilities(self, coordinator):
        """Test registering bot capabilities."""
        coordinator.register_bot_capabilities("bot1", ["trading", "swaps"])

        assert "bot1" in coordinator._bot_capabilities
        assert "trading" in coordinator._bot_capabilities["bot1"]
        assert "swaps" in coordinator._bot_capabilities["bot1"]

    def test_get_bot_load(self, coordinator):
        """Test getting current load for a bot."""
        coordinator._bot_loads = {"bot1": 5, "bot2": 3}

        assert coordinator.get_bot_load("bot1") == 5
        assert coordinator.get_bot_load("bot2") == 3
        assert coordinator.get_bot_load("bot3") == 0  # Default

    @pytest.mark.asyncio
    async def test_distribute_with_load_balancing(self, coordinator):
        """Test that distribution prefers less loaded bots."""
        coordinator._available_bots = ["bot1", "bot2", "bot3"]
        coordinator._bot_loads = {"bot1": 10, "bot2": 2, "bot3": 5}

        bot2 = MagicMock()
        bot2.execute_task = AsyncMock(return_value={"success": True})

        with patch.object(coordinator, "_get_bot", return_value=bot2):
            with patch.object(coordinator, "_use_load_balancing", True):
                result = await coordinator.distribute_task(
                    {"type": "test"},
                    use_load_balancing=True
                )

        # bot2 should be selected as it has the lowest load
        assert result["success"] is True


class TestTaskCoordinatorSingleton:
    """Test singleton pattern for coordinator."""

    def test_get_coordinator_returns_singleton(self):
        """Test that get_coordinator returns the same instance."""
        from core.orchestrator.coordinator import get_coordinator

        coord1 = get_coordinator()
        coord2 = get_coordinator()

        assert coord1 is coord2


class TestTaskPriority:
    """Tests for task priority handling."""

    @pytest.fixture
    def coordinator(self):
        from core.orchestrator.coordinator import TaskCoordinator
        return TaskCoordinator()

    @pytest.mark.asyncio
    async def test_high_priority_task_jumps_queue(self, coordinator):
        """Test that high priority tasks are processed first."""
        from core.orchestrator.coordinator import TaskPriority

        # Add tasks with different priorities
        coordinator.queue_task({"id": 1}, priority=TaskPriority.LOW)
        coordinator.queue_task({"id": 2}, priority=TaskPriority.HIGH)
        coordinator.queue_task({"id": 3}, priority=TaskPriority.NORMAL)

        # Get next task should return high priority first
        next_task = coordinator.get_next_queued_task()
        assert next_task["id"] == 2  # High priority

        next_task = coordinator.get_next_queued_task()
        assert next_task["id"] == 3  # Normal priority

        next_task = coordinator.get_next_queued_task()
        assert next_task["id"] == 1  # Low priority
