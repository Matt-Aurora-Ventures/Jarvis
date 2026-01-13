"""
JARVIS Database Layer

Provides connection pooling and database utilities:
- SQLite support (development)
- PostgreSQL support with connection pooling (production)
- Async support via databases library
- Migration utilities

Usage:
    from core.db import get_db, Database

    # Sync usage
    db = get_db()
    with db.connection() as conn:
        result = conn.execute("SELECT * FROM users").fetchall()

    # Async usage
    async with db.async_connection() as conn:
        result = await conn.fetch_all("SELECT * FROM users")
"""

from .pool import (
    Database,
    DatabaseConfig,
    get_db,
    get_async_db,
    init_database,
)

__all__ = [
    "Database",
    "DatabaseConfig",
    "get_db",
    "get_async_db",
    "init_database",
]
