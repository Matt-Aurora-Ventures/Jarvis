import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockLoadAutonomyState = vi.fn();
const mockSaveAutonomyState = vi.fn();
const mockWriteHourlyArtifact = vi.fn();

vi.mock('@/lib/autonomy/audit-store', () => ({
  loadAutonomyState: mockLoadAutonomyState,
  saveAutonomyState: mockSaveAutonomyState,
  writeHourlyArtifact: mockWriteHourlyArtifact,
  readAuditBundle: vi.fn(),
}));

const mockGetBatch = vi.fn();
const mockGetBatchResults = vi.fn();

vi.mock('@/lib/xai/client', () => ({
  getBatch: mockGetBatch,
  getBatchResults: mockGetBatchResults,
  createBatch: vi.fn(),
  addBatchRequests: vi.fn(),
  listModels: vi.fn(),
  XaiApiError: class XaiApiError extends Error {},
}));

const mockGetStrategyOverrideSnapshot = vi.fn();
const mockSaveStrategyOverrideSnapshot = vi.fn();

vi.mock('@/lib/autonomy/override-store', () => ({
  getStrategyOverrideSnapshot: mockGetStrategyOverrideSnapshot,
  saveStrategyOverrideSnapshot: mockSaveStrategyOverrideSnapshot,
}));

function cycleIdFrom(date = new Date()): string {
  const y = date.getUTCFullYear().toString().padStart(4, '0');
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const d = String(date.getUTCDate()).padStart(2, '0');
  const h = String(date.getUTCHours()).padStart(2, '0');
  return `${y}${m}${d}${h}`;
}

function previousCycleId(current: string): string {
  const y = Number(current.slice(0, 4));
  const m = Number(current.slice(4, 6)) - 1;
  const d = Number(current.slice(6, 8));
  const h = Number(current.slice(8, 10));
  const prev = new Date(Date.UTC(y, m, d, h));
  prev.setUTCHours(prev.getUTCHours() - 1);
  return cycleIdFrom(prev);
}

function makeBatchResults(args: { cycleId: string; decision: unknown; critique: unknown }) {
  const row = (batchRequestId: string, payload: unknown) => ({
    batch_request_id: batchRequestId,
    response: {
      completion_response: {
        choices: [{ message: { content: JSON.stringify(payload) } }],
        usage: { prompt_tokens: 10, completion_tokens: 20 },
      },
    },
  });

  return [
    row(`${args.cycleId}:decision`, args.decision),
    row(`${args.cycleId}:self_critique`, args.critique),
  ];
}

function makePendingState(currentCycle: string, pendingCycle: string) {
  return {
    updatedAt: new Date(0).toISOString(),
    latestCycleId: currentCycle,
    latestCompletedCycleId: undefined,
    pendingBatch: {
      cycleId: pendingCycle,
      batchId: 'batch-1',
      requestIds: [`${pendingCycle}:decision`, `${pendingCycle}:self_critique`],
      model: 'grok-4-1-fast-reasoning',
      submittedAt: new Date().toISOString(),
      matrix: {
        cycleId: pendingCycle,
        generatedAt: new Date().toISOString(),
        wrGatePolicy: {
          primaryPct: 70,
          fallbackPct: 50,
          minTrades: 1000,
          method: 'wilson95_lower',
          scope: 'memecoin_bags',
        },
        strategyRows: [],
        metrics: {
          liquidityRegime: { sampleSize: 0, avgLiquidityUsd: 0, medianLiquidityUsd: 0, avgMomentum1h: 0, avgVolLiqRatio: 0 },
          thompsonBeliefs: { availability: 'unavailable_server_scope', reason: 'n/a', rows: [] },
          reliability: { confirmed: 0, unresolved: 0, failed: 0 },
          realized: { totalPnlSol: 0, winCount: 0, lossCount: 0, tradeCount: 0, drawdownPct: 0 },
        },
        tokenBudget: { maxInputTokens: 1, maxOutputTokens: 1, estimatedInputTokens: 1 },
      },
      matrixHash: 'mhash',
    },
    cycles: {
      [currentCycle]: {
        cycleId: currentCycle,
        status: 'noop',
        reasonCode: 'AUTONOMY_NOOP_DISABLED',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        matrixHash: 'x',
      },
      [pendingCycle]: {
        cycleId: pendingCycle,
        status: 'pending',
        reasonCode: 'AUTONOMY_PENDING_BATCH',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        batchId: 'batch-1',
        matrixHash: 'mhash',
      },
    },
    budgetUsageByDay: {},
  };
}

