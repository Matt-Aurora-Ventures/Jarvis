/**
 * Phase 5d: Established Token Parameter Sweep
 * 
 * Tests ALL 5 entry types × wide SL/TP/maxAge ranges for the 5 new
 * established-token strategies. Finds the best profitable parameters.
 * 
 * Run: npx tsx backtest-data/scripts/05d_established_sweep.ts
 */

import {
  log, logError, readJSON, writeJSON, ensureDir,
} from './shared/utils';
import type { ScoredToken, Candle, AlgoExitParams, TradeResult, ExitReason } from './shared/types';

// ─── Copy friction constants from 05_simulate_trades.ts ───
const SLIPPAGE_ENTRY_PCT = 0.5;
const SLIPPAGE_EXIT_PCT = 0.3;
const FEE_PER_SIDE_PCT = 0.25;
const BASE_TX_FEE_SOL = 0.000005;
const PRIORITY_FEE_SOL = 0.0002;
const FIXED_COST_ROUND_TRIP_SOL = (BASE_TX_FEE_SOL + PRIORITY_FEE_SOL) * 2;
const POSITION_SIZE_USD = 10;
const SOL_PRICE_USD = 150;
const FIXED_COST_USD = FIXED_COST_ROUND_TRIP_SOL * SOL_PRICE_USD;
const FIXED_COST_PCT = (FIXED_COST_USD / POSITION_SIZE_USD) * 100;
const TOTAL_FRICTION_PCT = SLIPPAGE_ENTRY_PCT + SLIPPAGE_EXIT_PCT + FEE_PER_SIDE_PCT * 2 + FIXED_COST_PCT;
const MIN_COOLDOWN_CANDLES = 12;

// ─── Entry types to sweep ───
type EntryType = 'sma_crossover' | 'accumulation' | 'range_breakout' | 'pullback_buy' | 'vol_surge_scalp' | 'mean_reversion' | 'trend_follow' | 'momentum' | 'dip_buy';

const ALL_ENTRY_TYPES: EntryType[] = [
  'sma_crossover', 'accumulation', 'range_breakout', 'pullback_buy', 'vol_surge_scalp',
  'mean_reversion', 'trend_follow', 'momentum', 'dip_buy',
];

// ─── Strategies to sweep ───
const ESTABLISHED_ALGOS = [
  'sol_veteran', 'utility_swing', 'established_breakout', 'meme_classic', 'volume_spike',
];

// ─── Parameter ranges ───
const SL_RANGE = [5, 8, 10, 12, 15, 18, 20, 25];
const TP_RANGE = [15, 20, 25, 30, 40, 50, 60, 75, 100, 120, 150, 200];
const MAX_AGE_RANGE = [6, 12, 24, 48, 72, 96, 168];

// ─── Entry signal system (copied from 05_simulate_trades.ts + new types) ───

interface EntrySignal {
  candleIndex: number;
  entryPrice: number;
  score: number;
}

