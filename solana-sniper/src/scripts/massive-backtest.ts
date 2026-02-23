#!/usr/bin/env node
/**
 * Massive Backtest Runner
 *
 * Tests ALL 9 strategy presets across multiple token categories and
 * generates a comprehensive report with rankings and recommendations.
 *
 * Usage: npx tsx src/scripts/massive-backtest.ts
 */
import {
  runEnhancedBacktest,
  fetchBacktestData,
  type EnhancedBacktestConfig,
  type EnhancedBacktestResult,
  type PumpFunHistoricalToken,
} from '../analysis/historical-data.js';
import { computeFitnessScore } from '../analysis/self-improver.js';
import { getMacroSnapshot } from '../analysis/macro-correlator.js';
import { getHyperliquidCorrelations } from '../analysis/hyperliquid-data.js';
import { createModuleLogger } from '../utils/logger.js';
import fs from 'fs';
import path from 'path';

const log = createModuleLogger('massive-backtest');

// ─── Types ───────────────────────────────────────────────────

export interface StrategyPreset {
  name: string;
  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  minLiquidityUsd: number;
  safetyScoreMin: number;
  // Optional overrides
  ageCategory?: EnhancedBacktestConfig['ageCategory'];
  requireVolumeSurge?: boolean;
  minVolumeSurgeRatio?: number;
  adaptiveExits?: boolean;
  assetType?: EnhancedBacktestConfig['assetType'];
  sourceFilter?: 'all' | 'pumpfun' | 'raydium' | 'pumpswap';
  excludeAge?: Array<'fresh' | 'young' | 'established' | 'veteran'>;
  allowedEntryHoursUtc?: number[];
}

export interface StrategyResultEntry {
  name: string;
  winRate: number;
  totalTrades: number;
  pnlUsd: number;
  pnlPct: number;
  sharpe: number;
  profitFactor: number;
  maxDrawdown: number;
  avgWin: number;
  avgLoss: number;
  bestTrade: { symbol: string; pnlPct: number };
  worstTrade: { symbol: string; pnlPct: number };
  rugsAvoided: number;
  rugsHit: number;
  fitnessScore: number;
  avgHoldTime: number;
}

export interface CrossCategoryEntry {
  strategy: string;
  category: string;
  winRate: number;
  trades: number;
  pnlUsd: number;
  sharpe: number;
}

export interface TimeOfDayHourlyStat {
  hour: number;
  trades: number;
  winRate: number;
  avgPnlPct: number;
}

export interface TimeOfDayAnalysis {
  hourlyStats: TimeOfDayHourlyStat[];
  bestHours: number[];
  worstHours: number[];
}

export interface SourceBreakdownEntry {
  source: string;
  trades: number;
  winRate: number;
  avgPnlPct: number;
}

export interface MassiveBacktestReport {
  runAt: string;
  macroRegime: string;
  totalTokensFetched: number;
  tokenBreakdown: {
    bySource: Record<string, number>;
    byAge: Record<string, number>;
  };
  strategyResults: StrategyResultEntry[];
  crossCategoryResults: CrossCategoryEntry[];
  rankings: {
    byWinRate: string[];
    byPnl: string[];
    bySharpe: string[];
    byFitness: string[];
  };
  recommendations: string[];
  hyperliquidCorrelations?: {
    solBtc: number;
    solEth: number;
    btcVol: number;
    solVol: number;
  };
  timeOfDayAnalysis?: TimeOfDayAnalysis;
  sourceBreakdown?: SourceBreakdownEntry[];
}

// ─── Strategy Presets ────────────────────────────────────────

