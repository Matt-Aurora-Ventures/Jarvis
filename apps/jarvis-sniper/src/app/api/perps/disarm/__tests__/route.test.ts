import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('POST /api/perps/disarm', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());
    process.env.PERPS_SERVICE_BASE_URL = 'http://127.0.0.1:5001';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('forwards disarm requests to perps upstream', async () => {
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true, stage: 'disarmed' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const route = await import('@/app/api/perps/disarm/route');
    const req = new Request('http://localhost/api/perps/disarm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'ui_disarm' }),
    });
    const res = await route.POST(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:5001/api/perps/disarm',
      expect.objectContaining({ method: 'POST' }),
    );
  });
});
