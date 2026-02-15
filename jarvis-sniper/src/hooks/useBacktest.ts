'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
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
  /** Machine-readable win-rate percentage (0-100). */
  winRatePct?: number;
  /** Wilson 95% lower bound of win-rate (0-100). */
  winRateLower95Pct?: number;
  /** Wilson 95% upper bound of win-rate (0-100). */
  winRateUpper95Pct?: number;
  /** Aggregate net pnl metric for strategy ranking (percentage points). */
  netPnlPct?: number;
  /** Machine-readable profit factor value. */
  profitFactorValue?: number;
  /** Forward-compat: data source label added by Plan 03 */
  dataSource?: string;
  /** Forward-compat: whether real candle data was used */
  validated?: boolean;
}

export interface BacktestEvidenceMeta {
  runId: string;
  datasetCount: number;
  tradeCount: number;
}

export type BacktestDataScale = 'fast' | 'thorough';

export type BacktestSampleStage = 'tiny' | 'sanity' | 'stability' | 'promotion';

interface BacktestRunStatusView {
  state: 'running' | 'completed' | 'failed' | 'partial';
  progress: number;
  updatedAt: number;
  heartbeatAt: number | null;
  lastDatasetBatchAt: number | null;
  lastMovementAt: number;
  phase: 'universe_discovery' | 'dataset_fetch' | 'strategy_run' | 'artifact_persist' | 'unknown';
  stale: boolean;
  staleReason: string | null;
  livenessBudgetSec: number;
  completedChunks: number;
  failedChunks: number;
  totalChunks: number;
  currentChunk: string | null;
  currentActivity: string | null;
}

interface BacktestArtifactAvailability {
  manifest: boolean;
  evidence: boolean;
  report: boolean;
  csv: boolean;
}

export interface BacktestRunState {
  isRunning: boolean;
  isPolling: boolean;
  detachedRun: boolean;
  detachedReason: string | null;
  isStalled: boolean;
  stallSeconds: number;
  activeRunId: string | null;
  runStatus: BacktestRunStatusView | null;
  artifactAvailability: BacktestArtifactAvailability | null;
  progress: { current: number; total: number; currentStrategy: string } | null;
  results: BacktestSummary[] | null;
  report: string | null;
  evidence: BacktestEvidenceMeta | null;
  error: string | null;
  lastRunAt: number | null;
}

// ─── LocalStorage helpers ───────────────────────────────────────────────────

const LS_KEY = 'jarvis_backtest_results';

interface CachedBacktestData {
  results: BacktestSummary[];
  report: string | null;
  evidence: BacktestEvidenceMeta | null;
  lastRunAt: number;
}

interface ResponseErrorEnvelope {
  status: number;
  message: string;
  code?: string;
  retryable?: boolean;
  monitorUnavailable?: boolean;
  runMissing?: boolean;
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
      evidence: data.evidence ?? null,
      lastRunAt: data.lastRunAt,
    };
  } catch {
    return {};
  }
}

function saveCachedResults(
  results: BacktestSummary[],
  report: string | null,
  evidence: BacktestEvidenceMeta | null,
  lastRunAt: number,
) {
  if (typeof window === 'undefined') return;
  try {
    const data: CachedBacktestData = { results, report, evidence, lastRunAt };
    localStorage.setItem(LS_KEY, JSON.stringify(data));
  } catch {
    // localStorage quota exceeded — silently skip
  }
}

// ─── Hook ───────────────────────────────────────────────────────────────────

const INITIAL_STATE: BacktestRunState = {
  isRunning: false,
  isPolling: false,
  detachedRun: false,
  detachedReason: null,
  isStalled: false,
  stallSeconds: 0,
  activeRunId: null,
  runStatus: null,
  artifactAvailability: null,
  progress: null,
  results: null,
  report: null,
  evidence: null,
  error: null,
  lastRunAt: null,
};

// Hard gates (requested): don’t call something “validated” without real sample size.
const SAMPLE_THRESHOLDS = {
  sanity: 100,
  stability: 1000,
  promotion: 5000,
} as const;

function stageForTrades(trades: number): BacktestSampleStage {
  const t = Math.max(0, Math.floor(trades || 0));
  if (t >= SAMPLE_THRESHOLDS.promotion) return 'promotion';
  if (t >= SAMPLE_THRESHOLDS.stability) return 'stability';
  if (t >= SAMPLE_THRESHOLDS.sanity) return 'sanity';
  return 'tiny';
}

type PresetBacktestUpdate = {
  strategyId: string;
  winRate: string;
  trades: number;
  backtested: boolean;
  dataSource: string;
  underperformer: boolean;
  stage?: BacktestSampleStage;
  promotionEligible?: boolean;
  winRatePct?: number;
  winRateLower95Pct?: number;
  winRateUpper95Pct?: number;
  totalTrades?: number;
  netPnlPct?: number;
  profitFactorValue?: number;
};

export function buildPresetBacktestUpdates(rows: BacktestSummary[]): PresetBacktestUpdate[] {
  const byStrategy = new Map<
    string,
    {
      totalTrades: number;
      estWins: number;
      pfWeightedSum: number;
      pfTrades: number;
      wrLoWeightedSum: number;
      wrHiWeightedSum: number;
      wrBoundTrades: number;
      netPnlPctSum: number;
      netPnlRows: number;
      dataSources: Set<string>;
      validatedAny: boolean;
    }
  >();

  for (const r of rows) {
    const trades = typeof r.trades === 'number' ? Math.max(0, r.trades) : 0;
    const wrPctRaw = Number.isFinite(r.winRatePct) ? Number(r.winRatePct) : Number.parseFloat(r.winRate);
    const wrPct = Number.isFinite(wrPctRaw) ? wrPctRaw : 0;
    const wrLoRaw = Number.isFinite(r.winRateLower95Pct) ? Number(r.winRateLower95Pct) : Number.NaN;
    const wrHiRaw = Number.isFinite(r.winRateUpper95Pct) ? Number(r.winRateUpper95Pct) : Number.NaN;
    const pfRaw = Number.isFinite(r.profitFactorValue) ? Number(r.profitFactorValue) : Number.parseFloat(r.profitFactor);
    const netPnlRaw = Number.isFinite(r.netPnlPct) ? Number(r.netPnlPct) : Number.NaN;

    const cur = byStrategy.get(r.strategyId) ?? {
      totalTrades: 0,
      estWins: 0,
      pfWeightedSum: 0,
      pfTrades: 0,
      wrLoWeightedSum: 0,
      wrHiWeightedSum: 0,
      wrBoundTrades: 0,
      netPnlPctSum: 0,
      netPnlRows: 0,
      dataSources: new Set<string>(),
      validatedAny: false,
    };

    cur.totalTrades += trades;
    if (trades > 0) {
      cur.estWins += (wrPct / 100) * trades;
    }
    if (Number.isFinite(pfRaw) && trades > 0) {
      cur.pfWeightedSum += pfRaw * trades;
      cur.pfTrades += trades;
    }
    if (Number.isFinite(wrLoRaw) && Number.isFinite(wrHiRaw) && trades > 0) {
      cur.wrLoWeightedSum += wrLoRaw * trades;
      cur.wrHiWeightedSum += wrHiRaw * trades;
      cur.wrBoundTrades += trades;
    }
    if (Number.isFinite(netPnlRaw)) {
      cur.netPnlPctSum += netPnlRaw;
      cur.netPnlRows += 1;
    }
    if (r.dataSource) cur.dataSources.add(r.dataSource);
    if (r.validated) cur.validatedAny = true;

    byStrategy.set(r.strategyId, cur);
  }

  return [...byStrategy.entries()].map(([strategyId, agg]) => {
    const winRatePct =
      agg.totalTrades > 0 ? (agg.estWins / agg.totalTrades) * 100 : 0;
    const profitFactor =
      agg.pfTrades > 0 ? agg.pfWeightedSum / agg.pfTrades : 0;
    const winRateLower95Pct =
      agg.wrBoundTrades > 0 ? agg.wrLoWeightedSum / agg.wrBoundTrades : undefined;
    const winRateUpper95Pct =
      agg.wrBoundTrades > 0 ? agg.wrHiWeightedSum / agg.wrBoundTrades : undefined;
    const netPnlPct =
      agg.netPnlRows > 0 ? agg.netPnlPctSum : undefined;
    const dataSource =
      agg.dataSources.size === 1
        ? [...agg.dataSources][0]
        : agg.dataSources.size > 1
          ? 'mixed'
          : 'unknown';
    const stage = stageForTrades(agg.totalTrades);
    const underperformer = winRatePct < 40 || profitFactor < 1.0;

    return {
      strategyId,
      winRate: `${winRatePct.toFixed(1)}%`,
      trades: agg.totalTrades,
      backtested: stage !== 'tiny',
      dataSource,
      underperformer,
      stage,
      promotionEligible: stage === 'promotion' && !underperformer,
      winRatePct,
      winRateLower95Pct,
      winRateUpper95Pct,
      totalTrades: agg.totalTrades,
      netPnlPct,
      profitFactorValue: Number.isFinite(profitFactor) ? profitFactor : undefined,
    };
  });
}

export function useBacktest() {
  const [state, setState] = useState<BacktestRunState>(INITIAL_STATE);
  const pollTimerRef = useRef<number | null>(null);
  const lastMovementAtRef = useRef<number>(0);
  const lastSeenTimestampRef = useRef<number>(0);
  const monitorMissCountRef = useRef<number>(0);
  const prevRunStatusRef = useRef<BacktestRunStatusView | null>(null);

  const POLL_INTERVAL_MS = 4000;
  const stallThresholdMsRef = useRef<number>(420000);

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current != null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    monitorMissCountRef.current = 0;
    setState((prev) => ({
      ...prev,
      isPolling: false,
      detachedRun: false,
      detachedReason: null,
      isStalled: false,
      stallSeconds: 0,
    }));
  }, []);

  const stallThresholdFor = useCallback((mode: 'quick' | 'full' | 'grid', dataScale: BacktestDataScale): number => {
    if (mode === 'quick' && dataScale === 'fast') return 240_000;
    if (mode === 'quick' && dataScale === 'thorough') return 420_000;
    return 600_000;
  }, []);

  const fetchArtifacts = useCallback(async (runId: string): Promise<BacktestArtifactAvailability | null> => {
    try {
      const res = await fetch(`/api/backtest/runs/${encodeURIComponent(runId)}/artifacts`, {
        cache: 'no-store',
      });
      if (!res.ok) return null;
      const json = await res.json();
      const a = json?.available;
      if (!a || typeof a !== 'object') return null;
      return {
        manifest: !!a.manifest,
        evidence: !!a.evidence,
        report: !!a.report,
        csv: !!a.csv,
      };
    } catch {
      return null;
    }
  }, []);

  const readErrorFromResponse = useCallback(async (res: Response): Promise<ResponseErrorEnvelope> => {
    const fallback = `HTTP ${res.status}`;
    try {
      const contentType = String(res.headers.get('content-type') || '').toLowerCase();
      if (contentType.includes('application/json')) {
        const payload = await res.json();
        return {
          status: res.status,
          message: String(payload?.error || payload?.message || fallback),
          code: typeof payload?.code === 'string' ? payload.code : undefined,
          retryable: payload?.retryable === true,
          monitorUnavailable: payload?.monitorUnavailable === true,
          runMissing: payload?.runMissing === true,
        };
      }
      const text = (await res.text()).trim();
      if (!text) return { status: res.status, message: fallback };
      return {
        status: res.status,
        message: text.length > 280 ? `${text.slice(0, 277)}...` : text,
      };
    } catch {
      return { status: res.status, message: fallback };
    }
  }, []);

  const pollRunStatusOnce = useCallback(async (runId: string): Promise<BacktestRunStatusView | null> => {
    try {
      const res = await fetch(`/api/backtest/runs/${encodeURIComponent(runId)}`, { cache: 'no-store' });
      if (!res.ok) {
        const errEnv = await readErrorFromResponse(res);
        const errMsg = errEnv.message;
        const isRunMissing =
          res.status === 404 ||
          errEnv.runMissing === true ||
          errEnv.code === 'RUN_NOT_FOUND' ||
          errMsg.toLowerCase().includes('run id not found');
        if (isRunMissing) {
          if (pollTimerRef.current != null) {
            window.clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
          setState((prev) => ({
            ...prev,
            isPolling: false,
            detachedRun: false,
            detachedReason: null,
            error: `Run not found: ${errMsg}`,
          }));
          return null;
        }
        const isMonitorGap =
          res.status === 503 &&
          (
            errEnv.monitorUnavailable === true ||
            errEnv.code === 'RUN_MONITOR_UNAVAILABLE' ||
            errMsg.toLowerCase().includes('monitor unavailable') ||
            errMsg.toLowerCase().includes('status cache not found')
          );
        if (isMonitorGap) {
          monitorMissCountRef.current += 1;
          setState((prev) => ({
            ...prev,
            detachedRun: true,
            detachedReason:
              monitorMissCountRef.current >= 2
                ? 'Run monitor temporarily unavailable. Continuing polling and waiting for status reattach.'
                : prev.detachedReason,
            error:
              prev.error && prev.error.toLowerCase().includes('run monitor unavailable')
                ? null
                : prev.error,
          }));
          return prevRunStatusRef.current;
        }
        setState((prev) => ({
          ...prev,
          error: `Run monitor unavailable: ${errMsg}`,
        }));
        return null;
      }
      const json = await res.json();
      if (json?.monitorUnavailable) {
        const errMsg = String(json?.error || 'Run monitor unavailable.');
        monitorMissCountRef.current += 1;
        setState((prev) => ({
          ...prev,
          detachedRun: true,
          detachedReason:
            monitorMissCountRef.current >= 2
              ? `Run monitor temporarily unavailable: ${errMsg}`
              : prev.detachedReason,
          error:
            prev.error && prev.error.toLowerCase().includes('run monitor unavailable')
              ? null
              : prev.error,
        }));
        return prevRunStatusRef.current;
      }
      monitorMissCountRef.current = 0;
      const chunks = Array.isArray(json?.chunks) ? json.chunks : [];
      const running = chunks.find((c: any) => c?.status === 'running');
      const updatedAt = Number(json?.updatedAt || 0);
      const heartbeatAt = json?.heartbeatAt != null ? Number(json.heartbeatAt) : null;
      const lastDatasetBatchAt = json?.lastDatasetBatchAt != null ? Number(json.lastDatasetBatchAt) : null;
      const lastMovementAt =
        json?.lastMovementAt != null
          ? Number(json.lastMovementAt)
          : Math.max(updatedAt, heartbeatAt || 0, lastDatasetBatchAt || 0);
      if (lastMovementAt > lastSeenTimestampRef.current) {
        lastSeenTimestampRef.current = lastMovementAt;
        lastMovementAtRef.current = Date.now();
      }
      const elapsed = Date.now() - (lastMovementAtRef.current || Date.now());
      const stalled = elapsed >= stallThresholdMsRef.current && json?.state === 'running';

      const strategyId = running?.strategyId || null;
      const strategyName = strategyId
        ? STRATEGY_PRESETS.find((p) => p.id === strategyId)?.name ?? strategyId
        : null;

      const view: BacktestRunStatusView = {
        state: json?.state || 'running',
        progress: Number(json?.progress || 0),
        updatedAt,
        heartbeatAt,
        lastDatasetBatchAt,
        lastMovementAt,
        phase:
          json?.phase === 'universe_discovery' ||
          json?.phase === 'dataset_fetch' ||
          json?.phase === 'strategy_run' ||
          json?.phase === 'artifact_persist'
            ? json.phase
            : 'unknown',
        stale: !!json?.stale,
        staleReason: typeof json?.staleReason === 'string' ? json.staleReason : null,
        livenessBudgetSec: Number(json?.livenessBudgetSec || 0),
        completedChunks: Number(json?.completedChunks || 0),
        failedChunks: Number(json?.failedChunks || 0),
        totalChunks: Number(json?.totalChunks || 0),
        currentChunk: strategyName,
        currentActivity: typeof json?.currentActivity === 'string' ? json.currentActivity : null,
      };

      setState((prev) => ({
        ...prev,
        detachedRun: false,
        detachedReason: null,
        error:
          prev.error && prev.error.toLowerCase().includes('run monitor unavailable')
            ? null
            : prev.error,
        runStatus: view,
        isStalled: stalled,
        stallSeconds: stalled ? Math.floor(elapsed / 1000) : 0,
        progress: view.totalChunks > 0
          ? {
              current: Math.max(0, Math.min(view.totalChunks, view.completedChunks + view.failedChunks)),
              total: view.totalChunks,
              currentStrategy:
                view.currentChunk || view.currentActivity || prev.progress?.currentStrategy || 'Running...',
            }
          : prev.progress,
      }));
      prevRunStatusRef.current = view;

      if (view.state !== 'running') {
        const availability = await fetchArtifacts(runId);
        setState((prev) => ({
          ...prev,
          artifactAvailability: availability,
          isPolling: false,
          detachedRun: false,
          detachedReason: null,
          isStalled: false,
          stallSeconds: 0,
          error: view.stale ? (view.staleReason || 'Run became stale and was failed by liveness guard') : prev.error,
        }));
        if (pollTimerRef.current != null) {
          window.clearInterval(pollTimerRef.current);
          pollTimerRef.current = null;
        }
      }

      return view;
    } catch {
      return null;
    }
  }, [fetchArtifacts, readErrorFromResponse]);

  const startPolling = useCallback((runId: string) => {
    if (pollTimerRef.current != null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    lastMovementAtRef.current = Date.now();
    lastSeenTimestampRef.current = 0;
    monitorMissCountRef.current = 0;

    setState((prev) => ({
      ...prev,
      activeRunId: runId,
      isPolling: true,
      detachedRun: false,
      detachedReason: null,
      isStalled: false,
      stallSeconds: 0,
      runStatus: null,
      artifactAvailability: null,
    }));
    prevRunStatusRef.current = null;

    void pollRunStatusOnce(runId);
    pollTimerRef.current = window.setInterval(() => {
      void pollRunStatusOnce(runId);
    }, POLL_INTERVAL_MS);
  }, [pollRunStatusOnce]);

  // Hydrate from localStorage on mount
  useEffect(() => {
    const cached = loadCachedResults();
    if (cached.results) {
      setState((prev) => ({
        ...prev,
        results: cached.results ?? null,
        report: cached.report ?? null,
        evidence: cached.evidence ?? null,
        lastRunAt: cached.lastRunAt ?? null,
      }));
    }
  }, []);

  useEffect(() => () => {
    if (pollTimerRef.current != null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  /**
   * Run a backtest for a specific strategy (or 'all') in the given mode.
   */
  const runBacktest = useCallback(
    async (
      strategyId: string,
      mode: 'quick' | 'full' | 'grid' = 'quick',
      dataScale: BacktestDataScale = 'fast',
    ) => {
      stallThresholdMsRef.current = stallThresholdFor(mode, dataScale);
      const runId = `ui-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const manifestId = `manifest-${runId}`;
      startPolling(runId);

      setState((prev) => ({
        ...prev,
        isRunning: true,
        isPolling: true,
        detachedRun: false,
        detachedReason: null,
        activeRunId: runId,
        runStatus: null,
        artifactAvailability: null,
        isStalled: false,
        stallSeconds: 0,
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
          body: JSON.stringify({
            strategyId,
            mode,
            dataScale,
            includeEvidence: true,
            strictNoSynthetic: true,
            cohort: 'baseline_90d',
            lookbackHours: 2160,
            runId,
            manifestId,
          }),
        });

        if (!res.ok) {
          const postErrorEnv = await readErrorFromResponse(res);
          const postError = postErrorEnv.message;
          const status = await pollRunStatusOnce(runId);
          const availability = await fetchArtifacts(runId);
          setState((prev) => ({
            ...prev,
            isRunning: false,
            isPolling: status?.state === 'running',
            detachedRun: status?.state === 'running',
            detachedReason: status?.state === 'running'
              ? `Request returned ${postError}, but run is still active in background.`
              : null,
            activeRunId: runId,
            runStatus: status || prev.runStatus,
            artifactAvailability: availability,
            error:
              res.status >= 500
                ? `${postError}. The server may still be processing this run; monitoring will continue if status is available.`
                : postError,
          }));
          if (status?.state !== 'running') {
            stopPolling();
          }
          return;
        }

        const data = await res.json();
        const now = Date.now();
        const evidence = (data?.evidence as BacktestEvidenceMeta | null) ?? null;
        const resolvedRunId =
          typeof data?.runId === 'string' && data.runId.trim()
            ? data.runId.trim()
            : runId;

        if (resolvedRunId !== runId) {
          startPolling(resolvedRunId);
        }

        const latestStatus = await pollRunStatusOnce(resolvedRunId);
        const availability = await fetchArtifacts(resolvedRunId);
        setState((prev) => ({
          ...prev,
          isRunning: false,
          isPolling: false,
          detachedRun: false,
          detachedReason: null,
          activeRunId: resolvedRunId,
          runStatus: latestStatus || prev.runStatus,
          artifactAvailability: availability,
          progress: latestStatus?.totalChunks
            ? {
                current: Math.max(
                  0,
                  Math.min(latestStatus.totalChunks, latestStatus.completedChunks + latestStatus.failedChunks),
                ),
                total: latestStatus.totalChunks,
                currentStrategy:
                  latestStatus.currentChunk ||
                  latestStatus.currentActivity ||
                  prev.progress?.currentStrategy ||
                  'Completed',
              }
            : null,
          results: data.results ?? [],
          report: data.report ?? null,
          evidence,
          lastRunAt: now,
          error: null,
        }));

        // Persist to localStorage
        if (data.results) {
          saveCachedResults(data.results, data.report ?? null, evidence, now);
        }

        // Wire to Zustand store — guard against missing action (added in Plan 03)
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const storeState = useSniperStore.getState() as any;
        const updatePresets = storeState.updatePresetBacktestResults;
        // Only sync "quick" runs into the live presets. Grid/walk-forward results
        // are exploratory and shouldn't overwrite the active preset metadata.
        if (mode === 'quick' && typeof updatePresets === 'function' && data.results) {
          updatePresets(buildPresetBacktestUpdates(data.results as BacktestSummary[]));
        }
        stopPolling();
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Backtest failed';
        const status = await pollRunStatusOnce(runId);
        const availability = await fetchArtifacts(runId);
        setState((prev) => ({
          ...prev,
          isRunning: false,
          isPolling: status?.state === 'running',
          detachedRun: status?.state === 'running',
          detachedReason: status?.state === 'running'
            ? `Request channel failed (${message}), but run is still active in background.`
            : null,
          runStatus: status || prev.runStatus,
          artifactAvailability: availability,
          error: message,
        }));
        if (status?.state !== 'running') {
          stopPolling();
        }
      }
    },
    [fetchArtifacts, pollRunStatusOnce, readErrorFromResponse, startPolling, stopPolling],
  );

  /**
   * Convenience: run all strategies in quick mode.
   */
  const runAllStrategies = useCallback(
    (dataScale: BacktestDataScale = 'fast') => {
      return runBacktest('all', 'quick', dataScale);
    },
    [runBacktest],
  );

  /**
   * Clear all results (state + localStorage).
   */
  const clearResults = useCallback(() => {
    stopPolling();
    setState(INITIAL_STATE);
    if (typeof window !== 'undefined') {
      localStorage.removeItem(LS_KEY);
    }
  }, [stopPolling]);

  return { state, runBacktest, runAllStrategies, clearResults };
}
