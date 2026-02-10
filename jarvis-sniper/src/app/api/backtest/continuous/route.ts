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
import { fetchTokenHistory, generateMemeGraduationCandles } from '@/lib/historical-data';

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

// Allow up to 120 seconds for Vercel serverless
export const maxDuration = 120;

// ─── Strategy Classification ───

type StrategyCategory = 'bluechip' | 'memecoin' | 'xstock_index';

const STRATEGY_CATEGORY: Record<string, StrategyCategory> = {
  // Blue chip strategies
  bluechip_mean_revert: 'bluechip',
  bluechip_trend_follow: 'bluechip',
  bluechip_breakout: 'bluechip',
  // Memecoin strategies
  pump_fresh_tight: 'memecoin',
  momentum: 'memecoin',
  insight_j: 'memecoin',
  micro_cap_surge: 'memecoin',
  elite: 'memecoin',
  hybrid_b: 'memecoin',
  let_it_ride: 'memecoin',
  loose: 'memecoin',
  genetic_best: 'memecoin',
  genetic_v2: 'memecoin',
  // xStock / index / prestock
  xstock_intraday: 'xstock_index',
  xstock_swing: 'xstock_index',
  prestock_speculative: 'xstock_index',
  index_intraday: 'xstock_index',
  index_leveraged: 'xstock_index',
};

// Entry signals mapped to preset IDs
const ENTRY_SIGNALS: Record<string, BacktestConfig['entrySignal']> = {
  bluechip_mean_revert: meanReversionEntry,
  bluechip_trend_follow: trendFollowingEntry,
  bluechip_breakout: breakoutEntry,
  momentum_factor: momentumEntry,
  squeeze_breakout: squeezeBreakoutEntry,
  mean_reversion_rsi: meanReversionEntry,
  trend_adx: trendFollowingEntry,
};

// Full strategy configs (all 18)
const STRATEGY_CONFIGS: Record<string, Omit<BacktestConfig, 'entrySignal'>> = {
  // Blue chip strategies
  bluechip_mean_revert: {
    strategyId: 'bluechip_mean_revert',
    stopLossPct: 3, takeProfitPct: 8, trailingStopPct: 2,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.3, feePct: 0.25, maxHoldCandles: 48,
  },
  bluechip_trend_follow: {
    strategyId: 'bluechip_trend_follow',
    stopLossPct: 5, takeProfitPct: 15, trailingStopPct: 4,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.3, feePct: 0.25, maxHoldCandles: 168,
  },
  bluechip_breakout: {
    strategyId: 'bluechip_breakout',
    stopLossPct: 4, takeProfitPct: 12, trailingStopPct: 3,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.3, feePct: 0.25, maxHoldCandles: 72,
  },
  // Memecoin strategies
  pump_fresh_tight: {
    strategyId: 'pump_fresh_tight',
    stopLossPct: 20, takeProfitPct: 80, trailingStopPct: 8,
    minScore: 40, minLiquidityUsd: 5000,
    slippagePct: 1.0, feePct: 0.25, maxHoldCandles: 4,
  },
  momentum: {
    strategyId: 'momentum',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 8,
  },
  insight_j: {
    strategyId: 'insight_j',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 8,
  },
  micro_cap_surge: {
    strategyId: 'micro_cap_surge',
    stopLossPct: 45, takeProfitPct: 250, trailingStopPct: 20,
    minScore: 30, minLiquidityUsd: 3000,
    slippagePct: 1.5, feePct: 0.25, maxHoldCandles: 24,
  },
  elite: {
    strategyId: 'elite',
    stopLossPct: 15, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 100000,
    slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 8,
  },
  hybrid_b: {
    strategyId: 'hybrid_b',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 8,
  },
  let_it_ride: {
    strategyId: 'let_it_ride',
    stopLossPct: 20, takeProfitPct: 100, trailingStopPct: 5,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 24,
  },
  loose: {
    strategyId: 'loose',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 25000,
    slippagePct: 0.5, feePct: 0.25, maxHoldCandles: 8,
  },
  genetic_best: {
    strategyId: 'genetic_best',
    stopLossPct: 35, takeProfitPct: 200, trailingStopPct: 12,
    minScore: 43, minLiquidityUsd: 3000,
    slippagePct: 1.0, feePct: 0.25, maxHoldCandles: 24,
  },
  genetic_v2: {
    strategyId: 'genetic_v2',
    stopLossPct: 45, takeProfitPct: 207, trailingStopPct: 10,
    minScore: 0, minLiquidityUsd: 5000,
    slippagePct: 1.0, feePct: 0.25, maxHoldCandles: 24,
  },
  // xStock strategies
  xstock_intraday: {
    strategyId: 'xstock_intraday',
    stopLossPct: 1.5, takeProfitPct: 3, trailingStopPct: 1,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.2, feePct: 0.25, maxHoldCandles: 8,
  },
  xstock_swing: {
    strategyId: 'xstock_swing',
    stopLossPct: 3, takeProfitPct: 8, trailingStopPct: 2,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.2, feePct: 0.25, maxHoldCandles: 120,
  },
  // Prestock strategy
  prestock_speculative: {
    strategyId: 'prestock_speculative',
    stopLossPct: 5, takeProfitPct: 15, trailingStopPct: 3,
    minScore: 30, minLiquidityUsd: 5000,
    slippagePct: 0.3, feePct: 0.25, maxHoldCandles: 120,
  },
  // Index strategies
  index_intraday: {
    strategyId: 'index_intraday',
    stopLossPct: 0.8, takeProfitPct: 1.5, trailingStopPct: 0.5,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.15, feePct: 0.25, maxHoldCandles: 8,
  },
  index_leveraged: {
    strategyId: 'index_leveraged',
    stopLossPct: 3, takeProfitPct: 8, trailingStopPct: 2,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.2, feePct: 0.25, maxHoldCandles: 120,
  },
};