function findAllEntrySignals(candles: Candle[], entryType: EntryType): EntrySignal[] {
  const signals: EntrySignal[] = [];
  if (candles.length < 20) return signals;
  const LB = 5;
  let lastIdx = -MIN_COOLDOWN_CANDLES;

  for (let i = LB; i < candles.length - 5; i++) {
    if (i - lastIdx < MIN_COOLDOWN_CANDLES) continue;
    const c = candles[i];
    const prev = candles[i - 1];
    if (c.close <= 0 || prev.close <= 0 || c.volume <= 0) continue;
    const pct = ((c.close - prev.close) / prev.close) * 100;
    let s5 = 0;
    for (let j = i - LB + 1; j <= i; j++) s5 += candles[j].close;
    const sma5 = s5 / LB;
    let vSum = 0;
    for (let j = i - LB + 1; j <= i; j++) vSum += candles[j].volume;
    const avgVol = vSum / LB;
    const volSpike = avgVol > 0 ? c.volume / avgVol : 1;
    let triggered = false;

    switch (entryType) {
      case 'momentum':
        if (c.close > sma5 * 1.01 && pct > 2 && volSpike > 1.5) triggered = true;
        break;
      case 'mean_reversion':
        if (c.close < sma5 * 0.97 && c.close > c.open && prev.close < prev.open) triggered = true;
        break;
      case 'trend_follow':
        if (c.close > sma5 && c.high > prev.high && pct > 0.5 && volSpike > 1.2) triggered = true;
        break;
      case 'dip_buy':
        if (i >= 3) {
          const lo = Math.min(candles[i-1].close, candles[i-2].close, candles[i-3].close);
          const hi = Math.max(candles[i-1].open, candles[i-2].open, candles[i-3].open);
          const dip = hi > 0 ? ((hi - lo) / hi) * 100 : 0;
          if (dip > 3 && c.close > c.open && pct > 0.5) triggered = true;
        }
        break;
      case 'sma_crossover': {
        if (i < 20) break;
        let sc20 = 0;
        for (let j = i - 19; j <= i; j++) sc20 += candles[j].close;
        const scSma20 = sc20 / 20;
        let prevS5 = 0;
        for (let j = i - LB; j < i; j++) prevS5 += candles[j].close;
        const prevSma5 = prevS5 / LB;
        let prev20 = 0;
        for (let j = i - 20; j < i; j++) prev20 += candles[j].close;
        const prevSma20 = prev20 / 20;
        if (prevSma5 <= prevSma20 && sma5 > scSma20 && volSpike > 1.3 && c.close > c.open) {
          triggered = true;
        }
        break;
      }
      case 'accumulation': {
        if (i < 10) break;
        let avgVol5Prior = 0;
        for (let j = i - 9; j <= i - 5; j++) avgVol5Prior += candles[j].volume;
        avgVol5Prior /= 5;
        let avgVol5Recent = 0;
        for (let j = i - 4; j <= i; j++) avgVol5Recent += candles[j].volume;
        avgVol5Recent /= 5;
        let rangeHi = 0, rangeLo = Infinity;
        for (let j = i - 4; j <= i; j++) {
          if (candles[j].high > rangeHi) rangeHi = candles[j].high;
          if (candles[j].low < rangeLo) rangeLo = candles[j].low;
        }
        const rangeWidth = rangeLo > 0 ? ((rangeHi - rangeLo) / rangeLo) * 100 : 99;
        if (rangeWidth < 5 && avgVol5Recent > avgVol5Prior * 1.5 && c.close > c.open && pct > 0.3) {
          triggered = true;
        }
        break;
      }
      case 'range_breakout': {
        if (i < 20) break;
        let rbHigh = 0;
        for (let j = i - 20; j < i; j++) if (candles[j].high > rbHigh) rbHigh = candles[j].high;
        if (c.close > rbHigh * 1.005 && volSpike > 2.0 && c.close > c.open) {
          triggered = true;
        }
        break;
      }
      case 'pullback_buy': {
        if (i < 20) break;
        let pb20 = 0;
        for (let j = i - 19; j <= i; j++) pb20 += candles[j].close;
        const pbSma20 = pb20 / 20;
        const nearSma20 = Math.abs(prev.low - pbSma20) / pbSma20 < 0.015;
        if (sma5 > pbSma20 && nearSma20 && c.close > sma5 && c.close > c.open && pct > 0.5) {
          triggered = true;
        }
        break;
      }
      case 'vol_surge_scalp': {
        if (volSpike > 3.0 && pct > 1.5 && c.close > c.open && c.close > sma5) {
          triggered = true;
        }
        break;
      }
    }

    if (triggered) {
      signals.push({ candleIndex: i, entryPrice: c.close, score: 0 });
      lastIdx = i;
    }
  }
  return signals;
}

// ─── Trade simulation (same as 05_simulate_trades.ts) ───

