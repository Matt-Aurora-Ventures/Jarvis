import { existsSync } from 'fs';
import { appendFile, mkdir, readFile, stat, writeFile } from 'fs/promises';
import path from 'path';
import type { TradeTelemetryEvent } from './trade-telemetry-client';

const LOCAL_ROOT = path.join(process.cwd(), '.jarvis-cache', 'autonomy');
const LOCAL_TELEMETRY_FILE = path.join(LOCAL_ROOT, 'trade-telemetry.ndjson');
const MAX_TELEMETRY_FILE_BYTES = 16 * 1024 * 1024;
const TRIM_TARGET_BYTES = 10 * 1024 * 1024;

export interface PersistedTradeTelemetryEvent extends TradeTelemetryEvent {
  receivedAt: string;
  receivedAtMs: number;
}

export interface TradeExecutionPriors {
  sampleSize: number;
  lookbackDays: number;
  totalSellAttempts: number;
  confirmedEvents: number;
  noRouteEvents: number;
  unresolvedEvents: number;
  failedEvents: number;
  noRouteRate: number;
  unresolvedRate: number;
  failedRate: number;
  executionReliabilityPct: number;
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
    receivedAt: new Date(nowMs).toISOString(),
    receivedAtMs: nowMs,
  };
  return normalized;
}

async function maybeTrimTelemetryFile(): Promise<void> {
  try {
    if (!existsSync(LOCAL_TELEMETRY_FILE)) return;
    const st = await stat(LOCAL_TELEMETRY_FILE);
    if (!Number.isFinite(st.size) || st.size <= MAX_TELEMETRY_FILE_BYTES) return;
    const raw = await readFile(LOCAL_TELEMETRY_FILE, 'utf8');
    if (!raw) return;
    const lines = raw.trim().split('\n').filter(Boolean);
    if (lines.length <= 1) return;
    const out: string[] = [];
    let size = 0;
    for (let i = lines.length - 1; i >= 0; i--) {
      const line = lines[i];
      size += Buffer.byteLength(line, 'utf8') + 1;
      out.push(line);
      if (size >= TRIM_TARGET_BYTES) break;
    }
    out.reverse();
    await writeFile(LOCAL_TELEMETRY_FILE, `${out.join('\n')}\n`, 'utf8');
  } catch {
    // best effort
  }
}

export async function appendTradeTelemetryEvent(event: TradeTelemetryEvent): Promise<PersistedTradeTelemetryEvent> {
  const sanitized = sanitizeTelemetryEvent(event);
  await ensureLocalRoot();
  await appendFile(LOCAL_TELEMETRY_FILE, `${JSON.stringify(sanitized)}\n`, 'utf8');
  await maybeTrimTelemetryFile();
  return sanitized;
}

function parseTelemetryLines(raw: string): PersistedTradeTelemetryEvent[] {
  if (!raw) return [];
  const rows: PersistedTradeTelemetryEvent[] = [];
  for (const line of raw.split('\n')) {
    const text = line.trim();
    if (!text) continue;
    try {
      const parsed = JSON.parse(text) as PersistedTradeTelemetryEvent;
      if (!parsed || typeof parsed !== 'object') continue;
      rows.push(parsed);
    } catch {
      // skip malformed lines
    }
  }
  return rows;
}

export async function listTradeTelemetryEvents(): Promise<PersistedTradeTelemetryEvent[]> {
  try {
    if (!existsSync(LOCAL_TELEMETRY_FILE)) return [];
    const raw = await readFile(LOCAL_TELEMETRY_FILE, 'utf8');
    return parseTelemetryLines(raw);
  } catch {
    return [];
  }
}

export async function readTradeExecutionPriors(lookbackDays = 30): Promise<TradeExecutionPriors> {
  const rows = await listTradeTelemetryEvents();
  const now = Date.now();
  const windowMs = Math.max(1, Math.floor(lookbackDays)) * 24 * 60 * 60 * 1000;
  const cutoff = now - windowMs;
  const scoped = rows.filter((r) => Number(r.receivedAtMs || 0) >= cutoff);
  const attempts = scoped.filter((r) => r.eventType === 'sell_attempt' && r.includedInExecutionStats !== false);
  const totalSellAttempts = attempts.length;
  const confirmedEvents = attempts.filter((r) => r.executionOutcome === 'confirmed').length;
  const noRouteEvents = attempts.filter((r) => r.executionOutcome === 'no_route').length;
  const unresolvedEvents = attempts.filter((r) => r.executionOutcome === 'unresolved').length;
  const failedEvents = attempts.filter((r) => r.executionOutcome === 'failed').length;

  // Smooth toward conservative priors when sample size is small.
  const shrinkN = 50;
  const priorNoRoute = 0.08;
  const priorUnresolved = 0.05;
  const priorFailed = 0.03;
  const denom = totalSellAttempts + shrinkN;
  const noRouteRate = denom > 0 ? (noRouteEvents + priorNoRoute * shrinkN) / denom : priorNoRoute;
  const unresolvedRate = denom > 0 ? (unresolvedEvents + priorUnresolved * shrinkN) / denom : priorUnresolved;
  const failedRate = denom > 0 ? (failedEvents + priorFailed * shrinkN) / denom : priorFailed;
  const reliability = Math.max(0, 1 - noRouteRate - unresolvedRate - failedRate);

  return {
    sampleSize: scoped.length,
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
