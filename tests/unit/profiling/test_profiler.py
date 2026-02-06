"""
Unit tests for core/profiling/profiler.py

Tests the Profiler class with:
- start(name) and stop(name) methods
- get_stats(name) method
- @profile decorator
"""

import pytest
import time
import asyncio
from unittest.mock import MagicMock, patch


class TestProfilerClass:
    """Tests for the Profiler class."""

    def test_profiler_start_stop_basic(self):
        """Profiler.start() and stop() should track basic timing."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()
        profiler.start("test_operation")
        time.sleep(0.05)  # 50ms
        duration = profiler.stop("test_operation")

        assert duration >= 45  # Allow some tolerance
        assert duration < 100

    def test_profiler_stop_returns_duration_ms(self):
        """stop() should return duration in milliseconds."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()
        profiler.start("quick_op")
        time.sleep(0.01)  # 10ms
        duration = profiler.stop("quick_op")

        # Should be in milliseconds, not seconds
        assert duration >= 8
        assert duration < 50

    def test_profiler_stop_without_start_raises(self):
        """stop() without start() should raise an error."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        with pytest.raises(KeyError):
            profiler.stop("never_started")

    def test_profiler_multiple_operations(self):
        """Profiler should track multiple operations independently."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        profiler.start("op_a")
        time.sleep(0.02)
        profiler.start("op_b")
        time.sleep(0.02)
        duration_b = profiler.stop("op_b")
        duration_a = profiler.stop("op_a")

        # op_a should be longer than op_b
        assert duration_a > duration_b
        assert duration_a >= 35
        assert duration_b >= 15

    def test_profiler_nested_operations(self):
        """Profiler should handle nested operations correctly."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        profiler.start("outer")
        time.sleep(0.01)
        profiler.start("inner")
        time.sleep(0.02)
        inner_duration = profiler.stop("inner")
        time.sleep(0.01)
        outer_duration = profiler.stop("outer")

        assert outer_duration > inner_duration
        assert inner_duration >= 15
        assert outer_duration >= 35


class TestProfilerGetStats:
    """Tests for Profiler.get_stats() method."""

    def test_get_stats_returns_stats_object(self):
        """get_stats() should return a Stats object with relevant fields."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        # Record a few samples
        for _ in range(5):
            profiler.start("my_op")
            time.sleep(0.01)
            profiler.stop("my_op")

        stats = profiler.get_stats("my_op")

        assert hasattr(stats, 'count')
        assert hasattr(stats, 'total_ms')
        assert hasattr(stats, 'avg_ms')
        assert hasattr(stats, 'min_ms')
        assert hasattr(stats, 'max_ms')

    def test_get_stats_count(self):
        """get_stats().count should reflect number of completed operations."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        for _ in range(10):
            profiler.start("counted_op")
            profiler.stop("counted_op")

        stats = profiler.get_stats("counted_op")
        assert stats.count == 10

    def test_get_stats_total_ms(self):
        """get_stats().total_ms should be sum of all durations."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        for _ in range(3):
            profiler.start("summed_op")
            time.sleep(0.02)
            profiler.stop("summed_op")

        stats = profiler.get_stats("summed_op")
        assert stats.total_ms >= 50  # 3 * ~20ms with tolerance

    def test_get_stats_avg_ms(self):
        """get_stats().avg_ms should be total_ms / count."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        for _ in range(5):
            profiler.start("avg_op")
            time.sleep(0.01)
            profiler.stop("avg_op")

        stats = profiler.get_stats("avg_op")
        expected_avg = stats.total_ms / stats.count
        assert abs(stats.avg_ms - expected_avg) < 0.1

    def test_get_stats_min_max(self):
        """get_stats() should track min and max durations."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        # First: short sleep
        profiler.start("minmax_op")
        time.sleep(0.01)
        profiler.stop("minmax_op")

        # Second: longer sleep
        profiler.start("minmax_op")
        time.sleep(0.03)
        profiler.stop("minmax_op")

        stats = profiler.get_stats("minmax_op")
        assert stats.min_ms < stats.max_ms
        assert stats.min_ms >= 8
        assert stats.max_ms >= 25

    def test_get_stats_unknown_operation(self):
        """get_stats() on unknown operation should raise or return None."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        # Either raises KeyError or returns None
        try:
            stats = profiler.get_stats("unknown")
            assert stats is None
        except KeyError:
            pass  # Also acceptable


class TestProfilerReset:
    """Tests for Profiler.reset() functionality."""

    def test_profiler_reset_clears_stats(self):
        """reset() should clear all collected stats."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        profiler.start("to_clear")
        profiler.stop("to_clear")

        stats_before = profiler.get_stats("to_clear")
        assert stats_before is not None

        profiler.reset()

        stats_after = profiler.get_stats("to_clear")
        assert stats_after is None or stats_after.count == 0

    def test_profiler_reset_all(self):
        """reset() should clear all operations."""
        from core.profiling.profiler import Profiler

        profiler = Profiler()

        for op_name in ["op1", "op2", "op3"]:
            profiler.start(op_name)
            profiler.stop(op_name)

        profiler.reset()

        for op_name in ["op1", "op2", "op3"]:
            stats = profiler.get_stats(op_name)
            assert stats is None or stats.count == 0


