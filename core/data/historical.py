"""
Historical OHLCV Data Fetcher — Multi-source with quality validation.

Sources (in priority order):
    1. **GeckoTerminal** (primary) — No auth required, 30 req/min, ~6 months depth
    2. **DexPaprika** (secondary) — No auth required, pool-lifetime depth
    3. **CCXT/Binance** (CEX-listed tokens only) — Deep history, years of data

Data quality filters applied to ALL ingested data:
    - Drop candles with USD volume < $500
    - Flag assets with > 20% missing candles in any 24h window
    - Reject assets with < 1000 candles at target resolution for backtesting
    - Detect sandwich-attack wicks: (high - low) / close > 0.15 on 1m data

Usage::

    from core.data.historical import fetch_ohlcv, validate_ohlcv

    df = await fetch_ohlcv(
        pool_address="...",
        timeframe="1h",
        start_date=datetime(2025, 6, 1),
        end_date=datetime(2025, 12, 1),
    )
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    aiohttp = None

# Lazy import to avoid circular deps — GeckoTerminal sync client is re-used
# for non-async callers via _run_sync()
try:
    from core.geckoterminal import fetch_pool_ohlcv_safe, normalize_ohlcv_list
    HAS_GECKOTERMINAL = True
except ImportError:
    HAS_GECKOTERMINAL = False

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GECKOTERMINAL_BASE = "https://api.geckoterminal.com/api/v2"
DEXPAPRIKA_BASE = "https://api.dexpaprika.com/v1"

# GeckoTerminal timeframe mapping
GT_TIMEFRAMES = {
    "1m": "minute",
    "5m": "minute",
    "15m": "minute",
    "1h": "hour",
    "4h": "hour",
    "1d": "day",
}

# Interval in seconds for each timeframe
TIMEFRAME_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

MAX_CANDLES_PER_REQUEST = 1000
USER_AGENT = "LifeOS/1.0 (Jarvis Historical Data)"

# Quality thresholds
MIN_VOLUME_USD = 500.0
SANDWICH_WICK_THRESHOLD = 0.15    # (high - low) / close > 15% = suspected MEV
MISSING_CANDLE_WARN_PCT = 0.20    # > 20% missing in 24h = flagged
MIN_CANDLES_FOR_BACKTEST = 1000


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

class QualityFlag(Enum):
    """Flags applied to individual candles or entire datasets."""

    LOW_VOLUME = "low_volume"               # USD volume < $500
    SANDWICH_WICK = "sandwich_wick"         # MEV-like wick detected
    MISSING_CANDLE = "missing_candle"       # Gap in expected sequence
    STALE_PRICE = "stale_price"             # Identical OHLC across multiple candles
    ZERO_VOLUME = "zero_volume"             # Exactly zero volume


@dataclass
class DataQualityReport:
    """Summary of data quality checks for a fetched OHLCV dataset."""

    total_candles: int = 0
    dropped_low_volume: int = 0
    sandwich_wicks: int = 0
    missing_candles: int = 0
    stale_candles: int = 0
    expected_candles: int = 0
    gap_pct: float = 0.0
    is_backtest_eligible: bool = False
    flags: List[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Candles: {self.total_candles}/{self.expected_candles} "
            f"(gap {self.gap_pct:.1%}) | "
            f"Dropped: {self.dropped_low_volume} low-vol | "
            f"Wicks: {self.sandwich_wicks} | "
            f"Eligible: {self.is_backtest_eligible}"
        )


def validate_ohlcv(
    df: "pd.DataFrame",
    timeframe: str,
    min_volume_usd: float = MIN_VOLUME_USD,
) -> Tuple["pd.DataFrame", DataQualityReport]:
    """
    Apply data quality filters to an OHLCV DataFrame.

    Returns the cleaned DataFrame and a quality report.
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required for OHLCV validation")

    report = DataQualityReport()

    if df.empty:
        return df, report

    report.total_candles = len(df)

    # 1. Drop duplicate timestamps
    df = df.drop_duplicates(subset=["timestamp"], keep="last")

    # 2. Sort by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    # 3. Flag and drop low-volume candles
    low_vol_mask = df["volume_usd"] < min_volume_usd
    report.dropped_low_volume = int(low_vol_mask.sum())
    df = df[~low_vol_mask].reset_index(drop=True)

    # 4. Detect sandwich wicks on 1m data
    if timeframe == "1m" and len(df) > 0:
        close_vals = df["close"]
        range_vals = df["high"] - df["low"]
        # Avoid div-by-zero
        safe_close = close_vals.replace(0, float("nan"))
        wick_ratio = range_vals / safe_close
        sandwich_mask = wick_ratio > SANDWICH_WICK_THRESHOLD
        report.sandwich_wicks = int(sandwich_mask.sum())
        # Flag but don't drop — add quality column
        if "quality_flags" not in df.columns:
            df["quality_flags"] = ""
        df.loc[sandwich_mask, "quality_flags"] = (
            df.loc[sandwich_mask, "quality_flags"] + "sandwich_wick,"
        )

    # 5. Detect stale prices (identical OHLC across 3+ consecutive candles)
    if len(df) >= 3:
        is_stale = (
            (df["open"] == df["open"].shift(1))
            & (df["close"] == df["close"].shift(1))
            & (df["high"] == df["high"].shift(1))
            & (df["low"] == df["low"].shift(1))
        )
        report.stale_candles = int(is_stale.sum())

    # 6. Check for missing candles (gaps)
    if len(df) >= 2:
        interval_s = TIMEFRAME_SECONDS.get(timeframe, 3600)
        ts = df["timestamp"]
        if hasattr(ts.iloc[0], "timestamp"):
            # datetime objects
            diffs = ts.diff().dt.total_seconds().dropna()
        else:
            # numeric timestamps
            diffs = ts.diff().dropna()
        expected_gaps = diffs / interval_s
        missing = expected_gaps[expected_gaps > 1.5].sum() - len(expected_gaps[expected_gaps > 1.5])
        report.missing_candles = int(max(0, missing))

    # 7. Calculate expected candles and gap percentage
    if len(df) >= 2:
        interval_s = TIMEFRAME_SECONDS.get(timeframe, 3600)
        ts = df["timestamp"]
        if hasattr(ts.iloc[0], "timestamp"):
            span_s = (ts.iloc[-1] - ts.iloc[0]).total_seconds()
        else:
            span_s = float(ts.iloc[-1] - ts.iloc[0])
        report.expected_candles = max(1, int(span_s / interval_s) + 1)
        report.gap_pct = 1.0 - (len(df) / report.expected_candles) if report.expected_candles > 0 else 0.0
    else:
        report.expected_candles = len(df)

    # 8. Backtest eligibility
    report.is_backtest_eligible = (
        len(df) >= MIN_CANDLES_FOR_BACKTEST
        and report.gap_pct < MISSING_CANDLE_WARN_PCT
    )

    report.total_candles = len(df)

    if report.gap_pct > MISSING_CANDLE_WARN_PCT:
        report.flags.append(f"high_gap_pct:{report.gap_pct:.2%}")
    if report.sandwich_wicks > 0:
        report.flags.append(f"sandwich_wicks:{report.sandwich_wicks}")

    return df, report


