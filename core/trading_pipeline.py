"""
Deterministic trading pipeline for Jarvis.

Provides:
- Data ingestion (Hyperliquid snapshots)
- Strategy signals (SMA cross, RSI reversion)
- Backtesting with metrics
- Paper trading state + P&L logging

No external dependencies.
"""

from __future__ import annotations

import json
import math
import statistics
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import config, hyperliquid
from core.economics.revenue import get_revenue_tracker


ROOT = Path(__file__).resolve().parents[1]
TRADER_DIR = ROOT / "data" / "trader"
PAPER_STATE_FILE = TRADER_DIR / "paper_state.json"
PAPER_TRADES_FILE = TRADER_DIR / "paper_trades.jsonl"
BACKTEST_RESULTS_FILE = TRADER_DIR / "backtests.jsonl"


@dataclass
class StrategyConfig:
    kind: str = "sma_cross"
    params: Dict[str, float] = field(default_factory=dict)
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    risk_per_trade: float = 0.02
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.06
    max_position_pct: float = 0.25
    capital_usd: float = 1000.0


@dataclass
class BacktestResult:
    symbol: str
    interval: str
    strategy: str
    params: Dict[str, float]
    period_start: Optional[int]
    period_end: Optional[int]
    total_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    expectancy: float
    net_pnl: float
    roi: float
    equity_start: float
    equity_end: float
    trades: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""
    error: Optional[str] = None


def ensure_hyperliquid_snapshot(
    coin: str,
    interval: str,
    lookback_days: int,
    max_age_hours: int = 6,
) -> Optional[Path]:
    """Ensure a recent Hyperliquid snapshot exists."""
    TRADER_DIR.mkdir(parents=True, exist_ok=True)
    path = hyperliquid.latest_snapshot_for_coin(coin, interval=interval)
    if path and _is_recent(path, max_age_hours):
        return path

    cfg = config.load_config()
    if not cfg.get("hyperliquid", {}).get("enabled", True):
        return path

    hyperliquid.pull_lookback([coin], interval=interval, lookback_days=lookback_days)
    return hyperliquid.latest_snapshot_for_coin(coin, interval=interval)


def load_candles_for_symbol(coin: str, interval: str) -> List[Dict[str, Any]]:
    """Load and normalize candles from latest snapshot."""
    path = hyperliquid.latest_snapshot_for_coin(coin, interval=interval)
    if not path:
        return []
    snapshot = hyperliquid.load_snapshot(str(path))
    if not snapshot:
        return []
    candles = snapshot.get("candles", [])
    return _normalize_candles(candles)


