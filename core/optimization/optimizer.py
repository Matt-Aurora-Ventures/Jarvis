"""
Strategy Parameter Optimizer
Prompt #92: Hyperparameter tuning using Optuna

Optimizes trading strategy parameters using Bayesian optimization.
"""

import asyncio
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
import json

try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

from core.optimization.parameter_space import ParameterSpace, Parameter, ParameterType
from core.optimization.backtest import Backtester, BacktestResult

logger = logging.getLogger("jarvis.optimization.optimizer")


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class OptimizationResult:
    """Result of optimization run"""
    strategy_name: str
    best_parameters: Dict[str, Any]
    best_value: float
    best_backtest: Optional[BacktestResult]
    n_trials: int
    optimization_time_seconds: float
    all_trials: List[Dict[str, Any]] = field(default_factory=list)
    convergence_history: List[float] = field(default_factory=list)


@dataclass
class OptimizationConfig:
    """Configuration for optimization"""
    n_trials: int = 100
    timeout_seconds: Optional[int] = None
    objective: str = "sharpe_ratio"  # sharpe_ratio, total_return, win_rate
    n_jobs: int = 1
    show_progress: bool = True
    early_stopping_patience: int = 20


# =============================================================================
# STRATEGY OPTIMIZER
# =============================================================================

