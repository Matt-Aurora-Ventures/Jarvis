"""
Mock Implementations for ClawdBot Testing

Provides mock implementations of:
- Telegram Bot API
- LLM Client
- Storage
- Scheduler
"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Callable, Awaitable, Union
from dataclasses import dataclass, field
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock


@dataclass
class MockTelegramMessage:
    """Mock message returned from Telegram API."""
    message_id: int
    chat_id: int
    text: str
    date: datetime = field(default_factory=datetime.utcnow)


class MockTelegramBot:
    """
    Mock Telegram Bot API for testing.

    Simulates telebot.async_telebot.AsyncTeleBot behavior
    without making actual API calls.

    Usage:
        bot = MockTelegramBot()
        await bot.send_message(123, "Hello")
        assert len(bot.sent_messages) == 1
        assert bot.sent_messages[0]["text"] == "Hello"
    """

    def __init__(self):
        self.sent_messages: List[Dict[str, Any]] = []
        self.edited_messages: List[Dict[str, Any]] = []
        self.deleted_messages: List[Dict[str, Any]] = []
        self.sent_photos: List[Dict[str, Any]] = []
        self.sent_documents: List[Dict[str, Any]] = []
        self.callback_answers: List[Dict[str, Any]] = []
        self._message_id_counter = 1000
        self._handlers: Dict[str, List[Callable]] = {
            "message": [],
            "callback_query": [],
        }
        self._response_hooks: List[Callable] = []

    def _next_message_id(self) -> int:
        """Generate next message ID."""
        self._message_id_counter += 1
        return self._message_id_counter

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: Optional[str] = None,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[Any] = None,
        disable_notification: bool = False,
        **kwargs
    ) -> MockTelegramMessage:
        """Mock send_message."""
        msg_id = self._next_message_id()
        msg = {
            "message_id": msg_id,
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_to_message_id": reply_to_message_id,
            "reply_markup": reply_markup,
            "disable_notification": disable_notification,
            "timestamp": datetime.utcnow(),
            **kwargs,
        }
        self.sent_messages.append(msg)

        # Call response hooks
        for hook in self._response_hooks:
            hook(msg)

        return MockTelegramMessage(
            message_id=msg_id,
            chat_id=chat_id,
            text=text,
        )

    async def reply_to(
        self,
        message: Any,
        text: str,
        **kwargs
    ) -> MockTelegramMessage:
        """Mock reply_to (convenience method from telebot)."""
        chat_id = message.chat.id if hasattr(message, 'chat') else message.get('chat', {}).get('id')
        message_id = message.message_id if hasattr(message, 'message_id') else message.get('message_id')

        return await self.send_message(
            chat_id=chat_id,
            text=text,
            reply_to_message_id=message_id,
            **kwargs
        )

    async def edit_message_text(
        self,
        text: str,
        chat_id: Optional[int] = None,
        message_id: Optional[int] = None,
        inline_message_id: Optional[str] = None,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Any] = None,
        **kwargs
    ) -> MockTelegramMessage:
        """Mock edit_message_text."""
        msg = {
            "message_id": message_id,
            "chat_id": chat_id,
            "inline_message_id": inline_message_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": reply_markup,
            "timestamp": datetime.utcnow(),
            **kwargs,
        }
        self.edited_messages.append(msg)

        return MockTelegramMessage(
            message_id=message_id or 0,
            chat_id=chat_id or 0,
            text=text,
        )

    async def delete_message(
        self,
        chat_id: int,
        message_id: int,
    ) -> bool:
        """Mock delete_message."""
        self.deleted_messages.append({
            "chat_id": chat_id,
            "message_id": message_id,
            "timestamp": datetime.utcnow(),
        })
        return True

    async def send_photo(
        self,
        chat_id: int,
        photo: Any,
        caption: Optional[str] = None,
        **kwargs
    ) -> MockTelegramMessage:
        """Mock send_photo."""
        msg_id = self._next_message_id()
        self.sent_photos.append({
            "message_id": msg_id,
            "chat_id": chat_id,
            "photo": str(photo),
            "caption": caption,
            "timestamp": datetime.utcnow(),
            **kwargs,
        })
        return MockTelegramMessage(
            message_id=msg_id,
            chat_id=chat_id,
            text=caption or "",
        )

    async def send_document(
        self,
        chat_id: int,
        document: Any,
        caption: Optional[str] = None,
        **kwargs
    ) -> MockTelegramMessage:
        """Mock send_document."""
        msg_id = self._next_message_id()
        self.sent_documents.append({
            "message_id": msg_id,
            "chat_id": chat_id,
            "document": str(document),
            "caption": caption,
            "timestamp": datetime.utcnow(),
            **kwargs,
        })
        return MockTelegramMessage(
            message_id=msg_id,
            chat_id=chat_id,
            text=caption or "",
        )

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False,
        **kwargs
    ) -> bool:
        """Mock answer_callback_query."""
        self.callback_answers.append({
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert,
            "timestamp": datetime.utcnow(),
            **kwargs,
        })
        return True

    async def get_me(self) -> Dict[str, Any]:
        """Mock get_me."""
        return {
            "id": 123456789,
            "is_bot": True,
            "first_name": "TestBot",
            "username": "test_bot",
        }

    async def remove_webhook(self) -> bool:
        """Mock remove_webhook."""
        return True

    async def infinity_polling(self, **kwargs) -> None:
        """Mock infinity_polling - does nothing in tests."""
        pass

    def message_handler(self, **kwargs) -> Callable:
        """Decorator for message handlers."""
        def decorator(func: Callable) -> Callable:
            self._handlers["message"].append({
                "func": func,
                "filters": kwargs,
            })
            return func
        return decorator

    def callback_query_handler(self, **kwargs) -> Callable:
        """Decorator for callback query handlers."""
        def decorator(func: Callable) -> Callable:
            self._handlers["callback_query"].append({
                "func": func,
                "filters": kwargs,
            })
            return func
        return decorator

    def add_response_hook(self, hook: Callable[[Dict], None]) -> None:
        """Add a hook to be called when messages are sent."""
        self._response_hooks.append(hook)

    def get_last_sent_message(self) -> Optional[Dict[str, Any]]:
        """Get the last sent message."""
        return self.sent_messages[-1] if self.sent_messages else None

    def get_sent_texts(self) -> List[str]:
        """Get all sent message texts."""
        return [m["text"] for m in self.sent_messages]

    def reset(self) -> None:
        """Reset all captured data."""
        self.sent_messages.clear()
        self.edited_messages.clear()
        self.deleted_messages.clear()
        self.sent_photos.clear()
        self.sent_documents.clear()
        self.callback_answers.clear()


class MockLLMClient:
    """
    Mock LLM client for testing.

    Simulates LLM API calls without making actual requests.

    Usage:
        llm = MockLLMClient()
        llm.set_response("This is a test response")
        result = await llm.generate("Test prompt")
        assert result["text"] == "This is a test response"
    """

    def __init__(self):
        self._response: str = "Mock LLM response"
        self._responses: List[str] = []
        self._response_index: int = 0
        self.calls: List[Dict[str, Any]] = []
        self._should_fail: bool = False
        self._failure_message: str = "Mock LLM failure"
        self._tokens_used: int = 100
        self._model: str = "mock-model"
        self._latency: float = 0.0

    def set_response(self, response: str) -> None:
        """Set the response to return."""
        self._response = response

    def set_responses(self, responses: List[str]) -> None:
        """Set multiple responses to return in sequence."""
        self._responses = responses
        self._response_index = 0

    def set_failure(self, should_fail: bool, message: str = "Mock LLM failure") -> None:
        """Configure the client to fail on calls."""
        self._should_fail = should_fail
        self._failure_message = message

    def set_latency(self, seconds: float) -> None:
        """Set simulated latency for calls."""
        self._latency = seconds

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs
    ) -> Dict[str, Any]:
        """Mock LLM generation."""
        # Record the call
        self.calls.append({
            "method": "generate",
            "prompt": prompt,
            "model": model or self._model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timestamp": datetime.utcnow(),
            **kwargs,
        })

        # Simulate latency
        if self._latency > 0:
            await asyncio.sleep(self._latency)

        # Handle failure
        if self._should_fail:
            raise Exception(self._failure_message)

        # Get response
        if self._responses:
            response = self._responses[self._response_index % len(self._responses)]
            self._response_index += 1
        else:
            response = self._response

        return {
            "text": response,
            "tokens": self._tokens_used,
            "model": model or self._model,
            "prompt_tokens": len(prompt.split()) * 2,
            "completion_tokens": len(response.split()) * 2,
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Mock chat completion."""
        # Convert messages to prompt for recording
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        return await self.generate(prompt, **kwargs)

    async def health_check(self) -> bool:
        """Mock health check."""
        return not self._should_fail

    def get_last_prompt(self) -> Optional[str]:
        """Get the last prompt sent to the LLM."""
        if self.calls:
            return self.calls[-1]["prompt"]
        return None

    def was_called(self, method: str = "generate") -> bool:
        """Check if a method was called."""
        return any(c["method"] == method for c in self.calls)

    def call_count(self) -> int:
        """Get total number of calls."""
        return len(self.calls)

    def reset(self) -> None:
        """Reset mock state."""
        self.calls.clear()
        self._response_index = 0
        self._should_fail = False


