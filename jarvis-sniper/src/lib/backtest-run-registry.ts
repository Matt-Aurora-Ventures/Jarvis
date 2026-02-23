import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { ServerCache } from './server-cache';
import {
  readBacktestRunStatusFromGcs,
  writeBacktestRunStatusToGcsThrottled,
} from './backtest-run-status-store';

export type BacktestRunState = 'running' | 'completed' | 'failed' | 'partial';

export interface BacktestChunkStatus {
  id: string;
  strategyId: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startedAt?: number;
  endedAt?: number;
  elapsedMs?: number;
  error?: string;
}

export interface BacktestRunStatus {
  runId: string;
  manifestId: string;
  state: BacktestRunState;
  startedAt: number;
  updatedAt: number;
  heartbeatAt?: number;
  lastDatasetBatchAt?: number;
  lastMovementAt?: number;
  phase?: 'universe_discovery' | 'dataset_fetch' | 'strategy_run' | 'artifact_persist' | 'unknown';
  currentActivity?: string;
  completedAt?: number;
  stale?: boolean;
  staleReason?: string;
  livenessBudgetSec?: number;
  totalChunks: number;
  completedChunks: number;
  failedChunks: number;
  datasetsAttempted?: number;
  datasetsSucceeded?: number;
  datasetsFailed?: number;
  progress: number;
  chunks: BacktestChunkStatus[];
  strictNoSynthetic: boolean;
  targetTradesPerStrategy: number;
  sourceTierPolicy: string;
  cohort: string;
  evidenceRunId?: string;
  artifactsPath?: string;
  error?: string;
}

const RUN_TTL_MS = 24 * 60 * 60 * 1000;
const runCache = new ServerCache<BacktestRunStatus>();
const STATUS_DIR = join(process.cwd(), '.jarvis-cache', 'backtest-status');

function statusPath(runId: string): string {
  return join(STATUS_DIR, `${runId}.json`);
}

function persistRunStatus(run: BacktestRunStatus): void {
  try {
    if (!existsSync(STATUS_DIR)) mkdirSync(STATUS_DIR, { recursive: true });
    writeFileSync(statusPath(run.runId), JSON.stringify(run, null, 2), 'utf8');
  } catch {
    // best effort only
  }

  // Best-effort cross-instance visibility (Cloud Run often serves polling from different instances).
  writeBacktestRunStatusToGcsThrottled(run);
}

function touch(run: BacktestRunStatus): BacktestRunStatus {
  const now = Date.now();
  run.updatedAt = now;
  run.heartbeatAt = run.updatedAt;
  run.lastMovementAt = computeLastMovementAt(run);
  run.progress = run.totalChunks > 0
    ? Math.max(0, Math.min(100, Math.round(((run.completedChunks + run.failedChunks) / run.totalChunks) * 100)))
    : 0;
  return run;
}

function computeDefaultLivenessBudgetSec(run: BacktestRunStatus): number {
  // Deep/thorough multi-strategy runs need longer runway under free-tier API pacing.
  return run.totalChunks > 1 ? 45 * 60 : 15 * 60;
}

export function computeLastMovementAt(run: Pick<BacktestRunStatus, 'updatedAt' | 'heartbeatAt' | 'lastDatasetBatchAt'>): number {
  return Math.max(
    Number(run.updatedAt || 0),
    Number(run.heartbeatAt || 0),
    Number(run.lastDatasetBatchAt || 0),
  );
}

export function createBacktestRunStatus(args: {
  runId: string;
  manifestId?: string;
  strategyIds: string[];
  strictNoSynthetic?: boolean;
  targetTradesPerStrategy?: number;
  sourceTierPolicy?: string;
  cohort?: string;
  livenessBudgetSec?: number;
}): BacktestRunStatus {
  const now = Date.now();
  const run: BacktestRunStatus = {
    runId: args.runId,
    manifestId: args.manifestId || `manifest-${args.runId}`,
    state: 'running',
    startedAt: now,
    updatedAt: now,
    heartbeatAt: now,
    lastDatasetBatchAt: now,
    lastMovementAt: now,
    phase: 'unknown',
    currentActivity: 'Preparing backtest run',
    stale: false,
    staleReason: undefined,
    livenessBudgetSec: args.livenessBudgetSec,
    totalChunks: args.strategyIds.length,
    completedChunks: 0,
    failedChunks: 0,
    datasetsAttempted: 0,
    datasetsSucceeded: 0,
    datasetsFailed: 0,
    progress: 0,
    chunks: args.strategyIds.map((sid, idx) => ({
      id: `${args.runId}:${idx}:${sid}`,
      strategyId: sid,
      status: 'pending',
    })),
    strictNoSynthetic: !!args.strictNoSynthetic,
    targetTradesPerStrategy: Math.max(1, Math.floor(args.targetTradesPerStrategy || 5000)),
    sourceTierPolicy: args.sourceTierPolicy || 'adaptive_tiered',
    cohort: args.cohort || 'baseline_90d',
  };
  runCache.set(run.runId, run, RUN_TTL_MS);
  persistRunStatus(run);
  return run;
}

