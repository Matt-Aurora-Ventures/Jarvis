/**
 * Phase 8: Walk-Forward Validation
 *
 * Purpose:
 * - Validate strategy robustness across chronological folds (train -> validate).
 * - Avoid overfitting by requiring repeated out-of-sample profitability.
 *
 * Run:
 *   npx tsx backtest-data/scripts/08_walkforward_validate.ts
 *
 * Optional env:
 *   WALKFORWARD_FOLDS=5
 *   WALKFORWARD_MIN_VALIDATE_TRADES=10
 */

import { ensureDir, log, logError, readJSON, writeCSV, writeJSON } from './shared/utils';
import { CURRENT_ALGO_IDS } from './shared/algo-ids';
import type { SampleBand, StrategyStatusLabel, TradeResult, WalkforwardFoldMetrics, WalkforwardSummary } from './shared/types';

const STRICT_MIN_TRADES = 100;
const STRICT_MIN_PF = 1.15;
const STRICT_MIN_POS_RATE = 0.60;

function envInt(name: string, fallback: number): number {
  const raw = process.env[name];
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function sampleBand(trades: number): SampleBand {
  if (trades >= 50) return 'ROBUST';
  if (trades >= 25) return 'MEDIUM';
  return 'THIN';
}

function computeProfitFactor(pnls: number[]): number {
  let grossWin = 0;
  let grossLoss = 0;
  for (const p of pnls) {
    if (p > 0) grossWin += p;
    else grossLoss += -p;
  }
  if (grossLoss <= 0) return grossWin > 0 ? 999 : 0;
  return grossWin / grossLoss;
}

function summarize(trades: TradeResult[]): {
  trades: number;
  winRate: number;
  pf: number;
  expectancyPct: number;
  totalReturnPct: number;
} {
  const pnls = trades.map(t => t.pnl_percent);
  const wins = pnls.filter(v => v > 0).length;
  const total = pnls.reduce((s, v) => s + v, 0);
  return {
    trades: trades.length,
    winRate: trades.length ? +(wins / trades.length * 100).toFixed(1) : 0,
    pf: +computeProfitFactor(pnls).toFixed(3),
    expectancyPct: trades.length ? +(total / trades.length).toFixed(3) : 0,
    totalReturnPct: +total.toFixed(2),
  };
}

function classifyStatus(
  fullTrades: number,
  fullPf: number,
  fullExpectancy: number,
  passRate: number,
): StrategyStatusLabel {
  if (fullPf <= 1 || fullExpectancy <= 0) return 'EXPERIMENTAL_DISABLED';
  if (fullTrades >= STRICT_MIN_TRADES && fullPf > STRICT_MIN_PF && passRate >= STRICT_MIN_POS_RATE) return 'PROVEN';
  return 'EXPERIMENTAL';
}

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 8: Walk-Forward Validation');
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  const folds = envInt('WALKFORWARD_FOLDS', 5);
  const minValidateTrades = envInt('WALKFORWARD_MIN_VALIDATE_TRADES', 10);

  const summaryRows: WalkforwardSummary[] = [];
  const foldRows: Record<string, unknown>[] = [];
  const jsonOut: Record<string, WalkforwardSummary> = {};

  for (const algoId of CURRENT_ALGO_IDS) {
    const trades = (readJSON<TradeResult[]>(`results/results_${algoId}.json`) || [])
      .slice()
      .sort((a, b) => a.entry_timestamp - b.entry_timestamp);

    if (trades.length === 0) {
      log(`  ${algoId}: no trades`);
      continue;
    }

    const totalSummary = summarize(trades);
    const block = Math.max(1, Math.floor(trades.length / (folds + 1)));
    const foldMetrics: WalkforwardFoldMetrics[] = [];

    for (let fold = 1; fold <= folds; fold++) {
      const trainEnd = Math.min(trades.length, block * fold);
      const validateStart = trainEnd;
      const validateEnd = fold === folds ? trades.length : Math.min(trades.length, block * (fold + 1));
      const trainTrades = trades.slice(0, trainEnd);
      const validateTrades = trades.slice(validateStart, validateEnd);
      const validateSummary = summarize(validateTrades);

      const row: WalkforwardFoldMetrics = {
        fold,
        train_trades: trainTrades.length,
        validate_trades: validateTrades.length,
        validate_win_rate: validateSummary.winRate,
        validate_profit_factor: validateSummary.pf,
        validate_expectancy_pct: validateSummary.expectancyPct,
        validate_total_return_pct: validateSummary.totalReturnPct,
      };
      foldMetrics.push(row);

      foldRows.push({
        algo_id: algoId,
        ...row,
      });
    }

    const validFolds = foldMetrics.filter(f => f.validate_trades >= minValidateTrades);
    const passFolds = validFolds.filter(f => f.validate_profit_factor > 1 && f.validate_expectancy_pct > 0).length;
    const passRate = validFolds.length > 0 ? +(passFolds / validFolds.length).toFixed(3) : 0;
    const status = classifyStatus(totalSummary.trades, totalSummary.pf, totalSummary.expectancyPct, passRate);

    const summary: WalkforwardSummary = {
      algo_id: algoId,
      folds,
      total_trades: totalSummary.trades,
      validated_trades: validFolds.reduce((s, f) => s + f.validate_trades, 0),
      pass_folds: passFolds,
      fail_folds: Math.max(0, validFolds.length - passFolds),
      pass_rate: passRate,
      sample_band: sampleBand(totalSummary.trades),
      status_label: status,
      fold_metrics: foldMetrics,
    };

    summaryRows.push(summary);
    jsonOut[algoId] = summary;
    log(
      `  ${algoId}: folds=${validFolds.length}/${folds} passRate=${summary.pass_rate} ` +
      `PF=${totalSummary.pf} Exp=${totalSummary.expectancyPct}% status=${summary.status_label}`,
    );
  }

  summaryRows.sort((a, b) => b.pass_rate - a.pass_rate);
  writeCSV(
    'results/walkforward_report.csv',
    summaryRows.map((row) => ({
      algo_id: row.algo_id,
      folds: row.folds,
      total_trades: row.total_trades,
      validated_trades: row.validated_trades,
      pass_folds: row.pass_folds,
      fail_folds: row.fail_folds,
      pass_rate: row.pass_rate,
      sample_band: row.sample_band,
      status_label: row.status_label,
    })),
  );
  writeCSV('results/walkforward_folds.csv', foldRows);
  writeJSON('results/walkforward_report.json', jsonOut);

  log('\n✓ Phase 8 complete');
  log('  → results/walkforward_report.csv');
  log('  → results/walkforward_folds.csv');
  log('  → results/walkforward_report.json');
}

main().catch((err) => {
  logError('Fatal error in walk-forward validation', err);
  process.exit(1);
});
