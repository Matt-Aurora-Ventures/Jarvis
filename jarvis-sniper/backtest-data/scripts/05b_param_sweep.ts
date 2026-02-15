/**
 * Phase 5b: Parameter Sweep — Find Profitable Params for ALL Strategies
 * 
 * Tests every combination of SL/TP/maxAge for each strategy and finds
 * the best profitable configuration. Uses the same simulation engine
 * as Phase 5.
 * 
 * Run: npx tsx backtest-data/scripts/05b_param_sweep.ts
 */

import {
  log, logError, readJSON, writeJSON, ensureDir,
} from './shared/utils';
import type { ScoredToken, Candle, AlgoExitParams, TradeResult, ExitReason } from './shared/types';

// ─── REALISTIC FRICTION (same as Phase 5) ───
const SLIPPAGE_ENTRY_PCT = 0.5;
const SLIPPAGE_EXIT_PCT = 0.3;
const FEE_PER_SIDE_PCT = 0.25;

const BASE_TX_FEE_SOL = 0.000005;
const PRIORITY_FEE_SOL = 0.0002;
const FIXED_COST_PER_TX_SOL = BASE_TX_FEE_SOL + PRIORITY_FEE_SOL;
const FIXED_COST_ROUND_TRIP_SOL = FIXED_COST_PER_TX_SOL * 2;

const POSITION_SIZE_USD = 10;
const SOL_PRICE_USD = 150;
const FIXED_COST_USD = FIXED_COST_ROUND_TRIP_SOL * SOL_PRICE_USD;
const FIXED_COST_PCT = (FIXED_COST_USD / POSITION_SIZE_USD) * 100;
const TOTAL_FRICTION_PCT = SLIPPAGE_ENTRY_PCT + SLIPPAGE_EXIT_PCT + FEE_PER_SIDE_PCT * 2 + FIXED_COST_PCT;

const MIN_COOLDOWN_CANDLES = 12;

// ─── ALL 26 strategies ───
const ALL_ALGO_IDS = [
  'pump_fresh_tight', 'micro_cap_surge', 'elite', 'momentum', 'insight_j',
  'hybrid_b', 'let_it_ride', 'loose', 'genetic_best', 'genetic_v2',
  'bags_fresh_snipe', 'bags_momentum', 'bags_value', 'bags_dip_buyer',
  'bags_bluechip', 'bags_conservative', 'bags_aggressive', 'bags_elite',
  'bluechip_mean_revert', 'bluechip_trend_follow', 'bluechip_breakout',
  'xstock_intraday', 'xstock_swing', 'prestock_speculative',
  'index_intraday', 'index_leveraged',
];

// ─── Parameter grid per asset class ───
interface ParamGrid {
  slValues: number[];
  tpMultipliers: number[];  // TP = SL * multiplier
  maxAgeValues: number[];
}

// Memecoin strategies: wider range
const MEMECOIN_GRID: ParamGrid = {
  slValues: [4, 5, 6, 7, 8, 10, 12, 15],
  tpMultipliers: [1.5, 2, 2.5, 3, 4, 5],
  maxAgeValues: [2, 4, 6, 8],
};

// Blue chip: tighter params, longer holds
const BLUECHIP_GRID: ParamGrid = {
  slValues: [3, 4, 5, 6, 7, 8, 10],
  tpMultipliers: [1.5, 2, 2.5, 3, 3.5, 4],
  maxAgeValues: [4, 8, 12, 24],
};

// xStock/prestock: stock-calibrated
const STOCK_GRID: ParamGrid = {
  slValues: [2, 3, 4, 5, 6, 8],
  tpMultipliers: [1.5, 2, 2.5, 3, 3.5, 4, 5],
  maxAgeValues: [4, 8, 12, 24, 48],
};

// Index: tightest params
const INDEX_GRID: ParamGrid = {
  slValues: [1.5, 2, 3, 4, 5, 6],
  tpMultipliers: [1.5, 2, 2.5, 3, 3.5, 4, 5],
  maxAgeValues: [4, 8, 12, 24, 48],
};

function getGrid(algoId: string): ParamGrid {
  if (algoId.startsWith('bluechip_')) return BLUECHIP_GRID;
  if (algoId.startsWith('xstock_') || algoId === 'prestock_speculative') return STOCK_GRID;
  if (algoId.startsWith('index_')) return INDEX_GRID;
  return MEMECOIN_GRID;
}

// ─── Entry Signal System (copied from 05) ───

type EntryType = 'momentum' | 'fresh_pump' | 'aggressive' | 'mean_reversion' | 'trend_follow' | 'breakout' | 'dip_buy';

interface EntrySignal {
  candleIndex: number;
  entryPrice: number;
  score: number;
}