describe('autonomy apply gate', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    process.env.AUTONOMY_ENABLED = 'true';
    process.env.XAI_BATCH_ENABLED = 'true';
    process.env.XAI_API_KEY = 'test-key';
    process.env.AUTONOMY_APPLY_OVERRIDES = 'false';

    mockWriteHourlyArtifact.mockResolvedValue({ key: 'k', sha256: 'h' });
    mockGetStrategyOverrideSnapshot.mockResolvedValue(null);
    mockGetBatch.mockResolvedValue({
      batch_id: 'batch-1',
      state: {
        num_requests: 2,
        num_pending: 0,
        num_success: 2,
        num_error: 0,
        num_cancelled: 0,
      },
    });
  });

  it('does not apply overrides when AUTONOMY_APPLY_OVERRIDES=false', async () => {
    const currentCycle = cycleIdFrom(new Date());
    const pendingCycle = previousCycleId(currentCycle);

    const decision = {
      decision: 'adjust',
      reason: 'Test adjustment',
      confidence: 0.6,
      targets: [
        {
          strategyId: 'pump_fresh_tight',
          patch: { minScore: 55 },
          reason: 'Reduce false positives',
          confidence: 0.6,
          evidence: ['winRateCI95'],
        },
      ],
      evidence: ['session_pnl'],
      constraintsCheck: { pass: true, reasons: ['Within delta caps'] },
      alternativesConsidered: [{ option: 'hold', rejectedBecause: 'Needs adjustment' }],
    };

    const critique = {
      decision: 'hold',
      reason: 'Critique ok',
      confidence: 0.2,
      targets: [],
      evidence: [],
      constraintsCheck: { pass: true, reasons: ['No issues'] },
      alternativesConsidered: [{ option: 'adjust', rejectedBecause: 'Not needed' }],
    };

    mockGetBatchResults.mockResolvedValue({
      results: makeBatchResults({ cycleId: pendingCycle, decision, critique }),
    });
    mockLoadAutonomyState.mockResolvedValue(makePendingState(currentCycle, pendingCycle));

    const mod = await import('@/lib/autonomy/hourly-cycle');
    await mod.runHourlyAutonomyCycle();

    expect(mockSaveStrategyOverrideSnapshot).not.toHaveBeenCalled();
    expect(mockSaveAutonomyState).toHaveBeenCalledTimes(1);
    const savedState = mockSaveAutonomyState.mock.calls[0][0];
    expect(savedState.cycles[pendingCycle].reasonCode).toBe('AUTONOMY_NOOP_APPLY_DISABLED');
  });

  it('applies overrides when AUTONOMY_APPLY_OVERRIDES=true', async () => {
    process.env.AUTONOMY_APPLY_OVERRIDES = 'true';
    const currentCycle = cycleIdFrom(new Date());
    const pendingCycle = previousCycleId(currentCycle);

    const decision = {
      decision: 'adjust',
      reason: 'Test adjustment',
      confidence: 0.6,
      targets: [
        {
          strategyId: 'pump_fresh_tight',
          patch: { minScore: 55 },
          reason: 'Reduce false positives',
          confidence: 0.6,
          evidence: ['winRateCI95'],
        },
      ],
      evidence: ['session_pnl'],
      constraintsCheck: { pass: true, reasons: ['Within delta caps'] },
      alternativesConsidered: [{ option: 'hold', rejectedBecause: 'Needs adjustment' }],
    };

    const critique = {
      decision: 'hold',
      reason: 'Critique ok',
      confidence: 0.2,
      targets: [],
      evidence: [],
      constraintsCheck: { pass: true, reasons: ['No issues'] },
      alternativesConsidered: [{ option: 'adjust', rejectedBecause: 'Not needed' }],
    };

    mockGetBatchResults.mockResolvedValue({
      results: makeBatchResults({ cycleId: pendingCycle, decision, critique }),
    });
    mockLoadAutonomyState.mockResolvedValue(makePendingState(currentCycle, pendingCycle));

    const mod = await import('@/lib/autonomy/hourly-cycle');
    await mod.runHourlyAutonomyCycle();

    expect(mockSaveStrategyOverrideSnapshot).toHaveBeenCalledTimes(1);
  });
});
