'use client';

/**
 * useBacktest Hook -- React hook wrapping the backtest engine
 *
 * Runs all 4 built-in strategies against a pool's historical OHLCV data.
 * Caches results to avoid redundant API calls.
 * Returns the best strategy (highest win rate) and current signals.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  BUILTIN_STRATEGIES,
  runBacktest,
  getCurrentSignal,
  getConsensus,
  type BacktestResult,
  type BacktestOptions,
  type OHLCVCandle,
} from '@/lib/backtest-engine';
import { fetchOHLCV, type TimeInterval } from '@/lib/gecko-terminal';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StrategyResult {
  backtest: BacktestResult;
  currentSignal: {
    signal: 'BUY' | 'SELL' | 'HOLD';
    price: number;
    reason: string;
  };
}

export interface BacktestHookResult {
  /** Per-strategy results (backtest + current signal) */
  results: StrategyResult[];
  /** Whether any backtest is currently running */
  isRunning: boolean;
  /** Error message if something went wrong */
  error: string | null;
  /** Run all strategies */
  runAll: () => Promise<void>;
  /** Run a single strategy by name */
  runSingle: (strategyName: string) => Promise<void>;
  /** The strategy with the highest win rate */
  bestStrategy: StrategyResult | null;
  /** Consensus across all strategies */
  consensus: {
    consensus: 'BUY' | 'SELL' | 'HOLD';
    buyCount: number;
    sellCount: number;
    holdCount: number;
    total: number;
  } | null;
  /** Suggested TP/SL from the best strategy's backtest */
  suggestedTP: number;
  suggestedSL: number;
}

// ---------------------------------------------------------------------------
// Cache
// ---------------------------------------------------------------------------

const resultCache = new Map<string, { results: StrategyResult[]; timestamp: number }>();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes

function getCacheKey(poolAddress: string): string {
  return `backtest:${poolAddress}`;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useBacktest(
  poolAddress: string | null,
  options?: {
    strategyName?: string;
    timeframe?: TimeInterval;
    takeProfitPct?: number;
    stopLossPct?: number;
    autoRun?: boolean;
  },
): BacktestHookResult {
  const [results, setResults] = useState<StrategyResult[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef(false);

  const timeframe = options?.timeframe ?? '1h';
  const takeProfitPct = options?.takeProfitPct ?? 20;
  const stopLossPct = options?.stopLossPct ?? 10;
  const autoRun = options?.autoRun ?? true;

  // ---------------------------------------------------------------------------
  // Run all strategies
  // ---------------------------------------------------------------------------
  const runAll = useCallback(async () => {
    if (!poolAddress) return;

    // Check cache
    const cacheKey = getCacheKey(poolAddress);
    const cached = resultCache.get(cacheKey);
    if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
      setResults(cached.results);
      return;
    }

    setIsRunning(true);
    setError(null);
    abortRef.current = false;

    try {
      // Fetch candles once and share across strategies
      const candles = await fetchOHLCV(poolAddress, timeframe, 300);

      if (candles.length < 30) {
        setError('Insufficient data for backtesting (need at least 30 candles)');
        setIsRunning(false);
        return;
      }

      // Map to backtest engine format
      const ohlcv: OHLCVCandle[] = candles.map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume,
      }));

      const stratResults: StrategyResult[] = [];

      for (const strategy of BUILTIN_STRATEGIES) {
        if (abortRef.current) break;

        try {
          // Generate signals
          const signals = strategy.evaluate(ohlcv);

          // Import simulateTrades inline to avoid circular issues
          const { simulateTrades } = await import('@/lib/backtest-engine');

          const sim = simulateTrades(signals, ohlcv, { takeProfitPct, stopLossPct });

          const backtest: BacktestResult = {
            strategyName: strategy.name,
            ...sim,
          };

          const currentSignal = getCurrentSignal(strategy, ohlcv);

          stratResults.push({ backtest, currentSignal });
        } catch (err) {
          // Individual strategy failure should not block others
          console.warn(`Strategy ${strategy.name} failed:`, err);
          stratResults.push({
            backtest: {
              strategyName: strategy.name,
              totalTrades: 0,
              winRate: 0,
              avgReturn: 0,
              maxDrawdown: 0,
              sharpeRatio: 0,
              profitFactor: 0,
              trades: [],
            },
            currentSignal: { signal: 'HOLD', price: 0, reason: 'Strategy error' },
          });
        }
      }

      if (!abortRef.current) {
        setResults(stratResults);
        resultCache.set(cacheKey, { results: stratResults, timestamp: Date.now() });
      }
    } catch (err) {
      if (!abortRef.current) {
        const msg = err instanceof Error ? err.message : 'Backtest failed';
        setError(msg);
      }
    } finally {
      if (!abortRef.current) {
        setIsRunning(false);
      }
    }
  }, [poolAddress, timeframe, takeProfitPct, stopLossPct]);

  // ---------------------------------------------------------------------------
  // Run single strategy
  // ---------------------------------------------------------------------------
  const runSingle = useCallback(
    async (strategyName: string) => {
      if (!poolAddress) return;

      const strategy = BUILTIN_STRATEGIES.find(s => s.name === strategyName);
      if (!strategy) {
        setError(`Strategy "${strategyName}" not found`);
        return;
      }

      setIsRunning(true);
      setError(null);

      try {
        const result = await runBacktest(poolAddress, strategy, {
          timeframe,
          takeProfitPct,
          stopLossPct,
        });

        const candles = await fetchOHLCV(poolAddress, timeframe, 300);
        const ohlcv: OHLCVCandle[] = candles.map(c => ({
          time: c.time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume,
        }));

        const currentSignal = getCurrentSignal(strategy, ohlcv);

        // Update or add the result
        setResults(prev => {
          const idx = prev.findIndex(r => r.backtest.strategyName === strategyName);
          const newEntry: StrategyResult = { backtest: result, currentSignal };
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = newEntry;
            return next;
          }
          return [...prev, newEntry];
        });
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Backtest failed';
        setError(msg);
      } finally {
        setIsRunning(false);
      }
    },
    [poolAddress, timeframe, takeProfitPct, stopLossPct],
  );

  // ---------------------------------------------------------------------------
  // Auto-run on mount / pool change
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (autoRun && poolAddress) {
      runAll();
    }
    return () => {
      abortRef.current = true;
    };
  }, [poolAddress, autoRun, runAll]);

  // ---------------------------------------------------------------------------
  // Computed values
  // ---------------------------------------------------------------------------
  const bestStrategy =
    results.length > 0
      ? results.reduce((best, r) =>
          r.backtest.winRate > best.backtest.winRate ? r : best,
        )
      : null;

  const consensus =
    results.length > 0
      ? getConsensus(results.map(r => r.currentSignal))
      : null;

  // Suggested TP/SL based on best strategy's average return and max drawdown
  const suggestedTP = bestStrategy
    ? Math.max(takeProfitPct, Math.round(Math.abs(bestStrategy.backtest.avgReturn) * 1.5))
    : takeProfitPct;

  const suggestedSL = bestStrategy
    ? Math.max(stopLossPct, Math.round(Math.abs(bestStrategy.backtest.maxDrawdown) * 0.8))
    : stopLossPct;

  return {
    results,
    isRunning,
    error,
    runAll,
    runSingle,
    bestStrategy,
    consensus,
    suggestedTP,
    suggestedSL,
  };
}
