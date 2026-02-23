import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { NextResponse } from 'next/server';
import { getBacktestEvidence } from '@/lib/backtest-evidence';
import { getBacktestRunStatus, markBacktestRunStaleIfExpired } from '@/lib/backtest-run-registry';

export const runtime = 'nodejs';

const RUN_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{7,95}$/;
const ARTIFACTS_ROOT = join(process.cwd(), '.jarvis-cache', 'backtest-runs');

function normalizeRunId(raw: string): string {
  return String(raw || '').trim();
}

function isValidRunId(runId: string): boolean {
  return RUN_ID_PATTERN.test(normalizeRunId(runId));
}

function readArtifactManifest(runId: string): Record<string, unknown> | null {
  try {
    const p = join(ARTIFACTS_ROOT, runId, 'manifest.json');
    if (!existsSync(p)) return null;
    return JSON.parse(readFileSync(p, 'utf8')) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const runId = normalizeRunId(url.searchParams.get('runId') || '');

  if (!isValidRunId(runId)) {
    return NextResponse.json(
      {
        ok: false,
        runId,
        error: 'Invalid runId format',
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

  if (run.state === 'running') {
    return NextResponse.json(
      {
        ok: false,
        runId,
        state: run.state,
        phase: run.phase ?? 'unknown',
        progress: run.progress,
        error: 'Run not complete yet',
      },
      { status: 409 },
    );
  }

  const evidenceRunId = String(run.evidenceRunId || run.runId || runId).trim();
  const evidence = evidenceRunId ? getBacktestEvidence(evidenceRunId) : null;
  const manifest = evidenceRunId ? readArtifactManifest(evidenceRunId) : null;
  const manifestSummary = Array.isArray(manifest?.resultsSummary)
    ? (manifest.resultsSummary as unknown[])
    : [];
  const summary = Array.isArray(evidence?.resultsSummary)
    ? evidence.resultsSummary
    : manifestSummary;
  const manifestId = String(run.manifestId || '').trim();
  const encodedRunId = encodeURIComponent(runId);
  const artifactBase = `/api/backtest/runs/${encodedRunId}/artifacts`;

  return NextResponse.json({
    ok: true,
    runId: run.runId,
    state: run.state,
    phase: run.phase ?? 'unknown',
    progress: run.progress,
    completedAt: run.completedAt ?? null,
    datasetManifestIds: manifestId ? [manifestId] : [],
    summary,
    evidence: evidence
      ? {
          runId: evidence.runId,
          datasetCount: evidence.datasets.length,
          tradeCount: evidence.trades.length,
        }
      : null,
    artifacts: {
      index: artifactBase,
      manifest: `${artifactBase}?format=manifest`,
      evidence: `${artifactBase}?format=evidence`,
      report: `${artifactBase}?format=report`,
      csv: `${artifactBase}?format=csv`,
    },
    error: run.error ?? null,
  });
}
