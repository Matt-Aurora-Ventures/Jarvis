"""
Database connection manager with graceful shutdown support.

Provides:
- Connection pooling
- Automatic cleanup on shutdown
- Health checks
- Connection reuse
"""

import asyncio
import inspect
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

try:
    from core.shutdown_manager import get_shutdown_manager, ShutdownPhase
    SHUTDOWN_MANAGER_AVAILABLE = True
except ImportError:
    SHUTDOWN_MANAGER_AVAILABLE = False

logger = logging.getLogger(__name__)


def _get_static_attr(obj: Any, name: str) -> Optional[Any]:
    """Safely get attribute without triggering dynamic __getattr__."""
    try:
        inspect.getattr_static(obj, name)
    except AttributeError:
        return None
    return getattr(obj, name, None)


class DatabaseConnectionManager:
    """
    Manages database connections with graceful shutdown.

    Usage:
        db_mgr = get_db_manager()
        async with db_mgr.connection() as conn:
            # Use connection
            await conn.execute(...)
    """

    def __init__(self):
        self._connections: Dict[str, Any] = {}
        self._connection_pools: Dict[str, Any] = {}
        self._last_health_check: Optional[datetime] = None
        self._is_shutting_down = False

        # Register shutdown hook
        if SHUTDOWN_MANAGER_AVAILABLE:
            shutdown_mgr = get_shutdown_manager()
            shutdown_mgr.register_hook(
                name="db_connection_manager",
                callback=self._shutdown,
                phase=ShutdownPhase.CLEANUP,
                timeout=10.0,
                priority=50,
            )

    def register_connection(self, name: str, connection: Any):
        """Register a connection for cleanup on shutdown."""
        if self._is_shutting_down:
            logger.warning(f"Cannot register connection '{name}' during shutdown")
            return

        self._connections[name] = connection
        logger.debug(f"Registered connection: {name}")

    def register_pool(self, name: str, pool: Any):
        """Register a connection pool for cleanup on shutdown."""
        if self._is_shutting_down:
            logger.warning(f"Cannot register pool '{name}' during shutdown")
            return

        self._connection_pools[name] = pool
        logger.debug(f"Registered connection pool: {name}")

    async def _close_connection(self, name: str, conn: Any) -> bool:
        """Close a single connection."""
        try:
            # Try various close methods
            aclose = _get_static_attr(conn, "aclose")
            if callable(aclose):
                if asyncio.iscoroutinefunction(aclose):
                    await aclose()
                else:
                    aclose()
            else:
                close = _get_static_attr(conn, "close")
                if callable(close):
                    if asyncio.iscoroutinefunction(close):
                        await close()
                    else:
                        close()
                else:
                    disconnect = _get_static_attr(conn, "disconnect")
                    if callable(disconnect):
                        if asyncio.iscoroutinefunction(disconnect):
                            await disconnect()
                        else:
                            disconnect()
                    else:
                        logger.warning(f"Connection '{name}' has no close method")
                        return False

            logger.debug(f"Closed connection: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to close connection '{name}': {e}")
            return False

    async def _close_pool(self, name: str, pool: Any) -> bool:
        """Close a connection pool."""
        try:
            # Try various close methods for pools
            aclose = _get_static_attr(pool, "aclose")
            if callable(aclose):
                if asyncio.iscoroutinefunction(aclose):
                    await aclose()
                else:
                    aclose()
            else:
                close = _get_static_attr(pool, "close")
                if callable(close):
                    if asyncio.iscoroutinefunction(close):
                        await close()
                    else:
                        close()

                    # Wait for pool to close
                    wait_closed = _get_static_attr(pool, "wait_closed")
                    if callable(wait_closed) and asyncio.iscoroutinefunction(wait_closed):
                        await wait_closed()
                else:
                    terminate = _get_static_attr(pool, "terminate")
                    if callable(terminate):
                        terminate()
                    else:
                        logger.warning(f"Pool '{name}' has no close method")
                        return False

            logger.debug(f"Closed pool: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to close pool '{name}': {e}")
            return False

    async def _shutdown(self):
        """Graceful shutdown - close all connections and pools."""
        self._is_shutting_down = True

        logger.info(f"Closing {len(self._connection_pools)} pool(s) and {len(self._connections)} connection(s)...")

        # Close pools first (they manage connections)
        closed_pools = 0
        for name, pool in list(self._connection_pools.items()):
            if await self._close_pool(name, pool):
                closed_pools += 1

        # Close individual connections
        closed_conns = 0
        for name, conn in list(self._connections.items()):
            if await self._close_connection(name, conn):
                closed_conns += 1

        self._connections.clear()
        self._connection_pools.clear()

        logger.info(f"Database cleanup complete: {closed_pools} pools, {closed_conns} connections")

    async def health_check(self, force: bool = False) -> Dict[str, bool]:
        """
        Check health of all registered connections.

        Args:
            force: Force check even if recently checked

        Returns:
            Dict mapping connection names to health status
        """
        if not force:
            if self._last_health_check:
                since_check = datetime.now() - self._last_health_check
                if since_check < timedelta(seconds=30):
                    # Skip check if done recently
                    return {}

        results = {}

        # Check individual connections
        for name, conn in self._connections.items():
            try:
                # Try to ping the connection
                ping = _get_static_attr(conn, "ping")
                if callable(ping):
                    if asyncio.iscoroutinefunction(ping):
                        await ping()
                    else:
                        ping()
                    results[name] = True
                else:
                    execute = _get_static_attr(conn, "execute")
                    if callable(execute):
                        # Try a simple query
                        if asyncio.iscoroutinefunction(execute):
                            await execute("SELECT 1")
                        else:
                            execute("SELECT 1")
                        results[name] = True
                    else:
                        # Can't verify, assume healthy
                        results[name] = True

            except Exception as e:
                logger.error(f"Health check failed for '{name}': {e}")
                results[name] = False

        self._last_health_check = datetime.now()
        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about managed connections."""
        return {
            "pools": len(self._connection_pools),
            "connections": len(self._connections),
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "is_shutting_down": self._is_shutting_down,
        }


# Global singleton
_db_manager: Optional[DatabaseConnectionManager] = None


def get_db_manager() -> DatabaseConnectionManager:
    """Get or create the global database connection manager."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseConnectionManager()
    return _db_manager


@asynccontextmanager
async def managed_db_connection(connection_factory, name: str):
    """
    Context manager for database connections with automatic cleanup.

    Usage:
        async def create_conn():
            return await asyncpg.connect(dsn)

        async with managed_db_connection(create_conn, "main_db") as conn:
            await conn.execute("SELECT 1")
    """
    manager = get_db_manager()
    conn = await connection_factory()

    try:
        manager.register_connection(name, conn)
        yield conn
    finally:
        # Note: Cleanup happens via shutdown hook
        pass
