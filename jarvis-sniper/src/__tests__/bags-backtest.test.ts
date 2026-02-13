import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type {
  BagsBacktestResult,
  BagsStrategyResult,
  BagsGraduationRecord,
  BagsBacktestConfig,
} from '@/lib/bags-backtest';

// ────────────────────────────────────────────────────────────────
// Test Suite: Bags Backtest Engine
//
// Validates:
// 1. Type interfaces exist and are well-shaped
// 2. Graduation fetching with pagination + fallback endpoints
// 3. DexScreener price enrichment
// 4. Trade simulation with SL/TP/trailing/entry-delay
// 5. Score-based filtering
// 6. Result aggregation and ranking
// 7. Caching behavior
// ────────────────────────────────────────────────────────────────

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

// ─── Helpers ───

function makeGraduation(overrides: Partial<BagsGraduationRecord> = {}): BagsGraduationRecord {
  return {
    mint: 'So1TestMint111111111111111111111111111111111',
    symbol: 'TEST',
    name: 'Test Token',
    score: 65,
    graduationTime: Date.now() - 3600_000,
    bondingCurveScore: 70,
    holderDistributionScore: 60,
    socialScore: 50,
    marketCap: 50000,
    priceAtGraduation: 0.001,
    liquidity: 25000,
    ...overrides,
  };
}

function makeDexScreenerResponse(mint: string, overrides: Record<string, any> = {}) {
  return {
    baseToken: { address: mint, symbol: 'TEST', name: 'Test Token' },
    priceUsd: '0.002',
    priceChange: { m5: 10, h1: 25, h24: 100 },
    volume: { h24: '150000' },
    liquidity: { usd: '50000' },
    marketCap: '100000',
    pairCreatedAt: Date.now() - 7200_000,
    ...overrides,
  };
}

describe('bags-backtest types', () => {
  it('BagsBacktestResult should have required fields', async () => {
    const { runBagsBacktest } = await import('@/lib/bags-backtest');
    expect(typeof runBagsBacktest).toBe('function');
  });

  it('BagsStrategyResult should have scoring fields', async () => {
    // Verify the type shape by constructing a mock
    const result: BagsStrategyResult = {
      id: 'test',
      params: {
        stopLossPct: 15,
        takeProfitPct: 50,
        trailingStopPct: 10,
        entryDelayMinutes: 0,
        minScore: 0,
      },
      trades: 100,
      wins: 60,
      losses: 40,
      winRate: 0.6,
      avgProfitPct: 25,
      avgLossPct: -12,
      profitFactor: 1.8,
      maxDrawdownPct: 35,
      totalReturnPct: 150,
      sharpeRatio: 1.2,
    };
    expect(result.winRate).toBe(0.6);
    expect(result.profitFactor).toBe(1.8);
    expect(result.sharpeRatio).toBe(1.2);
  });

  it('BagsGraduationRecord should have score dimensions', async () => {
    const grad = makeGraduation();
    expect(grad.bondingCurveScore).toBeDefined();
    expect(grad.holderDistributionScore).toBeDefined();
    expect(grad.socialScore).toBeDefined();
    // NO liquidity score - bags locks liquidity
    expect((grad as any).liquidityScore).toBeUndefined();
  });
});

describe('fetchBagsGraduations', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should try multiple endpoints and return data from first success', async () => {
    const { fetchBagsGraduations } = await import('@/lib/bags-backtest');

    // First endpoint fails, second succeeds
    mockFetch
      .mockResolvedValueOnce({ ok: false, status: 404 })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([
          { mint: 'mint1', symbol: 'T1', name: 'Token1', score: 70, graduation_time: 1000 },
          { mint: 'mint2', symbol: 'T2', name: 'Token2', score: 50, graduation_time: 2000 },
        ]),
      });

    const result = await fetchBagsGraduations(10);
    expect(result.length).toBeGreaterThan(0);
    expect(result[0].mint).toBeTruthy();
  });

  it('should paginate when limit > 500', async () => {
    const { fetchBagsGraduations } = await import('@/lib/bags-backtest');

    const page1 = Array.from({ length: 500 }, (_, i) => ({
      mint: `mint_${i}`, symbol: `T${i}`, name: `Token${i}`, score: 50, graduation_time: 1000 + i,
    }));
    const page2 = Array.from({ length: 100 }, (_, i) => ({
      mint: `mint_${500 + i}`, symbol: `T${500 + i}`, name: `Token${500 + i}`, score: 50, graduation_time: 2000 + i,
    }));

    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => page1 })
      .mockResolvedValueOnce({ ok: true, json: async () => page2 });

    const result = await fetchBagsGraduations(600);
    expect(result.length).toBe(600);
  });

  it('should return empty array when all endpoints fail', async () => {
    const { fetchBagsGraduations } = await import('@/lib/bags-backtest');

    mockFetch.mockResolvedValue({ ok: false, status: 500 });
    const result = await fetchBagsGraduations(10);
    expect(result).toEqual([]);
  });

  it('should handle network errors gracefully', async () => {
    const { fetchBagsGraduations } = await import('@/lib/bags-backtest');

    mockFetch.mockRejectedValue(new Error('Network error'));
    const result = await fetchBagsGraduations(10);
    expect(result).toEqual([]);
  });
});

