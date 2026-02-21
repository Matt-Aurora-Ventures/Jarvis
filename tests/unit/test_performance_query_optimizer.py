"""Regression tests for core.performance.query_optimizer."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.performance.query_optimizer import QueryOptimizer
from core.security_validation import ValidationError


@pytest.fixture
def test_db_path(tmp_path: Path) -> str:
    """Create a temporary SQLite DB with a schema suitable for index suggestions."""
    db_path = tmp_path / "optimizer.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            status TEXT,
            created_at TEXT,
            type TEXT,
            symbol TEXT
        )
        """
    )
    conn.commit()
    conn.close()
    return str(db_path)


def test_suggest_indexes_rejects_malicious_table_name(test_db_path: str) -> None:
    optimizer = QueryOptimizer(db_path=test_db_path)

    with pytest.raises(ValidationError):
        optimizer.suggest_indexes("orders;DROP TABLE users;--")


def test_suggest_indexes_for_valid_table_uses_safe_identifiers(test_db_path: str) -> None:
    optimizer = QueryOptimizer(db_path=test_db_path)

    suggestions = optimizer.suggest_indexes("orders")

    assert "CREATE INDEX idx_orders_user_id ON orders(user_id);" in suggestions
    assert "CREATE INDEX idx_orders_created_at ON orders(created_at);" in suggestions
    assert "CREATE INDEX idx_orders_status ON orders(status);" in suggestions
    assert all(";" in statement for statement in suggestions)
    assert all("DROP TABLE" not in statement.upper() for statement in suggestions)
