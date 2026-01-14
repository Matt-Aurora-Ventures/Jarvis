"""
Custom Test Assertions

Provides custom assertion functions for testing.
"""

import json
import re
import asyncio
from typing import Any, Dict, List, Optional, Callable, Awaitable, Union
from datetime import datetime
from uuid import UUID


def assert_eventually(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str = "Condition was not met"
) -> None:
    """
    Assert that a condition eventually becomes true.

    Usage:
        assert_eventually(lambda: len(items) > 0)
    """
    import time
    start = time.time()

    while time.time() - start < timeout:
        if condition():
            return
        time.sleep(interval)

    raise AssertionError(f"{message} (waited {timeout}s)")


async def assert_eventually_async(
    condition: Callable[[], Union[bool, Awaitable[bool]]],
    timeout: float = 5.0,
    interval: float = 0.1,
    message: str = "Condition was not met"
) -> None:
    """
    Assert that an async condition eventually becomes true.

    Usage:
        await assert_eventually_async(lambda: cache.exists("key"))
    """
    import time
    start = time.time()

    while time.time() - start < timeout:
        result = condition()
        if asyncio.iscoroutine(result):
            result = await result

        if result:
            return
        await asyncio.sleep(interval)

    raise AssertionError(f"{message} (waited {timeout}s)")


def assert_json_equal(
    actual: Union[str, Dict],
    expected: Union[str, Dict],
    ignore_keys: Optional[List[str]] = None
) -> None:
    """
    Assert that two JSON objects are equal.

    Usage:
        assert_json_equal(response.json(), {"status": "ok"})
    """
    if isinstance(actual, str):
        actual = json.loads(actual)
    if isinstance(expected, str):
        expected = json.loads(expected)

    if ignore_keys:
        actual = _remove_keys(actual, ignore_keys)
        expected = _remove_keys(expected, ignore_keys)

    if actual != expected:
        raise AssertionError(
            f"JSON not equal:\n"
            f"Actual: {json.dumps(actual, indent=2)}\n"
            f"Expected: {json.dumps(expected, indent=2)}"
        )


def _remove_keys(obj: Any, keys: List[str]) -> Any:
    """Remove keys from a nested dict."""
    if isinstance(obj, dict):
        return {
            k: _remove_keys(v, keys)
            for k, v in obj.items()
            if k not in keys
        }
    elif isinstance(obj, list):
        return [_remove_keys(item, keys) for item in obj]
    return obj


def assert_contains_keys(
    data: Dict,
    keys: List[str],
    message: str = "Missing required keys"
) -> None:
    """
    Assert that a dict contains all required keys.

    Usage:
        assert_contains_keys(response, ["id", "name", "email"])
    """
    missing = [k for k in keys if k not in data]
    if missing:
        raise AssertionError(f"{message}: {missing}")


def assert_valid_uuid(value: str, message: str = "Invalid UUID") -> None:
    """
    Assert that a string is a valid UUID.

    Usage:
        assert_valid_uuid(response["id"])
    """
    try:
        UUID(value)
    except (TypeError, ValueError):
        raise AssertionError(f"{message}: {value}")


def assert_valid_datetime(
    value: str,
    format: str = "%Y-%m-%dT%H:%M:%S",
    message: str = "Invalid datetime"
) -> None:
    """
    Assert that a string is a valid datetime.

    Usage:
        assert_valid_datetime(response["created_at"])
    """
    try:
        # Try ISO format first
        datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        try:
            datetime.strptime(value, format)
        except ValueError:
            raise AssertionError(f"{message}: {value}")


def assert_in_range(
    value: float,
    min_val: float,
    max_val: float,
    message: str = "Value out of range"
) -> None:
    """
    Assert that a value is within a range.

    Usage:
        assert_in_range(confidence, 0.0, 1.0)
    """
    if not min_val <= value <= max_val:
        raise AssertionError(
            f"{message}: {value} not in [{min_val}, {max_val}]"
        )


