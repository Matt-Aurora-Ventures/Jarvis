import { createHash } from 'crypto';
import { mkdir, readFile, writeFile } from 'fs/promises';
import { existsSync } from 'fs';
import path from 'path';
import { Storage } from '@google-cloud/storage';
import type { AutonomyState } from './types';

const LOCAL_ROOT = path.join(process.cwd(), '.jarvis-cache', 'autonomy');
const LOCAL_STATE_FILE = path.join(LOCAL_ROOT, 'state.json');

const DEFAULT_STATE: AutonomyState = {
  updatedAt: new Date(0).toISOString(),
  latestCycleId: undefined,
  latestCompletedCycleId: undefined,
  pendingBatch: undefined,
  cycles: {},
  budgetUsageByDay: {},
};

let storageSingleton: Storage | null = null;
function gcs(): Storage {
  if (!storageSingleton) storageSingleton = new Storage();
  return storageSingleton;
}

export function auditBucketName(): string {
  return String(process.env.AUTONOMY_AUDIT_BUCKET || '').trim();
}

export function isAuditBucketConfigured(): boolean {
  return auditBucketName().length > 0;
}

export function cycleIdToPrefix(cycleId: string): string {
  const year = cycleId.slice(0, 4);
  const month = cycleId.slice(4, 6);
  const day = cycleId.slice(6, 8);
  const hour = cycleId.slice(8, 10);
  return `hourly/${year}/${month}/${day}/${hour}/${cycleId}`;
}

function sha256(text: string): string {
  return createHash('sha256').update(text).digest('hex');
}

async function ensureLocalRoot(): Promise<void> {
  if (!existsSync(LOCAL_ROOT)) {
    await mkdir(LOCAL_ROOT, { recursive: true });
  }
}

async function readLocalState(): Promise<AutonomyState> {
  try {
    if (!existsSync(LOCAL_STATE_FILE)) return { ...DEFAULT_STATE };
    const raw = await readFile(LOCAL_STATE_FILE, 'utf8');
    const parsed = JSON.parse(raw) as AutonomyState;
    return {
      ...DEFAULT_STATE,
      ...parsed,
      cycles: { ...(parsed.cycles || {}) },
      budgetUsageByDay: { ...(parsed.budgetUsageByDay || {}) },
    };
  } catch {
    return { ...DEFAULT_STATE };
  }
}

async function writeLocalState(state: AutonomyState): Promise<void> {
  await ensureLocalRoot();
  await writeFile(LOCAL_STATE_FILE, JSON.stringify(state, null, 2), 'utf8');
}

async function readJsonFromGcs<T>(key: string): Promise<T | null> {
  const bucket = auditBucketName();
  if (!bucket) return null;
  try {
    const file = gcs().bucket(bucket).file(key);
    const [exists] = await file.exists();
    if (!exists) return null;
    const [buf] = await file.download();
    return JSON.parse(buf.toString('utf8')) as T;
  } catch {
    return null;
  }
}

async function writeJsonToGcs(key: string, payload: unknown, contentType = 'application/json'): Promise<void> {
  const bucket = auditBucketName();
  if (!bucket) {
    if (process.env.NODE_ENV === 'production') {
      throw new Error('AUTONOMY_AUDIT_BUCKET is required in production');
    }
    return;
  }
  const file = gcs().bucket(bucket).file(key);
  await file.save(JSON.stringify(payload, null, 2), {
    resumable: false,
    contentType,
    metadata: {
      cacheControl: 'no-store',
    },
  });
}

async function writeTextToGcs(key: string, content: string, contentType = 'text/markdown'): Promise<void> {
  const bucket = auditBucketName();
  if (!bucket) {
    if (process.env.NODE_ENV === 'production') {
      throw new Error('AUTONOMY_AUDIT_BUCKET is required in production');
    }
    return;
  }
  const file = gcs().bucket(bucket).file(key);
  await file.save(content, {
    resumable: false,
    contentType,
    metadata: {
      cacheControl: 'no-store',
    },
  });
}

