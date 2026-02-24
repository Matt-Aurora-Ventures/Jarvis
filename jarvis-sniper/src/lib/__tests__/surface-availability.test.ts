import { describe, expect, it } from 'vitest';
import { resolveSurfaceAvailability } from '@/lib/surface-availability';

describe('resolveSurfaceAvailability', () => {
  it('defaults to enabled outside production when flags are unset', () => {
    const availability = resolveSurfaceAvailability({
      env: { NODE_ENV: 'development' },
    });

    expect(availability.investments.state).toBe('enabled');
    expect(availability.perps.state).toBe('enabled');
    expect(availability.tradfi.state).toBe('enabled');
  });

  it('keeps panel visible-disabled when explicitly disabled by env flag', () => {
    const availability = resolveSurfaceAvailability({
      env: {
        NODE_ENV: 'production',
        NEXT_PUBLIC_ENABLE_INVESTMENTS: 'false',
      },
    });

    expect(availability.investments.state).toBe('visible-disabled');
    expect(availability.investments.reason).toContain('NEXT_PUBLIC_ENABLE_INVESTMENTS');
  });

  it('falls back to visible-disabled when runtime health marks a surface unavailable', () => {
    const availability = resolveSurfaceAvailability({
      env: {
        NODE_ENV: 'production',
        NEXT_PUBLIC_ENABLE_PERPS: 'true',
      },
      health: {
        perps: false,
      },
    });

    expect(availability.perps.state).toBe('visible-disabled');
    expect(availability.perps.reason?.toLowerCase()).toContain('runtime health');
  });
});
