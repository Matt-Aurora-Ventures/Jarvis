"""Tests for pybroker comparison harness scaffolding."""

import pytest
from pathlib import Path

from tools.backtesting.pybroker_adapter import pybroker_available, to_pybroker_dataframe
from tools.backtesting.pybroker_compare import (
    _build_sample_candles,
    compare_metrics,
    run_pybroker_scenarios,
    run_comparison,
    run_internal_scenarios,
)


def test_build_sample_candles_are_time_ordered():
    candles = _build_sample_candles(32)
    assert len(candles) == 32
    timestamps = [c["timestamp"] for c in candles]
    assert timestamps == sorted(timestamps)


def test_internal_scenarios_return_expected_keys():
    candles = _build_sample_candles(96)
    results = run_internal_scenarios(candles, symbol="SOL")
    assert set(results.keys()) == {"buy_and_hold", "sma_crossover", "fixed_sl_tp_trend"}
    assert all(v.total_trades >= 0 for v in results.values())


def test_pybroker_adapter_emits_naive_utc_dates_for_strategy_filtering():
    candles = _build_sample_candles(24)
    df = to_pybroker_dataframe(candles, symbol="SOL")
    assert list(df.columns) == ["symbol", "date", "open", "high", "low", "close", "volume"]
    assert df["date"].dt.tz is None
    assert df["date"].is_monotonic_increasing


def test_run_pybroker_scenarios_executes_when_runtime_available():
    if not pybroker_available():
        pytest.skip("pybroker runtime unavailable in this environment")
    candles = _build_sample_candles(120)
    payload = run_pybroker_scenarios(candles, symbol="SOL")

    assert payload["available"] is True
    assert payload["status"] == "completed"
    assert set(payload["results"].keys()) == {"buy_and_hold", "sma_crossover", "fixed_sl_tp_trend"}
    for scenario in payload["results"].values():
        assert "final_capital" in scenario
        assert "total_return_pct" in scenario
        assert "sharpe_ratio" in scenario
        assert "max_drawdown_pct" in scenario
        assert "total_trades" in scenario


def test_comparison_writes_artifact_even_when_pybroker_missing(tmp_path: Path):
    out_file = run_comparison(output_root=tmp_path, symbol="SOL", tolerance_pct=5.0)
    assert out_file.exists()
    payload = out_file.read_text(encoding="utf-8")
    assert '"comparisons"' in payload
    assert '"pybroker"' in payload


def test_fixed_sl_tp_trend_parity_with_pybroker_delay_model():
    if not pybroker_available():
        pytest.skip("pybroker runtime unavailable in this environment")

    candles = _build_sample_candles(180)
    internal = run_internal_scenarios(candles, symbol="SOL")
    pybroker_payload = run_pybroker_scenarios(candles, symbol="SOL")
    comparisons = compare_metrics(internal, pybroker_payload, tolerance_pct=5.0)

    fixed = comparisons["fixed_sl_tp_trend"]
    assert fixed["status"] == "pass"
