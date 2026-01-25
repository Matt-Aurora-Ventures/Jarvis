"""
Unit Tests for Agent Coordinator

Tests the intelligent agent coordination system:
- Agent registration and conflict detection
- File locking mechanism
- Dependency graph management
- Execution order optimization
- Auto-recovery from failures
- Resource management

Uses mocked agents and database for deterministic testing.
"""

import unittest
import asyncio
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timedelta

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class TestAgentCoordinatorInitialization(unittest.TestCase):
    """Test AgentCoordinator initialization and basic state."""

    def test_coordinator_singleton(self):
        """Test that get_coordinator returns a singleton instance."""
        from core.agents.coordinator import get_coordinator

        coord1 = get_coordinator()
        coord2 = get_coordinator()

        self.assertIs(coord1, coord2)

    def test_coordinator_initialization(self):
        """Test coordinator initializes with empty state."""
        from core.agents.coordinator import AgentCoordinator

        coord = AgentCoordinator()

        self.assertEqual(coord.active_agents, {})
        self.assertEqual(coord.file_locks, {})
        self.assertEqual(coord.dependency_graph, {})

    def test_max_concurrent_agents_constant(self):
        """Test MAX_CONCURRENT_AGENTS is defined."""
        from core.agents.coordinator import AgentCoordinator

        self.assertTrue(hasattr(AgentCoordinator, 'MAX_CONCURRENT_AGENTS'))
        self.assertIsInstance(AgentCoordinator.MAX_CONCURRENT_AGENTS, int)
        self.assertGreater(AgentCoordinator.MAX_CONCURRENT_AGENTS, 0)

    def test_lock_timeout_constant(self):
        """Test LOCK_TIMEOUT_SECONDS is defined."""
        from core.agents.coordinator import AgentCoordinator

        self.assertTrue(hasattr(AgentCoordinator, 'LOCK_TIMEOUT_SECONDS'))
        self.assertIsInstance(AgentCoordinator.LOCK_TIMEOUT_SECONDS, (int, float))
        self.assertGreater(AgentCoordinator.LOCK_TIMEOUT_SECONDS, 0)


class TestAgentRegistration(unittest.TestCase):
    """Test agent registration and tracking."""

    def setUp(self):
        """Set up fresh coordinator for each test."""
        from core.agents.coordinator import AgentCoordinator
        self.coord = AgentCoordinator()

    def test_register_agent(self):
        """Test registering a new agent."""
        task_info = {
            "task_id": "test-task-1",
            "description": "Test task",
            "files": ["src/module.py"],
        }

        result = self.coord.register_agent("agent-1", task_info)

        self.assertTrue(result)
        self.assertIn("agent-1", self.coord.active_agents)
        self.assertEqual(self.coord.active_agents["agent-1"]["task_id"], "test-task-1")

    def test_register_agent_tracks_timestamp(self):
        """Test that registration tracks start time."""
        task_info = {"task_id": "task-1", "description": "Test"}

        before = time.time()
        self.coord.register_agent("agent-1", task_info)
        after = time.time()

        registered_at = self.coord.active_agents["agent-1"]["registered_at"]
        self.assertGreaterEqual(registered_at, before)
        self.assertLessEqual(registered_at, after)

    def test_register_duplicate_agent(self):
        """Test registering duplicate agent ID fails."""
        task_info = {"task_id": "task-1", "description": "Test"}

        self.coord.register_agent("agent-1", task_info)
        result = self.coord.register_agent("agent-1", {"task_id": "task-2"})

        self.assertFalse(result)

    def test_unregister_agent(self):
        """Test unregistering an agent."""
        task_info = {"task_id": "task-1", "description": "Test"}
        self.coord.register_agent("agent-1", task_info)

        result = self.coord.unregister_agent("agent-1")

        self.assertTrue(result)
        self.assertNotIn("agent-1", self.coord.active_agents)

    def test_unregister_nonexistent_agent(self):
        """Test unregistering non-existent agent."""
        result = self.coord.unregister_agent("nonexistent")

        self.assertFalse(result)

    def test_get_active_agents(self):
        """Test getting list of active agents."""
        self.coord.register_agent("agent-1", {"task_id": "t1"})
        self.coord.register_agent("agent-2", {"task_id": "t2"})

        agents = self.coord.get_active_agents()

        self.assertEqual(len(agents), 2)
        self.assertIn("agent-1", agents)
        self.assertIn("agent-2", agents)