export function getBacktestRunStatus(runId: string): BacktestRunStatus | null {
  const cached = runCache.get(runId);

  // Disk-backed run status survives dev HMR and server process turnover.
  //
  // IMPORTANT: Always prefer disk state when it is newer than the in-memory cache.
  // In Next.js dev/App Hosting, different requests can be handled by different
  // processes/instances; one instance may be writing status updates while another
  // serves the status endpoint. Returning a long-TTL in-memory cache here causes
  // the UI to "stall/spin" even though the run is progressing on disk.
  try {
    const diskPath = statusPath(runId);
    if (existsSync(diskPath)) {
      const restored = JSON.parse(readFileSync(diskPath, 'utf8')) as BacktestRunStatus;
      if (!cached) {
        runCache.set(runId, restored, RUN_TTL_MS);
        return restored;
      }

      const restoredMovement = computeLastMovementAt(restored);
      const cachedMovement = computeLastMovementAt(cached);
      const isNewer =
        restoredMovement > cachedMovement ||
        restored.updatedAt > cached.updatedAt ||
        restored.state !== cached.state ||
        restored.progress !== cached.progress ||
        restored.completedChunks !== cached.completedChunks ||
        restored.failedChunks !== cached.failedChunks ||
        restored.currentActivity !== cached.currentActivity;

      if (isNewer) {
        runCache.set(runId, restored, RUN_TTL_MS);
        return restored;
      }
    }
  } catch {
    // If disk read/parse fails, fall back to cache (if present) to avoid breaking polling.
    if (cached) return cached;
  }

  if (cached) return cached;

  // Best-effort disk fallback from persisted artifacts.
  try {
    const manifestPath = join(process.cwd(), '.jarvis-cache', 'backtest-runs', runId, 'manifest.json');
    if (!existsSync(manifestPath)) return null;
    const raw = JSON.parse(readFileSync(manifestPath, 'utf8'));
    const now = Date.now();
    const fallback: BacktestRunStatus = {
      runId,
      manifestId: String(raw?.runId || `manifest-${runId}`),
      state: 'completed',
      startedAt: now,
      updatedAt: now,
      heartbeatAt: now,
      lastDatasetBatchAt: now,
      currentActivity: 'Recovered from artifact cache',
      completedAt: now,
      totalChunks: 1,
      completedChunks: 1,
      failedChunks: 0,
      datasetsAttempted: 0,
      datasetsSucceeded: 0,
      datasetsFailed: 0,
      progress: 100,
      chunks: [
        {
          id: `${runId}:artifact`,
          strategyId: 'all',
          status: 'completed',
        },
      ],
      strictNoSynthetic: true,
      targetTradesPerStrategy: 5000,
      sourceTierPolicy: 'adaptive_tiered',
      cohort: 'baseline_90d',
      artifactsPath: manifestPath,
      evidenceRunId: String(raw?.runId || ''),
    };
    runCache.set(runId, fallback, RUN_TTL_MS);
    persistRunStatus(fallback);
    return fallback;
  } catch {
    return null;
  }
}

export async function getBacktestRunStatusRemote(runId: string): Promise<BacktestRunStatus | null> {
  const remote = await readBacktestRunStatusFromGcs(runId);
  if (!remote) return null;

  runCache.set(runId, remote, RUN_TTL_MS);
  persistRunStatus(remote);
  return remote;
}

export function markBacktestChunkRunning(runId: string, strategyId: string): void {
  const run = getBacktestRunStatus(runId);
  if (!run) return;
  const chunk = run.chunks.find((c) => c.strategyId === strategyId);
  if (!chunk) return;
  chunk.status = 'running';
  chunk.startedAt = Date.now();
  run.state = 'running';
  run.phase = 'strategy_run';
  run.stale = false;
  run.staleReason = undefined;
  run.currentActivity = `Running strategy: ${strategyId}`;
  runCache.set(runId, touch(run), RUN_TTL_MS);
  persistRunStatus(run);
}

export function markBacktestChunkDone(runId: string, strategyId: string): void {
  const run = getBacktestRunStatus(runId);
  if (!run) return;
  const chunk = run.chunks.find((c) => c.strategyId === strategyId);
  if (!chunk) return;
  if (chunk.status !== 'completed') {
    chunk.status = 'completed';
    chunk.endedAt = Date.now();
    chunk.elapsedMs = chunk.startedAt ? Math.max(0, chunk.endedAt - chunk.startedAt) : undefined;
    run.completedChunks += 1;
  }
  run.phase = 'strategy_run';
  run.currentActivity = `Completed strategy: ${strategyId}`;
  runCache.set(runId, touch(run), RUN_TTL_MS);
  persistRunStatus(run);
}

