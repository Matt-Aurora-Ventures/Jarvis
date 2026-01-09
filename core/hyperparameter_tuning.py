"""
Hyperparameter Tuning with Optuna.

Uses Optuna to optimize trading strategy parameters through
backtesting. Supports multiple objectives (profit, risk-adjusted return).
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
TUNING_DIR = ROOT / "data" / "tuning"
STUDIES_FILE = TUNING_DIR / "studies.json"

# Check for Optuna availability
try:
    import optuna
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    optuna = None


@dataclass
class TuningResult:
    """Result of a hyperparameter tuning session."""
    study_name: str
    n_trials: int
    best_params: Dict[str, Any]
    best_value: float
    objective: str
    symbol: str
    interval: str
    duration_seconds: float
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "study_name": self.study_name,
            "n_trials": self.n_trials,
            "best_params": self.best_params,
            "best_value": self.best_value,
            "objective": self.objective,
            "symbol": self.symbol,
            "interval": self.interval,
            "duration_seconds": self.duration_seconds,
            "created_at": self.created_at,
        }


def is_available() -> bool:
    """Check if Optuna is available."""
    return OPTUNA_AVAILABLE


def _get_param_space(strategy_kind: str) -> Dict[str, Tuple[str, Any]]:
    """
    Get the parameter space for a strategy.

    Returns dict of param_name -> (type, bounds/choices)
    Types: "int", "float", "categorical"
    """
    if strategy_kind == "sma_cross":
        return {
            "fast_period": ("int", (5, 30)),
            "slow_period": ("int", (20, 100)),
            "stop_loss_pct": ("float", (0.02, 0.10)),
            "take_profit_pct": ("float", (0.04, 0.20)),
        }
    elif strategy_kind == "rsi_reversion":
        return {
            "period": ("int", (7, 21)),
            "oversold": ("int", (20, 40)),
            "overbought": ("int", (60, 80)),
            "stop_loss_pct": ("float", (0.02, 0.10)),
            "take_profit_pct": ("float", (0.04, 0.20)),
        }
    elif strategy_kind == "bollinger_breakout":
        return {
            "period": ("int", (15, 50)),
            "std_dev": ("float", (1.5, 3.0)),
            "stop_loss_pct": ("float", (0.02, 0.10)),
            "take_profit_pct": ("float", (0.04, 0.20)),
        }
    else:
        # Generic parameters for unknown strategies
        return {
            "stop_loss_pct": ("float", (0.02, 0.10)),
            "take_profit_pct": ("float", (0.04, 0.20)),
        }


def _sample_params(trial, param_space: Dict[str, Tuple[str, Any]]) -> Dict[str, Any]:
    """Sample parameters from the search space using Optuna trial."""
    params = {}
    for name, (ptype, bounds) in param_space.items():
        if ptype == "int":
            params[name] = trial.suggest_int(name, bounds[0], bounds[1])
        elif ptype == "float":
            params[name] = trial.suggest_float(name, bounds[0], bounds[1])
        elif ptype == "categorical":
            params[name] = trial.suggest_categorical(name, bounds)
    return params


def tune_strategy(
    symbol: str,
    interval: str,
    strategy_kind: str = "sma_cross",
    n_trials: int = 50,
    objective: str = "sharpe_ratio",
    timeout_seconds: Optional[int] = None,
    candles: Optional[List[Dict[str, Any]]] = None,
) -> Optional[TuningResult]:
    """
    Tune strategy parameters using Optuna.

    Args:
        symbol: Trading symbol
        interval: Candle interval
        strategy_kind: Strategy type to tune
        n_trials: Number of optimization trials
        objective: Optimization objective (sharpe_ratio, profit_factor, roi, win_rate)
        timeout_seconds: Maximum time for optimization
        candles: Optional pre-loaded candle data

    Returns:
        TuningResult with best parameters or None if failed
    """
    if not OPTUNA_AVAILABLE:
        logger.error("Optuna not installed: pip install optuna")
        return None

    from core import trading_pipeline

    # Load candle data if not provided
    if candles is None:
        try:
            from core import hyperliquid
            path = hyperliquid.latest_snapshot_for_coin(symbol.upper(), interval=interval)
            if path and path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                candles = data.get("candles", [])
            else:
                logger.error(f"No candle data found for {symbol}")
                return None
        except Exception as e:
            logger.error(f"Failed to load candles: {e}")
            return None

    if not candles or len(candles) < 100:
        logger.error(f"Insufficient candle data: {len(candles) if candles else 0}")
        return None

    param_space = _get_param_space(strategy_kind)
    start_time = datetime.now(timezone.utc)

    def objective_fn(trial) -> float:
        """Optuna objective function."""
        # Sample parameters
        params = _sample_params(trial, param_space)

        # Extract strategy-specific params
        strategy_params = {k: v for k, v in params.items()
                         if k not in ("stop_loss_pct", "take_profit_pct")}

        # Create strategy config
        config = trading_pipeline.StrategyConfig(
            kind=strategy_kind,
            params=strategy_params,
            stop_loss_pct=params.get("stop_loss_pct", 0.05),
            take_profit_pct=params.get("take_profit_pct", 0.10),
        )

        # Run backtest
        try:
            result = trading_pipeline.backtest(
                candles=candles,
                symbol=symbol,
                interval=interval,
                strategy=config,
            )

            if result.error:
                return float("-inf")

            # Return objective value
            if objective == "sharpe_ratio":
                return result.sharpe_ratio
            elif objective == "profit_factor":
                return result.profit_factor
            elif objective == "roi":
                return result.roi
            elif objective == "win_rate":
                return result.win_rate
            elif objective == "expectancy":
                return result.expectancy
            else:
                return result.sharpe_ratio

        except Exception as e:
            logger.debug(f"Trial failed: {e}")
            return float("-inf")

    # Create and run study
    study_name = f"{symbol}_{strategy_kind}_{int(start_time.timestamp())}"

    try:
        study = optuna.create_study(
            study_name=study_name,
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=42),
        )

        # Suppress Optuna logging
        optuna.logging.set_verbosity(optuna.logging.WARNING)

        study.optimize(
            objective_fn,
            n_trials=n_trials,
            timeout=timeout_seconds,
            show_progress_bar=False,
        )

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        result = TuningResult(
            study_name=study_name,
            n_trials=len(study.trials),
            best_params=study.best_params,
            best_value=study.best_value,
            objective=objective,
            symbol=symbol,
            interval=interval,
            duration_seconds=duration,
            created_at=start_time.isoformat(),
        )

        # Save result
        _save_study_result(result)

        logger.info(
            f"Tuning complete: {study_name} "
            f"Best {objective}: {study.best_value:.4f} "
            f"Params: {study.best_params}"
        )

        return result

    except Exception as e:
        logger.error(f"Tuning failed: {e}")
        return None


def tune_solana_token(
    mint: str,
    symbol: str = "TOKEN",
    pool_address: Optional[str] = None,
    strategy_kind: str = "sma_cross",
    n_trials: int = 30,
    objective: str = "sharpe_ratio",
) -> Optional[TuningResult]:
    """
    Tune strategy for a Solana token using GeckoTerminal data.

    Args:
        mint: Token mint address
        symbol: Token symbol
        pool_address: LP pool address (if known)
        strategy_kind: Strategy type
        n_trials: Number of trials
        objective: Optimization objective

    Returns:
        TuningResult or None
    """
    if not OPTUNA_AVAILABLE:
        logger.error("Optuna not installed")
        return None

    # Fetch candle data from GeckoTerminal
    try:
        from core.geckoterminal import fetch_pool_ohlcv, normalize_ohlcv_list

        if not pool_address:
            # Try to find pool from DexScreener
            from core import dexscreener
            result = dexscreener.search_token(mint)
            if result.success and result.data:
                pairs = result.data.get("pairs", [])
                for pair in pairs:
                    if pair.get("chainId") == "solana":
                        pool_address = pair.get("pairAddress")
                        break

        if not pool_address:
            logger.error(f"Could not find pool for {mint}")
            return None

        # Fetch OHLCV data
        payload = fetch_pool_ohlcv("solana", pool_address, "hour", limit=500)
        if not payload:
            logger.error("Failed to fetch OHLCV data")
            return None

        ohlcv_list = payload.get("data", {}).get("attributes", {}).get("ohlcv_list", [])
        if not ohlcv_list:
            logger.error("No OHLCV data returned")
            return None

        candles = normalize_ohlcv_list(sorted(ohlcv_list, key=lambda x: x[0]))

        return tune_strategy(
            symbol=symbol,
            interval="hour",
            strategy_kind=strategy_kind,
            n_trials=n_trials,
            objective=objective,
            candles=candles,
        )

    except Exception as e:
        logger.error(f"Solana token tuning failed: {e}")
        return None


def _save_study_result(result: TuningResult) -> None:
    """Save study result to disk."""
    TUNING_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing studies
    studies = []
    if STUDIES_FILE.exists():
        try:
            studies = json.loads(STUDIES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Add new result
    studies.append(result.to_dict())

    # Keep only last 100 studies
    if len(studies) > 100:
        studies = studies[-100:]

    # Save
    STUDIES_FILE.write_text(
        json.dumps(studies, indent=2),
        encoding="utf-8"
    )


def get_recent_studies(limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent tuning studies."""
    if not STUDIES_FILE.exists():
        return []

    try:
        studies = json.loads(STUDIES_FILE.read_text(encoding="utf-8"))
        return list(reversed(studies[-limit:]))
    except Exception:
        return []


