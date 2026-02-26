import { NextResponse } from 'next/server';
import {
  BacktestEngine,
  meanReversionEntry,
  trendFollowingEntry,
  breakoutEntry,
  momentumEntry,
  squeezeBreakoutEntry,
  generateBacktestReport,
  walkForwardTest,
  gridSearch,
  type BacktestConfig,
  type BacktestResult,
  type OHLCVCandle,
} from '@/lib/backtest-engine';
import { ALL_BLUECHIPS } from '@/lib/bluechip-data';
import { fetchGeckoSolanaPoolUniverse } from '@/lib/gecko-universe';
import { fetchMintHistory, type OHLCVSource, type HistoricalDataSet } from '@/lib/historical-data';
import { XSTOCKS, PRESTOCKS, INDEXES, COMMODITIES_TOKENS, type TokenizedEquity } from '@/lib/xstocks-data';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';
import { computeCoverageHealth, resolveCoverageThreshold } from '@/lib/backtest-coverage-policy';
import {
  putBacktestEvidence,
  type BacktestEvidenceBundle,
  type BacktestEvidenceDataset,
  type BacktestEvidenceTradeRow,
} from '@/lib/backtest-evidence';
import { persistBacktestArtifacts } from '@/lib/backtest-artifacts';
import { createHash } from 'crypto';
import {
  loadFamilyDatasetManifest,
  persistFamilyDatasetManifest,
  type DatasetFamily,
} from '@/lib/backtest-dataset-manifest';
import { backtestCorsOptions, withBacktestCors } from '@/lib/backtest-cors';
import {
  createBacktestRunStatus,
  failBacktestRun,
  finalizeBacktestRun,
  getBacktestRunStatus,
  heartbeatBacktestRun,
  markBacktestDatasetBatch,
  markBacktestChunkDone,
  markBacktestChunkFailed,
  markBacktestChunkRunning,
  markBacktestRunPhase,
} from '@/lib/backtest-run-registry';

// Evidence downloads rely on Node.js filesystem fallback in dev/serverless.
export const runtime = 'nodejs';

// Allow up to 15 minutes for thorough backtests (26 strategies × multiple tokens).
export const maxDuration = 900;

export function OPTIONS(request: Request) {
  return backtestCorsOptions(request);
}

/**
 * Backtest API Route -- Run strategy validation against historical data
 *
 * POST /api/backtest
 * Body: {
 *   strategyId: string,       // Strategy preset ID or 'all'
 *   tokenSymbol?: string,     // Specific token or 'all' (default: 'all')
 *   mode?: 'quick' | 'full' | 'grid',  // quick=single run, full=walk-forward, grid=parameter search
 *   candles?: OHLCVCandle[],  // Optional: client-provided candle data
 * }
 *
 * Data sources:
 *   - Blue chip strategies: real OHLCV (DexScreener pair discovery + GeckoTerminal candles; optional Birdeye fallback)
 *   - Memecoin strategies: real OHLCV (DexScreener pair discovery + GeckoTerminal candles; optional Birdeye fallback)
 *   - xStock/index/prestock strategies: real OHLCV (DexScreener pair discovery + GeckoTerminal candles; optional Birdeye fallback)
 *
 * Fulfills: BACK-02 (Backtesting Engine), BACK-03 (Strategy Validation Report)
 */

// ─── Strategy Classification ───

type StrategyCategory = 'bluechip' | 'memecoin' | 'bags' | 'xstock_index';
type BacktestMode = 'quick' | 'full' | 'grid';
type BacktestDataScale = 'fast' | 'thorough';
type BacktestDataSource = OHLCVSource | 'mixed' | 'client';
type SourcePolicy = 'gecko_only' | 'allow_birdeye_fallback';
type RequestedFamily = DatasetFamily;

function normalizeDataScale(v: unknown): BacktestDataScale {
  return v === 'fast' ? 'fast' : 'thorough';
}

function normalizeSourcePolicy(v: unknown): SourcePolicy {
  return v === 'allow_birdeye_fallback' ? 'allow_birdeye_fallback' : 'gecko_only';
}

function normalizeLookbackHours(v: unknown): number {
  if (typeof v !== 'number' || !Number.isFinite(v)) return 2160; // ~90 days at 1h candles
  return Math.max(720, Math.min(4320, Math.floor(v)));
}

function meanCi95(mean: number, std: number, n: number): [number, number] {
  if (n < 2 || !Number.isFinite(mean) || !Number.isFinite(std)) return [mean, mean];
  const margin = 1.96 * (std / Math.sqrt(n));
  return [mean - margin, mean + margin];
}

function wilsonBoundsFromCounts(wins: number, total: number, z = 1.96): [number, number] {
  if (total <= 0) return [0, 0];
  const p = wins / total;
  const z2 = z * z;
  const denom = 1 + z2 / total;
  const centre = p + z2 / (2 * total);
  const margin = z * Math.sqrt((p * (1 - p) + z2 / (4 * total)) / total);
  return [(centre - margin) / denom, (centre + margin) / denom];
}

const STRATEGY_CATEGORY: Record<string, StrategyCategory> = {
  // Blue chip strategies -- use real OHLCV data
  bluechip_trend_follow: 'bluechip',
  bluechip_breakout: 'bluechip',
  // Memecoin strategies -- use real OHLCV data
  pump_fresh_tight: 'memecoin',
  momentum: 'memecoin',
  micro_cap_surge: 'memecoin',
  elite: 'memecoin',
  hybrid_b: 'memecoin',
  let_it_ride: 'memecoin',
  // Established token strategies
  sol_veteran: 'memecoin',
  utility_swing: 'memecoin',
  established_breakout: 'memecoin',
  meme_classic: 'memecoin',
  volume_spike: 'memecoin',
  // Bags strategies -- run only on bags ecosystem universe
  bags_fresh_snipe: 'bags',
  bags_dip_buyer: 'bags',
  bags_bluechip: 'bags',
  bags_conservative: 'bags',
  bags_momentum: 'bags',
  bags_value: 'bags',
  bags_aggressive: 'bags',
  bags_elite: 'bags',
  // xStock / index / prestock -- use real OHLCV data (SPL tokens on Solana)
  xstock_intraday: 'xstock_index',
  xstock_swing: 'xstock_index',
  prestock_speculative: 'xstock_index',
  index_intraday: 'xstock_index',
  index_leveraged: 'xstock_index',
};

function familyForStrategyId(strategyId: string): RequestedFamily {
  const cat = STRATEGY_CATEGORY[strategyId];
  if (cat === 'memecoin') return 'memecoin';
  if (cat === 'bags') return 'bags';
  if (cat === 'bluechip') return 'bluechip';
  if (strategyId.startsWith('xstock_')) return 'xstock';
  if (strategyId.startsWith('prestock_')) return 'prestock';
  if (strategyId.startsWith('index_')) return 'index';
  return 'xstock_index';
}

const STRATEGY_FAMILY_ORDER: RequestedFamily[] = [
  'memecoin',
  'bags',
  'bluechip',
  'xstock',
  'prestock',
  'index',
  'xstock_index',
];

