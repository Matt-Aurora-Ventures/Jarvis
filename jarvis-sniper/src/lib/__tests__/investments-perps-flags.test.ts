import { describe, expect, it } from 'vitest';
import { isInvestmentsEnabled, isPerpsEnabled } from '@/lib/investments-perps-flags';

describe('investments/perps feature flags', () => {
  it('defaults to enabled outside production when unset', () => {
    expect(isInvestmentsEnabled({ NODE_ENV: 'development' })).toBe(true);
    expect(isPerpsEnabled({ NODE_ENV: 'test' })).toBe(true);
  });

  it('defaults to disabled in production when unset', () => {
    expect(isInvestmentsEnabled({ NODE_ENV: 'production' })).toBe(false);
    expect(isPerpsEnabled({ NODE_ENV: 'production' })).toBe(false);
  });

  it('respects explicit flag values', () => {
    expect(isInvestmentsEnabled({ NODE_ENV: 'production', NEXT_PUBLIC_ENABLE_INVESTMENTS: 'true' })).toBe(true);
    expect(isPerpsEnabled({ NODE_ENV: 'development', NEXT_PUBLIC_ENABLE_PERPS: 'false' })).toBe(false);
  });
});