# ---------------------------------------------------------------------------
# GeckoTerminal async fetcher
# ---------------------------------------------------------------------------

async def _fetch_geckoterminal_ohlcv(
    pool_address: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    network: str = "solana",
) -> "pd.DataFrame":
    """
    Fetch OHLCV from GeckoTerminal API, paginating backwards from end_date.

    Returns a pandas DataFrame with columns:
    timestamp, open, high, low, close, volume_usd
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required")

    gt_tf = GT_TIMEFRAMES.get(timeframe)
    if gt_tf is None:
        raise ValueError(f"Unsupported timeframe: {timeframe}. Use one of {list(GT_TIMEFRAMES.keys())}")

    interval_s = TIMEFRAME_SECONDS[timeframe]
    all_rows: List[Dict[str, Any]] = []

    # GeckoTerminal uses aggregate for sub-hour queries
    aggregate = None
    if timeframe == "5m":
        aggregate = 5
    elif timeframe == "15m":
        aggregate = 15
    elif timeframe == "4h":
        aggregate = 4

    cursor_ts = int(end_date.timestamp())
    start_ts = int(start_date.timestamp())
    max_pages = 100  # Safety limit

    for _ in range(max_pages):
        if cursor_ts <= start_ts:
            break

        url = f"{GECKOTERMINAL_BASE}/networks/{network}/pools/{pool_address}/ohlcv/{gt_tf}"
        params: Dict[str, Any] = {
            "limit": MAX_CANDLES_PER_REQUEST,
            "before_timestamp": cursor_ts,
            "currency": "usd",
        }
        if aggregate:
            params["aggregate"] = aggregate

        try:
            if HAS_AIOHTTP:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        params=params,
                        headers={"User-Agent": USER_AGENT},
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as resp:
                        if resp.status == 429:
                            retry_after = resp.headers.get("Retry-After", "10")
                            wait = min(float(retry_after), 60)
                            logger.warning("GeckoTerminal rate limited, waiting %.1fs", wait)
                            await asyncio.sleep(wait)
                            continue
                        if resp.status != 200:
                            logger.warning("GeckoTerminal HTTP %d for %s", resp.status, pool_address)
                            break
                        data = await resp.json()
            elif HAS_GECKOTERMINAL:
                # Fallback to sync client
                result = fetch_pool_ohlcv_safe(
                    network, pool_address, gt_tf,
                    limit=MAX_CANDLES_PER_REQUEST,
                    before_timestamp=cursor_ts,
                )
                if not result.success:
                    logger.warning("GeckoTerminal fetch failed: %s", result.error)
                    break
                data = result.data
            else:
                raise ImportError("Either aiohttp or requests is required")
        except Exception as exc:
            logger.error("GeckoTerminal fetch error: %s", exc)
            break

        # Extract OHLCV list
        ohlcv_list = (
            data.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
            if data else []
        )

        if not ohlcv_list:
            break

        for row in ohlcv_list:
            if len(row) < 6:
                continue
            try:
                ts = int(row[0])
                if ts < start_ts:
                    continue
                all_rows.append({
                    "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc),
                    "open": float(row[1]),
                    "high": float(row[2]),
                    "low": float(row[3]),
                    "close": float(row[4]),
                    "volume_usd": float(row[5]),
                })
            except (TypeError, ValueError, IndexError):
                continue

        # Move cursor back
        oldest_ts = min(int(r[0]) for r in ohlcv_list if len(r) >= 6)
        if oldest_ts >= cursor_ts:
            break  # No progress
        cursor_ts = oldest_ts

        # Rate limit courtesy
        await asyncio.sleep(2.1)  # ~28 req/min, under 30 limit

    if not all_rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume_usd"])

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    logger.info(
        "GeckoTerminal: fetched %d candles for %s (%s) [%s → %s]",
        len(df), pool_address, timeframe,
        df["timestamp"].iloc[0].isoformat(),
        df["timestamp"].iloc[-1].isoformat(),
    )
    return df


# ---------------------------------------------------------------------------
# DexPaprika async fetcher
# ---------------------------------------------------------------------------

async def _fetch_dexpaprika_ohlcv(
    pool_address: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    network: str = "solana",
) -> "pd.DataFrame":
    """
    Fetch OHLCV from DexPaprika API (secondary source).

    DexPaprika offers pool-lifetime depth (often 1 year+) and is useful
    for cross-validating GeckoTerminal data and filling gaps.
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required")
    if not HAS_AIOHTTP:
        raise ImportError("aiohttp is required for DexPaprika fetching")

    # DexPaprika timeframe mapping
    dp_intervals = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "1h": "1h", "4h": "4h", "1d": "1d",
    }
    dp_interval = dp_intervals.get(timeframe)
    if dp_interval is None:
        raise ValueError(f"Unsupported timeframe for DexPaprika: {timeframe}")

    url = f"{DEXPAPRIKA_BASE}/{network}/pools/{pool_address}/ohlcv"
    params = {
        "start": start_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "interval": dp_interval,
        "limit": 1000,
    }

    all_rows: List[Dict[str, Any]] = []

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    logger.warning("DexPaprika HTTP %d for %s", resp.status, pool_address)
                    return pd.DataFrame(
                        columns=["timestamp", "open", "high", "low", "close", "volume_usd"]
                    )
                data = await resp.json()
    except Exception as exc:
        logger.error("DexPaprika fetch error: %s", exc)
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume_usd"])

    candles = data if isinstance(data, list) else data.get("data", [])

    for candle in candles:
        try:
            ts_raw = candle.get("time") or candle.get("timestamp") or candle.get("t")
            if isinstance(ts_raw, str):
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            elif isinstance(ts_raw, (int, float)):
                ts = datetime.fromtimestamp(ts_raw, tz=timezone.utc)
            else:
                continue

            all_rows.append({
                "timestamp": ts,
                "open": float(candle.get("open") or candle.get("o", 0)),
                "high": float(candle.get("high") or candle.get("h", 0)),
                "low": float(candle.get("low") or candle.get("l", 0)),
                "close": float(candle.get("close") or candle.get("c", 0)),
                "volume_usd": float(candle.get("volume") or candle.get("v", 0)),
            })
        except (TypeError, ValueError, KeyError):
            continue

    if not all_rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume_usd"])

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    logger.info("DexPaprika: fetched %d candles for %s (%s)", len(df), pool_address, timeframe)
    return df