function simulateOneTrade(
  candles: Candle[],
  params: AlgoExitParams,
  signal: EntrySignal,
): TradeResult | null {
  const rawEntry = signal.entryPrice;
  const entryPrice = rawEntry * (1 + SLIPPAGE_ENTRY_PCT / 100);
  if (entryPrice <= 0) return null;
  const entryTimestamp = candles[signal.candleIndex].timestamp;
  const slPrice = entryPrice * (1 - params.stopLossPct / 100);
  const tpPrice = entryPrice * (1 + params.takeProfitPct / 100);
  const minProfitableActivation = TOTAL_FRICTION_PCT + params.trailingStopPct + 0.5;
  const trailActivationPct = Math.min(minProfitableActivation, params.takeProfitPct * 0.9);
  const trailActivationPrice = entryPrice * (1 + trailActivationPct / 100);
  const maxAgeSeconds = (params.maxPositionAgeHours || 4) * 3600;
  let highWaterMark = entryPrice;
  let exitPrice = 0;
  let exitTimestamp = 0;
  let exitReason: ExitReason = 'end_of_data';
  let candlesInTrade = 0;
  let exited = false;

  for (let i = signal.candleIndex + 1; i < candles.length; i++) {
    const candle = candles[i];
    candlesInTrade++;
    if (candle.high > highWaterMark) highWaterMark = candle.high;
    // Conservative intrabar ambiguity: SL first (dual-trigger counts as SL).
    const slHit = candle.low <= slPrice;
    const tpHit = candle.high >= tpPrice;
    if (slHit) { exitPrice = slPrice; exitTimestamp = candle.timestamp; exitReason = 'sl_hit'; exited = true; break; }
    if (tpHit) { exitPrice = tpPrice; exitTimestamp = candle.timestamp; exitReason = 'tp_hit'; exited = true; break; }
    if (highWaterMark > trailActivationPrice) {
      const trailStopPrice = highWaterMark * (1 - params.trailingStopPct / 100);
      if (candle.low <= trailStopPrice) { exitPrice = trailStopPrice; exitTimestamp = candle.timestamp; exitReason = 'trail_stop'; exited = true; break; }
    }
    if (candle.timestamp - entryTimestamp > maxAgeSeconds) {
      // Expiry: exit at market close
      exitPrice = candle.close;
      exitTimestamp = candle.timestamp; exitReason = 'expired'; exited = true; break;
    }
  }
  if (!exited) { const lc = candles[candles.length - 1]; exitPrice = lc.close; exitTimestamp = lc.timestamp; }
  if (exitPrice <= 0) exitPrice = entryPrice;
  const exitAfterFriction = exitPrice * (1 - SLIPPAGE_EXIT_PCT / 100) * (1 - FEE_PER_SIDE_PCT / 100);
  const entryAfterFees = entryPrice * (1 + FEE_PER_SIDE_PCT / 100);
  const pricePnlPct = ((exitAfterFriction - entryAfterFees) / entryAfterFees) * 100;
  const grossPnlUsd = POSITION_SIZE_USD * (pricePnlPct / 100);
  const netPnlUsd = grossPnlUsd - FIXED_COST_USD;
  const netPnlPct = (netPnlUsd / POSITION_SIZE_USD) * 100;
  return {
    algo_id: params.algo_id, mint: '', symbol: '', name: '',
    entry_timestamp: entryTimestamp, entry_price_usd: entryPrice,
    exit_timestamp: exitTimestamp, exit_price_usd: exitAfterFriction,
    pnl_percent: +netPnlPct.toFixed(4), pnl_usd: +netPnlUsd.toFixed(4),
    exit_reason: exitReason, high_water_mark_price: highWaterMark,
    high_water_mark_percent: +((highWaterMark - entryPrice) / entryPrice * 100).toFixed(4),
    trade_duration_hours: +((exitTimestamp - entryTimestamp) / 3600).toFixed(2),
    candles_in_trade: candlesInTrade, score_at_entry: 0, liquidity_at_entry: 0,
    momentum_1h_at_entry: 0, vol_liq_ratio_at_entry: 0,
  };
}

function loadBestCandles(mint: string): Candle[] | null {
  for (const tf of ['5m', '15m'] as const) {
    const candles = readJSON<Candle[]>(`candles/${mint}_${tf}.json`);
    if (candles && candles.length >= 25) return candles;
  }
  return null;
}

// ─── Sweep one combo ───

interface SweepResult {
  algo_id: string;
  entryType: EntryType;
  sl: number;
  tp: number;
  maxAge: number;
  trades: number;
  winRate: number;
  expectancy: number;
  profitFactor: number;
  totalPnlPct: number;
}

