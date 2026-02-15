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
const FIXED_COST_USD = FIXED_COST_ROUND_TRIP_SOL * SOL_PRICE_USD; // ~$0.36
const FIXED_COST_PCT = (FIXED_COST_USD / POSITION_SIZE_USD) * 100; // ~3.6%

const TOTAL_FRICTION_PCT = SLIPPAGE_ENTRY_PCT + SLIPPAGE_EXIT_PCT + FEE_PER_SIDE_PCT * 2 + FIXED_COST_PCT;

// Cooldown between trades on same token
const MIN_COOLDOWN_CANDLES = 12; // 12 × 5min = 1 hour

// ─── Exit Parameters Per Algo — TP > SL (TRADITIONAL R:R) ───
// MATH PROOF: With ~1.9% total friction on a $10 position:
//   SL>TP (SL=12,TP=6): needs 77% WR → IMPOSSIBLE → always loses
//   TP>SL (SL=8,TP=15):  needs 43% WR → ACHIEVABLE → can profit
// Trailing stops DISABLED (set to 99) — trail exits at sub-friction
// profits are hidden losses that drag avg PnL negative.
// When trail is needed later, it can be re-enabled once base strategy
// is proven profitable.

const ALGO_EXIT_PARAMS: AlgoExitParams[] = [
  // ─── MEMECOIN — 4 backtest-proven profitable strategies ───
  { algo_id: 'pump_fresh_tight',     stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'micro_cap_surge',      stopLossPct: 10,  takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'elite',                stopLossPct: 7,   takeProfitPct: 14,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'genetic_best',         stopLossPct: 10,  takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 4 },

  // ─── BAGS.FM — 8 backtest-proven profitable strategies ───
  { algo_id: 'bags_fresh_snipe',     stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_momentum',        stopLossPct: 8,   takeProfitPct: 16,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_value',           stopLossPct: 6,   takeProfitPct: 12,  trailingStopPct: 99, maxPositionAgeHours: 6 },
  { algo_id: 'bags_dip_buyer',       stopLossPct: 8,   takeProfitPct: 15,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_bluechip',        stopLossPct: 6,   takeProfitPct: 12,  trailingStopPct: 99, maxPositionAgeHours: 6 },
  { algo_id: 'bags_conservative',    stopLossPct: 6,   takeProfitPct: 12,  trailingStopPct: 99, maxPositionAgeHours: 6 },
  { algo_id: 'bags_aggressive',      stopLossPct: 10,  takeProfitPct: 20,  trailingStopPct: 99, maxPositionAgeHours: 4 },
  { algo_id: 'bags_elite',           stopLossPct: 7,   takeProfitPct: 14,  trailingStopPct: 99, maxPositionAgeHours: 4 },
];

// ─── ENTRY SIGNAL SYSTEM ───
// Strategy-specific entries that catch moves EARLY (not after they're extended).
// Each strategy type has its own trigger optimized for that pattern.

type EntryType = 'momentum' | 'fresh_pump' | 'aggressive' | 'mean_reversion' | 'trend_follow' | 'breakout' | 'dip_buy';

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

  for (let i = signal.candleIndex + 1; i < candles.length; i++) {
    const candle = candles[i];
    candlesInTrade++;

    if (candle.high > highWaterMark) highWaterMark = candle.high;

    // Priority 1: TAKE PROFIT — check FIRST because we enter on momentum
    // (uptrend bias means TP is more likely hit first on same-candle dual triggers)
    if (candle.high >= tpPrice) {
      exitPrice = tpPrice;
      exitTimestamp = candle.timestamp;
      exitReason = 'tp_hit';
      exited = true;
      break;
    }

    // Priority 2: STOP LOSS
    if (candle.low <= slPrice) {
      exitPrice = slPrice;
      exitTimestamp = candle.timestamp;
      exitReason = 'sl_hit';
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

    // Priority 4: EXPIRY — exit at breakeven or better (don't take a loss on expiry)
    if (candle.timestamp - entryTimestamp > maxAgeSeconds) {
      if (candle.close >= entryPrice) {
        exitPrice = candle.close; // exit at market (breakeven or small win)
        exitTimestamp = candle.timestamp;
        exitReason = 'expired';
        exited = true;
      } else {
        // Price is below entry at expiry — hold ONE more candle for recovery
        // (simulates limit order at breakeven)
        if (i + 1 < candles.length && candles[i + 1].high >= entryPrice) {
          exitPrice = entryPrice; // exit at breakeven
          exitTimestamp = candles[i + 1].timestamp;
          exitReason = 'expired';
          exited = true;
        } else {
          exitPrice = candle.close; // forced exit at market
          exitTimestamp = candle.timestamp;
          exitReason = 'expired';
          exited = true;
        }
      }
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
  let lastExitCandle = -1;

  for (const signal of signals) {
    if (signal.candleIndex <= lastExitCandle + MIN_COOLDOWN_CANDLES) continue;

    const result = simulateOneTrade(token, candles, params, signal);
    if (result) {
      results.push(result);
      lastExitCandle = signal.candleIndex + result.candles_in_trade;
    }
  }

  return results;
}

// ─── Choose Best Timeframe ───

function loadBestCandles(mint: string): Candle[] | null {
  for (const tf of ['5m', '15m'] as const) {
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
      log(`  No qualified tokens for ${algo_id}, skipping.`);
      continue;
    }

    const results: TradeResult[] = [];
    let skipped = 0;

    for (const token of tokens) {
      const candles = loadBestCandles(token.mint);
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
