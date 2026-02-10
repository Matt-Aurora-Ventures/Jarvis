/**
 * Bags.fm Backtesting Pipeline
 *
 * Fetches historical bags.fm graduations, enriches with DexScreener price data,
 * and simulates trades across a grid of strategy parameters to find optimal
 * SL/TP/trailing/score configurations.
 *
 * Key design decisions:
 * - NO liquidity score filter (bags locks liquidity, making it irrelevant)
 * - Multiple endpoint fallbacks for graduation data
 * - Pagination support for large historical fetches
 * - In-memory cache with 1-hour TTL
 * - Graceful degradation on API failures
 */

import { ServerCache } from '@/lib/server-cache';

// ─── Types ───

export interface BagsGraduationRecord {
  mint: string;
  symbol: string;
  name: string;
  score: number;
  graduationTime: number;       // Unix ms
  bondingCurveScore: number;
  holderDistributionScore: number;
  socialScore: number;
  marketCap: number;
  priceAtGraduation: number;
  liquidity: number;
}

export interface EnrichedGraduation extends BagsGraduationRecord {
  currentPrice: number | null;
  peakPrice: number | null;
  priceChange5m: number | null;
  priceChange1h: number | null;
  priceChange24h: number | null;
  volume24h: number | null;
  timeToPeakMs: number | null;
  peakMultiplier: number | null;
}

export interface BagsTradeSimulation {
  hit: 'tp' | 'sl' | 'trail' | 'none';
  pnlPct: number;
  effectiveEntryPrice: number;
  exitPrice: number;
}

export interface BagsStrategyResult {
  id: string;
  params: {
    stopLossPct: number;
    takeProfitPct: number;
    trailingStopPct: number;
    entryDelayMinutes: number;
    minScore: number;
    minBondingScore?: number;
    minHolderScore?: number;
    minSocialScore?: number;
  };
  trades: number;
  wins: number;
  losses: number;
  winRate: number;
  avgProfitPct: number;
  avgLossPct: number;
  profitFactor: number;
  maxDrawdownPct: number;
  totalReturnPct: number;
  sharpeRatio: number;
}

export interface BagsBacktestResult {
  totalTokens: number;
  tokensWithData: number;
  strategyResults: BagsStrategyResult[];
  bestStrategy: BagsStrategyResult | null;
  graduationStats: {
    avgScoreWinners: number;
    avgScoreLosers: number;
    avgTimeToPeakMs: number;
    avgPeakMultiplier: number;
    medianLifespanHours: number;
  };
}

export interface BagsBacktestConfig {
  maxTokens?: number;
  minScore?: number;
  customSLRange?: number[];
  customTPRange?: number[];
  customTrailRange?: number[];
  customDelayRange?: number[];
  customScoreThresholds?: number[];
}

// ─── Constants ───

const BAGS_API_BASE = 'https://public-api-v2.bags.fm/api';
const DEXSCREENER_TOKENS = 'https://api.dexscreener.com/tokens/v1/solana';
const FETCH_TIMEOUT_MS = 8_000;
const CACHE_TTL_MS = 3_600_000; // 1 hour

// Default parameter grids
const DEFAULT_SL_RANGE = [5, 10, 15, 20, 25, 30, 40, 50];
const DEFAULT_TP_RANGE = [20, 30, 50, 75, 100, 150, 200, 300, 500];
const DEFAULT_TRAIL_RANGE = [0, 5, 8, 10, 15, 20, 25];
const DEFAULT_DELAY_RANGE = [0, 2, 5, 10, 15];
const DEFAULT_SCORE_THRESHOLDS = [0, 20, 30, 40, 50, 60, 70, 80];

// ─── Cache ───

export const backtestCache = new ServerCache<BagsBacktestResult>();
const CACHE_KEY = 'bags-backtest:latest';

// ─── Fetch Helpers ───

async function fetchWithTimeout(url: string, timeoutMs = FETCH_TIMEOUT_MS): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

// ─── Graduation Fetching ───

/**
 * Fetch bags.fm graduations with pagination and endpoint fallback.
 * Tries multiple API endpoints in order; uses the first that returns data.
 */
