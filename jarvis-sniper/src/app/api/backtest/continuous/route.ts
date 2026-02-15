import { NextResponse } from 'next/server';
import {
  BacktestEngine,
  meanReversionEntry,
  trendFollowingEntry,
  breakoutEntry,
  momentumEntry,
  squeezeBreakoutEntry,
  type BacktestConfig,
  type BacktestResult,
  type OHLCVCandle,
} from '@/lib/backtest-engine';
import { ALL_BLUECHIPS } from '@/lib/bluechip-data';
import { fetchGeckoSolanaPoolUniverse } from '@/lib/gecko-universe';
import { fetchTokenHistory, fetchMintHistory } from '@/lib/historical-data';
import { XSTOCKS, PRESTOCKS, INDEXES, COMMODITIES_TOKENS, type TokenizedEquity } from '@/lib/xstocks-data';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';

// Uses Node.js runtime for caching + filesystem-friendly execution.
export const runtime = 'nodejs';

/**
 * Continuous Backtesting API Route — Daily strategy drift detection
 *
 * POST /api/backtest/continuous
 * Body (optional): {
 *   strategies?: string[],   // Strategy IDs to test (default: all 18)
 *   threshold?: number,      // Minimum acceptable win rate (default: 0.45)
 * }
 *
 * Runs all strategies against the latest available data and produces a
 * drift report classifying each as healthy / degraded / failing.
 *
 * Designed to be called by a cron job or manual trigger, not by the UI
 * polling loop. Intentionally POST (side-effectful: fetches fresh data,
 * runs compute-heavy backtests).
 *
 * Fulfills: BACK-04 (Continuous Strategy Validation)
 */

// Allow up to 300 seconds for Vercel serverless (full run can be compute-heavy)
export const maxDuration = 300;

// ─── Strategy Classification ───

type StrategyCategory = 'bluechip' | 'memecoin' | 'xstock_index';

const STRATEGY_CATEGORY: Record<string, StrategyCategory> = {
  // Blue chip strategies
  bluechip_trend_follow: 'bluechip',
  bluechip_breakout: 'bluechip',
  // Memecoin strategies
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
  // xStock / index / prestock
  xstock_intraday: 'xstock_index',
  xstock_swing: 'xstock_index',
  prestock_speculative: 'xstock_index',
  index_intraday: 'xstock_index',
  index_leveraged: 'xstock_index',
};

// Entry signals — R4 realistic-TP (2026-02-15)
const ENTRY_SIGNALS: Record<string, BacktestConfig['entrySignal']> = {
  // Memecoin core
  elite: momentumEntry,
  pump_fresh_tight: momentumEntry,
  micro_cap_surge: momentumEntry,
  // Memecoin wide
  momentum: meanReversionEntry,
  hybrid_b: meanReversionEntry,
  let_it_ride: meanReversionEntry,
  // Established
  sol_veteran: meanReversionEntry,
  utility_swing: meanReversionEntry,
  established_breakout: meanReversionEntry,
  meme_classic: meanReversionEntry,
  volume_spike: meanReversionEntry,
  // Bluechip
  bluechip_trend_follow: meanReversionEntry,
  bluechip_breakout: meanReversionEntry,
  // xStock / Index / Prestock
  xstock_intraday: meanReversionEntry,
  xstock_swing: meanReversionEntry,
  prestock_speculative: meanReversionEntry,
  index_intraday: meanReversionEntry,
  index_leveraged: meanReversionEntry,
};

