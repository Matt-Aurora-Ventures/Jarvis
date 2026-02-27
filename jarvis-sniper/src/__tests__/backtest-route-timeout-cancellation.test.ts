import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockFetchMintHistory = vi.fn();
const mockReadTradeExecutionPriors = vi.fn();

vi.mock('@/lib/rate-limiter', () => ({
  apiRateLimiter: { check: vi.fn().mockReturnValue({ allowed: true }) },
  getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
}));

vi.mock('@/lib/autonomy/trade-telemetry-store', () => ({
  readTradeExecutionPriors: mockReadTradeExecutionPriors,
}));

vi.mock('@/lib/historical-data', () => ({
  fetchMintHistory: mockFetchMintHistory,
}));

function buildCandles(count = 80) {
  const now = Date.now();
  return Array.from({ length: count }, (_, i) => {
    const base = 100 + Math.sin(i / 5) * 2 + (i * 0.05);
    return {
      timestamp: now - ((count - i) * 60 * 60 * 1000),
      open: base,
      high: base + 0.6,
      low: base - 0.6,
      close: base + 0.1,
      volume: 1000 + (i * 10),
    };
  });
}

describe('POST /api/backtest timeout cancellation propagation', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mockReadTradeExecutionPriors.mockResolvedValue(null);
    mockFetchMintHistory.mockResolvedValue({
      tokenSymbol: 'SOL',
      mintAddress: 'So11111111111111111111111111111111111111112',
      pairAddress: 'pair-sol',
      candles: buildCandles(),
      fetchedAt: Date.now(),
      source: 'geckoterminal',
    });
  });

  it('passes an AbortSignal to fetchMintHistory for bluechip runs', async () => {
    const route = await import('@/app/api/backtest/route');

    const req = new Request('http://localhost/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategyId: 'bluechip_trend_follow',
        mode: 'quick',
        dataScale: 'fast',
        tokenSymbol: 'SOL',
        includeEvidence: false,
      }),
    });

    await route.POST(req);
    expect(mockFetchMintHistory).toHaveBeenCalled();
    const thirdArg = mockFetchMintHistory.mock.calls[0]?.[2] as { signal?: AbortSignal } | undefined;
    expect(thirdArg?.signal).toBeInstanceOf(AbortSignal);
  }, 20_000);
});
