# Backtest Statistical Validation Contract

## Permutation Test Method
Backtest significance now uses a **sign-flip Sharpe null model** in `core/trading/backtesting/validator.py`.

## Why sign-flip
1. Return shuffling preserves the same sample mean and variance, making Sharpe effectively order-invariant.
2. Sign-flip keeps magnitudes but randomizes direction, creating a meaningful null for directional edge.
3. This produces informative p-values for both strong-edge and neutral-edge strategy samples.

## Implementation Notes
1. `StrategyValidator` accepts `random_seed` for deterministic validation.
2. `ValidationResult` now exposes:
   - `stat_test_method`
   - `stat_test_runs`
3. `permutation_pvalue` uses add-one smoothing:
   - `p = (count_better + 1) / (runs + 1)`

## Regression Coverage
`tests/backtesting/test_strategy_validator.py` validates:
1. insufficient sample returns `None`,
2. strong edge yields low p-value,
3. neutral edge yields non-degenerate p-value,
4. result metadata exposes method and run count.

## Equity and Drawdown Accounting Note
Long-position equity tracking in both Python engines now uses:

1. `equity = cash + position_market_value` for long positions,
2. `equity = cash + unrealized_pnl` for short positions (current margin model).

This eliminates false catastrophic drawdowns during flat-price long holds and
keeps drawdown interpretation consistent with deployed capital.
