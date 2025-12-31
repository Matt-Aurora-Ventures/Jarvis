"""
Hyperliquid data ingestion utilities.
Pulls historical candle data for research and backtesting prep.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "hyperliquid"
LOG_PATH = ROOT / "data" / "hyperliquid.log"
API_URL = "https://api.hyperliquid.xyz/info"


def _log(action: str, details: Dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "details": details,
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def _post(payload: Dict[str, Any], timeout: int = 20) -> Any:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def _now_ms() -> int:
    return int(time.time() * 1000)


def fetch_mid_prices() -> Dict[str, float]:
    """Fetch latest mid prices for all symbols."""
    payload = {"type": "allMids"}
    try:
        response = _post(payload)
        if isinstance(response, dict):
            mids: Dict[str, float] = {}
            for key, value in response.items():
                try:
                    mids[key] = float(value)
                except (TypeError, ValueError):
                    continue
            return mids
    except Exception:
        pass
    return {}


def fetch_mid_price(symbol: str) -> Optional[float]:
    """Fetch latest mid price for a symbol."""
    symbol = symbol.upper()
    mids = fetch_mid_prices()
    return mids.get(symbol)


def _chunk_ranges(start_ms: int, end_ms: int, chunk_days: int) -> List[Tuple[int, int]]:
    if chunk_days <= 0:
        return [(start_ms, end_ms)]
    chunk_ms = int(chunk_days * 24 * 60 * 60 * 1000)
    ranges = []
    cursor = start_ms
    while cursor < end_ms:
        chunk_end = min(cursor + chunk_ms, end_ms)
        ranges.append((cursor, chunk_end))
        cursor = chunk_end
    return ranges


def _safe_ts(candle: Dict[str, Any]) -> Optional[int]:
    for key in ("t", "time", "timestamp"):
        value = candle.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None


def fetch_candles(
    coin: str,
    interval: str,
    start_ms: int,
    end_ms: int,
) -> List[Dict[str, Any]]:
    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin,
            "interval": interval,
            "startTime": start_ms,
            "endTime": end_ms,
        },
    }
    try:
        response = _post(payload)
        if isinstance(response, list):
            _log("candles_fetched", {
                "coin": coin,
                "interval": interval,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "count": len(response),
            })
            return response
    except urllib.error.HTTPError as exc:
        _log("candles_http_error", {
            "coin": coin,
            "interval": interval,
            "error": str(exc),
        })
    except Exception as exc:
        _log("candles_error", {
            "coin": coin,
            "interval": interval,
            "error": str(exc),
        })
    return []


def save_snapshot(
    coin: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    candles: List[Dict[str, Any]],
) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    safe_coin = coin.lower().replace("/", "_")
    filename = f"{safe_coin}_{interval}_{start_ms}_{end_ms}.json"
    path = DATA_DIR / filename
    payload = {
        "coin": coin,
        "interval": interval,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "candles": candles,
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def pull_lookback(
    coins: Iterable[str],
    interval: str = "1h",
    lookback_days: int = 30,
    chunk_days: int = 7,
) -> Dict[str, Any]:
    end_ms = _now_ms()
    start_ms = end_ms - int(lookback_days * 24 * 60 * 60 * 1000)
    results: Dict[str, Any] = {
        "start_ms": start_ms,
        "end_ms": end_ms,
        "interval": interval,
        "coins": {},
    }
    ranges = _chunk_ranges(start_ms, end_ms, chunk_days)

    for coin in coins:
        coin = coin.strip()
        if not coin:
            continue
        all_candles: List[Dict[str, Any]] = []
        for chunk_start, chunk_end in ranges:
            candles = fetch_candles(coin, interval, chunk_start, chunk_end)
            all_candles.extend(candles)
            time.sleep(0.3)
        all_candles.sort(key=lambda c: _safe_ts(c) or 0)
        path = save_snapshot(coin, interval, start_ms, end_ms, all_candles)
        results["coins"][coin] = {
            "count": len(all_candles),
            "path": str(path),
            "first_ts": _safe_ts(all_candles[0]) if all_candles else None,
            "last_ts": _safe_ts(all_candles[-1]) if all_candles else None,
        }

    _log("lookback_complete", {
        "coins": list(results["coins"].keys()),
        "interval": interval,
        "lookback_days": lookback_days,
        "chunk_days": chunk_days,
    })
    return results


def summarize_snapshot(snapshot: Dict[str, Any]) -> str:
    coins = snapshot.get("coins", {})
    if not coins:
        return "No Hyperliquid data collected."
    lines = ["Hyperliquid snapshot summary:"]
    for coin, info in coins.items():
        lines.append(
            f"- {coin}: {info.get('count', 0)} candles "
            f"({info.get('first_ts')} -> {info.get('last_ts')})"
        )
    return "\n".join(lines)


def load_snapshot(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def _extract_close(candle: Dict[str, Any]) -> Optional[float]:
    for key in ("c", "close", "C"):
        value = candle.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
    return None


def simple_ma_backtest(candles: List[Dict[str, Any]], fast: int = 5, slow: int = 20) -> Dict[str, Any]:
    closes = [price for price in (_extract_close(c) for c in candles) if price is not None]
    if len(closes) < max(fast, slow) + 2:
        return {"error": "Not enough data for backtest", "trades": 0, "roi": 0.0}

    def _ma(idx: int, window: int) -> float:
        start = max(0, idx - window + 1)
        window_vals = closes[start : idx + 1]
        return sum(window_vals) / len(window_vals)

    position = 0  # 0 = flat, 1 = long
    entry_price = 0.0
    pnl = 0.0
    trades = 0
    for i in range(max(fast, slow), len(closes)):
        fast_ma = _ma(i, fast)
        slow_ma = _ma(i, slow)
        price = closes[i]
        if position == 0 and fast_ma > slow_ma:
            position = 1
            entry_price = price
            trades += 1
        elif position == 1 and fast_ma < slow_ma:
            pnl += price - entry_price
            position = 0

    if position == 1:
        pnl += closes[-1] - entry_price

    roi = pnl / closes[0] if closes[0] else 0.0
    return {
        "trades": trades,
        "pnl": round(pnl, 4),
        "roi": round(roi, 4),
        "fast": fast,
        "slow": slow,
    }


def latest_snapshot_for_coin(coin: str, interval: str = "1h") -> Optional[Path]:
    if not DATA_DIR.exists():
        return None
    safe_coin = coin.lower().replace("/", "_")
    candidates = sorted(DATA_DIR.glob(f"{safe_coin}_{interval}_*.json"), reverse=True)
    return candidates[0] if candidates else None