// Strategy configs — R4 realistic-TP optimized (2026-02-15)
const STRATEGY_CONFIGS: Record<string, Omit<BacktestConfig, 'entrySignal'>> = {
  // Memecoin core (SL 10%, TP 20%)
  elite: { strategyId: 'elite', stopLossPct: 10, takeProfitPct: 20, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 100000, slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 12 },
  pump_fresh_tight: { strategyId: 'pump_fresh_tight', stopLossPct: 10, takeProfitPct: 20, trailingStopPct: 99, minScore: 40, minLiquidityUsd: 5000, slippagePct: 1.0, feePct: 0.25, maxHoldCandles: 8 },
  micro_cap_surge: { strategyId: 'micro_cap_surge', stopLossPct: 10, takeProfitPct: 20, trailingStopPct: 99, minScore: 30, minLiquidityUsd: 3000, slippagePct: 1.5, feePct: 0.25, maxHoldCandles: 8 },
  // Memecoin wide (SL 10%, TP 25%)
  momentum: { strategyId: 'momentum', stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 50000, slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 24 },
  hybrid_b: { strategyId: 'hybrid_b', stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 50000, slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 24 },
  let_it_ride: { strategyId: 'let_it_ride', stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 50000, slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 48 },
  // Established (SL 8%, TP 15%)
  sol_veteran: { strategyId: 'sol_veteran', stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99, minScore: 40, minLiquidityUsd: 50000, slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 168 },
  utility_swing: { strategyId: 'utility_swing', stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99, minScore: 55, minLiquidityUsd: 10000, slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 168 },
  established_breakout: { strategyId: 'established_breakout', stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99, minScore: 30, minLiquidityUsd: 10000, slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 168 },
  meme_classic: { strategyId: 'meme_classic', stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99, minScore: 40, minLiquidityUsd: 5000, slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 168 },
  volume_spike: { strategyId: 'volume_spike', stopLossPct: 8, takeProfitPct: 15, trailingStopPct: 99, minScore: 35, minLiquidityUsd: 20000, slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 168 },
  // Bluechip (SL 10%, TP 25%)
  bluechip_trend_follow: { strategyId: 'bluechip_trend_follow', stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 50000, slippagePct: 0.3, feePct: 0.25, maxHoldCandles: 48 },
  bluechip_breakout: { strategyId: 'bluechip_breakout', stopLossPct: 10, takeProfitPct: 25, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 50000, slippagePct: 0.3, feePct: 0.25, maxHoldCandles: 48 },
  // xStock / Prestock / Index (SL 4%, TP 10%)
  xstock_intraday: { strategyId: 'xstock_intraday', stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 10000, slippagePct: 0.2, feePct: 0.25, maxHoldCandles: 96 },
  xstock_swing: { strategyId: 'xstock_swing', stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 10000, slippagePct: 0.2, feePct: 0.25, maxHoldCandles: 96 },
  prestock_speculative: { strategyId: 'prestock_speculative', stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99, minScore: 30, minLiquidityUsd: 5000, slippagePct: 0.3, feePct: 0.25, maxHoldCandles: 96 },
  index_intraday: { strategyId: 'index_intraday', stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 10000, slippagePct: 0.15, feePct: 0.25, maxHoldCandles: 96 },
  index_leveraged: { strategyId: 'index_leveraged', stopLossPct: 4, takeProfitPct: 10, trailingStopPct: 99, minScore: 0, minLiquidityUsd: 10000, slippagePct: 0.2, feePct: 0.25, maxHoldCandles: 96 },
};

// ─── Drift Report Types ───

interface StrategyHealthResult {
  strategyId: string;
  winRate: number;
  profitFactor: number;
  totalTrades: number;
  status: 'healthy' | 'degraded' | 'failing';
}

interface ContinuousBacktestReport {
  timestamp: string;
  strategiesRun: number;
  results: StrategyHealthResult[];
  alerts: string[];
  overallHealth: 'green' | 'yellow' | 'red';
}

// ─── Data Fetching Helpers ───

const DEXSCREENER_BOOSTS = 'https://api.dexscreener.com/token-boosts/latest/v1';
const DEXSCREENER_PROFILES = 'https://api.dexscreener.com/token-profiles/latest/v1';
const DEXSCREENER_SOL_PAIRS =
  'https://api.dexscreener.com/latest/dex/tokens/So11111111111111111111111111111111111111112';

