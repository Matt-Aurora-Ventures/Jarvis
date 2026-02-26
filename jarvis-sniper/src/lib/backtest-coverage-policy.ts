export type CoverageFamily =
  | 'memecoin'
  | 'bags'
  | 'bluechip'
  | 'xstock'
  | 'prestock'
  | 'index'
  | 'xstock_index';

export type CoverageScale = 'fast' | 'thorough';

export interface CoverageThreshold {
  minDatasets: number;
  minHitRate: number;
}

export interface CoverageThresholdInput {
  family: CoverageFamily;
  dataScale: CoverageScale;
  requestedMaxTokens: number;
}

export interface CoverageHealth {
  healthy: boolean;
  hitRate: number;
  reason: 'ok' | 'below_min_datasets' | 'below_min_hit_rate';
}

function toFiniteInt(value: unknown, fallback: number): number {
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return Math.max(0, Math.floor(fallback));
  return Math.max(0, Math.floor(n));
}

function clampRate(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(1, value));
}

export function resolveCoverageThreshold(input: CoverageThresholdInput): CoverageThreshold {
  const requestedMaxTokens = Math.max(1, toFiniteInt(input.requestedMaxTokens, 1));
  const scale = input.dataScale === 'fast' ? 'fast' : 'thorough';
  const baseMinDatasets = scale === 'fast'
    ? Math.max(2, Math.floor(requestedMaxTokens * 0.25))
    : Math.max(6, Math.floor(requestedMaxTokens * 0.12));

  let minDatasets = baseMinDatasets;
  let minHitRate = scale === 'fast' ? 0.2 : 0.12;

  if (input.family === 'bags') {
    minDatasets = Math.max(baseMinDatasets, scale === 'fast' ? 5 : 15);
    minHitRate = scale === 'fast' ? 0.22 : 0.14;
  } else if (input.family === 'bluechip') {
    minDatasets = Math.max(baseMinDatasets, scale === 'fast' ? 3 : 8);
    minHitRate = scale === 'fast' ? 0.35 : 0.2;
  } else if (input.family === 'memecoin') {
    minDatasets = Math.max(baseMinDatasets, scale === 'fast' ? 6 : 20);
    minHitRate = scale === 'fast' ? 0.18 : 0.1;
  }

  return {
    minDatasets,
    minHitRate: clampRate(minHitRate),
  };
}

export function computeCoverageHealth(
  stats: { attempted: number; succeeded: number },
  threshold: CoverageThreshold,
): CoverageHealth {
  const attempted = Math.max(0, toFiniteInt(stats.attempted, 0));
  const succeeded = Math.max(0, toFiniteInt(stats.succeeded, 0));
  const hitRate = attempted > 0 ? clampRate(succeeded / attempted) : 0;

  if (succeeded < Math.max(1, toFiniteInt(threshold.minDatasets, 1))) {
    return { healthy: false, hitRate, reason: 'below_min_datasets' };
  }

  const minHitRate = clampRate(Number(threshold.minHitRate));
  if (hitRate < minHitRate) {
    return { healthy: false, hitRate, reason: 'below_min_hit_rate' };
  }

  return { healthy: true, hitRate, reason: 'ok' };
}