function getEntryType(algoId: string): EntryType {
  if (['pump_fresh_tight', 'bags_fresh_snipe'].includes(algoId)) return 'fresh_pump';
  if (['micro_cap_surge', 'genetic_best', 'genetic_v2', 'bags_aggressive'].includes(algoId)) return 'aggressive';
  if (['elite', 'momentum', 'insight_j', 'hybrid_b', 'bags_momentum'].includes(algoId)) return 'momentum';
  if (['let_it_ride', 'loose', 'bluechip_trend_follow', 'xstock_swing', 'index_leveraged', 'prestock_speculative'].includes(algoId)) return 'trend_follow';
  if (['bluechip_mean_revert', 'bags_value', 'bags_bluechip', 'bags_elite', 'bags_conservative'].includes(algoId)) return 'mean_reversion';
  if (['bluechip_breakout'].includes(algoId)) return 'breakout';
  if (['bags_dip_buyer'].includes(algoId)) return 'dip_buy';
  if (['xstock_intraday', 'index_intraday'].includes(algoId)) return 'momentum';
  return 'momentum';
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
      case 'fresh_pump':
        if (pct > 3 && volSpike > 1.8 && c.close > c.open) triggered = true;
        break;
      case 'aggressive':
        if (pct > 2 && volSpike > 1.3 && c.close > sma5) triggered = true;
        break;
      case 'mean_reversion':
        if (c.close < sma5 * 0.97 && c.close > c.open && prev.close < prev.open) triggered = true;
        break;
      case 'trend_follow':
        if (c.close > sma5 && c.high > prev.high && pct > 0.5 && volSpike > 1.2) triggered = true;
        break;
      case 'breakout': {
        let rHigh = 0;
        for (let j = Math.max(0, i - 10); j < i; j++) if (candles[j].high > rHigh) rHigh = candles[j].high;
        if (c.close > rHigh * 1.005 && volSpike > 1.8) triggered = true;
        break;
      }
      case 'dip_buy':
        if (i >= 3) {
          const lo = Math.min(candles[i-1].close, candles[i-2].close, candles[i-3].close);
          const hi = Math.max(candles[i-1].open, candles[i-2].open, candles[i-3].open);
          const dip = hi > 0 ? ((hi - lo) / hi) * 100 : 0;
          if (dip > 3 && c.close > c.open && pct > 0.5) triggered = true;
        }
        break;
    }

    if (triggered) {
      signals.push({ candleIndex: i, entryPrice: c.close, score: 0 });
      lastIdx = i;
    }
  }

  return signals;
}

// ─── Trade simulation (same as 05) ───

function simulateOneTrade(
  candles: Candle[],
  params: AlgoExitParams,
  signal: EntrySignal,
): { pnlPct: number; exitReason: ExitReason } | null {
  const rawEntry = signal.entryPrice;
  const entryPrice = rawEntry * (1 + SLIPPAGE_ENTRY_PCT / 100);
  if (entryPrice <= 0) return null;
  const entryTimestamp = candles[signal.candleIndex].timestamp;

  const slPrice = entryPrice * (1 - params.stopLossPct / 100);
  const tpPrice = entryPrice * (1 + params.takeProfitPct / 100);
  const trailActivationPct = Math.min(TOTAL_FRICTION_PCT + 99 + 0.5, params.takeProfitPct * 0.9);
  const trailActivationPrice = entryPrice * (1 + trailActivationPct / 100);
  const maxAgeSeconds = (params.maxPositionAgeHours || 4) * 3600;

  let highWaterMark = entryPrice;
  let exitPrice = 0;
  let exitReason: ExitReason = 'end_of_data';
  let exited = false;

  for (let i = signal.candleIndex + 1; i < candles.length; i++) {
    const candle = candles[i];

    if (candle.high > highWaterMark) highWaterMark = candle.high;

    // Conservative intrabar ambiguity:
    // If both SL and TP hit in the same candle, count it as SL.
    const slHit = candle.low <= slPrice;
    const tpHit = candle.high >= tpPrice;
    if (slHit) {
      exitPrice = slPrice;
      exitReason = 'sl_hit';
      exited = true;
      break;
    }
    if (tpHit) {
      exitPrice = tpPrice;
      exitReason = 'tp_hit';
      exited = true;
      break;
    }

    // Trailing stop (disabled at 99% but kept for correctness)
    if (highWaterMark > trailActivationPrice) {
      const trailStopPrice = highWaterMark * (1 - params.trailingStopPct / 100);
      if (candle.low <= trailStopPrice) {
        exitPrice = trailStopPrice;
        exitReason = 'trail_stop';
        exited = true;
        break;
      }
    }

    // Expiry
    if (candle.timestamp - entryTimestamp > maxAgeSeconds) {
      // Exit at market close at expiry (no "one more candle to breakeven" optimism)
      exitPrice = candle.close;
      exitReason = 'expired';
      exited = true;
      break;
    }
  }

  if (!exited) {
    exitPrice = candles[candles.length - 1].close;
    exitReason = 'end_of_data';
  }

  if (exitPrice <= 0) exitPrice = entryPrice;

  const exitAfterFriction = exitPrice * (1 - SLIPPAGE_EXIT_PCT / 100) * (1 - FEE_PER_SIDE_PCT / 100);
  const entryAfterFees = entryPrice * (1 + FEE_PER_SIDE_PCT / 100);
  const pricePnlPct = ((exitAfterFriction - entryAfterFees) / entryAfterFees) * 100;
  const grossPnlUsd = POSITION_SIZE_USD * (pricePnlPct / 100);
  const netPnlUsd = grossPnlUsd - FIXED_COST_USD;
  const netPnlPct = (netPnlUsd / POSITION_SIZE_USD) * 100;

  return { pnlPct: netPnlPct, exitReason };
}

