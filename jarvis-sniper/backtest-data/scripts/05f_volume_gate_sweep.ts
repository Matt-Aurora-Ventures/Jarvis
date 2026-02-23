/**
 * Phase 5f: Volume Gate Sweep
 *
 * Purpose:
 * - Optimize metadata gates for `volume_spike` using already-simulated trades.
 * - Prefer robust configs (trades >= minTrades) that remain profitable.
 *
 * Inputs:
 * - results/results_volume_spike.json
 *
 * Outputs:
 * - results/gate_sweep_best.json
 * - results/gate_sweep_all.json
 *
 * Run:
 *   npx vite-node backtest-data/scripts/05f_volume_gate_sweep.ts
 */

import { log, logError, readJSON, writeJSON } from './shared/utils';
import type { TradeResult } from './shared/types';

type Candidate = {
  scoreMin: number;
  liqMin: number;
  momMin: number;
  vlrMin: number;
  trades: number;
  winRate: number;
  profitFactor: number;
  expectancyPct: number;
  totalReturnPct: number;
  minPosFrac: number;
  avgPosFrac: number;
  robust: boolean;
  profitable: boolean;
  ranking: number;
};

function envInt(name: string, fallback: number): number {
  const raw = process.env[name];
  const n = raw ? parseInt(raw, 10) : NaN;
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function computeProfitFactor(pnls: number[]): number {
  let wins = 0;
  let losses = 0;
  for (const p of pnls) {
    if (p > 0) wins += p;
    else losses += -p;
  }
  if (losses <= 0) return wins > 0 ? 999 : 0;
  return wins / losses;
}

function rollingPosFrac(pnls: number[], window: number): number | null {
  if (pnls.length < window) return null;
  let sum = 0;
  for (let i = 0; i < window; i++) sum += pnls[i];
  let positive = sum > 0 ? 1 : 0;
  let total = 1;
  for (let i = window; i < pnls.length; i++) {
    sum += pnls[i] - pnls[i - window];
    total++;
    if (sum > 0) positive++;
  }
  return positive / total;
}

function consistency(pnls: number[]): { minPosFrac: number; avgPosFrac: number } {
  const windows = [10, 25, 50];
  const vals: number[] = [];
  for (const w of windows) {
    const v = rollingPosFrac(pnls, w);
    if (v !== null) vals.push(v);
  }
  if (vals.length === 0) return { minPosFrac: 0, avgPosFrac: 0 };
  return {
    minPosFrac: Math.min(...vals),
    avgPosFrac: vals.reduce((s, n) => s + n, 0) / vals.length,
  };
}

function buildCandidate(
  allTrades: TradeResult[],
  scoreMin: number,
  liqMin: number,
  momMin: number,
  vlrMin: number,
  minTrades: number,
): Candidate {
  const filtered = allTrades
    .filter(t =>
      t.score_at_entry >= scoreMin &&
      t.liquidity_at_entry >= liqMin &&
      t.momentum_1h_at_entry >= momMin &&
      t.vol_liq_ratio_at_entry >= vlrMin,
    )
    .sort((a, b) => a.entry_timestamp - b.entry_timestamp);

  const pnls = filtered.map(t => t.pnl_percent);
  const trades = filtered.length;
  const wins = pnls.filter(p => p > 0).length;
  const winRate = trades > 0 ? (wins / trades) * 100 : 0;
  const totalReturnPct = pnls.reduce((s, p) => s + p, 0);
  const expectancyPct = trades > 0 ? totalReturnPct / trades : 0;
  const profitFactor = computeProfitFactor(pnls);
  const { minPosFrac, avgPosFrac } = consistency(pnls);
  const robust = trades >= minTrades;
  const profitable = expectancyPct > 0 && profitFactor > 1;

  // Ranking:
  // 1) robust candidates first
  // 2) profitable first
  // 3) maximize expectancy while preferring stable minPosFrac and sample size
  const ranking =
    (robust ? 10_000 : 0) +
    (profitable ? 1_000 : 0) +
    (expectancyPct * 100) +
    ((profitFactor - 1) * 50) +
    (minPosFrac * 25) +
    Math.log2(trades + 1);

  return {
    scoreMin,
    liqMin,
    momMin,
    vlrMin,
    trades,
    winRate: +winRate.toFixed(2),
    profitFactor: +profitFactor.toFixed(3),
    expectancyPct: +expectancyPct.toFixed(3),
    totalReturnPct: +totalReturnPct.toFixed(2),
    minPosFrac: +minPosFrac.toFixed(3),
    avgPosFrac: +avgPosFrac.toFixed(3),
    robust,
    profitable,
    ranking: +ranking.toFixed(3),
  };
}

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 5f: Volume Gate Sweep');
  log('═══════════════════════════════════════════════════════');

  const trades = readJSON<TradeResult[]>('results/results_volume_spike.json') || [];
  if (trades.length === 0) {
    logError('No volume_spike trades found. Run 05_simulate_trades.ts first.');
    process.exit(1);
  }

  const MIN_TRADES = envInt('GATE_SWEEP_MIN_TRADES', 50);
  const scores = [35, 45, 50, 55, 60, 65];
  const liqs = [20_000, 50_000, 75_000, 100_000, 150_000, 200_000];
  const moms = [0, 2, 5, 8];
  const vlrs = [0.2, 0.4, 0.6, 0.8, 1.0];

  const candidates: Candidate[] = [];
  for (const scoreMin of scores) {
    for (const liqMin of liqs) {
      for (const momMin of moms) {
        for (const vlrMin of vlrs) {
          candidates.push(buildCandidate(trades, scoreMin, liqMin, momMin, vlrMin, MIN_TRADES));
        }
      }
    }
  }

  candidates.sort((a, b) => b.ranking - a.ranking);
  const best = candidates[0];
  const top = candidates.slice(0, 200);

  writeJSON('results/gate_sweep_best.json', {
    algo_id: 'volume_spike',
    minTrades: MIN_TRADES,
    generated_at: new Date().toISOString(),
    best,
  });
  writeJSON('results/gate_sweep_all.json', top);

  log(`Candidates evaluated: ${candidates.length}`);
  log(`Best gates: score>=${best.scoreMin}, liq>=${best.liqMin}, mom>=${best.momMin}, vlr>=${best.vlrMin}`);
  log(`Best metrics: trades=${best.trades}, WR=${best.winRate}%, PF=${best.profitFactor}, exp=${best.expectancyPct}%, minPos=${best.minPosFrac}`);
  log('\n✓ Phase 5f complete');
  log('  → results/gate_sweep_best.json');
  log('  → results/gate_sweep_all.json');
}

main().catch(err => {
  logError('Fatal error in volume gate sweep', err);
  process.exit(1);
});

