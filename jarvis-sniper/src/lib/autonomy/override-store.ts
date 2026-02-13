import path from 'path';
import { existsSync } from 'fs';
import { mkdir, readFile, writeFile } from 'fs/promises';
import { Storage } from '@google-cloud/storage';
import type { StrategyOverrideSnapshot } from './types';
import { emptyOverrideSnapshot } from './override-policy';

const LOCAL_ROOT = path.join(process.cwd(), '.jarvis-cache', 'autonomy');
const LOCAL_OVERRIDE_FILE = path.join(LOCAL_ROOT, 'strategy-overrides.json');
const GCS_OVERRIDE_KEY = 'state/strategy-overrides.json';

let storageSingleton: Storage | null = null;
function gcs(): Storage {
  if (!storageSingleton) storageSingleton = new Storage();
  return storageSingleton;
}

function bucketName(): string {
  return String(process.env.AUTONOMY_AUDIT_BUCKET || '').trim();
}

async function ensureLocalRoot(): Promise<void> {
  if (!existsSync(LOCAL_ROOT)) {
    await mkdir(LOCAL_ROOT, { recursive: true });
  }
}

async function readLocal(): Promise<StrategyOverrideSnapshot> {
  try {
    if (!existsSync(LOCAL_OVERRIDE_FILE)) return emptyOverrideSnapshot();
    const raw = await readFile(LOCAL_OVERRIDE_FILE, 'utf8');
    const parsed = JSON.parse(raw) as StrategyOverrideSnapshot;
    if (!parsed || typeof parsed !== 'object') return emptyOverrideSnapshot();
    return parsed;
  } catch {
    return emptyOverrideSnapshot();
  }
}

async function writeLocal(snapshot: StrategyOverrideSnapshot): Promise<void> {
  await ensureLocalRoot();
  await writeFile(LOCAL_OVERRIDE_FILE, JSON.stringify(snapshot, null, 2), 'utf8');
}

async function readGcs(): Promise<StrategyOverrideSnapshot | null> {
  const bucket = bucketName();
  if (!bucket) return null;
  try {
    const file = gcs().bucket(bucket).file(GCS_OVERRIDE_KEY);
    const [exists] = await file.exists();
    if (!exists) return null;
    const [buf] = await file.download();
    return JSON.parse(buf.toString('utf8')) as StrategyOverrideSnapshot;
  } catch {
    return null;
  }
}

async function writeGcs(snapshot: StrategyOverrideSnapshot): Promise<void> {
  const bucket = bucketName();
  if (!bucket) {
    if (process.env.NODE_ENV === 'production') {
      throw new Error('AUTONOMY_AUDIT_BUCKET is required in production');
    }
    return;
  }
  await gcs().bucket(bucket).file(GCS_OVERRIDE_KEY).save(JSON.stringify(snapshot, null, 2), {
    resumable: false,
    contentType: 'application/json',
    metadata: { cacheControl: 'no-store' },
  });
}

export async function getStrategyOverrideSnapshot(): Promise<StrategyOverrideSnapshot> {
  const fromGcs = await readGcs();
  if (fromGcs) return fromGcs;
  return readLocal();
}

export async function saveStrategyOverrideSnapshot(snapshot: StrategyOverrideSnapshot): Promise<void> {
  await writeLocal(snapshot);
  if (bucketName()) {
    await writeGcs(snapshot);
  }
}

