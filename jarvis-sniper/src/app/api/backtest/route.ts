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
import { fetchTokenHistory, generateMemeGraduationCandles, type OHLCVSource } from '@/lib/historical-data';

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
 *   - Blue chip strategies: real OHLCV via fetchTokenHistory (3-tier: DexScreener -> Birdeye -> synthetic)
 *   - Memecoin strategies: graduation-calibrated synthetic data via generateMemeGraduationCandles
 *   - xStock/index/prestock strategies: server-side synthetic candles (no real historical data available)
 *
 * Fulfills: BACK-02 (Backtesting Engine), BACK-03 (Strategy Validation Report)
 */

// ─── Strategy Classification ───

type StrategyCategory = 'bluechip' | 'memecoin' | 'xstock_index';

const STRATEGY_CATEGORY: Record<string, StrategyCategory> = {
  // Blue chip strategies -- use real OHLCV data
  bluechip_mean_revert: 'bluechip',
  bluechip_trend_follow: 'bluechip',
  bluechip_breakout: 'bluechip',
  // Memecoin strategies -- use graduation-calibrated synthetic data
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
  // xStock / index / prestock -- synthetic candles (no real data available)
  xstock_intraday: 'xstock_index',
  xstock_swing: 'xstock_index',
  prestock_speculative: 'xstock_index',
  index_intraday: 'xstock_index',
  index_leveraged: 'xstock_index',
};

// Strategy entry signals mapped to preset IDs
const ENTRY_SIGNALS: Record<string, BacktestConfig['entrySignal']> = {
  // Blue chip strategies
  bluechip_mean_revert: meanReversionEntry,
  bluechip_trend_follow: trendFollowingEntry,
  bluechip_breakout: breakoutEntry,

  // Advanced strategies (from research)
  momentum_factor: momentumEntry,
  squeeze_breakout: squeezeBreakoutEntry,
  mean_reversion_rsi: meanReversionEntry,
  trend_adx: trendFollowingEntry,
};

// Strategy configs derived from STRATEGY_PRESETS -- all 18 strategies
const STRATEGY_CONFIGS: Record<string, Omit<BacktestConfig, 'entrySignal'>> = {
  // ─── Blue chip strategies ───
  bluechip_mean_revert: {
    strategyId: 'bluechip_mean_revert',
    stopLossPct: 3, takeProfitPct: 8, trailingStopPct: 2,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.3, feePct: 0.25,
    maxHoldCandles: 48, // 48h
  },
  bluechip_trend_follow: {
    strategyId: 'bluechip_trend_follow',
    stopLossPct: 5, takeProfitPct: 15, trailingStopPct: 4,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.3, feePct: 0.25,
    maxHoldCandles: 168, // 7 days
  },
  bluechip_breakout: {
    strategyId: 'bluechip_breakout',
    stopLossPct: 4, takeProfitPct: 12, trailingStopPct: 3,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.3, feePct: 0.25,
    maxHoldCandles: 72, // 3 days
  },
  // ─── Memecoin strategies ───
  pump_fresh_tight: {
    strategyId: 'pump_fresh_tight',
    stopLossPct: 20, takeProfitPct: 80, trailingStopPct: 8,
    minScore: 40, minLiquidityUsd: 5000,
    slippagePct: 1.0, feePct: 0.25,
    maxHoldCandles: 4, // 4h
  },
  momentum: {
    strategyId: 'momentum',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 8,
  },
  insight_j: {
    strategyId: 'insight_j',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 8,
  },
  micro_cap_surge: {
    strategyId: 'micro_cap_surge',
    stopLossPct: 45, takeProfitPct: 250, trailingStopPct: 20,
    minScore: 30, minLiquidityUsd: 3000,
    slippagePct: 1.5, feePct: 0.25,
    maxHoldCandles: 24,
  },
  elite: {
    strategyId: 'elite',
    stopLossPct: 15, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 100000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 8,
  },
  hybrid_b: {
    strategyId: 'hybrid_b',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 8,
  },
  let_it_ride: {
    strategyId: 'let_it_ride',
    stopLossPct: 20, takeProfitPct: 100, trailingStopPct: 5,
    minScore: 0, minLiquidityUsd: 50000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 24,
  },
  loose: {
    strategyId: 'loose',
    stopLossPct: 20, takeProfitPct: 60, trailingStopPct: 8,
    minScore: 0, minLiquidityUsd: 25000,
    slippagePct: 0.5, feePct: 0.25,
    maxHoldCandles: 8,
  },
  genetic_best: {
    strategyId: 'genetic_best',
    stopLossPct: 35, takeProfitPct: 200, trailingStopPct: 12,
    minScore: 43, minLiquidityUsd: 3000,
    slippagePct: 1.0, feePct: 0.25,
    maxHoldCandles: 24,
  },
  genetic_v2: {
    strategyId: 'genetic_v2',
    stopLossPct: 45, takeProfitPct: 207, trailingStopPct: 10,
    minScore: 0, minLiquidityUsd: 5000,
    slippagePct: 1.0, feePct: 0.25,
    maxHoldCandles: 24,
  },
  // ─── xStock strategies ───
  xstock_intraday: {
    strategyId: 'xstock_intraday',
    stopLossPct: 1.5, takeProfitPct: 3, trailingStopPct: 1,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.2, feePct: 0.25,
    maxHoldCandles: 8,
  },
  xstock_swing: {
    strategyId: 'xstock_swing',
    stopLossPct: 3, takeProfitPct: 8, trailingStopPct: 2,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.2, feePct: 0.25,
    maxHoldCandles: 120,
  },
  // ─── Prestock strategy ───
  prestock_speculative: {
    strategyId: 'prestock_speculative',
    stopLossPct: 5, takeProfitPct: 15, trailingStopPct: 3,
    minScore: 30, minLiquidityUsd: 5000,
    slippagePct: 0.3, feePct: 0.25,
    maxHoldCandles: 120,
  },
  // ─── Index strategies ───
  index_intraday: {
    strategyId: 'index_intraday',
    stopLossPct: 0.8, takeProfitPct: 1.5, trailingStopPct: 0.5,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.15, feePct: 0.25,
    maxHoldCandles: 8,
  },
  index_leveraged: {
    strategyId: 'index_leveraged',
    stopLossPct: 3, takeProfitPct: 8, trailingStopPct: 2,
    minScore: 0, minLiquidityUsd: 10000,
    slippagePct: 0.2, feePct: 0.25,
    maxHoldCandles: 120,
  },
};

