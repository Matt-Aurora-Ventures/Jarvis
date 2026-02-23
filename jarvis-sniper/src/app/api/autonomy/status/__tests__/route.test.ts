import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockLoadAutonomyState = vi.fn();
const mockGetStrategyOverrideSnapshot = vi.fn();

vi.mock('@/lib/autonomy/audit-store', () => ({
  loadAutonomyState: mockLoadAutonomyState,
}));

vi.mock('@/lib/autonomy/override-store', () => ({
  getStrategyOverrideSnapshot: mockGetStrategyOverrideSnapshot,
}));

describe('GET /api/autonomy/status', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env.AUTONOMY_READ_TOKEN = 'read-token';
    process.env.AUTONOMY_ENABLED = 'true';
    process.env.AUTONOMY_APPLY_OVERRIDES = 'true';
    process.env.XAI_API_KEY = 'xai-test-key';
    process.env.AUTONOMY_READ_TOKEN = 'read-token';
  });

  it('returns sanitized runtime truth fields', async () => {
    mockLoadAutonomyState.mockResolvedValue({
      latestCycleId: '2026021715',
      latestCompletedCycleId: '2026021714',
      cycles: {
        '2026021714': {
          reasonCode: 'AUTONOMY_PENDING_BATCH',
        },
      },
    });
    mockGetStrategyOverrideSnapshot.mockResolvedValue({
      version: 4,
      updatedAt: '2026-02-17T15:45:00.000Z',
      cycleId: '2026021714',
      signature: 'sig-1',
      patches: [],
    });

    const route = await import('@/app/api/autonomy/status/route');
    const req = new Request('http://localhost/api/autonomy/status', {
      headers: { Authorization: 'Bearer read-token' },
    });
    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.autonomyEnabled).toBe(true);
    expect(body.applyOverridesEnabled).toBe(true);
    expect(body.xaiConfigured).toBe(true);
    expect(body.latestCycleId).toBe('2026021714');
    expect(body.latestReasonCode).toBe('AUTONOMY_PENDING_BATCH');
    expect(body.overrideVersion).toBe(4);
    expect(body.overrideUpdatedAt).toBe('2026-02-17T15:45:00.000Z');
  });
});