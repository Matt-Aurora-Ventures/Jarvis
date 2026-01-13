"""Deprecation warnings and utilities."""
import warnings
import functools
from typing import Callable, Optional
import logging

logger = logging.getLogger(__name__)


def deprecated(
    reason: str,
    version: str,
    replacement: Optional[str] = None,
    removal_version: Optional[str] = None
) -> Callable:
    """
    Mark a function as deprecated.
    
    Args:
        reason: Why this is deprecated
        version: Version when deprecated
        replacement: What to use instead
        removal_version: Version when it will be removed
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            message = f"{func.__name__} is deprecated since v{version}: {reason}"
            if replacement:
                message += f" Use {replacement} instead."
            if removal_version:
                message += f" Will be removed in v{removal_version}."
            
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            logger.warning(f"Deprecated function called: {func.__name__}")
            
            return func(*args, **kwargs)
        
        # Update docstring
        deprecation_note = f"\n\n.. deprecated:: {version}\n   {reason}"
        if replacement:
            deprecation_note += f"\n   Use :func:`{replacement}` instead."
        
        wrapper.__doc__ = (func.__doc__ or "") + deprecation_note
        wrapper._deprecated = True
        wrapper._deprecated_version = version
        wrapper._replacement = replacement
        
        return wrapper
    return decorator


def deprecated_parameter(
    param_name: str,
    reason: str,
    version: str,
    replacement: Optional[str] = None
) -> Callable:
    """Mark a function parameter as deprecated."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if param_name in kwargs:
                message = f"Parameter '{param_name}' in {func.__name__} is deprecated since v{version}: {reason}"
                if replacement:
                    message += f" Use '{replacement}' instead."
                warnings.warn(message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class DeprecatedClass:
    """Mixin for deprecated classes."""
    
    _deprecation_message: str = "This class is deprecated"
    _deprecation_version: str = "unknown"
    _replacement: Optional[str] = None
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, '_deprecation_message'):
            message = f"{cls.__name__} is deprecated since v{cls._deprecation_version}: {cls._deprecation_message}"
            if cls._replacement:
                message += f" Use {cls._replacement} instead."
            warnings.warn(message, DeprecationWarning, stacklevel=2)


def get_deprecated_items(module) -> list:
    """Get list of deprecated items in a module."""
    deprecated_items = []
    for name in dir(module):
        obj = getattr(module, name)
        if callable(obj) and getattr(obj, '_deprecated', False):
            deprecated_items.append({
                'name': name,
                'version': getattr(obj, '_deprecated_version', 'unknown'),
                'replacement': getattr(obj, '_replacement', None)
            })
    return deprecated_items