// ─── Load candles ───

function loadBestCandles(mint: string): Candle[] | null {
  for (const tf of ['5m', '15m'] as const) {
    const candles = readJSON<Candle[]>(`candles/${mint}_${tf}.json`);
    if (candles && candles.length >= 25) return candles;
  }
  return null;
}

// ─── Sweep result ───

interface SweepResult {
  algo_id: string;
  sl: number;
  tp: number;
  maxAge: number;
  trades: number;
  winRate: number;
  expectancy: number;
  profitFactor: number;
  totalPnlPct: number;
}

// ─── Run sweep for one algo ───

function sweepAlgo(algoId: string): SweepResult[] {
  const tokens = readJSON<(ScoredToken & { vol_liq_ratio?: number })[]>(
    `qualified/qualified_${algoId}.json`,
  );
  if (!tokens || tokens.length === 0) return [];

  // Pre-load candles and compute entry signals once
  const entryType = getEntryType(algoId);
  const tokenData: { candles: Candle[]; signals: EntrySignal[] }[] = [];

  for (const token of tokens) {
    const candles = loadBestCandles(token.mint);
    if (!candles) continue;
    const signals = findAllEntrySignals(candles, entryType);
    if (signals.length > 0) {
      tokenData.push({ candles, signals });
    }
  }

  if (tokenData.length === 0) return [];

  const grid = getGrid(algoId);
  const results: SweepResult[] = [];

  for (const sl of grid.slValues) {
    for (const mult of grid.tpMultipliers) {
      const tp = +(sl * mult).toFixed(1);
      for (const maxAge of grid.maxAgeValues) {
        const params: AlgoExitParams = {
          algo_id: algoId,
          stopLossPct: sl,
          takeProfitPct: tp,
          trailingStopPct: 99,  // disabled
          maxPositionAgeHours: maxAge,
        };

        let totalPnl = 0;
        let wins = 0;
        let losses = 0;
        let grossWin = 0;
        let grossLoss = 0;
        let tradeCount = 0;

        for (const { candles, signals } of tokenData) {
          let lastExitCandle = -MIN_COOLDOWN_CANDLES;

          for (const signal of signals) {
            if (signal.candleIndex <= lastExitCandle + MIN_COOLDOWN_CANDLES) continue;

            const result = simulateOneTrade(candles, params, signal);
            if (!result) continue;

            tradeCount++;
            totalPnl += result.pnlPct;

            if (result.pnlPct > 0) {
              wins++;
              grossWin += result.pnlPct;
            } else {
              losses++;
              grossLoss += Math.abs(result.pnlPct);
            }

            // Estimate candles in trade for cooldown
            // Rough: sl/tp hit within a few candles on average
            lastExitCandle = signal.candleIndex + 4;
          }
        }

        if (tradeCount < 10) continue; // Need minimum sample size

        const wr = (wins / tradeCount) * 100;
        const exp = totalPnl / tradeCount;
        const pf = grossLoss > 0 ? grossWin / grossLoss : grossWin > 0 ? Infinity : 0;

        results.push({
          algo_id: algoId,
          sl, tp, maxAge: maxAge,
          trades: tradeCount,
          winRate: +wr.toFixed(1),
          expectancy: +exp.toFixed(4),
          profitFactor: +pf.toFixed(2),
          totalPnlPct: +totalPnl.toFixed(2),
        });
      }
    }
  }

  return results;
}

