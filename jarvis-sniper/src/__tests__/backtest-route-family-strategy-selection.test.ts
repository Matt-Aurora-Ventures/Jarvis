import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockReadTradeExecutionPriors = vi.fn();
const mockLoadFamilyDatasetManifest = vi.fn();
const mockPersistFamilyDatasetManifest = vi.fn();

vi.mock('@/lib/rate-limiter', () => ({
  apiRateLimiter: { check: vi.fn().mockReturnValue({ allowed: true }) },
  getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
}));

vi.mock('@/lib/autonomy/trade-telemetry-store', () => ({
  readTradeExecutionPriors: mockReadTradeExecutionPriors,
}));

vi.mock('@/lib/backtest-dataset-manifest', () => ({
  loadFamilyDatasetManifest: mockLoadFamilyDatasetManifest,
  persistFamilyDatasetManifest: mockPersistFamilyDatasetManifest,
}));

function buildCandles(count = 80) {
  const now = Date.now();
  return Array.from({ length: count }, (_, i) => {
    const base = 100 + Math.sin(i / 7) * 2 + (i * 0.02);
    return {
      timestamp: now - ((count - i) * 60 * 60 * 1000),
      open: base,
      high: base + 0.5,
      low: base - 0.5,
      close: base + 0.1,
      volume: 1000 + (i * 7),
    };
  });
}

function buildManifestDataset(index: number) {
  return {
    tokenSymbol: `BAG${index}`,
    mintAddress: `bags-mint-${index}`,
    pairAddress: `bags-pair-${index}`,
    candles: buildCandles(),
    fetchedAt: Date.now(),
    source: 'geckoterminal' as const,
  };
}

describe('POST /api/backtest family strategy selection', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mockReadTradeExecutionPriors.mockResolvedValue(null);

    const manifestDatasets = Array.from({ length: 5 }, (_, i) => buildManifestDataset(i + 1));
    mockLoadFamilyDatasetManifest.mockImplementation((_manifestId: string, family: string) => {
      if (family !== 'bags') return null;
      return {
        manifest: {
          attempted: manifestDatasets.length,
          succeeded: manifestDatasets.length,
          skipped: 0,
        },
        datasets: manifestDatasets,
      };
    });
  });

  it('runs only the explicitly requested strategy when family and strategyId are both provided', async () => {
    const route = await import('@/app/api/backtest/route');
    const req = new Request('http://localhost/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        family: 'bags',
        strategyId: 'bags_momentum',
        mode: 'quick',
        dataScale: 'fast',
        sourcePolicy: 'allow_birdeye_fallback',
        strictNoSynthetic: true,
        includeEvidence: false,
      }),
    });

    const res = await route.POST(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.completedChunks).toBe(1);
    expect(body.failedChunks).toBe(0);
  }, 30_000);
});
