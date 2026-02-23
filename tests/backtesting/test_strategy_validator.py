"""Tests for strategy robustness validation utilities."""

from datetime import datetime, timedelta, timezone

import pytest

from core.trading.backtesting.metrics import Trade
from core.trading.backtesting.validator import StrategyValidator


def _build_trades(returns: list[float]) -> list[Trade]:
    """Create deterministic trades from return percentages."""
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    trades: list[Trade] = []
    for idx, pnl_pct in enumerate(returns):
        entry_time = start + timedelta(hours=idx * 2)
        exit_time = entry_time + timedelta(hours=1)
        trades.append(
            Trade(
                entry_time=entry_time,
                exit_time=exit_time,
                entry_price=100.0,
                exit_price=100.0 * (1 + pnl_pct),
                direction="long",
                size=1.0,
                pnl=1000.0 * pnl_pct,
                pnl_pct=pnl_pct,
                fees=0.0,
            )
        )
    return trades


def _equity_curve_from_returns(returns: list[float], initial_capital: float = 1_000_000) -> list[float]:
    equity = [initial_capital]
    current = initial_capital
    for r in returns:
        current *= (1 + r)
        equity.append(current)
    return equity


def test_permutation_returns_none_with_insufficient_trades():
    validator = StrategyValidator(permutation_runs=100, random_seed=7)
    trades = _build_trades([0.01] * 10)
    assert validator._run_permutation_test(trades) is None


def test_permutation_significance_detects_strong_edge():
    # Positive edge should not be explained by random sign permutations.
    returns = [0.04] * 45 + [-0.005] * 15
    trades = _build_trades(returns)
    validator = StrategyValidator(permutation_runs=500, random_seed=7)
    pvalue = validator._run_permutation_test(trades)
    assert pvalue is not None
    assert pvalue < 0.10


def test_permutation_pvalue_is_not_degenerate_for_neutral_edge():
    returns = [0.01, -0.01] * 40
    trades = _build_trades(returns)
    validator = StrategyValidator(permutation_runs=500, random_seed=11)
    pvalue = validator._run_permutation_test(trades)
    assert pvalue is not None
    assert 0.2 <= pvalue <= 0.8


def test_validation_result_exposes_stat_test_metadata():
    returns = [0.02, -0.005, 0.015, -0.01] * 20
    trades = _build_trades(returns)
    equity_curve = _equity_curve_from_returns(returns)
    validator = StrategyValidator(permutation_runs=100, monte_carlo_runs=100, random_seed=13)
    result = validator.validate(
        trades=trades,
        equity_curve=equity_curve,
        start_date=trades[0].entry_time,
        end_date=trades[-1].exit_time,
        initial_capital=equity_curve[0],
    )
    result_dict = result.to_dict()
    assert result_dict["stat_test_method"] == "sign_flip_sharpe"
    assert result_dict["stat_test_runs"] == 100