async function fetchWithTimeout(url: string, timeoutMs = 8000): Promise<Response> {
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

async function fetchDexScreenerSolanaMintUniverse(limit: number): Promise<string[]> {
  const out: string[] = [];
  const seen = new Set<string>();

  const push = (mint: string | undefined | null) => {
    if (!mint) return;
    if (mint === 'So11111111111111111111111111111111111111112') return;
    if (seen.has(mint)) return;
    seen.add(mint);
    out.push(mint);
  };

  const [boostsRes, profilesRes, solPairsRes] = await Promise.allSettled([
    fetchWithTimeout(DEXSCREENER_BOOSTS),
    fetchWithTimeout(DEXSCREENER_PROFILES),
    fetchWithTimeout(DEXSCREENER_SOL_PAIRS),
  ]);

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

  if (solPairsRes.status === 'fulfilled' && solPairsRes.value.ok) {
    try {
      const json = await solPairsRes.value.json();
      const pairs: any[] = json?.pairs || [];
      for (const pair of pairs) {
        push(pair?.baseToken?.address);
        if (out.length >= limit) return out.slice(0, limit);
      }
    } catch {
      // ignore
    }
  }

  return out.slice(0, limit);
}

function equityUniverseForStrategy(strategyId: string): TokenizedEquity[] {
  if (strategyId.startsWith('xstock_')) return XSTOCKS;
  if (strategyId.startsWith('prestock_')) return PRESTOCKS;
  if (strategyId.startsWith('index_')) return [...INDEXES, ...COMMODITIES_TOKENS];
  return [...XSTOCKS, ...PRESTOCKS, ...INDEXES, ...COMMODITIES_TOKENS];
}

type GeckoPoolCandidate = {
  baseMint: string;
  baseSymbol: string;
  poolAddress: string;
};

async function fetchDatasetsForPools(
  pools: GeckoPoolCandidate[],
  maxDatasets: number,
  options: Parameters<typeof fetchMintHistory>[2],
  batchSize = 3,
): Promise<{ datasets: { symbol: string; candles: OHLCVCandle[] }[]; attempted: number }> {
  const datasets: { symbol: string; candles: OHLCVCandle[] }[] = [];
  let attempted = 0;

  for (let i = 0; i < pools.length && datasets.length < maxDatasets; i += batchSize) {
    const batch = pools.slice(i, i + batchSize);
    attempted += batch.length;

    const settled = await Promise.allSettled(
      batch.map((p) =>
        fetchMintHistory(p.baseMint, p.baseSymbol || p.baseMint.slice(0, 6), {
          ...options,
          pairAddressOverride: p.poolAddress,
        }),
      ),
    );

    for (const s of settled) {
      if (s.status !== 'fulfilled') continue;
      datasets.push({ symbol: s.value.tokenSymbol, candles: s.value.candles });
      if (datasets.length >= maxDatasets) break;
    }
  }

  return { datasets, attempted };
}

async function fetchDatasetsForMints(
  mints: string[],
  maxDatasets: number,
  tokenSymbolForMint: (mint: string) => string,
  options: Parameters<typeof fetchMintHistory>[2],
  batchSize = 3,
): Promise<{ mints: string[]; datasets: { symbol: string; candles: OHLCVCandle[] }[]; attempted: number }> {
  const datasets: { symbol: string; candles: OHLCVCandle[] }[] = [];
  let attempted = 0;

  for (let i = 0; i < mints.length && datasets.length < maxDatasets; i += batchSize) {
    const batch = mints.slice(i, i + batchSize);
    attempted += batch.length;

    const settled = await Promise.allSettled(
      batch.map((mint) => fetchMintHistory(mint, tokenSymbolForMint(mint), options)),
    );

    for (const s of settled) {
      if (s.status !== 'fulfilled') continue;
      datasets.push({ symbol: s.value.tokenSymbol, candles: s.value.candles });
      if (datasets.length >= maxDatasets) break;
    }
  }

  return { mints, datasets, attempted };
}

function aggregateHealth(results: BacktestResult[]): { totalTrades: number; winRate: number; profitFactor: number } {
  let totalTrades = 0;
  let wins = 0;
  let winningPnl = 0;
  let losingPnl = 0;

  for (const r of results) {
    totalTrades += r.totalTrades;
    wins += r.wins;
    for (const t of r.trades) {
      if (t.pnlNet > 0) winningPnl += t.pnlNet;
      else losingPnl += Math.abs(t.pnlNet);
    }
  }

  const winRate = totalTrades > 0 ? wins / totalTrades : 0;
  const rawPF = losingPnl > 0 ? winningPnl / losingPnl : (winningPnl > 0 ? 999 : 0);
  const profitFactor = Math.min(rawPF, 999);

  return { totalTrades, winRate, profitFactor };
}

function runQuickStrategy(
  strategyId: string,
  config: Omit<BacktestConfig, 'entrySignal'>,
  candles: OHLCVCandle[],
  tokenSymbol: string,
): BacktestResult {
  const entrySignal = ENTRY_SIGNALS[strategyId] || momentumEntry;
  const fullConfig: BacktestConfig = { ...config, entrySignal };
  const engine = new BacktestEngine(candles, fullConfig);
  return engine.run(tokenSymbol);
}

// ─── POST Handler ───

export async function POST(request: Request) {
  const startTime = Date.now();

  try {
    // Rate limit check (strict: backtest is compute-heavy)
    const ip = getClientIp(request);
    const limit = apiRateLimiter.check(ip);
    if (!limit.allowed) {
      return NextResponse.json(
        { error: 'Rate limit exceeded', timestamp: new Date().toISOString() },
        {
          status: 429,
          headers: {
            'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
            'X-RateLimit-Remaining': '0',
          },
        },
      );
    }

    let strategies: string[] | undefined;
    let threshold = 0.45;

    try {
      const body = await request.json();
      strategies = body.strategies;
      if (typeof body.threshold === 'number') {
        threshold = body.threshold;
      }
    } catch {
      // Empty body is fine -- use defaults
    }

    // Determine which strategies to run
    const strategyIds = strategies && strategies.length > 0
      ? strategies.filter(id => STRATEGY_CONFIGS[id])
      : Object.keys(STRATEGY_CONFIGS);

    const healthResults: StrategyHealthResult[] = [];
    const alerts: string[] = [];

    // Per-request caches for expensive upstream calls.
    let bluechipCache: { datasets: { symbol: string; candles: OHLCVCandle[] }[] } | null = null;
    let memecoinCache:
      | { datasets: { symbol: string; candles: OHLCVCandle[] }[]; attempted: number; candidates: number }
      | null = null;
    const equityCache = new Map<string, { datasets: { symbol: string; candles: OHLCVCandle[] }[]; attempted: number }>();

    const ensureBluechipDatasets = async () => {
      if (bluechipCache) return bluechipCache;
      const tokens = ALL_BLUECHIPS.slice(0, 3);
      const settled = await Promise.allSettled(tokens.map((t) => fetchTokenHistory(t)));
      const datasets: { symbol: string; candles: OHLCVCandle[] }[] = [];
      for (let i = 0; i < tokens.length; i++) {
        const s = settled[i];
        if (s.status !== 'fulfilled') continue;
        datasets.push({ symbol: tokens[i].ticker, candles: s.value.candles });
      }
      bluechipCache = { datasets };
      return bluechipCache;
    };

    const ensureMemecoinDatasets = async () => {
      if (memecoinCache) return memecoinCache;

      const nowMs = Date.now();
      const minAgeMs = 50 * 60 * 60 * 1000; // minCandles (1h) => hours of history required
      const geckoCandidates = await fetchGeckoSolanaPoolUniverse(120, { minAgeMs });
      const eligible = geckoCandidates.filter((p) => {
        if (!p.createdAtMs) return true;
        return nowMs - p.createdAtMs >= minAgeMs;
      });

      const pools: GeckoPoolCandidate[] = eligible.map((p) => ({
        baseMint: p.baseMint,
        baseSymbol: p.baseSymbol,
        poolAddress: p.poolAddress,
      }));

      let { datasets, attempted } = await fetchDatasetsForPools(
        pools,
        12,
        {
          allowBirdeyeFallback: false,
          attemptBirdeyeIfCandlesBelow: 50,
          minCandles: 50,
          maxCandles: 600,
        },
        3,
      );

      // Fallback to DexScreener universe if GeckoTerminal discovery is down.
      let candidates = pools.map((p) => p.baseMint);
      if (datasets.length === 0) {
        const fallbackMints = await fetchDexScreenerSolanaMintUniverse(80);
        const fallback = await fetchDatasetsForMints(
          fallbackMints,
          12,
          (mint) => mint.slice(0, 6),
          {
            allowBirdeyeFallback: false,
            attemptBirdeyeIfCandlesBelow: 50,
            minCandles: 50,
            maxCandles: 600,
          },
          3,
        );
        candidates = fallbackMints;
        datasets = fallback.datasets;
        attempted += fallback.attempted;
      }

      memecoinCache = { datasets, attempted, candidates: candidates.length };
      return memecoinCache;
    };

    const equityGroupForStrategy = (sid: string): string => {
      if (sid.startsWith('xstock_')) return 'xstock';
      if (sid.startsWith('prestock_')) return 'prestock';
      if (sid.startsWith('index_')) return 'index';
      return 'xstock_index';
    };

    const ensureEquityDatasets = async (sid: string) => {
      const group = equityGroupForStrategy(sid);
      const cached = equityCache.get(group);
      if (cached) return cached;

      const equities = equityUniverseForStrategy(sid).slice(0, 10);
      const tickerByMint = new Map(equities.map((e) => [e.mintAddress, e.ticker]));
      const mints = equities.map((e) => e.mintAddress);

      const { datasets, attempted } = await fetchDatasetsForMints(
        mints,
        equities.length,
        (mint) => tickerByMint.get(mint) || mint.slice(0, 6),
        {
          allowBirdeyeFallback: true,
          attemptBirdeyeIfCandlesBelow: 50,
          minCandles: 50,
          birdeyeLookbackDays: 365,
        },
        3,
      );

      const res = { datasets, attempted };
      equityCache.set(group, res);
      return res;
    };

    // Run strategies sequentially to avoid memory pressure
    for (let i = 0; i < strategyIds.length; i++) {
      const sid = strategyIds[i];
      const config = STRATEGY_CONFIGS[sid];
      const category = STRATEGY_CATEGORY[sid] || 'xstock_index';

      console.log(`[continuous-backtest] Running ${sid} (${i + 1}/${strategyIds.length}) [${category}]`);

      try {
        let datasets: { symbol: string; candles: OHLCVCandle[] }[] = [];

        if (category === 'bluechip') {
          datasets = (await ensureBluechipDatasets()).datasets;
        } else if (category === 'memecoin') {
          const mc = await ensureMemecoinDatasets();
          datasets = mc.datasets;
          if (mc.datasets.length < 6) {
            alerts.push(`${sid}: memecoin datasets low (${mc.datasets.length}/${mc.candidates} candidates, attempted=${mc.attempted})`);
          }
        } else {
          const eq = await ensureEquityDatasets(sid);
          datasets = eq.datasets;
          if (eq.datasets.length < 3) {
            alerts.push(`${sid}: equity datasets low (${eq.datasets.length}, attempted=${eq.attempted})`);
          }
        }

        if (datasets.length === 0) {
          alerts.push(`${sid}: No data available`);
          healthResults.push({
            strategyId: sid,
            winRate: 0,
            profitFactor: 0,
            totalTrades: 0,
            status: 'failing',
          });
          continue;
        }

        const perAsset = datasets.map((d) => runQuickStrategy(sid, config, d.candles, d.symbol));
        const agg = aggregateHealth(perAsset);

        // Classify health
        let status: 'healthy' | 'degraded' | 'failing';
        if (agg.winRate >= threshold) {
          status = 'healthy';
        } else if (agg.winRate >= threshold * 0.8) {
          status = 'degraded';
        } else {
          status = 'failing';
        }

        if (status !== 'healthy') {
          alerts.push(
            `${sid}: win rate ${(agg.winRate * 100).toFixed(1)}% ` +
            `(threshold: ${(threshold * 100).toFixed(0)}%, status: ${status})`
          );
        }

        healthResults.push({
          strategyId: sid,
          winRate: agg.winRate,
          profitFactor: agg.profitFactor,
          totalTrades: agg.totalTrades,
          status,
        });

        console.log(
          `[continuous-backtest] ${sid}: WR=${(agg.winRate * 100).toFixed(1)}% ` +
          `PF=${agg.profitFactor.toFixed(2)} trades=${agg.totalTrades} → ${status}`
        );
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        console.error(`[continuous-backtest] ${sid} failed:`, message);
        alerts.push(`${sid}: Error - ${message}`);

        healthResults.push({
          strategyId: sid,
          winRate: 0,
          profitFactor: 0,
          totalTrades: 0,
          status: 'failing',
        });
      }

      // Safety: abort if we're nearing the 120s timeout
      if (Date.now() - startTime > 110_000) {
        alerts.push(`Timeout approaching after ${i + 1}/${strategyIds.length} strategies. Returning partial results.`);
        break;
      }
    }

    // Determine overall health
    const hasFailing = healthResults.some(r => r.status === 'failing');
    const hasDegraded = healthResults.some(r => r.status === 'degraded');
    const overallHealth: 'green' | 'yellow' | 'red' = hasFailing
      ? 'red'
      : hasDegraded
        ? 'yellow'
        : 'green';

    const report: ContinuousBacktestReport = {
      timestamp: new Date().toISOString(),
      strategiesRun: healthResults.length,
      results: healthResults,
      alerts,
      overallHealth,
    };

    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    console.log(
      `[continuous-backtest] Complete: ${healthResults.length} strategies, ` +
      `health=${overallHealth}, ${alerts.length} alerts, ${elapsed}s elapsed`
    );

    return NextResponse.json(report);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Continuous backtest failed';
    console.error('[continuous-backtest] Fatal error:', message);
    return NextResponse.json(
      { error: message, timestamp: new Date().toISOString() },
      { status: 500 },
    );
  }
}
