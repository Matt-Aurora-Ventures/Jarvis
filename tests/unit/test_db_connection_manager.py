"""
Tests for database connection manager.

Verifies:
- Connections are tracked correctly
- Cleanup happens on shutdown
- Health checks work
- Multiple connection types are supported
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta

from core.db_connection_manager import (
    DatabaseConnectionManager,
    get_db_manager,
    managed_db_connection,
)


class TestDatabaseConnectionManager:
    """Test database connection manager."""

    @pytest.mark.asyncio
    async def test_register_connection(self):
        """Test registering a connection."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        manager.register_connection("test_conn", conn)

        assert "test_conn" in manager._connections
        assert manager._connections["test_conn"] is conn

    @pytest.mark.asyncio
    async def test_register_pool(self):
        """Test registering a connection pool."""
        manager = DatabaseConnectionManager()

        pool = Mock()
        manager.register_pool("test_pool", pool)

        assert "test_pool" in manager._connection_pools
        assert manager._connection_pools["test_pool"] is pool

    @pytest.mark.asyncio
    async def test_close_connection_with_close_method(self):
        """Test closing connection with close() method."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.close = Mock()

        manager.register_connection("test", conn)
        await manager._close_connection("test", conn)

        conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_connection_with_aclose_method(self):
        """Test closing connection with aclose() method."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.aclose = AsyncMock()

        manager.register_connection("test", conn)
        await manager._close_connection("test", conn)

        conn.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_connection_with_async_close(self):
        """Test closing connection with async close() method."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.close = AsyncMock()

        manager.register_connection("test", conn)
        await manager._close_connection("test", conn)

        conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_pool_with_async_close(self):
        """Test closing pool with async close."""
        manager = DatabaseConnectionManager()

        pool = Mock()
        pool.close = AsyncMock()
        pool.wait_closed = AsyncMock()

        manager.register_pool("test", pool)
        await manager._close_pool("test", pool)

        pool.close.assert_called_once()
        pool.wait_closed.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_closes_all_connections(self):
        """Test that shutdown closes all connections and pools."""
        manager = DatabaseConnectionManager()

        # Create mock connections
        conn1 = Mock()
        conn1.close = Mock()

        conn2 = Mock()
        conn2.aclose = AsyncMock()

        pool1 = Mock()
        pool1.close = AsyncMock()
        pool1.wait_closed = AsyncMock()

        # Register
        manager.register_connection("conn1", conn1)
        manager.register_connection("conn2", conn2)
        manager.register_pool("pool1", pool1)

        # Shutdown
        await manager._shutdown()

        # All should be closed
        conn1.close.assert_called_once()
        conn2.aclose.assert_called_once()
        pool1.close.assert_called_once()

        # Registries should be cleared
        assert len(manager._connections) == 0
        assert len(manager._connection_pools) == 0

    @pytest.mark.asyncio
    async def test_health_check_with_ping(self):
        """Test health check using ping method."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.ping = Mock()

        manager.register_connection("test", conn)
        results = await manager.health_check(force=True)

        assert results["test"] is True
        conn.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_with_async_ping(self):
        """Test health check using async ping."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.ping = AsyncMock()

        manager.register_connection("test", conn)
        results = await manager.health_check(force=True)

        assert results["test"] is True
        conn.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_with_execute(self):
        """Test health check using execute method."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.execute = AsyncMock()

        manager.register_connection("test", conn)
        results = await manager.health_check(force=True)

        assert results["test"] is True
        conn.execute.assert_called_once_with("SELECT 1")

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check when connection fails."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.ping = Mock(side_effect=Exception("Connection failed"))

        manager.register_connection("test", conn)
        results = await manager.health_check(force=True)

        assert results["test"] is False

    @pytest.mark.asyncio
    async def test_health_check_caching(self):
        """Test that health checks are cached."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.ping = Mock()

        manager.register_connection("test", conn)

        # First check
        await manager.health_check(force=True)
        assert conn.ping.call_count == 1

        # Second check (should be cached)
        await manager.health_check(force=False)
        assert conn.ping.call_count == 1  # Not called again

        # Force check
        await manager.health_check(force=True)
        assert conn.ping.call_count == 2

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting manager statistics."""
        manager = DatabaseConnectionManager()

        # Add some connections
        manager.register_connection("conn1", Mock())
        manager.register_connection("conn2", Mock())
        manager.register_pool("pool1", Mock())

        stats = manager.get_stats()

        assert stats["connections"] == 2
        assert stats["pools"] == 1
        assert stats["is_shutting_down"] is False

    @pytest.mark.asyncio
    async def test_cannot_register_during_shutdown(self):
        """Test that connections cannot be registered during shutdown."""
        manager = DatabaseConnectionManager()
        manager._is_shutting_down = True

        conn = Mock()
        manager.register_connection("test", conn)

        # Should not be registered
        assert "test" not in manager._connections

    @pytest.mark.asyncio
    async def test_error_handling_in_shutdown(self):
        """Test that errors during shutdown don't crash."""
        manager = DatabaseConnectionManager()

        # Connection that fails to close
        bad_conn = Mock()
        bad_conn.close = Mock(side_effect=Exception("Close failed"))

        # Good connection
        good_conn = Mock()
        good_conn.close = Mock()

        manager.register_connection("bad", bad_conn)
        manager.register_connection("good", good_conn)

        # Should not raise
        await manager._shutdown()

        # Good connection should still be closed
        good_conn.close.assert_called_once()


