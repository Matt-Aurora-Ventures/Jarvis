import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('GET /api/investments/performance', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());
    process.env.INVESTMENTS_SERVICE_BASE_URL = 'http://127.0.0.1:8770';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('forwards allowed read endpoint and preserves query params', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ points: [{ ts: '2026-02-22T00:00:00Z', nav_usd: 100 }] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const route = await import('@/app/api/investments/performance/route');
    const res = await route.GET(new Request('http://localhost/api/investments/performance?hours=168'));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(Array.isArray(body.points)).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8770/api/investments/performance?hours=168',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('returns fallback payload when upstream is unavailable', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Investments upstream unavailable' }), {
        status: 502,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const route = await import('@/app/api/investments/performance/route');
    const res = await route.GET(new Request('http://localhost/api/investments/performance?hours=24'));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.basket_id).toBe('alpha');
    expect(body.hours).toBe(24);
    expect(Array.isArray(body.points)).toBe(true);
    expect(body.change_pct).toBe(0);
    expect(body._fallback).toBe(true);
  });
});
