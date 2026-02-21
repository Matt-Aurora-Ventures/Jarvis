"""Canonical SQL query optimization utilities."""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.security_validation import sanitize_sql_identifier

logger = logging.getLogger(__name__)


@dataclass
class QueryAnalysis:
    """Analysis result for a query."""

    query: str
    execution_time_ms: float
    rows_scanned: int
    uses_index: bool
    suggestions: List[str]
    explain_plan: List[Dict[str, Any]]


def suggest_indexes_for_table(
    db_path: str,
    table: str,
    candidate_columns: Optional[Iterable[str]] = None,
) -> List[str]:
    """Build index suggestions for one table with identifier sanitization."""
    safe_table = sanitize_sql_identifier(table)
    candidates = set(candidate_columns or [])
    suggestions: List[str] = []

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        cursor.execute(f"PRAGMA index_list({safe_table})")
        existing = {row[1] for row in cursor.fetchall()}

        cursor.execute(f"PRAGMA table_info({safe_table})")
        columns = [row[1] for row in cursor.fetchall()]

        for col in columns:
            if (
                col.endswith("_id")
                or col.endswith("_at")
                or (candidates and col in candidates)
            ):
                safe_col = sanitize_sql_identifier(col)
                index_name = f"idx_{safe_table}_{safe_col}"
                if index_name not in existing:
                    suggestions.append(
                        f"CREATE INDEX {index_name} ON {safe_table}({safe_col});"
                    )
        return suggestions
    finally:
        conn.close()


class QueryOptimizer:
    """Analyze and optimize database queries."""

    def __init__(self, db_path: str = "data/jarvis.db"):
        self.db_path = db_path
        self.slow_query_threshold_ms = 100
        self._query_stats: Dict[str, List[float]] = {}

    def analyze_query(self, query: str, params: tuple = None) -> QueryAnalysis:
        """Analyze a query and provide optimization suggestions."""
        suggestions = []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        explain_query = f"EXPLAIN QUERY PLAN {query}"
        try:
            cursor.execute(explain_query)
            explain_plan = [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error:
            explain_plan = []

        uses_index = any("USING INDEX" in str(row) for row in explain_plan)
        uses_scan = any("SCAN TABLE" in str(row) for row in explain_plan)

        if uses_scan and not uses_index:
            suggestions.append(
                "Consider adding an index - query performs full table scan"
            )

        start = time.perf_counter()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            rows = cursor.fetchall()
            rows_scanned = len(rows)
        except sqlite3.Error as exc:
            rows_scanned = 0
            suggestions.append(f"Query error: {exc}")

        execution_time = (time.perf_counter() - start) * 1000

        query_upper = query.upper()
        if "SELECT *" in query_upper:
            suggestions.append("Avoid SELECT * - specify needed columns")
        if "WHERE" not in query_upper and "LIMIT" not in query_upper:
            suggestions.append(
                "Query has no WHERE clause or LIMIT - may return too many rows"
            )
        if query_upper.count("JOIN") > 2:
            suggestions.append("Multiple JOINs detected - consider query restructuring")
        if "LIKE '%'" in query_upper or "LIKE '%" in query:
            suggestions.append("Leading wildcard in LIKE prevents index usage")
        if "OR" in query_upper and "WHERE" in query_upper:
            suggestions.append("OR conditions may prevent index usage - consider UNION")
        if execution_time > self.slow_query_threshold_ms:
            suggestions.append(f"Slow query ({execution_time:.0f}ms) - needs optimization")

        conn.close()
        return QueryAnalysis(
            query=query,
            execution_time_ms=execution_time,
            rows_scanned=rows_scanned,
            uses_index=uses_index,
            suggestions=suggestions,
            explain_plan=explain_plan,
        )

    def suggest_indexes(self, table: str) -> List[str]:
        """Suggest indexes for a table based on common query patterns."""
        return suggest_indexes_for_table(
            db_path=self.db_path,
            table=table,
            candidate_columns=["status", "type", "symbol"],
        )

    def get_slow_queries(self) -> List[Tuple[str, float]]:
        """Return queries that exceeded the slow threshold."""
        slow: List[Tuple[str, float]] = []
        for query, times in self._query_stats.items():
            avg_time = sum(times) / len(times)
            if avg_time > self.slow_query_threshold_ms:
                slow.append((query, avg_time))
        return sorted(slow, key=lambda item: item[1], reverse=True)

    def record_query(self, query: str, execution_time_ms: float) -> None:
        """Record query execution for statistics."""
        normalized = self._normalize_query(query)
        if normalized not in self._query_stats:
            self._query_stats[normalized] = []
        self._query_stats[normalized].append(execution_time_ms)
        if len(self._query_stats[normalized]) > 100:
            self._query_stats[normalized] = self._query_stats[normalized][-100:]

    def _normalize_query(self, query: str) -> str:
        """Normalize query for grouping by replacing literals with placeholders."""
        normalized = re.sub(r"'[^']*'", "'?'", query)
        normalized = re.sub(r"\b\d+\b", "?", normalized)
        return " ".join(normalized.split())


def analyze_query(query: str, db_path: str = "data/jarvis.db") -> QueryAnalysis:
    """Convenience function to analyze one query."""
    return QueryOptimizer(db_path).analyze_query(query)


def create_recommended_indexes(db_path: str = "data/jarvis.db") -> List[str]:
    """Generate SQL for recommended indexes across all non-sqlite tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()

    optimizer = QueryOptimizer(db_path)
    all_suggestions: List[str] = []
    for table in tables:
        all_suggestions.extend(optimizer.suggest_indexes(table))
    return all_suggestions