// Volatility profiles for xStock/index synthetic candles
const XSTOCK_INDEX_VOLATILITY: Record<string, number> = {
  xstock_intraday: 3,
  xstock_swing: 4,
  prestock_speculative: 8,
  index_intraday: 1.5,
  index_leveraged: 5,
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

/**
 * Generate synthetic candles for server-side backtesting.
 * Used for xStock/index/prestock strategies where no real on-chain data exists.
 */
function generateServerCandles(avgVolatility: number, numCandles = 4320): OHLCVCandle[] {
  const candles: OHLCVCandle[] = [];
  const hourlyVol = avgVolatility / 100 / 24;
  let price = 1.0;
  const now = Date.now();
  const startTime = now - numCandles * 3600 * 1000;

  for (let i = 0; i < numCandles; i++) {
    const open = price;
    const candleVol = hourlyVol * (0.5 + Math.random());
    const change = (Math.random() - 0.48) * 2 * candleVol;
    const close = open * (1 + change);
    const range = Math.abs(change) + candleVol * 0.5;
    const high = Math.max(open, close) * (1 + Math.random() * range);
    const low = Math.min(open, close) * (1 - Math.random() * range);
    const volume = 100000 * Math.exp((Math.random() - 0.5) * 2);

    candles.push({
      timestamp: startTime + i * 3600 * 1000,
      open, high, low, close, volume,
    });
    price = close;
  }

  return candles;
}

/**
 * Fetch candle data for a strategy based on its category.
 * Reduced dataset sizes for speed (50 meme patterns, 3 bluechip tokens).
 */
async function fetchDataForCategory(
  category: StrategyCategory,
  strategyId: string,
): Promise<OHLCVCandle[]> {
  switch (category) {
    case 'bluechip': {
      // Fetch representative tokens: SOL, JUP, RAY (first 3)
      const tokens = ALL_BLUECHIPS.slice(0, 3);
      const allCandles: OHLCVCandle[] = [];
      for (const token of tokens) {
        try {
          const data = await fetchTokenHistory(token);
          allCandles.push(...data.candles);
        } catch (err) {
          console.warn(`[continuous-backtest] Failed to fetch ${token.ticker}:`, err);
        }
      }
      return allCandles;
    }

    case 'memecoin': {
      // Reduced from 200 to 50 patterns for speed
      const datasets = generateMemeGraduationCandles(50);
      return datasets.flatMap(d => d.candles);
    }

    case 'xstock_index': {
      const volatility = XSTOCK_INDEX_VOLATILITY[strategyId] || 3;
      return generateServerCandles(volatility);
    }
  }
}

/**
 * Run a single strategy and return its BacktestResult.
 */
function runSingleStrategy(
  strategyId: string,
  config: Omit<BacktestConfig, 'entrySignal'>,
  candles: OHLCVCandle[],
): BacktestResult {
  const entrySignal = ENTRY_SIGNALS[strategyId] || momentumEntry;
  const fullConfig: BacktestConfig = { ...config, entrySignal };
  const engine = new BacktestEngine(candles, fullConfig);
  return engine.run(strategyId);
}

// ─── POST Handler ───

export async function POST(request: Request) {
  const startTime = Date.now();

  try {
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

    // Run strategies sequentially to avoid memory pressure
    for (let i = 0; i < strategyIds.length; i++) {
      const sid = strategyIds[i];
      const config = STRATEGY_CONFIGS[sid];
      const category = STRATEGY_CATEGORY[sid] || 'xstock_index';

      console.log(`[continuous-backtest] Running ${sid} (${i + 1}/${strategyIds.length}) [${category}]`);

      try {
        // Fetch data for this strategy's category
        const candles = await fetchDataForCategory(category, sid);

        if (candles.length === 0) {
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

        // Run the backtest
        const result = runSingleStrategy(sid, config, candles);

        // Classify health
        let status: 'healthy' | 'degraded' | 'failing';
        if (result.winRate >= threshold) {
          status = 'healthy';
        } else if (result.winRate >= threshold * 0.8) {
          status = 'degraded';
        } else {
          status = 'failing';
        }

        if (status !== 'healthy') {
          alerts.push(
            `${sid}: win rate ${(result.winRate * 100).toFixed(1)}% ` +
            `(threshold: ${(threshold * 100).toFixed(0)}%, status: ${status})`
          );
        }

        healthResults.push({
          strategyId: sid,
          winRate: result.winRate,
          profitFactor: result.profitFactor,
          totalTrades: result.totalTrades,
          status,
        });

        console.log(
          `[continuous-backtest] ${sid}: WR=${(result.winRate * 100).toFixed(1)}% ` +
          `PF=${result.profitFactor.toFixed(2)} trades=${result.totalTrades} → ${status}`
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
