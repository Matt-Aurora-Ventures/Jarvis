"""
Connection Pool - Reusable async HTTP client sessions with connection pooling.
Reduces overhead of creating new connections for each request.
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import weakref

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """Connection pool configuration."""
    max_connections: int = 100
    max_connections_per_host: int = 10
    timeout_total: float = 30.0
    timeout_connect: float = 10.0
    timeout_sock_read: float = 10.0
    keepalive_timeout: float = 60.0
    enable_cleanup_closed: bool = True


class ConnectionPool:
    """
    Manages reusable aiohttp ClientSession instances.
    Provides connection pooling and automatic cleanup.
    """
    
    def __init__(self, config: PoolConfig = None):
        self.config = config or PoolConfig()
        self._sessions: Dict[str, aiohttp.ClientSession] = {}
        self._lock = asyncio.Lock()
        self._created_at: Dict[str, datetime] = {}
        
    async def get_session(self, key: str = "default") -> aiohttp.ClientSession:
        """Get or create a session for the given key."""
        async with self._lock:
            if key in self._sessions:
                session = self._sessions[key]
                if not session.closed:
                    return session
                # Session was closed, remove it
                del self._sessions[key]
            
            # Create new session
            connector = aiohttp.TCPConnector(
                limit=self.config.max_connections,
                limit_per_host=self.config.max_connections_per_host,
                enable_cleanup_closed=self.config.enable_cleanup_closed,
                keepalive_timeout=self.config.keepalive_timeout,
            )
            
            timeout = aiohttp.ClientTimeout(
                total=self.config.timeout_total,
                connect=self.config.timeout_connect,
                sock_read=self.config.timeout_sock_read,
            )
            
            session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
            )
            
            self._sessions[key] = session
            self._created_at[key] = datetime.now(timezone.utc)
            logger.debug(f"Created new session for key: {key}")
            
            return session
    
    async def close_session(self, key: str):
        """Close a specific session."""
        async with self._lock:
            if key in self._sessions:
                session = self._sessions.pop(key)
                if not session.closed:
                    await session.close()
                self._created_at.pop(key, None)
                logger.debug(f"Closed session for key: {key}")
    
    async def close_all(self):
        """Close all sessions."""
        async with self._lock:
            for key, session in list(self._sessions.items()):
                if not session.closed:
                    await session.close()
            self._sessions.clear()
            self._created_at.clear()
            logger.debug("Closed all sessions")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "active_sessions": len(self._sessions),
            "sessions": {
                key: {
                    "closed": session.closed,
                    "created_at": self._created_at.get(key, "").isoformat() if self._created_at.get(key) else None,
                }
                for key, session in self._sessions.items()
            }
        }


# Singleton instance
_instance: Optional[ConnectionPool] = None


def get_connection_pool() -> ConnectionPool:
    """Get singleton connection pool."""
    global _instance
    if _instance is None:
        _instance = ConnectionPool()
    return _instance


async def get_session(key: str = "default") -> aiohttp.ClientSession:
    """Convenience function to get a session."""
    pool = get_connection_pool()
    return await pool.get_session(key)


async def close_all_sessions():
    """Convenience function to close all sessions."""
    pool = get_connection_pool()
    await pool.close_all()