class TestProfileDecorator:
    """Tests for the @profile decorator."""

    def test_profile_decorator_sync_function(self):
        """@profile should work with synchronous functions."""
        from core.profiling.profiler import profile, Profiler

        profiler = Profiler()

        @profile(profiler=profiler)
        def sync_op():
            time.sleep(0.02)
            return "done"

        result = sync_op()

        assert result == "done"
        stats = profiler.get_stats("sync_op")
        assert stats is not None
        assert stats.count >= 1
        assert stats.avg_ms >= 15

    def test_profile_decorator_preserves_return_value(self):
        """@profile should preserve the function's return value."""
        from core.profiling.profiler import profile, Profiler

        profiler = Profiler()

        @profile(profiler=profiler)
        def returns_value():
            return {"key": "value", "num": 42}

        result = returns_value()
        assert result == {"key": "value", "num": 42}

    def test_profile_decorator_with_custom_name(self):
        """@profile should accept a custom name."""
        from core.profiling.profiler import profile, Profiler

        profiler = Profiler()

        @profile(profiler=profiler, name="custom.operation.name")
        def named_func():
            return True

        named_func()

        stats = profiler.get_stats("custom.operation.name")
        assert stats is not None
        assert stats.count == 1

    def test_profile_decorator_with_args_kwargs(self):
        """@profile should pass through args and kwargs."""
        from core.profiling.profiler import profile, Profiler

        profiler = Profiler()

        @profile(profiler=profiler)
        def func_with_args(a, b, c=None):
            return (a, b, c)

        result = func_with_args(1, 2, c=3)
        assert result == (1, 2, 3)

    def test_profile_decorator_exception_handling(self):
        """@profile should not swallow exceptions."""
        from core.profiling.profiler import profile, Profiler

        profiler = Profiler()

        @profile(profiler=profiler)
        def raises_error():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            raises_error()

        # Should still record the timing
        stats = profiler.get_stats("raises_error")
        assert stats is not None
        assert stats.count >= 1

    @pytest.mark.asyncio
    async def test_profile_decorator_async_function(self):
        """@profile should work with async functions."""
        from core.profiling.profiler import profile, Profiler

        profiler = Profiler()

        @profile(profiler=profiler)
        async def async_op():
            await asyncio.sleep(0.02)
            return "async_done"

        result = await async_op()

        assert result == "async_done"
        stats = profiler.get_stats("async_op")
        assert stats is not None
        assert stats.count >= 1
        assert stats.avg_ms >= 15


class TestGlobalProfiler:
    """Tests for global/default profiler instance."""

    def test_global_profiler_singleton(self):
        """Should provide a global profiler instance."""
        from core.profiling.profiler import get_global_profiler

        profiler1 = get_global_profiler()
        profiler2 = get_global_profiler()

        assert profiler1 is profiler2

    def test_profile_decorator_uses_global_profiler(self):
        """@profile without explicit profiler should use global."""
        from core.profiling.profiler import profile, get_global_profiler

        global_profiler = get_global_profiler()
        global_profiler.reset()

        @profile()
        def auto_profiled():
            time.sleep(0.01)
            return True

        auto_profiled()

        stats = global_profiler.get_stats("auto_profiled")
        assert stats is not None
        assert stats.count >= 1