function sweepOneCombo(
  tokens: ScoredToken[],
  candleCache: Map<string, Candle[]>,
  algoId: string,
  entryType: EntryType,
  sl: number,
  tp: number,
  maxAge: number,
): SweepResult | null {
  const params: AlgoExitParams = { algo_id: algoId, stopLossPct: sl, takeProfitPct: tp, trailingStopPct: 99, maxPositionAgeHours: maxAge };
  const allTrades: TradeResult[] = [];

  for (const token of tokens) {
    const candles = candleCache.get(token.mint);
    if (!candles) continue;
    const signals = findAllEntrySignals(candles, entryType);
    let lastExitCandle = -1;
    for (const signal of signals) {
      if (signal.candleIndex <= lastExitCandle + MIN_COOLDOWN_CANDLES) continue;
      const result = simulateOneTrade(candles, params, signal);
      if (result) {
        allTrades.push(result);
        lastExitCandle = signal.candleIndex + result.candles_in_trade;
      }
    }
  }

  if (allTrades.length < 10) return null;

  const wins = allTrades.filter(t => t.pnl_usd > 0);
  const losses = allTrades.filter(t => t.pnl_usd <= 0);
  const totalWin = wins.reduce((s, t) => s + t.pnl_usd, 0);
  const totalLoss = Math.abs(losses.reduce((s, t) => s + t.pnl_usd, 0));
  const totalPnl = allTrades.reduce((s, t) => s + t.pnl_percent, 0);
  const pf = totalLoss > 0 ? totalWin / totalLoss : totalWin > 0 ? 99 : 0;

  return {
    algo_id: algoId,
    entryType,
    sl, tp, maxAge,
    trades: allTrades.length,
    winRate: +(wins.length / allTrades.length * 100).toFixed(1),
    expectancy: +(totalPnl / allTrades.length).toFixed(4),
    profitFactor: +pf.toFixed(2),
    totalPnlPct: +totalPnl.toFixed(2),
  };
}

// ─── Main ───

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 5d: Established Token Parameter Sweep');
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  const allResults: SweepResult[] = [];
  const bestPerAlgo: Record<string, SweepResult> = {};

  for (const algoId of ESTABLISHED_ALGOS) {
    log(`\n─── Loading tokens for ${algoId} ───`);
    const tokens = readJSON<ScoredToken[]>(`qualified/qualified_${algoId}.json`);
    if (!tokens || tokens.length === 0) {
      log(`  No tokens for ${algoId}, skipping.`);
      continue;
    }

    // Pre-load candles
    const candleCache = new Map<string, Candle[]>();
    let loaded = 0;
    for (const token of tokens) {
      const candles = loadBestCandles(token.mint);
      if (candles) { candleCache.set(token.mint, candles); loaded++; }
    }
    log(`  ${loaded}/${tokens.length} tokens have candle data`);

    let combos = 0;
    let profitable = 0;

    for (const entryType of ALL_ENTRY_TYPES) {
      for (const sl of SL_RANGE) {
        for (const tp of TP_RANGE) {
          if (tp <= sl) continue; // TP must be > SL
          for (const maxAge of MAX_AGE_RANGE) {
            combos++;
            const result = sweepOneCombo(tokens, candleCache, algoId, entryType, sl, tp, maxAge);
            if (result && result.totalPnlPct > 0 && result.profitFactor > 1.0) {
              allResults.push(result);
              profitable++;

              if (!bestPerAlgo[algoId] || result.expectancy > bestPerAlgo[algoId].expectancy) {
                bestPerAlgo[algoId] = result;
              }
            }
          }
        }
      }
    }

    log(`  ${algoId}: ${combos} combos tested, ${profitable} profitable`);
    if (bestPerAlgo[algoId]) {
      const b = bestPerAlgo[algoId];
      log(`  BEST: ${b.entryType} SL${b.sl}/TP${b.tp}/Age${b.maxAge}h → ${b.trades} trades, WR ${b.winRate}%, PF ${b.profitFactor}, Exp ${b.expectancy}%/trade, Total ${b.totalPnlPct}%`);
    }
  }

  // Save results
  writeJSON('results/established_sweep_all.json', allResults);
  writeJSON('results/established_sweep_best.json', Object.values(bestPerAlgo));

  log('\n═══════════════════════════════════════════════════════');
  log('BEST PARAMETERS PER STRATEGY:');
  log('═══════════════════════════════════════════════════════');
  for (const algoId of ESTABLISHED_ALGOS) {
    const b = bestPerAlgo[algoId];
    if (b) {
      log(`${algoId.padEnd(25)} ${b.entryType.padEnd(18)} SL${String(b.sl).padEnd(3)} TP${String(b.tp).padEnd(4)} Age${String(b.maxAge).padEnd(4)}h → ${b.trades} trades, WR ${b.winRate}%, PF ${b.profitFactor}, Exp +${b.expectancy}%`);
    } else {
      log(`${algoId.padEnd(25)} *** NO PROFITABLE COMBO FOUND ***`);
    }
  }

  log(`\n✓ Phase 5d complete: ${allResults.length} profitable combos found`);
  log(`  → results/established_sweep_best.json`);
}

main().catch(err => {
  logError('Fatal error in established sweep', err);
  process.exit(1);
});