export const STRATEGY_PRESETS: StrategyPreset[] = [
  {
    name: 'TRAIL_8',
    stopLossPct: 25,
    takeProfitPct: 100,
    trailingStopPct: 8,
    minLiquidityUsd: 50000,
    safetyScoreMin: 0.55,
  },
  {
    name: 'MOMENTUM',
    stopLossPct: 30,
    takeProfitPct: 150,
    trailingStopPct: 12,
    minLiquidityUsd: 25000,
    safetyScoreMin: 0.50,
  },
  {
    name: 'MICRO_CAP_SURGE',
    stopLossPct: 45,
    takeProfitPct: 250,
    trailingStopPct: 20,
    minLiquidityUsd: 3000,
    safetyScoreMin: 0.30,
    requireVolumeSurge: true,
    minVolumeSurgeRatio: 3.0,
    ageCategory: 'fresh' as const,
    adaptiveExits: false,
  },
  {
    name: 'SCALP',
    stopLossPct: 10,
    takeProfitPct: 30,
    trailingStopPct: 5,
    minLiquidityUsd: 50000,
    safetyScoreMin: 0.50,
  },
  {
    name: 'DEGEN',
    stopLossPct: 40,
    takeProfitPct: 200,
    trailingStopPct: 15,
    minLiquidityUsd: 10000,
    safetyScoreMin: 0.40,
  },
  {
    name: 'PUMP_FRESH_TIGHT',
    stopLossPct: 20,
    takeProfitPct: 80,
    trailingStopPct: 8,
    minLiquidityUsd: 5000,
    safetyScoreMin: 0.40,
    ageCategory: 'fresh' as const,
    sourceFilter: 'pumpswap' as const,
    adaptiveExits: false,
  },
  {
    name: 'VETERAN_SURGE',
    stopLossPct: 8,
    takeProfitPct: 20,
    trailingStopPct: 8,
    minLiquidityUsd: 50000,
    safetyScoreMin: 0.50,
    ageCategory: 'veteran',
    requireVolumeSurge: true,
    minVolumeSurgeRatio: 2.0,
    adaptiveExits: false,  // Use fixed params, adaptive is too loose
  },
  {
    name: 'SMART_FLOW',
    stopLossPct: 18,
    takeProfitPct: 70,
    trailingStopPct: 10,
    minLiquidityUsd: 50000,
    safetyScoreMin: 0.55,
    ageCategory: 'established',
    adaptiveExits: true,
  },
  {
    name: 'WIDE_NET',
    stopLossPct: 50,
    takeProfitPct: 300,
    trailingStopPct: 25,
    minLiquidityUsd: 1000,
    safetyScoreMin: 0.20,
    adaptiveExits: false,
  },
  // ─── DATA-DRIVEN STRATEGIES (based on massive backtest v1 findings) ──────
  {
    name: 'SURGE_HUNTER',
    stopLossPct: 35,
    takeProfitPct: 150,
    trailingStopPct: 15,
    minLiquidityUsd: 5000,
    safetyScoreMin: 0.40,
    requireVolumeSurge: true,
    minVolumeSurgeRatio: 2.5,
    adaptiveExits: false,  // Use the wide exits, not adaptive
  },
  {
    name: 'PUMPSWAP_ALPHA',
    stopLossPct: 30,
    takeProfitPct: 120,
    trailingStopPct: 12,
    minLiquidityUsd: 10000,
    safetyScoreMin: 0.45,
    adaptiveExits: false,
    sourceFilter: 'pumpswap',
  },
  {
    name: 'ESTABLISHED_MOMENTUM',
    stopLossPct: 20,
    takeProfitPct: 75,
    trailingStopPct: 10,
    minLiquidityUsd: 25000,
    safetyScoreMin: 0.50,
    ageCategory: 'established',
    adaptiveExits: true,
  },
  {
    name: 'FRESH_DEGEN',
    stopLossPct: 40,
    takeProfitPct: 200,
    trailingStopPct: 18,
    minLiquidityUsd: 3000,
    safetyScoreMin: 0.35,
    ageCategory: 'fresh',
    adaptiveExits: false,
  },
  // ─── GENETIC OPTIMIZER CHAMPION (83.3% WR, fitness 0.913) ──────
  {
    name: 'GENETIC_BEST',
    stopLossPct: 35,
    takeProfitPct: 200,
    trailingStopPct: 12,
    minLiquidityUsd: 3000,
    safetyScoreMin: 0.43,
    ageCategory: 'fresh',
    adaptiveExits: false,
  },
  {
    name: 'NO_VETERANS',
    stopLossPct: 30,
    takeProfitPct: 150,
    trailingStopPct: 12,
    minLiquidityUsd: 15000,
    safetyScoreMin: 0.45,
    adaptiveExits: true,
    excludeAge: ['veteran'],
  },
  // ─── GENETIC OPTIMIZER V2 CHAMPION (71.1% WR, $51.20 PnL, enhanced sim) ──────
  {
    name: 'GENETIC_V2',
    stopLossPct: 45,
    takeProfitPct: 207,
    trailingStopPct: 10,
    minLiquidityUsd: 5000,
    safetyScoreMin: 0.40,
    requireVolumeSurge: true,
    minVolumeSurgeRatio: 2.5,
    assetType: 'memecoin' as const,
    adaptiveExits: false,
  },
  // ─── TIME-FILTERED STRATEGIES (based on v4 ToD analysis) ──────
  {
    name: 'PUMP_FRESH_PEAK_HOURS',
    stopLossPct: 20,
    takeProfitPct: 80,
    trailingStopPct: 8,
    minLiquidityUsd: 5000,
    safetyScoreMin: 0.40,
    ageCategory: 'fresh' as const,
    sourceFilter: 'pumpswap' as const,
    adaptiveExits: false,
    // Peak hours from v4 analysis: UTC 12-18 (US market hours overlap with crypto activity)
    allowedEntryHoursUtc: [12, 13, 14, 15, 16, 17, 18],
  },
  {
    name: 'SURGE_NIGHT_OWL',
    stopLossPct: 35,
    takeProfitPct: 150,
    trailingStopPct: 15,
    minLiquidityUsd: 5000,
    safetyScoreMin: 0.40,
    requireVolumeSurge: true,
    minVolumeSurgeRatio: 2.5,
    adaptiveExits: false,
    // Asian session hours (many pumps happen during Asian prime time)
    allowedEntryHoursUtc: [0, 1, 2, 3, 4, 5, 6, 7, 8],
  },
  // ─── ASSET CLASS STRATEGIES (xStocks, PreStocks, Indexes, Commodities) ──────
  {
    name: 'XSTOCK_MOMENTUM',
    stopLossPct: 3,
    takeProfitPct: 8,
    trailingStopPct: 2,
    minLiquidityUsd: 1000,
    safetyScoreMin: 0.20,
    assetType: 'xstock' as const,
    adaptiveExits: false,
    // US market hours: 9:30am-4pm ET = UTC 14:30-21:00
    allowedEntryHoursUtc: [14, 15, 16, 17, 18, 19, 20],
  },
  {
    name: 'PRESTOCK_SPECULATIVE',
    stopLossPct: 15,
    takeProfitPct: 50,
    trailingStopPct: 8,
    minLiquidityUsd: 500,
    safetyScoreMin: 0.15,
    assetType: 'prestock' as const,
    adaptiveExits: false,
    // No hour filter — pre-IPO tokens trade 24/7 on crypto rails
  },
  {
    name: 'INDEX_MEAN_REVERT',
    stopLossPct: 2,
    takeProfitPct: 5,
    trailingStopPct: 1.5,
    minLiquidityUsd: 1000,
    safetyScoreMin: 0.20,
    assetType: 'index' as const,
    adaptiveExits: false,
    allowedEntryHoursUtc: [14, 15, 16, 17, 18, 19, 20],
  },
  {
    name: 'COMMODITY_TREND',
    stopLossPct: 4,
    takeProfitPct: 12,
    trailingStopPct: 3,
    minLiquidityUsd: 500,
    safetyScoreMin: 0.20,
    assetType: 'commodity' as const,
    adaptiveExits: false,
  },
];

