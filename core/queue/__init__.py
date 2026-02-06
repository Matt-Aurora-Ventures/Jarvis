"""
Message Queue System - Async message processing with multiple storage backends.

Provides:
- QueueManager: Central queue operations (enqueue, dequeue, peek)
- Worker: Background message processor with configurable concurrency
- Storage backends: InMemoryQueue, FileQueue, PriorityQueue
- DeadLetterQueue: Failed message handling with retry support

Usage:
    from core.queue import QueueManager, Worker, DeadLetterQueue

    # Create manager with default in-memory storage
    manager = QueueManager()

    # Enqueue messages
    msg_id = await manager.enqueue("tasks", {"action": "process", "data": 123})

    # Create worker to process messages
    async def handler(msg):
        print(f"Processing: {msg.payload}")
        return True

    worker = Worker(manager, "tasks", handler)
    await worker.start()
"""

from core.queue.storage import (
    Message,
    QueueStorage,
    InMemoryQueue,
    FileQueue,
    PriorityQueue,
)
from core.queue.manager import QueueManager
from core.queue.worker import Worker, WorkerConfig
from core.queue.dead_letter import DeadLetterQueue, FailedMessage

__all__ = [
    # Storage
    "Message",
    "QueueStorage",
    "InMemoryQueue",
    "FileQueue",
    "PriorityQueue",
    # Manager
    "QueueManager",
    # Worker
    "Worker",
    "WorkerConfig",
    # Dead Letter Queue
    "DeadLetterQueue",
    "FailedMessage",
]
