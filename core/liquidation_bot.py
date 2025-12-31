"""Liquidation sweep strategy module.

This strategy monitors liquidation prints and enters near smaller liquidation
clusters, assuming they precede larger liquidation cascades.
"""

from __future__ import annotations

import csv
import io
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from core import config, hyperliquid


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "data" / "trader"
SIGNAL_LOG = LOG_DIR / "liquidation_signals.jsonl"


@dataclass
class SymbolConfig:
    liquidation_usd: float
    time_window_mins: int
    stop_loss_pct: float
    take_profit_pct: float


@dataclass
class LiquidationSignal:
    symbol: str
    liquidation_usd: float
    liquidation_threshold: float
    liquidation_price: float
    current_price: float
    entry_price: float
    side: str
    size: float
    leverage: float
    stop_loss_price: float
    take_profit_price: float
    timestamp: float
    reason: str


def run_cycle(symbols: Optional[List[str]] = None) -> List[LiquidationSignal]:
    """Run one liquidation scan cycle and return any signals."""
    cfg = _load_bot_config()
    symbols = symbols or cfg.get("symbols", [])
    if not symbols:
        return []

    signals: List[LiquidationSignal] = []
    for symbol in symbols:
        signal = evaluate_symbol(symbol, cfg)
        if signal:
            signals.append(signal)
            _log_signal(signal)
    return signals


def evaluate_symbol(symbol: str, cfg: Dict[str, Any]) -> Optional[LiquidationSignal]:
    symbol_cfg = _get_symbol_config(symbol, cfg)
    if not symbol_cfg:
        return None

    liq_amount, liq_price = fetch_liquidation_data(symbol, symbol_cfg, cfg)
    if liq_price is None:
        return None

    current_price = hyperliquid.fetch_mid_price(symbol) or liq_price
    if liq_amount < symbol_cfg.liquidation_usd:
        return None

    entry_offset_pct = float(cfg.get("entry_offset_pct", 0.005))
    entry_price = round(liq_price * (1 - entry_offset_pct), _price_decimals(symbol))

    order_usd_size = float(cfg.get("order_usd_size", 10))
    leverage = float(cfg.get("leverage", 3))
    size = (order_usd_size * leverage) / max(entry_price, 1e-9)

    stop_loss_price = _stop_loss_price(entry_price, symbol_cfg.stop_loss_pct)
    take_profit_price = _take_profit_price(entry_price, symbol_cfg.take_profit_pct)

    return LiquidationSignal(
        symbol=symbol,
        liquidation_usd=liq_amount,
        liquidation_threshold=symbol_cfg.liquidation_usd,
        liquidation_price=liq_price,
        current_price=current_price,
        entry_price=entry_price,
        side="short",
        size=size,
        leverage=leverage,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        timestamp=time.time(),
        reason="Liquidation threshold met",
    )


def fetch_liquidation_data(
    symbol: str,
    symbol_cfg: SymbolConfig,
    cfg: Dict[str, Any],
) -> Tuple[float, Optional[float]]:
    api_url = cfg.get("moondev_api_url", "http://api.moondev.com:8000")
    api_key = cfg.get("moondev_api_key")
    if not api_key:
        api_key = cfg.get("moondev_api_key_env")
        if api_key:
            import os
            api_key = os.getenv(api_key)

    csv_text = _fetch_liquidation_csv(api_url, api_key, cfg.get("moondev_limit", 100000))
    if not csv_text:
        return 0.0, None

    return _parse_liquidation_csv(
        csv_text,
        symbol=symbol,
        time_window_mins=symbol_cfg.time_window_mins,
        symbol_col=int(cfg.get("symbol_col", 0)),
        price_col=int(cfg.get("price_col", 5)),
        time_col=int(cfg.get("time_col", -2)),
        usd_col=int(cfg.get("usd_col", -1)),
    )


def _fetch_liquidation_csv(api_url: str, api_key: Optional[str], limit: int) -> str:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    url = f"{api_url}/files/liq_data.csv?limit={limit}"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception:
        return ""


def _parse_liquidation_csv(
    csv_text: str,
    symbol: str,
    time_window_mins: int,
    symbol_col: int,
    price_col: int,
    time_col: int,
    usd_col: int,
) -> Tuple[float, Optional[float]]:
    reader = csv.reader(io.StringIO(csv_text))
    rows = list(reader)
    if not rows:
        return 0.0, None

    # Drop header if it contains non-numeric data in expected price column
    if rows and len(rows[0]) > abs(price_col):
        if not _safe_float(rows[0][price_col]):
            rows = rows[1:]

    if not rows:
        return 0.0, None

    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=time_window_mins)
    total_usd = 0.0
    latest_price = None

    for row in rows:
        if len(row) <= max(symbol_col, price_col, abs(time_col), abs(usd_col)):
            continue
        if row[symbol_col] != symbol:
            continue
        ts = _safe_float(row[time_col])
        if ts is None:
            continue
        trade_time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        if trade_time < start or trade_time > now:
            continue
        usd_size = _safe_float(row[usd_col])
        if usd_size is None:
            continue
        total_usd += usd_size
        price = _safe_float(row[price_col])
        if price is not None:
            latest_price = price

    return total_usd, latest_price


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _price_decimals(symbol: str) -> int:
    if symbol.upper() in {"BTC", "ETH"}:
        return 2
    return 4


def _stop_loss_price(entry_price: float, stop_loss_pct: float) -> float:
    pct = abs(stop_loss_pct) / 100
    return round(entry_price * (1 + pct), 6)


def _take_profit_price(entry_price: float, take_profit_pct: float) -> float:
    pct = abs(take_profit_pct) / 100
    return round(entry_price * (1 - pct), 6)


def _load_bot_config() -> Dict[str, Any]:
    cfg = config.load_config()
    return cfg.get("liquidation_bot", {})


def _get_symbol_config(symbol: str, cfg: Dict[str, Any]) -> Optional[SymbolConfig]:
    symbol_cfg = cfg.get("symbols_data", {}).get(symbol)
    if not symbol_cfg:
        return None
    return SymbolConfig(
        liquidation_usd=float(symbol_cfg.get("liquidations", 0)),
        time_window_mins=int(symbol_cfg.get("time_window_mins", 5)),
        stop_loss_pct=float(symbol_cfg.get("sl", -2)),
        take_profit_pct=float(symbol_cfg.get("tp", 1)),
    )


def _log_signal(signal: LiquidationSignal) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": signal.timestamp,
        "symbol": signal.symbol,
        "side": signal.side,
        "liquidation_usd": signal.liquidation_usd,
        "liquidation_threshold": signal.liquidation_threshold,
        "liquidation_price": signal.liquidation_price,
        "current_price": signal.current_price,
        "entry_price": signal.entry_price,
        "size": signal.size,
        "leverage": signal.leverage,
        "stop_loss_price": signal.stop_loss_price,
        "take_profit_price": signal.take_profit_price,
        "reason": signal.reason,
    }
    with SIGNAL_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")

