import { describe, expect, it } from 'vitest';
import { getSurfaceAvailabilityMap, resolveSurfaceAvailability } from '@/lib/surface-availability';

describe('surface availability contract', () => {
  it('disables surfaces when explicit public flags are false', () => {
    const env = {
      NODE_ENV: 'production',
      NEXT_PUBLIC_ENABLE_INVESTMENTS: 'false',
      NEXT_PUBLIC_ENABLE_PERPS: 'false',
      NEXT_PUBLIC_ENABLE_TRADFI: 'false',
    };
    const map = getSurfaceAvailabilityMap(env);

    expect(map.investments.visible).toBe(true);
    expect(map.investments.enabled).toBe(false);
    expect(map.investments.reason).toContain('staged rollout');

    expect(map.perps.visible).toBe(true);
    expect(map.perps.enabled).toBe(false);
    expect(map.perps.reason).toContain('staged rollout');

    expect(map.clawbot.visible).toBe(true);
    expect(map.clawbot.enabled).toBe(false);
    expect(map.clawbot.reason).toContain('staged rollout');

    expect(map.tradfi.visible).toBe(true);
    expect(map.tradfi.enabled).toBe(false);
    expect(map.tradfi.reason).toContain('staged rollout');
  });

  it('keeps clawbot demo-safe in all runtimes', () => {
    const prod = resolveSurfaceAvailability('clawbot', {
      NODE_ENV: 'production',
      NEXT_PUBLIC_ENABLE_CLAWBOT: 'true',
    });
    const dev = resolveSurfaceAvailability('clawbot', {
      NODE_ENV: 'development',
    });

    expect(prod.enabled).toBe(false);
    expect(prod.reason).toContain('staged rollout');
    expect(dev.enabled).toBe(false);
    expect(dev.reason).toContain('staged rollout');
  });

  it('enables tradfi outside production when no explicit flag is set', () => {
    const status = resolveSurfaceAvailability('tradfi', {
      NODE_ENV: 'development',
    });

    expect(status.visible).toBe(true);
    expect(status.enabled).toBe(true);
    expect(status.reason).toBeNull();
  });
});