class StrategyOptimizer:
    """
    Optimizes trading strategy parameters using Optuna.

    Features:
    - Bayesian optimization with TPE sampler
    - Multiple objective functions
    - Early stopping
    - Result persistence
    - Parallel optimization
    """

    def __init__(
        self,
        backtester: Backtester = None,
        db_path: str = None,
    ):
        self.backtester = backtester or Backtester()
        self.db_path = db_path or os.getenv(
            "OPTIMIZATION_DB",
            "data/optimization.db"
        )

        if not OPTUNA_AVAILABLE:
            logger.warning("Optuna not installed. Using random search.")

        self._init_database()

    def _init_database(self):
        """Initialize results database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimization_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                n_trials INTEGER,
                best_value REAL,
                best_parameters TEXT,
                objective TEXT,
                status TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS optimization_trials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                trial_number INTEGER,
                parameters TEXT,
                value REAL,
                timestamp TEXT,
                FOREIGN KEY (run_id) REFERENCES optimization_runs(id)
            )
        """)

        conn.commit()
        conn.close()

    # =========================================================================
    # OPTIMIZATION
    # =========================================================================

    async def optimize(
        self,
        strategy_func: Callable,
        parameter_space: ParameterSpace,
        price_data: List[Dict[str, Any]],
        config: OptimizationConfig = None,
    ) -> OptimizationResult:
        """
        Optimize strategy parameters.

        Args:
            strategy_func: Strategy function to optimize
            parameter_space: Parameter search space
            price_data: Historical price data
            config: Optimization configuration

        Returns:
            OptimizationResult with best parameters
        """
        config = config or OptimizationConfig()
        start_time = datetime.now(timezone.utc)

        # Record run start
        run_id = await self._record_run_start(
            parameter_space.name, config.n_trials, config.objective
        )

        if OPTUNA_AVAILABLE:
            result = await self._optimize_with_optuna(
                strategy_func, parameter_space, price_data, config, run_id
            )
        else:
            result = await self._optimize_random_search(
                strategy_func, parameter_space, price_data, config, run_id
            )

        # Record completion
        await self._record_run_complete(
            run_id, result.best_value, result.best_parameters
        )

        result.optimization_time_seconds = (
            datetime.now(timezone.utc) - start_time
        ).total_seconds()

        return result

    async def _optimize_with_optuna(
        self,
        strategy_func: Callable,
        parameter_space: ParameterSpace,
        price_data: List[Dict[str, Any]],
        config: OptimizationConfig,
        run_id: int,
    ) -> OptimizationResult:
        """Optimize using Optuna"""

        # Create objective function
        all_trials = []
        convergence_history = []
        best_backtest = None
        best_value = float('-inf')

        def objective(trial: optuna.Trial) -> float:
            nonlocal best_backtest, best_value

            # Sample parameters
            params = {}
            for param in parameter_space.parameters:
                params[param.name] = self._suggest_param(trial, param)

            # Run backtest
            result = asyncio.run(self.backtester.run(
                strategy_func=strategy_func,
                parameters=params,
                price_data=price_data,
                strategy_name=parameter_space.name,
            ))

            # Get objective value
            if config.objective == "sharpe_ratio":
                value = result.sharpe_ratio
            elif config.objective == "total_return":
                value = result.total_return_pct
            elif config.objective == "win_rate":
                value = result.win_rate
            elif config.objective == "sortino_ratio":
                value = result.sortino_ratio
            else:
                value = result.sharpe_ratio

            # Track trial
            all_trials.append({
                "trial": trial.number,
                "parameters": params,
                "value": value,
                "total_return": result.total_return_pct,
                "win_rate": result.win_rate,
            })

            # Track best
            if value > best_value:
                best_value = value
                best_backtest = result

            convergence_history.append(best_value)

            # Record trial
            asyncio.run(self._record_trial(
                run_id, trial.number, params, value
            ))

            return value

        # Create study
        sampler = TPESampler(seed=42)
        study = optuna.create_study(
            direction="maximize",
            sampler=sampler,
        )

        # Optimize
        study.optimize(
            objective,
            n_trials=config.n_trials,
            timeout=config.timeout_seconds,
            show_progress_bar=config.show_progress,
            n_jobs=config.n_jobs,
        )

        return OptimizationResult(
            strategy_name=parameter_space.name,
            best_parameters=study.best_params,
            best_value=study.best_value,
            best_backtest=best_backtest,
            n_trials=len(study.trials),
            optimization_time_seconds=0,  # Set later
            all_trials=all_trials,
            convergence_history=convergence_history,
        )

    async def _optimize_random_search(
        self,
        strategy_func: Callable,
        parameter_space: ParameterSpace,
        price_data: List[Dict[str, Any]],
        config: OptimizationConfig,
        run_id: int,
    ) -> OptimizationResult:
        """Fallback random search optimization"""
        best_params = None
        best_value = float('-inf')
        best_backtest = None
        all_trials = []
        convergence_history = []

        for i in range(config.n_trials):
            # Sample random parameters
            params = parameter_space.sample()

            # Run backtest
            result = await self.backtester.run(
                strategy_func=strategy_func,
                parameters=params,
                price_data=price_data,
                strategy_name=parameter_space.name,
            )

            # Get objective value
            if config.objective == "sharpe_ratio":
                value = result.sharpe_ratio
            elif config.objective == "total_return":
                value = result.total_return_pct
            elif config.objective == "win_rate":
                value = result.win_rate
            else:
                value = result.sharpe_ratio

            all_trials.append({
                "trial": i,
                "parameters": params,
                "value": value,
            })

            if value > best_value:
                best_value = value
                best_params = params
                best_backtest = result

            convergence_history.append(best_value)

            await self._record_trial(run_id, i, params, value)

            if config.show_progress and i % 10 == 0:
                logger.info(f"Trial {i}/{config.n_trials}, best: {best_value:.4f}")

        return OptimizationResult(
            strategy_name=parameter_space.name,
            best_parameters=best_params or {},
            best_value=best_value,
            best_backtest=best_backtest,
            n_trials=config.n_trials,
            optimization_time_seconds=0,
            all_trials=all_trials,
            convergence_history=convergence_history,
        )

    def _suggest_param(self, trial: "optuna.Trial", param: Parameter) -> Any:
        """Suggest a parameter value using Optuna"""
        if param.param_type == ParameterType.FLOAT:
            return trial.suggest_float(
                param.name,
                param.low,
                param.high,
                log=param.log_scale,
            )
        elif param.param_type == ParameterType.INT:
            return trial.suggest_int(
                param.name,
                int(param.low),
                int(param.high),
                step=int(param.step) if param.step else 1,
            )
        elif param.param_type == ParameterType.CATEGORICAL:
            return trial.suggest_categorical(param.name, param.choices)
        elif param.param_type == ParameterType.BOOLEAN:
            return trial.suggest_categorical(param.name, [True, False])
        else:
            return param.default

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    async def analyze_importance(
        self,
        result: OptimizationResult,
    ) -> Dict[str, float]:
        """Analyze parameter importance from optimization results"""
        if not OPTUNA_AVAILABLE:
            return {}

        # Calculate importance based on variance contribution
        # Simplified approach using correlation with objective
        if len(result.all_trials) < 10:
            return {}

        importances = {}
        values = [t["value"] for t in result.all_trials]

        for param_name in result.best_parameters.keys():
            param_values = []
            for trial in result.all_trials:
                params = trial.get("parameters", {})
                if param_name in params:
                    val = params[param_name]
                    if isinstance(val, (int, float)):
                        param_values.append(val)
                    elif isinstance(val, bool):
                        param_values.append(1 if val else 0)
                    else:
                        param_values.append(hash(str(val)) % 100)

            if len(param_values) == len(values):
                # Calculate correlation
                import statistics
                if len(set(param_values)) > 1:  # Need variance
                    mean_p = statistics.mean(param_values)
                    mean_v = statistics.mean(values)
                    std_p = statistics.stdev(param_values)
                    std_v = statistics.stdev(values)

                    if std_p > 0 and std_v > 0:
                        covariance = sum(
                            (p - mean_p) * (v - mean_v)
                            for p, v in zip(param_values, values)
                        ) / len(values)
                        correlation = covariance / (std_p * std_v)
                        importances[param_name] = abs(correlation)

        # Normalize
        total = sum(importances.values()) or 1
        return {k: v / total for k, v in importances.items()}

    async def get_optimization_history(
        self,
        strategy_name: str = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get historical optimization runs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT * FROM optimization_runs
            WHERE status = 'completed'
        """
        params = []

        if strategy_name:
            query += " AND strategy_name = ?"
            params.append(strategy_name)

        query += " ORDER BY completed_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        columns = [d[0] for d in cursor.description]
        runs = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return runs

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    async def _record_run_start(
        self,
        strategy_name: str,
        n_trials: int,
        objective: str,
    ) -> int:
        """Record optimization run start"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO optimization_runs
            (strategy_name, started_at, n_trials, objective, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            strategy_name,
            datetime.now(timezone.utc).isoformat(),
            n_trials,
            objective,
            "running",
        ))

        run_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return run_id

    async def _record_run_complete(
        self,
        run_id: int,
        best_value: float,
        best_parameters: Dict[str, Any],
    ):
        """Record optimization run completion"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE optimization_runs SET
                completed_at = ?,
                best_value = ?,
                best_parameters = ?,
                status = ?
            WHERE id = ?
        """, (
            datetime.now(timezone.utc).isoformat(),
            best_value,
            json.dumps(best_parameters),
            "completed",
            run_id,
        ))

        conn.commit()
        conn.close()

    async def _record_trial(
        self,
        run_id: int,
        trial_number: int,
        parameters: Dict[str, Any],
        value: float,
    ):
        """Record a single trial"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO optimization_trials
            (run_id, trial_number, parameters, value, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (
            run_id,
            trial_number,
            json.dumps(parameters),
            value,
            datetime.now(timezone.utc).isoformat(),
        ))

        conn.commit()
        conn.close()

    async def save_result(
        self,
        result: OptimizationResult,
        path: str = None,
    ):
        """Save optimization result to file"""
        path = path or f"data/optimization_{result.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        os.makedirs(os.path.dirname(path), exist_ok=True)

        data = {
            "strategy_name": result.strategy_name,
            "best_parameters": result.best_parameters,
            "best_value": result.best_value,
            "n_trials": result.n_trials,
            "optimization_time_seconds": result.optimization_time_seconds,
            "convergence_history": result.convergence_history,
            "all_trials": result.all_trials,
        }

        with open(path, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved optimization result to {path}")


# =============================================================================
# SINGLETON
# =============================================================================

_optimizer: Optional[StrategyOptimizer] = None


def get_strategy_optimizer() -> StrategyOptimizer:
    """Get or create the strategy optimizer singleton"""
    global _optimizer
    if _optimizer is None:
        _optimizer = StrategyOptimizer()
    return _optimizer
