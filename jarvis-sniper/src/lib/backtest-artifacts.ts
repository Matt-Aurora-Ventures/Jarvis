import { existsSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from 'fs';
import { join } from 'path';
import { evidenceTradesToCsv, type BacktestEvidenceBundle } from './backtest-evidence';

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
  } catch {
    // best-effort
  }
}

