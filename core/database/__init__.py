"""
Unified Database Access Layer for Jarvis.

Provides centralized, thread-safe access to all databases:
- Core: Trades, positions, users, orders
- Analytics: Sentiment, LLM costs, metrics
- Cache: Sessions, rate limits, API cache

SQLite Usage:
    from core.database import get_core_db, get_analytics_db, get_cache_db

    db = get_core_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM positions")
        positions = cur.fetchall()

PostgreSQL Usage (async):
    from core.database import get_postgres_client, PostgresClient
    from core.database.postgres_repositories import PostgresPositionRepository

    client = get_postgres_client()
    positions = await client.fetch("SELECT * FROM positions")

    # Or use repository pattern:
    repo = PostgresPositionRepository()
    positions = await repo.get_open_positions()

TimescaleDB Usage:
    from core.database import get_timescale_repository, TimescaleRepository

    repo = get_timescale_repository()
    ohlc = await repo.get_price_ohlc(token_mint="...", interval="1h", ...)
"""

from .pool import ConnectionPool, get_pool

# PostgreSQL async client
from .postgres_client import (
    PostgresClient,
    get_postgres_client,
    init_postgres,
    close_postgres,
)

# TimescaleDB repository
from .timescale_repository import (
    TimescaleRepository,
    PriceTick,
    StrategySignal,
    PositionSnapshot,
    get_timescale_repository,
    init_timescale,
)

# Data migration
from .migration import (
    DataMigrator,
    MigrationRunner,
)

# Database paths
CORE_DB = "data/jarvis_core.db"
ANALYTICS_DB = "data/jarvis_analytics.db"
CACHE_DB = "data/jarvis_cache.db"

# Legacy compatibility
LEGACY_DB = "data/jarvis.db"


def get_core_db() -> ConnectionPool:
    """
    Get connection pool for Core database.
    
    Contains: users, positions, trades, orders, bot_config, token_metadata
    """
    return get_pool(CORE_DB)


def get_analytics_db() -> ConnectionPool:
    """
    Get connection pool for Analytics database.
    
    Contains: llm_costs, sentiment, metrics, learnings, whale_tracking
    """
    return get_pool(ANALYTICS_DB)


def get_cache_db() -> ConnectionPool:
    """
    Get connection pool for Cache database.
    
    Contains: sessions, rate_limits, api_cache, spam_protection
    """
    return get_pool(CACHE_DB)


def health_check() -> dict:
    """
    Run health check on all databases.
    
    Returns dict with status of each database.
    """
    from pathlib import Path
    
    results = {}
    for name, path in [
        ("core", CORE_DB),
        ("analytics", ANALYTICS_DB),
        ("cache", CACHE_DB),
    ]:
        db_path = Path(path)
        try:
            if db_path.exists():
                pool = get_pool(path)
                pool.execute("SELECT 1")
                size_mb = db_path.stat().st_size / (1024 * 1024)
                results[name] = {
                    "status": "healthy",
                    "path": path,
                    "size_mb": round(size_mb, 2)
                }
            else:
                results[name] = {
                    "status": "not_initialized",
                    "path": path
                }
        except Exception as e:
            results[name] = {
                "status": "error",
                "path": path,
                "error": str(e)
            }
    
    all_healthy = all(r["status"] in ("healthy", "not_initialized") for r in results.values())
    return {
        "overall": "healthy" if all_healthy else "degraded",
        "databases": results
    }


def close_all() -> None:
    """Close all database connections. Call on application shutdown."""
    from .pool import _pools
    for pool in _pools.values():
        pool.close_all()


__all__ = [
    # SQLite pools
    "get_core_db",
    "get_analytics_db",
    "get_cache_db",
    "health_check",
    "close_all",
    "ConnectionPool",
    # PostgreSQL async
    "PostgresClient",
    "get_postgres_client",
    "init_postgres",
    "close_postgres",
    # TimescaleDB
    "TimescaleRepository",
    "PriceTick",
    "StrategySignal",
    "PositionSnapshot",
    "get_timescale_repository",
    "init_timescale",
    # Migration
    "DataMigrator",
    "MigrationRunner",
]