class MockStorage:
    """
    Mock storage for testing.

    Provides in-memory storage that mimics database/file operations.

    Usage:
        storage = MockStorage()
        await storage.set("user:123", {"name": "Test"})
        data = await storage.get("user:123")
    """

    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._collections: Dict[str, List[Dict]] = {}
        self.operations: List[Dict[str, Any]] = []

    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        self.operations.append({
            "type": "get",
            "key": key,
            "timestamp": datetime.utcnow(),
        })
        return self._data.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """Set a value by key."""
        self.operations.append({
            "type": "set",
            "key": key,
            "value": value,
            "ttl": ttl,
            "timestamp": datetime.utcnow(),
        })
        self._data[key] = value

    async def delete(self, key: str) -> bool:
        """Delete a value by key."""
        self.operations.append({
            "type": "delete",
            "key": key,
            "timestamp": datetime.utcnow(),
        })
        if key in self._data:
            del self._data[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        return key in self._data

    async def keys(self, pattern: str = "*") -> List[str]:
        """Get keys matching a pattern."""
        import fnmatch
        return [k for k in self._data.keys() if fnmatch.fnmatch(k, pattern)]

    # Collection operations (for database-like storage)

    async def insert(self, collection: str, document: Dict) -> Dict:
        """Insert a document into a collection."""
        if collection not in self._collections:
            self._collections[collection] = []

        # Add ID if not present
        if "id" not in document:
            document["id"] = len(self._collections[collection]) + 1

        self._collections[collection].append(document)
        self.operations.append({
            "type": "insert",
            "collection": collection,
            "document": document,
            "timestamp": datetime.utcnow(),
        })
        return document

    async def find(
        self,
        collection: str,
        query: Optional[Dict] = None
    ) -> List[Dict]:
        """Find documents in a collection."""
        if collection not in self._collections:
            return []

        if query is None:
            return self._collections[collection].copy()

        return [
            doc for doc in self._collections[collection]
            if all(doc.get(k) == v for k, v in query.items())
        ]

    async def find_one(
        self,
        collection: str,
        query: Dict
    ) -> Optional[Dict]:
        """Find a single document."""
        results = await self.find(collection, query)
        return results[0] if results else None

    async def update(
        self,
        collection: str,
        query: Dict,
        update: Dict
    ) -> int:
        """Update documents matching query."""
        if collection not in self._collections:
            return 0

        count = 0
        for doc in self._collections[collection]:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update)
                count += 1

        self.operations.append({
            "type": "update",
            "collection": collection,
            "query": query,
            "update": update,
            "count": count,
            "timestamp": datetime.utcnow(),
        })
        return count

    async def delete_many(self, collection: str, query: Dict) -> int:
        """Delete documents matching query."""
        if collection not in self._collections:
            return 0

        original_len = len(self._collections[collection])
        self._collections[collection] = [
            doc for doc in self._collections[collection]
            if not all(doc.get(k) == v for k, v in query.items())
        ]

        count = original_len - len(self._collections[collection])
        self.operations.append({
            "type": "delete_many",
            "collection": collection,
            "query": query,
            "count": count,
            "timestamp": datetime.utcnow(),
        })
        return count

    def get_operations(self, op_type: Optional[str] = None) -> List[Dict]:
        """Get recorded operations, optionally filtered by type."""
        if op_type:
            return [o for o in self.operations if o["type"] == op_type]
        return self.operations

    def reset(self) -> None:
        """Reset all storage."""
        self._data.clear()
        self._collections.clear()
        self.operations.clear()


