"""
Utility Decorators - Common decorators for robustness and performance.
"""

import asyncio
import functools
import time
import logging
from typing import Callable, Any, Optional, TypeVar, Type, Tuple

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum retry attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        logger.debug(f"{func.__name__} attempt {attempt + 1} failed: {e}, retrying in {current_delay}s")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_error
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_error = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < max_attempts - 1:
                        logger.debug(f"{func.__name__} attempt {attempt + 1} failed: {e}, retrying in {current_delay}s")
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_error
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def log_calls(level: int = logging.DEBUG):
    """
    Log function calls with arguments and results.
    
    Args:
        level: Logging level
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            logger.log(level, f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            try:
                result = await func(*args, **kwargs)
                logger.log(level, f"{func.__name__} returned {type(result).__name__}")
                return result
            except Exception as e:
                logger.log(level, f"{func.__name__} raised {type(e).__name__}: {e}")
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            logger.log(level, f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
            try:
                result = func(*args, **kwargs)
                logger.log(level, f"{func.__name__} returned {type(result).__name__}")
                return result
            except Exception as e:
                logger.log(level, f"{func.__name__} raised {type(e).__name__}: {e}")
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def memoize(ttl_seconds: float = 300):
    """
    Memoize function results with TTL.
    
    Args:
        ttl_seconds: Time to live for cached results
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            
            if key in cache:
                result, cached_at = cache[key]
                if now - cached_at < ttl_seconds:
                    return result
            
            result = await func(*args, **kwargs)
            cache[key] = (result, now)
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            
            if key in cache:
                result, cached_at = cache[key]
                if now - cached_at < ttl_seconds:
                    return result
            
            result = func(*args, **kwargs)
            cache[key] = (result, now)
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


def singleton(cls: Type[T]) -> Type[T]:
    """
    Singleton decorator for classes.
    """
    instances = {}
    
    @functools.wraps(cls)
    def get_instance(*args, **kwargs) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]
    
    return get_instance


def deprecated(message: str = ""):
    """
    Mark a function as deprecated.
    
    Args:
        message: Deprecation message
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import warnings
            warnings.warn(
                f"{func.__name__} is deprecated. {message}",
                DeprecationWarning,
                stacklevel=2
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator


def measure_time(func: Callable) -> Callable:
    """
    Measure and log execution time of a function.
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        try:
            return await func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            logger.debug(f"{func.__name__} took {elapsed:.3f}s")
    
    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            logger.debug(f"{func.__name__} took {elapsed:.3f}s")
    
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