export async function fetchBagsGraduations(limit = 500): Promise<BagsGraduationRecord[]> {
  const endpoints = [
    `${BAGS_API_BASE}/graduations`,
    `${BAGS_API_BASE}/tokens/graduated`,
    `${BAGS_API_BASE}/events/graduations`,
  ];

  for (const base of endpoints) {
    try {
      const results: BagsGraduationRecord[] = [];
      let offset = 0;
      const pageSize = Math.min(limit, 500);

      while (results.length < limit) {
        const url = `${base}?limit=${pageSize}&offset=${offset}`;
        const res = await fetchWithTimeout(url);
        if (!res.ok) break;

        const data = await res.json();
        const items = Array.isArray(data)
          ? data
          : (data.graduations || data.data || data.tokens || []);

        if (items.length === 0) break;

        const mapped = items.map(normalizeGraduation);
        results.push(...mapped);
        offset += pageSize;

        // If we got fewer than pageSize, there are no more pages
        if (items.length < pageSize) break;
      }

      if (results.length > 0) {
        return results.slice(0, limit);
      }
    } catch {
      // Try next endpoint
      continue;
    }
  }

  return [];
}

function normalizeGraduation(g: any): BagsGraduationRecord {
  const gradTimeRaw = g.graduation_time || g.graduated_at || g.timestamp || Date.now() / 1000;
  // Normalize to ms — if it looks like seconds (< 1e12), multiply by 1000
  const graduationTime = gradTimeRaw < 1e12 ? gradTimeRaw * 1000 : gradTimeRaw;

  return {
    mint: g.mint || g.address || g.token_address || '',
    symbol: g.symbol || '',
    name: g.name || '',
    score: g.score || g.kr8tiv_score || 50,
    graduationTime,
    bondingCurveScore: g.bonding_curve_score || g.bondingCurveScore || 0,
    holderDistributionScore: g.holder_distribution_score || g.holderScore || 0,
    socialScore: g.social_score || g.socialScore || 0,
    marketCap: parseFloat(g.market_cap || g.marketCap || '0'),
    priceAtGraduation: parseFloat(g.price_usd || g.priceUsd || g.price || '0'),
    liquidity: parseFloat(g.liquidity || g.initial_liquidity || '0'),
  };
}

// ─── DexScreener Enrichment ───

/**
 * Enrich graduation records with current price data from DexScreener.
 * Processes tokens one at a time to avoid rate limits.
 * Gracefully handles failures (returns null fields for missing data).
 */
export async function enrichWithDexScreener(
  graduations: BagsGraduationRecord[],
): Promise<EnrichedGraduation[]> {
  const results: EnrichedGraduation[] = [];

  for (const grad of graduations) {
    try {
      const res = await fetchWithTimeout(`${DEXSCREENER_TOKENS}/${grad.mint}`);
      if (!res.ok) {
        results.push(makeEnrichedDefault(grad));
        continue;
      }

      const pairs: any[] = await res.json();
      if (!Array.isArray(pairs) || pairs.length === 0) {
        results.push(makeEnrichedDefault(grad));
        continue;
      }

      // Pick highest-liquidity pair
      const best = pairs.reduce((a: any, b: any) => {
        const liqA = parseFloat(a?.liquidity?.usd || '0');
        const liqB = parseFloat(b?.liquidity?.usd || '0');
        return liqB > liqA ? b : a;
      }, pairs[0]);

      const currentPrice = parseFloat(best.priceUsd || '0');
      const priceChange5m = best.priceChange?.m5 ?? null;
      const priceChange1h = best.priceChange?.h1 ?? null;
      const priceChange24h = best.priceChange?.h24 ?? null;
      const volume24h = parseFloat(best.volume?.h24 || '0') || null;

      // Estimate peak price from graduation price + max price change
      // DexScreener doesn't give us historical peak directly, so we estimate
      const peakMultiplier = estimatePeakMultiplier(priceChange5m, priceChange1h, priceChange24h, grad.priceAtGraduation, currentPrice);
      const peakPrice = grad.priceAtGraduation > 0
        ? grad.priceAtGraduation * peakMultiplier
        : currentPrice * 1.5; // Fallback estimate

      const timeToPeakMs = estimateTimeToPeak(priceChange5m, priceChange1h);

      results.push({
        ...grad,
        currentPrice,
        peakPrice,
        priceChange5m,
        priceChange1h,
        priceChange24h,
        volume24h,
        timeToPeakMs,
        peakMultiplier,
      });
    } catch {
      results.push(makeEnrichedDefault(grad));
    }
  }

  return results;
}

function makeEnrichedDefault(grad: BagsGraduationRecord): EnrichedGraduation {
  return {
    ...grad,
    currentPrice: null,
    peakPrice: null,
    priceChange5m: null,
    priceChange1h: null,
    priceChange24h: null,
    volume24h: null,
    timeToPeakMs: null,
    peakMultiplier: null,
  };
}

/**
 * Estimate peak price multiplier from available price change data.
 * This is an approximation since we don't have full historical OHLCV.
 */
