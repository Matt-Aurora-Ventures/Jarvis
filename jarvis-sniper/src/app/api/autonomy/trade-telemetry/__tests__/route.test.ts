import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockAppendTradeTelemetryEvent = vi.fn();
const mockAutonomyLimiterCheck = vi.fn();
const mockUpsertTradeEvidence = vi.fn();

vi.mock('@/lib/autonomy/trade-telemetry-store', () => ({
  appendTradeTelemetryEvent: mockAppendTradeTelemetryEvent,
}));

vi.mock('@/lib/execution/evidence', () => ({
  upsertTradeEvidence: mockUpsertTradeEvidence,
}));

vi.mock('@/lib/rate-limiter', () => ({
  autonomyRateLimiter: { check: mockAutonomyLimiterCheck },
  getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
}));

describe('POST /api/autonomy/trade-telemetry', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env.AUTONOMY_TELEMETRY_TOKEN = 'telemetry-token';
    mockAutonomyLimiterCheck.mockReturnValue({ allowed: true });
    mockUpsertTradeEvidence.mockResolvedValue(undefined);
  });

  it('rejects invalid payloads', async () => {
    const route = await import('@/app/api/autonomy/trade-telemetry/route');
    const req = new Request('http://localhost/api/autonomy/trade-telemetry', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer telemetry-token',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ mint: 'abc', status: 'open' }),
    });
    const res = await route.POST(req);
    const body = await res.json();
    expect(res.status).toBe(400);
    expect(String(body.error || '')).toContain('positionId');
    expect(mockUpsertTradeEvidence).not.toHaveBeenCalled();
  });

  it('persists sanitized telemetry and execution evidence, returns 202', async () => {
    mockAppendTradeTelemetryEvent.mockResolvedValue({
      schemaVersion: 1,
      positionId: 'pos-1',
      mint: 'mint-1',
      status: 'closed',
      trustLevel: 'trusted',
      receivedAt: '2026-02-17T20:00:00.000Z',
      receivedAtMs: 1763352000000,
      eventType: 'sell_attempt',
      strategyId: 'strat-1',
      executionOutcome: 'confirmed',
    });
    const route = await import('@/app/api/autonomy/trade-telemetry/route');
    const req = new Request('http://localhost/api/autonomy/trade-telemetry', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer telemetry-token',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        positionId: 'pos-1',
        mint: 'mint-1',
        status: 'closed',
        eventType: 'sell_attempt',
        strategyId: 'strat-1',
        surface: 'bags',
        route: 'bags_sdk_proxy',
        expectedPrice: 1.1,
        executedPrice: 1.12,
        slippageBps: 18,
        priorityFeeLamports: 5000,
        jitoUsed: true,
        mevRiskTag: 'medium',
        datasetRefs: ['ds-1'],
        executionOutcome: 'confirmed',
      }),
    });
    const res = await route.POST(req);
    const body = await res.json();
    expect(res.status).toBe(202);
    expect(body.ok).toBe(true);
    expect(body.eventType).toBe('sell_attempt');
    expect(body.trustLevel).toBe('trusted');
    expect(mockAppendTradeTelemetryEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        positionId: 'pos-1',
        mint: 'mint-1',
        status: 'closed',
        trustLevel: 'trusted',
      }),
    );
    expect(mockUpsertTradeEvidence).toHaveBeenCalledWith(
      expect.objectContaining({
        tradeId: 'pos-1',
        surface: 'bags',
        strategyId: 'strat-1',
        route: 'bags_sdk_proxy',
        expectedPrice: 1.1,
        executedPrice: 1.12,
        slippageBps: 18,
        priorityFeeLamports: 5000,
        jitoUsed: true,
        mevRiskTag: 'medium',
        datasetRefs: ['ds-1'],
        outcome: 'confirmed',
      }),
    );
  });
});

