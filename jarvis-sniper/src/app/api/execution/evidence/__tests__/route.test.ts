import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockGetTradeEvidence = vi.fn();
const mockSummarizeTradeEvidence = vi.fn();

vi.mock('@/lib/execution/evidence', () => ({
  getTradeEvidence: mockGetTradeEvidence,
  summarizeTradeEvidence: mockSummarizeTradeEvidence,
}));

describe('GET /api/execution/evidence', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it('returns 404 when trade evidence is not found', async () => {
    mockGetTradeEvidence.mockReturnValue(null);
    const route = await import('@/app/api/execution/evidence/route');
    const req = new Request('http://localhost/api/execution/evidence?tradeId=trade-missing');

    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(404);
    expect(body.ok).toBe(false);
    expect(body.tradeId).toBe('trade-missing');
    expect(mockGetTradeEvidence).toHaveBeenCalledWith('trade-missing');
  });

  it('returns trade evidence when tradeId exists', async () => {
    mockGetTradeEvidence.mockReturnValue({ tradeId: 'trade-1', outcome: 'confirmed' });
    const route = await import('@/app/api/execution/evidence/route');
    const req = new Request('http://localhost/api/execution/evidence?tradeId=trade-1');

    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(body.tradeId).toBe('trade-1');
    expect(body.evidence).toEqual(expect.objectContaining({ tradeId: 'trade-1' }));
  });

  it('returns summary mode and forwards filters', async () => {
    mockSummarizeTradeEvidence.mockReturnValue({
      count: 3,
      medianSlippageBps: 5,
      p95SlippageBps: 12,
      byOutcome: { confirmed: 2, failed: 1 },
    });
    const route = await import('@/app/api/execution/evidence/route');
    const req = new Request('http://localhost/api/execution/evidence?surface=bags&strategyId=strat-1');

    const res = await route.GET(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(body.summary).toEqual(expect.objectContaining({ count: 3, medianSlippageBps: 5 }));
    expect(mockSummarizeTradeEvidence).toHaveBeenCalledWith({ surface: 'bags', strategyId: 'strat-1' });
  });
});
