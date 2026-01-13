"""
Timeout Utilities - Async timeout wrappers for operations.
Provides clean timeout handling without external dependencies.
"""

import asyncio
import functools
from typing import TypeVar, Callable, Any, Optional
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class TimeoutError(Exception):
    """Raised when an operation times out."""
    pass


async def with_timeout(
    coro,
    timeout_seconds: float,
    timeout_message: str = "Operation timed out"
) -> Any:
    """
    Execute a coroutine with a timeout.
    
    Args:
        coro: Coroutine to execute
        timeout_seconds: Maximum time to wait
        timeout_message: Message for timeout error
        
    Returns:
        Result of the coroutine
        
    Raises:
        TimeoutError: If operation times out
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise TimeoutError(timeout_message)


async def with_timeout_default(
    coro,
    timeout_seconds: float,
    default: T = None
) -> T:
    """
    Execute a coroutine with a timeout, returning default on timeout.
    
    Args:
        coro: Coroutine to execute
        timeout_seconds: Maximum time to wait
        default: Value to return on timeout
        
    Returns:
        Result of coroutine or default value
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.debug(f"Operation timed out after {timeout_seconds}s, returning default")
        return default


def timeout(seconds: float, default: Any = None, raise_on_timeout: bool = False):
    """
    Decorator to add timeout to an async function.
    
    Args:
        seconds: Timeout in seconds
        default: Default value to return on timeout (if not raising)
        raise_on_timeout: If True, raise TimeoutError; otherwise return default
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                if raise_on_timeout:
                    raise TimeoutError(f"{func.__name__} timed out after {seconds}s")
                logger.debug(f"{func.__name__} timed out after {seconds}s")
                return default
        return wrapper
    return decorator


async def race(*coros, timeout_seconds: float = None) -> Any:
    """
    Run multiple coroutines and return the first result.
    
    Args:
        *coros: Coroutines to race
        timeout_seconds: Optional timeout for all
        
    Returns:
        Result of the first coroutine to complete
    """
    tasks = [asyncio.create_task(c) for c in coros]
    
    try:
        done, pending = await asyncio.wait(
            tasks,
            timeout=timeout_seconds,
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
        
        if done:
            return done.pop().result()
        
        raise TimeoutError("All coroutines timed out")
        
    except Exception:
        # Cancel all tasks on error
        for task in tasks:
            task.cancel()
        raise


async def retry_with_timeout(
    func: Callable,
    timeout_seconds: float,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> Any:
    """
    Retry a function with timeout on each attempt.
    
    Args:
        func: Async function to call
        timeout_seconds: Timeout per attempt
        max_retries: Maximum retry attempts
        retry_delay: Delay between retries
        
    Returns:
        Result of successful call
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return await with_timeout(func(), timeout_seconds)
        except (TimeoutError, asyncio.TimeoutError) as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
    
    raise last_error or TimeoutError("All retries failed")