// ─── Volatility profiles for xStock/index synthetic candles ───

const XSTOCK_INDEX_VOLATILITY: Record<string, number> = {
  xstock_intraday: 3,     // ~3% daily for US stocks
  xstock_swing: 4,        // ~4% daily for swing stocks
  prestock_speculative: 8, // ~8% daily for pre-IPO
  index_intraday: 1.5,    // ~1.5% daily for SPY/QQQ
  index_leveraged: 5,     // ~5% daily for TQQQ (3x leveraged)
};

/**
 * Generate synthetic candles for server-side backtesting.
 * Used for xStock/index/prestock strategies where no real on-chain data exists.
 */
function generateServerCandles(
  avgVolatility: number,
  numCandles: number = 4320,
): OHLCVCandle[] {
  const candles: OHLCVCandle[] = [];
  const hourlyVol = avgVolatility / 100 / 24;
  let price = 1.0; // Normalized
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

// ─── Backtest Runner Helpers ───

interface StrategyRunResult {
  result: BacktestResult;
  dataSource: OHLCVSource;
  validated: boolean;
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
        stopLossPcts: [3, 5, 8, 10, 15, 20],
        takeProfitPcts: [8, 12, 15, 20, 30, 50],
        trailingStopPcts: [0, 2, 4, 6, 8],
        maxHoldCandles: [24, 48, 72, 168],
      },
      tokenSymbol,
      entrySignal,
    );
    return gridResults.slice(0, 10); // Top 10
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
  mode: string,
  tokenSymbol: string,
): Promise<StrategyRunResult[]> {
  const tokens = tokenSymbol === 'all'
    ? ALL_BLUECHIPS.slice(0, 5) // Top 5 for speed
    : ALL_BLUECHIPS.filter(t => t.ticker === tokenSymbol);

  const runResults: StrategyRunResult[] = [];

  // Process tokens in batches of 3 to avoid rate limits
  for (let batch = 0; batch < tokens.length; batch += 3) {
    const batchTokens = tokens.slice(batch, batch + 3);
    const batchData = await Promise.all(
      batchTokens.map(token => fetchTokenHistory(token))
    );

    for (let i = 0; i < batchTokens.length; i++) {
      const data = batchData[i];
      const results = runStrategy(
        sid, config, data.candles, batchTokens[i].ticker, mode, entrySignal,
      );
      for (const result of results) {
        runResults.push({
          result,
          dataSource: data.source,
          validated: data.source !== 'synthetic',
        });
      }
    }
  }

  return runResults;
}

/**
 * Run memecoin strategies against graduation-calibrated synthetic data.
 * Generates 200 synthetic token datasets and aggregates results.
 */