def get_best_params(symbol: str, strategy_kind: str) -> Optional[Dict[str, Any]]:
    """Get the best parameters from recent tuning for a symbol/strategy."""
    studies = get_recent_studies(limit=50)

    best_value = float("-inf")
    best_params = None

    for study in studies:
        if study.get("symbol") == symbol and strategy_kind in study.get("study_name", ""):
            if study.get("best_value", 0) > best_value:
                best_value = study["best_value"]
                best_params = study.get("best_params")

    return best_params


# CLI entry point
if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO)

    if not OPTUNA_AVAILABLE:
        print("Optuna not installed. Run: pip install optuna")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Tune trading strategy parameters")
    parser.add_argument("symbol", help="Trading symbol (e.g., BTC, ETH)")
    parser.add_argument("--interval", default="1h", help="Candle interval")
    parser.add_argument("--strategy", default="sma_cross", help="Strategy type")
    parser.add_argument("--trials", type=int, default=50, help="Number of trials")
    parser.add_argument("--objective", default="sharpe_ratio", help="Optimization objective")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds")

    args = parser.parse_args()

    print(f"Tuning {args.strategy} for {args.symbol} ({args.interval})")
    print(f"Trials: {args.trials}, Objective: {args.objective}")
    print("-" * 50)

    result = tune_strategy(
        symbol=args.symbol,
        interval=args.interval,
        strategy_kind=args.strategy,
        n_trials=args.trials,
        objective=args.objective,
        timeout_seconds=args.timeout,
    )

    if result:
        print("\nOptimization Complete!")
        print(f"Best {args.objective}: {result.best_value:.4f}")
        print(f"Best parameters: {json.dumps(result.best_params, indent=2)}")
        print(f"Duration: {result.duration_seconds:.1f}s")
    else:
        print("\nOptimization failed")
        sys.exit(1)
