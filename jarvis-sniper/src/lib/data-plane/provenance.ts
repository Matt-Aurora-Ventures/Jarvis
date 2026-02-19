import { createHash } from 'crypto';
import type { DataPlaneSource, DataPointProvenance } from '@/lib/data-plane/types';

function sha256(value: string): string {
  return createHash('sha256').update(value).digest('hex');
}

export function buildDataPointProvenance(args: {
  source: DataPlaneSource | string;
  fetchedAt?: string;
  latencyMs?: number | null;
  httpStatus?: number | null;
  reliabilityScore: number;
  raw: unknown;
}): DataPointProvenance {
  const fetchedAt = args.fetchedAt || new Date().toISOString();
  const rawHash = sha256(JSON.stringify(args.raw ?? null));
  return {
    source: args.source,
    fetchedAt,
    latencyMs: Number.isFinite(Number(args.latencyMs)) ? Number(args.latencyMs) : null,
    httpStatus: Number.isFinite(Number(args.httpStatus)) ? Number(args.httpStatus) : null,
    schemaVersion: 'v2',
    reliabilityScore: Number.isFinite(args.reliabilityScore) ? Number(args.reliabilityScore) : 0,
    rawHash,
  };
}
