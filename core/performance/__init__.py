"""Performance optimization utilities."""
from core.performance.profiler import (
    Profiler, profile, profile_async,
    profile_block, profile_performance,
    get_profiler_results, reset_profiler,
    export_results_json, export_results_csv, export_results_table,
    MemoryLeakDetector,
    run_benchmark, run_async_benchmark,
    PerformanceTracker, get_performance_tracker, track_performance,
)
from core.performance.query_optimizer import QueryOptimizer, analyze_query
from core.performance.lazy_loader import LazyLoader, lazy_import
from core.performance.uvloop_setup import install_uvloop, get_event_loop_policy
from core.performance.fast_json import (
    dumps, loads, dumps_str,
    HAS_ORJSON, HAS_MSGSPEC,
    get_json_performance_info,
)
from core.performance.metrics_collector import (
    MetricsCollector,
    PerformanceBaselines,
    get_metrics_collector,
    record_metric,
    generate_regression_report,
)
from core.performance.memory_monitor import (
    MemoryMonitor,
    MemorySnapshot,
    MemoryAlert,
    memory_monitor,
)

__all__ = [
    # Profiler
    "Profiler", "profile", "profile_async",
    "profile_block", "profile_performance",
    "get_profiler_results", "reset_profiler",
    "export_results_json", "export_results_csv", "export_results_table",
    "MemoryLeakDetector",
    "run_benchmark", "run_async_benchmark",
    "PerformanceTracker", "get_performance_tracker", "track_performance",
    # Query optimizer
    "QueryOptimizer", "analyze_query",
    # Lazy loading
    "LazyLoader", "lazy_import",
    # Event loop
    "install_uvloop", "get_event_loop_policy",
    # Fast JSON
    "dumps", "loads", "dumps_str",
    "HAS_ORJSON", "HAS_MSGSPEC",
    "get_json_performance_info",
    # Metrics collector
    "MetricsCollector",
    "PerformanceBaselines",
    "get_metrics_collector",
    "record_metric",
    "generate_regression_report",
    # Memory monitor
    "MemoryMonitor",
    "MemorySnapshot",
    "MemoryAlert",
    "memory_monitor",
]
