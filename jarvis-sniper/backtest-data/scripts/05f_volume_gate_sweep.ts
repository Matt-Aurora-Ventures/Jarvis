import { log, readJSON, writeJSON } from './shared/utils';
import type { ScoredToken, TradeResult } from './shared/types';

interface GateRes {
  min_score: number;
  min_liquidity_usd: number;
  min_age_hours: number;
  min_vol_liq_ratio: number;
  trades: number;
  min_pos_frac: number;
  expectancy_pct: number;
  profit_factor: number;
}

function minPosFrac(pnls: number[], window = 20): number {
  if (pnls.length === 0) return 0;
  if (pnls.length < window) return +(pnls.filter(v => v > 0).length / pnls.length).toFixed(3);
  let min = 1;
  for (let i = 0; i <= pnls.length - window; i++) {
    const p = pnls.slice(i, i + window).filter(v => v > 0).length / window;
    min = Math.min(min, p);
  }
  return +min.toFixed(3);
}

function pf(pnls: number[]): number {
  const w = pnls.filter(v => v > 0).reduce((s, v) => s + v, 0);
  const l = Math.abs(pnls.filter(v => v <= 0).reduce((s, v) => s + v, 0));
  if (l === 0) return w > 0 ? 999 : 0;
  return +(w / l).toFixed(3);
}

function main(): void {
  const tokens = readJSON<(ScoredToken & { age_hours?: number; vol_liq_ratio?: number })[]>('qualified/qualified_volume_spike.json') || [];
  const trades = readJSON<TradeResult[]>('results/results_volume_spike.json') || [];
  const tokenMap = new Map(tokens.map(t => [t.mint, t]));

  const scores = [35, 40, 45, 50];
  const liqs = [20000, 30000, 40000, 50000];
  const ages = [720, 1440, 2160];
  const ratios = [0.3, 0.45, 0.6, 0.8];

  const all: GateRes[] = [];

  for (const minScore of scores) {
    for (const minLiq of liqs) {
      for (const minAge of ages) {
        for (const minRatio of ratios) {
          const allowed = new Set(tokens.filter(t => {
            const age = t.age_hours ?? Infinity;
            const ratio = t.vol_liq_ratio ?? (t.liquidity_usd > 0 ? t.volume_24h_usd / t.liquidity_usd : 0);
            return t.score >= minScore && t.liquidity_usd >= minLiq && age >= minAge && ratio >= minRatio;
          }).map(t => t.mint));

          const filtered = trades.filter(tr => allowed.has(tr.mint));
          const pnls = filtered.map(t => t.pnl_percent);
          if (pnls.length < 20) continue;
          all.push({
            min_score: minScore,
            min_liquidity_usd: minLiq,
            min_age_hours: minAge,
            min_vol_liq_ratio: minRatio,
            trades: pnls.length,
            min_pos_frac: minPosFrac(pnls),
            expectancy_pct: +(pnls.reduce((s, v) => s + v, 0) / pnls.length).toFixed(3),
            profit_factor: pf(pnls),
          });
        }
      }
    }
  }

  all.sort((a, b) => {
    const ar = a.trades >= 50 ? 1 : 0;
    const br = b.trades >= 50 ? 1 : 0;
    if (br !== ar) return br - ar;
    if (b.min_pos_frac !== a.min_pos_frac) return b.min_pos_frac - a.min_pos_frac;
    if (b.expectancy_pct !== a.expectancy_pct) return b.expectancy_pct - a.expectancy_pct;
    return b.profit_factor - a.profit_factor;
  });

  writeJSON('results/gate_sweep_best.json', all.slice(0, 5));
  writeJSON('results/gate_sweep_all.json', all);
  log(`Volume gate sweep complete. tested=${all.length}`);
}

main();