def assert_matches_pattern(
    value: str,
    pattern: str,
    message: str = "Value does not match pattern"
) -> None:
    """
    Assert that a string matches a regex pattern.

    Usage:
        assert_matches_pattern(email, r".*@.*\\..*")
    """
    if not re.match(pattern, value):
        raise AssertionError(f"{message}: {value} !~ {pattern}")


def assert_is_sorted(
    items: List[Any],
    key: Optional[Callable] = None,
    reverse: bool = False,
    message: str = "List is not sorted"
) -> None:
    """
    Assert that a list is sorted.

    Usage:
        assert_is_sorted(timestamps, key=lambda x: x["created_at"])
    """
    if key:
        values = [key(item) for item in items]
    else:
        values = items

    expected = sorted(values, reverse=reverse)
    if values != expected:
        raise AssertionError(message)


def assert_unique(
    items: List[Any],
    key: Optional[Callable] = None,
    message: str = "List contains duplicates"
) -> None:
    """
    Assert that all items in a list are unique.

    Usage:
        assert_unique(users, key=lambda x: x["id"])
    """
    if key:
        values = [key(item) for item in items]
    else:
        values = items

    if len(values) != len(set(values)):
        raise AssertionError(message)


def assert_subset(
    subset: Dict,
    superset: Dict,
    message: str = "Subset check failed"
) -> None:
    """
    Assert that one dict is a subset of another.

    Usage:
        assert_subset({"id": 1}, response)
    """
    for key, value in subset.items():
        if key not in superset:
            raise AssertionError(f"{message}: key '{key}' not found")
        if superset[key] != value:
            raise AssertionError(
                f"{message}: key '{key}' has value {superset[key]}, expected {value}"
            )


def assert_type(
    value: Any,
    expected_type: type,
    message: str = "Type mismatch"
) -> None:
    """
    Assert that a value is of a specific type.

    Usage:
        assert_type(response["count"], int)
    """
    if not isinstance(value, expected_type):
        raise AssertionError(
            f"{message}: expected {expected_type.__name__}, got {type(value).__name__}"
        )


def assert_length(
    items: Any,
    expected: int,
    message: str = "Length mismatch"
) -> None:
    """
    Assert that a collection has a specific length.

    Usage:
        assert_length(results, 10)
    """
    actual = len(items)
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def assert_length_between(
    items: Any,
    min_len: int,
    max_len: int,
    message: str = "Length out of range"
) -> None:
    """
    Assert that a collection length is within a range.

    Usage:
        assert_length_between(results, 1, 100)
    """
    actual = len(items)
    if not min_len <= actual <= max_len:
        raise AssertionError(
            f"{message}: length {actual} not in [{min_len}, {max_len}]"
        )


def assert_no_exception(
    func: Callable,
    *args,
    message: str = "Unexpected exception",
    **kwargs
) -> Any:
    """
    Assert that a function does not raise an exception.

    Usage:
        result = assert_no_exception(parse_json, '{"key": "value"}')
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        raise AssertionError(f"{message}: {type(e).__name__}: {e}")


async def assert_no_exception_async(
    func: Callable[..., Awaitable],
    *args,
    message: str = "Unexpected exception",
    **kwargs
) -> Any:
    """
    Assert that an async function does not raise an exception.

    Usage:
        result = await assert_no_exception_async(fetch_data, url)
    """
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        raise AssertionError(f"{message}: {type(e).__name__}: {e}")


def assert_raises_with_message(
    exception_type: type,
    message_pattern: str,
    func: Callable,
    *args,
    **kwargs
) -> None:
    """
    Assert that a function raises an exception with a matching message.

    Usage:
        assert_raises_with_message(
            ValueError,
            "invalid.*format",
            parse_date,
            "not-a-date"
        )
    """
    try:
        func(*args, **kwargs)
        raise AssertionError(f"Expected {exception_type.__name__} to be raised")
    except exception_type as e:
        if not re.search(message_pattern, str(e)):
            raise AssertionError(
                f"Exception message '{e}' does not match pattern '{message_pattern}'"
            )
    except Exception as e:
        raise AssertionError(
            f"Expected {exception_type.__name__}, got {type(e).__name__}: {e}"
        )
