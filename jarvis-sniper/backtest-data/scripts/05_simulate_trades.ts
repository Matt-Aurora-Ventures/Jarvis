/**
 * Phase 5: Trade Simulation (Backtest Engine) — QUICK SCALP v2
 * 
 * Realistic simulation with:
 * - Tight SL/TP for quick in/out (5-10% SL, 8-20% TP)
 * - Slippage + fees modeled (1-2% entry slippage, 0.25% fee/side)
 * - Multiple trades per token (find ALL entry signals, not just first)
 * - Short max holds (1-4 hours for memecoins)
 * - Cooldown between trades on same token
 * 
 * Run: npx tsx backtest-data/scripts/05_simulate_trades.ts
 */

import {
  log, logError, readJSON, writeJSON, writeCSV, ensureDir,
} from './shared/utils';
import type { ScoredToken, Candle, AlgoExitParams, TradeResult, ExitReason } from './shared/types';

// ─── REALISTIC FRICTION (percentage-based) ───
const SLIPPAGE_ENTRY_PCT = 0.5;   // % added to entry price
const SLIPPAGE_EXIT_PCT = 0.3;    // % subtracted from exit price
const FEE_PER_SIDE_PCT = 0.25;    // Jupiter/Raydium fee per swap

// ─── FIXED SOLANA TRANSACTION COSTS ───
// Individual snipes use sendWithJito (jito.wtf/api/v1/transactions) NOT bundle tips.
// The 0.001 SOL JITO bundle tip is ONLY for batch Close All operations.
// Per-trade cost = priority fee (200,000 microlamports = 0.0002 SOL) + base fee per tx.
const BASE_TX_FEE_SOL = 0.000005;
const PRIORITY_FEE_SOL = 0.0002;         // from bags-trading.ts: priorityFeeMicroLamports: 200_000
const FIXED_COST_PER_TX_SOL = BASE_TX_FEE_SOL + PRIORITY_FEE_SOL;
const FIXED_COST_ROUND_TRIP_SOL = FIXED_COST_PER_TX_SOL * 2; // buy + sell = 2 txs

// Position sizing — users trade with $5-15 typically
const POSITION_SIZE_USD = 10;
const SOL_PRICE_USD = 150;
const FIXED_COST_USD = FIXED_COST_ROUND_TRIP_SOL * SOL_PRICE_USD; // ~$0.06
const FIXED_COST_PCT = (FIXED_COST_USD / POSITION_SIZE_USD) * 100; // ~0.6%

const TOTAL_FRICTION_PCT = SLIPPAGE_ENTRY_PCT + SLIPPAGE_EXIT_PCT + FEE_PER_SIDE_PCT * 2 + FIXED_COST_PCT;

// Cooldown between trades on the same token (time-based so it's timeframe-invariant).
const MIN_COOLDOWN_SECONDS = 60 * 60; // 1 hour

// ─── Exit Parameters Per Algo — TP > SL (TRADITIONAL R:R) ───
// MATH PROOF: With ~1.9% total friction on a $10 position:
//   SL>TP (SL=12,TP=6): needs ~77% WR → only viable with extremely selective entries
//   TP>SL (SL=8,TP=15):  needs ~43% WR → more realistic for noisy markets
// Trailing stops DISABLED (set to 99) — trail exits at sub-friction
// profits are hidden losses that drag avg PnL negative.
// When trail is needed later, it can be re-enabled once base strategy
// is proven profitable.

