import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('POST /api/investments/trigger-cycle', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());
    process.env.INVESTMENTS_SERVICE_BASE_URL = 'http://127.0.0.1:8770';
    delete process.env.INVESTMENTS_ADMIN_TOKEN;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('fails closed when admin token is unconfigured', async () => {
    const route = await import('@/app/api/investments/trigger-cycle/route');
    const res = await route.POST(
      new Request('http://localhost/api/investments/trigger-cycle', { method: 'POST' }),
    );
    const body = await res.json();

    expect(res.status).toBe(503);
    expect(String(body.error || '')).toContain('not configured');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('rejects unauthorized writes when token mismatch', async () => {
    process.env.INVESTMENTS_ADMIN_TOKEN = 'expected-token';
    const route = await import('@/app/api/investments/trigger-cycle/route');
    const res = await route.POST(
      new Request('http://localhost/api/investments/trigger-cycle', {
        method: 'POST',
        headers: { Authorization: 'Bearer wrong-token' },
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(401);
    expect(String(body.error || '')).toContain('Unauthorized');
    expect(fetch).not.toHaveBeenCalled();
  });

  it('forwards authorized write to investments upstream', async () => {
    process.env.INVESTMENTS_ADMIN_TOKEN = 'expected-token';
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const route = await import('@/app/api/investments/trigger-cycle/route');
    const res = await route.POST(
      new Request('http://localhost/api/investments/trigger-cycle', {
        method: 'POST',
        headers: { Authorization: 'Bearer expected-token', 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: true }),
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.ok).toBe(true);
    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8770/api/investments/trigger-cycle',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Bearer expected-token',
        }),
      }),
    );
  });
});
