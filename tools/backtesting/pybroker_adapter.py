"""Adapters for converting internal OHLCV data into pybroker-compatible formats."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


def pybroker_available() -> bool:
    """Return True when pybroker is importable in the current environment."""
    try:
        import pybroker  # noqa: F401
        return True
    except Exception:
        return False


def normalize_candles(candles: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Normalize candle payload into a sorted canonical schema."""
    normalized: list[dict[str, Any]] = []
    for candle in candles:
        timestamp = candle["timestamp"]
        if isinstance(timestamp, (int, float)):
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
            ts = dt.isoformat()
        else:
            ts = str(timestamp)
        normalized.append(
            {
                "timestamp": ts,
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle.get("volume", 0.0)),
            }
        )

    normalized.sort(key=lambda row: row["timestamp"])
    return normalized


def to_pybroker_dataframe(
    candles: Iterable[Mapping[str, Any]],
    symbol: str = "TEST",
):
    """
    Convert candles into a pybroker-friendly DataFrame.

    Column layout is intentionally explicit:
    - symbol
    - date (UTC)
    - open, high, low, close, volume
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "pandas is required for pybroker adapter conversion"
        ) from exc

    rows = normalize_candles(candles)
    df = pd.DataFrame(rows)
    # pybroker compares against tz-naive datetime bounds internally.
    # Convert to UTC then strip tzinfo for deterministic Strategy filtering.
    df["date"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("UTC").dt.tz_localize(None)
    df["symbol"] = symbol
    return df[["symbol", "date", "open", "high", "low", "close", "volume"]]
