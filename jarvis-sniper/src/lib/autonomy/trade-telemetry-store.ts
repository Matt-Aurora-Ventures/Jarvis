import { Storage } from '@google-cloud/storage';
import { createHash, randomUUID } from 'crypto';
import { auditBucketName, isAuditBucketConfigured } from './audit-store';
import type { TradeTelemetryRecord, TradeTelemetryIngest } from './types';

const LOCAL_ROOT = path.join(process.cwd(), '.jarvis-cache', 'autonomy');
const LOCAL_TELEMETRY_FILE = path.join(LOCAL_ROOT, 'trade-telemetry.ndjson');
const MAX_TELEMETRY_FILE_BYTES = 16 * 1024 * 1024;
const TRIM_TARGET_BYTES = 10 * 1024 * 1024;

export interface PersistedTradeTelemetryEvent extends TradeTelemetryEvent {
  trustLevel: 'trusted' | 'untrusted';
  receivedAt: string;
  receivedAtMs: number;
}

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

async function ensureLocalRoot(): Promise<void> {
  if (!existsSync(LOCAL_ROOT)) {
    await mkdir(LOCAL_ROOT, { recursive: true });
  }
}

function clampString(value: unknown, maxLen: number): string | undefined {
  const text = String(value || '').trim();
  if (!text) return undefined;
  return text.slice(0, maxLen);
}

function clampNumber(value: unknown, fallback = 0): number {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return n;
}

function sanitizeTelemetryEvent(input: TradeTelemetryEvent): PersistedTradeTelemetryEvent {
  const nowMs = Date.now();
  const normalized: PersistedTradeTelemetryEvent = {
    schemaVersion: Math.max(1, Math.floor(clampNumber(input.schemaVersion, 1))),
    eventType: input.eventType === 'sell_attempt' ? 'sell_attempt' : 'trade_closed',
    positionId: clampString(input.positionId, 128) || 'unknown',
    mint: clampString(input.mint, 128) || '',
    status: clampString(input.status, 64) || 'unknown',
    symbol: clampString(input.symbol, 64),
    walletAddress: clampString(input.walletAddress, 128) || null,
    strategyId: clampString(input.strategyId, 96) || null,
    entrySource: input.entrySource === 'auto' || input.entrySource === 'manual' ? input.entrySource : null,
    entryTime: Number.isFinite(Number(input.entryTime)) ? Number(input.entryTime) : null,
    exitTime: Number.isFinite(Number(input.exitTime)) ? Number(input.exitTime) : null,
    solInvested: Number.isFinite(Number(input.solInvested)) ? Number(input.solInvested) : null,
    exitSolReceived: Number.isFinite(Number(input.exitSolReceived)) ? Number(input.exitSolReceived) : null,
    pnlSol: Number.isFinite(Number(input.pnlSol)) ? Number(input.pnlSol) : null,
    pnlPercent: Number.isFinite(Number(input.pnlPercent)) ? Number(input.pnlPercent) : null,
    buyTxHash: clampString(input.buyTxHash, 128) || null,
    sellTxHash: clampString(input.sellTxHash, 128) || null,
    includedInStats: !!input.includedInStats,
    includedInExecutionStats: input.includedInExecutionStats !== false,
    executionOutcome:
      input.executionOutcome === 'confirmed'
      || input.executionOutcome === 'failed'
      || input.executionOutcome === 'unresolved'
      || input.executionOutcome === 'no_route'
        ? input.executionOutcome
        : undefined,
    failureCode: clampString(input.failureCode, 64) || null,
    failureReason: clampString(input.failureReason, 220) || null,
    attemptIndex: Number.isFinite(Number(input.attemptIndex)) ? Math.max(0, Math.floor(Number(input.attemptIndex))) : null,
    manualOnly: !!input.manualOnly,
    recoveredFrom: clampString(input.recoveredFrom, 64) || null,
    tradeSignerMode: clampString(input.tradeSignerMode, 32),
    sessionWalletPubkey: clampString(input.sessionWalletPubkey, 128) || null,
    activePreset: clampString(input.activePreset, 64) || null,
    trustLevel: input.trustLevel === 'trusted' ? 'trusted' : 'untrusted',
    receivedAt: new Date(nowMs).toISOString(),
    receivedAtMs: nowMs,
  };
  return normalized;
}

async function maybeTrimTelemetryFile(): Promise<void> {
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

export async function readTradeExecutionPriors(lookbackDays = 30): Promise<TradeExecutionPriors> {
  const rows = await listTradeTelemetryEvents();
  const now = Date.now();
  const windowMs = Math.max(1, Math.floor(lookbackDays)) * 24 * 60 * 60 * 1000;
  const cutoff = now - windowMs;
  const scoped = rows.filter((r) => Number(r.receivedAtMs || 0) >= cutoff);
  const trustedScoped = scoped.filter((r) => r.trustLevel === 'trusted');
  const attempts = trustedScoped.filter((r) => r.eventType === 'sell_attempt' && r.includedInExecutionStats !== false);
  const totalSellAttempts = attempts.length;
  const confirmedEvents = attempts.filter((r) => r.executionOutcome === 'confirmed').length;
  const noRouteEvents = attempts.filter((r) => r.executionOutcome === 'no_route').length;
  const unresolvedEvents = attempts.filter((r) => r.executionOutcome === 'unresolved').length;
  const failedEvents = attempts.filter((r) => r.executionOutcome === 'failed').length;

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
    sampleSize: trustedScoped.length,
    lookbackDays: Math.max(1, Math.floor(lookbackDays)),
    totalSellAttempts,
    confirmedEvents,
    noRouteEvents,
    unresolvedEvents,
    failedEvents,
    noRouteRate,
    unresolvedRate,
    failedRate,
    executionReliabilityPct: reliability * 100,
  };
}

