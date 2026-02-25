import { beforeEach, describe, expect, it, vi } from 'vitest';

const mockReadTradeExecutionPriors = vi.fn();

vi.mock('@/lib/rate-limiter', () => ({
  apiRateLimiter: { check: vi.fn().mockReturnValue({ allowed: true }) },
  getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
}));

vi.mock('@/lib/autonomy/trade-telemetry-store', () => ({
  readTradeExecutionPriors: mockReadTradeExecutionPriors,
}));

function buildCandles(count = 140) {
  const now = Date.now();
  return Array.from({ length: count }, (_, i) => {
    const base = 100 + Math.sin(i / 6) * 2 + (i * 0.03);
    const open = Number(base.toFixed(6));
    const close = Number((base + Math.sin(i / 3) * 0.2).toFixed(6));
    const high = Number((Math.max(open, close) + 0.25).toFixed(6));
    const low = Number((Math.min(open, close) - 0.25).toFixed(6));
    return {
      timestamp: now - ((count - i) * 60 * 60 * 1000),
      open,
      high,
      low,
      close,
      volume: 1000 + ((i % 7) * 25),
    };
  });
}

describe('POST /api/backtest execution realism contract', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mockReadTradeExecutionPriors.mockResolvedValue(null);
  });

  it('accepts client candles when strictNoSynthetic is omitted (default false)', async () => {
    const route = await import('@/app/api/backtest/route');
    const req = new Request('http://localhost/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategyId: 'bluechip_trend_follow',
        mode: 'quick',
        candles: buildCandles(),
        includeEvidence: false,
      }),
    });

    const res = await route.POST(req);
    const body = await res.json();
    expect(res.status).toBe(200);
    expect(body.sourceDiagnostics.strictNoSynthetic).toBe(false);
    expect(Array.isArray(body.results)).toBe(true);
    expect(body.results.length).toBeGreaterThan(0);
  }, 20000);

  it('fails closed when strictNoSynthetic is explicitly enabled for client candles', async () => {
    const route = await import('@/app/api/backtest/route');
    const req = new Request('http://localhost/api/backtest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        strategyId: 'bluechip_trend_follow',
        mode: 'quick',
        strictNoSynthetic: true,
        candles: buildCandles(),
        includeEvidence: false,
      }),
    });

    const res = await route.POST(req);
    const body = await res.json();
    expect(res.status).toBe(422);
    expect(String(body.error || '')).toContain('strictNoSynthetic gate failed');
  }, 20000);
});
