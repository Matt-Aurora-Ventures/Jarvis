import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/server-rpc-config', () => ({
  resolveServerRpcConfig: () => ({
    ok: true,
    url: 'https://mainnet.helius-rpc.com/?api-key=test',
    source: 'helius_gatekeeper',
    isProduction: false,
    diagnostic: 'ok',
    sanitizedUrl: 'https://mainnet.helius-rpc.com/?api-key=***',
  }),
}));

describe('GET /api/health backend.cloudRunTagUrl', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('fetch', vi.fn());
    delete process.env.BACKTEST_CLOUD_RUN_TAG_URL;
    delete process.env.BAGS_API_KEY;
    delete process.env.PERPS_SERVICE_BASE_URL;
    delete process.env.INVESTMENTS_SERVICE_BASE_URL;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('prefers BACKTEST_CLOUD_RUN_TAG_URL when it is a valid run.app URL', async () => {
    process.env.BACKTEST_CLOUD_RUN_TAG_URL = 'https://env-tag-123.us-central1.a.run.app';
    const route = await import('@/app/api/health/route');

    const res = await route.GET(
      new Request('http://localhost/api/health', {
        headers: {
          'x-fh-requested-host': 'https://header-tag.us-central1.a.run.app',
        },
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.backend.cloudRunTagUrl).toBe('https://env-tag-123.us-central1.a.run.app');
  });

  it('ignores invalid env value and falls back to header-derived run.app host', async () => {
    process.env.BACKTEST_CLOUD_RUN_TAG_URL = 'https://jarvislife.cloud';
    const route = await import('@/app/api/health/route');

    const res = await route.GET(
      new Request('http://localhost/api/health', {
        headers: {
          'x-fh-requested-host': 'https://svc-abcde-uc.a.run.app/some/path',
        },
      }),
    );
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.backend.cloudRunTagUrl).toBe('https://svc-abcde-uc.a.run.app');
  });

  it('returns null when neither env nor headers contain a valid run.app URL', async () => {
    process.env.BACKTEST_CLOUD_RUN_TAG_URL = 'https://example.com';
    const route = await import('@/app/api/health/route');

    const res = await route.GET(new Request('http://localhost/api/health'));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.backend.cloudRunTagUrl).toBeNull();
  });

  it('reports upstream reachability and degrades when upstream checks fail', async () => {
    process.env.PERPS_SERVICE_BASE_URL = 'https://perps.internal';
    process.env.INVESTMENTS_SERVICE_BASE_URL = 'https://investments.internal';

    const mockFetch = vi.mocked(fetch);
    mockFetch
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: false }), { status: 503 }));

    const route = await import('@/app/api/health/route');
    const res = await route.GET(new Request('http://localhost/api/health'));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.status).toBe('degraded');
    expect(body.upstreams.perps.configured).toBe(true);
    expect(body.upstreams.perps.ok).toBe(true);
    expect(body.upstreams.investments.configured).toBe(true);
    expect(body.upstreams.investments.ok).toBe(false);
    expect(String(mockFetch.mock.calls[0]?.[0] || '')).toContain('/api/perps/status');
    expect(String(mockFetch.mock.calls[1]?.[0] || '')).toContain('/api/investments/performance');
  });

  it('degrades when upstream base URLs are not configured', async () => {
    process.env.BAGS_API_KEY = 'configured';
    const route = await import('@/app/api/health/route');
    const res = await route.GET(new Request('http://localhost/api/health'));
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.status).toBe('degraded');
    expect(body.upstreams.perps.configured).toBe(false);
    expect(body.upstreams.investments.configured).toBe(false);
  });
});