// ─── Main ───

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 5b: Parameter Sweep — Find Profitable Params for ALL Strategies');
  log(`Friction: ${TOTAL_FRICTION_PCT.toFixed(1)}% | Position: $${POSITION_SIZE_USD}`);
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  const bestParams: Record<string, SweepResult> = {};
  const allSweepResults: Record<string, SweepResult[]> = {};

  for (const algoId of ALL_ALGO_IDS) {
    log(`\n─── Sweeping ${algoId} ───`);

    const results = sweepAlgo(algoId);
    allSweepResults[algoId] = results;

    if (results.length === 0) {
      log(`  No trades found for ${algoId}`);
      continue;
    }

    // Filter profitable (positive expectancy) and sort by:
    // 1. Expectancy (primary)
    // 2. Profit factor (tiebreaker)
    // 3. More trades preferred (statistical significance)
    const profitable = results
      .filter(r => r.expectancy > 0 && r.trades >= 15)
      .sort((a, b) => {
        // Weight: expectancy * log(trades) * PF
        const scoreA = a.expectancy * Math.log2(Math.max(a.trades, 1)) * Math.min(a.profitFactor, 3);
        const scoreB = b.expectancy * Math.log2(Math.max(b.trades, 1)) * Math.min(b.profitFactor, 3);
        return scoreB - scoreA;
      });

    if (profitable.length > 0) {
      const best = profitable[0];
      bestParams[algoId] = best;
      log(`  ✓ BEST: SL ${best.sl}% / TP ${best.tp}% / MaxAge ${best.maxAge}h`);
      log(`    WR: ${best.winRate}% | PF: ${best.profitFactor} | Exp: ${best.expectancy.toFixed(2)}% | Trades: ${best.trades}`);
      log(`    (${profitable.length} profitable combos found out of ${results.length} tested)`);

      // Show top 3 for reference
      if (profitable.length > 1) {
        log(`    Runner-ups:`);
        for (let i = 1; i < Math.min(4, profitable.length); i++) {
          const r = profitable[i];
          log(`      SL ${r.sl}% / TP ${r.tp}% / ${r.maxAge}h — WR ${r.winRate}% | PF ${r.profitFactor} | Exp ${r.expectancy.toFixed(2)}% | ${r.trades}t`);
        }
      }
    } else {
      // No profitable combo found — show the least-losing one
      const bestLosing = results
        .filter(r => r.trades >= 15)
        .sort((a, b) => b.expectancy - a.expectancy);

      if (bestLosing.length > 0) {
        const bl = bestLosing[0];
        log(`  ✗ NO PROFITABLE COMBO — best is still negative:`);
        log(`    SL ${bl.sl}% / TP ${bl.tp}% / ${bl.maxAge}h — WR ${bl.winRate}% | PF ${bl.profitFactor} | Exp ${bl.expectancy.toFixed(2)}% | ${bl.trades}t`);
        bestParams[algoId] = bl; // store anyway for reference
      } else {
        log(`  ✗ Insufficient data (< 15 trades for all combos)`);
      }
    }
  }

  // ─── Summary Table ───
  log('\n═══════════════════════════════════════════════════════');
  log('PARAMETER SWEEP RESULTS — BEST PARAMS PER STRATEGY');
  log('═══════════════════════════════════════════════════════');

  const sorted = Object.values(bestParams).sort((a, b) => b.expectancy - a.expectancy);
  let profitableCount = 0;

  for (const r of sorted) {
    const status = r.expectancy > 0 ? '✓' : '✗';
    if (r.expectancy > 0) profitableCount++;
    log(`${status} ${r.algo_id.padEnd(25)} SL ${String(r.sl).padStart(4)}% / TP ${String(r.tp).padStart(5)}% / ${String(r.maxAge).padStart(2)}h — WR ${String(r.winRate).padStart(5)}% | PF ${String(r.profitFactor).padStart(4)} | Exp ${r.expectancy >= 0 ? '+' : ''}${r.expectancy.toFixed(2)}% | ${r.trades}t`);
  }

  log(`\n${profitableCount}/${sorted.length} strategies profitable`);

  // Write results
  writeJSON('results/param_sweep_best.json', bestParams);
  writeJSON('results/param_sweep_all.json', allSweepResults);

  // Generate code-ready output for 05_simulate_trades.ts
  log('\n═══════════════════════════════════════════════════════');
  log('COPY-PASTE READY: ALGO_EXIT_PARAMS');
  log('═══════════════════════════════════════════════════════');
  log('const ALGO_EXIT_PARAMS: AlgoExitParams[] = [');
  for (const r of sorted.filter(r => r.expectancy > 0)) {
    log(`  { algo_id: '${r.algo_id}',${' '.repeat(Math.max(1, 25 - r.algo_id.length))}stopLossPct: ${r.sl},${' '.repeat(r.sl < 10 ? 3 : 2)}takeProfitPct: ${r.tp},${' '.repeat(r.tp < 10 ? 2 : 1)}trailingStopPct: 99, maxPositionAgeHours: ${r.maxAge} },`);
  }
  log('];');

  log('\n✓ Phase 5b complete');
  log('  → results/param_sweep_best.json');
  log('  → results/param_sweep_all.json');
}

main().catch(err => {
  logError('Fatal error in param sweep', err);
  process.exit(1);
});