// ─── Helper Functions (exported for testing) ─────────────────

/**
 * Build a complete EnhancedBacktestConfig from a strategy preset,
 * filling in defaults for any missing fields.
 */
export function buildFullConfig(preset: StrategyPreset): EnhancedBacktestConfig {
  return {
    initialCapitalUsd: 50,
    maxPositionUsd: 2.50,
    stopLossPct: preset.stopLossPct,
    takeProfitPct: preset.takeProfitPct,
    trailingStopPct: preset.trailingStopPct,
    minLiquidityUsd: preset.minLiquidityUsd,
    minBuySellRatio: 1.0,
    maxEntryDelayMs: 300000,
    safetyScoreMin: preset.safetyScoreMin,
    maxConcurrentPositions: 5,
    partialExitPct: 50,
    source: preset.sourceFilter ?? 'all',
    // Enhanced defaults, overridden by preset if provided
    minTokenAgeHours: 0,
    maxTokenAgeHours: 0,
    ageCategory: preset.ageCategory ?? 'all',
    requireVolumeSurge: preset.requireVolumeSurge ?? false,
    minVolumeSurgeRatio: preset.minVolumeSurgeRatio ?? 3,
    assetType: preset.assetType ?? 'all',
    adaptiveExits: preset.adaptiveExits ?? false,
    useOhlcv: false, // disabled by default for speed (50+ API calls, ~2 min per run)
    allowedEntryHoursUtc: preset.allowedEntryHoursUtc,
    profitLadder: undefined, // use DEFAULT_PROFIT_LADDER from historical-data.ts
  };
}

/**
 * Extract a StrategyResultEntry from a raw EnhancedBacktestResult.
 */
export function extractStrategyResult(
  name: string,
  result: EnhancedBacktestResult,
  fitnessScore: number,
): StrategyResultEntry {
  return {
    name,
    winRate: result.winRate,
    totalTrades: result.totalTrades,
    pnlUsd: result.totalPnlUsd,
    pnlPct: result.totalPnlPct,
    sharpe: result.sharpeRatio,
    profitFactor: result.profitFactor,
    maxDrawdown: result.maxDrawdownPct,
    avgWin: result.avgWinPct,
    avgLoss: result.avgLossPct,
    bestTrade: result.bestTrade,
    worstTrade: result.worstTrade,
    rugsAvoided: result.rugsAvoided,
    rugsHit: result.rugsHit,
    fitnessScore,
    avgHoldTime: result.avgHoldTimeMin,
  };
}

/**
 * Compute rankings across multiple dimensions.
 */
export function computeRankings(
  entries: StrategyResultEntry[],
): MassiveBacktestReport['rankings'] {
  if (entries.length === 0) {
    return { byWinRate: [], byPnl: [], bySharpe: [], byFitness: [] };
  }

  const byWinRate = [...entries].sort((a, b) => b.winRate - a.winRate).map(e => e.name);
  const byPnl = [...entries].sort((a, b) => b.pnlUsd - a.pnlUsd).map(e => e.name);
  const bySharpe = [...entries].sort((a, b) => b.sharpe - a.sharpe).map(e => e.name);
  const byFitness = [...entries].sort((a, b) => b.fitnessScore - a.fitnessScore).map(e => e.name);

  return { byWinRate, byPnl, bySharpe, byFitness };
}

/**
 * Generate plain-text recommendations based on results.
 */
