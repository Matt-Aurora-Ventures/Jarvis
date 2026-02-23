import { Storage } from '@google-cloud/storage';
import type { BacktestRunStatus } from './backtest-run-registry';

let storageSingleton: Storage | null = null;
function gcs(): Storage {
  if (!storageSingleton) storageSingleton = new Storage();
  return storageSingleton;
}

const lastWriteByRunId = new Map<string, number>();

export function backtestStatusBucketName(): string {
  return String(process.env.BACKTEST_STATUS_BUCKET || process.env.AUTONOMY_AUDIT_BUCKET || '').trim();
}

export function isBacktestStatusBucketConfigured(): boolean {
  return backtestStatusBucketName().length > 0;
}

function statusKey(runId: string): string {
  return `backtest/status/${runId}.json`;
}

export async function readBacktestRunStatusFromGcs(runId: string): Promise<BacktestRunStatus | null> {
  const bucket = backtestStatusBucketName();
  if (!bucket) return null;
  try {
    const file = gcs().bucket(bucket).file(statusKey(runId));
    const [exists] = await file.exists();
    if (!exists) return null;
    const [buf] = await file.download();
    return JSON.parse(buf.toString('utf8')) as BacktestRunStatus;
  } catch {
    return null;
  }
}

export async function writeBacktestRunStatusToGcs(run: BacktestRunStatus): Promise<void> {
  const bucket = backtestStatusBucketName();
  if (!bucket) return;
  const file = gcs().bucket(bucket).file(statusKey(run.runId));
  await file.save(JSON.stringify(run, null, 2), {
    resumable: false,
    contentType: 'application/json',
    metadata: {
      cacheControl: 'no-store',
    },
  });
}

export function writeBacktestRunStatusToGcsThrottled(run: BacktestRunStatus, minIntervalMs = 2000): void {
  const bucket = backtestStatusBucketName();
  if (!bucket) return;

  const now = Date.now();
  const last = lastWriteByRunId.get(run.runId) ?? 0;
  if (now - last < minIntervalMs) return;
  lastWriteByRunId.set(run.runId, now);

  void writeBacktestRunStatusToGcs(run).catch(() => {
    // best-effort only
  });
}

