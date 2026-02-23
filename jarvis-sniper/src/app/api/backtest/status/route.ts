import { NextResponse } from 'next/server';
import {
  computeLastMovementAt,
  getBacktestRunStatus,
  markBacktestRunStaleIfExpired,
} from '@/lib/backtest-run-registry';

export const runtime = 'nodejs';

const RUN_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{7,95}$/;

function normalizeRunId(raw: string): string {
  return String(raw || '').trim();
}

function isValidRunId(runId: string): boolean {
  return RUN_ID_PATTERN.test(normalizeRunId(runId));
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const runId = normalizeRunId(url.searchParams.get('runId') || '');

  if (!isValidRunId(runId)) {
    return NextResponse.json(
      {
        ok: false,
        error: 'Invalid runId format',
        runId,
      },
      { status: 400 },
    );
  }

  const staleChecked = markBacktestRunStaleIfExpired(runId);
  const run = staleChecked || getBacktestRunStatus(runId);
  if (!run) {
    return NextResponse.json(
      {
        ok: false,
        runId,
        error: 'Run ID not found (or expired from cache).',
      },
      { status: 404 },
    );
  }

  const manifestId = String(run.manifestId || '').trim();

  return NextResponse.json({
    ok: true,
    runId: run.runId,
    state: run.state,
    phase: run.phase ?? 'unknown',
    progress: run.progress,
    datasetManifestIds: manifestId ? [manifestId] : [],
    manifestId: manifestId || null,
    startedAt: run.startedAt,
    updatedAt: run.updatedAt,
    heartbeatAt: run.heartbeatAt ?? null,
    lastMovementAt: computeLastMovementAt(run),
    completedAt: run.completedAt ?? null,
    stale: !!run.stale,
    staleReason: run.staleReason ?? null,
    error: run.error ?? null,
  });
}