@dataclass
class ScheduledTask:
    """Represents a scheduled task."""
    id: str
    func: Callable
    run_at: datetime
    interval: Optional[float] = None
    args: tuple = field(default_factory=tuple)
    kwargs: Dict = field(default_factory=dict)
    executed: bool = False
    execution_count: int = 0


class MockScheduler:
    """
    Mock scheduler for testing.

    Allows testing scheduled/periodic tasks with instant execution.

    Usage:
        scheduler = MockScheduler()
        scheduler.schedule(my_task, delay=60)
        await scheduler.run_pending()  # Executes immediately
    """

    def __init__(self):
        self.tasks: List[ScheduledTask] = []
        self._task_id_counter = 0
        self.executed_tasks: List[Dict[str, Any]] = []

    def _next_task_id(self) -> str:
        """Generate next task ID."""
        self._task_id_counter += 1
        return f"task_{self._task_id_counter}"

    def schedule(
        self,
        func: Callable,
        delay: float = 0,
        interval: Optional[float] = None,
        *args,
        **kwargs
    ) -> str:
        """
        Schedule a task for execution.

        Args:
            func: Function to execute
            delay: Delay in seconds before first execution
            interval: Optional interval for repeating tasks
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Task ID
        """
        from datetime import timedelta
        task_id = self._next_task_id()
        task = ScheduledTask(
            id=task_id,
            func=func,
            run_at=datetime.utcnow() + timedelta(seconds=delay),
            interval=interval,
            args=args,
            kwargs=kwargs,
        )
        self.tasks.append(task)
        return task_id

    def schedule_at(
        self,
        func: Callable,
        run_at: datetime,
        *args,
        **kwargs
    ) -> str:
        """Schedule a task for a specific time."""
        task_id = self._next_task_id()
        task = ScheduledTask(
            id=task_id,
            func=func,
            run_at=run_at,
            args=args,
            kwargs=kwargs,
        )
        self.tasks.append(task)
        return task_id

    def cancel(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                del self.tasks[i]
                return True
        return False

    async def run_pending(self) -> List[str]:
        """
        Run all pending tasks immediately.

        In tests, this ignores scheduled times and runs everything.

        Returns:
            List of executed task IDs
        """
        executed_ids = []

        for task in self.tasks:
            if not task.executed or task.interval:
                try:
                    result = task.func(*task.args, **task.kwargs)
                    if asyncio.iscoroutine(result):
                        await result

                    task.executed = True
                    task.execution_count += 1
                    executed_ids.append(task.id)

                    self.executed_tasks.append({
                        "id": task.id,
                        "func": task.func.__name__,
                        "timestamp": datetime.utcnow(),
                        "execution_count": task.execution_count,
                    })
                except Exception as e:
                    self.executed_tasks.append({
                        "id": task.id,
                        "func": task.func.__name__,
                        "timestamp": datetime.utcnow(),
                        "error": str(e),
                    })

        return executed_ids

    async def run_task(self, task_id: str) -> bool:
        """Run a specific task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                result = task.func(*task.args, **task.kwargs)
                if asyncio.iscoroutine(result):
                    await result
                task.executed = True
                task.execution_count += 1
                return True
        return False

    def get_pending_tasks(self) -> List[ScheduledTask]:
        """Get all pending (not yet executed) tasks."""
        return [t for t in self.tasks if not t.executed or t.interval]

    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def was_executed(self, task_id: str) -> bool:
        """Check if a task was executed."""
        task = self.get_task(task_id)
        return task.executed if task else False

    def reset(self) -> None:
        """Reset all scheduler state."""
        self.tasks.clear()
        self.executed_tasks.clear()
        self._task_id_counter = 0
