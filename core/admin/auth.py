"""
Admin Authentication and Authorization.

Provides admin user verification and authorization decorators.

Environment Variables:
    ADMIN_USER_IDS: Comma-separated list of admin user IDs
                   Example: "123456789,987654321"

Usage:
    from core.admin.auth import is_admin, require_admin

    # Check admin status
    if is_admin(user_id):
        print("User is admin")

    # Decorator for protected functions
    @require_admin
    def protected_action(user_id: int, data: str):
        return f"Executed by {user_id}"
"""

import asyncio
import functools
import logging
import os
from typing import Callable, Optional, Set, TypeVar, Union

logger = logging.getLogger(__name__)

# Cached admin user IDs (parsed once)
_admin_user_ids: Optional[Set[int]] = None


class UnauthorizedError(Exception):
    """Raised when a non-admin user attempts an admin action."""

    def __init__(self, user_id: int, action: str = "admin action"):
        self.user_id = user_id
        self.action = action
        super().__init__(f"User {user_id} is not authorized for {action}")


def get_admin_user_ids() -> Set[int]:
    """
    Get the set of admin user IDs from environment.

    Parses ADMIN_USER_IDS environment variable (comma-separated integers).
    Results are cached after first call.

    Returns:
        Set of admin user IDs (empty set if not configured)
    """
    global _admin_user_ids

    if _admin_user_ids is not None:
        return _admin_user_ids

    ids_str = os.getenv("ADMIN_USER_IDS", "")
    if not ids_str:
        _admin_user_ids = set()
        return _admin_user_ids

    ids: Set[int] = set()
    for id_str in ids_str.split(","):
        id_str = id_str.strip()
        if id_str.isdigit():
            ids.add(int(id_str))

    _admin_user_ids = ids
    logger.debug(f"Loaded {len(ids)} admin user IDs")
    return _admin_user_ids


def is_admin(user_id: int) -> bool:
    """
    Check if a user ID is an admin.

    Args:
        user_id: The user ID to check

    Returns:
        True if user is an admin, False otherwise
    """
    admin_ids = get_admin_user_ids()
    return user_id in admin_ids


# Type variable for generic function signature preservation
F = TypeVar("F", bound=Callable)


def require_admin(func: F) -> F:
    """
    Decorator to require admin authorization for a function.

    The decorated function MUST have `user_id` as its first argument
    (after self for methods).

    Raises:
        UnauthorizedError: If the user is not an admin

    Usage:
        @require_admin
        def protected_func(user_id: int, data: str) -> str:
            return f"Success: {data}"

        @require_admin
        async def async_protected(user_id: int) -> str:
            return "Async success"

    Example:
        # For admin user
        result = protected_func(123456789, "test")  # Works

        # For non-admin user
        protected_func(999999999, "test")  # Raises UnauthorizedError
    """
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract user_id from args or kwargs
            user_id = _extract_user_id(args, kwargs)

            if not is_admin(user_id):
                logger.warning(
                    f"Unauthorized admin action attempted by user_id={user_id} "
                    f"on function={func.__name__}"
                )
                raise UnauthorizedError(user_id, func.__name__)

            return await func(*args, **kwargs)

        return async_wrapper  # type: ignore

    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Extract user_id from args or kwargs
            user_id = _extract_user_id(args, kwargs)

            if not is_admin(user_id):
                logger.warning(
                    f"Unauthorized admin action attempted by user_id={user_id} "
                    f"on function={func.__name__}"
                )
                raise UnauthorizedError(user_id, func.__name__)

            return func(*args, **kwargs)

        return sync_wrapper  # type: ignore


def _extract_user_id(args: tuple, kwargs: dict) -> int:
    """
    Extract user_id from function arguments.

    Looks for user_id in kwargs first, then assumes it's the first positional arg.
    """
    if "user_id" in kwargs:
        return kwargs["user_id"]

    if args:
        # First arg might be self for methods, or user_id for functions
        first_arg = args[0]
        if isinstance(first_arg, int):
            return first_arg
        # If first arg is an object (self), try second arg
        if len(args) > 1 and isinstance(args[1], int):
            return args[1]

    raise ValueError("Could not extract user_id from function arguments")


def clear_admin_cache() -> None:
    """
    Clear the cached admin user IDs.

    Useful for testing or when admin IDs change at runtime.
    """
    global _admin_user_ids
    _admin_user_ids = None
    logger.debug("Admin user IDs cache cleared")