const ALGO_EXIT_PARAMS: AlgoExitParams[] = [
  // ─── MEMECOIN CORE — 3 strategies (SL 10%, TP 20% = 2:1 R:R) ───
  // PROVEN: These work at 10/20 across R1-R3
  { algo_id: 'elite',                stopLossPct: 10,  takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 12 },
  { algo_id: 'micro_cap_surge',      stopLossPct: 10,  takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 8 },
  { algo_id: 'pump_fresh_tight',     stopLossPct: 10,  takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 8 },

  // ─── MEMECOIN WIDE — 3 strategies (SL 10%, TP 25% = 2.5:1 R:R) ───
  // FINAL: mean_reversion entry, SL 10/TP 25. PF 0.97 (borderline). Higher TP needed for profit.
  { algo_id: 'momentum',             stopLossPct: 10,  takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 48 },
  { algo_id: 'hybrid_b',             stopLossPct: 10,  takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 48 },
  { algo_id: 'let_it_ride',          stopLossPct: 10,  takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 72 },

  // ─── ESTABLISHED TOKENS — 5 strategies (SL 7-8%, TP 15%) ───
  // PROVEN: 8/15 works for sol_veteran, utility_swing, meme_classic
  // volume_spike moves to mean_reversion entry at 8/15 (was dip_buy — failed at 10/20 and 8/20)
  { algo_id: 'sol_veteran',          stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },
  { algo_id: 'utility_swing',        stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },
  { algo_id: 'established_breakout', stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },
  { algo_id: 'meme_classic',         stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },
  { algo_id: 'volume_spike',         stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 168 },

  // ─── BAGS.FM — 8 strategies (mixed params, all optimized) ───
  { algo_id: 'bags_fresh_snipe',     stopLossPct: 10,  takeProfitPct: 30,  trailingStopPct: 99, maxPositionAgeHours: 8 },
  { algo_id: 'bags_momentum',        stopLossPct: 10,  takeProfitPct: 30,  trailingStopPct: 99, maxPositionAgeHours: 12 },
  { algo_id: 'bags_aggressive',      stopLossPct: 7,   takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 12 },
  { algo_id: 'bags_dip_buyer',       stopLossPct: 8,   takeProfitPct: 25,  trailingStopPct: 99, maxPositionAgeHours: 8 },
  { algo_id: 'bags_elite',           stopLossPct: 5,   takeProfitPct: 9,   trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_value',           stopLossPct: 5,   takeProfitPct: 10,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_conservative',    stopLossPct: 5,   takeProfitPct: 10,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_bluechip',        stopLossPct: 5,   takeProfitPct: 9,   trailingStopPct: 99, maxPositionAgeHours: 4 },

  // ─── BLUE CHIP SOLANA — 2 strategies (SL 10%, TP 25% = 2.5:1 R:R) ───
  // R4: mean_reversion entry + SL 10/TP 25. breakout entry failed in R3.
  // Updated (2026-02-16 sweep on 15m candles): SL 5 / TP 30 / 14d max age.
  { algo_id: 'bluechip_trend_follow',stopLossPct: 5,   takeProfitPct: 30,  trailingStopPct: 99, maxPositionAgeHours: 336 },
  { algo_id: 'bluechip_breakout',    stopLossPct: 5,   takeProfitPct: 30,  trailingStopPct: 99, maxPositionAgeHours: 336 },

  // ─── xSTOCK & PRESTOCK (tokenized equities) ───
  // Calibrated via backtest-data/scripts/05e_equity_sweep.ts (2026-02-16 run on curated mint allowlist).
  { algo_id: 'xstock_intraday',      stopLossPct: 8,   takeProfitPct: 100, trailingStopPct: 99, maxPositionAgeHours: 48 },
  { algo_id: 'xstock_swing',         stopLossPct: 2,   takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 72 },
  { algo_id: 'prestock_speculative', stopLossPct: 10,  takeProfitPct: 12,  trailingStopPct: 99, maxPositionAgeHours: 720 },

  // ─── INDEX — requires higher TF + longer holds ───
  // Calibrated via 05e (daily candles): equity_mean_reversion, SL 6 / TP 20 / 30d max age.
  { algo_id: 'index_intraday',       stopLossPct: 6,   takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 720 },
  { algo_id: 'index_leveraged',      stopLossPct: 6,   takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 720 },
];

// ─── ENTRY SIGNAL SYSTEM ───
// Strategy-specific entries that catch moves EARLY (not after they're extended).
// Each strategy type has its own trigger optimized for that pattern.

type EntryType =
  | 'momentum'
  | 'fresh_pump'
  | 'aggressive'
  | 'mean_reversion'
  | 'trend_follow'
  | 'breakout'
  | 'dip_buy'
  | 'strict_trend'
  | 'sma_crossover'
  | 'accumulation'
  | 'range_breakout'
  | 'pullback_buy'
  | 'vol_surge_scalp'
  // Tokenized equities move differently than memecoins; use separate thresholds.
  | 'equity_mean_reversion';

interface EntrySignal {
  candleIndex: number;
  entryPrice: number;
  score: number;
}

function computeATR(candles: Candle[], endIdx: number, period: number): number {
  let sum = 0;
  const start = Math.max(1, endIdx - period + 1);
  let count = 0;
  for (let i = start; i <= endIdx; i++) {
    const tr = Math.max(
      candles[i].high - candles[i].low,
      Math.abs(candles[i].high - candles[i - 1].close),
      Math.abs(candles[i].low - candles[i - 1].close),
    );
    sum += tr;
    count++;
  }
  return count > 0 ? sum / count : 0;
}

function getEntryType(algoId: string): EntryType {
  // Sweep-optimized entry types — some strategies changed from original
  if (['pump_fresh_tight', 'bags_fresh_snipe'].includes(algoId)) return 'fresh_pump';
  if (['micro_cap_surge', 'bags_aggressive'].includes(algoId)) return 'aggressive';
  if (['elite', 'bags_momentum'].includes(algoId)) return 'momentum';
  // Deep sweep found mean_reversion entry works for these (was momentum/aggressive/trend_follow)
  // FINAL (R4): mean_reversion for memecoin wide, bluechip, xstock/index, volume_spike
  // Tested: momentum, aggressive, breakout, range_breakout entries all worse (R3, R6)
  if (['momentum', 'hybrid_b', 'let_it_ride', 'bluechip_trend_follow', 'bluechip_breakout'].includes(algoId)) return 'mean_reversion';
  if (['bags_value', 'bags_bluechip', 'bags_elite', 'bags_conservative'].includes(algoId)) return 'mean_reversion';
  // Tokenized equities: calibrated via backtest-data/scripts/05e_equity_sweep.ts (2026-02-16).
  if (algoId === 'xstock_intraday') return 'mean_reversion';
  if (algoId === 'xstock_swing') return 'momentum';
  if (algoId === 'prestock_speculative') return 'range_breakout';
  // Indexes behave much better on higher timeframes with gentle mean reversion.
  if (algoId === 'index_intraday') return 'equity_mean_reversion';
  if (algoId === 'index_leveraged') return 'equity_mean_reversion';
  if (['volume_spike'].includes(algoId)) return 'mean_reversion';
  if (['bags_dip_buyer'].includes(algoId)) return 'dip_buy';
  // Established token strategies (sweep-optimized entry types)
  if (['sol_veteran', 'utility_swing', 'established_breakout', 'meme_classic'].includes(algoId)) return 'mean_reversion';
  return 'momentum';
}

function findAllEntrySignals(candles: Candle[], entryType: EntryType): EntrySignal[] {
  const signals: EntrySignal[] = [];
  if (candles.length < 20) return signals;

  const LB = 5;
  let lastSignalTs = -Infinity;

  for (let i = LB; i < candles.length - 5; i++) {
    const ts = candles[i].timestamp;
    if (Number.isFinite(lastSignalTs) && ts - lastSignalTs < MIN_COOLDOWN_SECONDS) continue;

    const c = candles[i];
    const prev = candles[i - 1];
    if (c.close <= 0 || prev.close <= 0 || c.volume <= 0) continue;

    const pct = ((c.close - prev.close) / prev.close) * 100;

    // SMA-5
    let s5 = 0;
    for (let j = i - LB + 1; j <= i; j++) s5 += candles[j].close;
    const sma5 = s5 / LB;

    // Volume spike vs last 5
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
      case 'equity_mean_reversion':
        // Equities/indexes usually won't dip 3% in one 5m bar. Use a smaller threshold.
        // Keep the same "reversal candle" requirement to avoid catching falling knives.
        if (c.close < sma5 * 0.998 && c.close > c.open && prev.close < prev.open) triggered = true;
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
      case 'strict_trend': {
        // Stricter trend: above SMA20, new high, 1%+ move, strong volume, 2 green candles
        let st20 = 0;
        const stLb = Math.min(20, i);
        for (let j = i - stLb + 1; j <= i; j++) st20 += candles[j].close;
        const stSma20 = st20 / stLb;
        if (c.close > stSma20 && c.close > sma5 && c.high > prev.high && pct > 1.0 && volSpike > 1.5 &&
            c.close > c.open && prev.close > prev.open) {
          triggered = true;
        }
        break;
      }
      case 'sma_crossover': {
        // SMA5 crosses above SMA20 with volume confirmation — classic trend start
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
        // Cross: prev SMA5 <= SMA20, current SMA5 > SMA20, with volume
        if (prevSma5 <= prevSma20 && sma5 > scSma20 && volSpike > 1.3 && c.close > c.open) {
          triggered = true;
        }
        break;
      }
      case 'accumulation': {
        // Volume increasing while price stable — accumulation before breakout
        if (i < 10) break;
        let avgVol10 = 0;
        for (let j = i - 9; j <= i; j++) avgVol10 += candles[j].volume;
        avgVol10 /= 10;
        let avgVol5Prior = 0;
        for (let j = i - 9; j <= i - 5; j++) avgVol5Prior += candles[j].volume;
        avgVol5Prior /= 5;
        let avgVol5Recent = 0;
        for (let j = i - 4; j <= i; j++) avgVol5Recent += candles[j].volume;
        avgVol5Recent /= 5;
        // Price range is tight (<3%), volume is ramping up (1.5x+)
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
        // Price breaks above 20-candle high with 2x+ volume — confirmed breakout
        if (i < 20) break;
        let rbHigh = 0;
        for (let j = i - 20; j < i; j++) if (candles[j].high > rbHigh) rbHigh = candles[j].high;
        if (c.close > rbHigh * 1.005 && volSpike > 2.0 && c.close > c.open) {
          triggered = true;
        }
        break;
      }
      case 'pullback_buy': {
        // Price pulls back to SMA20 in an uptrend, then bounces
        if (i < 20) break;
        let pb20 = 0;
        for (let j = i - 19; j <= i; j++) pb20 += candles[j].close;
        const pbSma20 = pb20 / 20;
        // Uptrend: SMA5 > SMA20
        // Pullback: prev candle touched near SMA20 (within 1%)
        // Bounce: current candle is green and above SMA5
        const nearSma20 = Math.abs(prev.low - pbSma20) / pbSma20 < 0.015;
        if (sma5 > pbSma20 && nearSma20 && c.close > sma5 && c.close > c.open && pct > 0.5) {
          triggered = true;
        }
        break;
      }
      case 'vol_surge_scalp': {
        // Sudden 3x+ volume spike with strong green candle — quick scalp
        if (volSpike > 3.0 && pct > 1.5 && c.close > c.open && c.close > sma5) {
          triggered = true;
        }
        break;
      }
    }

    if (triggered) {
      signals.push({ candleIndex: i, entryPrice: c.close, score: 0 });
      lastSignalTs = ts;
    }
  }

  return signals;
}

