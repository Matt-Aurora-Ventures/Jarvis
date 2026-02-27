import { describe, expect, it } from 'vitest';
import { isInvestmentsEnabled, isPerpsEnabled } from '@/lib/investments-perps-flags';

describe('investments/perps feature flags', () => {
  it('defaults to enabled when unset in all environments', () => {
    expect(isInvestmentsEnabled({ NODE_ENV: 'development' })).toBe(true);
    expect(isPerpsEnabled({ NODE_ENV: 'test' })).toBe(true);
    expect(isInvestmentsEnabled({ NODE_ENV: 'production' })).toBe(true);
    expect(isPerpsEnabled({ NODE_ENV: 'production' })).toBe(true);
  });

  it('respects explicit flag values', () => {
    expect(isInvestmentsEnabled({ NODE_ENV: 'production', NEXT_PUBLIC_ENABLE_INVESTMENTS: 'true' })).toBe(true);
    expect(isPerpsEnabled({ NODE_ENV: 'development', NEXT_PUBLIC_ENABLE_PERPS: 'false' })).toBe(false);
  });
});
