"""Backtest contract gate runner for CI."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NPM_EXECUTABLE = "npm.cmd" if sys.platform.startswith("win") else "npm"

PY_CONTRACT_TESTS = [
    "tests/unit/test_core_backtester.py::TestIndicators::test_ema_insufficient_data",
    "tests/unit/test_core_backtester.py::TestIndicators::test_rsi_returns_50_insufficient_data",
    "tests/unit/test_core_backtester.py::TestTradingMethods::test_close_position_long_uses_exit_value_once",
    "tests/backtesting/test_backtest.py::TestEngineParity::test_legacy_and_advanced_engine_capital_parity",
    "tests/backtesting/test_strategy_validator.py",
]

TS_CONTRACT_TESTS = [
    "src/__tests__/backtest-route-execution-realism.test.ts",
    "src/__tests__/rpc-and-backtest-regressions.test.ts",
    "src/__tests__/backtest-cost-accounting.test.ts",
]


def _run(cmd: list[str], cwd: Path) -> None:
    rendered = " ".join(shlex.quote(part) for part in cmd)
    print(f"$ {rendered}")
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> int:
    _run([sys.executable, "-m", "pytest", "-q", *PY_CONTRACT_TESTS], REPO_ROOT)
    _run([NPM_EXECUTABLE, "run", "-s", "test", "--", *TS_CONTRACT_TESTS], REPO_ROOT / "jarvis-sniper")
    print("Backtest contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
