import { describe, expect, it } from 'vitest';
import {
  computeCoverageHealth,
  resolveCoverageThreshold,
} from '@/lib/backtest-coverage-policy';

describe('backtest coverage policy', () => {
  it('enforces stronger minimum dataset counts for bags and bluechip', () => {
    const bagsFast = resolveCoverageThreshold({
      family: 'bags',
      dataScale: 'fast',
      requestedMaxTokens: 10,
    });
    const bluechipFast = resolveCoverageThreshold({
      family: 'bluechip',
      dataScale: 'fast',
      requestedMaxTokens: 5,
    });

    expect(bagsFast.minDatasets).toBeGreaterThanOrEqual(5);
    expect(bluechipFast.minDatasets).toBeGreaterThanOrEqual(3);
  });

  it('raises minimum datasets for thorough runs', () => {
    const bagsThorough = resolveCoverageThreshold({
      family: 'bags',
      dataScale: 'thorough',
      requestedMaxTokens: 200,
    });
    const bluechipThorough = resolveCoverageThreshold({
      family: 'bluechip',
      dataScale: 'thorough',
      requestedMaxTokens: 120,
    });

    expect(bagsThorough.minDatasets).toBeGreaterThanOrEqual(15);
    expect(bluechipThorough.minDatasets).toBeGreaterThanOrEqual(8);
  });

  it('marks near-empty universes as unhealthy', () => {
    const policy = resolveCoverageThreshold({
      family: 'bags',
      dataScale: 'fast',
      requestedMaxTokens: 10,
    });
    const health = computeCoverageHealth(
      { attempted: 20, succeeded: 2 },
      policy,
    );

    expect(health.healthy).toBe(false);
    expect(health.reason).toBe('below_min_datasets');
  });

  it('marks healthy when hit-rate and absolute minimum are both met', () => {
    const policy = resolveCoverageThreshold({
      family: 'bluechip',
      dataScale: 'fast',
      requestedMaxTokens: 8,
    });
    const health = computeCoverageHealth(
      { attempted: 12, succeeded: 6 },
      policy,
    );

    expect(health.healthy).toBe(true);
    expect(health.hitRate).toBeGreaterThanOrEqual(policy.minHitRate);
  });
});