export function generateRecommendations(
  entries: StrategyResultEntry[],
  crossCategory: CrossCategoryEntry[],
): string[] {
  const recs: string[] = [];

  if (entries.length === 0) return recs;

  // Filter to strategies that actually traded
  const traded = entries.filter(e => e.totalTrades > 0);

  if (traded.length === 0) {
    recs.push('No strategies produced any trades. Consider relaxing filter parameters or fetching more data.');
    return recs;
  }

  // Highest win rate
  const bestWR = [...traded].sort((a, b) => b.winRate - a.winRate)[0];
  recs.push(
    `${bestWR.name} had the highest win rate at ${(bestWR.winRate * 100).toFixed(1)}% with ${bestWR.totalTrades} trades.`,
  );

  // Best risk-adjusted returns (Sharpe)
  const bestSharpe = [...traded].sort((a, b) => b.sharpe - a.sharpe)[0];
  if (bestSharpe.name !== bestWR.name) {
    recs.push(
      `${bestSharpe.name} had the best risk-adjusted returns (Sharpe: ${bestSharpe.sharpe.toFixed(2)}).`,
    );
  }

  // Most profitable
  const bestPnl = [...traded].sort((a, b) => b.pnlUsd - a.pnlUsd)[0];
  if (bestPnl.name !== bestWR.name && bestPnl.pnlUsd > 0) {
    recs.push(
      `${bestPnl.name} was the most profitable at $${bestPnl.pnlUsd.toFixed(2)} USD (${bestPnl.pnlPct.toFixed(1)}%).`,
    );
  }

  // Best fitness score
  const bestFit = [...traded].sort((a, b) => b.fitnessScore - a.fitnessScore)[0];
  if (bestFit.name !== bestWR.name && bestFit.name !== bestSharpe.name) {
    recs.push(
      `${bestFit.name} had the highest composite fitness score (${bestFit.fitnessScore.toFixed(3)}).`,
    );
  }

  // Best rug avoidance
  const bestRugAvoid = [...traded].sort((a, b) => {
    const ratioA = a.rugsAvoided / Math.max(1, a.rugsAvoided + a.rugsHit);
    const ratioB = b.rugsAvoided / Math.max(1, b.rugsAvoided + b.rugsHit);
    return ratioB - ratioA;
  })[0];
  if (bestRugAvoid.rugsAvoided > 0) {
    recs.push(
      `${bestRugAvoid.name} had the best rug avoidance: ${bestRugAvoid.rugsAvoided} avoided, ${bestRugAvoid.rugsHit} hit.`,
    );
  }

  // Lowest drawdown among profitable strategies
  const profitable = traded.filter(e => e.pnlUsd > 0);
  if (profitable.length > 0) {
    const lowestDD = [...profitable].sort((a, b) => a.maxDrawdown - b.maxDrawdown)[0];
    recs.push(
      `${lowestDD.name} had the lowest drawdown among profitable strategies at ${lowestDD.maxDrawdown.toFixed(1)}%.`,
    );
  }

  // Strategies that lost money
  const losers = traded.filter(e => e.pnlUsd < 0);
  if (losers.length > 0) {
    const worstNames = losers.map(l => l.name).join(', ');
    recs.push(
      `Strategies that lost money: ${worstNames}. Consider disabling or adjusting these.`,
    );
  }

  // Cross-category insights
  if (crossCategory.length > 0) {
    // Compare veteran vs fresh performance
    const veteranResults = crossCategory.filter(c => c.category === 'veteran' && c.trades > 0);
    const freshResults = crossCategory.filter(c => c.category === 'fresh' && c.trades > 0);

    if (veteranResults.length > 0 && freshResults.length > 0) {
      const avgVetWR = veteranResults.reduce((s, r) => s + r.winRate, 0) / veteranResults.length;
      const avgFreshWR = freshResults.reduce((s, r) => s + r.winRate, 0) / freshResults.length;
      const diff = ((avgVetWR - avgFreshWR) * 100).toFixed(1);
      if (avgVetWR > avgFreshWR) {
        recs.push(`Veteran tokens outperformed fresh tokens by ${diff}% average win rate.`);
      } else {
        recs.push(`Fresh tokens outperformed veteran tokens by ${(parseFloat(diff) * -1).toFixed(1)}% average win rate.`);
      }
    }

    // Volume surge insight
    const surgeResults = crossCategory.filter(c => c.category === 'volume_surge' && c.trades > 0);
    if (surgeResults.length > 0) {
      const avgSurgeWR = surgeResults.reduce((s, r) => s + r.winRate, 0) / surgeResults.length;
      const overallAvgWR = traded.reduce((s, r) => s + r.winRate, 0) / traded.length;
      const surgeAdv = ((avgSurgeWR - overallAvgWR) * 100).toFixed(1);
      if (avgSurgeWR > overallAvgWR) {
        recs.push(`Volume surge tokens had ${surgeAdv}% higher win rate than the overall average.`);
      }
    }

    // Best category for top strategy
    const topStrategy = bestFit.name;
    const topStratCross = crossCategory.filter(c => c.strategy === topStrategy && c.trades > 0);
    if (topStratCross.length > 1) {
      const bestCat = [...topStratCross].sort((a, b) => b.winRate - a.winRate)[0];
      recs.push(
        `${topStrategy} performs best on '${bestCat.category}' tokens (${(bestCat.winRate * 100).toFixed(1)}% WR, ${bestCat.trades} trades).`,
      );
    }

    // Source comparison
    const sourceResults = crossCategory.filter(c =>
      ['pumpfun', 'raydium', 'pumpswap'].includes(c.category) && c.trades > 0,
    );
    if (sourceResults.length > 0) {
      const bestSource = [...sourceResults].sort((a, b) => b.winRate - a.winRate)[0];
      recs.push(
        `Best source: '${bestSource.category}' (${(bestSource.winRate * 100).toFixed(1)}% WR across ${bestSource.trades} trades with ${bestSource.strategy}).`,
      );
    }
  }

  return recs;
}

