"""
Tests for graceful shutdown manager.

Verifies:
- Shutdown hooks execute in correct order
- Timeouts are respected
- Signal handling works correctly
- Database connections close properly
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from core.shutdown_manager import (
    ShutdownManager,
    ShutdownPhase,
    ShutdownAwareService,
    DatabaseShutdownMixin,
    TaskManagerMixin,
)


class TestShutdownManager:
    """Test core shutdown manager functionality."""

    @pytest.mark.asyncio
    async def test_hook_registration(self):
        """Test that hooks can be registered."""
        manager = ShutdownManager()

        async def dummy_hook():
            pass

        manager.register_hook(
            name="test_hook",
            callback=dummy_hook,
            phase=ShutdownPhase.GRACEFUL,
        )

        assert len(manager.hooks) == 1
        assert manager.hooks[0].name == "test_hook"
        assert manager.hooks[0].phase == ShutdownPhase.GRACEFUL

    @pytest.mark.asyncio
    async def test_hook_execution_order(self):
        """Test that hooks execute in phase order."""
        manager = ShutdownManager()
        execution_order = []

        async def immediate_hook():
            execution_order.append("immediate")

        async def graceful_hook():
            execution_order.append("graceful")

        async def cleanup_hook():
            execution_order.append("cleanup")

        # Register in reverse order
        manager.register_hook("cleanup", cleanup_hook, ShutdownPhase.CLEANUP)
        manager.register_hook("graceful", graceful_hook, ShutdownPhase.GRACEFUL)
        manager.register_hook("immediate", immediate_hook, ShutdownPhase.IMMEDIATE)

        await manager.shutdown()

        # Should execute in phase order regardless of registration order
        assert execution_order == ["immediate", "graceful", "cleanup"]

    @pytest.mark.asyncio
    async def test_priority_within_phase(self):
        """Test that priority determines order within a phase."""
        manager = ShutdownManager()
        execution_order = []

        async def low_priority():
            execution_order.append("low")

        async def high_priority():
            execution_order.append("high")

        async def medium_priority():
            execution_order.append("medium")

        # Register with different priorities
        manager.register_hook("low", low_priority, ShutdownPhase.GRACEFUL, priority=1)
        manager.register_hook("high", high_priority, ShutdownPhase.GRACEFUL, priority=100)
        manager.register_hook("medium", medium_priority, ShutdownPhase.GRACEFUL, priority=50)

        await manager.shutdown()

        # Should execute high priority first
        assert execution_order == ["high", "medium", "low"]

    @pytest.mark.asyncio
    async def test_hook_timeout(self):
        """Test that slow hooks are timed out."""
        manager = ShutdownManager()

        async def slow_hook():
            await asyncio.sleep(10)  # Will timeout

        manager.register_hook("slow", slow_hook, ShutdownPhase.GRACEFUL, timeout=0.1)

        # Should not raise, just log timeout
        await manager.shutdown()

        # Shutdown should complete despite timeout
        assert manager._shutdown_complete

    @pytest.mark.asyncio
    async def test_hook_error_handling(self):
        """Test that errors in hooks don't stop shutdown."""
        manager = ShutdownManager()
        execution_order = []

        async def failing_hook():
            execution_order.append("failing")
            raise RuntimeError("Hook failed")

        async def succeeding_hook():
            execution_order.append("succeeding")

        manager.register_hook("failing", failing_hook, ShutdownPhase.GRACEFUL)
        manager.register_hook("succeeding", succeeding_hook, ShutdownPhase.GRACEFUL)

        # Should not raise
        await manager.shutdown()

        # Both hooks should have been called
        assert "failing" in execution_order
        assert "succeeding" in execution_order

    @pytest.mark.asyncio
    async def test_multiple_shutdown_calls(self):
        """Test that multiple shutdown calls are safe."""
        manager = ShutdownManager()
        call_count = 0

        async def counting_hook():
            nonlocal call_count
            call_count += 1

        manager.register_hook("counter", counting_hook, ShutdownPhase.GRACEFUL)

        # Call shutdown multiple times
        await manager.shutdown()
        await manager.shutdown()
        await manager.shutdown()

        # Hook should only execute once
        assert call_count == 1


class TestShutdownAwareService:
    """Test the ShutdownAwareService base class."""

    @pytest.mark.asyncio
    async def test_service_lifecycle(self):
        """Test service start and shutdown."""

        class TestService(ShutdownAwareService):
            def __init__(self):
                super().__init__(name="test_service")
                self.started = False
                self.shutdown_called = False

            async def _startup(self):
                self.started = True

            async def _shutdown(self):
                self.shutdown_called = True

        service = TestService()
        await service.start()

        assert service.started
        assert service._running

        await service._shutdown_hook()

        assert service.shutdown_called
        assert not service._running

    @pytest.mark.asyncio
    async def test_service_double_start_error(self):
        """Test that starting a service twice raises an error."""

        class TestService(ShutdownAwareService):
            async def _startup(self):
                pass

        service = TestService("test")
        await service.start()

        with pytest.raises(RuntimeError, match="already running"):
            await service.start()


