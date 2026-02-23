import { existsSync, readFileSync } from 'fs';
import { join, normalize, resolve, sep } from 'path';
import { NextResponse } from 'next/server';
import { getBacktestRunStatus } from '@/lib/backtest-run-registry';

export const runtime = 'nodejs';

const ARTIFACTS_ROOT = resolve(process.cwd(), '.jarvis-cache', 'backtest-runs');
const RUN_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{7,95}$/;

function isValidRunId(runId: string): boolean {
  const normalized = String(runId || '').trim();
  return RUN_ID_PATTERN.test(normalized);
}

function resolveRunDirSafe(runId: string): string | null {
  if (!isValidRunId(runId)) return null;

  const candidate = resolve(ARTIFACTS_ROOT, runId);
  const normalizedRoot = normalize(ARTIFACTS_ROOT).toLowerCase();
  const normalizedCandidate = normalize(candidate).toLowerCase();
  const rootPrefix = normalizedRoot.endsWith(sep)
    ? normalizedRoot
    : `${normalizedRoot}${sep}`;

  if (!normalizedCandidate.startsWith(rootPrefix)) return null;
  return candidate;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId: rawRequestedRunId } = await params;
  const requestedRunId = String(rawRequestedRunId || '').trim();
  if (!isValidRunId(requestedRunId)) {
    return NextResponse.json({ error: 'Invalid runId format', runId: requestedRunId }, { status: 400 });
  }

  const run = getBacktestRunStatus(requestedRunId);
  const resolvedRunId = String(run?.evidenceRunId || requestedRunId).trim();
  if (!isValidRunId(resolvedRunId)) {
    return NextResponse.json({ error: 'Invalid resolved runId format', runId: requestedRunId }, { status: 400 });
  }

  const dir = resolveRunDirSafe(resolvedRunId);
  if (!dir) {
    return NextResponse.json({ error: 'Invalid artifact path', runId: requestedRunId }, { status: 400 });
  }

  const manifestPath = join(dir, 'manifest.json');
  const evidencePath = join(dir, 'evidence.json');
  const reportPath = join(dir, 'report.md');
  const tradesPath = join(dir, 'trades.csv');

  if (!existsSync(dir)) {
    return NextResponse.json({ error: 'Artifacts not found', runId: requestedRunId }, { status: 404 });
  }

  const url = new URL(request.url);
  const format = (url.searchParams.get('format') || '').toLowerCase();
  if (format) {
    const lookup: Record<string, { path: string; contentType: string }> = {
      manifest: { path: manifestPath, contentType: 'application/json; charset=utf-8' },
      evidence: { path: evidencePath, contentType: 'application/json; charset=utf-8' },
      report: { path: reportPath, contentType: 'text/markdown; charset=utf-8' },
      csv: { path: tradesPath, contentType: 'text/csv; charset=utf-8' },
    };
    const hit = lookup[format];
    if (!hit || !existsSync(hit.path)) {
      return NextResponse.json({ error: `Artifact format "${format}" unavailable`, runId: requestedRunId }, { status: 404 });
    }
    const body = readFileSync(hit.path, 'utf8');
    return new NextResponse(body, {
      headers: {
        'Content-Type': hit.contentType,
        'Cache-Control': 'no-store',
      },
    });
  }

  return NextResponse.json({
    runId: requestedRunId,
    artifactRunId: resolvedRunId,
    available: {
      manifest: existsSync(manifestPath),
      evidence: existsSync(evidencePath),
      report: existsSync(reportPath),
      csv: existsSync(tradesPath),
    },
    links: {
      manifest: `/api/backtest/runs/${encodeURIComponent(requestedRunId)}/artifacts?format=manifest`,
      evidence: `/api/backtest/runs/${encodeURIComponent(requestedRunId)}/artifacts?format=evidence`,
      report: `/api/backtest/runs/${encodeURIComponent(requestedRunId)}/artifacts?format=report`,
      csv: `/api/backtest/runs/${encodeURIComponent(requestedRunId)}/artifacts?format=csv`,
    },
  });
}