class TestFileConflictDetection(unittest.TestCase):
    """Test file conflict detection and prevention."""

    def setUp(self):
        """Set up fresh coordinator."""
        from core.agents.coordinator import AgentCoordinator
        self.coord = AgentCoordinator()

    def test_check_file_conflict_no_conflict(self):
        """Test no conflict when file is not locked."""
        result = self.coord.check_file_conflict("agent-1", "src/new_file.py")

        self.assertFalse(result)

    def test_check_file_conflict_with_conflict(self):
        """Test conflict detected when file is locked by another agent."""
        self.coord.acquire_file_lock("agent-1", "src/module.py")

        result = self.coord.check_file_conflict("agent-2", "src/module.py")

        self.assertTrue(result)

    def test_check_file_conflict_same_agent(self):
        """Test no conflict when same agent checks its own lock."""
        self.coord.acquire_file_lock("agent-1", "src/module.py")

        result = self.coord.check_file_conflict("agent-1", "src/module.py")

        self.assertFalse(result)

    def test_acquire_file_lock(self):
        """Test acquiring a file lock."""
        result = self.coord.acquire_file_lock("agent-1", "src/module.py")

        self.assertTrue(result)
        self.assertIn("src/module.py", self.coord.file_locks)
        self.assertEqual(self.coord.file_locks["src/module.py"]["agent_id"], "agent-1")

    def test_acquire_file_lock_already_locked(self):
        """Test acquiring lock on already locked file fails."""
        self.coord.acquire_file_lock("agent-1", "src/module.py")

        result = self.coord.acquire_file_lock("agent-2", "src/module.py")

        self.assertFalse(result)

    def test_acquire_file_lock_with_operation(self):
        """Test acquiring lock with operation type."""
        result = self.coord.acquire_file_lock("agent-1", "src/module.py", operation="write")

        self.assertTrue(result)
        self.assertEqual(self.coord.file_locks["src/module.py"]["operation"], "write")

    def test_release_file_lock(self):
        """Test releasing a file lock."""
        self.coord.acquire_file_lock("agent-1", "src/module.py")

        result = self.coord.release_file_lock("agent-1", "src/module.py")

        self.assertTrue(result)
        self.assertNotIn("src/module.py", self.coord.file_locks)

    def test_release_file_lock_wrong_agent(self):
        """Test releasing lock by wrong agent fails."""
        self.coord.acquire_file_lock("agent-1", "src/module.py")

        result = self.coord.release_file_lock("agent-2", "src/module.py")

        self.assertFalse(result)
        self.assertIn("src/module.py", self.coord.file_locks)

    def test_release_all_locks_for_agent(self):
        """Test releasing all locks held by an agent."""
        self.coord.acquire_file_lock("agent-1", "src/file1.py")
        self.coord.acquire_file_lock("agent-1", "src/file2.py")
        self.coord.acquire_file_lock("agent-2", "src/file3.py")

        count = self.coord.release_all_locks("agent-1")

        self.assertEqual(count, 2)
        self.assertNotIn("src/file1.py", self.coord.file_locks)
        self.assertNotIn("src/file2.py", self.coord.file_locks)
        self.assertIn("src/file3.py", self.coord.file_locks)

    def test_get_locked_files(self):
        """Test getting list of locked files."""
        self.coord.acquire_file_lock("agent-1", "src/file1.py")
        self.coord.acquire_file_lock("agent-2", "src/file2.py")

        locked = self.coord.get_locked_files()

        self.assertEqual(len(locked), 2)
        self.assertIn("src/file1.py", locked)
        self.assertIn("src/file2.py", locked)

    def test_get_locks_by_agent(self):
        """Test getting locks held by specific agent."""
        self.coord.acquire_file_lock("agent-1", "src/file1.py")
        self.coord.acquire_file_lock("agent-1", "src/file2.py")
        self.coord.acquire_file_lock("agent-2", "src/file3.py")

        locks = self.coord.get_locks_by_agent("agent-1")

        self.assertEqual(len(locks), 2)
        self.assertIn("src/file1.py", locks)
        self.assertIn("src/file2.py", locks)


