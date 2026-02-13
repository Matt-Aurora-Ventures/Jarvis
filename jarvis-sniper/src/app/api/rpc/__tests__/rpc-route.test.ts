import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mockResolveServerRpcConfig = vi.fn();
const mockRateLimiterCheck = vi.fn();

vi.mock('@/lib/server-rpc-config', () => ({
  resolveServerRpcConfig: mockResolveServerRpcConfig,
}));

vi.mock('@/lib/rate-limiter', () => ({
  rpcRateLimiter: { check: mockRateLimiterCheck },
  getClientIp: vi.fn().mockReturnValue('127.0.0.1'),
}));

const originalFetch = globalThis.fetch;

describe('POST /api/rpc', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    mockRateLimiterCheck.mockReturnValue({ allowed: true });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it('returns 503 JSON-RPC error when server RPC config is unavailable', async () => {
    mockResolveServerRpcConfig.mockReturnValue({
      ok: false,
      url: null,
      source: 'missing',
      isProduction: true,
      diagnostic: 'Missing server RPC config.',
      sanitizedUrl: null,
    });

    const route = await import('@/app/api/rpc/route');
    const req = new Request('http://localhost/api/rpc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'getSlot',
        params: [],
      }),
    });

    const res = await route.POST(req);
    const body = await res.json();

    expect(res.status).toBe(503);
    expect(body.error?.message).toBe('RPC provider unavailable');
    expect(body.error?.data?.source).toBe('missing');
  });

  it('forwards allowed RPC methods when config is valid', async () => {
    mockResolveServerRpcConfig.mockReturnValue({
      ok: true,
      url: 'https://beta.helius-rpc.com/?api-key=***',
      source: 'helius_gatekeeper',
      isProduction: true,
      diagnostic: 'Using helius_gatekeeper',
      sanitizedUrl: 'https://beta.helius-rpc.com/?api-key=***',
    });

    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          jsonrpc: '2.0',
          result: 123456,
          id: 7,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    ) as any;

    const route = await import('@/app/api/rpc/route');
    const req = new Request('http://localhost/api/rpc', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jsonrpc: '2.0',
        id: 7,
        method: 'getSlot',
        params: [],
      }),
    });

    const res = await route.POST(req);
    const body = await res.json();

    expect(res.status).toBe(200);
    expect(body.result).toBe(123456);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });
});

