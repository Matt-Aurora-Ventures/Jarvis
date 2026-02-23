import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockMarkStale = vi.fn();
const mockGetStatus = vi.fn();
const mockGetEvidence = vi.fn();

vi.mock('@/lib/backtest-run-registry', () => ({
  markBacktestRunStaleIfExpired: mockMarkStale,
  getBacktestRunStatus: mockGetStatus,
}));

vi.mock('@/lib/backtest-evidence', () => ({
  getBacktestEvidence: mockGetEvidence,
}));

describe('GET /api/backtest/result', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('returns 400 for invalid run id', async () => {
    const route = await import('@/app/api/backtest/result/route');
    const req = new Request('http://localhost/api/backtest/result?runId=bad');

    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(400);
    expect(body.ok).toBe(false);
  });

  it('returns 409 while run is still running', async () => {
    mockMarkStale.mockReturnValue(null);
    mockGetStatus.mockReturnValue({
      runId: 'ui-1700000000000-abcd1234',
      state: 'running',
      phase: 'strategy_run',
      progress: 42,
    });

    const route = await import('@/app/api/backtest/result/route');
    const req = new Request('http://localhost/api/backtest/result?runId=ui-1700000000000-abcd1234');

    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(409);
    expect(body.ok).toBe(false);
    expect(body.progress).toBe(42);
  });

  it('returns summary and evidence metadata when run is complete', async () => {
    mockMarkStale.mockReturnValue(null);
    mockGetStatus.mockReturnValue({
      runId: 'ui-1700000000000-abcd1234',
      evidenceRunId: 'ui-1700000000000-abcd1234',
      manifestId: 'manifest-1',
      state: 'completed',
      phase: 'artifact_persist',
      progress: 100,
      completedAt: 1700000002000,
      error: null,
    });
    mockGetEvidence.mockReturnValue({
      runId: 'ui-1700000000000-abcd1234',
      datasets: [{ tokenSymbol: 'SOL' }],
      trades: [{ strategyId: 'elite' }],
      resultsSummary: [{ strategyId: 'elite', winRate: 55 }],
    });

    const route = await import('@/app/api/backtest/result/route');
    const req = new Request('http://localhost/api/backtest/result?runId=ui-1700000000000-abcd1234');

    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(body.datasetManifestIds).toEqual(['manifest-1']);
    expect(body.summary).toEqual([{ strategyId: 'elite', winRate: 55 }]);
    expect(body.evidence).toEqual(expect.objectContaining({ datasetCount: 1, tradeCount: 1 }));
  });
});
