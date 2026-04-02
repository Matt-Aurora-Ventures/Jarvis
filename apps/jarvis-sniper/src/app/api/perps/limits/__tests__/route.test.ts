import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('POST /api/perps/limits', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());
    process.env.PERPS_SERVICE_BASE_URL = 'http://127.0.0.1:5001';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('forwards limits update requests to perps upstream', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true, max_trades_per_day: 20, daily_loss_limit_usd: 250 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const route = await import('@/app/api/perps/limits/route');
    const req = new Request('http://localhost/api/perps/limits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ max_trades_per_day: 20, daily_loss_limit_usd: 250 }),
    });
    const res = await route.POST(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:5001/api/perps/limits',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
