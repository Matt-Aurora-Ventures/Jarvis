"""Background task queue."""
import asyncio
import uuid
import time
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    id: str
    name: str
    kwargs: Dict[str, Any]
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    created_at: float = field(default_factory=time.time)
    started_at: float = 0
    completed_at: float = 0
    progress: float = 0


class TaskQueue:
    """Async task queue for background processing."""
    
    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.tasks: Dict[str, Task] = {}
        self.handlers: Dict[str, Callable] = {}
        self._queue: asyncio.Queue = None
        self._workers: List[asyncio.Task] = []
        self._running = False
    
    def register(self, name: str, handler: Callable):
        self.handlers[name] = handler
    
    async def start(self):
        if self._running:
            return
        self._running = True
        self._queue = asyncio.Queue()
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(self.max_workers)]
        logger.info(f"Task queue started with {self.max_workers} workers")
    
    async def stop(self):
        self._running = False
        for worker in self._workers:
            worker.cancel()
        self._workers = []
    
    async def enqueue(self, task_name: str, **kwargs) -> str:
        if task_name not in self.handlers:
            raise ValueError(f"Unknown task: {task_name}")
        
        task_id = uuid.uuid4().hex[:12]
        task = Task(id=task_id, name=task_name, kwargs=kwargs)
        self.tasks[task_id] = task
        
        if self._queue:
            await self._queue.put(task_id)
        
        logger.info(f"Task enqueued: {task_name} ({task_id})")
        return task_id
    
    def get_status(self, task_id: str) -> Optional[Dict]:
        task = self.tasks.get(task_id)
        if not task:
            return None
        return {
            "id": task.id, "name": task.name, "status": task.status.value,
            "progress": task.progress, "result": task.result, "error": task.error,
            "created_at": task.created_at, "started_at": task.started_at, "completed_at": task.completed_at
        }
    
    def cancel(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if task and task.status == TaskStatus.PENDING:
            task.status = TaskStatus.CANCELLED
            return True
        return False
    
    async def _worker(self, worker_id: int):
        while self._running:
            try:
                task_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                task = self.tasks.get(task_id)
                
                if not task or task.status == TaskStatus.CANCELLED:
                    continue
                
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()
                
                try:
                    handler = self.handlers[task.name]
                    if asyncio.iscoroutinefunction(handler):
                        task.result = await handler(**task.kwargs)
                    else:
                        task.result = handler(**task.kwargs)
                    task.status = TaskStatus.COMPLETED
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    logger.error(f"Task {task_id} failed: {e}")
                finally:
                    task.completed_at = time.time()
                    task.progress = 1.0
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    def cleanup(self, max_age: float = 3600):
        cutoff = time.time() - max_age
        to_remove = [tid for tid, t in self.tasks.items() 
                    if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED) 
                    and t.completed_at < cutoff]
        for tid in to_remove:
            del self.tasks[tid]
        return len(to_remove)


_task_queue: Optional[TaskQueue] = None


def get_task_queue() -> TaskQueue:
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue
