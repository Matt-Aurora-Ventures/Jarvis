import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { NextResponse } from 'next/server';
import { getBacktestRunStatus } from '@/lib/backtest-run-registry';
import { backtestCorsOptions, withBacktestCors } from '@/lib/backtest-cors';

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

  if (!existsSync(dir)) {
    return withBacktestCors(
      request,
      NextResponse.json({ error: 'Artifacts not found', runId: requestedRunId }, { status: 404 }),
    );
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
      return withBacktestCors(
        request,
        NextResponse.json(
          { error: `Artifact format "${format}" unavailable`, runId: requestedRunId },
          { status: 404 },
        ),
      );
    }
    const body = readFileSync(hit.path, 'utf8');
    return withBacktestCors(request, new NextResponse(body, {
      headers: {
        'Content-Type': hit.contentType,
        'Cache-Control': 'no-store',
      },
    }));
  }

  return withBacktestCors(
    request,
    NextResponse.json({
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
    }),
  );
}