def run_backtest(
    candles: List[Dict[str, Any]],
    symbol: str,
    interval: str,
    strategy: StrategyConfig,
) -> BacktestResult:
    """Run a deterministic backtest on normalized candles."""
    closes = [c["close"] for c in candles if c.get("close") is not None]
    timestamps = [c.get("timestamp") for c in candles if c.get("close") is not None]

    if len(closes) < 20:
        return BacktestResult(
            symbol=symbol,
            interval=interval,
            strategy=strategy.kind,
            params=strategy.params,
            period_start=timestamps[0] if timestamps else None,
            period_end=timestamps[-1] if timestamps else None,
            total_trades=0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            expectancy=0.0,
            net_pnl=0.0,
            roi=0.0,
            equity_start=strategy.capital_usd,
            equity_end=strategy.capital_usd,
            trades=[],
            error="Not enough data for backtest",
        )

    indicator = _build_indicator_series(closes, strategy)
    warmup = indicator.get("warmup", 0)

    equity = strategy.capital_usd
    equity_curve: List[float] = []
    trades: List[Dict[str, Any]] = []
    position: Optional[Dict[str, Any]] = None
    peak = equity
    max_dd = 0.0

    for idx, price in enumerate(closes):
        timestamp = timestamps[idx] if idx < len(timestamps) else None

        if idx < warmup:
            equity_curve.append(equity)
            continue

        signal = _signal_for_index(indicator, strategy, idx)

        # Exit conditions for open position
        if position:
            exit_reason = _check_exit(position, price, signal)
            if exit_reason:
                trade = _close_position(position, price, timestamp, exit_reason, strategy)
                equity += trade["pnl"]
                trades.append(trade)
                position = None

        # Entry condition
        if position is None and signal == "enter":
            position = _open_position(
                symbol,
                price,
                timestamp,
                strategy,
            )

        # Mark-to-market equity curve
        current_equity = equity
        if position:
            current_equity += _unrealized_pnl(position, price)

        equity_curve.append(current_equity)
        peak = max(peak, current_equity)
        if peak > 0:
            dd = (peak - current_equity) / peak
            max_dd = max(max_dd, dd)

    # Close any open position at end
    if position:
        final_price = closes[-1]
        trade = _close_position(position, final_price, timestamps[-1] if timestamps else None, "final", strategy)
        equity += trade["pnl"]
        trades.append(trade)
        equity_curve[-1] = equity

    metrics = _compute_metrics(trades, equity_curve, strategy.capital_usd, interval)

    return BacktestResult(
        symbol=symbol,
        interval=interval,
        strategy=strategy.kind,
        params=strategy.params,
        period_start=timestamps[0] if timestamps else None,
        period_end=timestamps[-1] if timestamps else None,
        total_trades=metrics["total_trades"],
        win_rate=metrics["win_rate"],
        profit_factor=metrics["profit_factor"],
        max_drawdown=max_dd,
        sharpe_ratio=metrics["sharpe_ratio"],
        expectancy=metrics["expectancy"],
        net_pnl=metrics["net_pnl"],
        roi=metrics["roi"],
        equity_start=strategy.capital_usd,
        equity_end=metrics["equity_end"],
        trades=trades,
        notes=metrics.get("notes", ""),
    )


def format_backtest_summary(result: BacktestResult) -> str:
    """Create a readable backtest summary."""
    if result.error:
        return f"Backtest failed: {result.error}"

    return (
        f"BACKTEST: {result.symbol} ({result.interval}) {result.strategy}\n"
        f"Trades: {result.total_trades} | Win rate: {result.win_rate*100:.1f}%\n"
        f"Profit factor: {result.profit_factor:.2f} | Max DD: {result.max_drawdown*100:.1f}%\n"
        f"Sharpe: {result.sharpe_ratio:.2f} | Expectancy: ${result.expectancy:.2f}\n"
        f"Net PnL: ${result.net_pnl:+.2f} | ROI: {result.roi*100:.2f}%\n"
    )


def paper_trade_cycle(
    candles: List[Dict[str, Any]],
    symbol: str,
    interval: str,
    strategy: StrategyConfig,
) -> Dict[str, Any]:
    """Execute a single paper trading cycle."""
    closes = [c["close"] for c in candles if c.get("close") is not None]
    timestamps = [c.get("timestamp") for c in candles if c.get("close") is not None]

    if not closes:
        return {"error": "No candle data"}

    indicator = _build_indicator_series(closes, strategy)
    warmup = indicator.get("warmup", 0)
    if len(closes) <= warmup:
        return {"error": "Not enough data for strategy"}

    idx = len(closes) - 1
    price = closes[-1]
    timestamp = timestamps[-1] if timestamps else None
    signal = _signal_for_index(indicator, strategy, idx)

    state = _load_paper_state(strategy.capital_usd)
    positions = state.get("positions", {})
    position = positions.get(symbol)

    closed_trade = None
    opened_trade = None

    if position:
        exit_reason = _check_exit(position, price, signal)
        if exit_reason:
            closed_trade = _close_position(position, price, timestamp, exit_reason, strategy)
            state["equity_usd"] = round(state.get("equity_usd", strategy.capital_usd) + closed_trade["pnl"], 4)
            positions.pop(symbol, None)
            _log_paper_trade(closed_trade, event="close")
            _log_revenue(closed_trade, symbol=symbol, paper=True)

    if position is None and signal == "enter":
        opened_trade = _open_position(
            symbol,
            price,
            timestamp,
            strategy,
            capital_usd=state.get("equity_usd", strategy.capital_usd),
        )
        positions[symbol] = opened_trade
        _log_paper_trade(opened_trade, event="open")

    state["positions"] = positions
    state["last_update"] = datetime.now(timezone.utc).isoformat()
    _save_paper_state(state)

    return {
        "symbol": symbol,
        "interval": interval,
        "signal": signal,
        "price": price,
        "opened_trade": opened_trade,
        "closed_trade": closed_trade,
        "equity_usd": state.get("equity_usd", strategy.capital_usd),
        "positions": positions,
    }


