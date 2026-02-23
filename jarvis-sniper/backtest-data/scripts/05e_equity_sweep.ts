import { ensureDir, log, readJSON, writeJSON } from './shared/utils';
import type { Candle, ScoredToken, TradeResult } from './shared/types';

type EntryType = 'mean_reversion' | 'trend_follow' | 'strict_trend' | 'breakout';
type Tf = '15m' | '1h' | '1d';

interface SweepResult {
  algo_id: string;
  timeframe: Tf;
  entry_type: EntryType;
  stop_loss_pct: number;
  take_profit_pct: number;
  max_age_hours: number;
  trades: number;
  min_pos_frac: number;
  expectancy_pct: number;
  profit_factor: number;
}

function loadCandles(mint: string, tf: Tf): Candle[] {
  if (tf === '1d') {
    const h1 = readJSON<Candle[]>(`candles/${mint}_1h.json`) || [];
    if (h1.length < 24) return [];
    const out: Candle[] = [];
    for (let i = 0; i < h1.length; i += 24) {
      const chunk = h1.slice(i, i + 24);
      if (chunk.length < 24) break;
      out.push({
        timestamp: chunk[0].timestamp,
        open: chunk[0].open,
        close: chunk[chunk.length - 1].close,
        high: Math.max(...chunk.map(c => c.high)),
        low: Math.min(...chunk.map(c => c.low)),
        volume: chunk.reduce((s, c) => s + c.volume, 0),
      });
    }
    return out;
  }
  return readJSON<Candle[]>(`candles/${mint}_${tf}.json`) || [];
}

function signals(candles: Candle[], entry: EntryType): number[] {
  const idx: number[] = [];
  const lb = 5;
  let last = -12;
  for (let i = lb; i < candles.length - 3; i++) {
    if (i - last < 12) continue;
    const c = candles[i];
    const p = candles[i - 1];
    if (p.close <= 0) continue;
    const pct = ((c.close - p.close) / p.close) * 100;
    const sma5 = candles.slice(i - 4, i + 1).reduce((s, x) => s + x.close, 0) / 5;
    const avgVol = candles.slice(i - 4, i + 1).reduce((s, x) => s + x.volume, 0) / 5;
    const v = avgVol > 0 ? c.volume / avgVol : 1;

    let ok = false;
    if (entry === 'mean_reversion') ok = c.close < sma5 * 0.97 && c.close > c.open && p.close < p.open;
    if (entry === 'trend_follow') ok = c.close > sma5 && c.high > p.high && pct > 0.5 && v > 1.2;
    if (entry === 'strict_trend') ok = c.close > sma5 * 1.01 && pct > 1.0 && v > 1.5 && c.close > c.open && p.close > p.open;
    if (entry === 'breakout') {
      const rh = Math.max(...candles.slice(Math.max(0, i - 10), i).map(x => x.high));
      ok = c.close > rh * 1.005 && v > 1.8;
    }
    if (ok) { idx.push(i); last = i; }
  }
  return idx;
}

function sim(candles: Candle[], i: number, slPct: number, tpPct: number, maxAgeHours: number): number | null {
  const entry = candles[i].close * 1.005;
  const sl = entry * (1 - slPct / 100);
  const tp = entry * (1 + tpPct / 100);
  const startTs = candles[i].timestamp;
  const maxAge = maxAgeHours * 3600;
  for (let k = i + 1; k < candles.length; k++) {
    const c = candles[k];
    const slHit = c.low <= sl;
    const tpHit = c.high >= tp;
    if (slHit) return -slPct;
    if (tpHit) return tpPct;
    if (c.timestamp - startTs > maxAge) {
      return ((c.close - entry) / entry) * 100;
    }
  }
  return null;
}

function minPosFrac(pnls: number[], window = 20): number {
  if (pnls.length === 0) return 0;
  if (pnls.length < window) return +(pnls.filter(v => v > 0).length / pnls.length).toFixed(3);
  let min = 1;
  for (let i = 0; i <= pnls.length - window; i++) {
    const p = pnls.slice(i, i + window).filter(v => v > 0).length / window;
    if (p < min) min = p;
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
  const algo = process.argv[2] || 'xstock_swing';
  ensureDir('results');
  const tokens = readJSON<ScoredToken[]>(`qualified/qualified_${algo}.json`) || [];
  const timeframes: Tf[] = ['15m', '1h', '1d'];
  const entries: EntryType[] = ['mean_reversion', 'trend_follow', 'strict_trend', 'breakout'];
  const sls = [4, 5, 6, 7];
  const tps = [8, 10, 12, 14, 16];
  const ages = [24, 48, 72, 96];

  const all: SweepResult[] = [];

  for (const timeframe of timeframes) {
    for (const entry of entries) {
      for (const sl of sls) {
        for (const tp of tps) {
          for (const age of ages) {
            const pnls: number[] = [];
            for (const t of tokens) {
              const candles = loadCandles(t.mint, timeframe);
              if (candles.length < 30) continue;
              const sigs = signals(candles, entry);
              for (const s of sigs) {
                const pnl = sim(candles, s, sl, tp, age);
                if (pnl !== null) pnls.push(pnl);
              }
            }
            if (pnls.length === 0) continue;
            all.push({
              algo_id: algo,
              timeframe,
              entry_type: entry,
              stop_loss_pct: sl,
              take_profit_pct: tp,
              max_age_hours: age,
              trades: pnls.length,
              min_pos_frac: minPosFrac(pnls),
              expectancy_pct: +(pnls.reduce((s, v) => s + v, 0) / pnls.length).toFixed(3),
              profit_factor: pf(pnls),
            });
          }
        }
      }
    }
  }

  all.sort((a, b) => {
    const atr = a.trades >= 50 ? 1 : 0;
    const btr = b.trades >= 50 ? 1 : 0;
    if (btr !== atr) return btr - atr;
    if (b.min_pos_frac !== a.min_pos_frac) return b.min_pos_frac - a.min_pos_frac;
    if (b.expectancy_pct !== a.expectancy_pct) return b.expectancy_pct - a.expectancy_pct;
    return b.profit_factor - a.profit_factor;
  });

  const best = all[0] || null;
  writeJSON('results/equity_sweep_best.json', best ? [best] : []);
  writeJSON('results/equity_sweep_all.json', all.slice(0, 300));
  log(`Equity sweep complete for ${algo}. combos=${all.length}`);
}

main();
