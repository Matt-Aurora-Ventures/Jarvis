import { describe, it, expect, vi, beforeEach } from 'vitest';

// ────────────────────────────────────────────────────────────────
// Test Suite: Bags Backtest API Route
//
// Validates:
// 1. GET returns cached results
// 2. POST triggers fresh backtest
// 3. Response shape includes top strategies + stats
// 4. Error handling
// ────────────────────────────────────────────────────────────────

// We test the route handler functions directly (not via HTTP)
// since Next.js route handlers are just async functions.

// Mock the backtest engine to avoid real API calls
vi.mock('@/lib/bags-backtest', () => ({
  runBagsBacktest: vi.fn(),
  backtestCache: {
    get: vi.fn(),
    set: vi.fn(),
    invalidate: vi.fn(),
  },
}));

// Mock rate limiter so tests aren't blocked
vi.mock('@/lib/rate-limiter', () => ({
  apiRateLimiter: { check: vi.fn().mockReturnValue({ allowed: true }) },
  getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
}));

/** Helper: create a minimal GET Request for the route handler */
function mockGetRequest() {
  return new Request('http://localhost/api/bags-backtest', { method: 'GET' });
}

describe('GET /api/bags-backtest', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('should export a GET handler', async () => {
    const route = await import('@/app/api/bags-backtest/route');
    expect(typeof route.GET).toBe('function');
  });

  it('should return cached results when available', async () => {
    const { backtestCache } = await import('@/lib/bags-backtest');
    const mockResult = {
      totalTokens: 100,
      tokensWithData: 80,
      strategyResults: [{ id: 'test', sharpeRatio: 1.5 }],
      bestStrategy: { id: 'test', sharpeRatio: 1.5 },
      graduationStats: { avgPeakMultiplier: 2.5 },
    };

    (backtestCache.get as any).mockReturnValue(mockResult);

    const route = await import('@/app/api/bags-backtest/route');
    const response = await route.GET(mockGetRequest());
    const data = await response.json();

    expect(data.topStrategies).toBeDefined();
    expect(data.cached).toBe(true);
  });

  it('should run fresh backtest when cache is empty', async () => {
    const { backtestCache, runBagsBacktest } = await import('@/lib/bags-backtest');

    (backtestCache.get as any).mockReturnValue(null);
    (runBagsBacktest as any).mockResolvedValue({
      totalTokens: 50,
      tokensWithData: 40,
      strategyResults: [
        { id: 'strat1', sharpeRatio: 2.0, winRate: 0.65, profitFactor: 1.8, trades: 30 },
        { id: 'strat2', sharpeRatio: 1.5, winRate: 0.60, profitFactor: 1.5, trades: 25 },
      ],
      bestStrategy: { id: 'strat1', sharpeRatio: 2.0 },
      graduationStats: {
        avgScoreWinners: 65,
        avgScoreLosers: 40,
        avgTimeToPeakMs: 3600000,
        avgPeakMultiplier: 3.0,
        medianLifespanHours: 12,
      },
    });

    const route = await import('@/app/api/bags-backtest/route');
    const response = await route.GET(mockGetRequest());
    const data = await response.json();

    expect(data.totalTokens).toBe(50);
    expect(data.topStrategies).toBeDefined();
    expect(data.graduationStats).toBeDefined();
    expect(data.cached).toBe(false);
  });

  it('should return top 10 strategies max', async () => {
    const { backtestCache, runBagsBacktest } = await import('@/lib/bags-backtest');

    (backtestCache.get as any).mockReturnValue(null);

    const manyStrategies = Array.from({ length: 50 }, (_, i) => ({
      id: `strat_${i}`,
      sharpeRatio: 50 - i,
      winRate: 0.5 + i * 0.001,
      profitFactor: 1.5,
      trades: 20,
    }));

    (runBagsBacktest as any).mockResolvedValue({
      totalTokens: 100,
      tokensWithData: 80,
      strategyResults: manyStrategies,
      bestStrategy: manyStrategies[0],
      graduationStats: { avgPeakMultiplier: 2.0, medianLifespanHours: 8 },
    });

    const route = await import('@/app/api/bags-backtest/route');
    const response = await route.GET(mockGetRequest());
    const data = await response.json();

    expect(data.topStrategies.length).toBeLessThanOrEqual(10);
  });
});

describe('POST /api/bags-backtest', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('should export a POST handler', async () => {
    const route = await import('@/app/api/bags-backtest/route');
    expect(typeof route.POST).toBe('function');
  });

  it('should accept custom parameters', async () => {
    const { backtestCache, runBagsBacktest } = await import('@/lib/bags-backtest');

    (backtestCache.get as any).mockReturnValue(null);
    (runBagsBacktest as any).mockResolvedValue({
      totalTokens: 20,
      tokensWithData: 15,
      strategyResults: [{ id: 'custom', sharpeRatio: 1.0, trades: 10 }],
      bestStrategy: { id: 'custom', sharpeRatio: 1.0 },
      graduationStats: { avgPeakMultiplier: 1.5, medianLifespanHours: 4 },
    });

    const route = await import('@/app/api/bags-backtest/route');
    const request = new Request('http://localhost/api/bags-backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ maxTokens: 20, minScore: 50 }),
    });

    const response = await route.POST(request);
    const data = await response.json();

    expect(data.totalTokens).toBeDefined();
    expect((runBagsBacktest as any)).toHaveBeenCalled();
  });

  it('should invalidate cache on POST', async () => {
    const { backtestCache, runBagsBacktest } = await import('@/lib/bags-backtest');

    (runBagsBacktest as any).mockResolvedValue({
      totalTokens: 10,
      tokensWithData: 8,
      strategyResults: [],
      bestStrategy: null,
      graduationStats: { avgPeakMultiplier: 1.0, medianLifespanHours: 2 },
    });

    const route = await import('@/app/api/bags-backtest/route');
    const request = new Request('http://localhost/api/bags-backtest', {
      method: 'POST',
      body: '{}',
    });

    await route.POST(request);
    expect(backtestCache.invalidate).toHaveBeenCalled();
  });

  it('should handle errors gracefully', async () => {
    const { runBagsBacktest } = await import('@/lib/bags-backtest');
    (runBagsBacktest as any).mockRejectedValue(new Error('API down'));

    const route = await import('@/app/api/bags-backtest/route');
    const request = new Request('http://localhost/api/bags-backtest', {
      method: 'POST',
      body: '{}',
    });

    const response = await route.POST(request);
    expect(response.status).toBe(500);
    const data = await response.json();
    expect(data.error).toBeTruthy();
  });
});
