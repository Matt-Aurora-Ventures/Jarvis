import { describe, expect, it } from 'vitest';
import { isInvestmentsEnabled, isPerpsEnabled } from '@/lib/investments-perps-flags';

describe('investments/perps feature flags', () => {
  it('defaults to disabled when unset in all environments', () => {
    expect(isInvestmentsEnabled({ NODE_ENV: 'development' })).toBe(false);
    expect(isPerpsEnabled({ NODE_ENV: 'test' })).toBe(false);
    expect(isInvestmentsEnabled({ NODE_ENV: 'production' })).toBe(false);
    expect(isPerpsEnabled({ NODE_ENV: 'production' })).toBe(false);
  });

  it('respects explicit flag values', () => {
    expect(isInvestmentsEnabled({ NODE_ENV: 'production', NEXT_PUBLIC_ENABLE_INVESTMENTS: 'true' })).toBe(true);
    expect(isPerpsEnabled({ NODE_ENV: 'development', NEXT_PUBLIC_ENABLE_PERPS: 'false' })).toBe(false);
  });
});