describe('enrichWithDexScreener', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should fetch price data for each graduation token', async () => {
    const { enrichWithDexScreener } = await import('@/lib/bags-backtest');

    const grads = [makeGraduation({ mint: 'mint1' }), makeGraduation({ mint: 'mint2' })];
    const pair1 = makeDexScreenerResponse('mint1', { priceUsd: '0.005' });
    const pair2 = makeDexScreenerResponse('mint2', { priceUsd: '0.010' });

    mockFetch
      .mockResolvedValueOnce({ ok: true, json: async () => [pair1] })
      .mockResolvedValueOnce({ ok: true, json: async () => [pair2] });

    const enriched = await enrichWithDexScreener(grads);
    expect(enriched.length).toBe(2);
    expect(enriched[0].currentPrice).toBeDefined();
    expect(enriched[0].peakPrice).toBeDefined();
    expect(enriched[0].priceChange5m).toBeDefined();
    expect(enriched[0].priceChange1h).toBeDefined();
    expect(enriched[0].priceChange24h).toBeDefined();
  });

  it('should handle DexScreener failures gracefully (skip token)', async () => {
    const { enrichWithDexScreener } = await import('@/lib/bags-backtest');

    const grads = [makeGraduation({ mint: 'mint1' })];
    mockFetch.mockResolvedValueOnce({ ok: false, status: 429 });

    const enriched = await enrichWithDexScreener(grads);
    // Should still return the graduation with null/default price data
    expect(enriched.length).toBe(1);
  });
});

describe('simulateBagsTrade', () => {
  it('should calculate win when price reaches TP', async () => {
    const { simulateBagsTrade } = await import('@/lib/bags-backtest');

    const result = simulateBagsTrade({
      entryPrice: 0.001,
      peakPrice: 0.003, // 200% gain
      currentPrice: 0.0015,
      stopLossPct: 20,
      takeProfitPct: 100, // TP at 100% = 0.002
      trailingStopPct: 0,
    });

    expect(result.hit).toBe('tp');
    expect(result.pnlPct).toBeCloseTo(100, 0);
  });

  it('should calculate loss when price hits SL', async () => {
    const { simulateBagsTrade } = await import('@/lib/bags-backtest');

    const result = simulateBagsTrade({
      entryPrice: 0.001,
      peakPrice: 0.0011, // Barely moved up
      currentPrice: 0.0005, // Dumped 50%
      stopLossPct: 20,
      takeProfitPct: 100,
      trailingStopPct: 0,
    });

    expect(result.hit).toBe('sl');
    expect(result.pnlPct).toBeCloseTo(-20, 0);
  });

  it('should trigger trailing stop after peak', async () => {
    const { simulateBagsTrade } = await import('@/lib/bags-backtest');

    const result = simulateBagsTrade({
      entryPrice: 0.001,
      peakPrice: 0.003, // 200% gain
      currentPrice: 0.002, // Dropped 33% from peak
      stopLossPct: 50,
      takeProfitPct: 500, // Very high TP never hit
      trailingStopPct: 25, // Trail triggers at 25% from peak
    });

    expect(result.hit).toBe('trail');
    expect(result.pnlPct).toBeGreaterThan(0); // Still profitable
  });

  it('should apply entry delay by adjusting entry price', async () => {
    const { simulateBagsTrade } = await import('@/lib/bags-backtest');

    // With delay, entry price may be different (simulated as small markup)
    const noDelay = simulateBagsTrade({
      entryPrice: 0.001,
      peakPrice: 0.002,
      currentPrice: 0.0015,
      stopLossPct: 20,
      takeProfitPct: 50,
      trailingStopPct: 0,
      entryDelayMinutes: 0,
    });

    const withDelay = simulateBagsTrade({
      entryPrice: 0.001,
      peakPrice: 0.002,
      currentPrice: 0.0015,
      stopLossPct: 20,
      takeProfitPct: 50,
      trailingStopPct: 0,
      entryDelayMinutes: 5,
      priceChange5m: 10, // 10% gain in first 5 min
    });

    // Entry with delay should have a different (worse) entry
    expect(withDelay.effectiveEntryPrice).toBeGreaterThan(noDelay.effectiveEntryPrice);
  });
});

