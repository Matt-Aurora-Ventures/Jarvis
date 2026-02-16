import { ensureDir, log, logError, readJSON, writeCSV, writeJSON } from './shared/utils';
import type { TradeResult } from './shared/types';

interface Row {
  algo_id: string;
  trades: number;
  win_rate: number;
  expectancy_pct: number;
  profit_factor: number;
  min_pos_frac: number;
  status: string;
  sample_band: 'ROBUST' | 'MEDIUM' | 'THIN';
  notes: string;
}

const ALGO_IDS = [
  'pump_fresh_tight', 'micro_cap_surge', 'elite', 'momentum', 'hybrid_b', 'let_it_ride',
  'sol_veteran', 'utility_swing', 'established_breakout', 'meme_classic', 'volume_spike',
  'bags_fresh_snipe', 'bags_momentum', 'bags_value', 'bags_dip_buyer', 'bags_bluechip',
  'bags_conservative', 'bags_aggressive', 'bags_elite', 'bluechip_trend_follow', 'bluechip_breakout',
  'xstock_intraday', 'xstock_swing', 'prestock_speculative', 'index_intraday', 'index_leveraged',
];

function rollingMinPosFrac(trades: TradeResult[], window = 20): number {
  if (trades.length === 0) return 0;
  if (trades.length < window) {
    const p = trades.filter(t => t.pnl_percent > 0).length / trades.length;
    return +p.toFixed(3);
  }
  let min = 1;
  for (let i = 0; i <= trades.length - window; i++) {
    const slice = trades.slice(i, i + window);
    const p = slice.filter(t => t.pnl_percent > 0).length / window;
    if (p < min) min = p;
  }
  return +min.toFixed(3);
}

function computePF(trades: TradeResult[]): number {
  const wins = trades.filter(t => t.pnl_percent > 0).reduce((s, t) => s + t.pnl_percent, 0);
  const losses = Math.abs(trades.filter(t => t.pnl_percent <= 0).reduce((s, t) => s + t.pnl_percent, 0));
  if (losses === 0) return wins > 0 ? 999 : 0;
  return +(wins / losses).toFixed(3);
}

function main(): void {
  log('Phase 7b: Consistency report');
  ensureDir('results');

  const rows: Row[] = [];

  for (const algoId of ALGO_IDS) {
    const trades = readJSON<TradeResult[]>(`results/results_${algoId}.json`) || [];
    if (trades.length === 0) {
      rows.push({
        algo_id: algoId,
        trades: 0,
        win_rate: 0,
        expectancy_pct: 0,
        profit_factor: 0,
        min_pos_frac: 0,
        status: 'NO_DATA',
        sample_band: 'THIN',
        notes: 'No trades generated',
      });
      continue;
    }

    const winRate = +(trades.filter(t => t.pnl_percent > 0).length / trades.length * 100).toFixed(1);
    const expectancy = +(trades.reduce((s, t) => s + t.pnl_percent, 0) / trades.length).toFixed(3);
    const pf = computePF(trades);
    const minPos = rollingMinPosFrac(trades, 20);

    const sampleBand: Row['sample_band'] = trades.length >= 50 ? 'ROBUST' : trades.length >= 25 ? 'MEDIUM' : 'THIN';
    let status = minPos >= 0.7 ? 'PASS' : 'FAIL';
    let notes = '';

    if (sampleBand === 'THIN') notes = 'THIN_SAMPLE';
    if (algoId === 'xstock_swing' && (expectancy < 0 || pf < 1)) {
      status = 'EXPERIMENTAL_DISABLED';
      notes = 'Losing across sweeps; keep experimental/disabled';
    }

    rows.push({
      algo_id: algoId,
      trades: trades.length,
      win_rate: winRate,
      expectancy_pct: expectancy,
      profit_factor: pf,
      min_pos_frac: minPos,
      status,
      sample_band: sampleBand,
      notes,
    });
  }

  rows.sort((a, b) => b.min_pos_frac - a.min_pos_frac);
  writeCSV('results/consistency_report.csv', rows as unknown as Record<string, unknown>[]);
  writeJSON('results/consistency_report.json', rows);
  log('Wrote consistency report');
}

main();
