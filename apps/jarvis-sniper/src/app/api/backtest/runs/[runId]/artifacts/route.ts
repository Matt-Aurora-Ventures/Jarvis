import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { NextResponse } from 'next/server';
import { getBacktestRunStatus } from '@/lib/backtest-run-registry';
import { backtestCorsOptions, withBacktestCors } from '@/lib/backtest-cors';
import { readArtifactFromGcs } from '@/lib/backtest-artifacts';

export const runtime = 'nodejs';

export function OPTIONS(request: Request) {
  return backtestCorsOptions(request);
}

function runDir(runId: string): string {
  return join(process.cwd(), '.jarvis-cache', 'backtest-runs', runId);
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ runId: string }> },
) {
  const { runId: requestedRunId } = await params;
  const run = getBacktestRunStatus(requestedRunId);
  const resolvedRunId = run?.evidenceRunId || requestedRunId;
  const dir = runDir(resolvedRunId);
  const manifestPath = join(dir, 'manifest.json');
  const evidencePath = join(dir, 'evidence.json');
  const reportPath = join(dir, 'report.md');
  const tradesPath = join(dir, 'trades.csv');

  const localDirExists = existsSync(dir);

  // Helper: read from local disk first, fall back to GCS (Cloud Run ephemeral storage).
  const formatToFilename: Record<string, string> = {
    manifest: 'manifest.json',
    evidence: 'evidence.json',
    report: 'report.md',
    csv: 'trades.csv',
  };

  async function readArtifact(localPath: string, filename: string): Promise<string | null> {
    if (existsSync(localPath)) return readFileSync(localPath, 'utf8');
    // GCS fallback — handles Cloud Run container restarts / instance drift.
    return readArtifactFromGcs(resolvedRunId, filename);
  }

  const url = new URL(request.url);
  const format = (url.searchParams.get('format') || '').toLowerCase();
  if (format) {
    const lookup: Record<string, { path: string; filename: string; contentType: string }> = {
      manifest: { path: manifestPath, filename: 'manifest.json', contentType: 'application/json; charset=utf-8' },
      evidence: { path: evidencePath, filename: 'evidence.json', contentType: 'application/json; charset=utf-8' },
      report: { path: reportPath, filename: 'report.md', contentType: 'text/markdown; charset=utf-8' },
      csv: { path: tradesPath, filename: 'trades.csv', contentType: 'text/csv; charset=utf-8' },
    };
    const hit = lookup[format];
    if (!hit) {
      return withBacktestCors(
        request,
        NextResponse.json(
          { error: `Artifact format "${format}" unavailable`, runId: requestedRunId },
          { status: 404 },
        ),
      );
    }
    const body = await readArtifact(hit.path, hit.filename);
    if (!body) {
      return withBacktestCors(
        request,
        NextResponse.json(
          { error: `Artifact format "${format}" unavailable`, runId: requestedRunId },
          { status: 404 },
        ),
      );
    }
    return withBacktestCors(request, new NextResponse(body, {
      headers: {
        'Content-Type': hit.contentType,
        'Cache-Control': 'no-store',
      },
    }));
  }

  // Availability check — probe local + GCS for each artifact.
  const availEntries = await Promise.all(
    Object.entries(formatToFilename).map(async ([key, filename]) => {
      const localPath = join(dir, filename);
      const localExists = localDirExists && existsSync(localPath);
      if (localExists) return [key, true] as const;
      const gcsBody = await readArtifactFromGcs(resolvedRunId, filename);
      return [key, gcsBody !== null] as const;
    }),
  );
  const available = Object.fromEntries(availEntries);

  if (!Object.values(available).some(Boolean)) {
    return withBacktestCors(
      request,
      NextResponse.json({ error: 'Artifacts not found', runId: requestedRunId }, { status: 404 }),
    );
  }

  return withBacktestCors(
    request,
    NextResponse.json({
      runId: requestedRunId,
      artifactRunId: resolvedRunId,
      available,
      links: {
        manifest: `/api/backtest/runs/${encodeURIComponent(requestedRunId)}/artifacts?format=manifest`,
        evidence: `/api/backtest/runs/${encodeURIComponent(requestedRunId)}/artifacts?format=evidence`,
        report: `/api/backtest/runs/${encodeURIComponent(requestedRunId)}/artifacts?format=report`,
        csv: `/api/backtest/runs/${encodeURIComponent(requestedRunId)}/artifacts?format=csv`,
      },
    }),
  );
}