// ─── Trade Simulation Engine ───

function simulateOneTrade(
  token: ScoredToken & { vol_liq_ratio?: number; age_hours?: number },
  candles: Candle[],
  params: AlgoExitParams,
  signal: EntrySignal,
): TradeResult | null {
  const rawEntry = signal.entryPrice;
  const entryPrice = rawEntry * (1 + SLIPPAGE_ENTRY_PCT / 100);
  if (entryPrice <= 0) return null;
  const entryTimestamp = candles[signal.candleIndex].timestamp;

  // Fixed SL/TP/Trail — no ATR widening
  const slPrice = entryPrice * (1 - params.stopLossPct / 100);
  const tpPrice = entryPrice * (1 + params.takeProfitPct / 100);
  // Trail activation: MUST guarantee minimum trail exit > total friction (~1.9%)
  // minTrailExit = activationPct - trailingStopPct  →  must exceed TOTAL_FRICTION_PCT
  // activationPct = TOTAL_FRICTION_PCT + trailingStopPct + 0.5% buffer
  // If activation > TP, trail never fires (TP catches it first — which is fine)
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
  let dualTriggerBar = false;

  for (let i = signal.candleIndex + 1; i < candles.length; i++) {
    const candle = candles[i];
    candlesInTrade++;

    if (candle.high > highWaterMark) highWaterMark = candle.high;

    // Conservative intrabar ambiguity rule:
    // If both TP and SL are hit in the same candle, count it as SL.
    const slHit = candle.low <= slPrice;
    const tpHit = candle.high >= tpPrice;

    // Priority 1: STOP LOSS (SL-first)
    if (slHit) {
      dualTriggerBar = tpHit;
      exitPrice = slPrice;
      exitTimestamp = candle.timestamp;
      exitReason = 'sl_hit';
      exited = true;
      break;
    }

    // Priority 2: TAKE PROFIT
    if (tpHit) {
      exitPrice = tpPrice;
      exitTimestamp = candle.timestamp;
      exitReason = 'tp_hit';
      exited = true;
      break;
    }

    // Priority 3: TRAILING STOP
    if (highWaterMark > trailActivationPrice) {
      const trailStopPrice = highWaterMark * (1 - params.trailingStopPct / 100);
      if (candle.low <= trailStopPrice) {
        exitPrice = trailStopPrice;
        exitTimestamp = candle.timestamp;
        exitReason = 'trail_stop';
        exited = true;
        break;
      }
    }

    // Priority 4: EXPIRY — exit at market (candle close) at expiry
    if (candle.timestamp - entryTimestamp > maxAgeSeconds) {
      exitPrice = candle.close;
      exitTimestamp = candle.timestamp;
      exitReason = 'expired';
      exited = true;
      break;
    }
  }

  if (!exited) {
    const lastCandle = candles[candles.length - 1];
    exitPrice = lastCandle.close;
    exitTimestamp = lastCandle.timestamp;
    exitReason = 'end_of_data';
    candlesInTrade = candles.length - signal.candleIndex - 1;
  }

  if (exitPrice <= 0) exitPrice = entryPrice;

  // Apply exit slippage + DEX fees
  const exitAfterFriction = exitPrice * (1 - SLIPPAGE_EXIT_PCT / 100) * (1 - FEE_PER_SIDE_PCT / 100);
  const entryAfterFees = entryPrice * (1 + FEE_PER_SIDE_PCT / 100);

  // PnL as percentage (before fixed costs)
  const pricePnlPct = ((exitAfterFriction - entryAfterFees) / entryAfterFees) * 100;

  // Actual USD PnL on a real $POSITION_SIZE_USD trade including JITO/Solana fixed costs
  const grossPnlUsd = POSITION_SIZE_USD * (pricePnlPct / 100);
  const netPnlUsd = grossPnlUsd - FIXED_COST_USD;
  const netPnlPct = (netPnlUsd / POSITION_SIZE_USD) * 100;

  const hwmPercent = ((highWaterMark - entryPrice) / entryPrice) * 100;
  const durationHours = (exitTimestamp - entryTimestamp) / 3600;

  return {
    algo_id: params.algo_id,
    mint: token.mint,
    symbol: token.symbol,
    name: token.name,
    entry_timestamp: entryTimestamp,
    entry_price_usd: entryPrice,
    exit_timestamp: exitTimestamp,
    exit_price_usd: exitAfterFriction,
    pnl_percent: +netPnlPct.toFixed(4),        // NET of all costs including JITO
    pnl_usd: +netPnlUsd.toFixed(4),            // actual USD on $10 position
    exit_reason: exitReason,
    dual_trigger_bar: dualTriggerBar,
    high_water_mark_price: highWaterMark,
    high_water_mark_percent: +hwmPercent.toFixed(4),
    trade_duration_hours: +durationHours.toFixed(2),
    candles_in_trade: candlesInTrade,
    score_at_entry: token.score,
    liquidity_at_entry: token.liquidity_usd,
    momentum_1h_at_entry: token.price_change_1h,
    vol_liq_ratio_at_entry: token.vol_liq_ratio || (token.liquidity_usd > 0 ? token.volume_24h_usd / token.liquidity_usd : 0),
  };
}

