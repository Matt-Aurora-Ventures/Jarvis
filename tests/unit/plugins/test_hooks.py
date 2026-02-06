"""Tests for core/plugins/hooks.py - Hook system for plugins."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import Dict, Any


class TestHookPoints:
    """Tests for hook point constants."""

    def test_hook_points_defined(self):
        """Standard hook points should be defined."""
        from core.plugins.hooks import HookPoint

        assert HookPoint.PRE_MESSAGE is not None
        assert HookPoint.POST_MESSAGE is not None
        assert HookPoint.ON_ERROR is not None
        assert HookPoint.ON_STARTUP is not None
        assert HookPoint.ON_SHUTDOWN is not None


class TestHookManager:
    """Tests for the HookManager class."""

    @pytest.fixture
    def hook_manager(self):
        """Create a fresh HookManager for each test."""
        from core.plugins.hooks import HookManager

        return HookManager()

    @pytest.fixture
    def async_callback(self):
        """Create an async callback function."""
        callback = AsyncMock(return_value={"processed": True})
        callback.__name__ = "test_callback"
        return callback

    def test_hook_manager_initialization(self, hook_manager):
        """HookManager should initialize with empty hooks."""
        from core.plugins.hooks import HookPoint

        # All hook points should have empty lists
        for point in HookPoint:
            hooks = hook_manager.get_hooks(point)
            assert hooks == []

    def test_register_hook(self, hook_manager, async_callback):
        """register_hook should add a callback to a hook point."""
        from core.plugins.hooks import HookPoint

        hook_manager.register_hook(HookPoint.PRE_MESSAGE, async_callback)

        hooks = hook_manager.get_hooks(HookPoint.PRE_MESSAGE)
        assert len(hooks) == 1
        assert hooks[0].callback is async_callback

    def test_register_hook_with_priority(self, hook_manager, async_callback):
        """register_hook should support priority ordering."""
        from core.plugins.hooks import HookPoint

        callback2 = AsyncMock()
        callback2.__name__ = "callback2"

        hook_manager.register_hook(HookPoint.PRE_MESSAGE, async_callback, priority=10)
        hook_manager.register_hook(HookPoint.PRE_MESSAGE, callback2, priority=5)

        hooks = hook_manager.get_hooks(HookPoint.PRE_MESSAGE)
        # Higher priority should come first
        assert hooks[0].callback is async_callback
        assert hooks[1].callback is callback2

    def test_register_hook_with_plugin_name(self, hook_manager, async_callback):
        """register_hook should track plugin ownership."""
        from core.plugins.hooks import HookPoint

        hook_manager.register_hook(
            HookPoint.PRE_MESSAGE, async_callback, plugin_name="my_plugin"
        )

        hooks = hook_manager.get_hooks(HookPoint.PRE_MESSAGE)
        assert hooks[0].plugin_name == "my_plugin"

    def test_unregister_hook(self, hook_manager, async_callback):
        """unregister_hook should remove a specific callback."""
        from core.plugins.hooks import HookPoint

        hook_manager.register_hook(HookPoint.PRE_MESSAGE, async_callback)
        hook_manager.unregister_hook(HookPoint.PRE_MESSAGE, async_callback)

        hooks = hook_manager.get_hooks(HookPoint.PRE_MESSAGE)
        assert len(hooks) == 0

    def test_unregister_hooks_by_plugin(self, hook_manager, async_callback):
        """unregister_hooks_by_plugin should remove all hooks for a plugin."""
        from core.plugins.hooks import HookPoint

        callback2 = AsyncMock()
        callback2.__name__ = "callback2"

        hook_manager.register_hook(
            HookPoint.PRE_MESSAGE, async_callback, plugin_name="my_plugin"
        )
        hook_manager.register_hook(
            HookPoint.POST_MESSAGE, callback2, plugin_name="my_plugin"
        )

        hook_manager.unregister_hooks_by_plugin("my_plugin")

        assert len(hook_manager.get_hooks(HookPoint.PRE_MESSAGE)) == 0
        assert len(hook_manager.get_hooks(HookPoint.POST_MESSAGE)) == 0

    @pytest.mark.asyncio
    async def test_trigger_hooks(self, hook_manager, async_callback):
        """trigger_hooks should call all registered callbacks."""
        from core.plugins.hooks import HookPoint

        hook_manager.register_hook(HookPoint.PRE_MESSAGE, async_callback)

        data = {"message": "test"}
        results = await hook_manager.trigger_hooks(HookPoint.PRE_MESSAGE, data)

        async_callback.assert_called_once_with(data)
        assert len(results) == 1
        assert results[0] == {"processed": True}

    @pytest.mark.asyncio
    async def test_trigger_hooks_in_priority_order(self, hook_manager):
        """trigger_hooks should call callbacks in priority order."""
        from core.plugins.hooks import HookPoint

        call_order = []

        async def callback1(data):
            call_order.append(1)
            return 1

        async def callback2(data):
            call_order.append(2)
            return 2

        async def callback3(data):
            call_order.append(3)
            return 3

        hook_manager.register_hook(HookPoint.PRE_MESSAGE, callback1, priority=5)
        hook_manager.register_hook(HookPoint.PRE_MESSAGE, callback2, priority=10)
        hook_manager.register_hook(HookPoint.PRE_MESSAGE, callback3, priority=1)

        await hook_manager.trigger_hooks(HookPoint.PRE_MESSAGE, {})

        # Higher priority first: 2 (10), 1 (5), 3 (1)
        assert call_order == [2, 1, 3]

    @pytest.mark.asyncio
    async def test_trigger_hooks_with_exception(self, hook_manager):
        """trigger_hooks should handle exceptions gracefully."""
        from core.plugins.hooks import HookPoint

        call_order = []

        async def failing_callback(data):
            raise ValueError("Test error")

        async def good_callback(data):
            call_order.append("good")
            return "good"

        hook_manager.register_hook(HookPoint.PRE_MESSAGE, failing_callback, priority=10)
        hook_manager.register_hook(HookPoint.PRE_MESSAGE, good_callback, priority=5)

        # Should not raise, should continue to next callback
        results = await hook_manager.trigger_hooks(HookPoint.PRE_MESSAGE, {})

        assert "good" in call_order
        # Results should include error info and good result
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_trigger_hooks_stops_on_consume(self, hook_manager):
        """trigger_hooks should stop when a hook consumes the event."""
        from core.plugins.hooks import HookPoint, HookResult

        call_order = []

        async def consumer_callback(data):
            call_order.append("consumer")
            return HookResult(consumed=True, data={"consumed": True})

        async def after_callback(data):
            call_order.append("after")
            return "after"

        hook_manager.register_hook(
            HookPoint.PRE_MESSAGE, consumer_callback, priority=10
        )
        hook_manager.register_hook(HookPoint.PRE_MESSAGE, after_callback, priority=5)

        results = await hook_manager.trigger_hooks(HookPoint.PRE_MESSAGE, {})

        # Only consumer should be called
        assert call_order == ["consumer"]

    @pytest.mark.asyncio
    async def test_trigger_hooks_data_modification(self, hook_manager):
        """Hooks should be able to modify data for subsequent hooks."""
        from core.plugins.hooks import HookPoint, HookResult

        async def modifier_callback(data):
            data["modified"] = True
            return HookResult(consumed=False, data=data)

        async def reader_callback(data):
            return {"saw_modification": data.get("modified", False)}

        hook_manager.register_hook(HookPoint.PRE_MESSAGE, modifier_callback, priority=10)
        hook_manager.register_hook(HookPoint.PRE_MESSAGE, reader_callback, priority=5)

        results = await hook_manager.trigger_hooks(
            HookPoint.PRE_MESSAGE, {}, allow_modification=True
        )

        # Second callback should see the modification
        assert results[1]["saw_modification"] is True


class TestHookResult:
    """Tests for the HookResult class."""

    def test_hook_result_default(self):
        """HookResult should have sensible defaults."""
        from core.plugins.hooks import HookResult

        result = HookResult()
        assert result.consumed is False
        assert result.data is None
        assert result.error is None

    def test_hook_result_consumed(self):
        """HookResult can indicate event was consumed."""
        from core.plugins.hooks import HookResult

        result = HookResult(consumed=True, data={"handled": True})
        assert result.consumed is True
        assert result.data == {"handled": True}

    def test_hook_result_with_error(self):
        """HookResult can include error information."""
        from core.plugins.hooks import HookResult

        error = ValueError("Test error")
        result = HookResult(error=error)
        assert result.error is error


class TestGlobalHookManager:
    """Tests for the global hook manager instance."""

    def test_global_instance_exists(self):
        """A global hook manager should be available."""
        from core.plugins.hooks import hook_manager

        assert hook_manager is not None

    def test_register_hook_function(self):
        """register_hook should be available as module-level function."""
        from core.plugins.hooks import register_hook, HookPoint

        # Should not raise
        async def dummy(data):
            pass

        register_hook(HookPoint.ON_STARTUP, dummy)

    def test_trigger_hooks_function(self):
        """trigger_hooks should be available as module-level function."""
        from core.plugins.hooks import trigger_hooks, HookPoint

        # Should be importable
        assert callable(trigger_hooks)