function orderStrategyIds(ids: string[]): string[] {
  const rank = (sid: string) => {
    const fam = familyForStrategyId(sid);
    const idx = STRATEGY_FAMILY_ORDER.indexOf(fam);
    return idx >= 0 ? idx : 999;
  };
  return [...ids].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

function resolveStrategyIdsFromFamily(family: RequestedFamily): string[] {
  const ids = Object.keys(STRATEGY_CONFIGS);
  switch (family) {
    case 'memecoin':
      return orderStrategyIds(ids.filter((sid) => familyForStrategyId(sid) === 'memecoin'));
    case 'bags':
      return orderStrategyIds(ids.filter((sid) => familyForStrategyId(sid) === 'bags'));
    case 'bluechip':
      return orderStrategyIds(ids.filter((sid) => familyForStrategyId(sid) === 'bluechip'));
    case 'xstock':
      return orderStrategyIds(ids.filter((sid) => familyForStrategyId(sid) === 'xstock'));
    case 'prestock':
      return orderStrategyIds(ids.filter((sid) => familyForStrategyId(sid) === 'prestock'));
    case 'index':
      return orderStrategyIds(ids.filter((sid) => familyForStrategyId(sid) === 'index'));
    case 'xstock_index':
      return orderStrategyIds(ids.filter((sid) => STRATEGY_CATEGORY[sid] === 'xstock_index'));
    default:
      return orderStrategyIds(ids);
  }
}

// Strategy entry signals mapped to preset IDs — R4 realistic-TP (2026-02-15)
const ENTRY_SIGNALS: Record<string, BacktestConfig['entrySignal']> = {
  // ── Memecoin core ──
  elite: momentumEntry,
  pump_fresh_tight: momentumEntry,          // fresh_pump in offline backtest; momentumEntry is closest
  micro_cap_surge: momentumEntry,           // aggressive in offline backtest; momentumEntry is closest
  // ── Memecoin wide ──
  momentum: meanReversionEntry,
  hybrid_b: meanReversionEntry,
  let_it_ride: meanReversionEntry,
  // ── Established tokens ──
  sol_veteran: meanReversionEntry,
  utility_swing: meanReversionEntry,
  established_breakout: meanReversionEntry,
  meme_classic: meanReversionEntry,
  volume_spike: meanReversionEntry,
  // ── Blue chip ──
  bluechip_trend_follow: meanReversionEntry,
  bluechip_breakout: meanReversionEntry,
  // ── Bags ──
  bags_fresh_snipe: momentumEntry,          // fresh_pump offline; momentumEntry is closest
  bags_momentum: momentumEntry,
  bags_aggressive: momentumEntry,           // aggressive offline; momentumEntry is closest
  bags_dip_buyer: meanReversionEntry,       // dip_buy offline; meanReversionEntry is closest
  bags_elite: meanReversionEntry,
  bags_value: meanReversionEntry,
  bags_conservative: meanReversionEntry,
  bags_bluechip: meanReversionEntry,
  // ── xStock / Index / Prestock ──
  xstock_intraday: meanReversionEntry,
  xstock_swing: meanReversionEntry,
  prestock_speculative: meanReversionEntry,
  index_intraday: meanReversionEntry,
  index_leveraged: meanReversionEntry,
};

type StrategyRuntimeConfig = Omit<BacktestConfig, 'entrySignal'> & {
  strategyRevision: string;
  seedVersion: string;
  promotedFromRunId?: string;
};

const STRATEGY_SEED_METADATA: Pick<StrategyRuntimeConfig, 'strategyRevision' | 'seedVersion'> = {
  strategyRevision: 'v3-backtest-proven-2026-02-15',
  seedVersion: 'seed-v3',
};

// Strategy configs — R4 realistic-TP optimized (2026-02-15).
// SL/TP/trail must match STRATEGY_PRESETS in useSniperStore.ts.
const STRATEGY_CONFIGS_BASE: Record<string, Omit<StrategyRuntimeConfig, 'strategyRevision' | 'seedVersion' | 'promotedFromRunId'>> = {
  // ─── Memecoin core (SL 10%, TP 20%, trail disabled) ───
  elite: {
    strategyId: 'elite',
    stopLossPct: 10, takeProfitPct: 20, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 100000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 12,
  },
  pump_fresh_tight: {
    strategyId: 'pump_fresh_tight',
    stopLossPct: 10, takeProfitPct: 20, trailingStopPct: 99,
    minScore: 40, minLiquidityUsd: 5000,
    slippagePct: 1.0, feePct: 0.25,
    maxHoldCandles: 8,
  },
  micro_cap_surge: {
    strategyId: 'micro_cap_surge',
    stopLossPct: 10, takeProfitPct: 20, trailingStopPct: 99,
    minScore: 30, minLiquidityUsd: 3000,
    slippagePct: 1.5, feePct: 0.25,
    maxHoldCandles: 8,
  },
  // ─── Memecoin wide (SL 10%, TP 25%, trail disabled) ───
  momentum: {
    strategyId: 'momentum',
    stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 24,
  },
  hybrid_b: {
    strategyId: 'hybrid_b',
    stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 24,
  },
  let_it_ride: {
    strategyId: 'let_it_ride',
    stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 48,
  },
  // ─── Established tokens (SL 8%, TP 15%, trail disabled) ───
  sol_veteran: {
    strategyId: 'sol_veteran',
    stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
    minScore: 40, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 168,
  },
  utility_swing: {
    strategyId: 'utility_swing',
    stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
    minScore: 55, minLiquidityUsd: 10000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 168,
  },
  established_breakout: {
    strategyId: 'established_breakout',
    stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
    minScore: 30, minLiquidityUsd: 10000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 168,
  },
  meme_classic: {
    strategyId: 'meme_classic',
    stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
    minScore: 40, minLiquidityUsd: 5000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 168,
  },
  volume_spike: {
    strategyId: 'volume_spike',
    stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99,
    minScore: 35, minLiquidityUsd: 20000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 168,
  },
  // ─── Bags tight (SL 5%, TP 9-10%, trail disabled) ───
  bags_elite: {
    strategyId: 'bags_elite',
    stopLossPct: 5, takeProfitPct: 9, trailingStopPct: 99,
    minScore: 70, minLiquidityUsd: 0,
    slippagePct: 0.6, feePct: 0.25,
    maxHoldCandles: 4,
  },
  bags_bluechip: {
    strategyId: 'bags_bluechip',
    stopLossPct: 5, takeProfitPct: 9, trailingStopPct: 99,
    minScore: 60, minLiquidityUsd: 0,
    slippagePct: 0.6, feePct: 0.25,
    maxHoldCandles: 4,
  },
  bags_value: {
    strategyId: 'bags_value',
    stopLossPct: 5, takeProfitPct: 10, trailingStopPct: 99,
    minScore: 60, minLiquidityUsd: 0,
    slippagePct: 0.6, feePct: 0.25,
    maxHoldCandles: 4,
  },
  bags_conservative: {
    strategyId: 'bags_conservative',
    stopLossPct: 5, takeProfitPct: 10, trailingStopPct: 99,
    minScore: 40, minLiquidityUsd: 0,
    slippagePct: 0.8, feePct: 0.25,
    maxHoldCandles: 4,
  },
  // ─── Bags wide (SL 7-10%, TP 25-30%, trail disabled) ───
  bags_fresh_snipe: {
    strategyId: 'bags_fresh_snipe',
    stopLossPct: 10, takeProfitPct: 30, trailingStopPct: 99,
    minScore: 35, minLiquidityUsd: 0,
    slippagePct: 0.8, feePct: 0.25,
    maxHoldCandles: 8,
  },
  bags_momentum: {
    strategyId: 'bags_momentum',
    stopLossPct: 10, takeProfitPct: 30, trailingStopPct: 99,
    minScore: 30, minLiquidityUsd: 0,
    slippagePct: 1.0, feePct: 0.25,
    maxHoldCandles: 12,
  },
  bags_aggressive: {
    strategyId: 'bags_aggressive',
    stopLossPct: 7, takeProfitPct: 25, trailingStopPct: 99,
    minScore: 10, minLiquidityUsd: 0,
    slippagePct: 1.2, feePct: 0.25,
    maxHoldCandles: 12,
  },
  bags_dip_buyer: {
    strategyId: 'bags_dip_buyer',
    stopLossPct: 8, takeProfitPct: 25, trailingStopPct: 99,
    minScore: 25, minLiquidityUsd: 0,
    slippagePct: 1.0, feePct: 0.25,
    maxHoldCandles: 8,
  },
  // ─── Blue chip Solana (SL 10%, TP 25%, trail disabled) ───
  bluechip_trend_follow: {
    strategyId: 'bluechip_trend_follow',
    stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.3, feePct: 0.25,
    maxHoldCandles: 48,
  },
  bluechip_breakout: {
    strategyId: 'bluechip_breakout',
    stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.3, feePct: 0.25,
    maxHoldCandles: 48,
  },
  // ─── xStock / Prestock / Index (SL 4%, TP 10%, trail disabled) ───
  xstock_intraday: {
    strategyId: 'xstock_intraday',
    stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.2, feePct: 0.25,
    maxHoldCandles: 96,
  },
  xstock_swing: {
    strategyId: 'xstock_swing',
    stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.2, feePct: 0.25,
    maxHoldCandles: 96,
  },
  prestock_speculative: {
    strategyId: 'prestock_speculative',
    stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99,
    minScore: 30, minLiquidityUsd: 5000,
    slippagePct: 0.3, feePct: 0.25,
    maxHoldCandles: 96,
  },
  index_intraday: {
    strategyId: 'index_intraday',
    stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.15, feePct: 0.25,
    maxHoldCandles: 96,
  },
  index_leveraged: {
    strategyId: 'index_leveraged',
    stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.2, feePct: 0.25,
    maxHoldCandles: 96,
  },
};

const STRATEGY_CONFIGS: Record<string, StrategyRuntimeConfig> = Object.fromEntries(
  Object.entries(STRATEGY_CONFIGS_BASE).map(([strategyId, config]) => [
    strategyId,
    { ...config, ...STRATEGY_SEED_METADATA },
  ]),
) as Record<string, StrategyRuntimeConfig>;

// ─── Backtest Runner Helpers ───

interface StrategyRunResult {
  result: BacktestResult;
  dataSource: BacktestDataSource;
  validated: boolean;
}

type EvidenceSink = (args: {
  dataset: HistoricalDataSet;
  result: BacktestResult;
  mode: BacktestMode;
}) => void;

function makeRunId(): string {
  // Not cryptographic; just unique enough for short-lived server cache keys.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function hashCandlesHex(candles: OHLCVCandle[]): string {
  // Stable SHA-256 hash of normalized candle fields.
  const h = createHash('sha256');
  for (const c of candles) {
    // Avoid JSON stringify overhead; use a stable delimiter format.
    h.update(
      `${c.timestamp},${c.open},${c.high},${c.low},${c.close},${c.volume};`,
      'utf8',
    );
  }
  return h.digest('hex');
}

function toEvidenceDataset(ds: HistoricalDataSet): BacktestEvidenceDataset {
  const first = ds.candles[0]?.timestamp ?? 0;
  const last = ds.candles[ds.candles.length - 1]?.timestamp ?? first;

  const out: BacktestEvidenceDataset = {
    tokenSymbol: ds.tokenSymbol,
    mintAddress: ds.mintAddress,
    pairAddress: ds.pairAddress,
    candles: ds.candles.length,
    dataHash: hashCandlesHex(ds.candles),
    dataStartTime: first,
    dataEndTime: last,
    fetchedAt: ds.fetchedAt,
    source: ds.source,
  };

  // When GeckoTerminal is used, pairAddress is the pool address.
  if (ds.source === 'geckoterminal' && ds.pairAddress) {
    out.geckoPoolUrl = `https://www.geckoterminal.com/solana/pools/${ds.pairAddress}`;
  }

  return out;
}

/**
 * Run a single strategy against the given candle data.
 * Supports quick, full (walk-forward), and grid modes.
 */
function runStrategy(
  sid: string,
  config: Omit<BacktestConfig, 'entrySignal'>,
  candles: OHLCVCandle[],
  tokenSymbol: string,
  mode: string,
  entrySignal: BacktestConfig['entrySignal'],
): BacktestResult[] {
  const fullConfig: BacktestConfig = {
    ...config,
    entrySignal,
  };

  if (mode === 'full') {
    const wf = walkForwardTest(candles, fullConfig, tokenSymbol);
    return [wf.inSample, wf.outOfSample];
  } else if (mode === 'grid') {
    const gridResults = gridSearch(
      candles,
      {
        strategyId: sid,
        minScore: config.minScore,
        minLiquidityUsd: config.minLiquidityUsd,
        slippagePct: config.slippagePct,
        feePct: config.feePct,
      },
      {
        stopLossPcts: [2, 3, 5, 8, 10, 15, 20, 30, 40, 50],
        takeProfitPcts: [5, 8, 12, 15, 20, 30, 50, 80, 100, 150, 200, 300],
        trailingStopPcts: [0, 2, 3, 5, 8, 10, 15, 20],
        maxHoldCandles: [4, 8, 12, 24, 48, 72, 168, 336],
      },
      tokenSymbol,
      entrySignal,
    );
    return gridResults.slice(0, 25); // Top 25
  } else {
    // Quick single run
    const engine = new BacktestEngine(candles, fullConfig);
    return [engine.run(tokenSymbol)];
  }
}

/**
 * Run blue chip strategies against real OHLCV data.
 * Fetches token history in batches of 3 to respect rate limits.
 */
async function runBluechipStrategy(
  sid: string,
  config: Omit<BacktestConfig, 'entrySignal'>,
  entrySignal: BacktestConfig['entrySignal'],
  mode: BacktestMode,
  tokenSymbol: string,
  maxTokens: number,
  fetchOpts: {
    allowBirdeyeFallback: boolean;
    maxCandles: number;
    minCandles: number;
    fetchBatchSize?: number;
    minDatasetsRequired?: number;
  },
  onEvidence?: EvidenceSink,
  onDatasetBatch?: (args: { attempted: number; succeeded: number; failed: number; context: string }) => void,
): Promise<StrategyRunResult[]> {
  const withTimeBudget = async <T,>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> => {
    // Avoid Promise.race() + setTimeout() without cleanup: it can trigger late unhandled rejections
    // after the main promise already resolved, leaving "zombie" runs with no heartbeat.
    const ms = Math.max(1000, Math.floor(timeoutMs || 0));
    return await new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Timeout (${ms}ms): ${label}`)), ms);
      promise.then(
        (val) => {
          clearTimeout(timer);
          resolve(val);
        },
        (err) => {
          clearTimeout(timer);
          reject(err);
        },
      );
    });
  };

  // Avoid indefinite hangs due to upstream network stalls (DexScreener pair discovery, etc.).
  // GeckoTerminal pulls are paced server-side, but any single token should not be allowed to
  // block the entire backtest run.
  const perTokenTimeoutMs = Math.max(
    15_000,
    Math.min(90_000, fetchOpts.maxCandles <= 600 ? 25_000 : 60_000),
  );

  const tokens = tokenSymbol === 'all'
    ? ALL_BLUECHIPS.slice(0, Math.max(1, Math.min(maxTokens, ALL_BLUECHIPS.length)))
    : ALL_BLUECHIPS.filter(t => t.ticker === tokenSymbol);

  const runResults: StrategyRunResult[] = [];
  let datasetsUsed = 0;

  // Process hardcoded blue chips in batches of 3 to avoid rate limits
  for (let batch = 0; batch < tokens.length; batch += 3) {
    const batchTokens = tokens.slice(batch, batch + 3);
    const ctx = `hardcoded-bluechip ${Math.floor(batch / 3) + 1}/${Math.ceil(tokens.length / 3)}`;
    const hb: ReturnType<typeof setInterval> | null = onDatasetBatch
      ? setInterval(() => {
          onDatasetBatch({ attempted: 0, succeeded: 0, failed: 0, context: `${ctx} (waiting...)` });
        }, 10_000)
      : null;
    const batchData = await Promise.allSettled(
      batchTokens.map(token =>
        withTimeBudget(
          fetchMintHistory(token.mintAddress, token.ticker, {
            allowBirdeyeFallback: fetchOpts.allowBirdeyeFallback,
            attemptBirdeyeIfCandlesBelow: fetchOpts.minCandles,
            minCandles: fetchOpts.minCandles,
            maxCandles: fetchOpts.maxCandles,
            resolution: '60',
          }),
          perTokenTimeoutMs,
          `fetchMintHistory ${token.ticker}`,
        ),
      ),
    );
    if (hb) clearInterval(hb);

    let succeeded = 0;
    for (let i = 0; i < batchTokens.length; i++) {
      const settled = batchData[i];
      if (settled.status !== 'fulfilled') continue;
      succeeded += 1;
      const data = settled.value;
      datasetsUsed += 1;
      const results = runStrategy(
        sid, config, data.candles, batchTokens[i].ticker, mode, entrySignal,
      );
      for (const result of results) {
        onEvidence?.({ dataset: data, result, mode });
        runResults.push({
          result,
          dataSource: data.source,
          validated: true,
        });
      }
    }
    onDatasetBatch?.({
      attempted: batchTokens.length,
      succeeded,
      failed: Math.max(0, batchTokens.length - succeeded),
      context: ctx,
    });
  }

  // Supplement with GeckoTerminal top-liquidity established pools to reach maxTokens
  if (tokenSymbol === 'all' && maxTokens > ALL_BLUECHIPS.length) {
    const supplementNeeded = maxTokens - runResults.length;
    if (supplementNeeded > 0) {
      const bluechipMints = new Set(ALL_BLUECHIPS.map(t => t.mintAddress));
      // Request 3x candidates since some will fail OHLCV fetch
      const candidateLimit = Math.min(600, supplementNeeded * 3);
      const geckoPools = await fetchGeckoSolanaPoolUniverse(candidateLimit, {
        minAgeMs: 48 * 60 * 60 * 1000, // 48h minimum age for candle data
        onProgress: ({ endpoint, page, pages, received }) => {
          onDatasetBatch?.({
            attempted: 0,
            succeeded: 0,
            failed: 0,
            context: `gecko-universe ${endpoint} ${page}/${pages} (received ${received})`,
          });
        },
      });

      // Filter out already-tested blue chips
      const supplementPools = geckoPools
        .filter(p => !bluechipMints.has(p.baseMint))
        .slice(0, supplementNeeded * 2); // Extra buffer for failures

      const { datasets } = await fetchDatasetsForPools(
        supplementPools.map(p => ({
          baseMint: p.baseMint,
          baseSymbol: p.baseSymbol,
          poolAddress: p.poolAddress,
        })),
        supplementNeeded,
        {
          allowBirdeyeFallback: fetchOpts.allowBirdeyeFallback,
          attemptBirdeyeIfCandlesBelow: fetchOpts.minCandles,
          minCandles: fetchOpts.minCandles,
          maxCandles: fetchOpts.maxCandles,
          resolution: '60',
        },
        fetchOpts.fetchBatchSize ?? 4,
        onDatasetBatch,
      );

      for (const ds of datasets) {
        datasetsUsed += 1;
        const results = runStrategy(sid, config, ds.candles, ds.tokenSymbol, mode, entrySignal);
        for (const result of results) {
          onEvidence?.({ dataset: ds, result, mode });
          runResults.push({
            result,
            dataSource: ds.source,
            validated: true,
          });
        }
      }
    }
  }

  const minDatasetsRequired = Math.max(1, Math.floor(fetchOpts.minDatasetsRequired || 1));
  if (datasetsUsed < minDatasetsRequired) {
    throw new Error(
      `Bluechip coverage gate failed: only ${datasetsUsed} datasets available (min ${minDatasetsRequired})`,
    );
  }

  return runResults;
}

/**
 * Aggregate BacktestResults across multiple independent assets by combining trade outcomes.
 *
 * Note: this is not a portfolio simulation (assets overlap in time). It is a pragmatic way to
 * validate whether a strategy's per-trade edge holds across a broader, real-data universe.
 */
function aggregateBacktestResults(
  strategyId: string,
  fullConfig: BacktestConfig,
  tokenLabel: string,
  results: BacktestResult[],
): BacktestResult {
  let totalTrades = 0;
  let wins = 0;
  let losses = 0;
  let winningPnl = 0;
  let losingPnl = 0;
  let sumReturn = 0;
  let sumSquaresReturn = 0;
  let sumHoldCandles = 0;
  let bestTrade = Number.NEGATIVE_INFINITY;
  let worstTrade = Number.POSITIVE_INFINITY;

  let equity = 100;
  let peak = 100;
  let maxDrawdownPct = 0;
  const equityCurve: number[] = [equity];

  const tradeSamples: BacktestResult['trades'] = [];
  const MAX_TRADE_SAMPLES = 500;

  let dataStartTime = Number.POSITIVE_INFINITY;
  let dataEndTime = 0;
  let totalCandles = 0;

  for (const r of results) {
    dataStartTime = Math.min(dataStartTime, r.dataStartTime);
    dataEndTime = Math.max(dataEndTime, r.dataEndTime);
    totalCandles += r.totalCandles;

    for (const t of r.trades) {
      totalTrades += 1;
      sumReturn += t.pnlNet;
      sumSquaresReturn += t.pnlNet * t.pnlNet;
      sumHoldCandles += t.holdCandles;

      if (t.pnlNet > 0) {
        wins += 1;
        winningPnl += t.pnlNet;
      } else {
        losses += 1;
        losingPnl += Math.abs(t.pnlNet);
      }

      bestTrade = Math.max(bestTrade, t.pnlNet);
      worstTrade = Math.min(worstTrade, t.pnlNet);

      if (tradeSamples.length < MAX_TRADE_SAMPLES) {
        const logReturn = Number.isFinite((t as any).logReturn)
          ? Number((t as any).logReturn)
          : (t.entryPrice > 0 && t.exitPrice > 0 ? Math.log(t.exitPrice / t.entryPrice) : 0);
        tradeSamples.push({ ...t, logReturn });
      }

      // "Pseudo equity" across independent samples: useful as a drawdown sanity check.
      equity *= (1 + t.pnlNet / 100);
      equityCurve.push(equity);
      if (equityCurve.length > 100) equityCurve.shift();

      peak = Math.max(peak, equity);
      const dd = peak > 0 ? ((peak - equity) / peak) * 100 : 0;
      maxDrawdownPct = Math.max(maxDrawdownPct, dd);
    }
  }

  const winRate = totalTrades > 0 ? wins / totalTrades : 0;
  const rawPF = losingPnl > 0 ? winningPnl / losingPnl : (winningPnl > 0 ? 999 : 0);
  const profitFactor = Math.min(rawPF, 999);

  const avgReturnPct = totalTrades > 0 ? sumReturn / totalTrades : 0;
  const avgHold = totalTrades > 0 ? sumHoldCandles / totalTrades : 0;
  const expectancy = avgReturnPct; // Mean per-trade pnlNet

  const variance = totalTrades > 1
    ? (sumSquaresReturn - totalTrades * avgReturnPct * avgReturnPct) / (totalTrades - 1)
    : 0;
  const stdReturn = Math.sqrt(Math.max(variance, 0));
  const MIN_STD = 0.001;
  const sharpeLike = (avgReturnPct / Math.max(stdReturn, MIN_STD)) * Math.sqrt(Math.max(totalTrades, 1));
  const sharpeRatio = Math.max(-10, Math.min(10, sharpeLike));
  const avgReturnCI95 = meanCi95(avgReturnPct, stdReturn, totalTrades);
  const winRateCI95 = wilsonBoundsFromCounts(wins, totalTrades);
  const sharpeCiHalfWidth = totalTrades > 1 ? (1.96 / Math.sqrt(totalTrades)) : 0;
  const sharpeCI95: [number, number] = [
    sharpeRatio - sharpeCiHalfWidth,
    sharpeRatio + sharpeCiHalfWidth,
  ];
  const cltReliable = totalTrades >= 50;
  const logReturns = tradeSamples.map((t) =>
    Number.isFinite((t as any).logReturn) ? Number((t as any).logReturn) : 0,
  );
  let ewmaVariance = logReturns.length > 0 ? logReturns[0] * logReturns[0] : 0;
  for (let i = 1; i < logReturns.length; i++) {
    ewmaVariance = 0.9 * ewmaVariance + 0.1 * logReturns[i] * logReturns[i];
  }
  const ewmaVol = Math.sqrt(Math.max(ewmaVariance, 0));
  const parkinsonVol = 0;
  const winRateDisplay = totalTrades > 0
    ? `${(winRate * 100).toFixed(1)}% [${(winRateCI95[0] * 100).toFixed(1)}-${(winRateCI95[1] * 100).toFixed(1)}%]`
    : '0.0% [0.0-0.0%]';

  return {
    strategyId: strategyId,
    config: fullConfig,
    tokenSymbol: tokenLabel,
    totalTrades,
    wins,
    losses,
    winRate,
    profitFactor,
    avgReturnPct,
    bestTradePct: totalTrades > 0 ? bestTrade : 0,
    worstTradePct: totalTrades > 0 ? worstTrade : 0,
    maxDrawdownPct,
    sharpeRatio,
    avgHoldCandles: avgHold,
    expectancy,
    trades: tradeSamples,
    equityCurve,
    dataStartTime: Number.isFinite(dataStartTime) ? dataStartTime : 0,
    dataEndTime,
    totalCandles,
    avgReturnCI95,
    winRateCI95,
    sharpeCI95,
    cltReliable,
    parkinsonVol,
    ewmaVol,
    winRateDisplay,
  };
}

function wilsonBoundsPctFromCounts(wins: number, total: number): { lower: number; upper: number } {
  const n = Math.max(0, Math.floor(Number(total) || 0));
  if (n <= 0) return { lower: 0, upper: 0 };
  const k = Math.max(0, Math.floor(Number(wins) || 0));
  const p = k / n;
  const z = 1.96;
  const denom = 1 + (z * z) / n;
  const center = p + (z * z) / (2 * n);
  const margin = z * Math.sqrt((p * (1 - p) + (z * z) / (4 * n)) / n);
  return {
    lower: ((center - margin) / denom) * 100,
    upper: ((center + margin) / denom) * 100,
  };
}

// ─── Real Data Universes ───

const DEXSCREENER_BOOSTS = 'https://api.dexscreener.com/token-boosts/latest/v1';
const DEXSCREENER_PROFILES = 'https://api.dexscreener.com/token-profiles/latest/v1';
const DEXSCREENER_SOL_PAIRS =
  'https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112';
const DEXSCREENER_SOL_TOKEN_PAIRS = 'https://api.dexscreener.com/tokens/v1/solana';
const JUPITER_GEMS_URL = 'https://datapi.jup.ag/v1/pools/gems';
const BAGS_TOP_FEES_URL = 'https://api2.bags.fm/api/v1/token-launch/top-tokens/lifetime-fees';

async function fetchWithTimeout(
  url: string,
  initOrTimeout: RequestInit | number = 8000,
  timeoutMs = 8000,
): Promise<Response> {
  const timeout = typeof initOrTimeout === 'number' ? initOrTimeout : timeoutMs;
  const init = typeof initOrTimeout === 'number' ? undefined : initOrTimeout;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    return await fetch(url, {
      headers: { Accept: 'application/json', ...(init?.headers || {}) },
      ...init,
      signal: controller.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

async function fetchDexScreenerSolanaMintUniverse(limit: number): Promise<string[]> {
  const out: string[] = [];
  const seen = new Set<string>();
  const EXCLUDE = new Set([
    // WSOL
    'So11111111111111111111111111111111111111112',
    // USDC / USDT (avoid stablecoin bias in "memecoin" validation)
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
  ]);

  const push = (mint: string | undefined | null) => {
    if (!mint) return;
    if (EXCLUDE.has(mint)) return;
    if (seen.has(mint)) return;
    seen.add(mint);
    out.push(mint);
  };

  const [boostsRes, profilesRes, solPairsRes] = await Promise.allSettled([
    fetchWithTimeout(DEXSCREENER_BOOSTS),
    fetchWithTimeout(DEXSCREENER_PROFILES),
    fetchWithTimeout(DEXSCREENER_SOL_PAIRS),
  ]);

  if (solPairsRes.status === 'fulfilled' && solPairsRes.value.ok) {
    try {
      const json = await solPairsRes.value.json();
      const pairs: any[] = json?.pairs || [];
      for (const pair of pairs) {
        const chainId = String(pair?.chainId || '').trim().toLowerCase();
        if (chainId && chainId !== 'solana') continue;

        const baseMint = String(pair?.baseToken?.address || '').trim();
        const quoteMint = String(pair?.quoteToken?.address || '').trim();
        if (!baseMint || !quoteMint) continue;
        const baseExcluded = EXCLUDE.has(baseMint);
        const quoteExcluded = EXCLUDE.has(quoteMint);
        if (baseExcluded && quoteExcluded) continue;
        push(baseExcluded ? quoteMint : baseMint);
        if (out.length >= limit) return out.slice(0, limit);
      }
    } catch {
      // ignore
    }
  }

  if (boostsRes.status === 'fulfilled' && boostsRes.value.ok) {
    try {
      const all: any[] = await boostsRes.value.json();
      for (const b of all) {
        if (b?.chainId !== 'solana') continue;
        push(b?.tokenAddress);
        if (out.length >= limit) return out.slice(0, limit);
      }
    } catch {
      // ignore
    }
  }

  if (profilesRes.status === 'fulfilled' && profilesRes.value.ok) {
    try {
      const all: any[] = await profilesRes.value.json();
      for (const p of all) {
        if (p?.chainId !== 'solana') continue;
        push(p?.tokenAddress);
        if (out.length >= limit) return out.slice(0, limit);
      }
    } catch {
      // ignore
    }
  }

  return out.slice(0, limit);
}

async function fetchBagsMintUniverse(limit: number): Promise<string[]> {
  const out: string[] = [];
  const seen = new Set<string>();

  const push = (mint: unknown) => {
    if (typeof mint !== 'string') return;
    const m = mint.trim();
    if (!m || m.length < 20 || seen.has(m)) return;
    seen.add(m);
    out.push(m);
  };

  try {
    const res = await fetchWithTimeout(
      JUPITER_GEMS_URL,
      {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        recent: { launchpads: ['bags.fun'], minMcap: 0 },
        aboutToGraduate: { launchpads: ['bags.fun'], minMcap: 0 },
        graduated: { launchpads: ['bags.fun'], minMcap: 0 },
      }),
      },
      12000,
    );
    if (res.ok) {
      const json = await res.json();
      const buckets = ['recent', 'aboutToGraduate', 'graduated'] as const;
      for (const bucket of buckets) {
        const pools: any[] = json?.[bucket]?.pools || [];
        for (const p of pools) {
          push(p?.baseAsset?.id);
          push(p?.baseAsset?.mint);
          push(p?.id);
          if (out.length >= limit) return out.slice(0, limit);
        }
      }
    }
  } catch {
    // ignore and continue to bags top earners source
  }

  try {
    const res = await fetchWithTimeout(BAGS_TOP_FEES_URL, 12000);
    if (res.ok) {
      const json = await res.json();
      const rows: any[] = json?.response || [];
      for (const row of rows) {
        push(row?.token);
        push(row?.tokenInfo?.id);
        if (out.length >= limit) return out.slice(0, limit);
      }
    }
  } catch {
    // ignore
  }

  return out.slice(0, limit);
}

interface GeckoPoolCandidate {
  baseMint: string;
  baseSymbol: string;
  poolAddress: string;
}

function safeDexNumber(v: unknown): number {
  const n = typeof v === 'number' ? v : Number.parseFloat(String(v ?? '0'));
  return Number.isFinite(n) ? n : 0;
}

/**
 * DexScreener universe discovery optimized for backtesting:
 * - Pull SOL pairs once (WSOL pairs endpoint)
 * - Keep the best-liquidity pool per base mint
 * - Return pool candidates so fetchMintHistory can use pairAddressOverride (no per-mint Dex calls)
 */
async function fetchDexScreenerSolanaPoolUniverse(limit: number): Promise<GeckoPoolCandidate[]> {
  const target = Math.max(10, Math.min(2000, Math.floor(limit || 0)));

  const EXCLUDE = new Set([
    // WSOL
    'So11111111111111111111111111111111111111112',
    // USDC / USDT
    'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
    'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
  ]);

  // Step 1: get candidate mints (boosts + profiles + a few high-liq SOL pairs).
  const candidateMints = await fetchDexScreenerSolanaMintUniverse(target);
  if (candidateMints.length === 0) return [];
  const mintSet = new Set(candidateMints);

  // Step 2: resolve pool addresses in batches (DexScreener supports comma-separated mints).
  const byMint = new Map<string, { pool: GeckoPoolCandidate; liquidityUsd: number }>();
  const batchSize = 20; // keep URL lengths safe

  for (let i = 0; i < candidateMints.length; i += batchSize) {
    const batch = candidateMints.slice(i, i + batchSize);
    const url = `${DEXSCREENER_SOL_TOKEN_PAIRS}/${batch.join(',')}`;

    let pairs: any[] = [];
    try {
      const res = await fetchWithTimeout(url, 12_000);
      if (!res.ok) continue;
      const json = await res.json();
      pairs = Array.isArray(json) ? json : [];
    } catch {
      continue;
    }

    for (const pair of pairs) {
      const chainId = String(pair?.chainId || '').trim().toLowerCase();
      if (chainId && chainId !== 'solana') continue;

      const poolAddress = String(pair?.pairAddress || '').trim();
      if (!poolAddress) continue;

      const baseMint = String(pair?.baseToken?.address || '').trim();
      const quoteMint = String(pair?.quoteToken?.address || '').trim();
      if (!baseMint || !quoteMint) continue;

      // Determine which side is a requested mint; prefer baseToken if both match.
      let primaryMint = '';
      let primarySym = '';
      if (mintSet.has(baseMint)) {
        primaryMint = baseMint;
        primarySym = String(pair?.baseToken?.symbol || '').trim() || baseMint.slice(0, 6);
      } else if (mintSet.has(quoteMint)) {
        primaryMint = quoteMint;
        primarySym = String(pair?.quoteToken?.symbol || '').trim() || quoteMint.slice(0, 6);
      } else {
        continue;
      }

      if (EXCLUDE.has(primaryMint)) continue;

      const liquidityUsd = safeDexNumber(pair?.liquidity?.usd);
      const existing = byMint.get(primaryMint);
      if (!existing || liquidityUsd > existing.liquidityUsd) {
        byMint.set(primaryMint, {
          pool: { baseMint: primaryMint, baseSymbol: primarySym, poolAddress },
          liquidityUsd,
        });
      }
    }
  }

  return [...byMint.values()]
    .sort((a, b) => b.liquidityUsd - a.liquidityUsd)
    .slice(0, target)
    .map((row) => row.pool);
}

async function fetchDatasetsForPools(
  pools: GeckoPoolCandidate[],
  maxDatasets: number,
  options: Parameters<typeof fetchMintHistory>[2],
  batchSize = 4,
  onBatch?: (args: { attempted: number; succeeded: number; failed: number; context: string }) => void,
): Promise<{ datasets: HistoricalDataSet[]; sources: Set<OHLCVSource>; attempted: number }> {
  const withTimeBudget = async <T,>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> => {
    const ms = Math.max(1000, Math.floor(timeoutMs || 0));
    return await new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Timeout (${ms}ms): ${label}`)), ms);
      promise.then(
        (val) => {
          clearTimeout(timer);
          resolve(val);
        },
        (err) => {
          clearTimeout(timer);
          reject(err);
        },
      );
    });
  };

  const maxCandles = Math.max(0, Number((options as any)?.maxCandles ?? 0) || 0);
  const perTokenTimeoutMs = Math.max(15_000, Math.min(90_000, maxCandles <= 600 ? 25_000 : 60_000));
  const attemptCeiling = Math.max(batchSize * 4, maxDatasets * 6);

  const datasets: HistoricalDataSet[] = [];
  const sources = new Set<OHLCVSource>();
  let attempted = 0;

  for (let i = 0; i < pools.length && datasets.length < maxDatasets && attempted < attemptCeiling; i += batchSize) {
    const batch = pools.slice(i, i + batchSize);
    attempted += batch.length;

    const ctx = `pool-batch ${Math.floor(i / batchSize) + 1}/${Math.ceil(pools.length / batchSize)}`;
    const hb: ReturnType<typeof setInterval> | null = onBatch
      ? setInterval(() => {
          onBatch({ attempted: 0, succeeded: 0, failed: 0, context: `${ctx} (waiting...)` });
        }, 10_000)
      : null;
    const settled = await Promise.allSettled(
      batch.map((p) =>
        withTimeBudget(
          fetchMintHistory(p.baseMint, p.baseSymbol || p.baseMint.slice(0, 6), {
            ...options,
            pairAddressOverride: p.poolAddress,
          }),
          perTokenTimeoutMs,
          `fetchMintHistory ${p.baseSymbol || p.baseMint.slice(0, 6)}`,
        ),
      ),
    );
    if (hb) clearInterval(hb);

    let succeeded = 0;
    let failed = 0;
    for (const s of settled) {
      if (s.status !== 'fulfilled') continue;
      datasets.push(s.value);
      sources.add(s.value.source);
      succeeded += 1;
      if (datasets.length >= maxDatasets) break;
    }
    failed = Math.max(0, batch.length - succeeded);
    onBatch?.({
      attempted: batch.length,
      succeeded,
      failed,
      context: ctx,
    });
  }

  return { datasets, sources, attempted };
}