// Simulate ALL trades for one token (multiple entries via strategy-specific signals)
function simulateAllTrades(
  token: ScoredToken & { vol_liq_ratio?: number; age_hours?: number },
  candles: Candle[],
  params: AlgoExitParams,
): TradeResult[] {
  if (candles.length < 20) return [];

  const entryType = getEntryType(params.algo_id);
  const signals = findAllEntrySignals(candles, entryType);
  if (signals.length === 0) return [];

  const results: TradeResult[] = [];
  let lastExitTs = -Infinity;

  for (const signal of signals) {
    const entryTs = candles[signal.candleIndex]?.timestamp ?? 0;
    if (Number.isFinite(lastExitTs) && entryTs - lastExitTs < MIN_COOLDOWN_SECONDS) continue;

    const result = simulateOneTrade(token, candles, params, signal);
    if (result) {
      results.push(result);
      lastExitTs = result.exit_timestamp;
    }
  }

  return results;
}

// ─── Choose Best Timeframe ───

function loadBestCandles(algoId: string, mint: string): Candle[] | null {
  const isEquity =
    algoId.startsWith('xstock_') ||
    algoId.startsWith('index_') ||
    algoId === 'prestock_speculative';

  // Default: try shorter timeframes first, but allow 1h as a fallback.
  // Some asset classes (bluechips, indexes) behave far better on higher TFs.
  let tfs: ('5m' | '15m' | '1h' | '1d')[] = ['5m', '15m', '1h', '1d'];

  if (isEquity) {
    // Equity/index strategies are sensitive to timeframe; keep deterministic per-strategy defaults.
    if (algoId === 'xstock_intraday') tfs = ['1h', '15m', '5m', '1d'];
    else if (algoId === 'xstock_swing') tfs = ['1h', '15m', '5m', '1d'];
    else if (algoId === 'index_intraday') tfs = ['1d', '1h', '15m', '5m'];
    else if (algoId === 'index_leveraged') tfs = ['1d', '1h', '15m', '5m'];
    else if (algoId === 'prestock_speculative') tfs = ['1d', '1h', '15m', '5m'];
    else tfs = ['1h', '15m', '5m', '1d'];
  } else {
    // Bluechip strategies should prefer higher timeframes to reduce noise.
    if (algoId === 'bluechip_trend_follow' || algoId === 'bluechip_breakout') {
      // Sweep results are strongest on 15m with longer max-age; keep 1h/1d as fallbacks.
      tfs = ['15m', '1h', '5m', '1d'];
    }
  }

  for (const tf of tfs) {
    const candles = readJSON<Candle[]>(`candles/${mint}_${tf}.json`);
    if (candles && candles.length >= 25) return candles;
  }
  return null;
}