class TestDatabaseShutdownMixin:
    """Test database connection cleanup."""

    @pytest.mark.asyncio
    async def test_connection_cleanup(self):
        """Test that database connections are closed on shutdown."""

        class TestService(DatabaseShutdownMixin, ShutdownAwareService):
            def __init__(self):
                super().__init__(name="db_service")

        service = TestService()

        # Mock database connections
        conn1 = AsyncMock()
        conn2 = AsyncMock()

        service.register_db_connection(conn1)
        service.register_db_connection(conn2)

        await service._close_db_connections()

        # Both connections should be closed
        conn1.close.assert_called_once()
        conn2.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_close_method(self):
        """Test connections with async close methods."""

        class TestService(DatabaseShutdownMixin, ShutdownAwareService):
            def __init__(self):
                super().__init__(name="db_service")

        service = TestService()

        # Mock connection with aclose
        conn = Mock()
        conn.aclose = AsyncMock()

        service.register_db_connection(conn)
        await service._close_db_connections()

        conn.aclose.assert_called_once()


class TestTaskManagerMixin:
    """Test background task management."""

    @pytest.mark.asyncio
    async def test_task_cancellation(self):
        """Test that background tasks are cancelled on shutdown."""

        class TestService(TaskManagerMixin, ShutdownAwareService):
            def __init__(self):
                super().__init__(name="task_service")

        service = TestService()

        # Create a long-running task
        async def long_task():
            await asyncio.sleep(100)

        task = service.create_task(long_task(), name="long_task")

        # Task should be running
        assert not task.done()

        # Cancel tasks
        await service._cancel_background_tasks(timeout=0.5)

        # Task should be cancelled
        assert task.cancelled() or task.done()

    @pytest.mark.asyncio
    async def test_multiple_task_cancellation(self):
        """Test cancelling multiple background tasks."""

        class TestService(TaskManagerMixin, ShutdownAwareService):
            def __init__(self):
                super().__init__(name="task_service")

        service = TestService()

        async def dummy_task():
            await asyncio.sleep(100)

        # Create multiple tasks
        tasks = [
            service.create_task(dummy_task(), name=f"task_{i}")
            for i in range(5)
        ]

        # All should be running
        assert all(not t.done() for t in tasks)

        # Cancel all
        await service._cancel_background_tasks(timeout=0.5)

        # All should be cancelled or done
        assert all(t.cancelled() or t.done() for t in tasks)


class TestSignalHandling:
    """Test signal handling integration."""

    def test_signal_handler_installation(self):
        """Test that signal handlers can be installed."""
        manager = ShutdownManager()

        # Should not raise
        manager.install_signal_handlers()

        assert manager._signal_handlers_installed

    def test_double_installation_warning(self):
        """Test that double installation is safe."""
        manager = ShutdownManager()

        manager.install_signal_handlers()
        # Second call should log warning but not crash
        manager.install_signal_handlers()


class TestShutdownIntegration:
    """Integration tests for complete shutdown flows."""

    @pytest.mark.asyncio
    async def test_complete_shutdown_flow(self):
        """Test a complete shutdown with multiple components."""
        manager = ShutdownManager()

        # Simulate multiple components
        db_closed = False
        tasks_cancelled = False
        state_saved = False

        async def close_db():
            nonlocal db_closed
            db_closed = True

        async def cancel_tasks():
            nonlocal tasks_cancelled
            tasks_cancelled = True

        async def save_state():
            nonlocal state_saved
            state_saved = True

        # Register in different phases
        manager.register_hook("save_state", save_state, ShutdownPhase.PERSIST)
        manager.register_hook("cancel_tasks", cancel_tasks, ShutdownPhase.GRACEFUL)
        manager.register_hook("close_db", close_db, ShutdownPhase.CLEANUP)

        await manager.shutdown()

        # All should have executed
        assert tasks_cancelled
        assert state_saved
        assert db_closed

    @pytest.mark.asyncio
    async def test_timeout_doesnt_block_shutdown(self):
        """Test that timeouts don't prevent shutdown completion."""
        manager = ShutdownManager(shutdown_timeout=5.0)

        completed_hooks = []

        async def fast_hook():
            completed_hooks.append("fast")

        async def slow_hook():
            await asyncio.sleep(10)  # Will timeout
            completed_hooks.append("slow")

        async def another_fast_hook():
            completed_hooks.append("another_fast")

        manager.register_hook("fast", fast_hook, ShutdownPhase.GRACEFUL, timeout=1.0)
        manager.register_hook("slow", slow_hook, ShutdownPhase.GRACEFUL, timeout=0.1)
        manager.register_hook("another", another_fast_hook, ShutdownPhase.GRACEFUL, timeout=1.0)

        start = datetime.now()
        await manager.shutdown()
        elapsed = (datetime.now() - start).total_seconds()

        # Should complete quickly despite slow hook
        assert elapsed < 3.0

        # Fast hooks should complete, slow should timeout
        assert "fast" in completed_hooks
        assert "another_fast" in completed_hooks
        assert "slow" not in completed_hooks  # Timed out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
