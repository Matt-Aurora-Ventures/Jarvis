/**
 * Phase 5e: Equity/Index Sweep (Tokenized Equities Calibration)
 *
 * Purpose:
 * - Find *any* profitable + consistent configs for tokenized equities strategies:
 *   xStocks, PreStocks, Indexes.
 *
 * Why a separate sweep?
 * - These assets have very different volatility/volume profiles vs memecoins.
 * - We need to sweep (timeframe × entryType × SL/TP/maxAge) on the *curated mint allowlist*.
 *
 * Run:
 *   npx tsx backtest-data/scripts/05e_equity_sweep.ts
 *
 * Optional env:
 *   EQUITY_SWEEP_ALGOS=xstock_intraday,xstock_swing,prestock_speculative,index_intraday,index_leveraged
 *   EQUITY_SWEEP_TIMEFRAMES=5m,15m,1h,1d
 *   EQUITY_SWEEP_MIN_TRADES=30
 *   EQUITY_SWEEP_MAX_TOKENS=50
 */

import {
  log, logError, readJSON, writeJSON, ensureDir,
} from './shared/utils';
import { CURRENT_ALGO_IDS, type AlgoId } from './shared/algo-ids';
import type { ScoredToken, Candle, ExitReason, TradeResult } from './shared/types';

// ─── Friction model (keep aligned with 05_simulate_trades.ts) ───
const SLIPPAGE_ENTRY_PCT = 0.5;
const SLIPPAGE_EXIT_PCT = 0.3;
const FEE_PER_SIDE_PCT = 0.25;
const BASE_TX_FEE_SOL = 0.000005;
const PRIORITY_FEE_SOL = 0.0002;
const FIXED_COST_ROUND_TRIP_SOL = (BASE_TX_FEE_SOL + PRIORITY_FEE_SOL) * 2;

const POSITION_SIZE_USD = 10;
const SOL_PRICE_USD = 150;
const FIXED_COST_USD = FIXED_COST_ROUND_TRIP_SOL * SOL_PRICE_USD;
const MIN_COOLDOWN_SECONDS = 60 * 60;

type Timeframe = '5m' | '15m' | '1h' | '1d';

type EntryType =
  | 'mean_reversion'
  | 'equity_mean_reversion'
  | 'trend_follow'
  | 'momentum'
  | 'sma_crossover'
  | 'range_breakout'
  | 'pullback_buy'
  | 'vol_surge_scalp'
  | 'strict_trend';

interface EntrySignal {
  candleIndex: number;
  entryPrice: number;
}

interface ExitParams {
  stopLossPct: number;
  takeProfitPct: number;
  maxPositionAgeHours: number;
}

type WindowSize = 10 | 25 | 50 | 100;
const WINDOWS: WindowSize[] = [10, 25, 50, 100];

interface Metrics {
  trades: number;
  winRate: number;
  profitFactor: number;
  expectancyPct: number;
  totalReturnPct: number;
  posFracByWindow: Partial<Record<WindowSize, number>>;
  minPosFrac: number;
}

interface Candidate {
  algo_id: AlgoId;
  timeframe: Timeframe;
  entryType: EntryType;
  sl: number;
  tp: number;
  maxAge: number;
  metrics: Metrics;
  score: number;
}

function envNum(name: string, fallback: number): number {
  const raw = process.env[name];
  const n = raw ? Number(raw) : NaN;
  return Number.isFinite(n) ? n : fallback;
}

function parseAlgoList(): AlgoId[] {
  const raw = String(process.env.EQUITY_SWEEP_ALGOS || '').trim();
  if (!raw) {
    return [
      'xstock_intraday',
      'xstock_swing',
      'prestock_speculative',
      'index_intraday',
      'index_leveraged',
    ];
  }
  const wanted = raw.split(',').map(s => s.trim()).filter(Boolean);
  const set = new Set(wanted);
  return CURRENT_ALGO_IDS.filter(id => set.has(id));
}

function parseTimeframes(): Timeframe[] {
  const raw = String(process.env.EQUITY_SWEEP_TIMEFRAMES || '').trim();
  if (!raw) return ['5m', '15m', '1h', '1d'];
  const wanted = raw.split(',').map(s => s.trim()).filter(Boolean);
  const out: Timeframe[] = [];
  for (const w of wanted) {
    if (w === '5m' || w === '15m' || w === '1h' || w === '1d') out.push(w);
  }
  return out.length ? out : ['5m', '15m', '1h', '1d'];
}