function runMemecoinStrategy(
  sid: string,
  config: Omit<BacktestConfig, 'entrySignal'>,
  entrySignal: BacktestConfig['entrySignal'],
  mode: string,
): StrategyRunResult[] {
  const graduationData = generateMemeGraduationCandles(200);
  const runResults: StrategyRunResult[] = [];

  for (const dataset of graduationData) {
    // Only run quick mode against graduation data (walk-forward/grid not meaningful on short series)
    const results = runStrategy(
      sid, config, dataset.candles, dataset.tokenSymbol, 'quick', entrySignal,
    );
    for (const result of results) {
      runResults.push({
        result,
        dataSource: 'synthetic' as OHLCVSource,
        validated: false, // synthetic-calibrated, not real data
      });
    }
  }

  return runResults;
}

/**
 * Run xStock/index/prestock strategies against synthetic candles.
 */
function runXstockIndexStrategy(
  sid: string,
  config: Omit<BacktestConfig, 'entrySignal'>,
  entrySignal: BacktestConfig['entrySignal'],
  mode: string,
): StrategyRunResult[] {
  const volatility = XSTOCK_INDEX_VOLATILITY[sid] || 3;
  const candles = generateServerCandles(volatility);
  const results = runStrategy(sid, config, candles, sid, mode, entrySignal);

  return results.map(result => ({
    result,
    dataSource: 'synthetic' as OHLCVSource,
    validated: false,
  }));
}

// ─── POST Handler ───

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const {
      strategyId = 'all',
      tokenSymbol = 'all',
      mode = 'quick',
      candles: clientCandles,
    } = body;

    const allRunResults: StrategyRunResult[] = [];

    // Determine which strategies to test
    const strategyIds = strategyId === 'all'
      ? Object.keys(STRATEGY_CONFIGS)
      : [strategyId];

    for (const sid of strategyIds) {
      const config = STRATEGY_CONFIGS[sid];
      if (!config) continue;

      const entrySignal = ENTRY_SIGNALS[sid] || momentumEntry;
      const category = STRATEGY_CATEGORY[sid] || 'xstock_index';

      // If client provided candles, use those directly (override data source logic)
      if (clientCandles) {
        const results = runStrategy(sid, config, clientCandles, tokenSymbol, mode, entrySignal);
        for (const result of results) {
          allRunResults.push({
            result,
            dataSource: 'synthetic' as OHLCVSource,
            validated: false,
          });
        }
        continue;
      }

      // Route to appropriate data source based on strategy category
      switch (category) {
        case 'bluechip': {
          const bluechipResults = await runBluechipStrategy(
            sid, config, entrySignal, mode, tokenSymbol,
          );
          allRunResults.push(...bluechipResults);
          break;
        }
        case 'memecoin': {
          const memeResults = runMemecoinStrategy(sid, config, entrySignal, mode);
          allRunResults.push(...memeResults);
          break;
        }
        case 'xstock_index': {
          const xstockResults = runXstockIndexStrategy(sid, config, entrySignal, mode);
          allRunResults.push(...xstockResults);
          break;
        }
      }
    }

    // Extract BacktestResult array for report generation
    const results = allRunResults.map(r => r.result);

    // Generate report
    const report = generateBacktestReport(results);

    // Summary stats with validation metadata
    const summary = allRunResults.map(r => ({
      strategyId: r.result.strategyId,
      token: r.result.tokenSymbol,
      trades: r.result.totalTrades,
      winRate: `${(r.result.winRate * 100).toFixed(1)}%`,
      profitFactor: r.result.profitFactor.toFixed(2),
      sharpe: r.result.sharpeRatio.toFixed(2),
      maxDD: `${r.result.maxDrawdownPct.toFixed(1)}%`,
      expectancy: r.result.expectancy.toFixed(4),
      avgHold: `${r.result.avgHoldCandles.toFixed(0)}h`,
      validated: r.validated,
      dataSource: r.dataSource,
    }));

    // Detect underperformers: win rate < 40% OR profit factor < 1.0
    const underperformers = allRunResults
      .filter(r => r.result.winRate < 0.40 || r.result.profitFactor < 1.0)
      .map(r => r.result.strategyId);
    // Deduplicate
    const uniqueUnderperformers = [...new Set(underperformers)];

    return NextResponse.json({
      results: summary,
      report,
      underperformers: uniqueUnderperformers,
      fullResults: results.map(r => ({
        ...r,
        trades: r.trades.slice(0, 50), // Limit trade details
        equityCurve: r.equityCurve.slice(-100), // Last 100 points
      })),
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Backtest failed';
    return NextResponse.json(
      { error: message },
      { status: 500 }
    );
  }
}