class TestDependencyManagement(unittest.TestCase):
    """Test dependency graph management."""

    def setUp(self):
        """Set up fresh coordinator."""
        from core.agents.coordinator import AgentCoordinator
        self.coord = AgentCoordinator()

    def test_add_dependency(self):
        """Test adding a dependency between agents."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        self.coord.register_agent("agent-b", {"task_id": "tb"})

        result = self.coord.add_dependency("agent-b", "agent-a")  # b depends on a

        self.assertTrue(result)
        self.assertIn("agent-b", self.coord.dependency_graph)
        self.assertIn("agent-a", self.coord.dependency_graph["agent-b"])

    def test_add_dependency_nonexistent_agent(self):
        """Test adding dependency with non-existent agent fails."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})

        result = self.coord.add_dependency("agent-b", "agent-a")

        self.assertFalse(result)

    def test_check_dependencies_satisfied(self):
        """Test checking if dependencies are satisfied."""
        self.coord.register_agent("agent-a", {"task_id": "ta", "status": "completed"})
        self.coord.register_agent("agent-b", {"task_id": "tb"})
        self.coord.add_dependency("agent-b", "agent-a")

        # Mark agent-a as completed
        self.coord.active_agents["agent-a"]["status"] = "completed"

        result = self.coord.check_dependencies("agent-b")

        self.assertEqual(result, [])  # No unsatisfied dependencies

    def test_check_dependencies_unsatisfied(self):
        """Test checking unsatisfied dependencies."""
        self.coord.register_agent("agent-a", {"task_id": "ta", "status": "running"})
        self.coord.register_agent("agent-b", {"task_id": "tb"})
        self.coord.add_dependency("agent-b", "agent-a")

        result = self.coord.check_dependencies("agent-b")

        self.assertEqual(result, ["agent-a"])

    def test_check_dependencies_multiple(self):
        """Test checking multiple dependencies."""
        self.coord.register_agent("agent-a", {"task_id": "ta", "status": "running"})
        self.coord.register_agent("agent-b", {"task_id": "tb", "status": "running"})
        self.coord.register_agent("agent-c", {"task_id": "tc"})
        self.coord.add_dependency("agent-c", "agent-a")
        self.coord.add_dependency("agent-c", "agent-b")

        result = self.coord.check_dependencies("agent-c")

        self.assertEqual(len(result), 2)
        self.assertIn("agent-a", result)
        self.assertIn("agent-b", result)

    def test_detect_circular_dependency(self):
        """Test detection of circular dependencies."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        self.coord.register_agent("agent-b", {"task_id": "tb"})
        self.coord.add_dependency("agent-b", "agent-a")

        # Try to create circular dependency
        result = self.coord.add_dependency("agent-a", "agent-b")

        self.assertFalse(result)  # Should reject circular dependency


class TestExecutionOrderOptimization(unittest.TestCase):
    """Test execution order optimization."""

    def setUp(self):
        """Set up fresh coordinator."""
        from core.agents.coordinator import AgentCoordinator
        self.coord = AgentCoordinator()

    def test_optimize_execution_order_no_deps(self):
        """Test optimization with no dependencies."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        self.coord.register_agent("agent-b", {"task_id": "tb"})

        order = self.coord.optimize_execution_order()

        self.assertEqual(len(order), 2)
        self.assertIn("agent-a", order)
        self.assertIn("agent-b", order)

    def test_optimize_execution_order_with_deps(self):
        """Test optimization respects dependencies."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        self.coord.register_agent("agent-b", {"task_id": "tb"})
        self.coord.register_agent("agent-c", {"task_id": "tc"})
        self.coord.add_dependency("agent-b", "agent-a")  # b depends on a
        self.coord.add_dependency("agent-c", "agent-b")  # c depends on b

        order = self.coord.optimize_execution_order()

        # a should come before b, b should come before c
        self.assertLess(order.index("agent-a"), order.index("agent-b"))
        self.assertLess(order.index("agent-b"), order.index("agent-c"))

    def test_optimize_execution_order_complex(self):
        """Test optimization with complex dependency graph."""
        #    a   b
        #   / \ /
        #  c   d
        #   \ /
        #    e
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        self.coord.register_agent("agent-b", {"task_id": "tb"})
        self.coord.register_agent("agent-c", {"task_id": "tc"})
        self.coord.register_agent("agent-d", {"task_id": "td"})
        self.coord.register_agent("agent-e", {"task_id": "te"})

        self.coord.add_dependency("agent-c", "agent-a")
        self.coord.add_dependency("agent-d", "agent-a")
        self.coord.add_dependency("agent-d", "agent-b")
        self.coord.add_dependency("agent-e", "agent-c")
        self.coord.add_dependency("agent-e", "agent-d")

        order = self.coord.optimize_execution_order()

        # a and b should come first (no deps)
        # c and d should come after a (and b for d)
        # e should come last
        self.assertLess(order.index("agent-a"), order.index("agent-c"))
        self.assertLess(order.index("agent-a"), order.index("agent-d"))
        self.assertLess(order.index("agent-b"), order.index("agent-d"))
        self.assertLess(order.index("agent-c"), order.index("agent-e"))
        self.assertLess(order.index("agent-d"), order.index("agent-e"))


class TestConflictDetection(unittest.TestCase):
    """Test conflict detection and resolution."""

    def setUp(self):
        """Set up fresh coordinator."""
        from core.agents.coordinator import AgentCoordinator
        self.coord = AgentCoordinator()

    def test_detect_conflicts_none(self):
        """Test no conflicts detected when none exist."""
        self.coord.register_agent("agent-a", {"task_id": "ta", "files": ["src/a.py"]})
        self.coord.register_agent("agent-b", {"task_id": "tb", "files": ["src/b.py"]})

        conflicts = self.coord.detect_conflicts()

        self.assertEqual(len(conflicts), 0)

    def test_detect_conflicts_file_overlap(self):
        """Test detection of file overlap conflicts."""
        self.coord.register_agent("agent-a", {"task_id": "ta", "files": ["src/shared.py"]})
        self.coord.register_agent("agent-b", {"task_id": "tb", "files": ["src/shared.py"]})

        conflicts = self.coord.detect_conflicts()

        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["type"], "file_overlap")
        self.assertIn("agent-a", conflicts[0]["agents"])
        self.assertIn("agent-b", conflicts[0]["agents"])

    def test_detect_conflicts_duplicate_task(self):
        """Test detection of duplicate task conflicts."""
        self.coord.register_agent("agent-a", {"task_id": "task-1", "description": "Do X"})
        self.coord.register_agent("agent-b", {"task_id": "task-1", "description": "Do X"})

        conflicts = self.coord.detect_conflicts()

        self.assertTrue(any(c["type"] == "duplicate_task" for c in conflicts))

    def test_resolve_conflict_file_edit(self):
        """Test resolution strategy for file edit conflicts."""
        from core.agents.coordinator import ConflictType

        conflict = {
            "type": ConflictType.FILE_EDIT,
            "agents": ["agent-a", "agent-b"],
            "file": "src/shared.py",
        }

        resolution = self.coord.resolve_conflict(conflict)

        self.assertEqual(resolution["strategy"], "serialize")
        self.assertIn("queue", resolution)

    def test_resolve_conflict_duplicate_task(self):
        """Test resolution strategy for duplicate tasks."""
        from core.agents.coordinator import ConflictType

        conflict = {
            "type": ConflictType.DUPLICATE_TASK,
            "agents": ["agent-a", "agent-b"],
            "task_id": "task-1",
        }

        resolution = self.coord.resolve_conflict(conflict)

        self.assertEqual(resolution["strategy"], "cancel_duplicate")
        self.assertIn("keep", resolution)
        self.assertIn("cancel", resolution)


class TestAutoRecovery(unittest.TestCase):
    """Test auto-recovery from failures."""

    def setUp(self):
        """Set up fresh coordinator."""
        from core.agents.coordinator import AgentCoordinator
        self.coord = AgentCoordinator()

    def test_mark_agent_failed(self):
        """Test marking an agent as failed."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})

        self.coord.mark_agent_failed("agent-a", "Connection timeout")

        self.assertEqual(self.coord.active_agents["agent-a"]["status"], "failed")
        self.assertEqual(self.coord.active_agents["agent-a"]["error"], "Connection timeout")

    def test_recover_failed_agent_retry(self):
        """Test recovering failed agent with retry strategy."""
        self.coord.register_agent("agent-a", {"task_id": "ta", "retry_count": 0})
        self.coord.mark_agent_failed("agent-a", "Temporary error")

        result = self.coord.recover_failed_agent("agent-a")

        self.assertEqual(result["strategy"], "retry")
        self.assertEqual(self.coord.active_agents["agent-a"]["retry_count"], 1)

    def test_recover_failed_agent_max_retries(self):
        """Test recovery after max retries exceeded."""
        from core.agents.coordinator import AgentCoordinator

        self.coord.register_agent("agent-a", {
            "task_id": "ta",
            "retry_count": AgentCoordinator.MAX_RETRIES,
        })
        self.coord.mark_agent_failed("agent-a", "Persistent error")

        result = self.coord.recover_failed_agent("agent-a")

        self.assertEqual(result["strategy"], "abandon")

    def test_recover_failed_agent_releases_locks(self):
        """Test that recovery releases locks held by failed agent."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        self.coord.acquire_file_lock("agent-a", "src/file.py")
        self.coord.mark_agent_failed("agent-a", "Error")

        self.coord.recover_failed_agent("agent-a")

        self.assertNotIn("src/file.py", self.coord.file_locks)

    def test_cleanup_stale_agents(self):
        """Test cleanup of stale agents."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        # Manually set old timestamp
        self.coord.active_agents["agent-a"]["last_heartbeat"] = time.time() - 3600

        count = self.coord.cleanup_stale_agents(max_age_seconds=300)

        self.assertEqual(count, 1)
        self.assertNotIn("agent-a", self.coord.active_agents)