/**
 * Analyze trades grouped by UTC hour of token creation time.
 * Identifies optimal entry windows based on historical performance.
 */
export function analyzeTimeOfDay(
  result: EnhancedBacktestResult,
  tokens: PumpFunHistoricalToken[],
): TimeOfDayAnalysis {
  if (!result.trades || result.trades.length === 0) {
    return { hourlyStats: [], bestHours: [], worstHours: [] };
  }

  // Build a lookup map: symbol -> createdAt (unix seconds)
  const symbolToCreatedAt = new Map<string, number>();
  for (const token of tokens) {
    symbolToCreatedAt.set(token.symbol, token.createdAt);
  }

  // Group trades by UTC hour of token creation
  const hourBuckets = new Map<number, { pnlPcts: number[]; wins: number }>();

  for (const trade of result.trades) {
    const createdAt = symbolToCreatedAt.get(trade.symbol);
    if (createdAt === undefined) continue;

    const utcHour = new Date(createdAt * 1000).getUTCHours();

    if (!hourBuckets.has(utcHour)) {
      hourBuckets.set(utcHour, { pnlPcts: [], wins: 0 });
    }

    const bucket = hourBuckets.get(utcHour)!;
    bucket.pnlPcts.push(trade.pnlPct);
    if (trade.pnlPct > 0) {
      bucket.wins += 1;
    }
  }

  // Convert buckets to hourly stats
  const hourlyStats: TimeOfDayHourlyStat[] = [];
  for (const [hour, bucket] of hourBuckets.entries()) {
    const trades = bucket.pnlPcts.length;
    const winRate = trades > 0 ? bucket.wins / trades : 0;
    const avgPnlPct = trades > 0
      ? bucket.pnlPcts.reduce((sum, p) => sum + p, 0) / trades
      : 0;

    hourlyStats.push({ hour, trades, winRate, avgPnlPct });
  }

  // Sort by hour for consistent output
  hourlyStats.sort((a, b) => a.hour - b.hour);

  // Determine best and worst hours (need at least 1 trade)
  const withTrades = hourlyStats.filter(s => s.trades > 0);

  if (withTrades.length === 0) {
    return { hourlyStats, bestHours: [], worstHours: [] };
  }

  // Sort by avgPnlPct descending to find best/worst
  const sortedByPnl = [...withTrades].sort((a, b) => b.avgPnlPct - a.avgPnlPct);

  // Best hours: top quartile or at least top 1
  const bestCount = Math.max(1, Math.floor(sortedByPnl.length / 4));
  const bestHours = sortedByPnl.slice(0, bestCount)
    .filter(s => s.avgPnlPct > 0)
    .map(s => s.hour);

  // Worst hours: bottom quartile or at least bottom 1
  const worstCount = Math.max(1, Math.floor(sortedByPnl.length / 4));
  const worstHours = sortedByPnl.slice(-worstCount)
    .filter(s => s.avgPnlPct < 0)
    .map(s => s.hour);

  return { hourlyStats, bestHours, worstHours };
}

/**
 * Analyze trades grouped by token source (pumpfun, raydium, pumpswap).
 */
export function analyzeSourceBreakdown(
  result: EnhancedBacktestResult,
): SourceBreakdownEntry[] {
  if (!result.trades || result.trades.length === 0) {
    return [];
  }

  const sourceBuckets = new Map<string, { pnlPcts: number[]; wins: number }>();

  for (const trade of result.trades) {
    const source = trade.source || 'unknown';

    if (!sourceBuckets.has(source)) {
      sourceBuckets.set(source, { pnlPcts: [], wins: 0 });
    }

    const bucket = sourceBuckets.get(source)!;
    bucket.pnlPcts.push(trade.pnlPct);
    if (trade.pnlPct > 0) {
      bucket.wins += 1;
    }
  }

  const entries: SourceBreakdownEntry[] = [];
  for (const [source, bucket] of sourceBuckets.entries()) {
    const trades = bucket.pnlPcts.length;
    const winRate = trades > 0 ? bucket.wins / trades : 0;
    const avgPnlPct = trades > 0
      ? bucket.pnlPcts.reduce((sum, p) => sum + p, 0) / trades
      : 0;

    entries.push({ source, trades, winRate, avgPnlPct });
  }

  // Sort by trade count descending
  entries.sort((a, b) => b.trades - a.trades);

  return entries;
}

