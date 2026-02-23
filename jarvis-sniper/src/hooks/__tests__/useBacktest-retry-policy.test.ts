import { describe, expect, it } from 'vitest';
import {
  buildRelaxedBacktestRetryPayload,
  shouldRetryBacktestWithRelaxedPolicy,
  type BacktestPostPayload,
} from '@/hooks/useBacktest';

describe('useBacktest retry policy', () => {
  it('retries only on strictNoSynthetic gate failures', () => {
    expect(
      shouldRetryBacktestWithRelaxedPolicy({
        status: 422,
        message: 'strictNoSynthetic gate failed: one or more strategies had no executable real-data path',
      }),
    ).toBe(true);

    expect(
      shouldRetryBacktestWithRelaxedPolicy({
        status: 422,
        message: 'Backtest produced no results',
      }),
    ).toBe(false);

    expect(
      shouldRetryBacktestWithRelaxedPolicy({
        status: 500,
        message: 'strictNoSynthetic gate failed',
      }),
    ).toBe(false);
  });

  it('builds relaxed retry payload with synthetic candles and strict gate disabled', () => {
    const basePayload: BacktestPostPayload = {
      strategyId: 'all',
      mode: 'quick',
      dataScale: 'fast',
      includeEvidence: true,
      strictNoSynthetic: true,
      cohort: 'baseline_90d',
      lookbackHours: 2160,
      runId: 'run-123',
      manifestId: 'manifest-run-123',
    };

    const retryPayload = buildRelaxedBacktestRetryPayload(basePayload);

    expect(retryPayload.strictNoSynthetic).toBe(false);
    expect(Array.isArray(retryPayload.candles)).toBe(true);
    expect(retryPayload.candles?.length).toBeGreaterThan(100);
    expect(basePayload.candles).toBeUndefined();
    expect(basePayload.strictNoSynthetic).toBe(true);

    const first = retryPayload.candles?.[0];
    const last = retryPayload.candles?.[retryPayload.candles.length - 1];
    expect(first?.low).toBeLessThan(first?.high ?? 0);
    expect(last?.timestamp ?? 0).toBeGreaterThan(first?.timestamp ?? 0);
  });
});
