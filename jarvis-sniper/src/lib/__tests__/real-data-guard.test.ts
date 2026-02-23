import { describe, expect, it } from 'vitest';
import {
  assertPromotableDataSource,
  isPromotableDataSource,
  isSyntheticOrNonPromotableSource,
  normalizeDataSource,
} from '@/lib/real-data-guard';

describe('real-data-guard', () => {
  it('normalizes and recognizes promotable sources', () => {
    expect(normalizeDataSource(' GeckoTerminal ')).toBe('geckoterminal');
    expect(isPromotableDataSource('geckoterminal')).toBe(true);
    expect(isPromotableDataSource('birdeye')).toBe(true);
    expect(isPromotableDataSource('mixed')).toBe(true);
  });

  it('detects synthetic/non-promotable sources', () => {
    expect(isSyntheticOrNonPromotableSource('client')).toBe(true);
    expect(isSyntheticOrNonPromotableSource('dexscreener_synthetic')).toBe(true);
    expect(isSyntheticOrNonPromotableSource('randomized')).toBe(true);
    expect(isPromotableDataSource('client')).toBe(false);
    expect(isPromotableDataSource('synthetic_randomized')).toBe(false);
    expect(isPromotableDataSource('')).toBe(false);
  });

  it('throws when promotable assertion fails', () => {
    expect(() => assertPromotableDataSource('client', 'unit-test')).toThrow(/Real-data guard failed/);
    expect(() => assertPromotableDataSource('birdeye', 'unit-test')).not.toThrow();
  });
});