async function fetchDatasetsForMints(
  mints: string[],
  maxDatasets: number,
  tokenSymbolForMint: (mint: string) => string,
  options: Parameters<typeof fetchMintHistory>[2],
  batchSize = 4,
  onBatch?: (args: { attempted: number; succeeded: number; failed: number; context: string }) => void,
): Promise<{ datasets: HistoricalDataSet[]; sources: Set<OHLCVSource>; attempted: number }> {
  const withTimeBudget = async <T,>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> => {
    const ms = Math.max(1000, Math.floor(timeoutMs || 0));
    return await new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`Timeout (${ms}ms): ${label}`)), ms);
      promise.then(
        (val) => {
          clearTimeout(timer);
          resolve(val);
        },
        (err) => {
          clearTimeout(timer);
          reject(err);
        },
      );
    });
  };

  const maxCandles = Math.max(0, Number((options as any)?.maxCandles ?? 0) || 0);
  const perTokenTimeoutMs = Math.max(15_000, Math.min(90_000, maxCandles <= 600 ? 25_000 : 60_000));
  const attemptCeiling = Math.max(batchSize * 4, maxDatasets * 6);

  const datasets: HistoricalDataSet[] = [];
  const sources = new Set<OHLCVSource>();
  let attempted = 0;

  for (let i = 0; i < mints.length && datasets.length < maxDatasets && attempted < attemptCeiling; i += batchSize) {
    const batch = mints.slice(i, i + batchSize);
    attempted += batch.length;

    const ctx = `mint-batch ${Math.floor(i / batchSize) + 1}/${Math.ceil(mints.length / batchSize)}`;
    const hb: ReturnType<typeof setInterval> | null = onBatch
      ? setInterval(() => {
          onBatch({ attempted: 0, succeeded: 0, failed: 0, context: `${ctx} (waiting...)` });
        }, 10_000)
      : null;
    const settled = await Promise.allSettled(
      batch.map((mint) =>
        withTimeBudget(
          fetchMintHistory(mint, tokenSymbolForMint(mint), options),
          perTokenTimeoutMs,
          `fetchMintHistory ${tokenSymbolForMint(mint)}`,
        ),
      ),
    );
    if (hb) clearInterval(hb);

    let succeeded = 0;
    let failed = 0;
    for (const s of settled) {
      if (s.status !== 'fulfilled') continue;
      datasets.push(s.value);
      sources.add(s.value.source);
      succeeded += 1;
      if (datasets.length >= maxDatasets) break;
    }
    failed = Math.max(0, batch.length - succeeded);
    onBatch?.({
      attempted: batch.length,
      succeeded,
      failed,
      context: ctx,
    });
  }

  return { datasets, sources, attempted };
}

