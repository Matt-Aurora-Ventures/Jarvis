import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockLoadAutonomyState = vi.fn();
const mockGetStrategyOverrideSnapshot = vi.fn();

vi.mock('@/lib/autonomy/audit-store', () => ({
  loadAutonomyState: mockLoadAutonomyState,
}));

vi.mock('@/lib/autonomy/override-store', () => ({
  getStrategyOverrideSnapshot: mockGetStrategyOverrideSnapshot,
}));

describe('GET /api/autonomy/status auth', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env.AUTONOMY_READ_TOKEN = 'read-token';
    process.env.AUTONOMY_ENABLED = 'true';
    process.env.AUTONOMY_APPLY_OVERRIDES = 'true';
    mockLoadAutonomyState.mockResolvedValue({
      latestCycleId: '2026021715',
      latestCompletedCycleId: '2026021714',
      cycles: {},
    });
    mockGetStrategyOverrideSnapshot.mockResolvedValue({
      version: 0,
      updatedAt: new Date(0).toISOString(),
      cycleId: '',
      signature: '',
      patches: [],
    });
  });

  it('returns 401 without token', async () => {
    const route = await import('@/app/api/autonomy/status/route');
    const req = new Request('http://localhost/api/autonomy/status');
    const res = await route.GET(req);
    expect(res.status).toBe(401);
  });

  it('returns 200 with valid token', async () => {
    const route = await import('@/app/api/autonomy/status/route');
    const req = new Request('http://localhost/api/autonomy/status', {
      headers: { Authorization: 'Bearer read-token' },
    });
    const res = await route.GET(req);
    expect(res.status).toBe(200);
  });
});