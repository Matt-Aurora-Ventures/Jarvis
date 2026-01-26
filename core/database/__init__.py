"""
Unified Database Access Layer for Jarvis.

Provides centralized, thread-safe access to all databases:
- Core: Trades, positions, users, orders
- Analytics: Sentiment, LLM costs, metrics  
- Cache: Sessions, rate limits, API cache

Usage:
    from core.database import get_core_db, get_analytics_db, get_cache_db
    
    db = get_core_db()
    with db.cursor() as cur:
        cur.execute("SELECT * FROM positions")
        positions = cur.fetchall()
"""

from .pool import ConnectionPool, get_pool

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


def get_legacy_db() -> ConnectionPool:
    """
    Get connection pool for legacy database (deprecated).
    
    Use get_core_db() instead for new code.
    """
    return get_pool(LEGACY_DB)


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
    "get_core_db",
    "get_analytics_db", 
    "get_cache_db",
    "get_legacy_db",
    "health_check",
    "close_all",
    "ConnectionPool",
]
