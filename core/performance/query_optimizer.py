"""Compatibility shim for canonical query optimizer module."""

from core.query_optimizer import (
    QueryAnalysis,
    QueryOptimizer,
    analyze_query,
    create_recommended_indexes,
)

__all__ = [
    "QueryAnalysis",
    "QueryOptimizer",
    "analyze_query",
    "create_recommended_indexes",
]
