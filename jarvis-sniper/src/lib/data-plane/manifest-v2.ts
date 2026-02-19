import { createHash } from 'crypto';
import { existsSync, mkdirSync, writeFileSync } from 'fs';
import { join } from 'path';
import { Storage } from '@google-cloud/storage';
import type { DatasetManifestV2 } from '@/lib/data-plane/types';

const ROOT = join(process.cwd(), '.jarvis-cache', 'data-plane', 'manifests');
let storageSingleton: Storage | null = null;

function gcs(): Storage {
  if (!storageSingleton) storageSingleton = new Storage();
  return storageSingleton;
}

function sha256(text: string): string {
  return createHash('sha256').update(text).digest('hex');
}

function stableStringify(value: unknown): string {
  return JSON.stringify(value, (_k, v) => {
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      const ordered: Record<string, unknown> = {};
      for (const key of Object.keys(v as Record<string, unknown>).sort()) {
        ordered[key] = (v as Record<string, unknown>)[key];
      }
      return ordered;
    }
    return v;
  });
}

export function buildDatasetManifestV2(args: {
  family: string;
  surface: DatasetManifestV2['surface'];
  timeRange: { from: string; to: string };
  records: Array<Record<string, unknown>>;
}): DatasetManifestV2 {
  const sourceMix: Record<string, number> = {};
  for (const row of args.records) {
    const source = String((row?.provenance as any)?.source || row?.source || 'unknown').trim().toLowerCase();
    sourceMix[source] = (sourceMix[source] || 0) + 1;
  }

  const normalized = args.records
    .map((r) => stableStringify(r))
    .sort();

  const nowIso = new Date().toISOString();
  const payload = {
    family: args.family,
    surface: args.surface,
    timeRange: args.timeRange,
    records: normalized,
    sourceMix,
  };
  const digest = sha256(stableStringify(payload));

  return {
    datasetId: `ds-${digest.slice(0, 20)}`,
    family: args.family,
    surface: args.surface,
    timeRange: args.timeRange,
    schemaVersion: 'v2',
    recordCount: args.records.length,
    sha256: digest,
    sourceMix,
    createdAt: nowIso,
  };
}

function ensureDir(dir: string): void {
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
}

function auditBucketName(): string {
  return String(process.env.DATA_PLANE_AUDIT_BUCKET || process.env.AUTONOMY_AUDIT_BUCKET || '').trim();
}

async function writeManifestGcs(manifest: DatasetManifestV2): Promise<void> {
  const bucket = auditBucketName();
  if (!bucket) return;
  const key = `datasets/${manifest.family}/${manifest.datasetId}/manifest.v2.json`;
  await gcs().bucket(bucket).file(key).save(JSON.stringify(manifest, null, 2), {
    resumable: false,
    contentType: 'application/json',
    metadata: { cacheControl: 'no-store' },
  });
}

async function writeManifestFirestore(manifest: DatasetManifestV2): Promise<void> {
  const enabled = String(process.env.DATA_PLANE_FIRESTORE_ENABLED || 'false').trim().toLowerCase() === 'true';
  if (!enabled) return;
  try {
    const loader = new Function('name', 'return import(name);');
    const mod: any = await loader('@google-cloud/firestore');
    const FirestoreCtor = mod?.Firestore;
    if (!FirestoreCtor) return;
    const db = new FirestoreCtor();
    await db.collection('dataset_manifests').doc(manifest.datasetId).set(manifest, { merge: true });
  } catch {
    // best effort
  }
}

export async function persistDatasetManifestV2(manifest: DatasetManifestV2): Promise<{ path: string }> {
  const dir = join(ROOT, manifest.family, manifest.datasetId);
  ensureDir(dir);
  const path = join(dir, 'manifest.v2.json');
  writeFileSync(path, JSON.stringify(manifest, null, 2), 'utf8');

  await Promise.allSettled([
    writeManifestGcs(manifest),
    writeManifestFirestore(manifest),
  ]);

  return { path };
}
