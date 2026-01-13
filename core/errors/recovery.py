"""Error recovery strategies."""
import asyncio
import time
from typing import Callable, TypeVar, Optional, Any
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RecoveryStrategy:
    """Collection of error recovery strategies."""
    
    @staticmethod
    async def retry(func: Callable, max_attempts: int = 3, delay: float = 1.0) -> T:
        last_error = None
        for attempt in range(max_attempts):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func()
                return func()
            except Exception as e:
                last_error = e
                if attempt < max_attempts - 1:
                    wait = delay * (2 ** attempt)
                    logger.warning(f"Attempt {attempt+1} failed, retrying in {wait:.1f}s: {e}")
                    await asyncio.sleep(wait)
        raise last_error
    
    @staticmethod
    async def fallback(func: Callable, fallback_func: Callable) -> T:
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            return func()
        except Exception as e:
            logger.warning(f"Primary failed ({e}), using fallback")
            if asyncio.iscoroutinefunction(fallback_func):
                return await fallback_func()
            return fallback_func()
    
    @staticmethod
    async def timeout(func: Callable, seconds: float) -> T:
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(func(), timeout=seconds)
            return func()
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {seconds}s")
    
    @staticmethod
    async def bulkhead(func: Callable, semaphore: asyncio.Semaphore) -> T:
        async with semaphore:
            if asyncio.iscoroutinefunction(func):
                return await func()
            return func()


def with_recovery(strategy: str = "retry", **strategy_kwargs):
    """Decorator for adding recovery behavior."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            async def call():
                return await func(*args, **kwargs)
            
            if strategy == "retry":
                return await RecoveryStrategy.retry(call, **strategy_kwargs)
            elif strategy == "timeout":
                return await RecoveryStrategy.timeout(call, **strategy_kwargs)
            return await call()
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


class DeadLetterQueue:
    """Queue for failed operations."""
    
    def __init__(self, path: str = "data/dlq"):
        from pathlib import Path
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
    
    def add(self, event_type: str, payload: dict, error: Exception):
        import json
        entry = {
            "timestamp": time.time(), "event_type": event_type,
            "payload": payload, "error": str(error),
            "error_type": type(error).__name__, "retries": 0
        }
        filename = f"{int(time.time()*1000)}_{event_type}.json"
        (self.path / filename).write_text(json.dumps(entry, indent=2))
        logger.error(f"Added to DLQ: {event_type}")
    
    def process(self, handler: Callable) -> int:
        import json
        processed = 0
        for f in self.path.glob("*.json"):
            entry = json.loads(f.read_text())
            if entry["retries"] < 3:
                try:
                    handler(entry["event_type"], entry["payload"])
                    f.unlink()
                    processed += 1
                except Exception as e:
                    entry["retries"] += 1
                    entry["last_error"] = str(e)
                    f.write_text(json.dumps(entry, indent=2))
        return processed


dlq = DeadLetterQueue()
