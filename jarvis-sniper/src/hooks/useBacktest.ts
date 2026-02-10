'use client';

import { useState, useEffect, useCallback } from 'react';
import { STRATEGY_PRESETS } from '@/stores/useSniperStore';
import { useSniperStore } from '@/stores/useSniperStore';

// ─── Types ──────────────────────────────────────────────────────────────────

export interface BacktestSummary {
  strategyId: string;
  token: string;
  trades: number;
  winRate: string;
  profitFactor: string;
  sharpe: string;
  maxDD: string;
  expectancy: string;
  avgHold: string;
  /** Forward-compat: data source label added by Plan 03 */
  dataSource?: string;
  /** Forward-compat: whether real candle data was used */
  validated?: boolean;
}

export interface BacktestRunState {
  isRunning: boolean;
  progress: { current: number; total: number; currentStrategy: string } | null;
  results: BacktestSummary[] | null;
  report: string | null;
  error: string | null;
  lastRunAt: number | null;
}

// ─── LocalStorage helpers ───────────────────────────────────────────────────

const LS_KEY = 'jarvis_backtest_results';

interface CachedBacktestData {
  results: BacktestSummary[];
  report: string | null;
  lastRunAt: number;
}

function loadCachedResults(): Partial<BacktestRunState> {
  if (typeof window === 'undefined') return {};
  try {
    const raw = localStorage.getItem(LS_KEY);
    if (!raw) return {};
    const data: CachedBacktestData = JSON.parse(raw);
    return {
      results: data.results,
      report: data.report ?? null,
      lastRunAt: data.lastRunAt,
    };
  } catch {
    return {};
  }
}

function saveCachedResults(results: BacktestSummary[], report: string | null, lastRunAt: number) {
  if (typeof window === 'undefined') return;
  try {
    const data: CachedBacktestData = { results, report, lastRunAt };
    localStorage.setItem(LS_KEY, JSON.stringify(data));
  } catch {
    // localStorage quota exceeded — silently skip
  }
}

// ─── Hook ───────────────────────────────────────────────────────────────────

const INITIAL_STATE: BacktestRunState = {
  isRunning: false,
  progress: null,
  results: null,
  report: null,
  error: null,
  lastRunAt: null,
};

export function useBacktest() {
  const [state, setState] = useState<BacktestRunState>(INITIAL_STATE);

  // Hydrate from localStorage on mount
  useEffect(() => {
    const cached = loadCachedResults();
    if (cached.results) {
      setState((prev) => ({
        ...prev,
        results: cached.results ?? null,
        report: cached.report ?? null,
        lastRunAt: cached.lastRunAt ?? null,
      }));
    }
  }, []);

  /**
   * Run a backtest for a specific strategy (or 'all') in the given mode.
   */
  const runBacktest = useCallback(
    async (strategyId: string, mode: 'quick' | 'full' | 'grid' = 'quick') => {
      setState((prev) => ({
        ...prev,
        isRunning: true,
        error: null,
        progress: {
          current: 0,
          total: strategyId === 'all' ? STRATEGY_PRESETS.length : 1,
          currentStrategy:
            strategyId === 'all'
              ? STRATEGY_PRESETS[0]?.name ?? 'Starting...'
              : STRATEGY_PRESETS.find((p) => p.id === strategyId)?.name ?? strategyId,
        },
      }));

      try {
        const res = await fetch('/api/backtest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ strategyId, mode }),
        });

        if (!res.ok) {
          const errBody = await res.json().catch(() => ({ error: 'Unknown error' }));
          throw new Error(errBody.error || `HTTP ${res.status}`);
        }

        const data = await res.json();
        const now = Date.now();

        setState((prev) => ({
          ...prev,
          isRunning: false,
          progress: null,
          results: data.results ?? [],
          report: data.report ?? null,
          lastRunAt: now,
          error: null,
        }));

        // Persist to localStorage
        if (data.results) {
          saveCachedResults(data.results, data.report ?? null, now);
        }

        // Wire to Zustand store — guard against missing action (added in Plan 03)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const storeState = useSniperStore.getState() as any;
        const updatePresets = storeState.updatePresetBacktestResults;
        if (typeof updatePresets === 'function' && data.results) {
          updatePresets(
            data.results.map((r: BacktestSummary) => ({
              strategyId: r.strategyId,
              winRate: r.winRate,
              trades: r.trades,
              backtested: true,
              dataSource: r.dataSource || 'synthetic',
              underperformer:
                parseFloat(r.winRate) < 40 || parseFloat(r.profitFactor) < 1.0,
            })),
          );
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Backtest failed';
        setState((prev) => ({
          ...prev,
          isRunning: false,
          progress: null,
          error: message,
        }));
      }
    },
    [],
  );

  /**
   * Convenience: run all strategies in quick mode.
   */
  const runAllStrategies = useCallback(() => {
    return runBacktest('all', 'quick');
  }, [runBacktest]);

  /**
   * Clear all results (state + localStorage).
   */
  const clearResults = useCallback(() => {
    setState(INITIAL_STATE);
    if (typeof window !== 'undefined') {
      localStorage.removeItem(LS_KEY);
    }
  }, []);

  return { state, runBacktest, runAllStrategies, clearResults };
}