# ---------------------------------------------------------------------------
# CCXT/Binance fetcher (CEX-listed tokens only)
# ---------------------------------------------------------------------------

async def _fetch_ccxt_ohlcv(
    symbol: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
) -> "pd.DataFrame":
    """
    Fetch OHLCV from Binance via CCXT for CEX-listed tokens.

    Only use for: SOL/USDT, JUP/USDT, RAY/USDT, BONK/USDT, etc.
    Provides deep historical data (years of 1-minute candles).
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required")

    try:
        import ccxt.async_support as ccxt_async
    except ImportError:
        logger.warning("ccxt not installed — skipping Binance historical fetch")
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume_usd"])

    # CCXT timeframe mapping
    ccxt_tf_map = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "1h": "1h", "4h": "4h", "1d": "1d",
    }
    ccxt_tf = ccxt_tf_map.get(timeframe)
    if ccxt_tf is None:
        raise ValueError(f"Unsupported CCXT timeframe: {timeframe}")

    exchange = ccxt_async.binance({"enableRateLimit": True})

    try:
        all_rows: List[Dict[str, Any]] = []
        since_ms = int(start_date.timestamp() * 1000)
        end_ms = int(end_date.timestamp() * 1000)

        while since_ms < end_ms:
            ohlcv = await exchange.fetch_ohlcv(
                symbol, ccxt_tf, since=since_ms, limit=1000
            )
            if not ohlcv:
                break

            for row in ohlcv:
                ts_ms, o, h, l, c, vol = row[:6]
                if ts_ms > end_ms:
                    break
                all_rows.append({
                    "timestamp": datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume_usd": float(c) * float(vol),  # Approximate USD volume
                })

            # Move cursor
            last_ts = ohlcv[-1][0]
            if last_ts <= since_ms:
                break
            since_ms = last_ts + 1

            await asyncio.sleep(0.1)  # Rate limit courtesy
    finally:
        await exchange.close()

    if not all_rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume_usd"])

    df = pd.DataFrame(all_rows)
    df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
    logger.info("CCXT/Binance: fetched %d candles for %s (%s)", len(df), symbol, timeframe)
    return df


# ---------------------------------------------------------------------------
# Unified fetcher
# ---------------------------------------------------------------------------

# CEX-listed tokens that should use Binance for deep historical data
CEX_LISTED_SYMBOLS: Dict[str, str] = {
    "SOL": "SOL/USDT",
    "JUP": "JUP/USDT",
    "RAY": "RAY/USDT",
    "BONK": "BONK/USDT",
    "WIF": "WIF/USDT",
    "RNDR": "RNDR/USDT",
    "PYTH": "PYTH/USDT",
    "JTO": "JTO/USDT",
    "W": "W/USDT",
    "HNT": "HNT/USDT",
}


async def fetch_ohlcv(
    pool_address: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    *,
    source: str = "geckoterminal",
    network: str = "solana",
    cex_symbol: Optional[str] = None,
    validate: bool = True,
) -> Tuple["pd.DataFrame", Optional[DataQualityReport]]:
    """
    Fetch historical OHLCV data with automatic quality validation.

    Args:
        pool_address: DEX pool address (for GeckoTerminal/DexPaprika)
        timeframe: "1m", "5m", "15m", "1h", "4h", "1d"
        start_date: UTC start datetime
        end_date: UTC end datetime
        source: "geckoterminal", "dexpaprika", "ccxt", or "auto"
        network: Blockchain network (default "solana")
        cex_symbol: Token symbol for CEX lookup (e.g., "SOL")
        validate: Whether to run data quality validation

    Returns:
        Tuple of (DataFrame, DataQualityReport or None)
        DataFrame columns: timestamp, open, high, low, close, volume_usd
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required for fetch_ohlcv")

    if timeframe not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}. Use one of {list(TIMEFRAME_SECONDS.keys())}")

    # Ensure timezone-aware datetimes
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)

    df: pd.DataFrame

    if source == "auto":
        # Try CEX first for listed tokens (deepest history)
        if cex_symbol and cex_symbol.upper() in CEX_LISTED_SYMBOLS:
            try:
                df = await _fetch_ccxt_ohlcv(
                    CEX_LISTED_SYMBOLS[cex_symbol.upper()],
                    timeframe, start_date, end_date,
                )
                if len(df) >= MIN_CANDLES_FOR_BACKTEST:
                    logger.info("Using CCXT/Binance data for %s (%d candles)", cex_symbol, len(df))
                    if validate:
                        return validate_ohlcv(df, timeframe)
                    return df, None
            except Exception as exc:
                logger.warning("CCXT fetch failed for %s: %s — falling back", cex_symbol, exc)

        # Try GeckoTerminal
        try:
            df = await _fetch_geckoterminal_ohlcv(
                pool_address, timeframe, start_date, end_date, network,
            )
            if not df.empty:
                if validate:
                    return validate_ohlcv(df, timeframe)
                return df, None
        except Exception as exc:
            logger.warning("GeckoTerminal failed: %s — trying DexPaprika", exc)

        # Fall back to DexPaprika
        try:
            df = await _fetch_dexpaprika_ohlcv(
                pool_address, timeframe, start_date, end_date, network,
            )
            if validate:
                return validate_ohlcv(df, timeframe)
            return df, None
        except Exception as exc:
            logger.error("All data sources failed for %s: %s", pool_address, exc)
            empty = pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume_usd"])
            return empty, DataQualityReport()

    elif source == "geckoterminal":
        df = await _fetch_geckoterminal_ohlcv(
            pool_address, timeframe, start_date, end_date, network,
        )
    elif source == "dexpaprika":
        df = await _fetch_dexpaprika_ohlcv(
            pool_address, timeframe, start_date, end_date, network,
        )
    elif source == "ccxt":
        if not cex_symbol:
            raise ValueError("cex_symbol is required for ccxt source")
        pair = CEX_LISTED_SYMBOLS.get(cex_symbol.upper(), f"{cex_symbol.upper()}/USDT")
        df = await _fetch_ccxt_ohlcv(pair, timeframe, start_date, end_date)
    else:
        raise ValueError(f"Unknown source: {source}. Use 'geckoterminal', 'dexpaprika', 'ccxt', or 'auto'")

    if validate:
        return validate_ohlcv(df, timeframe)
    return df, None