function estimatePeakMultiplier(
  pc5m: number | null,
  pc1h: number | null,
  pc24h: number | null,
  gradPrice: number,
  currentPrice: number,
): number {
  // Use the highest observed price change as a proxy for peak
  const changes = [pc5m, pc1h, pc24h].filter((v): v is number => v !== null);
  if (changes.length === 0) {
    return gradPrice > 0 && currentPrice > 0 ? currentPrice / gradPrice : 1.5;
  }

  const maxChange = Math.max(...changes);
  // The max price change % represents approximately how high the token went
  // from some reference point. Use it as a multiplier estimate.
  const multiplier = 1 + (maxChange / 100);
  return Math.max(1.0, multiplier);
}

function estimateTimeToPeak(pc5m: number | null, pc1h: number | null): number | null {
  // If 5m change is the highest, peak was likely within first 5 mins
  if (pc5m !== null && pc1h !== null) {
    if (pc5m > pc1h) return 5 * 60 * 1000;    // 5 min
    return 30 * 60 * 1000;  // ~30 min
  }
  if (pc5m !== null) return 5 * 60 * 1000;
  if (pc1h !== null) return 30 * 60 * 1000;
  return null;
}

// ─── Trade Simulation ───

export interface SimulateTradeParams {
  entryPrice: number;
  peakPrice: number;
  currentPrice: number;
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  entryDelayMinutes?: number;
  priceChange5m?: number;
}

/**
 * Simulate a single bags.fm trade given entry conditions and exit parameters.
 *
 * Uses the graduation price as entry, peak price to check TP/trailing,
 * and current price to check SL. Since we don't have tick-by-tick data,
 * we use a simplified model:
 *
 * 1. Check if TP would have been hit (peak >= entry * (1 + TP%))
 * 2. Check if trailing stop would have triggered after peak
 * 3. Check if SL would have been hit (min price <= entry * (1 - SL%))
 * 4. If nothing hit, use current price as exit
 */
export function simulateBagsTrade(params: SimulateTradeParams): BagsTradeSimulation {
  const {
    entryPrice,
    peakPrice,
    currentPrice,
    stopLossPct,
    takeProfitPct,
    trailingStopPct,
    entryDelayMinutes = 0,
    priceChange5m = 0,
  } = params;

  // Apply entry delay — if delayed, entry price is adjusted by 5m price change
  let effectiveEntry = entryPrice;
  if (entryDelayMinutes > 0 && priceChange5m !== 0) {
    // Scale the 5m change proportionally to delay
    const delayFraction = Math.min(entryDelayMinutes / 5, 1);
    const priceAdjustment = 1 + (priceChange5m / 100) * delayFraction;
    effectiveEntry = entryPrice * priceAdjustment;
  }

  const tpPrice = effectiveEntry * (1 + takeProfitPct / 100);
  const slPrice = effectiveEntry * (1 - stopLossPct / 100);

  // 1. Check if TP hit (peak reached TP level)
  if (peakPrice >= tpPrice) {
    return {
      hit: 'tp',
      pnlPct: takeProfitPct,
      effectiveEntryPrice: effectiveEntry,
      exitPrice: tpPrice,
    };
  }

  // 2. Check trailing stop (peak was high but then dropped)
  if (trailingStopPct > 0 && peakPrice > effectiveEntry) {
    const trailExitPrice = peakPrice * (1 - trailingStopPct / 100);

    // Trailing stop triggers if: price went up, then fell trailingStopPct from peak
    // AND the trail exit is above the fixed SL price (otherwise SL gets hit first)
    if (trailExitPrice > slPrice && currentPrice <= trailExitPrice) {
      const trailPnl = ((trailExitPrice - effectiveEntry) / effectiveEntry) * 100;
      return {
        hit: 'trail',
        pnlPct: trailPnl,
        effectiveEntryPrice: effectiveEntry,
        exitPrice: trailExitPrice,
      };
    }
  }

  // 3. Check if SL hit (current or implied low reached SL)
  // If current price is below SL, or the token has dropped enough that SL would have been hit
  if (currentPrice <= slPrice) {
    return {
      hit: 'sl',
      pnlPct: -stopLossPct,
      effectiveEntryPrice: effectiveEntry,
      exitPrice: slPrice,
    };
  }

  // 4. No clear exit — use current price
  const openPnl = ((currentPrice - effectiveEntry) / effectiveEntry) * 100;
  return {
    hit: 'none',
    pnlPct: openPnl,
    effectiveEntryPrice: effectiveEntry,
    exitPrice: currentPrice,
  };
}

// ─── Backtest Engine ───