class TestResourceManagement(unittest.TestCase):
    """Test resource management and limits."""

    def setUp(self):
        """Set up fresh coordinator."""
        from core.agents.coordinator import AgentCoordinator
        self.coord = AgentCoordinator()

    def test_can_accept_agent_under_limit(self):
        """Test accepting agent when under limit."""
        result = self.coord.can_accept_agent()

        self.assertTrue(result)

    def test_can_accept_agent_at_limit(self):
        """Test rejecting agent when at limit."""
        from core.agents.coordinator import AgentCoordinator

        # Fill up to limit
        for i in range(AgentCoordinator.MAX_CONCURRENT_AGENTS):
            self.coord.register_agent(f"agent-{i}", {"task_id": f"t{i}"})

        result = self.coord.can_accept_agent()

        self.assertFalse(result)

    def test_get_resource_usage(self):
        """Test getting resource usage stats."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        self.coord.acquire_file_lock("agent-a", "src/file.py")

        usage = self.coord.get_resource_usage()

        self.assertEqual(usage["active_agents"], 1)
        self.assertEqual(usage["file_locks"], 1)
        self.assertIn("capacity_percent", usage)

    def test_agent_heartbeat(self):
        """Test agent heartbeat updates timestamp."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        original_heartbeat = self.coord.active_agents["agent-a"]["last_heartbeat"]

        time.sleep(0.1)
        self.coord.heartbeat("agent-a")

        new_heartbeat = self.coord.active_agents["agent-a"]["last_heartbeat"]
        self.assertGreater(new_heartbeat, original_heartbeat)


