"""Fallback patterns for graceful degradation."""
import asyncio
from functools import wraps
from typing import Callable, TypeVar, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

_cache: dict[str, Any] = {}


def with_fallback(
    fallback_value: Any = None,
    fallback_func: Callable = None,
    cache_key: str = None,
    cache_ttl: int = 300
):
    """
    Decorator that provides fallback behavior on failure.
    
    Priority:
    1. Try the function
    2. Use cached value if available
    3. Use fallback_func if provided
    4. Use fallback_value
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                if cache_key:
                    _cache[cache_key] = {
                        "value": result,
                        "timestamp": __import__("time").time()
                    }
                
                return result
            
            except Exception as e:
                logger.warning(f"{func.__name__} failed: {e}, using fallback")
                
                if cache_key and cache_key in _cache:
                    cached = _cache[cache_key]
                    age = __import__("time").time() - cached["timestamp"]
                    if age < cache_ttl:
                        logger.info(f"Using cached value for {func.__name__}")
                        return cached["value"]
                
                if fallback_func:
                    if asyncio.iscoroutinefunction(fallback_func):
                        return await fallback_func(*args, **kwargs)
                    return fallback_func(*args, **kwargs)
                
                return fallback_value
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                
                if cache_key:
                    _cache[cache_key] = {
                        "value": result,
                        "timestamp": __import__("time").time()
                    }
                
                return result
            
            except Exception as e:
                logger.warning(f"{func.__name__} failed: {e}, using fallback")
                
                if cache_key and cache_key in _cache:
                    cached = _cache[cache_key]
                    age = __import__("time").time() - cached["timestamp"]
                    if age < cache_ttl:
                        return cached["value"]
                
                if fallback_func:
                    return fallback_func(*args, **kwargs)
                
                return fallback_value
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


class FallbackChain:
    """Execute a chain of fallback functions until one succeeds."""
    
    def __init__(self, *funcs: Callable):
        self.funcs = list(funcs)
    
    def add(self, func: Callable) -> "FallbackChain":
        """Add a function to the chain."""
        self.funcs.append(func)
        return self
    
    async def execute(self, *args, **kwargs) -> Any:
        """Execute the chain until one succeeds."""
        last_error = None
        
        for i, func in enumerate(self.funcs):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                if i > 0:
                    logger.info(f"Fallback {i} succeeded: {func.__name__}")
                
                return result
            
            except Exception as e:
                last_error = e
                logger.warning(f"Function {func.__name__} failed: {e}")
                continue
        
        raise last_error or Exception("All fallbacks failed")
    
    def execute_sync(self, *args, **kwargs) -> Any:
        """Execute the chain synchronously."""
        last_error = None
        
        for i, func in enumerate(self.funcs):
            try:
                result = func(*args, **kwargs)
                
                if i > 0:
                    logger.info(f"Fallback {i} succeeded: {func.__name__}")
                
                return result
            
            except Exception as e:
                last_error = e
                logger.warning(f"Function {func.__name__} failed: {e}")
                continue
        
        raise last_error or Exception("All fallbacks failed")


async def try_multiple(
    funcs: List[Callable],
    args: tuple = (),
    kwargs: dict = None,
    return_first_success: bool = True
) -> Any:
    """Try multiple functions and return results from the first success."""
    kwargs = kwargs or {}
    
    for func in funcs:
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            if return_first_success:
                return result
        except Exception as e:
            logger.debug(f"{func.__name__} failed: {e}")
            continue
    
    raise Exception("All functions failed")
