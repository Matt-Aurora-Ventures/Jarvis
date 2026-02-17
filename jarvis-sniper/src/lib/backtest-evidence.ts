import { ServerCache } from './server-cache';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, unlinkSync, writeFileSync } from 'fs';
import { join } from 'path';

/**
 * Backtest Evidence Bundle
 *
 * Goal: provide trade-level, timestamped artifacts derived ONLY from real upstream data.
 * No synthetic candles are generated anywhere in this pipeline.
 *
 * Evidence is cached server-side for a short TTL so the UI can download CSV/manifest
 * without re-running compute-heavy backtests.
 */

export interface BacktestEvidenceDataset {
  tokenSymbol: string;
  mintAddress: string;
  pairAddress: string;
  candles: number;
  /** SHA-256 hash of the normalized candle list used for this run (hex). */
  dataHash?: string;
  dataStartTime: number;
  dataEndTime: number;
  fetchedAt: number;
  source: string;
  geckoPoolUrl?: string;
}

export interface BacktestEvidenceTradeRow {
  strategyId: string;
  mode: string;
  tokenSymbol: string;
  resultTokenSymbol: string;
  mintAddress: string;
  pairAddress: string;
  source: string;

  entryTime: number;
  exitTime: number;
  entryPrice: number;
  exitPrice: number;
  pnlPct: number;
  pnlNet: number;
  exitReason: string;
  holdCandles: number;
  highWaterMark: number;
  lowWaterMark: number;
  maxDrawdownPct: number;

  stopLossPct: number;
  takeProfitPct: number;
  trailingStopPct: number;
  maxHoldCandles: number;
  slippagePct: number;
  feePct: number;
  minScore: number;
  minLiquidityUsd: number;
  executionReliabilityPct?: number;
  noRouteRate?: number;
  unresolvedRate?: number;
  failedRate?: number;
  executionAdjustedPnlNet?: number;
  degraded?: boolean;
  degradedReasons?: string;
}

export interface BacktestEvidenceBundle {
  runId: string;
  generatedAt: string;
  request: Record<string, unknown>;
  meta: Record<string, unknown>;
  datasets: BacktestEvidenceDataset[];
  trades: BacktestEvidenceTradeRow[];
  reportMd: string | null;
  resultsSummary: unknown[];
}

const CACHE_TTL_MS = 30 * 60 * 1000; // 30 minutes

export const backtestEvidenceCache = new ServerCache<BacktestEvidenceBundle>();

const EVIDENCE_DIR = join(process.cwd(), '.jarvis-cache', 'backtest-evidence');
let lastDiskCleanupAt = 0;

function ensureEvidenceDir(): void {
  try {
    if (!existsSync(EVIDENCE_DIR)) mkdirSync(EVIDENCE_DIR, { recursive: true });
  } catch {
    // ignore (read-only fs, edge runtime, etc.)
  }
}

function evidencePath(runId: string): string {
  return join(EVIDENCE_DIR, `${runId}.json`);
}

function maybeCleanupDiskCache(now: number): void {
  // Best-effort; don't do filesystem scans too frequently.
  if (now - lastDiskCleanupAt < 60_000) return;
  lastDiskCleanupAt = now;

  try {
    if (!existsSync(EVIDENCE_DIR)) return;
    const files = readdirSync(EVIDENCE_DIR);
    for (const f of files) {
      if (!f.endsWith('.json')) continue;
      const full = join(EVIDENCE_DIR, f);
      try {
        const st = statSync(full);
        // If older than TTL + 5 minutes buffer, delete.
        if (now - st.mtimeMs > CACHE_TTL_MS + 5 * 60_000) {
          unlinkSync(full);
        }
      } catch {
        // ignore
      }
    }
  } catch {
    // ignore
  }
}

export function putBacktestEvidence(bundle: BacktestEvidenceBundle): void {
  backtestEvidenceCache.set(bundle.runId, bundle, CACHE_TTL_MS);

  // Persist to disk so evidence downloads work even if route handlers don't share memory.
  // (Common in serverless/dev worker setups.)
  try {
    const now = Date.now();
    ensureEvidenceDir();
    maybeCleanupDiskCache(now);
    writeFileSync(
      evidencePath(bundle.runId),
      JSON.stringify(
        {
          expiresAt: now + CACHE_TTL_MS,
          bundle,
        },
      ),
      'utf8',
    );
  } catch {
    // ignore (best-effort)
  }
}

export function getBacktestEvidence(runId: string): BacktestEvidenceBundle | null {
  const cached = backtestEvidenceCache.get(runId);
  if (cached) return cached;

  // Disk fallback (best-effort).
  try {
    const p = evidencePath(runId);
    if (!existsSync(p)) return null;

    const raw = JSON.parse(readFileSync(p, 'utf8'));
    const expiresAt = Number(raw?.expiresAt ?? 0);
    const bundle = raw?.bundle as BacktestEvidenceBundle | undefined;
    if (!bundle || !expiresAt || !Number.isFinite(expiresAt)) return null;

    const now = Date.now();
    if (now >= expiresAt) {
      try { unlinkSync(p); } catch {}
      return null;
    }

    backtestEvidenceCache.set(runId, bundle, Math.max(1, expiresAt - now));
    return bundle;
  } catch {
    return null;
  }
}

function csvEscape(value: unknown): string {
  if (value == null) return '';
  const s = String(value);
  if (/[",\r\n]/.test(s)) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function evidenceTradesToCsv(bundle: BacktestEvidenceBundle): string {
  const header: (keyof BacktestEvidenceTradeRow)[] = [
    'strategyId',
    'mode',
    'tokenSymbol',
    'resultTokenSymbol',
    'mintAddress',
    'pairAddress',
    'source',
    'entryTime',
    'exitTime',
    'entryPrice',
    'exitPrice',
    'pnlPct',
    'pnlNet',
    'exitReason',
    'holdCandles',
    'highWaterMark',
    'lowWaterMark',
    'maxDrawdownPct',
    'stopLossPct',
    'takeProfitPct',
    'trailingStopPct',
    'maxHoldCandles',
    'slippagePct',
    'feePct',
    'minScore',
    'minLiquidityUsd',
    'executionReliabilityPct',
    'noRouteRate',
    'unresolvedRate',
    'failedRate',
    'executionAdjustedPnlNet',
    'degraded',
    'degradedReasons',
  ];

  const lines: string[] = [];
  lines.push(header.join(','));

  for (const row of bundle.trades) {
    lines.push(header.map((k) => csvEscape((row as any)[k])).join(','));
  }

  // CSV spec: CRLF is safest across Excel/Windows.
  return lines.join('\r\n');
}