function sourceLabel(sources: Set<OHLCVSource>): BacktestDataSource {
  return sources.size === 1 ? [...sources][0] : 'mixed';
}

function equityUniverseForStrategy(strategyId: string): TokenizedEquity[] {
  if (strategyId.startsWith('xstock_')) return XSTOCKS;
  if (strategyId.startsWith('prestock_')) return PRESTOCKS;
  if (strategyId.startsWith('index_')) return [...INDEXES, ...COMMODITIES_TOKENS];
  return [...XSTOCKS, ...PRESTOCKS, ...INDEXES, ...COMMODITIES_TOKENS];
}

async function runMemecoinStrategyReal(
  sid: string,
  config: Omit<BacktestConfig, 'entrySignal'>,
  entrySignal: BacktestConfig['entrySignal'],
  mode: BacktestMode,
  maxTokens: number,
  datasets: HistoricalDataSet[],
  sources: Set<OHLCVSource>,
  onEvidence?: EvidenceSink,
): Promise<StrategyRunResult[]> {
  if (datasets.length === 0) {
    throw new Error('No real memecoin OHLCV datasets available');
  }

  // Grid mode is exploratory and expensive: run on a single representative dataset.
  if (mode === 'grid') {
    const target = datasets[0];
    const results = runStrategy(sid, config, target.candles, target.tokenSymbol, mode, entrySignal);
    return results.map((result) => {
      onEvidence?.({ dataset: target, result, mode });
      return {
        result,
        dataSource: target.source,
        validated: true,
      };
    });
  }

  const fullConfig: BacktestConfig = { ...config, entrySignal };
  const labelBase = `MEME (n=${Math.min(maxTokens, datasets.length)})`;

  if (mode === 'full') {
    const train: BacktestResult[] = [];
    const test: BacktestResult[] = [];

    for (const ds of datasets) {
      const [inSample, outOfSample] = runStrategy(
        sid,
        config,
        ds.candles,
        ds.tokenSymbol,
        mode,
        entrySignal,
      );
      if (inSample) train.push(inSample);
      if (outOfSample) test.push(outOfSample);
      if (inSample) onEvidence?.({ dataset: ds, result: inSample, mode });
      if (outOfSample) onEvidence?.({ dataset: ds, result: outOfSample, mode });
    }

    return [
      {
        result: aggregateBacktestResults(sid, fullConfig, `${labelBase}_train`, train),
        dataSource: sourceLabel(sources),
        validated: true,
      },
      {
        result: aggregateBacktestResults(sid, fullConfig, `${labelBase}_test`, test),
        dataSource: sourceLabel(sources),
        validated: true,
      },
    ];
  }

  const quickResults: BacktestResult[] = [];
  for (const ds of datasets) {
    const [r] = runStrategy(sid, config, ds.candles, ds.tokenSymbol, 'quick', entrySignal);
    if (r) {
      quickResults.push(r);
      onEvidence?.({ dataset: ds, result: r, mode });
    }
  }

  return [
    {
      result: aggregateBacktestResults(sid, fullConfig, labelBase, quickResults),
      dataSource: sourceLabel(sources),
      validated: true,
    },
  ];
}

