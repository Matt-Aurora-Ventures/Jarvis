import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('GET /api/perps/prices', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('forwards request to perps upstream allowlist endpoint', async () => {
    process.env.PERPS_SERVICE_BASE_URL = 'http://127.0.0.1:5001';
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ 'SOL-USD': { price: 123 } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const route = await import('@/app/api/perps/prices/route');
    const res = await route.GET(new Request('http://localhost/api/perps/prices'));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body['SOL-USD'].price).toBe(123);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:5001/api/perps/prices',
      expect.objectContaining({ method: 'GET' }),
    );
  });
});