export async function loadAutonomyState(): Promise<AutonomyState> {
  if (!isAuditBucketConfigured()) {
    return readLocalState();
  }
  const gcsState = await readJsonFromGcs<AutonomyState>('state/autonomy-state.json');
  if (!gcsState) {
    return readLocalState();
  }
  return {
    ...DEFAULT_STATE,
    ...gcsState,
    cycles: { ...(gcsState.cycles || {}) },
    budgetUsageByDay: { ...(gcsState.budgetUsageByDay || {}) },
  };
}

export async function saveAutonomyState(state: AutonomyState): Promise<void> {
  const next = {
    ...DEFAULT_STATE,
    ...state,
    updatedAt: new Date().toISOString(),
  };
  await writeLocalState(next);
  if (isAuditBucketConfigured()) {
    await writeJsonToGcs('state/autonomy-state.json', next);
  }
}

export async function writeHourlyArtifact(args: {
  cycleId: string;
  fileName: 'decision-matrix.json' | 'decision-response.json' | 'decision-report.md' | 'applied-overrides.json';
  content: unknown;
  contentType?: string;
}): Promise<{ key: string; sha256: string }> {
  const prefix = cycleIdToPrefix(args.cycleId);
  const key = `${prefix}/${args.fileName}`;

  if (args.fileName.endsWith('.md')) {
    const text = String(args.content ?? '');
    await ensureLocalRoot();
    const localPath = path.join(LOCAL_ROOT, key);
    await mkdir(path.dirname(localPath), { recursive: true });
    await writeFile(localPath, text, 'utf8');
    if (isAuditBucketConfigured()) {
      await writeTextToGcs(key, text, args.contentType || 'text/markdown');
    }
    return { key, sha256: sha256(text) };
  }

  const jsonText = JSON.stringify(args.content ?? {}, null, 2);
  await ensureLocalRoot();
  const localPath = path.join(LOCAL_ROOT, key);
  await mkdir(path.dirname(localPath), { recursive: true });
  await writeFile(localPath, jsonText, 'utf8');
  if (isAuditBucketConfigured()) {
    await writeJsonToGcs(key, args.content, args.contentType || 'application/json');
  }
  return { key, sha256: sha256(jsonText) };
}

export async function readHourlyArtifact(cycleId: string, fileName: string): Promise<string | null> {
  const key = `${cycleIdToPrefix(cycleId)}/${fileName}`;
  if (isAuditBucketConfigured()) {
    try {
      const file = gcs().bucket(auditBucketName()).file(key);
      const [exists] = await file.exists();
      if (exists) {
        const [buf] = await file.download();
        return buf.toString('utf8');
      }
    } catch {
      // continue local fallback
    }
  }
  const localPath = path.join(LOCAL_ROOT, key);
  if (!existsSync(localPath)) return null;
  return readFile(localPath, 'utf8');
}

export async function readAuditBundle(cycleId: string): Promise<{
  cycleId: string;
  matrix: unknown | null;
  response: unknown | null;
  reportMarkdown: string | null;
  appliedOverrides: unknown | null;
}> {
  const [matrixRaw, responseRaw, reportMd, appliedRaw] = await Promise.all([
    readHourlyArtifact(cycleId, 'decision-matrix.json'),
    readHourlyArtifact(cycleId, 'decision-response.json'),
    readHourlyArtifact(cycleId, 'decision-report.md'),
    readHourlyArtifact(cycleId, 'applied-overrides.json'),
  ]);
  const parseJson = (text: string | null): unknown | null => {
    if (!text) return null;
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  };
  return {
    cycleId,
    matrix: parseJson(matrixRaw),
    response: parseJson(responseRaw),
    reportMarkdown: reportMd,
    appliedOverrides: parseJson(appliedRaw),
  };
}

