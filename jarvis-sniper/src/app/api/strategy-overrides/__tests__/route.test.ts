import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetStrategyOverrideSnapshot = vi.fn();

vi.mock('@/lib/autonomy/override-store', () => ({
  getStrategyOverrideSnapshot: mockGetStrategyOverrideSnapshot,
}));

describe('GET /api/strategy-overrides', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env.AUTONOMY_READ_TOKEN = 'read-token';
  });

  it('returns stable schema with versioned snapshot', async () => {
    mockGetStrategyOverrideSnapshot.mockResolvedValue({
      version: 3,
      updatedAt: '2026-02-13T18:00:00.000Z',
      cycleId: '2026021318',
      signature: 'abc123',
      patches: [
        {
          strategyId: 'pump_fresh_tight',
          patch: { stopLossPct: 18 },
          reason: 'test',
          confidence: 0.8,
          evidence: ['metric.a'],
          sourceCycleId: '2026021318',
          decidedAt: '2026-02-13T18:00:00.000Z',
        },
      ],
    });
    const route = await import('@/app/api/strategy-overrides/route');
    const req = new Request('http://localhost/api/strategy-overrides', {
      headers: { Authorization: 'Bearer read-token' },
    });
    const res = await route.GET(req);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.version).toBe(3);
    expect(Array.isArray(body.patches)).toBe(true);
    expect(body.patches[0].strategyId).toBe('pump_fresh_tight');
  });
});