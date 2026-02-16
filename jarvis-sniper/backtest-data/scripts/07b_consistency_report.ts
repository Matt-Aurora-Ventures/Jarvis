/**
 * Phase 7b: Consistency Report (No Sweeping)
 *
 * Purpose:
 * - Compute rolling-window consistency metrics for each strategy using the
 *   already-simulated trades in `results/results_{algo}.json`.
 *
 * This is the metric that matches "profitable over 10..1000 trades in succession":
 * for each window size W, compute the fraction of sliding windows whose cumulative
 * pnl% is positive.
 *
 * Run:
 *   npx tsx backtest-data/scripts/07b_consistency_report.ts
 */

import { log, logError, readJSON, writeCSV, writeJSON, ensureDir } from './shared/utils';
import { CURRENT_ALGO_IDS, type AlgoId } from './shared/algo-ids';
import type { TradeResult } from './shared/types';

type WindowSize = 10 | 25 | 50 | 100 | 250 | 500 | 1000;
const WINDOWS: WindowSize[] = [10, 25, 50, 100, 250, 500, 1000];

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

function rollingWindowStats(pnls: number[], window: number): { posFrac: number; minSum: number } | null {
  if (pnls.length < window) return null;
  let sum = 0;
  for (let i = 0; i < window; i++) sum += pnls[i];

  let pos = sum > 0 ? 1 : 0;
  let windows = 1;
  let minSum = sum;

  for (let i = window; i < pnls.length; i++) {
    sum += pnls[i] - pnls[i - window];
    windows += 1;
    if (sum > 0) pos += 1;
    if (sum < minSum) minSum = sum;
  }

  return { posFrac: pos / windows, minSum };
}

function computeConsistency(trades: TradeResult[]): {
  posFracByWindow: Partial<Record<WindowSize, number>>;
  minSumByWindow: Partial<Record<WindowSize, number>>;
  minPosFrac: number;
  avgPosFrac: number;
} {
  const sortedPnls = trades
    .slice()
    .sort((a, b) => a.entry_timestamp - b.entry_timestamp)
    .map(t => t.pnl_percent);

  const posFracByWindow: Partial<Record<WindowSize, number>> = {};
  const minSumByWindow: Partial<Record<WindowSize, number>> = {};
  const computed: number[] = [];

  for (const w of WINDOWS) {
    const st = rollingWindowStats(sortedPnls, w);
    if (!st) continue;
    posFracByWindow[w] = +st.posFrac.toFixed(3);
    minSumByWindow[w] = +st.minSum.toFixed(2);
    computed.push(st.posFrac);
  }

  const minPosFrac = computed.length ? Math.min(...computed) : 0;
  const avgPosFrac = computed.length ? computed.reduce((s, v) => s + v, 0) / computed.length : 0;

  return {
    posFracByWindow,
    minSumByWindow,
    minPosFrac: +minPosFrac.toFixed(3),
    avgPosFrac: +avgPosFrac.toFixed(3),
  };
}

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 7b: Consistency Report');
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  const rows: Record<string, unknown>[] = [];
  const jsonOut: Record<string, unknown> = {};

  for (const algoId of CURRENT_ALGO_IDS) {
    const trades = readJSON<TradeResult[]>(`results/results_${algoId}.json`) || [];
    if (trades.length === 0) {
      log(`  ${algoId}: no trades`);
      continue;
    }

    const pnls = trades.map(t => t.pnl_percent);
    const wins = pnls.filter(p => p > 0).length;
    const total = pnls.reduce((s, p) => s + p, 0);
    const pf = computeProfitFactor(pnls);

    const cons = computeConsistency(trades);

    const row: Record<string, unknown> = {
      algo_id: algoId,
      trades: trades.length,
      win_rate: +(wins / trades.length * 100).toFixed(1),
      profit_factor: +pf.toFixed(3),
      expectancy_pct: +(total / trades.length).toFixed(3),
      total_return_pct: +total.toFixed(2),
      min_pos_frac: cons.minPosFrac,
      avg_pos_frac: cons.avgPosFrac,
    };

    for (const w of WINDOWS) {
      const k = `pos${w}` as const;
      const v = cons.posFracByWindow[w];
      if (v !== undefined) row[k] = v;
    }

    rows.push(row);
    jsonOut[algoId] = { ...row, min_sum_by_window: cons.minSumByWindow };
  }

  rows.sort((a, b) => Number(b.min_pos_frac) - Number(a.min_pos_frac));

  writeCSV('results/consistency_report.csv', rows);
  writeJSON('results/consistency_report.json', jsonOut);

  log('\n✓ Phase 7b complete');
  log('  → results/consistency_report.csv');
  log('  → results/consistency_report.json');
}

main().catch(err => {
  logError('Fatal error in consistency report', err);
  process.exit(1);
});