async function runXstockIndexStrategyReal(
  sid: string,
  config: Omit<BacktestConfig, 'entrySignal'>,
  entrySignal: BacktestConfig['entrySignal'],
  mode: BacktestMode,
  maxTokens: number,
  datasets: HistoricalDataSet[],
  sources: Set<OHLCVSource>,
  onEvidence?: EvidenceSink,
): Promise<StrategyRunResult[]> {
  if (datasets.length === 0) {
    throw new Error('No real xStock/index OHLCV datasets available');
  }

  if (mode === 'grid') {
    const target = datasets[0];
    const results = runStrategy(sid, config, target.candles, target.tokenSymbol, mode, entrySignal);
    return results.map((result) => {
      onEvidence?.({ dataset: target, result, mode });
      return {
        result,
        dataSource: target.source,
        validated: true,
      };
    });
  }

  const fullConfig: BacktestConfig = { ...config, entrySignal };
  const labelBase = `XSTOCK/INDEX (n=${Math.min(maxTokens, datasets.length)})`;

  if (mode === 'full') {
    const train: BacktestResult[] = [];
    const test: BacktestResult[] = [];

    for (const ds of datasets) {
      const [inSample, outOfSample] = runStrategy(
        sid,
        config,
        ds.candles,
        ds.tokenSymbol,
        mode,
        entrySignal,
      );
      if (inSample) train.push(inSample);
      if (outOfSample) test.push(outOfSample);
      if (inSample) onEvidence?.({ dataset: ds, result: inSample, mode });
      if (outOfSample) onEvidence?.({ dataset: ds, result: outOfSample, mode });
    }

    return [
      {
        result: aggregateBacktestResults(sid, fullConfig, `${labelBase}_train`, train),
        dataSource: sourceLabel(sources),
        validated: true,
      },
      {
        result: aggregateBacktestResults(sid, fullConfig, `${labelBase}_test`, test),
        dataSource: sourceLabel(sources),
        validated: true,
      },
    ];
  }

  const quickResults: BacktestResult[] = [];
  for (const ds of datasets) {
    const [r] = runStrategy(sid, config, ds.candles, ds.tokenSymbol, 'quick', entrySignal);
    if (r) {
      quickResults.push(r);
      onEvidence?.({ dataset: ds, result: r, mode });
    }
  }

  return [
    {
      result: aggregateBacktestResults(sid, fullConfig, labelBase, quickResults),
      dataSource: sourceLabel(sources),
      validated: true,
    },
  ];
}

// ─── POST Handler ───

