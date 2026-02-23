import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetStrategyOverrideSnapshot = vi.fn();

vi.mock('@/lib/autonomy/override-store', () => ({
  getStrategyOverrideSnapshot: mockGetStrategyOverrideSnapshot,
}));

describe('GET /api/strategy-overrides auth', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    process.env.AUTONOMY_READ_TOKEN = 'read-token';
    mockGetStrategyOverrideSnapshot.mockResolvedValue({
      version: 0,
      updatedAt: new Date(0).toISOString(),
      cycleId: '',
      signature: '',
      patches: [],
    });
  });

  it('returns 401 without token', async () => {
    const route = await import('@/app/api/strategy-overrides/route');
    const req = new Request('http://localhost/api/strategy-overrides');
    const res = await route.GET(req);
    expect(res.status).toBe(401);
  });

  it('returns 200 with valid token', async () => {
    const route = await import('@/app/api/strategy-overrides/route');
    const req = new Request('http://localhost/api/strategy-overrides', {
      headers: { Authorization: 'Bearer read-token' },
    });
    const res = await route.GET(req);
    expect(res.status).toBe(200);
  });
});