"""Performance optimization utilities."""
from core.performance.profiler import Profiler, profile, profile_async
from core.performance.query_optimizer import QueryOptimizer, analyze_query
from core.performance.lazy_loader import LazyLoader, lazy_import
from core.performance.uvloop_setup import install_uvloop, get_event_loop_policy
from core.performance.fast_json import (
    dumps, loads, dumps_str,
    HAS_ORJSON, HAS_MSGSPEC,
    get_json_performance_info,
)

__all__ = [
    "Profiler", "profile", "profile_async",
    "QueryOptimizer", "analyze_query",
    "LazyLoader", "lazy_import",
    "install_uvloop", "get_event_loop_policy",
    "dumps", "loads", "dumps_str",
    "HAS_ORJSON", "HAS_MSGSPEC",
    "get_json_performance_info",
]
