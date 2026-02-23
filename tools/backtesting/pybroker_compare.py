"""Run deterministic internal backtests and compare against pybroker benchmarks."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.backtesting.backtest_engine import AdvancedBacktestEngine, BacktestConfig
from tools.backtesting.pybroker_adapter import normalize_candles, pybroker_available, to_pybroker_dataframe


@dataclass
class ScenarioMetrics:
    final_capital: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    total_trades: int


def _build_sample_candles(count: int = 180) -> list[dict[str, Any]]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    price = 100.0
    candles: list[dict[str, Any]] = []
    for i in range(count):
        trend = 0.0012
        cycle = 0.015 if i % 14 < 7 else -0.012
        noise = ((i % 5) - 2) * 0.001
        price *= (1 + trend + cycle + noise)
        candles.append(
            {
                "timestamp": (start + timedelta(hours=i)).isoformat(),
                "open": round(price * 0.998, 6),
                "high": round(price * 1.01, 6),
                "low": round(price * 0.99, 6),
                "close": round(price, 6),
                "volume": 1_000_000 + (i * 500),
            }
        )
    return candles


def _buy_and_hold(engine, candle) -> None:
    if engine.is_flat() and engine._current_idx == 0:
        engine.buy(1.0, "buy_and_hold_enter")
    elif engine.is_long() and engine._current_idx == len(engine._all_candles) - 1:
        engine.close_position("buy_and_hold_exit")


def _sma_crossover(engine, candle) -> None:
    if engine._current_idx < 20:
        return

    fast = engine.sma(10)
    slow = engine.sma(20)
    if engine.is_flat() and fast > slow:
        engine.buy(1.0, "sma_cross_enter")
    elif engine.is_long() and (fast < slow or engine._current_idx == len(engine._all_candles) - 1):
        engine.close_position("sma_cross_exit")


def _fixed_sl_tp_trend(engine, candle) -> None:
    # Align with pybroker execution semantics:
    # pybroker requires buy/sell delays >= 1 bar, so we stage intent and execute
    # on the next bar to compare like-for-like behavior.
    if not hasattr(engine, "_fixed_sl_tp_pending_entry"):
        engine._fixed_sl_tp_pending_entry = False
    if not hasattr(engine, "_fixed_sl_tp_pending_exit"):
        engine._fixed_sl_tp_pending_exit = False

    if engine._fixed_sl_tp_pending_exit and engine.is_long():
        engine.close_position("fixed_sl_tp_delayed_exit")
    engine._fixed_sl_tp_pending_exit = False

    if engine._fixed_sl_tp_pending_entry and engine.is_flat():
        engine.buy(1.0, "fixed_sl_tp_enter")
    engine._fixed_sl_tp_pending_entry = False

    if engine.is_flat() and engine._current_idx >= 10 and engine.sma(5) > engine.sma(10):
        engine._fixed_sl_tp_pending_entry = True
        return

    if engine.is_long():
        entry = engine.position.entry_price
        stop = entry * 0.95
        target = entry * 1.05
        px = engine.close()
        if px <= stop:
            engine._fixed_sl_tp_pending_exit = True
        elif px >= target:
            engine._fixed_sl_tp_pending_exit = True
        elif engine._current_idx == len(engine._all_candles) - 1:
            engine._fixed_sl_tp_pending_exit = True


SCENARIOS: dict[str, Callable] = {
    "buy_and_hold": _buy_and_hold,
    "sma_crossover": _sma_crossover,
    "fixed_sl_tp_trend": _fixed_sl_tp_trend,
}


def run_internal_scenarios(
    candles: list[dict[str, Any]],
    symbol: str = "SOL",
    initial_capital: float = 10_000.0,
) -> dict[str, ScenarioMetrics]:
    normalized = normalize_candles(candles)
    results: dict[str, ScenarioMetrics] = {}

    for scenario_name, strategy in SCENARIOS.items():
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = AdvancedBacktestEngine(results_dir=Path(tmpdir))
            engine.load_data(symbol, normalized)
            cfg = BacktestConfig(
                symbol=symbol,
                start_date=normalized[0]["timestamp"][:10],
                end_date=normalized[-1]["timestamp"][:10],
                initial_capital=initial_capital,
                fee_rate=0.001,
                slippage_bps=5.0,
                max_position_size=1.0,
                allow_short=False,
            )
            result = engine.run(strategy, cfg, strategy_name=scenario_name)
            results[scenario_name] = ScenarioMetrics(
                final_capital=result.final_capital,
                total_return_pct=result.metrics.total_return_pct,
                sharpe_ratio=result.metrics.sharpe_ratio,
                max_drawdown_pct=result.metrics.max_drawdown,
                total_trades=result.metrics.total_trades,
            )
    return results


def run_pybroker_scenarios(
    candles: list[dict[str, Any]],
    symbol: str = "SOL",
) -> dict[str, Any]:
    if not pybroker_available():
        return {
            "available": False,
            "status": "skipped",
            "reason": "pybroker not installed in environment",
            "results": {},
        }

    try:
        import numpy as np
        import pybroker

        frame = to_pybroker_dataframe(candles, symbol=symbol)
        start_date = frame["date"].min().to_pydatetime()
        end_date = frame["date"].max().to_pydatetime()

        def run_scenario(exec_fn: Callable[[Any], None]) -> ScenarioMetrics:
            strategy = pybroker.Strategy(
                frame,
                start_date,
                end_date,
                config=pybroker.StrategyConfig(
                    initial_cash=10_000.0,
                    fee_mode=pybroker.FeeMode.ORDER_PERCENT,
                    fee_amount=0.1,  # 0.1%
                    buy_delay=1,
                    sell_delay=1,
                    exit_on_last_bar=True,
                ),
            )
            strategy.add_execution(exec_fn, symbols=symbol)
            result = strategy.backtest(seed=42, disable_parallel=True)
            metrics = result.metrics
            return ScenarioMetrics(
                final_capital=float(metrics.end_market_value),
                total_return_pct=float(metrics.total_return_pct),
                sharpe_ratio=float(metrics.sharpe),
                max_drawdown_pct=abs(float(metrics.max_drawdown_pct)),
                total_trades=int(metrics.trade_count),
            )

        def exec_buy_and_hold(ctx: Any) -> None:
            if ctx.bars == 1 and ctx.long_pos() is None:
                ctx.buy_shares = ctx.calc_target_shares(1.0)

        def exec_sma_crossover(ctx: Any) -> None:
            if ctx.bars < 20:
                return
            closes = ctx.close
            fast = float(np.mean(closes[-10:]))
            slow = float(np.mean(closes[-20:]))
            long_pos = ctx.long_pos()
            if long_pos is None and fast > slow:
                ctx.buy_shares = ctx.calc_target_shares(1.0)
            elif long_pos is not None and fast < slow:
                ctx.sell_all_shares()

        def exec_fixed_sl_tp_trend(ctx: Any) -> None:
            if ctx.bars < 10:
                return
            closes = ctx.close
            long_pos = ctx.long_pos()
            if long_pos is None:
                fast = float(np.mean(closes[-5:]))
                slow = float(np.mean(closes[-10:]))
                if fast > slow:
                    ctx.buy_shares = ctx.calc_target_shares(1.0)
                    ctx.stop_loss_pct = 5
                    ctx.stop_profit_pct = 5

        scenario_results = {
            "buy_and_hold": run_scenario(exec_buy_and_hold),
            "sma_crossover": run_scenario(exec_sma_crossover),
            "fixed_sl_tp_trend": run_scenario(exec_fixed_sl_tp_trend),
        }
    except Exception as exc:  # pragma: no cover - environment specific
        return {
            "available": True,
            "status": "error",
            "reason": f"pybroker scenario execution failed: {exc}",
            "results": {},
        }

    return {
        "available": True,
        "status": "completed",
        "reason": "pybroker benchmark scenarios executed successfully",
        "results": {name: asdict(metrics) for name, metrics in scenario_results.items()},
    }


def compare_metrics(
    internal_results: dict[str, ScenarioMetrics],
    pybroker_payload: dict[str, Any],
    tolerance_pct: float = 5.0,
) -> dict[str, Any]:
    comparisons: dict[str, Any] = {}
    py_results = pybroker_payload.get("results", {}) if isinstance(pybroker_payload, dict) else {}
    py_status = pybroker_payload.get("status") if isinstance(pybroker_payload, dict) else "unknown"

    for scenario, internal in internal_results.items():
        if scenario not in py_results:
            comparisons[scenario] = {
                "status": "skipped",
                "reason": f"pybroker scenario unavailable (status={py_status})",
                "internal": asdict(internal),
            }
            continue

        peer = py_results[scenario]
        delta = abs(internal.total_return_pct - float(peer["total_return_pct"]))
        comparisons[scenario] = {
            "status": "pass" if delta <= tolerance_pct else "fail",
            "delta_total_return_pct": delta,
            "tolerance_pct": tolerance_pct,
            "internal": asdict(internal),
            "pybroker": peer,
        }
    return comparisons


def run_comparison(output_root: Path, symbol: str = "SOL", tolerance_pct: float = 5.0) -> Path:
    candles = _build_sample_candles()
    internal = run_internal_scenarios(candles, symbol=symbol)
    pybroker_payload = run_pybroker_scenarios(candles, symbol=symbol)
    comparisons = compare_metrics(internal, pybroker_payload, tolerance_pct=tolerance_pct)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = output_root / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "comparison.json"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "scenarios": list(SCENARIOS.keys()),
        "internal_results": {k: asdict(v) for k, v in internal.items()},
        "pybroker": pybroker_payload,
        "comparisons": comparisons,
    }
    out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-root",
        default="artifacts/backtest_compare",
        help="Directory to write comparison artifacts to.",
    )
    parser.add_argument("--symbol", default="SOL", help="Benchmark symbol label.")
    parser.add_argument(
        "--tolerance-pct",
        type=float,
        default=5.0,
        help="Allowed total-return delta percentage points for pass/fail comparison.",
    )
    args = parser.parse_args()

    out_file = run_comparison(
        output_root=Path(args.output_root),
        symbol=args.symbol,
        tolerance_pct=args.tolerance_pct,
    )
    print(f"Wrote pybroker comparison artifact: {out_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