/**
 * Run the full bags.fm backtesting pipeline.
 *
 * 1. Fetch historical graduations
 * 2. Enrich with DexScreener price data
 * 3. Simulate trades across parameter grid
 * 4. Aggregate and rank results
 */
export async function runBagsBacktest(
  config: BagsBacktestConfig = {},
): Promise<BagsBacktestResult> {
  const {
    maxTokens = 200,
    customSLRange = DEFAULT_SL_RANGE,
    customTPRange = DEFAULT_TP_RANGE,
    customTrailRange = DEFAULT_TRAIL_RANGE,
    customDelayRange = DEFAULT_DELAY_RANGE,
    customScoreThresholds = DEFAULT_SCORE_THRESHOLDS,
  } = config;

  // 1. Fetch graduations
  const graduations = await fetchBagsGraduations(maxTokens);
  if (graduations.length === 0) {
    return emptyResult();
  }

  // 2. Enrich with price data
  const enriched = await enrichWithDexScreener(graduations);
  const withData = enriched.filter(e => e.currentPrice !== null && e.currentPrice > 0);

  if (withData.length === 0) {
    return {
      ...emptyResult(),
      totalTokens: graduations.length,
    };
  }

  // 3. Build strategy grid and simulate
  const strategyResults: BagsStrategyResult[] = [];

  // Test a reduced grid for performance: pick representative combos
  // Full grid would be 8 * 9 * 7 * 5 * 8 = 20,160 strategies
  // We test a smart subset: ~100-200 strategies
  const slRange = customSLRange.length > 4
    ? [customSLRange[0], customSLRange[2], customSLRange[4], customSLRange[customSLRange.length - 1]]
    : customSLRange;
  const tpRange = customTPRange.length > 4
    ? [customTPRange[0], customTPRange[2], customTPRange[4], customTPRange[customTPRange.length - 1]]
    : customTPRange;
  const trailRange = customTrailRange.length > 3
    ? [customTrailRange[0], customTrailRange[2], customTrailRange[customTrailRange.length - 1]]
    : customTrailRange;
  const delayRange = customDelayRange.length > 3
    ? [customDelayRange[0], customDelayRange[1], customDelayRange[customDelayRange.length - 1]]
    : customDelayRange;

  for (const sl of slRange) {
    for (const tp of tpRange) {
      // Skip invalid combos (SL should be < TP)
      if (sl >= tp) continue;

      for (const trail of trailRange) {
        for (const delay of delayRange) {
          for (const minScore of customScoreThresholds) {
            const id = `sl${sl}_tp${tp}_trail${trail}_delay${delay}_score${minScore}`;
            const result = simulateStrategyAcrossTokens(
              withData, { sl, tp, trail, delay, minScore },
            );

            if (result.trades >= 1) {
              strategyResults.push({
                id,
                params: {
                  stopLossPct: sl,
                  takeProfitPct: tp,
                  trailingStopPct: trail,
                  entryDelayMinutes: delay,
                  minScore,
                },
                ...result,
              });
            }
          }
        }
      }
    }
  }

  // 4. Sort by Sharpe ratio
  strategyResults.sort((a, b) => b.sharpeRatio - a.sharpeRatio);

  // 5. Compute graduation stats
  const graduationStats = computeGraduationStats(withData);

  const bestStrategy = strategyResults.length > 0 ? strategyResults[0] : null;

  return {
    totalTokens: graduations.length,
    tokensWithData: withData.length,
    strategyResults,
    bestStrategy,
    graduationStats,
  };
}

interface SimParams {
  sl: number;
  tp: number;
  trail: number;
  delay: number;
  minScore: number;
}

