import { describe, expect, it } from 'vitest';
import {
  checkBudgetAndQuota,
  estimateCostUsd,
  recordUsage,
} from '@/lib/xai/budget-rate';
import type { AutonomyState } from '@/lib/autonomy/types';

function makeState(overrides: Partial<AutonomyState> = {}): AutonomyState {
  return {
    updatedAt: new Date().toISOString(),
    latestCycleId: undefined,
    latestCompletedCycleId: undefined,
    pendingBatch: undefined,
    cycles: {},
    budgetUsageByDay: {},
    ...overrides,
  };
}

describe('xai budget and quota', () => {
  it('passes when under daily and hourly caps', () => {
    const res = checkBudgetAndQuota({
      state: makeState(),
      cycleId: '2026021312',
      estimatedInputTokens: 4000,
      estimatedOutputTokens: 1200,
      nowIso: '2026-02-13T12:00:00.000Z',
    });
    expect(res.ok).toBe(true);
    expect(res.estimatedCostUsd).toBeGreaterThanOrEqual(0);
  });

  it('fails when daily budget would be exceeded', () => {
    const cost = estimateCostUsd(100000, 100000);
    const state = makeState({
      budgetUsageByDay: {
        '2026-02-13': {
          estimatedCostUsd: 9.99,
          inputTokens: 0,
          outputTokens: 0,
          cycles: 1,
        },
      },
    });
    const res = checkBudgetAndQuota({
      state,
      cycleId: '2026021313',
      estimatedInputTokens: 100000,
      estimatedOutputTokens: 100000,
      nowIso: '2026-02-13T13:00:00.000Z',
    });
    expect(cost).toBeGreaterThan(0);
    expect(res.ok).toBe(false);
    expect(res.reasonCode).toBe('AUTONOMY_NOOP_BUDGET_CAP');
  });

  it('fails when there is already an active batch for this cycle', () => {
    const state = makeState({
      pendingBatch: {
        cycleId: '2026021314',
        batchId: 'batch-1',
        model: 'grok-4-1-fast-reasoning',
        submittedAt: '2026-02-13T14:05:00.000Z',
        matrix: {} as any,
        matrixHash: 'abc',
      },
    });
    const res = checkBudgetAndQuota({
      state,
      cycleId: '2026021314',
      estimatedInputTokens: 1000,
      estimatedOutputTokens: 1000,
      nowIso: '2026-02-13T14:10:00.000Z',
    });
    expect(res.ok).toBe(false);
    expect(res.reasonCode).toBe('AUTONOMY_NOOP_ACTIVE_CYCLE_LIMIT');
  });

  it('records usage cumulatively by day', () => {
    const next = recordUsage(makeState(), {
      inputTokens: 1000,
      outputTokens: 500,
      nowIso: '2026-02-13T15:00:00.000Z',
    });
    expect(next.budgetUsageByDay['2026-02-13']).toBeDefined();
    expect(next.budgetUsageByDay['2026-02-13'].inputTokens).toBe(1000);
    expect(next.budgetUsageByDay['2026-02-13'].outputTokens).toBe(500);
  });
});

