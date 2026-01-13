"""
JARVIS Async Task Queue

Lightweight async task queue for:
- Background job processing
- Scheduled tasks
- Retry on failure
- Priority queues
- Task persistence (optional)

Usage:
    from core.tasks import TaskQueue, task

    queue = TaskQueue()

    @task(queue, retry=3, priority=1)
    async def send_notification(user_id: int, message: str):
        await notification_service.send(user_id, message)

    # Enqueue task
    await queue.enqueue(send_notification, user_id=123, message="Hello!")

    # Or use decorator directly
    await send_notification.delay(user_id=123, message="Hello!")
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from heapq import heappush, heappop
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Result of task execution."""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    attempts: int = 0

    @property
    def duration_ms(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return None


@dataclass(order=True)
class Task:
    """A queued task."""
    priority: int
    created_at: float
    task_id: str = field(compare=False)
    func: Callable = field(compare=False)
    args: tuple = field(compare=False, default_factory=tuple)
    kwargs: dict = field(compare=False, default_factory=dict)
    max_retries: int = field(compare=False, default=0)
    retry_delay: float = field(compare=False, default=1.0)
    timeout: Optional[float] = field(compare=False, default=None)
    attempts: int = field(compare=False, default=0)
    scheduled_at: Optional[float] = field(compare=False, default=None)

    def __post_init__(self):
        if not self.task_id:
            self.task_id = str(uuid.uuid4())[:8]


class TaskQueue:
    """
    Async task queue with priority support.

    Features:
    - Priority-based execution
    - Configurable concurrency
    - Retry on failure
    - Scheduled tasks
    - Task tracking
    """

    def __init__(
        self,
        max_workers: int = 5,
        max_queue_size: int = 1000,
        default_timeout: float = 300.0,
    ):
        self.max_workers = max_workers
        self.max_queue_size = max_queue_size
        self.default_timeout = default_timeout

        self._queue: List[Task] = []  # Priority heap
        self._scheduled: List[Task] = []  # Scheduled tasks heap
        self._running: Dict[str, Task] = {}
        self._results: Dict[str, TaskResult] = {}
        self._workers: List[asyncio.Task] = []
        self._running_flag = False
        self._lock = asyncio.Lock()
        self._event = asyncio.Event()

        # Stats
        self._stats = {
            "enqueued": 0,
            "completed": 0,
            "failed": 0,
            "retried": 0,
        }

    async def start(self):
        """Start the task queue workers."""
        if self._running_flag:
            return

        self._running_flag = True
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self.max_workers)
        ]

        # Start scheduler
        self._scheduler_task = asyncio.create_task(self._scheduler())
        logger.info(f"TaskQueue started with {self.max_workers} workers")

    async def stop(self, wait: bool = True, timeout: float = 30.0):
        """Stop the task queue."""
        self._running_flag = False
        self._event.set()

        if wait:
            # Wait for workers to finish
            if self._workers:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self._workers, return_exceptions=True),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    for worker in self._workers:
                        worker.cancel()

        if hasattr(self, '_scheduler_task'):
            self._scheduler_task.cancel()

        logger.info("TaskQueue stopped")

    async def enqueue(
        self,
        func: Callable,
        *args,
        priority: int = 5,
        max_retries: int = 0,
        retry_delay: float = 1.0,
        timeout: Optional[float] = None,
        delay: float = 0,
        **kwargs
    ) -> str:
        """
        Add a task to the queue.

        Args:
            func: Async function to execute
            *args: Positional arguments
            priority: Task priority (lower = higher priority)
            max_retries: Maximum retry attempts
            retry_delay: Delay between retries
            timeout: Task timeout
            delay: Delay before execution (seconds)
            **kwargs: Keyword arguments

        Returns:
            Task ID
        """
        async with self._lock:
            if len(self._queue) + len(self._scheduled) >= self.max_queue_size:
                raise RuntimeError("Task queue is full")

        task = Task(
            priority=priority,
            created_at=time.time(),
            task_id=str(uuid.uuid4())[:8],
            func=func,
            args=args,
            kwargs=kwargs,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout or self.default_timeout,
            scheduled_at=time.time() + delay if delay > 0 else None,
        )

        async with self._lock:
            if task.scheduled_at:
                heappush(self._scheduled, (task.scheduled_at, task))
            else:
                heappush(self._queue, task)

            self._results[task.task_id] = TaskResult(
                task_id=task.task_id,
                status=TaskStatus.PENDING,
            )
            self._stats["enqueued"] += 1

        self._event.set()
        logger.debug(f"Task {task.task_id} enqueued (priority={priority})")
        return task.task_id

    async def get_result(
        self,
        task_id: str,
        timeout: Optional[float] = None
    ) -> Optional[TaskResult]:
        """Wait for and return task result."""
        start = time.time()

        while True:
            result = self._results.get(task_id)
            if result and result.status in (
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.CANCELLED
            ):
                return result

            if timeout and (time.time() - start) > timeout:
                return None

            await asyncio.sleep(0.1)

    def get_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status."""
        result = self._results.get(task_id)
        return result.status if result else None

    async def cancel(self, task_id: str) -> bool:
        """Cancel a pending task."""
        async with self._lock:
            # Check scheduled tasks
            for i, (_, task) in enumerate(self._scheduled):
                if task.task_id == task_id:
                    self._scheduled.pop(i)
                    self._results[task_id].status = TaskStatus.CANCELLED
                    return True

            # Check pending tasks
            for i, task in enumerate(self._queue):
                if task.task_id == task_id:
                    self._queue.pop(i)
                    self._results[task_id].status = TaskStatus.CANCELLED
                    return True

        return False

    async def _worker(self, worker_id: int):
        """Worker coroutine that processes tasks."""
        logger.debug(f"Worker {worker_id} started")

        while self._running_flag:
            task = await self._get_next_task()
            if task is None:
                continue

            await self._execute_task(task)

        logger.debug(f"Worker {worker_id} stopped")

    async def _get_next_task(self) -> Optional[Task]:
        """Get next task from queue."""
        while self._running_flag:
            async with self._lock:
                if self._queue:
                    return heappop(self._queue)

            # Wait for new tasks
            self._event.clear()
            try:
                await asyncio.wait_for(self._event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                pass

        return None

    async def _execute_task(self, task: Task):
        """Execute a task with retry support."""
        task.attempts += 1
        result = self._results[task.task_id]
        result.status = TaskStatus.RUNNING
        result.started_at = time.time()
        result.attempts = task.attempts

        self._running[task.task_id] = task

        try:
            # Execute with timeout
            if asyncio.iscoroutinefunction(task.func):
                task_result = await asyncio.wait_for(
                    task.func(*task.args, **task.kwargs),
                    timeout=task.timeout
                )
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                task_result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: task.func(*task.args, **task.kwargs)
                    ),
                    timeout=task.timeout
                )

            result.status = TaskStatus.COMPLETED
            result.result = task_result
            self._stats["completed"] += 1
            logger.debug(f"Task {task.task_id} completed")

        except asyncio.TimeoutError:
            result.error = "Task timed out"
            await self._handle_failure(task, result, "timeout")

        except Exception as e:
            result.error = str(e)
            await self._handle_failure(task, result, str(e))

        finally:
            result.completed_at = time.time()
            self._running.pop(task.task_id, None)

    async def _handle_failure(self, task: Task, result: TaskResult, error: str):
        """Handle task failure with retry logic."""
        if task.attempts < task.max_retries:
            result.status = TaskStatus.RETRYING
            self._stats["retried"] += 1
            logger.warning(
                f"Task {task.task_id} failed ({error}), "
                f"retrying in {task.retry_delay}s "
                f"(attempt {task.attempts}/{task.max_retries})"
            )

            # Schedule retry
            await asyncio.sleep(task.retry_delay)
            async with self._lock:
                heappush(self._queue, task)
            self._event.set()
        else:
            result.status = TaskStatus.FAILED
            self._stats["failed"] += 1
            logger.error(f"Task {task.task_id} failed permanently: {error}")

    async def _scheduler(self):
        """Move scheduled tasks to main queue when ready."""
        while self._running_flag:
            now = time.time()

            async with self._lock:
                while self._scheduled and self._scheduled[0][0] <= now:
                    _, task = heappop(self._scheduled)
                    heappush(self._queue, task)
                    self._event.set()

            await asyncio.sleep(0.1)

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            **self._stats,
            "pending": len(self._queue),
            "scheduled": len(self._scheduled),
            "running": len(self._running),
            "max_workers": self.max_workers,
        }

    @property
    def is_running(self) -> bool:
        return self._running_flag


def task(
    queue: TaskQueue,
    priority: int = 5,
    retry: int = 0,
    retry_delay: float = 1.0,
    timeout: Optional[float] = None,
) -> Callable:
    """
    Decorator to register a function as a task.

    Usage:
        queue = TaskQueue()

        @task(queue, retry=3)
        async def process_data(data: dict):
            ...

        # Enqueue
        task_id = await process_data.delay(data={"key": "value"})
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        async def delay(*args, **kwargs) -> str:
            return await queue.enqueue(
                func,
                *args,
                priority=priority,
                max_retries=retry,
                retry_delay=retry_delay,
                timeout=timeout,
                **kwargs
            )

        async def schedule(delay_seconds: float, *args, **kwargs) -> str:
            return await queue.enqueue(
                func,
                *args,
                priority=priority,
                max_retries=retry,
                retry_delay=retry_delay,
                timeout=timeout,
                delay=delay_seconds,
                **kwargs
            )

        wrapper.delay = delay
        wrapper.schedule = schedule
        wrapper.queue = queue
        return wrapper

    return decorator