function loadCandles(mint: string, tf: Timeframe): Candle[] | null {
  const candles = readJSON<Candle[]>(`candles/${mint}_${tf}.json`);
  if (!candles || candles.length < 25) return null;
  return candles;
}

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

function rollingPosFrac(pnls: number[], window: number): number | null {
  if (pnls.length < window) return null;
  let sum = 0;
  for (let i = 0; i < window; i++) sum += pnls[i];
  let pos = sum > 0 ? 1 : 0;
  let windows = 1;
  for (let i = window; i < pnls.length; i++) {
    sum += pnls[i] - pnls[i - window];
    windows += 1;
    if (sum > 0) pos += 1;
  }
  return pos / windows;
}

function computeMetrics(trades: TradeResult[]): Metrics {
  const sorted = trades.slice().sort((a, b) => a.entry_timestamp - b.entry_timestamp);
  const pnls = sorted.map(t => t.pnl_percent);
  const wins = pnls.filter(p => p > 0).length;
  const total = pnls.reduce((s, p) => s + p, 0);

  const posFracByWindow: Metrics['posFracByWindow'] = {};
  const computed: number[] = [];
  for (const w of WINDOWS) {
    const pf = rollingPosFrac(pnls, w);
    if (pf === null) continue;
    const v = +pf.toFixed(3);
    posFracByWindow[w] = v;
    computed.push(v);
  }

  return {
    trades: trades.length,
    winRate: trades.length ? +(wins / trades.length * 100).toFixed(1) : 0,
    profitFactor: +computeProfitFactor(pnls).toFixed(3),
    expectancyPct: trades.length ? +(total / trades.length).toFixed(3) : 0,
    totalReturnPct: +total.toFixed(2),
    posFracByWindow,
    minPosFrac: computed.length ? +Math.min(...computed).toFixed(3) : 0,
  };
}

function scoreCandidate(m: Metrics): number {
  // Push toward consistency first, then expectancy.
  // Keep it simple: prefer higher minPos (stability) and positive expectancy.
  return (
    m.minPosFrac * 1000 +
    Math.min(5, m.profitFactor) * 50 +
    m.expectancyPct * 50 +
    Math.log10(Math.max(1, m.trades)) * 20
  );
}

