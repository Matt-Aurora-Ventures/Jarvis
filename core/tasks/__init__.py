"""
JARVIS Task Queue Module

Async task queue for background job processing.
"""

from .queue import (
    TaskQueue,
    TaskStatus,
    TaskResult,
    Task,
    task,
    get_task_queue,
    start_task_queue,
    stop_task_queue,
)

from .long_running import (
    generate_treasury_report,
    generate_sentiment_report,
    execute_batch_trades,
    analyze_historical_performance,
    backfill_market_data,
    cleanup_old_data,
    health_check_all_systems,
    queue_report_generation,
    queue_batch_trades,
    queue_historical_analysis,
    queue_maintenance,
)

__all__ = [
    # Queue components
    "TaskQueue",
    "TaskStatus",
    "TaskResult",
    "Task",
    "task",
    "get_task_queue",
    "start_task_queue",
    "stop_task_queue",
    # Long-running tasks
    "generate_treasury_report",
    "generate_sentiment_report",
    "execute_batch_trades",
    "analyze_historical_performance",
    "backfill_market_data",
    "cleanup_old_data",
    "health_check_all_systems",
    # Queue helpers
    "queue_report_generation",
    "queue_batch_trades",
    "queue_historical_analysis",
    "queue_maintenance",
]