# Global queue instance
_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    """Get or create the global task queue."""
    global _queue
    if _queue is None:
        _queue = TaskQueue()
    return _queue


async def start_task_queue():
    """Start the global task queue."""
    queue = get_task_queue()
    await queue.start()


async def stop_task_queue():
    """Stop the global task queue."""
    global _queue
    if _queue:
        await _queue.stop()
        _queue = None


if __name__ == "__main__":
    import random

    logging.basicConfig(level=logging.INFO)

    async def demo():
        print("Task Queue Demo")
        print("=" * 50)

        queue = TaskQueue(max_workers=3)
        await queue.start()

        # Define tasks
        @task(queue, retry=2)
        async def process_item(item_id: int):
            await asyncio.sleep(random.uniform(0.1, 0.5))
            if random.random() < 0.3:  # 30% failure rate
                raise Exception("Random failure")
            return f"Processed item {item_id}"

        @task(queue, priority=1)  # High priority
        async def urgent_task(msg: str):
            print(f"URGENT: {msg}")
            return msg

        # Enqueue tasks
        task_ids = []
        for i in range(10):
            task_id = await process_item.delay(item_id=i)
            task_ids.append(task_id)
            print(f"Enqueued task {task_id}")

        # Add urgent task
        await urgent_task.delay(msg="This is urgent!")

        # Schedule a delayed task
        await process_item.schedule(2.0, item_id=99)
        print("Scheduled task for 2 seconds")

        # Wait for results
        print("\nWaiting for results...")
        for task_id in task_ids[:5]:
            result = await queue.get_result(task_id, timeout=10)
            if result:
                print(f"  {task_id}: {result.status.value} - {result.result or result.error}")

        # Show stats
        print(f"\nStats: {queue.get_stats()}")

        await queue.stop()
        print("\nDemo complete!")

    asyncio.run(demo())
