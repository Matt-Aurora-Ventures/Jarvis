"""
Task Queue Usage Examples

Demonstrates how to use the async task queue for various long-running operations.
"""

import asyncio
import logging
from datetime import datetime

from core.tasks import (
    TaskQueue,
    get_task_queue,
    start_task_queue,
    queue_report_generation,
    queue_batch_trades,
    queue_historical_analysis,
    queue_maintenance,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# EXAMPLE 1: Basic Task Queue Usage
# =============================================================================

async def example_basic_usage():
    """Basic task queue setup and usage."""
    print("\n=== Example 1: Basic Usage ===")

    # Create and start queue
    queue = TaskQueue(max_workers=3)
    await queue.start()

    # Define a simple task
    async def fetch_data(url: str):
        await asyncio.sleep(0.5)  # Simulate API call
        return f"Data from {url}"

    # Enqueue task
    task_id = await queue.enqueue(fetch_data, url="https://api.example.com")
    print(f"Enqueued task: {task_id}")

    # Wait for result
    result = await queue.get_result(task_id, timeout=10.0)
    print(f"Result: {result.result}")
    print(f"Duration: {result.duration_ms:.2f}ms")

    await queue.stop()


# =============================================================================
# EXAMPLE 2: Progress Tracking
# =============================================================================

async def example_progress_tracking():
    """Demonstrate progress tracking for long tasks."""
    print("\n=== Example 2: Progress Tracking ===")

    queue = TaskQueue(max_workers=2)
    await queue.start()

    # Define task with progress reporting
    async def analyze_tokens(num_tokens: int, progress_callback):
        for i in range(num_tokens):
            await asyncio.sleep(0.1)  # Simulate analysis
            progress = (i + 1) / num_tokens
            progress_callback(progress, f"Analyzed {i+1}/{num_tokens} tokens")
        return {"tokens_analyzed": num_tokens, "status": "complete"}

    # Progress callback
    def on_progress(progress: float, message: str):
        bar_length = 30
        filled = int(bar_length * progress)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\r[{bar}] {progress*100:.1f}% - {message}", end='')

    # Enqueue with progress tracking
    task_id = await queue.enqueue(
        analyze_tokens,
        num_tokens=10,
        on_progress=on_progress
    )

    result = await queue.get_result(task_id, timeout=30.0)
    print(f"\n✓ Complete: {result.result}")

    await queue.stop()


# =============================================================================
# EXAMPLE 3: Callbacks and Error Handling
# =============================================================================

async def example_callbacks():
    """Demonstrate completion and error callbacks."""
    print("\n=== Example 3: Callbacks ===")

    queue = TaskQueue(max_workers=2)
    await queue.start()

    results_log = []

    # Callbacks
    def on_complete(result):
        results_log.append(("success", result))
        print(f"✓ Task completed: {result}")

    def on_error(error):
        results_log.append(("error", str(error)))
        print(f"✗ Task failed: {error}")

    # Successful task
    async def success_task():
        await asyncio.sleep(0.2)
        return "Success!"

    # Failing task
    async def failing_task():
        await asyncio.sleep(0.1)
        raise ValueError("Something went wrong")

    # Enqueue both
    task1 = await queue.enqueue(success_task, on_complete=on_complete)
    task2 = await queue.enqueue(
        failing_task,
        max_retries=2,
        retry_delay=0.1,
        on_error=on_error
    )

    # Wait for both
    await queue.get_result(task1, timeout=5.0)
    await queue.get_result(task2, timeout=5.0)
    await asyncio.sleep(0.2)  # Give callbacks time

    print(f"\nResults log: {len(results_log)} entries")

    await queue.stop()


# =============================================================================
# EXAMPLE 4: Priority Queue
# =============================================================================

async def example_priority():
    """Demonstrate priority-based execution."""
    print("\n=== Example 4: Priority Queue ===")

    queue = TaskQueue(max_workers=1)  # Single worker to see priority
    await queue.start()

    execution_order = []

    async def tracked_task(name: str, duration: float = 0.1):
        execution_order.append(name)
        await asyncio.sleep(duration)
        print(f"  Executed: {name}")
        return name

    # Enqueue with different priorities (lower number = higher priority)
    await queue.enqueue(tracked_task, "Low Priority", priority=10)
    await queue.enqueue(tracked_task, "High Priority", priority=1)
    await queue.enqueue(tracked_task, "Medium Priority", priority=5)
    await queue.enqueue(tracked_task, "Urgent!", priority=0)

    await asyncio.sleep(1.0)  # Let them execute

    print(f"Execution order: {execution_order}")
    print("Note: Higher priority (lower number) executes first")

    await queue.stop()


# =============================================================================
# EXAMPLE 5: Scheduled Tasks
# =============================================================================

async def example_scheduled():
    """Demonstrate scheduled task execution."""
    print("\n=== Example 5: Scheduled Tasks ===")

    queue = TaskQueue(max_workers=2)
    await queue.start()

    async def scheduled_report(report_type: str):
        print(f"Generating {report_type} report at {datetime.now().strftime('%H:%M:%S')}")
        await asyncio.sleep(0.2)
        return f"{report_type} report generated"

    print(f"Current time: {datetime.now().strftime('%H:%M:%S')}")

    # Schedule tasks for future execution
    task1 = await queue.enqueue(
        scheduled_report,
        report_type="hourly",
        delay=1.0  # Execute in 1 second
    )

    task2 = await queue.enqueue(
        scheduled_report,
        report_type="daily",
        delay=2.0  # Execute in 2 seconds
    )

    print("Tasks scheduled, waiting...")

    await queue.get_result(task1, timeout=5.0)
    await queue.get_result(task2, timeout=5.0)

    await queue.stop()


# =============================================================================
# EXAMPLE 6: Batch Operations
# =============================================================================

async def example_batch_processing():
    """Demonstrate batch processing with progress."""
    print("\n=== Example 6: Batch Processing ===")

    queue = TaskQueue(max_workers=3)
    await queue.start()

    # Simulate batch trade execution
    trades = [
        {"token": "SOL", "action": "buy", "amount": 1.0},
        {"token": "USDC", "action": "buy", "amount": 100.0},
        {"token": "BONK", "action": "sell", "amount": 1000.0},
    ]

    async def execute_trade(trade: dict, progress_callback):
        await asyncio.sleep(0.3)  # Simulate execution
        progress_callback(1.0, f"Executed {trade['action']} {trade['token']}")
        return {"status": "filled", "trade": trade}

    # Execute all trades in parallel
    task_ids = []
    for trade in trades:
        task_id = await queue.enqueue(
            execute_trade,
            trade=trade,
            task_type="trade"
        )
        task_ids.append(task_id)
        print(f"Queued: {trade['action']} {trade['token']}")

    # Collect results
    results = []
    for task_id in task_ids:
        result = await queue.get_result(task_id, timeout=5.0)
        results.append(result.result)

    print(f"\n✓ Completed {len(results)}/{len(trades)} trades")

    await queue.stop()


# =============================================================================
# EXAMPLE 7: Using Pre-built Long-Running Tasks
# =============================================================================

async def example_long_running_tasks():
    """Demonstrate using pre-built long-running tasks."""
    print("\n=== Example 7: Long-Running Tasks ===")

    # Use global queue
    await start_task_queue()
    queue = get_task_queue()

    # Queue a treasury report
    print("Queueing treasury report...")
    task_id = await queue_report_generation(
        queue,
        period="weekly",
        on_complete=lambda result: print(f"✓ Report complete: {result.get('report_id')}")
    )

    print(f"Task queued: {task_id}")
    print("Monitoring progress...")

    # Monitor progress
    while True:
        progress = queue.get_progress(task_id)
        if progress:
            print(f"  {progress['status']}: {progress.get('progress', 0)*100:.0f}%")

            if progress['status'] in ('completed', 'failed'):
                break

        await asyncio.sleep(0.5)

    result = await queue.get_result(task_id, timeout=60.0)
    print(f"Final status: {result.status.value}")

    await stop_task_queue()


# =============================================================================
# EXAMPLE 8: Queue Statistics and Monitoring
# =============================================================================

async def example_monitoring():
    """Demonstrate queue monitoring and statistics."""
    print("\n=== Example 8: Queue Monitoring ===")

    queue = TaskQueue(max_workers=3)
    await queue.start()

    async def work(duration: float):
        await asyncio.sleep(duration)
        return "done"

    # Enqueue various tasks
    for i in range(10):
        await queue.enqueue(work, duration=0.1 * (i + 1))

    # Monitor queue stats
    for _ in range(5):
        await asyncio.sleep(0.3)
        stats = queue.get_stats()

        print(f"\nQueue Stats:")
        print(f"  Enqueued: {stats['enqueued']}")
        print(f"  Completed: {stats['completed']}")
        print(f"  Running: {stats['running']}")
        print(f"  Pending: {stats['pending']}")

        if stats['running'] == 0 and stats['pending'] == 0:
            break

    await queue.stop()


# =============================================================================
# EXAMPLE 9: Task Filtering by Type
# =============================================================================

async def example_task_filtering():
    """Demonstrate filtering tasks by type."""
    print("\n=== Example 9: Task Type Filtering ===")

    queue = TaskQueue(max_workers=3)
    await queue.start()

    async def generic_task(task_type: str):
        await asyncio.sleep(0.2)
        return f"{task_type} complete"

    # Enqueue different types
    await queue.enqueue(generic_task, "report", task_type="report")
    await queue.enqueue(generic_task, "analysis", task_type="analysis")
    await queue.enqueue(generic_task, "report", task_type="report")
    await queue.enqueue(generic_task, "maintenance", task_type="maintenance")

    await asyncio.sleep(0.5)

    # Filter by type
    reports = queue.get_tasks_by_type("report")
    analyses = queue.get_tasks_by_type("analysis")

    print(f"Report tasks: {len(reports)}")
    print(f"Analysis tasks: {len(analyses)}")

    await queue.stop()


# =============================================================================
# EXAMPLE 10: Decorator Pattern
# =============================================================================

async def example_decorator():
    """Demonstrate using @task decorator."""
    print("\n=== Example 10: Task Decorator ===")

    from core.tasks import task

    queue = TaskQueue(max_workers=2)
    await queue.start()

    # Define tasks using decorator
    @task(queue, retry=3, priority=1)
    async def important_calculation(x: int, y: int):
        await asyncio.sleep(0.1)
        return x * y

    @task(queue, priority=5)
    async def background_cleanup(items: int):
        await asyncio.sleep(0.2)
        return f"Cleaned {items} items"

    # Use .delay() to enqueue
    calc_task = await important_calculation.delay(x=42, y=2)
    cleanup_task = await background_cleanup.delay(items=100)

    # Wait for results
    calc_result = await queue.get_result(calc_task, timeout=5.0)
    cleanup_result = await queue.get_result(cleanup_task, timeout=5.0)

    print(f"Calculation: {calc_result.result}")
    print(f"Cleanup: {cleanup_result.result}")

    await queue.stop()


# =============================================================================
# RUN ALL EXAMPLES
# =============================================================================

async def run_all_examples():
    """Run all examples."""
    examples = [
        example_basic_usage,
        example_progress_tracking,
        example_callbacks,
        example_priority,
        example_scheduled,
        example_batch_processing,
        # example_long_running_tasks,  # Requires actual implementations
        example_monitoring,
        example_task_filtering,
        example_decorator,
    ]

    for example in examples:
        try:
            await example()
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"\nExample failed: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("Task Queue Examples")
    print("=" * 60)

    asyncio.run(run_all_examples())

    print("\n" + "=" * 60)
    print("All examples complete!")
    print("=" * 60)