// ─── Main execution ──────────────────────────────────────────

async function main(): Promise<void> {
  const startTime = Date.now();
  log.info('='.repeat(70));
  log.info('  MASSIVE BACKTEST RUNNER  -  Testing ALL 9 Strategy Presets');
  log.info('='.repeat(70));
  log.info(`Started at: ${new Date().toISOString()}`);
  log.info(`Strategies: ${STRATEGY_PRESETS.map(p => p.name).join(', ')}`);

  const winningDir = path.resolve(process.cwd(), 'winning');
  if (!fs.existsSync(winningDir)) fs.mkdirSync(winningDir, { recursive: true });

  // ─── Phase 1: Data Collection ─────────────────────────────
  log.info('\n--- PHASE 1: DATA COLLECTION ---');

  let cachedData: PumpFunHistoricalToken[];
  try {
    log.info('Fetching 5000+ tokens (deep fetch mode)...');
    cachedData = await fetchBacktestData(5000, true);
    log.info(`Fetched ${cachedData.length} tokens.`);
  } catch (err) {
    log.error('Failed to fetch backtest data, attempting without deep fetch', {
      error: (err as Error).message,
    });
    cachedData = await fetchBacktestData(1000, false);
    log.info(`Fetched ${cachedData.length} tokens (fallback mode).`);
  }

  // Token breakdown
  const bySource: Record<string, number> = {};
  const byAge: Record<string, number> = {};
  for (const t of cachedData) {
    bySource[t.source] = (bySource[t.source] ?? 0) + 1;
    byAge[t.ageCategory] = (byAge[t.ageCategory] ?? 0) + 1;
  }
  log.info('Token breakdown by source:', bySource);
  log.info('Token breakdown by age:', byAge);
  log.info(`xStocks: ${cachedData.filter(t => t.isXStock).length}`);
  log.info(`Volume surges: ${cachedData.filter(t => t.isVolumeSurge).length}`);

  // Macro snapshot (optional)
  let macroRegime = 'unknown';
  try {
    const macro = await getMacroSnapshot();
    macroRegime = macro.regime;
    log.info(`Macro regime: ${macro.regime}, BTC trend: ${macro.btcTrend}, meme multiplier: ${macro.memeExposureMultiplier.toFixed(2)}`);
  } catch (err) {
    log.warn('Macro snapshot unavailable', { error: (err as Error).message });
  }

  // Hyperliquid correlations (optional)
  let hlCorrelations: MassiveBacktestReport['hyperliquidCorrelations'] | undefined;
  try {
    const hl = await getHyperliquidCorrelations();
    hlCorrelations = {
      solBtc: hl.solBtcCorrelation,
      solEth: hl.solEthCorrelation,
      btcVol: hl.btcVolatility,
      solVol: hl.solVolatility,
    };
    log.info('Hyperliquid correlations:', {
      solBtc: hl.solBtcCorrelation.toFixed(3),
      solEth: hl.solEthCorrelation.toFixed(3),
      btcVol: hl.btcVolatility.toFixed(1) + '%',
      solVol: hl.solVolatility.toFixed(1) + '%',
    });
  } catch (err) {
    log.warn('Hyperliquid correlations unavailable', { error: (err as Error).message });
  }

  // ─── Phase 2: Run ALL Strategies ──────────────────────────
  log.info(`\n--- PHASE 2: RUNNING ALL ${STRATEGY_PRESETS.length} STRATEGIES ---`);

  const strategyResults: StrategyResultEntry[] = [];
  const rawResults: Map<string, EnhancedBacktestResult> = new Map();

  for (const preset of STRATEGY_PRESETS) {
    log.info(`\nRunning ${preset.name}...`);
    try {
      const config = buildFullConfig(preset);

      // Filter out excluded age categories if specified
      let strategyData = cachedData;
      if (preset.excludeAge && preset.excludeAge.length > 0) {
        strategyData = cachedData.filter(t => !preset.excludeAge!.includes(t.ageCategory));
        log.info(`  Filtered out age categories [${preset.excludeAge.join(', ')}]: ${cachedData.length} -> ${strategyData.length} tokens`);
      }

      const result = await runEnhancedBacktest(config, strategyData);
      const fitness = computeFitnessScore(result);
      const entry = extractStrategyResult(preset.name, result, fitness);

      strategyResults.push(entry);
      rawResults.set(preset.name, result);

      log.info(`  ${preset.name}: WR=${(entry.winRate * 100).toFixed(1)}%, PnL=$${entry.pnlUsd.toFixed(2)}, Sharpe=${entry.sharpe.toFixed(2)}, Trades=${entry.totalTrades}, Fitness=${fitness.toFixed(3)}`);
    } catch (err) {
      log.error(`  ${preset.name} FAILED: ${(err as Error).message}`);
      // Push a zeroed entry so report is complete
      strategyResults.push({
        name: preset.name,
        winRate: 0,
        totalTrades: 0,
        pnlUsd: 0,
        pnlPct: 0,
        sharpe: 0,
        profitFactor: 0,
        maxDrawdown: 0,
        avgWin: 0,
        avgLoss: 0,
        bestTrade: { symbol: 'N/A', pnlPct: 0 },
        worstTrade: { symbol: 'N/A', pnlPct: 0 },
        rugsAvoided: 0,
        rugsHit: 0,
        fitnessScore: 0,
        avgHoldTime: 0,
      });
    }
  }

  // ─── Phase 2.5: Time-of-Day & Source Breakdown Analysis ────
  log.info('\n--- PHASE 2.5: TIME-OF-DAY ANALYSIS ---');

  let todAnalysis: TimeOfDayAnalysis | undefined;
  let sourceBreakdown: SourceBreakdownEntry[] | undefined;

  const topStrategyName = strategyResults
    .filter(s => s.totalTrades > 10)
    .sort((a, b) => b.fitnessScore - a.fitnessScore)[0]?.name;

  if (topStrategyName) {
    const topResult = rawResults.get(topStrategyName);
    if (topResult) {
      // Time-of-day analysis
      todAnalysis = analyzeTimeOfDay(topResult, cachedData);
      log.info(`  Time-of-day analysis for ${topStrategyName}:`);
      for (const stat of todAnalysis.hourlyStats.filter(s => s.trades > 0)) {
        log.info(`  Hour ${String(stat.hour).padStart(2, '0')}:00 UTC: ${stat.trades} trades, WR=${(stat.winRate * 100).toFixed(1)}%, AvgPnL=${stat.avgPnlPct.toFixed(1)}%`);
      }
      if (todAnalysis.bestHours.length > 0) {
        log.info(`  Best hours: ${todAnalysis.bestHours.map(h => h + ':00').join(', ')} UTC`);
      }
      if (todAnalysis.worstHours.length > 0) {
        log.info(`  Worst hours: ${todAnalysis.worstHours.map(h => h + ':00').join(', ')} UTC`);
      }

      // Source breakdown analysis
      sourceBreakdown = analyzeSourceBreakdown(topResult);
      if (sourceBreakdown.length > 0) {
        log.info(`  Source breakdown for ${topStrategyName}:`);
        for (const entry of sourceBreakdown) {
          log.info(`  ${entry.source}: ${entry.trades} trades, WR=${(entry.winRate * 100).toFixed(1)}%, AvgPnL=${entry.avgPnlPct.toFixed(1)}%`);
        }
      }
    }
  } else {
    log.info('  No strategy with >10 trades to analyze.');
  }

  // ─── Phase 3: Cross-Category Analysis ─────────────────────
  log.info('\n--- PHASE 3: CROSS-CATEGORY ANALYSIS ---');

  // Pick top 3 strategies by fitness
  const top3 = [...strategyResults]
    .sort((a, b) => b.fitnessScore - a.fitnessScore)
    .slice(0, 3)
    .filter(s => s.totalTrades > 0);

  log.info(`Top 3 strategies for cross-category analysis: ${top3.map(s => s.name).join(', ')}`);

  const crossCategoryResults: CrossCategoryEntry[] = [];

  // Define cross-category configs
  interface CrossCatDef {
    label: string;
    overrides: Partial<EnhancedBacktestConfig>;
  }

  const crossCategories: CrossCatDef[] = [
    { label: 'fresh', overrides: { ageCategory: 'fresh' } },
    { label: 'established', overrides: { ageCategory: 'established' } },
    { label: 'veteran', overrides: { ageCategory: 'veteran' } },
    { label: 'volume_surge', overrides: { requireVolumeSurge: true, minVolumeSurgeRatio: 2.0 } },
    { label: 'xstock', overrides: { assetType: 'xstock' } },
    { label: 'pumpfun', overrides: { source: 'pumpfun' } },
    { label: 'raydium', overrides: { source: 'raydium' } },
    { label: 'pumpswap', overrides: { source: 'pumpswap' } },
  ];

  for (const strategy of top3) {
    const preset = STRATEGY_PRESETS.find(p => p.name === strategy.name);
    if (!preset) continue;

    for (const cat of crossCategories) {
      try {
        const baseConfig = buildFullConfig(preset);
        const crossConfig: EnhancedBacktestConfig = { ...baseConfig, ...cat.overrides };
        const result = await runEnhancedBacktest(crossConfig, cachedData);

        crossCategoryResults.push({
          strategy: strategy.name,
          category: cat.label,
          winRate: result.winRate,
          trades: result.totalTrades,
          pnlUsd: result.totalPnlUsd,
          sharpe: result.sharpeRatio,
        });

        if (result.totalTrades > 0) {
          log.info(`  ${strategy.name} x ${cat.label}: WR=${(result.winRate * 100).toFixed(1)}%, Trades=${result.totalTrades}, PnL=$${result.totalPnlUsd.toFixed(2)}`);
        }
      } catch (err) {
        log.warn(`  ${strategy.name} x ${cat.label} failed: ${(err as Error).message}`);
        crossCategoryResults.push({
          strategy: strategy.name,
          category: cat.label,
          winRate: 0,
          trades: 0,
          pnlUsd: 0,
          sharpe: 0,
        });
      }
    }
  }

  // ─── Phase 4: Generate Report ─────────────────────────────
  log.info('\n--- PHASE 4: GENERATING REPORT ---');

  const rankings = computeRankings(strategyResults);
  const recommendations = generateRecommendations(strategyResults, crossCategoryResults);

  const report: MassiveBacktestReport = {
    runAt: new Date().toISOString(),
    macroRegime,
    totalTokensFetched: cachedData.length,
    tokenBreakdown: { bySource, byAge },
    strategyResults,
    crossCategoryResults,
    rankings,
    recommendations,
    hyperliquidCorrelations: hlCorrelations,
    timeOfDayAnalysis: todAnalysis,
    sourceBreakdown,
  };

  // Write JSON report
  const reportPath = path.join(winningDir, 'massive-backtest-results.json');
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  log.info(`Report written to: ${reportPath}`);

  // ─── Phase 5: Console Summary ─────────────────────────────
  log.info('\n' + '='.repeat(70));
  log.info('  MASSIVE BACKTEST RESULTS SUMMARY');
  log.info('='.repeat(70));
  log.info(`Macro Regime: ${macroRegime}`);
  log.info(`Tokens Fetched: ${cachedData.length}`);
  log.info(`Token Sources: ${Object.entries(bySource).map(([k, v]) => `${k}=${v}`).join(', ')}`);
  log.info(`Token Ages: ${Object.entries(byAge).map(([k, v]) => `${k}=${v}`).join(', ')}`);

  if (hlCorrelations) {
    log.info(`Hyperliquid: SOL/BTC corr=${hlCorrelations.solBtc.toFixed(3)}, SOL/ETH corr=${hlCorrelations.solEth.toFixed(3)}, BTC vol=${hlCorrelations.btcVol.toFixed(1)}%, SOL vol=${hlCorrelations.solVol.toFixed(1)}%`);
  }

  log.info('\n--- STRATEGY LEADERBOARD ---');
  log.info(`${'Strategy'.padEnd(18)} ${'WR%'.padStart(6)} ${'Trades'.padStart(7)} ${'PnL $'.padStart(9)} ${'Sharpe'.padStart(7)} ${'PF'.padStart(6)} ${'DD%'.padStart(6)} ${'Fitness'.padStart(8)}`);
  log.info('-'.repeat(70));

  const sorted = [...strategyResults].sort((a, b) => b.fitnessScore - a.fitnessScore);
  for (const s of sorted) {
    const wr = (s.winRate * 100).toFixed(1);
    const pnl = s.pnlUsd.toFixed(2);
    const sharpe = s.sharpe.toFixed(2);
    const pf = s.profitFactor === Infinity ? 'Inf' : s.profitFactor.toFixed(2);
    const dd = s.maxDrawdown.toFixed(1);
    const fit = s.fitnessScore.toFixed(3);
    log.info(`${s.name.padEnd(18)} ${wr.padStart(6)} ${String(s.totalTrades).padStart(7)} ${pnl.padStart(9)} ${sharpe.padStart(7)} ${pf.padStart(6)} ${dd.padStart(6)} ${fit.padStart(8)}`);
  }

  log.info('\n--- RANKINGS ---');
  log.info(`By Win Rate:  ${rankings.byWinRate.join(' > ')}`);
  log.info(`By PnL:       ${rankings.byPnl.join(' > ')}`);
  log.info(`By Sharpe:    ${rankings.bySharpe.join(' > ')}`);
  log.info(`By Fitness:   ${rankings.byFitness.join(' > ')}`);

  if (crossCategoryResults.length > 0) {
    log.info('\n--- CROSS-CATEGORY HIGHLIGHTS ---');
    const significantCross = crossCategoryResults.filter(c => c.trades > 0);
    for (const c of significantCross) {
      log.info(`  ${c.strategy} x ${c.category}: WR=${(c.winRate * 100).toFixed(1)}%, Trades=${c.trades}, PnL=$${c.pnlUsd.toFixed(2)}, Sharpe=${c.sharpe.toFixed(2)}`);
    }
  }

  log.info('\n--- RECOMMENDATIONS ---');
  for (const rec of recommendations) {
    log.info(`  * ${rec}`);
  }

  const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
  log.info(`\nCompleted in ${elapsed}s`);
  log.info('='.repeat(70));
}

// ─── Entry point ─────────────────────────────────────────────

function sleep(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

process.on('SIGINT', () => {
  log.info('\nInterrupted. Shutting down...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  log.info('\nTerminated. Shutting down...');
  process.exit(0);
});

// Only run main() when executed directly, not when imported by tests
const isDirectExecution = process.argv[1]?.includes('massive-backtest');
if (isDirectExecution) {
  main()
    .then(() => process.exit(0))
    .catch(err => {
      log.error('Fatal error:', { error: (err as Error).message, stack: (err as Error).stack });
      process.exit(1);
    });
}