# ---------------------------------------------------------------------------
# Cross-validation
# ---------------------------------------------------------------------------

async def cross_validate(
    pool_address: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    max_deviation_pct: float = 2.0,
) -> Dict[str, Any]:
    """
    Fetch from both GeckoTerminal and DexPaprika and compare close prices.

    Returns a report indicating data reliability. If median deviation > max_deviation_pct,
    the data should be considered unreliable.
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required")

    gt_df = await _fetch_geckoterminal_ohlcv(pool_address, timeframe, start_date, end_date)
    dp_df = await _fetch_dexpaprika_ohlcv(pool_address, timeframe, start_date, end_date)

    if gt_df.empty or dp_df.empty:
        return {
            "validated": False,
            "reason": "one_source_empty",
            "gt_candles": len(gt_df),
            "dp_candles": len(dp_df),
        }

    # Merge on closest timestamps
    gt_df = gt_df.rename(columns={"close": "gt_close"})
    dp_df = dp_df.rename(columns={"close": "dp_close"})

    merged = pd.merge_asof(
        gt_df[["timestamp", "gt_close"]].sort_values("timestamp"),
        dp_df[["timestamp", "dp_close"]].sort_values("timestamp"),
        on="timestamp",
        tolerance=pd.Timedelta(seconds=TIMEFRAME_SECONDS.get(timeframe, 3600)),
    )
    merged = merged.dropna(subset=["gt_close", "dp_close"])

    if merged.empty:
        return {"validated": False, "reason": "no_overlapping_timestamps"}

    deviation = abs(merged["gt_close"] - merged["dp_close"]) / merged["gt_close"] * 100
    median_dev = float(deviation.median())
    max_dev = float(deviation.max())

    return {
        "validated": median_dev <= max_deviation_pct,
        "median_deviation_pct": round(median_dev, 3),
        "max_deviation_pct": round(max_dev, 3),
        "overlapping_candles": len(merged),
        "gt_candles": len(gt_df),
        "dp_candles": len(dp_df),
    }


# ---------------------------------------------------------------------------
# Sync wrapper for non-async callers
# ---------------------------------------------------------------------------

def fetch_ohlcv_sync(
    pool_address: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    **kwargs: Any,
) -> Tuple["pd.DataFrame", Optional[DataQualityReport]]:
    """Synchronous wrapper around ``fetch_ohlcv()``."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Already in an event loop — schedule as a task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run,
                fetch_ohlcv(pool_address, timeframe, start_date, end_date, **kwargs),
            )
            return future.result(timeout=300)
    else:
        return asyncio.run(
            fetch_ohlcv(pool_address, timeframe, start_date, end_date, **kwargs)
        )
