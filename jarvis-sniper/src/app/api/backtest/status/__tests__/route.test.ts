import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockMarkStale = vi.fn();
const mockGetStatus = vi.fn();
const mockComputeLastMovementAt = vi.fn();

vi.mock('@/lib/backtest-run-registry', () => ({
  markBacktestRunStaleIfExpired: mockMarkStale,
  getBacktestRunStatus: mockGetStatus,
  computeLastMovementAt: mockComputeLastMovementAt,
}));

describe('GET /api/backtest/status', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mockComputeLastMovementAt.mockReturnValue(1700000000000);
  });

  it('returns 400 for invalid run id', async () => {
    const route = await import('@/app/api/backtest/status/route');
    const req = new Request('http://localhost/api/backtest/status?runId=bad');

    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body.ok).toBe(false);
  });

  it('returns 404 when run is missing', async () => {
    mockMarkStale.mockReturnValue(null);
    mockGetStatus.mockReturnValue(null);
    const route = await import('@/app/api/backtest/status/route');
    const req = new Request('http://localhost/api/backtest/status?runId=ui-1700000000000-abcd1234');

    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(404);
    expect(body.ok).toBe(false);
  });

  it('returns normalized status payload for a run', async () => {
    mockMarkStale.mockReturnValue(null);
    mockGetStatus.mockReturnValue({
      runId: 'ui-1700000000000-abcd1234',
      manifestId: 'manifest-1',
      state: 'completed',
      phase: 'artifact_persist',
      progress: 100,
      startedAt: 1700000000000,
      updatedAt: 1700000001000,
      heartbeatAt: 1700000001000,
      completedAt: 1700000002000,
      stale: false,
      staleReason: null,
      error: null,
    });

    const route = await import('@/app/api/backtest/status/route');
    const req = new Request('http://localhost/api/backtest/status?runId=ui-1700000000000-abcd1234');

    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(body.datasetManifestIds).toEqual(['manifest-1']);
    expect(body.lastMovementAt).toBe(1700000000000);
  });
});
