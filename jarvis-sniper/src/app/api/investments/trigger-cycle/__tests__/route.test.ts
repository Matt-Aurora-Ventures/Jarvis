import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

describe('POST /api/investments/trigger-cycle', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());
    process.env.INVESTMENTS_SERVICE_BASE_URL = 'http://127.0.0.1:8770';
    process.env.INVESTMENTS_ADMIN_TOKEN = 'expected-token';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('forwards trigger-cycle writes to investments upstream using server admin token', async () => {
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
        headers: { 'Content-Type': 'application/json' },
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

  it('still proxies when server admin token is missing (upstream decides auth)', async () => {
    delete process.env.INVESTMENTS_ADMIN_TOKEN;
    const mockFetch = vi.mocked(fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const route = await import('@/app/api/investments/trigger-cycle/route');
    const res = await route.POST(
      new Request('http://localhost/api/investments/trigger-cycle', { method: 'POST' }),
    );
    const body = await res.json();

    expect(res.status).toBe(401);
    expect(String(body.error || '')).toContain('Unauthorized');
    expect(mockFetch).toHaveBeenCalledWith(
      'http://127.0.0.1:8770/api/investments/trigger-cycle',
      expect.objectContaining({
        method: 'POST',
      }),
    );
    const call = mockFetch.mock.calls[0]?.[1] as RequestInit | undefined;
    expect((call?.headers as Record<string, string> | undefined)?.Authorization).toBeUndefined();
  });
});
