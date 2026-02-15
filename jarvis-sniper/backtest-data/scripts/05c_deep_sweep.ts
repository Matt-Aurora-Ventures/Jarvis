/**
 * Phase 5c: Deep Parameter Sweep — Fix Remaining Unprofitable Strategies
 * 
 * Targets the 10 strategies that were close to breakeven but still negative.
 * Uses much wider parameter ranges and also tries alternative entry types.
 * 
 * Run: npx tsx backtest-data/scripts/05c_deep_sweep.ts
 */

import {
  log, logError, readJSON, writeJSON, ensureDir,
} from './shared/utils';
import type { ScoredToken, Candle, AlgoExitParams, ExitReason } from './shared/types';

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

// ─── Strategies that need fixing ───
const FAILING_ALGOS = [
  'prestock_speculative', 'xstock_intraday', 'index_intraday',
  'momentum', 'hybrid_b', 'index_leveraged',
  'bluechip_trend_follow', 'genetic_v2', 'bluechip_breakout', 'let_it_ride',
];

// ─── Entry Signal System ───

type EntryType = 'momentum' | 'fresh_pump' | 'aggressive' | 'mean_reversion' | 'trend_follow' | 'breakout' | 'dip_buy' | 'strict_momentum' | 'strict_trend' | 'strict_breakout';

interface EntrySignal {
  candleIndex: number;
  entryPrice: number;
  score: number;
}

// Original entry types per algo
const ORIGINAL_ENTRY: Record<string, EntryType> = {
  momentum: 'momentum',
  hybrid_b: 'momentum',
  genetic_v2: 'aggressive',
  let_it_ride: 'trend_follow',
  xstock_intraday: 'momentum',
  xstock_swing: 'trend_follow',
  prestock_speculative: 'trend_follow',
  index_intraday: 'momentum',
  index_leveraged: 'trend_follow',
  bluechip_mean_revert: 'mean_reversion',
  bluechip_trend_follow: 'trend_follow',
  bluechip_breakout: 'breakout',
};

