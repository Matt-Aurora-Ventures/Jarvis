import { Storage } from '@google-cloud/storage';
import { createHash, randomUUID } from 'crypto';
import { auditBucketName, isAuditBucketConfigured } from './audit-store';
import type { TradeTelemetryRecord, TradeTelemetryIngest } from './types';

let storageSingleton: Storage | null = null;
function gcs(): Storage {
  if (!storageSingleton) storageSingleton = new Storage();
  return storageSingleton;
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

function isoToParts(iso: string): { y: string; m: string; d: string; h: string } | null {
  try {
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return null;
    const y = String(dt.getUTCFullYear()).padStart(4, '0');
    const m = pad2(dt.getUTCMonth() + 1);
    const d = pad2(dt.getUTCDate());
    const h = pad2(dt.getUTCHours());
    return { y, m, d, h };
  } catch {
    return null;
  }
}

export function tradeTelemetryPrefixForIso(iso: string): string {
  const parts = isoToParts(iso);
  if (!parts) return 'telemetry/trades/unknown';
  return `telemetry/trades/${parts.y}/${parts.m}/${parts.d}/${parts.h}`;
}

function sha256(text: string): string {
  return createHash('sha256').update(text).digest('hex');
}

export async function writeTradeTelemetry(args: {
  payload: TradeTelemetryIngest;
  receivedAtIso?: string;
}): Promise<{ key: string; sha256: string } | null> {
  if (!isAuditBucketConfigured()) return null;
  const bucketName = auditBucketName();
  if (!bucketName) return null;

  const receivedAt = args.receivedAtIso || new Date().toISOString();
  const prefix = tradeTelemetryPrefixForIso(receivedAt);
  const eventId = (() => {
    try {
      return randomUUID();
    } catch {
      return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    }
  })();

  const record: TradeTelemetryRecord = {
    ...args.payload,
    receivedAt,
    source: 'client',
  };

  const key = `${prefix}/${Date.now()}-${eventId}.json`;
  const jsonText = JSON.stringify(record, null, 2);
  await gcs().bucket(bucketName).file(key).save(jsonText, {
    resumable: false,
    contentType: 'application/json',
    metadata: {
      cacheControl: 'no-store',
    },
  });
  return { key, sha256: sha256(jsonText) };
}

function startOfUtcDay(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
}

function addDaysUtc(date: Date, days: number): Date {
  const d = new Date(date.getTime());
  d.setUTCDate(d.getUTCDate() + days);
  return d;
}

function dayPrefix(date: Date): string {
  const y = String(date.getUTCFullYear()).padStart(4, '0');
  const m = pad2(date.getUTCMonth() + 1);
  const d = pad2(date.getUTCDate());
  return `telemetry/trades/${y}/${m}/${d}/`;
}

async function downloadJson(file: any): Promise<any | null> {
  try {
    const [buf] = await file.download();
    return JSON.parse(buf.toString('utf8'));
  } catch {
    return null;
  }
}

export async function listRecentTradeTelemetry(args: {
  days: number;
  maxRecords?: number;
}): Promise<TradeTelemetryRecord[]> {
  const bucketName = auditBucketName();
  if (!bucketName) return [];

  const maxRecords = Number.isFinite(args.maxRecords) ? Math.max(1, Math.floor(Number(args.maxRecords))) : 500;
  const days = Math.max(1, Math.floor(args.days));

  const now = new Date();
  const today = startOfUtcDay(now);
  const start = addDaysUtc(today, -1 * (days - 1));

  const prefixes: string[] = [];
  for (let i = 0; i < days; i++) {
    prefixes.push(dayPrefix(addDaysUtc(start, i)));
  }

  const bucket = gcs().bucket(bucketName);
  const files: any[] = [];
  for (const prefix of prefixes) {
    try {
      const [found] = await bucket.getFiles({ prefix });
      files.push(...found);
    } catch {
      // ignore prefix list failures
    }
  }

  // newest first; key includes ms prefix so lexical sort is roughly time-sorted within hour
  files.sort((a, b) => String(b.name).localeCompare(String(a.name)));
  const selected = files.slice(0, maxRecords);

  // Download with a small concurrency cap to avoid spiking RPC.
  const out: TradeTelemetryRecord[] = [];
  const concurrency = 20;
  for (let i = 0; i < selected.length; i += concurrency) {
    const chunk = selected.slice(i, i + concurrency);
    const rows = await Promise.all(chunk.map(downloadJson));
    for (const row of rows) {
      if (row && typeof row === 'object') out.push(row as TradeTelemetryRecord);
    }
  }

  // oldest first for equity/drawdown computations
  out.sort((a, b) => String(a.receivedAt || '').localeCompare(String(b.receivedAt || '')));
  return out;
}

export function summarizeTelemetry(records: TradeTelemetryRecord[]): {
  totalPnlSol: number;
  winCount: number;
  lossCount: number;
  tradeCount: number;
  drawdownPct: number;
  byStrategy: Record<string, { wins: number; losses: number; pnlSol: number }>;
} {
  let totalPnlSol = 0;
  let winCount = 0;
  let lossCount = 0;
  let tradeCount = 0;
  let equity = 0;
  let peak = 0;
  let maxDrawdown = 0;

  const byStrategy: Record<string, { wins: number; losses: number; pnlSol: number }> = {};

  for (const r of records) {
    if (!r || typeof r !== 'object') continue;
    if (r.includedInStats === false) continue;

    const pnl = Number(r.pnlSol);
    if (!Number.isFinite(pnl)) continue;
    tradeCount += 1;
    totalPnlSol += pnl;
    if (pnl >= 0) winCount += 1;
    else lossCount += 1;

    equity += pnl;
    peak = Math.max(peak, equity);
    maxDrawdown = Math.max(maxDrawdown, peak - equity);

    const sid = String(r.strategyId || '').trim();
    if (sid) {
      if (!byStrategy[sid]) byStrategy[sid] = { wins: 0, losses: 0, pnlSol: 0 };
      byStrategy[sid].pnlSol += pnl;
      if (pnl >= 0) byStrategy[sid].wins += 1;
      else byStrategy[sid].losses += 1;
    }
  }

  const drawdownPct = peak > 0 ? (maxDrawdown / peak) * 100 : 0;
  return {
    totalPnlSol: Number(totalPnlSol.toFixed(6)),
    winCount,
    lossCount,
    tradeCount,
    drawdownPct: Number(drawdownPct.toFixed(4)),
    byStrategy,
  };
}

