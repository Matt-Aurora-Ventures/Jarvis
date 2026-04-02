#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

mkdir -p backtest-data/results
TS="$(date -u +%Y%m%d_%H%M%S)"
LOG_FILE="backtest-data/results/run_log_${TS}.md"

echo "# Backtest CI Run Log" > "$LOG_FILE"
echo "" >> "$LOG_FILE"
echo "- started_at_utc: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$LOG_FILE"
echo "- root: $ROOT_DIR" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

if [[ -f backtest-data/results/source_request_log.csv ]]; then
  rm -f backtest-data/results/source_request_log.csv
fi

RUNNER="./node_modules/.bin/tsx"
if [[ ! -x "$RUNNER" ]]; then
  RUNNER="npx --yes tsx"
fi

echo "- runner: \`$RUNNER\`" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

run_step() {
  local script="$1"
  local start end elapsed
  start=$(date +%s)
  echo "## ${script}" >> "$LOG_FILE"
  echo "" >> "$LOG_FILE"
  echo "\`\`\`bash" >> "$LOG_FILE"
  echo "$RUNNER $script" >> "$LOG_FILE"
  echo "\`\`\`" >> "$LOG_FILE"
  echo "" >> "$LOG_FILE"

  set +e
  if [[ "$RUNNER" == "npx --yes tsx" ]]; then
    npx --yes tsx "$script"
  else
    "$RUNNER" "$script"
  fi
  local status=$?
  set -e

  end=$(date +%s)
  elapsed=$((end - start))

  echo "- exit_code: ${status}" >> "$LOG_FILE"
  echo "- elapsed_seconds: ${elapsed}" >> "$LOG_FILE"
  echo "" >> "$LOG_FILE"

  if [[ $status -ne 0 ]]; then
    echo "Run failed at script: $script (exit=$status)"
    exit $status
  fi
}

run_step backtest-data/scripts/01_discover_universe.ts
run_step backtest-data/scripts/02_score_universe.ts
run_step backtest-data/scripts/03_filter_by_algo.ts
run_step backtest-data/scripts/04_fetch_candles.ts
run_step backtest-data/scripts/05_simulate_trades.ts
run_step backtest-data/scripts/06_generate_reports.ts
run_step backtest-data/scripts/07b_consistency_report.ts
run_step backtest-data/scripts/08_walkforward_validate.ts
run_step backtest-data/scripts/05e_equity_sweep.ts
run_step backtest-data/scripts/07_gate_sweep.ts

if [[ -f backtest-data/scripts/05f_volume_gate_sweep.ts ]]; then
  run_step backtest-data/scripts/05f_volume_gate_sweep.ts
fi

run_step backtest-data/scripts/09_generate_recommendations_and_provenance.ts

echo "## Output Artifacts" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
for f in \
  backtest-data/results/master_comparison.csv \
  backtest-data/results/master_comparison.json \
  backtest-data/results/consistency_report.csv \
  backtest-data/results/consistency_report.json \
  backtest-data/results/walkforward_report.csv \
  backtest-data/results/walkforward_report.json \
  backtest-data/results/strategy_recommendations.json \
  backtest-data/results/strategy_recommendations.md \
  backtest-data/results/provenance_manifest.json \
  backtest-data/results/source_request_log.csv \
  backtest-data/results/source_coverage.json \
  backtest-data/results/dataset_hashes.json \
  backtest-data/results/evidence_report.md; do
  if [[ -f "$f" ]]; then
    echo "- ✅ $f" >> "$LOG_FILE"
  else
    echo "- ❌ $f" >> "$LOG_FILE"
  fi
done

echo "" >> "$LOG_FILE"
echo "- completed_at_utc: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
echo "Backtest CI run complete. Log: $LOG_FILE"