function simulateStrategyAcrossTokens(
  tokens: EnrichedGraduation[],
  params: SimParams,
): Omit<BagsStrategyResult, 'id' | 'params'> {
  const filtered = tokens.filter(t => t.score >= params.minScore);

  const trades: BagsTradeSimulation[] = [];
  for (const token of filtered) {
    if (!token.currentPrice || !token.peakPrice || token.priceAtGraduation <= 0) continue;

    const sim = simulateBagsTrade({
      entryPrice: token.priceAtGraduation,
      peakPrice: token.peakPrice,
      currentPrice: token.currentPrice,
      stopLossPct: params.sl,
      takeProfitPct: params.tp,
      trailingStopPct: params.trail,
      entryDelayMinutes: params.delay,
      priceChange5m: token.priceChange5m ?? 0,
    });

    trades.push(sim);
  }

  if (trades.length === 0) {
    return {
      trades: 0,
      wins: 0,
      losses: 0,
      winRate: 0,
      avgProfitPct: 0,
      avgLossPct: 0,
      profitFactor: 0,
      maxDrawdownPct: 0,
      totalReturnPct: 0,
      sharpeRatio: 0,
    };
  }

  const wins = trades.filter(t => t.pnlPct > 0);
  const losses = trades.filter(t => t.pnlPct <= 0);

  const totalProfit = wins.reduce((s, t) => s + t.pnlPct, 0);
  const totalLoss = Math.abs(losses.reduce((s, t) => s + t.pnlPct, 0));

  const avgProfitPct = wins.length > 0 ? totalProfit / wins.length : 0;
  const avgLossPct = losses.length > 0 ? -(totalLoss / losses.length) : 0;
  const rawPF = totalLoss > 0 ? totalProfit / totalLoss : (totalProfit > 0 ? 999 : 0);
  const profitFactor = Math.min(rawPF, 999);
  const totalReturnPct = trades.reduce((s, t) => s + t.pnlPct, 0);

  // Max drawdown (equity-based, bounded 0-100%)
  let equity = 100;
  let peakEquity = 100;
  let maxDD = 0;
  for (const trade of trades) {
    equity *= (1 + trade.pnlPct / 100);
    equity = Math.max(equity, 0); // Equity can't go negative
    peakEquity = Math.max(peakEquity, equity);
    const dd = peakEquity > 0 ? ((peakEquity - equity) / peakEquity) * 100 : 0;
    maxDD = Math.max(maxDD, dd);
  }

  // Sharpe ratio (simplified: mean return / std dev)
  const returns = trades.map(t => t.pnlPct);
  const meanReturn = returns.reduce((s, r) => s + r, 0) / returns.length;
  const variance = returns.length > 1
    ? returns.reduce((s, r) => s + (r - meanReturn) ** 2, 0) / (returns.length - 1)
    : 0;
  const stdReturn = Math.sqrt(variance);
  const MIN_STD = 0.001;
  const effectiveStd = Math.max(stdReturn, MIN_STD);
  const rawSharpe = effectiveStd > MIN_STD ? meanReturn / effectiveStd : 0;
  const sharpeRatio = Math.max(-10, Math.min(10, rawSharpe));

  return {
    trades: trades.length,
    wins: wins.length,
    losses: losses.length,
    winRate: wins.length / trades.length,
    avgProfitPct,
    avgLossPct,
    profitFactor,
    maxDrawdownPct: maxDD,
    totalReturnPct,
    sharpeRatio,
  };
}

function computeGraduationStats(tokens: EnrichedGraduation[]): BagsBacktestResult['graduationStats'] {
  const winners = tokens.filter(t =>
    t.currentPrice !== null && t.priceAtGraduation > 0 && t.currentPrice > t.priceAtGraduation
  );
  const losers = tokens.filter(t =>
    t.currentPrice !== null && t.priceAtGraduation > 0 && t.currentPrice <= t.priceAtGraduation
  );

  const avgScoreWinners = winners.length > 0
    ? winners.reduce((s, t) => s + t.score, 0) / winners.length
    : 0;
  const avgScoreLosers = losers.length > 0
    ? losers.reduce((s, t) => s + t.score, 0) / losers.length
    : 0;

  const timeToPeaks = tokens
    .map(t => t.timeToPeakMs)
    .filter((v): v is number => v !== null);
  const avgTimeToPeakMs = timeToPeaks.length > 0
    ? timeToPeaks.reduce((s, t) => s + t, 0) / timeToPeaks.length
    : 0;

  const multipliers = tokens
    .map(t => t.peakMultiplier)
    .filter((v): v is number => v !== null && v > 0);
  const avgPeakMultiplier = multipliers.length > 0
    ? multipliers.reduce((s, m) => s + m, 0) / multipliers.length
    : 1;

  // Median lifespan in hours — use time since graduation
  const lifespans = tokens
    .map(t => (Date.now() - t.graduationTime) / (1000 * 60 * 60))
    .sort((a, b) => a - b);
  const medianLifespanHours = lifespans.length > 0
    ? lifespans[Math.floor(lifespans.length / 2)]
    : 0;

  return {
    avgScoreWinners,
    avgScoreLosers,
    avgTimeToPeakMs,
    avgPeakMultiplier,
    medianLifespanHours,
  };
}

function emptyResult(): BagsBacktestResult {
  return {
    totalTokens: 0,
    tokensWithData: 0,
    strategyResults: [],
    bestStrategy: null,
    graduationStats: {
      avgScoreWinners: 0,
      avgScoreLosers: 0,
      avgTimeToPeakMs: 0,
      avgPeakMultiplier: 0,
      medianLifespanHours: 0,
    },
  };
}