// Alternative entry types to try — stricter signals = higher quality entries
const ALT_ENTRIES: EntryType[] = [
  'momentum', 'aggressive', 'trend_follow', 'mean_reversion', 'breakout',
  'strict_momentum', 'strict_trend', 'strict_breakout',
];

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

    // SMA-20 for stricter signals
    let s20 = 0;
    const lb20 = Math.min(20, i);
    for (let j = i - lb20 + 1; j <= i; j++) s20 += candles[j].close;
    const sma20 = s20 / lb20;

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

      // ─── STRICTER ENTRY SIGNALS — fewer trades but higher quality ───

      case 'strict_momentum':
        // Require: above SMA20, strong volume, 3%+ candle, green candle
        if (c.close > sma20 * 1.02 && c.close > sma5 * 1.01 && pct > 3 && volSpike > 2.0 && c.close > c.open) {
          triggered = true;
        }
        break;

      case 'strict_trend':
        // Require: above SMA20, new high, 1%+ move, strong volume, 2 green candles in a row
        if (c.close > sma20 && c.close > sma5 && c.high > prev.high && pct > 1.0 && volSpike > 1.5 &&
            c.close > c.open && prev.close > prev.open) {
          triggered = true;
        }
        break;

      case 'strict_breakout': {
        // Require: break above 20-candle high with massive volume
        let rHigh20 = 0;
        for (let j = Math.max(0, i - 20); j < i; j++) if (candles[j].high > rHigh20) rHigh20 = candles[j].high;
        if (c.close > rHigh20 * 1.01 && volSpike > 2.5 && c.close > c.open) {
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

// ─── Trade simulation ───

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
  entryType: string;
  sl: number;
  tp: number;
  maxAge: number;
  trades: number;
  winRate: number;
  expectancy: number;
  profitFactor: number;
  totalPnlPct: number;
}

// ─── Pre-load all candle data per algo ───

function loadTokenCandles(algoId: string): { candles: Candle[] }[] {
  const tokens = readJSON<(ScoredToken & { vol_liq_ratio?: number })[]>(
    `qualified/qualified_${algoId}.json`,
  );
  if (!tokens || tokens.length === 0) return [];

  const data: { candles: Candle[] }[] = [];
  for (const token of tokens) {
    const candles = loadBestCandles(token.mint);
    if (candles && candles.length >= 25) {
      data.push({ candles });
    }
  }
  return data;
}

// ─── Deep sweep for one algo ───

function deepSweepAlgo(algoId: string): SweepResult[] {
  const tokenData = loadTokenCandles(algoId);
  if (tokenData.length === 0) return [];

  const isStock = algoId.startsWith('xstock_') || algoId === 'prestock_speculative';
  const isIndex = algoId.startsWith('index_');
  const isBluechip = algoId.startsWith('bluechip_');

  // Much wider grid
  let slValues: number[];
  let tpMultipliers: number[];
  let maxAgeValues: number[];

  if (isStock || isIndex) {
    slValues = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
    tpMultipliers = [2, 3, 4, 5, 6, 7, 8, 10];
    maxAgeValues = [8, 12, 24, 48, 72, 96];
  } else if (isBluechip) {
    slValues = [3, 4, 5, 6, 7, 8, 10, 12, 15];
    tpMultipliers = [2, 3, 4, 5, 6, 7, 8];
    maxAgeValues = [8, 12, 24, 48, 72];
  } else {
    // memecoins (momentum, hybrid_b, genetic_v2, let_it_ride, loose)
    slValues = [5, 6, 7, 8, 10, 12, 15, 18, 20];
    tpMultipliers = [3, 4, 5, 6, 7, 8, 10];
    maxAgeValues = [4, 6, 8, 12, 24];
  }

  const results: SweepResult[] = [];

  // Try multiple entry types
  for (const entryType of ALT_ENTRIES) {
    // Pre-compute signals for this entry type
    const signalsPerToken: EntrySignal[][] = [];
    for (const td of tokenData) {
      signalsPerToken.push(findAllEntrySignals(td.candles, entryType));
    }

    // Check if any signals exist
    const totalSignals = signalsPerToken.reduce((s, arr) => s + arr.length, 0);
    if (totalSignals < 10) continue;

    for (const sl of slValues) {
      for (const mult of tpMultipliers) {
        const tp = +(sl * mult).toFixed(1);

        for (const maxAge of maxAgeValues) {
          const params: AlgoExitParams = {
            algo_id: algoId,
            stopLossPct: sl,
            takeProfitPct: tp,
            trailingStopPct: 99,
            maxPositionAgeHours: maxAge,
          };

          let totalPnl = 0;
          let wins = 0;
          let losses = 0;
          let grossWin = 0;
          let grossLoss = 0;
          let tradeCount = 0;

          for (let t = 0; t < tokenData.length; t++) {
            const { candles } = tokenData[t];
            const signals = signalsPerToken[t];
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

              lastExitCandle = signal.candleIndex + 4;
            }
          }

          if (tradeCount < 10) continue;

          const wr = (wins / tradeCount) * 100;
          const exp = totalPnl / tradeCount;
          const pf = grossLoss > 0 ? grossWin / grossLoss : grossWin > 0 ? Infinity : 0;

          if (exp > -2) { // Only store semi-viable results
            results.push({
              algo_id: algoId,
              entryType: entryType,
              sl, tp, maxAge,
              trades: tradeCount,
              winRate: +wr.toFixed(1),
              expectancy: +exp.toFixed(4),
              profitFactor: +pf.toFixed(2),
              totalPnlPct: +totalPnl.toFixed(2),
            });
          }
        }
      }
    }
  }

  return results;
}

