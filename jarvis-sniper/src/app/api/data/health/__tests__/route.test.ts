import { describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/data-plane/health-store', () => ({
  getSourceHealthSummary: vi.fn(() => ({
    updatedAt: '2026-02-19T00:00:00.000Z',
    totalSources: 2,
    healthySources: 1,
    degradedSources: 1,
    snapshots: [
      {
        source: 'dexscreener:boosts',
        checkedAt: '2026-02-19T00:00:00.000Z',
        ok: true,
        freshnessMs: 0,
        latencyMs: 120,
        httpStatus: 200,
        reliabilityScore: 0.95,
        errorBudgetBurn: 0,
        redundancyState: 'healthy',
      },
    ],
  })),
}));

describe('GET /api/data/health', () => {
  it('returns source health summary', async () => {
    const { GET } = await import('@/app/api/data/health/route');
    const response = await GET();
    expect(response.status).toBe(200);
    const payload = await response.json();
    expect(payload.ok).toBe(true);
    expect(payload.totalSources).toBe(2);
    expect(Array.isArray(payload.sources)).toBe(true);
    expect(payload.sources[0].source).toBe('dexscreener:boosts');
  });
});
