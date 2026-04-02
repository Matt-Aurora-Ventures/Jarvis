import { existsSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from 'fs';
import { join } from 'path';
import { Storage } from '@google-cloud/storage';
import { evidenceTradesToCsv, type BacktestEvidenceBundle } from './backtest-evidence';
import { backtestStatusBucketName } from './backtest-run-status-store';

let _gcsStorage: Storage | null = null;
function gcs(): Storage {
  if (!_gcsStorage) _gcsStorage = new Storage();
  return _gcsStorage;
}

function artifactGcsKey(runId: string, filename: string): string {
  return `backtest/artifacts/${runId}/${filename}`;
}

/**
 * Persist backtest runs to disk for longer-lived research / tuning workflows.
 *
 * This is intentionally separate from the short-lived evidence cache:
 * - evidence cache: optimized for UI downloads (TTL)
 * - artifacts: keeps a rolling window of the most recent runs for auditability
 *
 * Best-effort: if filesystem is unavailable (edge/serverless), it silently no-ops.
 */

const RUNS_DIR = join(process.cwd(), '.jarvis-cache', 'backtest-runs');
const MAX_RUNS = 40;

function ensureRunsDir(): void {
  if (!existsSync(RUNS_DIR)) mkdirSync(RUNS_DIR, { recursive: true });
}

function safeRm(dir: string): void {
  try {
    rmSync(dir, { recursive: true, force: true });
  } catch {
    // ignore
  }
}

function cleanupOldRuns(): void {
  try {
    if (!existsSync(RUNS_DIR)) return;
    const entries = readdirSync(RUNS_DIR, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => d.name);

    if (entries.length <= MAX_RUNS) return;

    const sortable = entries
      .map((name) => {
        const full = join(RUNS_DIR, name);
        let mtime = 0;
        try {
          mtime = statSync(full).mtimeMs;
        } catch {
          // ignore
        }
        return { name, full, mtime };
      })
      .sort((a, b) => b.mtime - a.mtime);

    for (const victim of sortable.slice(MAX_RUNS)) safeRm(victim.full);
  } catch {
    // ignore
  }
}

export function persistBacktestArtifacts(bundle: BacktestEvidenceBundle): void {
  try {
    ensureRunsDir();
    cleanupOldRuns();

    const dir = join(RUNS_DIR, bundle.runId);
    mkdirSync(dir, { recursive: true });

    // Evidence bundle (full fidelity)
    writeFileSync(join(dir, 'evidence.json'), JSON.stringify(bundle, null, 2), 'utf8');

    // Manifest (compact entrypoint)
    writeFileSync(
      join(dir, 'manifest.json'),
      JSON.stringify(
        {
          runId: bundle.runId,
          generatedAt: bundle.generatedAt,
          request: bundle.request,
          meta: bundle.meta,
          datasetCount: bundle.datasets.length,
          tradeCount: bundle.trades.length,
          datasets: bundle.datasets,
          resultsSummary: bundle.resultsSummary,
        },
        null,
        2,
      ),
      'utf8',
    );

    // Trade ledger
    writeFileSync(join(dir, 'trades.csv'), evidenceTradesToCsv(bundle), 'utf8');

    // Markdown report (if available)
    if (bundle.reportMd) {
      writeFileSync(join(dir, 'report.md'), bundle.reportMd, 'utf8');
    }

    // Also persist to GCS so artifacts survive container restarts on Cloud Run.
    void persistArtifactsToGcs(bundle).catch(() => {/* best-effort */});
  } catch {
    // best-effort
  }
}

async function persistArtifactsToGcs(bundle: BacktestEvidenceBundle): Promise<void> {
  const bucket = backtestStatusBucketName();
  if (!bucket) return;

  const files: Array<{ key: string; body: string; contentType: string }> = [
    {
      key: artifactGcsKey(bundle.runId, 'evidence.json'),
      body: JSON.stringify(bundle, null, 2),
      contentType: 'application/json',
    },
    {
      key: artifactGcsKey(bundle.runId, 'manifest.json'),
      body: JSON.stringify({
        runId: bundle.runId,
        generatedAt: bundle.generatedAt,
        request: bundle.request,
        meta: bundle.meta,
        datasetCount: bundle.datasets.length,
        tradeCount: bundle.trades.length,
        datasets: bundle.datasets,
        resultsSummary: bundle.resultsSummary,
      }, null, 2),
      contentType: 'application/json',
    },
    {
      key: artifactGcsKey(bundle.runId, 'trades.csv'),
      body: evidenceTradesToCsv(bundle),
      contentType: 'text/csv',
    },
  ];

  if (bundle.reportMd) {
    files.push({
      key: artifactGcsKey(bundle.runId, 'report.md'),
      body: bundle.reportMd,
      contentType: 'text/markdown',
    });
  }

  await Promise.all(
    files.map((f) =>
      gcs().bucket(bucket).file(f.key).save(f.body, {
        resumable: false,
        contentType: f.contentType,
        metadata: { cacheControl: 'no-store' },
      }),
    ),
  );
}

/**
 * Read a single artifact from GCS.  Falls back when local disk is empty
 * (e.g. Cloud Run container restarted between write and read).
 */
export async function readArtifactFromGcs(
  runId: string,
  filename: string,
): Promise<string | null> {
  const bucket = backtestStatusBucketName();
  if (!bucket) return null;
  try {
    const file = gcs().bucket(bucket).file(artifactGcsKey(runId, filename));
    const [exists] = await file.exists();
    if (!exists) return null;
    const [buf] = await file.download();
    return buf.toString('utf8');
  } catch {
    return null;
  }
}