def format_paper_summary(result: Dict[str, Any]) -> str:
    """Readable summary for paper trading cycle."""
    if result.get("error"):
        return f"Paper trade: {result['error']}"

    lines = [
        f"PAPER TRADE: {result.get('symbol')} ({result.get('interval')})",
        f"Signal: {result.get('signal')} | Price: {result.get('price'):.4f}",
        f"Equity: ${result.get('equity_usd', 0):.2f}",
    ]

    closed_trade = result.get("closed_trade")
    if closed_trade:
        lines.append(
            f"Closed {closed_trade['side']} @ {closed_trade['exit_price']:.4f} | "
            f"PnL ${closed_trade['pnl']:+.2f} ({closed_trade['exit_reason']})"
        )

    opened_trade = result.get("opened_trade")
    if opened_trade:
        lines.append(
            f"Opened {opened_trade['side']} @ {opened_trade['entry_price']:.4f} | "
            f"Size {opened_trade['size_pct']*100:.1f}%"
        )

    if not closed_trade and not opened_trade:
        lines.append("No position change")

    return "\n".join(lines)


def log_backtest_result(result: BacktestResult) -> None:
    """Append backtest result to log file."""
    TRADER_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.time(),
        "symbol": result.symbol,
        "interval": result.interval,
        "strategy": result.strategy,
        "params": result.params,
        "period_start": result.period_start,
        "period_end": result.period_end,
        "total_trades": result.total_trades,
        "win_rate": result.win_rate,
        "profit_factor": result.profit_factor,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "expectancy": result.expectancy,
        "net_pnl": result.net_pnl,
        "roi": result.roi,
        "equity_start": result.equity_start,
        "equity_end": result.equity_end,
        "error": result.error,
    }
    with open(BACKTEST_RESULTS_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def load_backtest_results(days: int = 30, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load backtest results from log."""
    entries = _read_jsonl(BACKTEST_RESULTS_FILE)
    cutoff = time.time() - (days * 86400) if days else None
    normalized_symbol = symbol.upper() if symbol else None
    results: List[Dict[str, Any]] = []
    for entry in entries:
        ts = entry.get("timestamp")
        if cutoff and ts and ts < cutoff:
            continue
        if normalized_symbol and entry.get("symbol", "").upper() != normalized_symbol:
            continue
        results.append(entry)
    return results


def summarize_backtests(days: int = 30, symbol: Optional[str] = None) -> Dict[str, Any]:
    """Summarize recent backtests."""
    results = load_backtest_results(days=days, symbol=symbol)
    if not results:
        return {
            "count": 0,
            "best_sharpe": None,
            "best_roi": None,
            "latest": None,
        }

    def _safe(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float("-inf")

    best_sharpe = max(results, key=lambda r: _safe(r.get("sharpe_ratio")))
    best_roi = max(results, key=lambda r: _safe(r.get("roi")))
    latest = max(results, key=lambda r: _safe(r.get("timestamp", 0)))

    return {
        "count": len(results),
        "best_sharpe": best_sharpe,
        "best_roi": best_roi,
        "latest": latest,
    }


def load_paper_trade_events(days: int = 30, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load paper trade events from log."""
    entries = _read_jsonl(PAPER_TRADES_FILE)
    cutoff = time.time() - (days * 86400) if days else None
    normalized_symbol = symbol.upper() if symbol else None
    results: List[Dict[str, Any]] = []
    for entry in entries:
        ts = entry.get("timestamp")
        if cutoff and ts and ts < cutoff:
            continue
        if normalized_symbol and entry.get("symbol", "").upper() != normalized_symbol:
            continue
        results.append(entry)
    return results


def summarize_paper_trades(days: int = 30, symbol: Optional[str] = None) -> Dict[str, Any]:
    """Summarize closed paper trades."""
    events = load_paper_trade_events(days=days, symbol=symbol)
    closed = [e for e in events if e.get("event") == "close"]
    if not closed:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "net_pnl": 0.0,
            "roi": 0.0,
            "first_trade_at": None,
            "last_trade_at": None,
        }

    wins = [e for e in closed if e.get("pnl", 0) > 0]
    net_pnl = sum(float(e.get("pnl", 0.0)) for e in closed)
    win_rate = len(wins) / len(closed) if closed else 0.0

    first_ts = min(e.get("timestamp", time.time()) for e in closed)
    last_ts = max(e.get("timestamp", time.time()) for e in closed)

    state = _load_paper_state(default_capital=1000.0)
    capital = float(state.get("capital_usd", 1000.0))
    roi = net_pnl / capital if capital else 0.0

    return {
        "total_trades": len(closed),
        "win_rate": win_rate,
        "net_pnl": net_pnl,
        "roi": roi,
        "first_trade_at": first_ts,
        "last_trade_at": last_ts,
    }


def _is_recent(path: Path, max_age_hours: int) -> bool:
    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds < (max_age_hours * 3600)


def _normalize_candles(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for candle in candles:
        timestamp = _get_numeric(candle, ["t", "time", "timestamp"])
        open_price = _get_numeric(candle, ["o", "open", "O"])
        high = _get_numeric(candle, ["h", "high", "H"])
        low = _get_numeric(candle, ["l", "low", "L"])
        close = _get_numeric(candle, ["c", "close", "C"])
        volume = _get_numeric(candle, ["v", "volume", "V"])
        if close is None:
            continue
        normalized.append({
            "timestamp": int(timestamp) if timestamp is not None else None,
            "open": open_price,
            "high": high,
            "low": low,
            "close": float(close),
            "volume": volume,
        })
    return normalized


def _get_numeric(payload: Dict[str, Any], keys: List[str]) -> Optional[float]:
    for key in keys:
        if key in payload:
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    continue
    return None


def _build_indicator_series(closes: List[float], strategy: StrategyConfig) -> Dict[str, Any]:
    if strategy.kind == "rsi":
        period = int(strategy.params.get("period", 14))
        rsi = _rsi_series(closes, period)
        return {
            "type": "rsi",
            "series": rsi,
            "lower": float(strategy.params.get("lower", 30)),
            "upper": float(strategy.params.get("upper", 70)),
            "warmup": period + 1,
        }

    fast = int(strategy.params.get("fast", 5))
    slow = int(strategy.params.get("slow", 20))
    fast_ma = _sma_series(closes, fast)
    slow_ma = _sma_series(closes, slow)
    return {
        "type": "sma",
        "fast": fast_ma,
        "slow": slow_ma,
        "warmup": max(fast, slow) + 1,
    }


def _signal_for_index(indicator: Dict[str, Any], strategy: StrategyConfig, idx: int) -> Optional[str]:
    if indicator.get("type") == "rsi":
        series = indicator.get("series", [])
        if idx <= 0 or idx >= len(series):
            return None
        value = series[idx]
        if value is None:
            return None
        if value < indicator.get("lower", 30):
            return "enter"
        if value > indicator.get("upper", 70):
            return "exit"
        return None

    fast_series = indicator.get("fast", [])
    slow_series = indicator.get("slow", [])
    if idx <= 0 or idx >= len(fast_series) or idx >= len(slow_series):
        return None
    fast_prev = fast_series[idx - 1]
    slow_prev = slow_series[idx - 1]
    fast_now = fast_series[idx]
    slow_now = slow_series[idx]
    if fast_prev is None or slow_prev is None or fast_now is None or slow_now is None:
        return None
    if fast_prev <= slow_prev and fast_now > slow_now:
        return "enter"
    if fast_prev >= slow_prev and fast_now < slow_now:
        return "exit"
    return None


def _sma_series(closes: List[float], window: int) -> List[Optional[float]]:
    series: List[Optional[float]] = [None] * len(closes)
    if window <= 0:
        return series
    total = 0.0
    for i, price in enumerate(closes):
        total += price
        if i >= window:
            total -= closes[i - window]
        if i >= window - 1:
            series[i] = total / window
    return series


def _rsi_series(closes: List[float], period: int) -> List[Optional[float]]:
    series: List[Optional[float]] = [None] * len(closes)
    if period <= 0 or len(closes) <= period:
        return series

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        gains += max(delta, 0)
        losses += max(-delta, 0)

    avg_gain = gains / period
    avg_loss = losses / period
    rs = avg_gain / avg_loss if avg_loss > 0 else math.inf
    series[period] = 100 - (100 / (1 + rs))

    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = max(delta, 0)
        loss = max(-delta, 0)
        avg_gain = ((avg_gain * (period - 1)) + gain) / period
        avg_loss = ((avg_loss * (period - 1)) + loss) / period
        rs = avg_gain / avg_loss if avg_loss > 0 else math.inf
        series[i] = 100 - (100 / (1 + rs))

    return series


def _open_position(
    symbol: str,
    price: float,
    timestamp: Optional[int],
    strategy: StrategyConfig,
    capital_usd: Optional[float] = None,
) -> Dict[str, Any]:
    size_pct = _position_size(strategy)
    capital = capital_usd if capital_usd is not None else strategy.capital_usd
    entry_price = _apply_slippage(price, strategy.slippage_bps, side="buy")
    stop_loss = entry_price * (1 - strategy.stop_loss_pct)
    take_profit = entry_price * (1 + strategy.take_profit_pct)

    return {
        "id": uuid.uuid4().hex[:10],
        "symbol": symbol,
        "side": "long",
        "entry_price": entry_price,
        "size_pct": size_pct,
        "notional": capital * size_pct,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "opened_at": timestamp or int(time.time()),
        "strategy": strategy.kind,
    }


def _close_position(
    position: Dict[str, Any],
    price: float,
    timestamp: Optional[int],
    reason: str,
    strategy: StrategyConfig,
) -> Dict[str, Any]:
    exit_price = _apply_slippage(price, strategy.slippage_bps, side="sell")
    entry_price = position["entry_price"]
    notional = position["notional"]
    pnl = ((exit_price - entry_price) / entry_price) * notional
    pnl -= _fees(notional, strategy.fee_bps)

    return {
        **position,
        "exit_price": exit_price,
        "closed_at": timestamp or int(time.time()),
        "exit_reason": reason,
        "pnl": round(pnl, 4),
        "pnl_pct": pnl / notional if notional else 0.0,
    }


def _unrealized_pnl(position: Dict[str, Any], price: float) -> float:
    entry_price = position["entry_price"]
    notional = position["notional"]
    return ((price - entry_price) / entry_price) * notional


def _check_exit(position: Dict[str, Any], price: float, signal: Optional[str]) -> Optional[str]:
    if price <= position.get("stop_loss", -math.inf):
        return "stop_loss"
    if price >= position.get("take_profit", math.inf):
        return "take_profit"
    if signal == "exit":
        return "signal"
    return None


def _position_size(strategy: StrategyConfig) -> float:
    if strategy.stop_loss_pct <= 0:
        return min(strategy.max_position_pct, 0.1)
    size = strategy.risk_per_trade / strategy.stop_loss_pct
    return min(strategy.max_position_pct, max(0.0, size))


def _apply_slippage(price: float, slippage_bps: float, side: str) -> float:
    if slippage_bps <= 0:
        return price
    factor = slippage_bps / 10000
    if side == "buy":
        return price * (1 + factor)
    return price * (1 - factor)


def _fees(notional: float, fee_bps: float) -> float:
    if fee_bps <= 0:
        return 0.0
    return notional * (fee_bps / 10000) * 2


def _compute_metrics(
    trades: List[Dict[str, Any]],
    equity_curve: List[float],
    initial_equity: float,
    interval: str,
) -> Dict[str, Any]:
    total_trades = len(trades)
    wins = [t for t in trades if t.get("pnl", 0) > 0]
    losses = [t for t in trades if t.get("pnl", 0) < 0]

    win_rate = len(wins) / total_trades if total_trades else 0.0
    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)

    avg_win = statistics.mean([t["pnl"] for t in wins]) if wins else 0.0
    avg_loss = statistics.mean([abs(t["pnl"]) for t in losses]) if losses else 0.0
    loss_rate = 1 - win_rate
    expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

    equity_end = equity_curve[-1] if equity_curve else initial_equity
    net_pnl = equity_end - initial_equity
    roi = net_pnl / initial_equity if initial_equity else 0.0

    returns = _equity_returns(equity_curve)
    sharpe = _sharpe_ratio(returns, interval)

    return {
        "total_trades": total_trades,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "net_pnl": net_pnl,
        "roi": roi,
        "equity_end": equity_end,
        "sharpe_ratio": sharpe,
    }


def _equity_returns(equity_curve: List[float]) -> List[float]:
    returns: List[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]
        current = equity_curve[i]
        if prev:
            returns.append((current / prev) - 1)
    return returns


def _sharpe_ratio(returns: List[float], interval: str) -> float:
    if len(returns) < 2:
        return 0.0
    mean_ret = statistics.mean(returns)
    std_ret = statistics.pstdev(returns)
    if std_ret == 0:
        return 0.0
    annual_factor = _annualization_factor(interval)
    return (mean_ret / std_ret) * math.sqrt(annual_factor)


def _annualization_factor(interval: str) -> float:
    try:
        value = float(interval[:-1])
        unit = interval[-1]
        if unit == "m":
            return 365 * 24 * 60 / max(value, 1)
        if unit == "h":
            return 365 * 24 / max(value, 1)
        if unit == "d":
            return 365 / max(value, 1)
        if unit == "w":
            return 52 / max(value, 1)
    except Exception:
        pass
    return 365.0


def _load_paper_state(default_capital: float) -> Dict[str, Any]:
    if PAPER_STATE_FILE.exists():
        try:
            with open(PAPER_STATE_FILE, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {
        "capital_usd": default_capital,
        "equity_usd": default_capital,
        "positions": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _save_paper_state(state: Dict[str, Any]) -> None:
    TRADER_DIR.mkdir(parents=True, exist_ok=True)
    with open(PAPER_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def _log_paper_trade(trade: Dict[str, Any], event: str) -> None:
    TRADER_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": time.time(),
        "event": event,
        **trade,
    }
    with open(PAPER_TRADES_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def _log_revenue(trade: Dict[str, Any], symbol: str, paper: bool = True) -> None:
    try:
        tracker = get_revenue_tracker()
        tracker.log_trading_profit(
            profit_usd=trade.get("pnl", 0.0),
            trade_id=trade.get("id", ""),
            strategy=trade.get("strategy", ""),
            symbol=symbol,
            paper=paper,
        )
    except Exception:
        pass


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                entries.append(payload)
    return entries
