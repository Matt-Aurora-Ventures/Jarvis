#!/usr/bin/env bash
set -euo pipefail

SKIP_JS="${SKIP_JS:-0}"
SKIP_PYBROKER="${SKIP_PYBROKER:-0}"
STRICT_PYBROKER="${STRICT_PYBROKER:-0}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

TS="$(date -u +%Y%m%d-%H%M%S)"
ARTIFACT_DIR="$REPO_ROOT/artifacts/backtest_validation/$TS"
mkdir -p "$ARTIFACT_DIR"

echo "Running Python backtest contract tests..."
python -m pytest -q \
  tests/backtesting \
  tests/unit/test_backtester.py \
  tests/unit/test_core_backtester.py \
  tests/backtesting/test_strategy_validator.py

if [[ "$SKIP_JS" != "1" ]]; then
  echo "Running jarvis-sniper backtest test suite..."
  (
    cd "$REPO_ROOT/jarvis-sniper"
    npm run -s test -- \
      src/__tests__/bags-backtest.test.ts \
      src/__tests__/bags-backtest-api.test.ts \
      src/__tests__/backtest-route-execution-realism.test.ts \
      src/__tests__/backtest-campaign-orchestrator.test.ts \
      src/__tests__/backtest-artifact-integrity.test.ts \
      src/__tests__/rpc-and-backtest-regressions.test.ts \
      src/__tests__/backtest-cost-accounting.test.ts
  )
fi

if [[ "$SKIP_PYBROKER" != "1" ]]; then
  echo "Running pybroker comparison harness..."
  python tools/backtesting/pybroker_compare.py --output-root artifacts/backtest_compare
  if [[ "$STRICT_PYBROKER" == "1" ]]; then
    echo "Running strict pybroker comparison assertion..."
    python scripts/backtesting/assert_pybroker_comparison.py --artifact-root artifacts/backtest_compare --strict --enforce-parity
  else
    echo "Running warning-mode pybroker comparison assertion..."
    python scripts/backtesting/assert_pybroker_comparison.py --artifact-root artifacts/backtest_compare
  fi
fi

echo "Backtest validation complete. Artifacts dir: $ARTIFACT_DIR"