class TestCoordinatorStatus(unittest.TestCase):
    """Test coordinator status reporting."""

    def setUp(self):
        """Set up fresh coordinator."""
        from core.agents.coordinator import AgentCoordinator
        self.coord = AgentCoordinator()

    def test_get_status_empty(self):
        """Test status with no agents."""
        status = self.coord.get_status()

        self.assertEqual(status["active_agents"], 0)
        self.assertEqual(status["file_locks"], 0)
        self.assertEqual(status["conflicts"], 0)

    def test_get_status_with_agents(self):
        """Test status with active agents."""
        self.coord.register_agent("agent-a", {"task_id": "ta"})
        self.coord.register_agent("agent-b", {"task_id": "tb"})
        self.coord.acquire_file_lock("agent-a", "src/file.py")

        status = self.coord.get_status()

        self.assertEqual(status["active_agents"], 2)
        self.assertEqual(status["file_locks"], 1)

    def test_get_agent_status(self):
        """Test getting individual agent status."""
        self.coord.register_agent("agent-a", {"task_id": "ta", "description": "Test"})
        self.coord.acquire_file_lock("agent-a", "src/file.py")

        status = self.coord.get_agent_status("agent-a")

        self.assertIsNotNone(status)
        self.assertEqual(status["task_id"], "ta")
        self.assertEqual(len(status["locks"]), 1)


class TestAsyncOperations(unittest.TestCase):
    """Test async coordinator operations."""

    def setUp(self):
        """Set up fresh coordinator."""
        from core.agents.coordinator import AgentCoordinator
        self.coord = AgentCoordinator()

    def test_async_register_agent(self):
        """Test async agent registration."""
        async def run_test():
            result = await self.coord.async_register_agent("agent-a", {"task_id": "ta"})
            self.assertTrue(result)
            self.assertIn("agent-a", self.coord.active_agents)

        asyncio.run(run_test())

    def test_async_acquire_file_lock(self):
        """Test async file lock acquisition."""
        async def run_test():
            result = await self.coord.async_acquire_file_lock("agent-a", "src/file.py")
            self.assertTrue(result)
            self.assertIn("src/file.py", self.coord.file_locks)

        asyncio.run(run_test())

    def test_async_wait_for_dependencies(self):
        """Test async waiting for dependencies."""
        async def run_test():
            self.coord.register_agent("agent-a", {"task_id": "ta", "status": "running"})
            self.coord.register_agent("agent-b", {"task_id": "tb"})
            self.coord.add_dependency("agent-b", "agent-a")

            # Complete agent-a in background
            async def complete_a():
                await asyncio.sleep(0.1)
                self.coord.active_agents["agent-a"]["status"] = "completed"

            asyncio.create_task(complete_a())

            # Wait for dependencies (should complete when a finishes)
            result = await self.coord.async_wait_for_dependencies("agent-b", timeout=1.0)
            self.assertTrue(result)

        asyncio.run(run_test())


if __name__ == '__main__':
    unittest.main()