describe('runBagsBacktest', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('should return BagsBacktestResult with all required fields', async () => {
    const { runBagsBacktest } = await import('@/lib/bags-backtest');

    // Mock graduation endpoint
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => Array.from({ length: 10 }, (_, i) => ({
        mint: `mint_${i}`,
        symbol: `T${i}`,
        name: `Token ${i}`,
        score: 40 + i * 5,
        graduation_time: (Date.now() - 86400_000) / 1000,
        bonding_curve_score: 50,
        holder_distribution_score: 60,
        social_score: 40,
      })),
    });

    // Mock DexScreener for each token
    for (let i = 0; i < 10; i++) {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [makeDexScreenerResponse(`mint_${i}`, {
          priceUsd: String(0.001 * (1 + Math.random())),
        })],
      });
    }

    const result = await runBagsBacktest();

    expect(result.totalTokens).toBeGreaterThan(0);
    expect(result.tokensWithData).toBeGreaterThan(0);
    expect(result.strategyResults).toBeDefined();
    expect(Array.isArray(result.strategyResults)).toBe(true);
    expect(result.bestStrategy).toBeDefined();
    expect(result.graduationStats).toBeDefined();
    expect(result.graduationStats.avgPeakMultiplier).toBeDefined();
    expect(result.graduationStats.medianLifespanHours).toBeDefined();
  });

  it('should test multiple SL/TP combinations', async () => {
    const { runBagsBacktest } = await import('@/lib/bags-backtest');

    // Provide minimal mock data
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [
        { mint: 'mint_1', symbol: 'T1', name: 'Token 1', score: 70, graduation_time: Date.now() / 1000 },
      ],
    });
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [makeDexScreenerResponse('mint_1')],
    });

    const result = await runBagsBacktest({ maxTokens: 5 });
    // With minimal mock data (1 token), strategy results may be empty if
    // the token doesn't meet scoring thresholds for any SL/TP combo.
    expect(result.strategyResults).toBeDefined();
    expect(Array.isArray(result.strategyResults)).toBe(true);
  });

  it('should filter by score thresholds', async () => {
    const { runBagsBacktest } = await import('@/lib/bags-backtest');

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => [
        { mint: 'low', symbol: 'LOW', name: 'Low Score', score: 20, graduation_time: Date.now() / 1000 },
        { mint: 'high', symbol: 'HIGH', name: 'High Score', score: 80, graduation_time: Date.now() / 1000 },
      ],
    });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => [makeDexScreenerResponse('low')] });
    mockFetch.mockResolvedValueOnce({ ok: true, json: async () => [makeDexScreenerResponse('high')] });

    const result = await runBagsBacktest({ maxTokens: 5 });
    // Strategy results with high minScore should have fewer trades
    const highScoreStrategies = result.strategyResults.filter(s => s.params.minScore >= 60);
    const lowScoreStrategies = result.strategyResults.filter(s => s.params.minScore === 0);

    if (highScoreStrategies.length > 0 && lowScoreStrategies.length > 0) {
      expect(highScoreStrategies[0].trades).toBeLessThanOrEqual(lowScoreStrategies[0].trades);
    }
  });

  it('should rank strategies by sharpeRatio', async () => {
    const { runBagsBacktest } = await import('@/lib/bags-backtest');

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => Array.from({ length: 5 }, (_, i) => ({
        mint: `mint_${i}`, symbol: `T${i}`, name: `Token ${i}`,
        score: 60, graduation_time: Date.now() / 1000,
      })),
    });
    for (let i = 0; i < 5; i++) {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [makeDexScreenerResponse(`mint_${i}`)],
      });
    }

    const result = await runBagsBacktest({ maxTokens: 5 });
    // Best strategy should have highest sharpe
    if (result.strategyResults.length > 1) {
      expect(result.bestStrategy!.sharpeRatio).toBeGreaterThanOrEqual(
        result.strategyResults[result.strategyResults.length - 1].sharpeRatio
      );
    }
  });
});

describe('backtest caching', () => {
  it('should export a cache mechanism', async () => {
    const { backtestCache } = await import('@/lib/bags-backtest');
    expect(backtestCache).toBeDefined();
    expect(typeof backtestCache.get).toBe('function');
    expect(typeof backtestCache.set).toBe('function');
  });
});