// ─── Main ───

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 5c: DEEP Parameter Sweep — Fix 10 Remaining Strategies');
  log(`Friction: ${TOTAL_FRICTION_PCT.toFixed(1)}% | Position: $${POSITION_SIZE_USD}`);
  log('Testing: wider SL/TP ranges + stricter entry signals + longer holds');
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  const bestParams: Record<string, SweepResult> = {};

  for (const algoId of FAILING_ALGOS) {
    log(`\n─── Deep sweeping ${algoId} ───`);
    const t0 = Date.now();

    const results = deepSweepAlgo(algoId);

    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    log(`  Tested ${results.length} combinations in ${elapsed}s`);

    if (results.length === 0) {
      log(`  ✗ No results for ${algoId}`);
      continue;
    }

    // Find best profitable combo — weight by expectancy * log(trades) * PF
    const profitable = results
      .filter(r => r.expectancy > 0 && r.trades >= 15)
      .sort((a, b) => {
        const scoreA = a.expectancy * Math.log2(Math.max(a.trades, 1)) * Math.min(a.profitFactor, 3);
        const scoreB = b.expectancy * Math.log2(Math.max(b.trades, 1)) * Math.min(b.profitFactor, 3);
        return scoreB - scoreA;
      });

    if (profitable.length > 0) {
      const best = profitable[0];
      bestParams[algoId] = best;
      log(`  ✓ FOUND PROFITABLE: Entry=${best.entryType} SL ${best.sl}% / TP ${best.tp}% / MaxAge ${best.maxAge}h`);
      log(`    WR: ${best.winRate}% | PF: ${best.profitFactor} | Exp: +${best.expectancy.toFixed(2)}% | Trades: ${best.trades}`);
      log(`    (${profitable.length} profitable combos found)`);

      // Show top 5
      for (let i = 1; i < Math.min(6, profitable.length); i++) {
        const r = profitable[i];
        log(`      Alt ${i}: Entry=${r.entryType} SL ${r.sl}% / TP ${r.tp}% / ${r.maxAge}h — WR ${r.winRate}% | PF ${r.profitFactor} | Exp +${r.expectancy.toFixed(2)}% | ${r.trades}t`);
      }
    } else {
      // Show closest-to-profitable
      const closest = results
        .filter(r => r.trades >= 15)
        .sort((a, b) => b.expectancy - a.expectancy)
        .slice(0, 3);

      log(`  ✗ STILL UNPROFITABLE — closest:`);
      for (const r of closest) {
        log(`    Entry=${r.entryType} SL ${r.sl}% / TP ${r.tp}% / ${r.maxAge}h — WR ${r.winRate}% | PF ${r.profitFactor} | Exp ${r.expectancy.toFixed(2)}% | ${r.trades}t`);
      }

      if (closest.length > 0) bestParams[algoId] = closest[0];
    }
  }

  // ─── Summary ───
  log('\n═══════════════════════════════════════════════════════');
  log('DEEP SWEEP RESULTS');
  log('═══════════════════════════════════════════════════════');

  const sorted = Object.values(bestParams).sort((a, b) => b.expectancy - a.expectancy);
  let profCount = 0;

  for (const r of sorted) {
    const status = r.expectancy > 0 ? '✓' : '✗';
    if (r.expectancy > 0) profCount++;
    log(`${status} ${r.algo_id.padEnd(25)} Entry=${r.entryType.padEnd(16)} SL ${String(r.sl).padStart(4)}% / TP ${String(r.tp).padStart(5)}% / ${String(r.maxAge).padStart(2)}h — WR ${String(r.winRate).padStart(5)}% | PF ${String(r.profitFactor).padStart(4)} | Exp ${r.expectancy >= 0 ? '+' : ''}${r.expectancy.toFixed(2)}% | ${r.trades}t`);
  }

  log(`\n${profCount}/${sorted.length} of the 10 failing strategies now profitable`);

  writeJSON('results/deep_sweep_best.json', bestParams);

  log('\n✓ Phase 5c complete');
  log('  → results/deep_sweep_best.json');
}

main().catch(err => {
  logError('Fatal error in deep sweep', err);
  process.exit(1);
});
