"""Fast JSON serialization using orjson and msgspec."""
from typing import Any, Type, TypeVar, Optional
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Try to import fast JSON libraries
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False
    orjson = None

try:
    import msgspec
    HAS_MSGSPEC = True
except ImportError:
    HAS_MSGSPEC = False
    msgspec = None


def dumps(obj: Any, pretty: bool = False) -> bytes:
    """
    Serialize object to JSON bytes using the fastest available library.
    
    Performance: orjson is 3-10x faster than stdlib json.
    """
    if HAS_ORJSON:
        opts = orjson.OPT_INDENT_2 if pretty else 0
        return orjson.dumps(obj, option=opts)
    else:
        import json
        indent = 2 if pretty else None
        return json.dumps(obj, indent=indent).encode()


def loads(data: bytes | str) -> Any:
    """
    Deserialize JSON bytes/string using the fastest available library.
    """
    if HAS_ORJSON:
        return orjson.loads(data)
    else:
        import json
        return json.loads(data)


def dumps_str(obj: Any, pretty: bool = False) -> str:
    """Serialize to JSON string."""
    return dumps(obj, pretty).decode()


# msgspec-based fast schemas
if HAS_MSGSPEC:
    from msgspec import Struct, json as msgspec_json
    
    class FastStruct(Struct, frozen=True, kw_only=True):
        """Base class for fast, immutable data structures."""
        pass
    
    def decode_fast(data: bytes | str, type_: Type[T]) -> T:
        """Decode JSON to a typed msgspec Struct (10-80x faster than Pydantic)."""
        return msgspec_json.decode(data, type=type_)
    
    def encode_fast(obj: Any) -> bytes:
        """Encode msgspec Struct to JSON bytes."""
        return msgspec_json.encode(obj)
    
    # Fast trading schemas using msgspec
    class FastOrder(Struct, frozen=True):
        """Ultra-fast order schema for hot paths."""
        symbol: str
        side: str  # "buy" or "sell"
        amount: float
        price: Optional[float] = None
        order_type: str = "market"
    
    class FastTrade(Struct, frozen=True):
        """Ultra-fast trade schema."""
        id: str
        symbol: str
        side: str
        amount: float
        price: float
        timestamp: float
        fee: float = 0.0
    
    class FastQuote(Struct, frozen=True):
        """Ultra-fast quote schema."""
        symbol: str
        bid: float
        ask: float
        last: float
        volume: float
        timestamp: float
    
    class FastPosition(Struct, frozen=True):
        """Ultra-fast position schema."""
        symbol: str
        size: float
        entry_price: float
        current_price: float
        unrealized_pnl: float
        realized_pnl: float = 0.0

else:
    # Fallback - no msgspec
    FastStruct = object
    FastOrder = None
    FastTrade = None
    FastQuote = None
    FastPosition = None
    
    def decode_fast(data: bytes | str, type_: Type[T]) -> T:
        raise ImportError("msgspec not installed")
    
    def encode_fast(obj: Any) -> bytes:
        raise ImportError("msgspec not installed")


# Utility functions
def json_response(data: Any) -> dict:
    """Create a fast JSON response for FastAPI."""
    if HAS_ORJSON:
        from fastapi.responses import ORJSONResponse
        return ORJSONResponse(content=data)
    return data


def get_json_performance_info() -> dict:
    """Get info about available JSON libraries."""
    return {
        "orjson_available": HAS_ORJSON,
        "msgspec_available": HAS_MSGSPEC,
        "recommended": "msgspec" if HAS_MSGSPEC else ("orjson" if HAS_ORJSON else "stdlib"),
    }