function findEntrySignals(candles: Candle[], entryType: EntryType): EntrySignal[] {
  const signals: EntrySignal[] = [];
  if (candles.length < 25) return signals;

  const LB = 5;
  let lastSignalTs = -Infinity;

  for (let i = LB; i < candles.length - 5; i++) {
    const ts = candles[i].timestamp;
    if (Number.isFinite(lastSignalTs) && ts - lastSignalTs < MIN_COOLDOWN_SECONDS) continue;

    const c = candles[i];
    const prev = candles[i - 1];
    if (c.close <= 0 || prev.close <= 0 || c.volume <= 0) continue;

    const pct = ((c.close - prev.close) / prev.close) * 100;

    // SMA5
    let s5 = 0;
    for (let j = i - LB + 1; j <= i; j++) s5 += candles[j].close;
    const sma5 = s5 / LB;

    // SMA20 (for some signals)
    let s20 = 0;
    const lb20 = Math.min(20, i);
    for (let j = i - lb20 + 1; j <= i; j++) s20 += candles[j].close;
    const sma20 = s20 / lb20;

    // Volume spike vs last 5
    let vSum = 0;
    for (let j = i - LB + 1; j <= i; j++) vSum += candles[j].volume;
    const avgVol = vSum / LB;
    const volSpike = avgVol > 0 ? c.volume / avgVol : 1;

    let triggered = false;

    switch (entryType) {
      case 'mean_reversion':
        if (c.close < sma5 * 0.97 && c.close > c.open && prev.close < prev.open) triggered = true;
        break;
      case 'equity_mean_reversion':
        if (c.close < sma5 * 0.998 && c.close > c.open && prev.close < prev.open) triggered = true;
        break;
      case 'trend_follow':
        if (c.close > sma5 && c.high > prev.high && pct > 0.5 && volSpike > 1.2) triggered = true;
        break;
      case 'momentum':
        if (c.close > sma5 * 1.01 && pct > 2 && volSpike > 1.5) triggered = true;
        break;
      case 'sma_crossover': {
        if (i < 20) break;
        let prevS5 = 0;
        for (let j = i - LB; j < i; j++) prevS5 += candles[j].close;
        const prevSma5 = prevS5 / LB;
        let prev20 = 0;
        for (let j = i - 20; j < i; j++) prev20 += candles[j].close;
        const prevSma20 = prev20 / 20;
        if (prevSma5 <= prevSma20 && sma5 > sma20 && volSpike > 1.2 && c.close > c.open) triggered = true;
        break;
      }
      case 'range_breakout': {
        let rHigh = 0;
        for (let j = Math.max(0, i - 20); j < i; j++) if (candles[j].high > rHigh) rHigh = candles[j].high;
        if (rHigh > 0 && c.close > rHigh * 1.005 && volSpike > 1.8 && c.close > c.open) triggered = true;
        break;
      }
      case 'pullback_buy': {
        // Trend is up (SMA5 > SMA20) and price pulls back near SMA20 then reclaims.
        const nearSma20 = Math.abs(prev.low - sma20) / sma20 < 0.015;
        if (sma5 > sma20 && nearSma20 && c.close > sma5 && c.close > c.open && pct > 0.2) triggered = true;
        break;
      }
      case 'vol_surge_scalp':
        if (volSpike > 3.0 && pct > 1.5 && c.close > c.open && c.close > sma5) triggered = true;
        break;
      case 'strict_trend':
        if (c.close > sma20 * 1.01 && c.close > sma5 && c.high > prev.high && pct > 1.0 && volSpike > 1.5 &&
            c.close > c.open && prev.close > prev.open) {
          triggered = true;
        }
        break;
    }

    if (triggered) {
      signals.push({ candleIndex: i, entryPrice: c.close });
      lastSignalTs = ts;
    }
  }

  return signals;
}

function simulateOneTrade(
  algoId: AlgoId,
  token: ScoredToken & { vol_liq_ratio?: number },
  candles: Candle[],
  params: ExitParams,
  signal: EntrySignal,
): TradeResult | null {
  const rawEntry = signal.entryPrice;
  const entryPrice = rawEntry * (1 + SLIPPAGE_ENTRY_PCT / 100);
  if (entryPrice <= 0) return null;
  const entryTimestamp = candles[signal.candleIndex].timestamp;

  const slPrice = entryPrice * (1 - params.stopLossPct / 100);
  const tpPrice = entryPrice * (1 + params.takeProfitPct / 100);
  const maxAgeSeconds = params.maxPositionAgeHours * 3600;

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

    const slHit = candle.low <= slPrice;
    const tpHit = candle.high >= tpPrice;
    if (slHit) {
      exitPrice = slPrice;
      exitTimestamp = candle.timestamp;
      exitReason = 'sl_hit';
      dualTriggerBar = tpHit;
      exited = true;
      break;
    }
    if (tpHit) {
      exitPrice = tpPrice;
      exitTimestamp = candle.timestamp;
      exitReason = 'tp_hit';
      exited = true;
      break;
    }

    if (candle.timestamp - entryTimestamp > maxAgeSeconds) {
      exitPrice = candle.close;
      exitTimestamp = candle.timestamp;
      exitReason = 'expired';
      exited = true;
      break;
    }
  }

  if (!exited) {
    const last = candles[candles.length - 1];
    exitPrice = last.close;
    exitTimestamp = last.timestamp;
    exitReason = 'end_of_data';
  }

  if (exitPrice <= 0) exitPrice = entryPrice;

  const exitAfterFriction = exitPrice * (1 - SLIPPAGE_EXIT_PCT / 100) * (1 - FEE_PER_SIDE_PCT / 100);
  const entryAfterFees = entryPrice * (1 + FEE_PER_SIDE_PCT / 100);
  const pricePnlPct = ((exitAfterFriction - entryAfterFees) / entryAfterFees) * 100;
  const grossPnlUsd = POSITION_SIZE_USD * (pricePnlPct / 100);
  const netPnlUsd = grossPnlUsd - FIXED_COST_USD;
  const netPnlPct = (netPnlUsd / POSITION_SIZE_USD) * 100;

  return {
    algo_id: algoId,
    mint: token.mint,
    symbol: token.symbol,
    name: token.name,
    entry_timestamp: entryTimestamp,
    entry_price_usd: entryPrice,
    exit_timestamp: exitTimestamp,
    exit_price_usd: exitAfterFriction,
    pnl_percent: +netPnlPct.toFixed(4),
    pnl_usd: +netPnlUsd.toFixed(4),
    exit_reason: exitReason,
    dual_trigger_bar: dualTriggerBar,
    high_water_mark_price: highWaterMark,
    high_water_mark_percent: +(((highWaterMark - entryPrice) / entryPrice) * 100).toFixed(4),
    trade_duration_hours: +(((exitTimestamp - entryTimestamp) / 3600)).toFixed(2),
    candles_in_trade: candlesInTrade,
    score_at_entry: token.score,
    liquidity_at_entry: token.liquidity_usd,
    momentum_1h_at_entry: token.price_change_1h,
    vol_liq_ratio_at_entry: token.vol_liq_ratio || (token.liquidity_usd > 0 ? token.volume_24h_usd / token.liquidity_usd : 0),
  };
}

