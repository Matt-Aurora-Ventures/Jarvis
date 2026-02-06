"""
Tests for cleanup management module.

Verifies:
- Cleanup handler registration
- Cleanup execution order
- Resource cleanup (connections, logs, state)
- Error handling during cleanup
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock


class TestCleanupManager:
    """Test CleanupManager class functionality."""

    def test_import_cleanup_manager(self):
        """Test that CleanupManager can be imported."""
        from core.lifecycle.cleanup import CleanupManager
        assert CleanupManager is not None

    def test_cleanup_manager_init(self):
        """Test CleanupManager initialization."""
        from core.lifecycle.cleanup import CleanupManager

        manager = CleanupManager()
        assert manager is not None
        assert len(manager.get_registered_cleanups()) == 0

    def test_register_cleanup(self):
        """Test registering a cleanup function."""
        from core.lifecycle.cleanup import CleanupManager

        manager = CleanupManager()

        async def cleanup_fn():
            pass

        manager.register_cleanup(cleanup_fn, name="test_cleanup")

        cleanups = manager.get_registered_cleanups()
        assert len(cleanups) == 1
        assert cleanups[0]["name"] == "test_cleanup"

    def test_register_cleanup_with_priority(self):
        """Test registering cleanup with priority."""
        from core.lifecycle.cleanup import CleanupManager

        manager = CleanupManager()

        async def high_priority():
            pass

        async def low_priority():
            pass

        manager.register_cleanup(low_priority, name="low", priority=1)
        manager.register_cleanup(high_priority, name="high", priority=100)

        cleanups = manager.get_registered_cleanups()
        # High priority should be first
        assert cleanups[0]["name"] == "high"
        assert cleanups[1]["name"] == "low"

    @pytest.mark.asyncio
    async def test_run_cleanup(self):
        """Test running all cleanups."""
        from core.lifecycle.cleanup import CleanupManager

        manager = CleanupManager()
        executed = []

        async def cleanup1():
            executed.append("cleanup1")

        async def cleanup2():
            executed.append("cleanup2")

        manager.register_cleanup(cleanup1, name="cleanup1")
        manager.register_cleanup(cleanup2, name="cleanup2")

        results = await manager.run_cleanup()

        assert len(executed) == 2
        assert results.success
        assert results.completed_count == 2

    @pytest.mark.asyncio
    async def test_run_cleanup_order(self):
        """Test cleanups run in priority order."""
        from core.lifecycle.cleanup import CleanupManager

        manager = CleanupManager()
        execution_order = []

        async def first():
            execution_order.append("first")

        async def second():
            execution_order.append("second")

        async def third():
            execution_order.append("third")

        manager.register_cleanup(third, name="third", priority=1)
        manager.register_cleanup(first, name="first", priority=100)
        manager.register_cleanup(second, name="second", priority=50)

        await manager.run_cleanup()

        assert execution_order == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_cleanup_error_handling(self):
        """Test that errors in cleanup don't stop other cleanups."""
        from core.lifecycle.cleanup import CleanupManager

        manager = CleanupManager()
        executed = []

        async def failing_cleanup():
            executed.append("failing")
            raise RuntimeError("Cleanup failed")

        async def succeeding_cleanup():
            executed.append("succeeding")

        manager.register_cleanup(failing_cleanup, name="failing", priority=100)
        manager.register_cleanup(succeeding_cleanup, name="succeeding", priority=1)

        results = await manager.run_cleanup()

        # Both should have been attempted
        assert "failing" in executed
        assert "succeeding" in executed
        assert results.failed_count == 1
        assert results.completed_count == 1

    @pytest.mark.asyncio
    async def test_cleanup_timeout(self):
        """Test that slow cleanups are timed out."""
        from core.lifecycle.cleanup import CleanupManager

        manager = CleanupManager()

        async def slow_cleanup():
            await asyncio.sleep(10)  # Will timeout

        manager.register_cleanup(slow_cleanup, name="slow", timeout=0.1)

        results = await manager.run_cleanup()

        assert results.timed_out_count == 1

    @pytest.mark.asyncio
    async def test_unregister_cleanup(self):
        """Test unregistering a cleanup."""
        from core.lifecycle.cleanup import CleanupManager

        manager = CleanupManager()

        async def cleanup_fn():
            pass

        manager.register_cleanup(cleanup_fn, name="to_remove")
        assert len(manager.get_registered_cleanups()) == 1

        manager.unregister_cleanup("to_remove")
        assert len(manager.get_registered_cleanups()) == 0


class TestCleanupTypes:
    """Test specific cleanup types."""

    @pytest.mark.asyncio
    async def test_close_connections_cleanup(self):
        """Test cleanup closes database connections."""
        from core.lifecycle.cleanup import CleanupManager, close_connections

        manager = CleanupManager()

        # Mock connection
        mock_conn = AsyncMock()
        mock_conn.close = AsyncMock()

        connections = [mock_conn]

        manager.register_cleanup(
            lambda: close_connections(connections),
            name="connections"
        )

        await manager.run_cleanup()

        mock_conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_flush_logs_cleanup(self):
        """Test cleanup flushes log handlers."""
        from core.lifecycle.cleanup import CleanupManager, flush_logs

        manager = CleanupManager()

        # Mock logger
        mock_handler = Mock()
        mock_handler.flush = Mock()

        with patch('logging.root.handlers', [mock_handler]):
            manager.register_cleanup(flush_logs, name="logs")
            await manager.run_cleanup()

            mock_handler.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_state_cleanup(self):
        """Test cleanup saves application state."""
        from core.lifecycle.cleanup import CleanupManager, save_state

        manager = CleanupManager()
        state = {"key": "value"}
        save_path = "/tmp/test_state.json"

        with patch('builtins.open', Mock()) as mock_open:
            with patch('json.dump') as mock_dump:
                manager.register_cleanup(
                    lambda: save_state(state, save_path),
                    name="state"
                )
                await manager.run_cleanup()


class TestCleanupResult:
    """Test CleanupResult data structure."""

    def test_import_cleanup_result(self):
        """Test that CleanupResult can be imported."""
        from core.lifecycle.cleanup import CleanupResult
        assert CleanupResult is not None

    def test_cleanup_result_success(self):
        """Test CleanupResult for successful cleanup."""
        from core.lifecycle.cleanup import CleanupResult

        result = CleanupResult(
            success=True,
            completed_count=3,
            failed_count=0,
            timed_out_count=0,
            duration_ms=150.0,
            details=[],
        )

        assert result.success
        assert result.total_count == 3

    def test_cleanup_result_partial_failure(self):
        """Test CleanupResult for partial failure."""
        from core.lifecycle.cleanup import CleanupResult

        result = CleanupResult(
            success=False,
            completed_count=2,
            failed_count=1,
            timed_out_count=0,
            duration_ms=200.0,
            details=[{"name": "failed", "error": "test"}],
        )

        assert not result.success
        assert result.total_count == 3


class TestGetCleanupManager:
    """Test global cleanup manager singleton."""

    def test_get_cleanup_manager(self):
        """Test getting the global cleanup manager."""
        from core.lifecycle.cleanup import get_cleanup_manager

        manager1 = get_cleanup_manager()
        manager2 = get_cleanup_manager()

        assert manager1 is manager2

    def test_cleanup_manager_different_instances(self):
        """Test creating separate CleanupManager instances."""
        from core.lifecycle.cleanup import CleanupManager

        manager1 = CleanupManager()
        manager2 = CleanupManager()

        assert manager1 is not manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