// ─── Main ───

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 5: Trade Simulation v3 (Strategy Entries + Fixed Costs + ATR-Adaptive)');
  log(`Position size: $${POSITION_SIZE_USD} | SOL: $${SOL_PRICE_USD}`);
  log(`Fixed Solana costs: $${FIXED_COST_USD.toFixed(2)}/trade (${FIXED_COST_PCT.toFixed(1)}% of position)`);
  log(`DEX friction: ${(SLIPPAGE_ENTRY_PCT + SLIPPAGE_EXIT_PCT + FEE_PER_SIDE_PCT * 2).toFixed(1)}% (slippage + fees)`);
  log(`Total round-trip cost: ${TOTAL_FRICTION_PCT.toFixed(1)}%`);
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  let totalSimulated = 0;
  let totalSkipped = 0;

  for (const params of ALGO_EXIT_PARAMS) {
    const { algo_id } = params;
    log(`\n─── Simulating ${algo_id} (SL ${params.stopLossPct}% / TP ${params.takeProfitPct}% / Trail ${params.trailingStopPct}% / Max ${params.maxPositionAgeHours}h) ───`);

    const tokens = readJSON<(ScoredToken & { vol_liq_ratio?: number })[]>(
      `qualified/qualified_${algo_id}.json`,
    );

    if (!tokens || tokens.length === 0) {
      // Important: always overwrite stale results from prior runs, otherwise Phase 6 can
      // accidentally pick up old `results_{algo}.json` for strategies that are now empty.
      log(`  No qualified tokens for ${algo_id}, writing empty results.`);
      writeJSON(`results/results_${algo_id}.json`, []);
      continue;
    }

    const results: TradeResult[] = [];
    let skipped = 0;

    for (const token of tokens) {
      const candles = loadBestCandles(algo_id, token.mint);
      if (!candles) { skipped++; continue; }

      const trades = simulateAllTrades(token, candles, params);
      if (trades.length > 0) results.push(...trades);
      else skipped++;
    }

    log(`  ${algo_id}: ${results.length} trades simulated, ${skipped} skipped`);
    totalSimulated += results.length;
    totalSkipped += skipped;

    results.sort((a, b) => a.entry_timestamp - b.entry_timestamp);

    writeJSON(`results/results_${algo_id}.json`, results);
    writeCSV(`results/results_${algo_id}.csv`, results as unknown as Record<string, unknown>[]);

    if (results.length > 0) {
      const wins = results.filter(r => r.pnl_usd > 0).length;
      const wr = (wins / results.length * 100).toFixed(1);
      const avgPnlUsd = results.reduce((s, r) => s + r.pnl_usd, 0) / results.length;
      const avgPnlPct = results.reduce((s, r) => s + r.pnl_percent, 0) / results.length;
      const tpHits = results.filter(r => r.exit_reason === 'tp_hit').length;
      const slHits = results.filter(r => r.exit_reason === 'sl_hit').length;
      const trailHits = results.filter(r => r.exit_reason === 'trail_stop').length;
      const avgDuration = results.reduce((s, r) => s + r.trade_duration_hours, 0) / results.length;
      const totalPnl = results.reduce((s, r) => s + r.pnl_usd, 0);
      log(`  WR: ${wr}% | Avg PnL: $${avgPnlUsd.toFixed(2)} (${avgPnlPct.toFixed(2)}%) | Total: $${totalPnl.toFixed(2)} | Trades: ${results.length} | Avg hold: ${avgDuration.toFixed(1)}h`);
      log(`  Exits: TP ${tpHits} | SL ${slHits} | Trail ${trailHits} | Expired ${results.filter(r => r.exit_reason === 'expired').length} | EOD ${results.filter(r => r.exit_reason === 'end_of_data').length}`);
    }
  }

  log('');
  log('═══════════════════════════════════════════════════════');
  log(`Total trades simulated: ${totalSimulated}`);
  log(`Total skipped (no data): ${totalSkipped}`);
  log(`Position size: $${POSITION_SIZE_USD} | Fixed cost/trade: $${FIXED_COST_USD.toFixed(2)}`);

  log(`\n✓ Phase 5 complete`);
  log(`  → results/results_{algo_id}.json`);
  log(`  → results/results_{algo_id}.csv`);
}

main().catch(err => {
  logError('Fatal error in trade simulation', err);
  process.exit(1);
});