export function markBacktestChunkFailed(runId: string, strategyId: string, error: string): void {
  const run = getBacktestRunStatus(runId);
  if (!run) return;
  const chunk = run.chunks.find((c) => c.strategyId === strategyId);
  if (!chunk) return;
  if (chunk.status !== 'failed') {
    chunk.status = 'failed';
    chunk.error = error;
    chunk.endedAt = Date.now();
    chunk.elapsedMs = chunk.startedAt ? Math.max(0, chunk.endedAt - chunk.startedAt) : undefined;
    run.failedChunks += 1;
  }
  run.phase = 'strategy_run';
  run.currentActivity = `Failed strategy: ${strategyId}`;
  runCache.set(runId, touch(run), RUN_TTL_MS);
  persistRunStatus(run);
}

export function finalizeBacktestRun(runId: string, args?: { evidenceRunId?: string; artifactsPath?: string }): void {
  const run = getBacktestRunStatus(runId);
  if (!run) return;
  run.completedAt = Date.now();
  run.evidenceRunId = args?.evidenceRunId || run.evidenceRunId;
  run.artifactsPath = args?.artifactsPath || run.artifactsPath;
  run.phase = 'artifact_persist';
  run.currentActivity = 'Finalizing artifacts';
  run.state = run.failedChunks > 0
    ? (run.completedChunks > 0 ? 'partial' : 'failed')
    : 'completed';
  runCache.set(runId, touch(run), RUN_TTL_MS);
  persistRunStatus(run);
}

export function failBacktestRun(runId: string, error: string): void {
  const run = getBacktestRunStatus(runId);
  if (!run) return;
  run.state = 'failed';
  run.error = error;
  run.phase = 'unknown';
  run.stale = false;
  run.staleReason = undefined;
  run.currentActivity = 'Run failed';
  run.completedAt = Date.now();
  runCache.set(runId, touch(run), RUN_TTL_MS);
  persistRunStatus(run);
}

export function heartbeatBacktestRun(runId: string, activity?: string): void {
  const run = getBacktestRunStatus(runId);
  if (!run) return;
  run.stale = false;
  run.staleReason = undefined;
  if (activity && activity.trim()) {
    run.currentActivity = activity.trim();
  }
  runCache.set(runId, touch(run), RUN_TTL_MS);
  persistRunStatus(run);
}

export function markBacktestRunPhase(
  runId: string,
  phase: BacktestRunStatus['phase'],
  activity?: string,
): void {
  const run = getBacktestRunStatus(runId);
  if (!run) return;
  run.phase = phase || 'unknown';
  run.stale = false;
  run.staleReason = undefined;
  if (activity && activity.trim()) {
    run.currentActivity = activity.trim();
  }
  runCache.set(runId, touch(run), RUN_TTL_MS);
  persistRunStatus(run);
}

export function markBacktestDatasetBatch(
  runId: string,
  args: {
    attemptedDelta?: number;
    succeededDelta?: number;
    failedDelta?: number;
    activity?: string;
  },
): void {
  const run = getBacktestRunStatus(runId);
  if (!run) return;
  const attemptedDelta = Math.max(0, Math.floor(args.attemptedDelta || 0));
  const succeededDelta = Math.max(0, Math.floor(args.succeededDelta || 0));
  const failedDelta = Math.max(0, Math.floor(args.failedDelta || 0));
  run.datasetsAttempted = Math.max(0, Math.floor(run.datasetsAttempted || 0) + attemptedDelta);
  run.datasetsSucceeded = Math.max(0, Math.floor(run.datasetsSucceeded || 0) + succeededDelta);
  run.datasetsFailed = Math.max(0, Math.floor(run.datasetsFailed || 0) + failedDelta);
  run.phase = 'dataset_fetch';
  run.lastDatasetBatchAt = Date.now();
  run.lastMovementAt = computeLastMovementAt(run);
  run.stale = false;
  run.staleReason = undefined;
  if (args.activity && args.activity.trim()) {
    run.currentActivity = args.activity.trim();
  }
  runCache.set(runId, touch(run), RUN_TTL_MS);
  persistRunStatus(run);
}

export function markBacktestRunStaleIfExpired(runId: string, nowMs = Date.now()): BacktestRunStatus | null {
  const run = getBacktestRunStatus(runId);
  if (!run) return null;
  if (run.state !== 'running') return run;
  if (run.stale) return run;

  const lastMovementAt = computeLastMovementAt(run);
  const livenessBudgetSec = Math.max(60, Math.floor(run.livenessBudgetSec || computeDefaultLivenessBudgetSec(run)));
  const staleThresholdMs = livenessBudgetSec * 1000;

  if (nowMs - lastMovementAt < staleThresholdMs) return run;

  run.state = 'failed';
  run.stale = true;
  run.staleReason = `No heartbeat/progress movement within liveness budget (${livenessBudgetSec}s).`;
  run.error = run.error || run.staleReason;
  run.completedAt = nowMs;
  run.currentActivity = 'Run marked stale';
  run.lastMovementAt = lastMovementAt;
  // Keep the heartbeat timestamp untouched to preserve factual last movement timing.
  run.updatedAt = nowMs;
  run.progress = run.totalChunks > 0
    ? Math.max(0, Math.min(100, Math.round(((run.completedChunks + run.failedChunks) / run.totalChunks) * 100)))
    : 0;
  runCache.set(runId, run, RUN_TTL_MS);
  persistRunStatus(run);
  return run;
}