export async function POST(request: Request) {
  let runIdForError = '';
  try {
    // Rate limit check
    const ip = getClientIp(request);
    const limit = apiRateLimiter.check(ip);
    if (!limit.allowed) {
      return withBacktestCors(request, NextResponse.json(
        { error: 'Rate limit exceeded' },
        {
          status: 429,
          headers: {
            'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
            'X-RateLimit-Remaining': '0',
          },
        },
      ));
    }

    const body = await request.json();
    const {
      strategyId = 'all',
      strategyIds: requestedStrategyIdsRaw,
      family: requestedFamilyRaw,
      tokenSymbol = 'all',
      mode = 'quick' as BacktestMode,
      dataScale: rawDataScale,
      includeFullResults = false,
      includeReport = true,
      // Evidence defaults ON so every run is auditable (manifest + report + trade CSV).
      includeEvidence = true,
      candles: clientCandles,
      runId: requestedRunId,
      manifestId: requestedManifestId,
      datasetManifestId: requestedDatasetManifestId,
      strictNoSynthetic = false,
      targetTradesPerStrategy = 5000,
      sourceTierPolicy = 'adaptive_tiered',
      cohort = 'baseline_90d',
    } = body;

    const dataScale = normalizeDataScale(rawDataScale);
    const sourcePolicy = normalizeSourcePolicy(body.sourcePolicy);
    const allowBirdeyeFallback = sourcePolicy === 'allow_birdeye_fallback';
    const lookbackHours = normalizeLookbackHours(body.lookbackHours);
    const historyCandles = lookbackHours; // 1h resolution
    const runId = typeof requestedRunId === 'string' && requestedRunId.trim()
      ? requestedRunId.trim()
      : makeRunId();
    runIdForError = runId;
    const manifestId = typeof requestedManifestId === 'string' && requestedManifestId.trim()
      ? requestedManifestId.trim()
      : `manifest-${runId}`;
    const stableDatasetManifestId = (() => {
      // Reuse cached datasets across UI runs to reduce free-tier rate limit pressure.
      const cohortTag = String(cohort || 'baseline_90d')
        .trim()
        .replace(/[^a-zA-Z0-9_-]+/g, '-')
        .slice(0, 64);
      return `datasets-${cohortTag}-${lookbackHours}-${dataScale}-${sourcePolicy}`;
    })();
    const activeDatasetManifestId = typeof requestedDatasetManifestId === 'string' && requestedDatasetManifestId.trim()
      ? requestedDatasetManifestId.trim()
      : stableDatasetManifestId;
    const requestedMaxCandles = typeof body.maxCandles === 'number'
      ? Math.max(120, Math.min(4000, Math.floor(body.maxCandles)))
      : null;
    const fetchBatchSize = typeof body.fetchBatchSize === 'number'
      ? Math.max(1, Math.min(8, Math.floor(body.fetchBatchSize)))
      : (dataScale === 'fast' ? 4 : 3);

    // Dataset sizing: "fast" keeps the UI snappy; "thorough" runs 200+ tokens.
    // maxTokens override lets callers push to 200+ for deep validation.
    const requestedMax = typeof body.maxTokens === 'number' ? Math.max(10, Math.min(500, body.maxTokens)) : null;
    const scaleCfg = dataScale === 'fast'
      ? {
          bluechipMaxTokens: requestedMax ? Math.min(requestedMax, 10) : Math.min(5, ALL_BLUECHIPS.length),
          memecoinMaxTokens: requestedMax ? Math.min(requestedMax, 20) : 10,
          bagsMaxTokens: requestedMax ? Math.min(requestedMax, 12) : 10,
          xstockMaxTokens: requestedMax ? Math.min(requestedMax, 10) : 5,
        }
      : {
          bluechipMaxTokens: requestedMax ?? 200,
          memecoinMaxTokens: requestedMax ?? 200,
          bagsMaxTokens: requestedMax ?? 200,
          xstockMaxTokens: requestedMax ? Math.min(requestedMax, 80) : 50,
        };
    const bagsCoverageThreshold = resolveCoverageThreshold({
      family: 'bags',
      dataScale,
      requestedMaxTokens: scaleCfg.bagsMaxTokens,
    });
    const bluechipCoverageThreshold = resolveCoverageThreshold({
      family: 'bluechip',
      dataScale,
      requestedMaxTokens: scaleCfg.bluechipMaxTokens,
    });

    const allRunResults: StrategyRunResult[] = [];
    let universeTimeouts = 0;
    let fallbacksTriggered = 0;
    let discoveryEndpointFailures = 0;

    // Evidence artifacts (trade ledger + dataset provenance). Stored in server cache for download.
    const evidenceRunId = includeEvidence ? makeRunId() : null;
    const evidenceDatasets = new Map<string, BacktestEvidenceDataset>();
    const evidenceTrades: BacktestEvidenceTradeRow[] = [];

    const onEvidence: EvidenceSink | undefined = includeEvidence && evidenceRunId
      ? ({ dataset, result, mode }) => {
          const key = dataset.mintAddress || `${dataset.tokenSymbol}:${dataset.pairAddress}`;
          if (!evidenceDatasets.has(key)) {
            evidenceDatasets.set(key, toEvidenceDataset(dataset));
          }

          const cfg = result.config;
          for (const t of result.trades) {
            evidenceTrades.push({
              strategyId: result.strategyId,
              mode,
              tokenSymbol: dataset.tokenSymbol,
              resultTokenSymbol: result.tokenSymbol,
              mintAddress: dataset.mintAddress,
              pairAddress: dataset.pairAddress,
              source: dataset.source,
              entryTime: t.entryTime,
              exitTime: t.exitTime,
              entryPrice: t.entryPrice,
              exitPrice: t.exitPrice,
              pnlPct: t.pnlPct,
              pnlNet: t.pnlNet,
              exitReason: t.exitReason,
              holdCandles: t.holdCandles,
              highWaterMark: t.highWaterMark,
              lowWaterMark: t.lowWaterMark,
              maxDrawdownPct: t.maxDrawdownPct,
              stopLossPct: cfg.stopLossPct,
              takeProfitPct: cfg.takeProfitPct,
              trailingStopPct: cfg.trailingStopPct,
              maxHoldCandles: cfg.maxHoldCandles,
              slippagePct: cfg.slippagePct,
              feePct: cfg.feePct,
              minScore: cfg.minScore,
              minLiquidityUsd: cfg.minLiquidityUsd,
            });
          }
        }
      : undefined;

    // Real-data universes are expensive to build; cache them per request.
    let memecoinUniverse:
      | { mints: string[]; datasets: HistoricalDataSet[]; sources: Set<OHLCVSource>; attempted: number }
      | null = null;
    let bagsUniverse:
      | { mints: string[]; datasets: HistoricalDataSet[]; sources: Set<OHLCVSource>; attempted: number }
      | null = null;

    const equityUniverses = new Map<
      string,
      { datasets: HistoricalDataSet[]; sources: Set<OHLCVSource>; attempted: number }
    >();

    const withTimeBudget = async <T,>(
      promise: Promise<T>,
      timeoutMs: number,
      timeoutMessage: string,
    ): Promise<T> => {
      // IMPORTANT: clear the timer when the promise resolves/rejects to prevent late unhandled
      // rejections that can crash the route handler and leave run status stuck at "running".
      const ms = Math.max(1000, Math.floor(timeoutMs || 0));
      return await new Promise<T>((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error(timeoutMessage)), ms);
        promise.then(
          (val) => {
            clearTimeout(timer);
            resolve(val);
          },
          (err) => {
            clearTimeout(timer);
            reject(err);
          },
        );
      });
    };

    const ensureMemecoinUniverse = async () => {
      if (memecoinUniverse) return memecoinUniverse;
      markBacktestRunPhase(runId, 'universe_discovery', 'Resolving memecoin dataset universe');
      const fromManifest = loadFamilyDatasetManifest(activeDatasetManifestId, 'memecoin');
      if (fromManifest && fromManifest.datasets.length > 0) {
        const manifestSources = new Set<OHLCVSource>(fromManifest.datasets.map((d) => d.source));
        memecoinUniverse = {
          mints: fromManifest.datasets.map((d) => d.mintAddress),
          datasets: fromManifest.datasets.slice(0, scaleCfg.memecoinMaxTokens),
          sources: manifestSources,
          attempted: fromManifest.manifest.attempted,
        };
        markBacktestDatasetBatch(runId, {
          attemptedDelta: 0,
          succeededDelta: 0,
          failedDelta: 0,
          activity: `Loaded memecoin dataset manifest (${memecoinUniverse.datasets.length} datasets)`,
        });
        return memecoinUniverse;
      }

      // Pull more candidate mints than we need (some will fail OHLCV fetch).
      // Memecoin pools are often new; fast mode allows shorter histories to increase coverage.
      // Memecoin strategies are most relevant in the first 6h-48h after launch; requiring long
      // histories collapses dataset coverage (most pools are very new). Keep a 12-candle minimum
      // (12h on 1h candles) so we can scale breadth while still using only real data.
      const minCandles = dataScale === 'fast' ? 12 : 48;
      const maxCandles = requestedMaxCandles ?? (dataScale === 'fast' ? Math.min(600, historyCandles) : historyCandles);

      // Prefer GeckoTerminal-driven universe so pair addresses are guaranteed to exist on Gecko.
      const geckoCandidateLimit = dataScale === 'fast'
        ? Math.min(160, Math.max(scaleCfg.memecoinMaxTokens * 2, 40))
        : Math.min(600, Math.max(scaleCfg.memecoinMaxTokens * 3, 180));
      const nowMs = Date.now();
      const minAgeMs = minCandles * 60 * 60 * 1000;
      let geckoPools: Awaited<ReturnType<typeof fetchGeckoSolanaPoolUniverse>> = [];
      try {
        geckoPools = await withTimeBudget(
          fetchGeckoSolanaPoolUniverse(geckoCandidateLimit, {
            minAgeMs,
            onProgress: ({ endpoint, page, pages, received }) => {
              if (received === 0) discoveryEndpointFailures += 1;
              heartbeatBacktestRun(
                runId,
                `Memecoin discovery ${endpoint} page ${page}/${pages} (received ${received})`,
              );
            },
          }),
          120_000,
          'Gecko memecoin universe discovery timed out',
        );
      } catch (err) {
        universeTimeouts += 1;
        fallbacksTriggered += 1;
        const message = err instanceof Error ? err.message : 'Gecko memecoin universe discovery failed';
        heartbeatBacktestRun(runId, `${message}; switching to DexScreener fallback`);
        geckoPools = [];
      }
      markBacktestDatasetBatch(runId, {
        attemptedDelta: 0,
        succeededDelta: 0,
        failedDelta: 0,
        activity: `Memecoin universe discovery complete (${geckoPools.length} pools)`,
      });
      const eligibleGeckoPools = geckoPools.filter((p) => {
        if (!p.createdAtMs || !Number.isFinite(p.createdAtMs)) return true; // unknown; allow
        return nowMs - p.createdAtMs >= minAgeMs;
      });

      const pools: GeckoPoolCandidate[] = eligibleGeckoPools.map((p) => ({
        baseMint: p.baseMint,
        baseSymbol: p.baseSymbol,
        poolAddress: p.poolAddress,
      }));
      let mints = pools.map((p) => p.baseMint);

      markBacktestRunPhase(runId, 'dataset_fetch', 'Fetching memecoin OHLCV datasets');
      let { datasets, sources, attempted } = await fetchDatasetsForPools(
        pools,
        scaleCfg.memecoinMaxTokens,
        {
          // Avoid hammering Birdeye when scaling up; GeckoTerminal OHLCV is primary.
          allowBirdeyeFallback,
          attemptBirdeyeIfCandlesBelow: minCandles,
          minCandles,
          maxCandles,
          resolution: '60',
        },
        fetchBatchSize,
        ({ attempted, succeeded, failed, context }) => {
          markBacktestDatasetBatch(runId, {
            attemptedDelta: attempted,
            succeededDelta: succeeded,
            failedDelta: failed,
            activity: `Memecoin ${context}`,
          });
        },
      );

      // Fallback: if GeckoTerminal pool discovery is down, try DexScreener-derived mints.
      if (datasets.length === 0) {
        fallbacksTriggered += 1;
        const candidateLimit = dataScale === 'fast'
          ? Math.min(240, Math.max(scaleCfg.memecoinMaxTokens * 12, 80))
          : Math.min(2000, Math.max(scaleCfg.memecoinMaxTokens * 30, 300));
        heartbeatBacktestRun(runId, `Memecoin fallback discovery via DexScreener (WSOL pairs, target=${candidateLimit})`);

        // Prefer pool candidates so we can skip per-mint DexScreener pair discovery.
        const fallbackPools = await fetchDexScreenerSolanaPoolUniverse(candidateLimit);
        if (fallbackPools.length > 0) {
          const fallback = await fetchDatasetsForPools(
            fallbackPools,
            scaleCfg.memecoinMaxTokens,
            {
              allowBirdeyeFallback,
              attemptBirdeyeIfCandlesBelow: minCandles,
              minCandles,
              maxCandles,
              resolution: '60',
            },
            fetchBatchSize,
            ({ attempted, succeeded, failed, context }) => {
              markBacktestDatasetBatch(runId, {
                attemptedDelta: attempted,
                succeededDelta: succeeded,
                failedDelta: failed,
                activity: `Memecoin fallback ${context}`,
              });
            },
          );

          mints = fallbackPools.map((p) => p.baseMint);
          datasets = fallback.datasets;
          sources = fallback.sources;
          attempted += fallback.attempted;
        }

        // Last-resort fallback: mint-only universe (slower; performs per-mint pair discovery).
        if (datasets.length === 0) {
          heartbeatBacktestRun(runId, `Memecoin fallback (last resort) via DexScreener token lists (${candidateLimit} mints)`);
          const fallbackMints = await fetchDexScreenerSolanaMintUniverse(candidateLimit);
          const fallback = await fetchDatasetsForMints(
            fallbackMints,
            scaleCfg.memecoinMaxTokens,
            (mint) => mint.slice(0, 6),
            {
              allowBirdeyeFallback,
              attemptBirdeyeIfCandlesBelow: minCandles,
              minCandles,
              maxCandles,
              resolution: '60',
            },
            fetchBatchSize,
            ({ attempted, succeeded, failed, context }) => {
              markBacktestDatasetBatch(runId, {
                attemptedDelta: attempted,
                succeededDelta: succeeded,
                failedDelta: failed,
                activity: `Memecoin fallback ${context}`,
              });
            },
          );

          mints = fallbackMints;
          datasets = fallback.datasets;
          sources = fallback.sources;
          attempted += fallback.attempted;
        }
      }

      memecoinUniverse = { mints, datasets, sources, attempted };
      persistFamilyDatasetManifest({
        manifestId: activeDatasetManifestId,
        family: 'memecoin',
        dataScale,
        sourcePolicy,
        lookbackHours,
        attempted,
        succeeded: datasets.length,
        skipped: Math.max(0, attempted - datasets.length),
        datasets,
      });
      return memecoinUniverse;
    };

    const ensureBagsUniverse = async () => {
      if (bagsUniverse) return bagsUniverse;
      const fromManifest = loadFamilyDatasetManifest(activeDatasetManifestId, 'bags');
      if (fromManifest && fromManifest.datasets.length > 0) {
        const manifestSources = new Set<OHLCVSource>(fromManifest.datasets.map((d) => d.source));
        const manifestDatasets = fromManifest.datasets.slice(0, scaleCfg.bagsMaxTokens);
        const manifestAttempted = Math.max(
          manifestDatasets.length,
          Math.floor(Number(fromManifest.manifest.attempted || 0)),
        );
        const manifestHealth = computeCoverageHealth(
          { attempted: manifestAttempted, succeeded: manifestDatasets.length },
          bagsCoverageThreshold,
        );
        if (manifestHealth.healthy) {
          bagsUniverse = {
            mints: fromManifest.datasets.map((d) => d.mintAddress),
            datasets: manifestDatasets,
            sources: manifestSources,
            attempted: fromManifest.manifest.attempted,
          };
          markBacktestDatasetBatch(runId, {
            attemptedDelta: 0,
            succeededDelta: 0,
            failedDelta: 0,
            activity: `Loaded bags dataset manifest (${bagsUniverse.datasets.length} datasets)`,
          });
          return bagsUniverse;
        }
        heartbeatBacktestRun(
          runId,
          `Bags manifest coverage low (${manifestDatasets.length} datasets, hit-rate ${(manifestHealth.hitRate * 100).toFixed(1)}%); rebuilding`,
        );
      }

      const minCandles = dataScale === 'fast' ? 12 : 48;
      const maxCandles = requestedMaxCandles ?? (dataScale === 'fast' ? Math.min(600, historyCandles) : historyCandles);
      const candidateLimit = dataScale === 'fast'
        ? Math.min(400, Math.max(scaleCfg.bagsMaxTokens * 6, 60))
        : Math.min(2000, Math.max(scaleCfg.bagsMaxTokens * 10, 300));
      const mints = await fetchBagsMintUniverse(candidateLimit);

      const initial = await fetchDatasetsForMints(
        mints,
        scaleCfg.bagsMaxTokens,
        (mint) => mint.slice(0, 6),
        {
          allowBirdeyeFallback,
          attemptBirdeyeIfCandlesBelow: minCandles,
          minCandles,
          maxCandles,
          resolution: '60',
        },
        dataScale === 'fast' ? Math.max(fetchBatchSize, 8) : fetchBatchSize,
        ({ attempted, succeeded, failed, context }) => {
          markBacktestDatasetBatch(runId, {
            attemptedDelta: attempted,
            succeededDelta: succeeded,
            failedDelta: failed,
            activity: `Bags ${context}`,
          });
        },
      );

      let datasets = initial.datasets;
      let sources = initial.sources;
      let attempted = initial.attempted;
      let health = computeCoverageHealth(
        { attempted, succeeded: datasets.length },
        bagsCoverageThreshold,
      );

      // Recovery pass: force fallback source + relaxed minimum depth when bags coverage is thin.
      if (!health.healthy) {
        heartbeatBacktestRun(
          runId,
          `Bags coverage below gate (${datasets.length}/${bagsCoverageThreshold.minDatasets}); retrying with fallback source`,
        );
        fallbacksTriggered += 1;
        const relaxedMinCandles = dataScale === 'fast' ? 8 : 24;
        const recovery = await fetchDatasetsForMints(
          mints,
          scaleCfg.bagsMaxTokens,
          (mint) => mint.slice(0, 6),
          {
            allowBirdeyeFallback: true,
            attemptBirdeyeIfCandlesBelow: relaxedMinCandles,
            minCandles: relaxedMinCandles,
            maxCandles,
            resolution: '60',
          },
          dataScale === 'fast' ? Math.max(fetchBatchSize, 8) : fetchBatchSize,
          ({ attempted, succeeded, failed, context }) => {
            markBacktestDatasetBatch(runId, {
              attemptedDelta: attempted,
              succeededDelta: succeeded,
              failedDelta: failed,
              activity: `Bags recovery ${context}`,
            });
          },
        );
        attempted += recovery.attempted;
        const byMint = new Map<string, HistoricalDataSet>();
        for (const ds of [...datasets, ...recovery.datasets]) {
          if (!byMint.has(ds.mintAddress)) {
            byMint.set(ds.mintAddress, ds);
          }
          if (byMint.size >= scaleCfg.bagsMaxTokens) break;
        }
        datasets = [...byMint.values()];
        sources = new Set<OHLCVSource>([...sources, ...recovery.sources]);
        health = computeCoverageHealth(
          { attempted, succeeded: datasets.length },
          bagsCoverageThreshold,
        );
      }

      if (!health.healthy) {
        throw new Error(
          `Bags coverage gate failed: datasets=${datasets.length}, attempted=${attempted}, hitRate=${(health.hitRate * 100).toFixed(1)}%, minDatasets=${bagsCoverageThreshold.minDatasets}`,
        );
      }

      bagsUniverse = { mints, datasets, sources, attempted };
      persistFamilyDatasetManifest({
        manifestId: activeDatasetManifestId,
        family: 'bags',
        dataScale,
        sourcePolicy,
        lookbackHours,
        attempted,
        succeeded: datasets.length,
        skipped: Math.max(0, attempted - datasets.length),
        datasets,
      });
      return bagsUniverse;
    };

    const equityGroupForStrategy = (sid: string): string => {
      if (sid.startsWith('xstock_')) return 'xstock';
      if (sid.startsWith('prestock_')) return 'prestock';
      if (sid.startsWith('index_')) return 'index';
      return 'xstock_index';
    };

    const ensureEquityUniverse = async (sid: string) => {
      const group = equityGroupForStrategy(sid);
      const cached = equityUniverses.get(group);
      if (cached) return cached;
      const manifestFamily: DatasetFamily =
        group === 'xstock' ? 'xstock' : group === 'prestock' ? 'prestock' : group === 'index' ? 'index' : 'xstock_index';
      const fromManifest = loadFamilyDatasetManifest(activeDatasetManifestId, manifestFamily);
      if (fromManifest && fromManifest.datasets.length > 0) {
        const manifestRes = {
          datasets: fromManifest.datasets.slice(0, scaleCfg.xstockMaxTokens),
          sources: new Set<OHLCVSource>(fromManifest.datasets.map((d) => d.source)),
          attempted: fromManifest.manifest.attempted,
        };
        equityUniverses.set(group, manifestRes);
        markBacktestDatasetBatch(runId, {
          attemptedDelta: 0,
          succeededDelta: 0,
          failedDelta: 0,
          activity: `Loaded ${manifestFamily} dataset manifest (${manifestRes.datasets.length} datasets)`,
        });
        return manifestRes;
      }

      const equities = equityUniverseForStrategy(sid).slice(0, scaleCfg.xstockMaxTokens);
      const tickerByMint = new Map(equities.map((e) => [e.mintAddress, e.ticker]));
      const mints = equities.map((e) => e.mintAddress);

      const { datasets, sources, attempted } = await fetchDatasetsForMints(
        mints,
        scaleCfg.xstockMaxTokens,
        (mint) => tickerByMint.get(mint) || mint.slice(0, 6),
        {
          allowBirdeyeFallback,
          attemptBirdeyeIfCandlesBelow: dataScale === 'fast' ? 50 : 120,
          minCandles: dataScale === 'fast' ? 50 : 120,
          maxCandles: requestedMaxCandles ?? (dataScale === 'fast' ? Math.min(600, historyCandles) : historyCandles),
          birdeyeLookbackDays: 365,
          resolution: '60',
        },
        fetchBatchSize,
        ({ attempted, succeeded, failed, context }) => {
          markBacktestDatasetBatch(runId, {
            attemptedDelta: attempted,
            succeededDelta: succeeded,
            failedDelta: failed,
            activity: `TradFi ${group} ${context}`,
          });
        },
      );

      const res = { datasets, sources, attempted };
      equityUniverses.set(group, res);
      persistFamilyDatasetManifest({
        manifestId: activeDatasetManifestId,
        family: manifestFamily,
        dataScale,
        sourcePolicy,
        lookbackHours,
        attempted,
        succeeded: datasets.length,
        skipped: Math.max(0, attempted - datasets.length),
        datasets,
      });
      return res;
    };

    // Determine which strategies to test.
    const familySet = new Set<RequestedFamily>(['memecoin', 'bags', 'bluechip', 'xstock', 'prestock', 'index', 'xstock_index']);
    const requestedFamilyCandidate =
      typeof requestedFamilyRaw === 'string' && requestedFamilyRaw.trim()
        ? requestedFamilyRaw.trim().toLowerCase()
        : '';
    if (requestedFamilyCandidate && !familySet.has(requestedFamilyCandidate as RequestedFamily)) {
      return withBacktestCors(request, NextResponse.json(
        {
          error: `Unknown family "${requestedFamilyRaw}"`,
          knownFamilies: [...familySet.values()],
        },
        { status: 400 },
      ));
    }
    const requestedFamily: RequestedFamily | null = requestedFamilyCandidate
      ? (requestedFamilyCandidate as RequestedFamily)
      : null;

    const requestedStrategyIds = Array.isArray(requestedStrategyIdsRaw)
      ? requestedStrategyIdsRaw
          .filter((v): v is string => typeof v === 'string' && v.trim().length > 0)
          .map((v) => v.trim())
      : [];

    let strategyIds: string[] = [];
    if (requestedStrategyIds.length > 0) {
      strategyIds = requestedStrategyIds;
    } else if (requestedFamily) {
      strategyIds = resolveStrategyIdsFromFamily(requestedFamily);
    } else {
      strategyIds = strategyId === 'all'
        ? orderStrategyIds(Object.keys(STRATEGY_CONFIGS))
        : [strategyId];
    }

    const unknownStrategyIds = strategyIds.filter((sid) => !STRATEGY_CONFIGS[sid]);
    if (unknownStrategyIds.length > 0) {
      return withBacktestCors(request, NextResponse.json(
        {
          error: `Unknown strategyIds: ${unknownStrategyIds.join(', ')}`,
          knownStrategies: Object.keys(STRATEGY_CONFIGS),
        },
        { status: 400 },
      ));
    }

    if (strategyIds.length === 0) {
      return withBacktestCors(request, NextResponse.json(
        { error: 'No strategies resolved for request' },
        { status: 400 },
      ));
    }

    const livenessBudgetSec = mode === 'quick' && dataScale === 'fast' ? 15 * 60 : 45 * 60;

    createBacktestRunStatus({
      runId,
      manifestId,
      strategyIds,
      strictNoSynthetic: !!strictNoSynthetic,
      targetTradesPerStrategy: Number(targetTradesPerStrategy) || 5000,
      sourceTierPolicy: String(sourceTierPolicy || 'adaptive_tiered'),
      cohort: String(cohort || 'baseline_90d'),
      livenessBudgetSec,
    });
    heartbeatBacktestRun(runId, `Initialized run with ${strategyIds.length} strategy chunks`);

    for (const sid of strategyIds) {
      const config = STRATEGY_CONFIGS[sid];
      if (!config) continue;

      const entrySignal = ENTRY_SIGNALS[sid] || momentumEntry;
      const category = STRATEGY_CATEGORY[sid] || 'xstock_index';
      markBacktestChunkRunning(runId, sid);
      heartbeatBacktestRun(runId, `Running ${sid} (${category})`);
      try {
        // If client provided candles, use those directly (override data source logic)
        if (clientCandles) {
          heartbeatBacktestRun(runId, `Using client candles for ${sid}`);
          const results = runStrategy(sid, config, clientCandles, tokenSymbol, mode, entrySignal);
          for (const result of results) {
            allRunResults.push({
              result,
              dataSource: 'client',
              validated: false,
            });
          }
          markBacktestChunkDone(runId, sid);
          continue;
        }

        // Route to appropriate data source based on strategy category
        switch (category) {
          case 'bluechip': {
            markBacktestRunPhase(runId, 'dataset_fetch', `Fetching bluechip datasets for ${sid}`);
            const bluechipResults = await runBluechipStrategy(
              sid,
              config,
              entrySignal,
              mode,
              tokenSymbol,
              scaleCfg.bluechipMaxTokens,
              {
                allowBirdeyeFallback,
                maxCandles: requestedMaxCandles ?? (dataScale === 'fast' ? Math.min(600, historyCandles) : historyCandles),
                minCandles: dataScale === 'fast' ? 50 : 120,
                fetchBatchSize,
                minDatasetsRequired: bluechipCoverageThreshold.minDatasets,
              },
              onEvidence,
              ({ attempted, succeeded, failed, context }) => {
                markBacktestDatasetBatch(runId, {
                  attemptedDelta: attempted,
                  succeededDelta: succeeded,
                  failedDelta: failed,
                  activity: `Bluechip ${context}`,
                });
              },
            );
            allRunResults.push(...bluechipResults);
            heartbeatBacktestRun(runId, `Completed ${sid} on ${bluechipResults.length} bluechip result rows`);
            break;
          }
          case 'memecoin': {
            heartbeatBacktestRun(runId, `Building memecoin universe for ${sid}`);
            const universe = await ensureMemecoinUniverse();
            // Help TS control-flow narrowing: assignments inside closures are not tracked in the outer function.
            memecoinUniverse = universe;
            const memeResults = await runMemecoinStrategyReal(
              sid,
              config,
              entrySignal,
              mode,
              scaleCfg.memecoinMaxTokens,
              universe.datasets,
              universe.sources,
              onEvidence,
            );
            allRunResults.push(...memeResults);
            heartbeatBacktestRun(
              runId,
              `Completed ${sid} using ${universe.datasets.length} memecoin datasets (attempted ${universe.attempted})`,
            );
            break;
          }
          case 'bags': {
            heartbeatBacktestRun(runId, `Building bags universe for ${sid}`);
            const universe = await ensureBagsUniverse();
            bagsUniverse = universe;
            const bagsResults = await runMemecoinStrategyReal(
              sid,
              config,
              entrySignal,
              mode,
              scaleCfg.bagsMaxTokens,
              universe.datasets,
              universe.sources,
              onEvidence,
            );
            allRunResults.push(...bagsResults);
            heartbeatBacktestRun(
              runId,
              `Completed ${sid} using ${universe.datasets.length} bags datasets (attempted ${universe.attempted})`,
            );
            break;
          }
          case 'xstock_index': {
            heartbeatBacktestRun(runId, `Building tradfi universe for ${sid}`);
            const universe = await ensureEquityUniverse(sid);
            const xstockResults = await runXstockIndexStrategyReal(
              sid,
              config,
              entrySignal,
              mode,
              scaleCfg.xstockMaxTokens,
              universe.datasets,
              universe.sources,
              onEvidence,
            );
            allRunResults.push(...xstockResults);
            heartbeatBacktestRun(
              runId,
              `Completed ${sid} using ${universe.datasets.length} tradfi datasets (attempted ${universe.attempted})`,
            );
            break;
          }
        }
        markBacktestChunkDone(runId, sid);
      } catch (err) {
        const message = err instanceof Error ? err.message : `Strategy ${sid} failed`;
        heartbeatBacktestRun(runId, `Chunk failed for ${sid}: ${message}`);
        markBacktestChunkFailed(runId, sid, message);
      }
    }

    if (!clientCandles && allRunResults.length === 0) {
      failBacktestRun(runId, 'No usable real-data datasets for requested strategy/source');
      return withBacktestCors(request, NextResponse.json(
        {
          error: 'Backtest produced no results (no usable real-data datasets for requested strategy/source)',
          runId,
          meta: {
            dataScale,
            sourcePolicy,
            lookbackHours,
            family: requestedFamily,
            datasetManifestId: activeDatasetManifestId,
            requestedMaxTokens: requestedMax,
            strategyId,
            memecoinCandidates: memecoinUniverse?.mints?.length ?? 0,
            memecoinDatasetsUsed: memecoinUniverse?.datasets?.length ?? 0,
            bagsCandidates: bagsUniverse?.mints?.length ?? 0,
            bagsDatasetsUsed: bagsUniverse?.datasets?.length ?? 0,
          },
        },
        { status: 422 },
      ));
    }

    if (strictNoSynthetic) {
      const disallowed = allRunResults.filter((r) => r.dataSource === 'client' || !r.dataSource);
      if (disallowed.length > 0) {
        failBacktestRun(runId, 'strictNoSynthetic gate failed: non-real data source detected');
        return withBacktestCors(request, NextResponse.json(
          {
            error: 'strictNoSynthetic gate failed: non-real data source detected',
            runId,
            disallowedSources: disallowed.map((d) => d.dataSource),
          },
          { status: 422 },
        ));
      }
    }

    // Extract BacktestResult array for report generation
    const results = allRunResults.map(r => r.result);

    // Generate report (optional, and capped to avoid huge payloads).
    const report = includeReport && results.length <= 250
      ? generateBacktestReport(results)
      : null;

    // Summary stats with validation metadata
    const summary = allRunResults.map((r) => {
      const winRatePct = r.result.winRate * 100;
      const existingCi = Array.isArray((r.result as any).winRateCI95)
        ? (r.result as any).winRateCI95 as [number, number]
        : null;
      const bounds = existingCi
        ? { lower: Number(existingCi[0] || 0) * 100, upper: Number(existingCi[1] || 0) * 100 }
        : wilsonBoundsPctFromCounts(r.result.wins, r.result.totalTrades);
      const netPnlPct = Number((r.result.avgReturnPct || 0) * (r.result.totalTrades || 0));

      return {
        strategyId: r.result.strategyId,
        token: r.result.tokenSymbol,
        trades: r.result.totalTrades,
        winRate: `${winRatePct.toFixed(1)}%`,
        winRatePct: Number(winRatePct.toFixed(4)),
        winRateLower95Pct: Number(bounds.lower.toFixed(4)),
        winRateUpper95Pct: Number(bounds.upper.toFixed(4)),
        netPnlPct: Number(netPnlPct.toFixed(4)),
        profitFactor: r.result.profitFactor.toFixed(2),
        profitFactorValue: Number((r.result.profitFactor || 0).toFixed(6)),
        sharpe: r.result.sharpeRatio.toFixed(2),
        maxDD: `${r.result.maxDrawdownPct.toFixed(1)}%`,
        expectancy: r.result.expectancy.toFixed(4),
        avgHold: `${r.result.avgHoldCandles.toFixed(0)}h`,
        validated: r.validated,
        dataSource: r.dataSource,
      };
    });

    // Detect underperformers: win rate < 40% OR profit factor < 1.0
    const underperformers = allRunResults
      .filter(r => r.result.winRate < 0.40 || r.result.profitFactor < 1.0)
      .map(r => r.result.strategyId);
    // Deduplicate
    const uniqueUnderperformers = [...new Set(underperformers)];

    const equityAttempted = [...equityUniverses.values()].reduce((s, v) => s + (v.attempted || 0), 0);
    const equitySucceeded = [...equityUniverses.values()].reduce((s, v) => s + v.datasets.length, 0);
    const computedDatasetsAttempted = (memecoinUniverse?.attempted ?? 0) + (bagsUniverse?.attempted ?? 0) + equityAttempted;
    const computedDatasetsSucceeded = (memecoinUniverse?.datasets?.length ?? 0) + (bagsUniverse?.datasets?.length ?? 0) + equitySucceeded;
    const runDiag = getBacktestRunStatus(runId);
    const datasetsAttempted = (runDiag?.datasetsAttempted ?? 0) > 0 ? (runDiag?.datasetsAttempted ?? 0) : computedDatasetsAttempted;
    const datasetsSucceeded = (runDiag?.datasetsSucceeded ?? 0) > 0 ? (runDiag?.datasetsSucceeded ?? 0) : computedDatasetsSucceeded;
    const datasetsSkipped = Math.max(0, datasetsAttempted - datasetsSucceeded);
    const sourceDiagnosticsExpanded = {
      geckoterminal: [...evidenceDatasets.values()].filter((d) => d.source === 'geckoterminal').length,
      birdeye: [...evidenceDatasets.values()].filter((d) => d.source === 'birdeye').length,
      mixed: allRunResults.filter((r) => r.dataSource === 'mixed').length,
      client: allRunResults.filter((r) => r.dataSource === 'client').length,
    };

    const meta = {
        dataScale,
        sourcePolicy,
        lookbackHours,
        family: requestedFamily,
        datasetManifestId: activeDatasetManifestId,
        requestedMaxTokens: requestedMax,
        bluechipMaxTokens: scaleCfg.bluechipMaxTokens,
        bluechipHardcoded: ALL_BLUECHIPS.length,
        memecoinMaxTokens: scaleCfg.memecoinMaxTokens,
        memecoinCandidates: memecoinUniverse?.mints?.length ?? 0,
        memecoinDatasetsUsed: memecoinUniverse?.datasets?.length ?? 0,
        bagsMaxTokens: scaleCfg.bagsMaxTokens,
        bagsCandidates: bagsUniverse?.mints?.length ?? 0,
        bagsDatasetsUsed: bagsUniverse?.datasets?.length ?? 0,
        xstockMaxTokens: scaleCfg.xstockMaxTokens,
        xstockDatasetsUsed: [...equityUniverses.values()].reduce((s, v) => s + v.datasets.length, 0),
        datasetsAttempted,
        datasetsSucceeded,
        datasetsSkipped,
        sourceDiagnosticsExpanded,
        totalResults: allRunResults.length,
      };

    if (includeEvidence && evidenceRunId) {
      heartbeatBacktestRun(runId, 'Persisting evidence artifacts');
      const bundle: BacktestEvidenceBundle = {
        runId: evidenceRunId,
        generatedAt: new Date().toISOString(),
        request: {
          strategyId,
          tokenSymbol,
          mode,
          dataScale,
          sourcePolicy,
          lookbackHours,
        },
        meta,
        datasets: [...evidenceDatasets.values()],
        trades: evidenceTrades,
        reportMd: report,
        resultsSummary: summary,
      };
      putBacktestEvidence(bundle);
      // Long-lived artifacts for research/tuning runs (best-effort).
      persistBacktestArtifacts(bundle);
      heartbeatBacktestRun(runId, 'Evidence artifacts persisted');
    }

    const artifactsPath = includeEvidence && evidenceRunId
      ? `.jarvis-cache/backtest-runs/${evidenceRunId}/manifest.json`
      : undefined;
    finalizeBacktestRun(runId, {
      evidenceRunId: evidenceRunId || undefined,
      artifactsPath,
    });
    heartbeatBacktestRun(runId, 'Run completed');
    const runStatus = getBacktestRunStatus(runId);

    return withBacktestCors(request, NextResponse.json({
      meta,
      runId,
      manifestId,
      progress: runStatus?.progress ?? 100,
      completedChunks: runStatus?.completedChunks ?? strategyIds.length,
      failedChunks: runStatus?.failedChunks ?? 0,
      datasetsAttempted: runStatus?.datasetsAttempted ?? datasetsAttempted,
      datasetsSucceeded: runStatus?.datasetsSucceeded ?? datasetsSucceeded,
      datasetsFailed: runStatus?.datasetsFailed ?? Math.max(0, datasetsAttempted - datasetsSucceeded),
      sourceDiagnostics: {
        sourceTierPolicy: String(sourceTierPolicy || 'adaptive_tiered'),
        strictNoSynthetic: !!strictNoSynthetic,
        targetTradesPerStrategy: Number(targetTradesPerStrategy) || 5000,
        cohort: String(cohort || 'baseline_90d'),
        datasetsAttempted,
        datasetsSucceeded,
        datasetsSkipped,
        sourceDiagnosticsExpanded,
      },
      results: summary,
      report,
      evidence: includeEvidence && evidenceRunId
        ? {
            runId: evidenceRunId,
            datasetCount: evidenceDatasets.size,
            tradeCount: evidenceTrades.length,
          }
        : null,
      underperformers: uniqueUnderperformers,
      fullResults: includeFullResults
        ? results.map(r => ({
            ...r,
            trades: r.trades.slice(0, 50), // Limit trade details
            equityCurve: r.equityCurve.slice(-100), // Last 100 points
          }))
        : [],
    }));
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Backtest failed';
    if (runIdForError) {
      failBacktestRun(runIdForError, message);
    }
    return withBacktestCors(request, NextResponse.json(
      { error: message, runId: runIdForError || null },
      { status: 500 }
    ));
  }
}
