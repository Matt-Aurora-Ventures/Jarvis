import { NextResponse } from 'next/server';
import {
  computeLastMovementAt,
  getBacktestRunStatus,
  markBacktestRunStaleIfExpired,
} from '@/lib/backtest-run-registry';

export const runtime = 'nodejs';

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId } = await params;
  const runEpochMatch = /^ui-(\d{10,13})-/i.exec(String(runId || '').trim());
  const runStartedAt = runEpochMatch ? Number(runEpochMatch[1]) : 0;
  const runAgeMs = runStartedAt > 0 ? Math.max(0, Date.now() - runStartedAt) : Number.POSITIVE_INFINITY;

  let run = null as ReturnType<typeof getBacktestRunStatus> | null;
  try {
    const staleChecked = markBacktestRunStaleIfExpired(runId);
    run = staleChecked || getBacktestRunStatus(runId);
  } catch {
    return NextResponse.json(
      {
        runId,
        state: 'unknown',
        monitorUnavailable: true,
        runMissing: false,
        retryable: true,
        code: 'RUN_MONITOR_UNAVAILABLE',
        error: 'Run monitor temporarily unavailable. Please retry status polling.',
      },
      { status: 503 },
    );
  }
  if (!run) {
    const likelyRecent = Number.isFinite(runAgeMs) && runAgeMs <= 5 * 60 * 1000;
    if (likelyRecent) {
      return NextResponse.json(
        {
          runId,
          state: 'unknown',
          monitorUnavailable: true,
          runMissing: false,
          retryable: true,
          code: 'RUN_MONITOR_UNAVAILABLE',
          error: 'Run monitor temporarily unavailable. Status cache not found yet for this run ID.',
        },
        { status: 503 },
      );
    }
    return NextResponse.json(
      {
        runId,
        state: 'unknown',
        monitorUnavailable: false,
        runMissing: true,
        retryable: false,
        code: 'RUN_NOT_FOUND',
        error: 'Run ID not found (or expired from cache).',
      },
      { status: 404 },
    );
  }

  const lastMovementAt = computeLastMovementAt(run);
  const livenessBudgetSec = Math.max(60, Math.floor(run.livenessBudgetSec || (run.totalChunks > 1 ? 45 * 60 : 15 * 60)));

  return NextResponse.json({
    runId: run.runId,
    manifestId: run.manifestId,
    state: run.state,
    progress: run.progress,
    startedAt: run.startedAt,
    updatedAt: run.updatedAt,
    heartbeatAt: run.heartbeatAt ?? null,
    lastDatasetBatchAt: run.lastDatasetBatchAt ?? null,
    lastMovementAt,
    currentActivity: run.currentActivity ?? null,
    phase: run.phase ?? 'unknown',
    stale: !!run.stale,
    staleReason: run.staleReason ?? null,
    livenessBudgetSec,
    completedAt: run.completedAt ?? null,
    totalChunks: run.totalChunks,
    completedChunks: run.completedChunks,
    failedChunks: run.failedChunks,
    datasetsAttempted: run.datasetsAttempted ?? 0,
    datasetsSucceeded: run.datasetsSucceeded ?? 0,
    datasetsFailed: run.datasetsFailed ?? 0,
    chunks: run.chunks,
    evidenceRunId: run.evidenceRunId ?? null,
    artifactsPath: run.artifactsPath ?? null,
    sourceDiagnostics: {
      strictNoSynthetic: run.strictNoSynthetic,
      targetTradesPerStrategy: run.targetTradesPerStrategy,
      sourceTierPolicy: run.sourceTierPolicy,
      cohort: run.cohort,
    },
    error: run.error ?? null,
  });
}
