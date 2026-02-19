import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from 'fs';
import { join } from 'path';
import { Storage } from '@google-cloud/storage';
import type { TradeEvidenceV2 } from '@/lib/data-plane/types';

const ROOT = join(process.cwd(), '.jarvis-cache', 'execution-evidence');
let storageSingleton: Storage | null = null;
const REMOTE_PERSIST_TIMEOUT_MS = Math.max(50, Number(process.env.DATA_PLANE_PERSIST_TIMEOUT_MS || 750) || 750);

function gcs(): Storage {
  if (!storageSingleton) storageSingleton = new Storage();
  return storageSingleton;
}

function bucketName(): string {
  return String(process.env.DATA_PLANE_AUDIT_BUCKET || process.env.AUTONOMY_AUDIT_BUCKET || '').trim();
}

function ensureRoot(): void {
  if (!existsSync(ROOT)) mkdirSync(ROOT, { recursive: true });
}

function safeTradeId(tradeId: string): string {
  return String(tradeId || '')
    .trim()
    .replace(/[^a-zA-Z0-9_-]+/g, '_')
    .slice(0, 128);
}

function dayStamp(iso: string): string {
  return String(iso || '').slice(0, 10) || new Date().toISOString().slice(0, 10);
}

function localPathFor(tradeId: string, decisionTs: string, surface: string): string {
  const day = dayStamp(decisionTs);
  const folder = join(ROOT, day, surface || 'unknown');
  if (!existsSync(folder)) mkdirSync(folder, { recursive: true });
  return join(folder, `${safeTradeId(tradeId)}.json`);
}

async function withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T | null> {
  return await Promise.race([
    promise,
    new Promise<null>((resolve) => setTimeout(() => resolve(null), timeoutMs)),
  ]);
}
async function writeGcs(evidence: TradeEvidenceV2): Promise<void> {
  const bucket = bucketName();
  if (!bucket) return;
  const day = dayStamp(evidence.decisionTs);
  const key = `trades/${day}/${evidence.surface}/${safeTradeId(evidence.tradeId)}.json`;
  await gcs().bucket(bucket).file(key).save(JSON.stringify(evidence, null, 2), {
    resumable: false,
    contentType: 'application/json',
    metadata: { cacheControl: 'no-store' },
  });
}

async function writeFirestore(evidence: TradeEvidenceV2): Promise<void> {
  const enabled = String(process.env.DATA_PLANE_FIRESTORE_ENABLED || 'false').trim().toLowerCase() === 'true';
  if (!enabled) return;
  try {
    const loader = new Function('name', 'return import(name);');
    const mod: any = await loader('@google-cloud/firestore');
    const FirestoreCtor = mod?.Firestore;
    if (!FirestoreCtor) return;
    const db = new FirestoreCtor();
    await db.collection('trade_evidence').doc(safeTradeId(evidence.tradeId)).set(evidence, { merge: true });
  } catch {
    // best effort
  }
}

export async function upsertTradeEvidence(evidence: TradeEvidenceV2): Promise<void> {
  ensureRoot();
  const path = localPathFor(evidence.tradeId, evidence.decisionTs, evidence.surface);
  writeFileSync(path, JSON.stringify(evidence, null, 2), 'utf8');
    await Promise.allSettled([
    withTimeout(writeGcs(evidence), REMOTE_PERSIST_TIMEOUT_MS),
    withTimeout(writeFirestore(evidence), REMOTE_PERSIST_TIMEOUT_MS),
  ]);
}

export function getTradeEvidence(tradeId: string): TradeEvidenceV2 | null {
  ensureRoot();
  const safeId = safeTradeId(tradeId);
  if (!safeId) return null;

  const days = existsSync(ROOT)
    ? readdirSync(ROOT, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name)
    : [];

  for (const day of days.sort().reverse()) {
    const dayDir = join(ROOT, day);
    const surfaces = readdirSync(dayDir, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name);
    for (const surface of surfaces) {
      const file = join(dayDir, surface, `${safeId}.json`);
      if (!existsSync(file)) continue;
      try {
        return JSON.parse(readFileSync(file, 'utf8')) as TradeEvidenceV2;
      } catch {
        return null;
      }
    }
  }
  return null;
}

function collectRecentEvidence(limit = 5000): TradeEvidenceV2[] {
  ensureRoot();
  const out: TradeEvidenceV2[] = [];
  if (!existsSync(ROOT)) return out;
  const days = readdirSync(ROOT, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name).sort().reverse();
  for (const day of days) {
    const dayDir = join(ROOT, day);
    const surfaces = readdirSync(dayDir, { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name);
    for (const surface of surfaces) {
      const folder = join(dayDir, surface);
      const files = readdirSync(folder).filter((f) => f.endsWith('.json'));
      for (const file of files) {
        if (out.length >= limit) return out;
        try {
          out.push(JSON.parse(readFileSync(join(folder, file), 'utf8')) as TradeEvidenceV2);
        } catch {
          // skip invalid
        }
      }
    }
  }
  return out;
}

export function summarizeTradeEvidence(args?: {
  surface?: TradeEvidenceV2['surface'];
  strategyId?: string;
}): {
  count: number;
  medianSlippageBps: number | null;
  p95SlippageBps: number | null;
  byOutcome: Record<string, number>;
} {
  let rows = collectRecentEvidence();
  if (args?.surface) rows = rows.filter((r) => r.surface === args.surface);
  if (args?.strategyId) rows = rows.filter((r) => r.strategyId === args.strategyId);

  const withSlippage = rows
    .map((r) => Number(r.slippageBps))
    .filter((v) => Number.isFinite(v))
    .sort((a, b) => a - b);

  const percentile = (arr: number[], p: number): number | null => {
    if (arr.length === 0) return null;
    const i = Math.max(0, Math.min(arr.length - 1, Math.floor((arr.length - 1) * p)));
    return Number(arr[i].toFixed(6));
  };

  const byOutcome: Record<string, number> = {};
  for (const row of rows) {
    byOutcome[row.outcome] = (byOutcome[row.outcome] || 0) + 1;
  }

  return {
    count: rows.length,
    medianSlippageBps: percentile(withSlippage, 0.5),
    p95SlippageBps: percentile(withSlippage, 0.95),
    byOutcome,
  };
}