function simulateTradesFromSignals(
  algoId: AlgoId,
  token: ScoredToken & { vol_liq_ratio?: number },
  candles: Candle[],
  params: ExitParams,
  signals: EntrySignal[],
): TradeResult[] {
  if (signals.length === 0) return [];

  const trades: TradeResult[] = [];
  let lastExitTs = -Infinity;

  for (const s of signals) {
    const entryTs = candles[s.candleIndex]?.timestamp ?? 0;
    if (Number.isFinite(lastExitTs) && entryTs - lastExitTs < MIN_COOLDOWN_SECONDS) continue;

    const tr = simulateOneTrade(algoId, token, candles, params, s);
    if (!tr) continue;

    trades.push(tr);
    lastExitTs = tr.exit_timestamp;
  }

  return trades;
}

async function main(): Promise<void> {
  log('═══════════════════════════════════════════════════════');
  log('Phase 5e: Equity/Index Sweep');
  log('═══════════════════════════════════════════════════════');

  ensureDir('results');

  const algos = parseAlgoList();
  const tfs = parseTimeframes();
  const minTrades = Math.max(10, Math.floor(envNum('EQUITY_SWEEP_MIN_TRADES', 30)));
  const maxTokens = Math.max(1, Math.floor(envNum('EQUITY_SWEEP_MAX_TOKENS', 50)));
  const topK = Math.max(10, Math.floor(envNum('EQUITY_SWEEP_TOP_K', 200)));

  log(`Config: algos=${algos.length} | tfs=${tfs.join(',')} | minTrades=${minTrades} | maxTokens=${maxTokens} | topK=${topK}`);

  const ENTRY_TYPES: EntryType[] = [
    'equity_mean_reversion',
    'mean_reversion',
    'sma_crossover',
    'pullback_buy',
    'trend_follow',
    'range_breakout',
    'vol_surge_scalp',
    'momentum',
    'strict_trend',
  ];

  const SL_VALUES = [1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];
  const TP_VALUES = [3, 4, 5, 6, 8, 10, 12, 15, 20, 30, 50, 75, 100];
  const MAX_AGE_VALUES = [12, 24, 48, 72, 96, 168, 336, 720];

  const bestByAlgo: Partial<Record<AlgoId, Candidate>> = {};
  const bestByAlgoWinRate: Partial<Record<AlgoId, Candidate>> = {};
  const topByAlgo: Partial<Record<AlgoId, Candidate[]>> = {};

  function pushTop(list: Candidate[], c: Candidate): void {
    list.push(c);
    list.sort((a, b) => b.score - a.score);
    if (list.length > topK) list.length = topK;
  }

  for (const algoId of algos) {
    const tokens = readJSON<(ScoredToken & { vol_liq_ratio?: number })[]>(`qualified/qualified_${algoId}.json`) || [];
    if (tokens.length === 0) {
      log(`\n─── ${algoId}: no qualified tokens ───`);
      continue;
    }

    const selected = tokens.slice(0, maxTokens);
    log(`\n─── Sweeping ${algoId} (${selected.length}/${tokens.length} tokens) ───`);

    const top: Candidate[] = [];
    let bestWrOverall: Candidate | undefined;

    // Pre-load candles once per (token, tf)
    const candlesByMintTf = new Map<string, Candle[]>();
    for (const token of selected) {
      for (const tf of tfs) {
        const candles = loadCandles(token.mint, tf);
        if (candles) candlesByMintTf.set(`${token.mint}:${tf}`, candles);
      }
    }

    for (const tf of tfs) {
      // Precompute entry signals per (mint, entryType) for this timeframe.
      const signalsByMintEntry = new Map<string, EntrySignal[]>();

      for (const entryType of ENTRY_TYPES) {
        for (const token of selected) {
          const candles = candlesByMintTf.get(`${token.mint}:${tf}`);
          if (!candles) continue;
          const key = `${token.mint}:${entryType}`;
          if (!signalsByMintEntry.has(key)) {
            signalsByMintEntry.set(key, findEntrySignals(candles, entryType));
          }
        }

        for (const sl of SL_VALUES) {
          for (const tp of TP_VALUES) {
            // Skip impossible combos (TP too close to friction for tiny SL)
            if (tp <= 2) continue;

            for (const maxAge of MAX_AGE_VALUES) {
              const params: ExitParams = { stopLossPct: sl, takeProfitPct: tp, maxPositionAgeHours: maxAge };

              const trades: TradeResult[] = [];
              for (const token of selected) {
                const candles = candlesByMintTf.get(`${token.mint}:${tf}`);
                if (!candles) continue;

                // Fast skip if this token has no signals for this entryType.
                const sigs = signalsByMintEntry.get(`${token.mint}:${entryType}`) || [];
                if (sigs.length === 0) continue;

                // Enforce exit cooldown based on actual exits (time-based).
                trades.push(...simulateTradesFromSignals(algoId, token, candles, params, sigs));
              }

              if (trades.length < minTrades) continue;

              const m = computeMetrics(trades);
              // Require at least breakeven PF to consider.
              if (m.profitFactor < 1.0) continue;

              const candidate: Candidate = {
                algo_id: algoId,
                timeframe: tf,
                entryType,
                sl,
                tp,
                maxAge,
                metrics: m,
                score: scoreCandidate(m),
              };

              pushTop(top, candidate);

              // Track best-by-winrate across the FULL search space (not just topK-by-score).
              if (!bestWrOverall) {
                bestWrOverall = candidate;
              } else if (candidate.metrics.winRate > bestWrOverall.metrics.winRate) {
                bestWrOverall = candidate;
              } else if (
                candidate.metrics.winRate === bestWrOverall.metrics.winRate &&
                candidate.metrics.minPosFrac > bestWrOverall.metrics.minPosFrac
              ) {
                bestWrOverall = candidate;
              } else if (
                candidate.metrics.winRate === bestWrOverall.metrics.winRate &&
                candidate.metrics.minPosFrac === bestWrOverall.metrics.minPosFrac &&
                candidate.metrics.expectancyPct > bestWrOverall.metrics.expectancyPct
              ) {
                bestWrOverall = candidate;
              }
            }
          }
        }
      }
    }

    if (top.length === 0) {
      log(`  ✗ No profitable configs found (PF>=1 and trades>=${minTrades})`);
      continue;
    }

    bestByAlgo[algoId] = top[0];
    topByAlgo[algoId] = top;
    if (bestWrOverall) bestByAlgoWinRate[algoId] = bestWrOverall;

    const b = top[0];
    log(`  ✓ BEST: tf=${b.timeframe} entry=${b.entryType} SL=${b.sl}% TP=${b.tp}% maxAge=${b.maxAge}h`);
    log(`    trades=${b.metrics.trades} WR=${b.metrics.winRate}% PF=${b.metrics.profitFactor} Exp=${b.metrics.expectancyPct}% minPos=${b.metrics.minPosFrac}`);
  }

  writeJSON('results/equity_sweep_best.json', bestByAlgo);
  writeJSON('results/equity_sweep_best_by_winrate.json', bestByAlgoWinRate);
  writeJSON('results/equity_sweep_top.json', topByAlgo);
  log('\n✓ Phase 5e complete');
  log('  → results/equity_sweep_best.json');
  log('  → results/equity_sweep_best_by_winrate.json');
  log('  → results/equity_sweep_top.json');
}

main().catch(err => {
  logError('Fatal error in equity sweep', err);
  process.exit(1);
});
