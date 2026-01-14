"""
Optimized JSON Serialization

Provides fast JSON serialization with multiple backend support.
Falls back gracefully when faster backends unavailable.
"""
import json
from typing import Any, Optional, Type, Callable
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from dataclasses import is_dataclass, asdict
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

# Try to import faster JSON libraries
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

try:
    import ujson
    HAS_UJSON = True
except ImportError:
    HAS_UJSON = False


class JSONEncoder(json.JSONEncoder):
    """Extended JSON encoder with support for common types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, date):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        if isinstance(obj, set):
            return list(obj)
        if is_dataclass(obj):
            return asdict(obj)
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()

        return super().default(obj)


def _default_serializer(obj: Any) -> Any:
    """Default serializer for non-standard types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    if isinstance(obj, set):
        return list(obj)
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    if hasattr(obj, '__dict__'):
        return obj.__dict__

    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class FastJSONSerializer:
    """
    High-performance JSON serializer with automatic backend selection.

    Tries to use the fastest available JSON library:
    1. orjson (fastest, Rust-based)
    2. ujson (fast, C-based)
    3. stdlib json (fallback)

    Usage:
        serializer = FastJSONSerializer()

        # Serialize
        json_bytes = serializer.dumps({"key": "value"})
        json_str = serializer.dumps_str({"key": "value"})

        # Deserialize
        data = serializer.loads(json_bytes)
    """

    def __init__(self, use_orjson: bool = True, use_ujson: bool = True):
        self._use_orjson = use_orjson and HAS_ORJSON
        self._use_ujson = use_ujson and HAS_UJSON

        if self._use_orjson:
            self._backend = "orjson"
        elif self._use_ujson:
            self._backend = "ujson"
        else:
            self._backend = "json"

        logger.debug(f"Using JSON backend: {self._backend}")

    @property
    def backend(self) -> str:
        """Get the current backend name."""
        return self._backend

    def dumps(self, obj: Any) -> bytes:
        """
        Serialize object to JSON bytes.

        Args:
            obj: Object to serialize

        Returns:
            JSON as bytes
        """
        if self._use_orjson:
            return orjson.dumps(
                obj,
                default=_default_serializer,
                option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_UTC_Z
            )
        elif self._use_ujson:
            return ujson.dumps(obj, default=_default_serializer).encode('utf-8')
        else:
            return json.dumps(obj, cls=JSONEncoder, separators=(',', ':')).encode('utf-8')

    def dumps_str(self, obj: Any) -> str:
        """
        Serialize object to JSON string.

        Args:
            obj: Object to serialize

        Returns:
            JSON as string
        """
        if self._use_orjson:
            return orjson.dumps(
                obj,
                default=_default_serializer,
                option=orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_UTC_Z
            ).decode('utf-8')
        elif self._use_ujson:
            return ujson.dumps(obj, default=_default_serializer)
        else:
            return json.dumps(obj, cls=JSONEncoder, separators=(',', ':'))

    def dumps_pretty(self, obj: Any) -> str:
        """
        Serialize object to pretty-printed JSON string.

        Args:
            obj: Object to serialize

        Returns:
            Pretty JSON as string
        """
        if self._use_orjson:
            return orjson.dumps(
                obj,
                default=_default_serializer,
                option=orjson.OPT_INDENT_2
            ).decode('utf-8')
        elif self._use_ujson:
            return ujson.dumps(obj, default=_default_serializer, indent=2)
        else:
            return json.dumps(obj, cls=JSONEncoder, indent=2)

    def loads(self, data: bytes | str) -> Any:
        """
        Deserialize JSON to object.

        Args:
            data: JSON bytes or string

        Returns:
            Deserialized object
        """
        if self._use_orjson:
            return orjson.loads(data)
        elif self._use_ujson:
            return ujson.loads(data)
        else:
            return json.loads(data)


# Global serializer instance
_serializer: Optional[FastJSONSerializer] = None


def get_serializer() -> FastJSONSerializer:
    """Get the global JSON serializer."""
    global _serializer
    if _serializer is None:
        _serializer = FastJSONSerializer()
    return _serializer


def dumps(obj: Any) -> bytes:
    """Serialize object to JSON bytes using fastest backend."""
    return get_serializer().dumps(obj)


def dumps_str(obj: Any) -> str:
    """Serialize object to JSON string using fastest backend."""
    return get_serializer().dumps_str(obj)


def loads(data: bytes | str) -> Any:
    """Deserialize JSON using fastest backend."""
    return get_serializer().loads(data)


# Response helpers for FastAPI
class ORJSONResponse:
    """FastAPI response class using orjson for faster serialization."""

    media_type = "application/json"

    def __init__(self, content: Any, status_code: int = 200):
        self.body = get_serializer().dumps(content)
        self.status_code = status_code

    def __call__(self, scope, receive, send):
        import asyncio
        return asyncio.create_task(self._send(scope, receive, send))

    async def _send(self, scope, receive, send):
        await send({
            'type': 'http.response.start',
            'status': self.status_code,
            'headers': [[b'content-type', b'application/json']],
        })
        await send({
            'type': 'http.response.body',
            'body': self.body,
        })


@lru_cache(maxsize=256)
def _get_cached_schema(model_class: Type) -> dict:
    """Cache JSON schema for Pydantic models."""
    if hasattr(model_class, 'model_json_schema'):
        return model_class.model_json_schema()
    elif hasattr(model_class, 'schema'):
        return model_class.schema()
    return {}


def benchmark_backends() -> dict:
    """Benchmark available JSON backends."""
    import time

    test_data = {
        "string": "hello world",
        "number": 12345,
        "float": 123.456,
        "boolean": True,
        "null": None,
        "array": [1, 2, 3, 4, 5],
        "nested": {"a": 1, "b": 2, "c": {"d": 3}},
        "datetime": datetime.now().isoformat(),
    }

    results = {}
    iterations = 10000

    # Standard library
    start = time.perf_counter()
    for _ in range(iterations):
        json.dumps(test_data)
    results["json"] = time.perf_counter() - start

    # ujson
    if HAS_UJSON:
        start = time.perf_counter()
        for _ in range(iterations):
            ujson.dumps(test_data)
        results["ujson"] = time.perf_counter() - start

    # orjson
    if HAS_ORJSON:
        start = time.perf_counter()
        for _ in range(iterations):
            orjson.dumps(test_data)
        results["orjson"] = time.perf_counter() - start

    return {
        "iterations": iterations,
        "times_seconds": results,
        "ops_per_second": {k: iterations / v for k, v in results.items()},
        "fastest": min(results, key=results.get) if results else None
    }
