"""Retry logic with exponential backoff."""
import asyncio
import random
import time
from functools import wraps
from typing import Callable, TypeVar, Type, Tuple, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()


def calculate_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool
) -> float:
    """Calculate delay for a retry attempt."""
    delay = base_delay * (exponential_base ** attempt)
    delay = min(delay, max_delay)
    
    if jitter:
        delay = delay * (0.5 + random.random())
    
    return delay


async def retry_with_backoff(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable[[Exception, int], None] = None
) -> T:
    """
    Execute an async function with retry and exponential backoff.
    """
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func()
            else:
                return func()
        except retryable_exceptions as e:
            last_exception = e
            
            if attempt == max_attempts - 1:
                logger.error(f"All {max_attempts} attempts failed: {e}")
                raise
            
            delay = calculate_delay(attempt, base_delay, max_delay, 2.0, True)
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.2f}s")
            
            if on_retry:
                on_retry(e, attempt)
            
            await asyncio.sleep(delay)
    
    raise last_exception


def with_retry(config: RetryConfig = None):
    """Decorator for adding retry logic to functions."""
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except config.non_retryable_exceptions:
                    raise
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        raise
                    
                    delay = calculate_delay(
                        attempt,
                        config.base_delay,
                        config.max_delay,
                        config.exponential_base,
                        config.jitter
                    )
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}")
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except config.non_retryable_exceptions:
                    raise
                except config.retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        raise
                    
                    delay = calculate_delay(
                        attempt,
                        config.base_delay,
                        config.max_delay,
                        config.exponential_base,
                        config.jitter
                    )
                    logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}")
                    time.sleep(delay)
            
            raise last_exception
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class RetryableError(Exception):
    """Exception that should trigger a retry."""
    pass


class NonRetryableError(Exception):
    """Exception that should not trigger a retry."""
    pass