class TestManagedConnection:
    """Test managed_db_connection context manager."""

    @pytest.mark.asyncio
    async def test_managed_connection_lifecycle(self):
        """Test connection lifecycle with context manager."""
        connection_opened = False
        connection_closed = False

        async def create_conn():
            nonlocal connection_opened
            connection_opened = True

            conn = Mock()
            conn.close = Mock()
            return conn

        async with managed_db_connection(create_conn, "test") as conn:
            assert connection_opened
            assert conn is not None

        # Connection should be registered (cleanup via shutdown hook)
        manager = get_db_manager()
        assert "test" in manager._connections

    @pytest.mark.asyncio
    async def test_managed_connection_exception_handling(self):
        """Test that exceptions don't prevent registration."""
        async def create_conn():
            return Mock()

        try:
            async with managed_db_connection(create_conn, "test") as conn:
                raise RuntimeError("Test error")
        except RuntimeError:
            pass

        # Connection should still be registered for cleanup
        manager = get_db_manager()
        assert "test" in manager._connections


class TestGlobalManager:
    """Test global manager singleton."""

    def test_singleton_pattern(self):
        """Test that get_db_manager returns the same instance."""
        manager1 = get_db_manager()
        manager2 = get_db_manager()

        assert manager1 is manager2


class TestConnectionCloseMethods:
    """Test various connection close method patterns."""

    @pytest.mark.asyncio
    async def test_disconnect_method(self):
        """Test connection with disconnect() method."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.disconnect = Mock()

        await manager._close_connection("test", conn)
        conn.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_disconnect_method(self):
        """Test connection with async disconnect()."""
        manager = DatabaseConnectionManager()

        conn = Mock()
        conn.disconnect = AsyncMock()

        await manager._close_connection("test", conn)
        conn.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_close_method(self):
        """Test connection with no close method."""
        manager = DatabaseConnectionManager()

        conn = Mock(spec=[])  # No methods

        result = await manager._close_connection("test", conn)
        assert result is False

    @pytest.mark.asyncio
    async def test_pool_terminate_method(self):
        """Test pool with terminate() method."""
        manager = DatabaseConnectionManager()

        pool = Mock()
        pool.terminate = Mock()

        await manager._close_pool("test", pool)
        pool.terminate.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
