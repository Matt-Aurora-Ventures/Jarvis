import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'fs';
import { join } from 'path';
import { Storage } from '@google-cloud/storage';
import type { SourceHealthSnapshot } from '@/lib/data-plane/types';

const ROOT = join(process.cwd(), '.jarvis-cache', 'data-plane');
const SOURCE_HEALTH_FILE = join(ROOT, 'source-health.json');
const sourceHealth = new Map<string, SourceHealthSnapshot>();
let storageSingleton: Storage | null = null;

function gcs(): Storage {
  if (!storageSingleton) storageSingleton = new Storage();
  return storageSingleton;
}

function auditBucketName(): string {
  return String(process.env.DATA_PLANE_AUDIT_BUCKET || process.env.AUTONOMY_AUDIT_BUCKET || '').trim();
}

function ensureRoot(): void {
  if (!existsSync(ROOT)) mkdirSync(ROOT, { recursive: true });
}

function loadLocalCache(): void {
  try {
    if (!existsSync(SOURCE_HEALTH_FILE)) return;
    const parsed = JSON.parse(readFileSync(SOURCE_HEALTH_FILE, 'utf8')) as SourceHealthSnapshot[];
    for (const row of Array.isArray(parsed) ? parsed : []) {
      if (!row?.source) continue;
      sourceHealth.set(String(row.source), row);
    }
  } catch {
    // best effort
  }
}

let loaded = false;
function ensureLoaded(): void {
  if (loaded) return;
  loaded = true;
  loadLocalCache();
}

function writeLocal(): void {
  try {
    ensureRoot();
    writeFileSync(
      SOURCE_HEALTH_FILE,
      JSON.stringify([...sourceHealth.values()].sort((a, b) => String(a.source).localeCompare(String(b.source))), null, 2),
      'utf8',
    );
  } catch {
    // best effort
  }
}

async function writeGcs(snapshot: SourceHealthSnapshot): Promise<void> {
  const bucket = auditBucketName();
  if (!bucket) return;
  try {
    const key = `source-health/${String(snapshot.source)}.json`;
    await gcs().bucket(bucket).file(key).save(JSON.stringify(snapshot, null, 2), {
      resumable: false,
      contentType: 'application/json',
      metadata: { cacheControl: 'no-store' },
    });
  } catch {
    // best effort
  }
}

async function writeFirestore(snapshot: SourceHealthSnapshot): Promise<void> {
  const enabled = String(process.env.DATA_PLANE_FIRESTORE_ENABLED || 'false').trim().toLowerCase() === 'true';
  if (!enabled) return;
  try {
    const loader = new Function('name', 'return import(name);');
    const mod: any = await loader('@google-cloud/firestore');
    const FirestoreCtor = mod?.Firestore;
    if (!FirestoreCtor) return;
    const db = new FirestoreCtor();
    const docId = String(snapshot.source).replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 128) || 'unknown';
    await db.collection('source_health').doc(docId).set(snapshot, { merge: true });
  } catch {
    // best effort
  }
}

export async function recordSourceHealth(snapshot: SourceHealthSnapshot): Promise<void> {
  ensureLoaded();
  sourceHealth.set(String(snapshot.source), snapshot);
  writeLocal();
  await Promise.allSettled([writeGcs(snapshot), writeFirestore(snapshot)]);
}

export function getSourceHealthSnapshots(): SourceHealthSnapshot[] {
  ensureLoaded();
  return [...sourceHealth.values()].sort((a, b) => String(a.source).localeCompare(String(b.source)));
}

export function getSourceHealthSummary(): {
  updatedAt: string;
  totalSources: number;
  healthySources: number;
  degradedSources: number;
  snapshots: SourceHealthSnapshot[];
} {
  const snapshots = getSourceHealthSnapshots();
  const healthySources = snapshots.filter((s) => s.reliabilityScore >= 0.8 && s.ok).length;
  const degradedSources = snapshots.length - healthySources;
  return {
    updatedAt: new Date().toISOString(),
    totalSources: snapshots.length,
    healthySources,
    degradedSources,
    snapshots,
  };
}
