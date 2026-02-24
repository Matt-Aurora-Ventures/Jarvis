import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('GET /api/perps/history/[market]', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());
    process.env.PERPS_SERVICE_BASE_URL = 'http://127.0.0.1:5001';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('rejects markets outside allowlist', async () => {
    const route = await import('@/app/api/perps/history/[market]/route');
    const res = await route.GET(
      new Request('http://localhost/api/perps/history/XRP-USD'),
      { params: Promise.resolve({ market: 'XRP-USD' }) },
    );
    const body = await res.json();

    expect(res.status).toBe(404);
    expect(String(body.error || '')).toContain('Unknown market');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('forwards allowed market requests with query params', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ candles: [{ time: 1, open: 1, high: 2, low: 1, close: 2 }] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const route = await import('@/app/api/perps/history/[market]/route');
    const req = new Request('http://localhost/api/perps/history/sol-usd?resolution=15');
    const res = await route.GET(req, { params: Promise.resolve({ market: 'sol-usd' }) });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(Array.isArray(body.candles)).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:5001/api/perps/history/SOL-USD?resolution=15',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('falls back to direct benchmarks history when perps upstream is unavailable', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ error: 'Perps upstream unavailable', details: 'connect ECONNREFUSED 127.0.0.1:5001' }),
          {
            status: 502,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            s: 'ok',
            t: [1700000000],
            o: [101.1],
            h: [102.0],
            l: [100.9],
            c: [101.5],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          },
        ),
      );

    const route = await import('@/app/api/perps/history/[market]/route');
    const req = new Request('http://localhost/api/perps/history/sol-usd?resolution=5');
    const res = await route.GET(req, { params: Promise.resolve({ market: 'sol-usd' }) });
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.market).toBe('SOL-USD');
    expect(Array.isArray(body.candles)).toBe(true);
    expect(body.candles).toHaveLength(1);
    expect(body.source).toBe('pyth-benchmarks-fallback');
    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      'http://127.0.0.1:5001/api/perps/history/SOL-USD?resolution=5',
      expect.objectContaining({ method: 'GET' }),
    );
    expect(String(mockFetch.mock.calls[1]?.[0] || '')).toContain('benchmarks.pyth.network');
  });
});
