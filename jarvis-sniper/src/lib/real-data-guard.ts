export type PromotableDataSource =
  | 'geckoterminal'
  | 'birdeye'
  | 'helius'
  | 'jupiter'
  | 'dexscreener'
  | 'mixed';

const PROMOTABLE_SOURCES = new Set<string>([
  'geckoterminal',
  'birdeye',
  'helius',
  'jupiter',
  'dexscreener',
  'mixed',
]);

const SYNTHETIC_OR_NON_PROMOTABLE = new Set<string>([
  'client',
  'synthetic',
  'random',
  'simulated',
  'mock',
  'paper',
  'dexscreener_synthetic',
  'synthetic_randomized',
]);

export function normalizeDataSource(value: unknown): string {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/\s+/g, '_');
}

export function isSyntheticOrNonPromotableSource(value: unknown): boolean {
  const normalized = normalizeDataSource(value);
  if (!normalized) return true;
  if (SYNTHETIC_OR_NON_PROMOTABLE.has(normalized)) return true;
  if (normalized.includes('synthetic')) return true;
  if (normalized.includes('random')) return true;
  if (normalized.includes('simulated')) return true;
  return false;
}

export function isPromotableDataSource(value: unknown): value is PromotableDataSource {
  const normalized = normalizeDataSource(value);
  if (!normalized) return false;
  if (isSyntheticOrNonPromotableSource(normalized)) return false;
  return PROMOTABLE_SOURCES.has(normalized);
}

export function assertPromotableDataSource(value: unknown, context: string): void {
  if (!isPromotableDataSource(value)) {
    throw new Error(
      `Real-data guard failed in ${context}: non-promotable source "${normalizeDataSource(value)}"`,
    );
  }
}