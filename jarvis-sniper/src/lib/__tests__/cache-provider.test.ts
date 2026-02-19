import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { __resetCacheProviderWarningForTests, createCacheProvider, getCacheProviderMode } from '../cache-provider';

type MutableEnv = {
  JARVIS_CACHE_PROVIDER?: string;
  JARVIS_STRICT_DISTRIBUTED_STATE?: string;
  REDIS_URL?: string;
  UPSTASH_REDIS_REST_URL?: string;
  UPSTASH_REDIS_REST_TOKEN?: string;
};

const originalEnv: MutableEnv = {
  JARVIS_CACHE_PROVIDER: process.env.JARVIS_CACHE_PROVIDER,
  JARVIS_STRICT_DISTRIBUTED_STATE: process.env.JARVIS_STRICT_DISTRIBUTED_STATE,
  REDIS_URL: process.env.REDIS_URL,
  UPSTASH_REDIS_REST_URL: process.env.UPSTASH_REDIS_REST_URL,
  UPSTASH_REDIS_REST_TOKEN: process.env.UPSTASH_REDIS_REST_TOKEN,
};

function resetProviderEnv(): void {
  delete process.env.JARVIS_CACHE_PROVIDER;
  delete process.env.JARVIS_STRICT_DISTRIBUTED_STATE;
  delete process.env.REDIS_URL;
  delete process.env.UPSTASH_REDIS_REST_URL;
  delete process.env.UPSTASH_REDIS_REST_TOKEN;
}

function mockUpstashCachePipeline(): void {
  const kv = new Map<string, string>();

  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
    const rawBody = String(init?.body || '[]');
    const body = JSON.parse(rawBody) as string[][];
    const command = body?.[0] || [];
    const op = String(command[0] || '').toUpperCase();

    if (op === 'GET') {
      const key = String(command[1] || '');
      return {
        ok: true,
        json: async () => [{ result: kv.has(key) ? kv.get(key) : null }],
      } as unknown as Response;
    }

    if (op === 'SET') {
      const key = String(command[1] || '');
      const value = String(command[2] || '');
      kv.set(key, value);
      return {
        ok: true,
        json: async () => [{ result: 'OK' }],
      } as unknown as Response;
    }

    if (op === 'DEL') {
      const key = String(command[1] || '');
      kv.delete(key);
      return {
        ok: true,
        json: async () => [{ result: 1 }],
      } as unknown as Response;
    }

    return {
      ok: false,
      status: 400,
      text: async () => `unsupported op: ${op}`,
    } as unknown as Response;
  }));
}

describe('cache-provider', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.unstubAllGlobals();
    resetProviderEnv();
    vi.restoreAllMocks();
    __resetCacheProviderWarningForTests();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    process.env.JARVIS_CACHE_PROVIDER = originalEnv.JARVIS_CACHE_PROVIDER;
    process.env.JARVIS_STRICT_DISTRIBUTED_STATE = originalEnv.JARVIS_STRICT_DISTRIBUTED_STATE;
    process.env.REDIS_URL = originalEnv.REDIS_URL;
    process.env.UPSTASH_REDIS_REST_URL = originalEnv.UPSTASH_REDIS_REST_URL;
    process.env.UPSTASH_REDIS_REST_TOKEN = originalEnv.UPSTASH_REDIS_REST_TOKEN;
    __resetCacheProviderWarningForTests();
  });

  it('defaults to memory mode when redis signals are absent', () => {
    const provider = createCacheProvider<string>({ namespace: 'test' });

    expect(provider.mode).toBe('memory');
    expect(getCacheProviderMode()).toBe('memory');
  });

  it('falls back to memory mode and warns when redis is requested', () => {
    process.env.JARVIS_CACHE_PROVIDER = 'redis';
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const provider = createCacheProvider<string>({ namespace: 'test' });

    expect(provider.mode).toBe('memory');
    expect(getCacheProviderMode()).toBe('memory');
    expect(warnSpy).toHaveBeenCalled();
  });

  it('reports memory mode when a redis url is present', () => {
    process.env.REDIS_URL = 'redis://localhost:6379';
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    expect(getCacheProviderMode()).toBe('memory');
    expect(warnSpy).toHaveBeenCalled();
  });

  it('throws when strict distributed guard is enabled and redis is requested', () => {
    process.env.JARVIS_CACHE_PROVIDER = 'redis';
    process.env.JARVIS_STRICT_DISTRIBUTED_STATE = 'true';

    expect(() => createCacheProvider<string>({ namespace: 'strict' }))
      .toThrow(/redis mode requested for cache-provider/i);
  });

  it('expires entries by ttl', async () => {
    const provider = createCacheProvider<string>({ namespace: 'ttl' });

    await provider.set('k', 'v', 25);
    await expect(provider.get('k')).resolves.toBe('v');

    vi.advanceTimersByTime(26);
    await expect(provider.get('k')).resolves.toBeNull();
  });

  it('shares redis-backed cache state across provider instances', async () => {
    process.env.JARVIS_CACHE_PROVIDER = 'redis';
    process.env.UPSTASH_REDIS_REST_URL = 'https://example.upstash.io';
    process.env.UPSTASH_REDIS_REST_TOKEN = 'token';
    mockUpstashCachePipeline();

    const first = createCacheProvider<string>({ namespace: 'shared' });
    const second = createCacheProvider<string>({ namespace: 'shared' });

    expect(first.mode).toBe('redis');
    expect(second.mode).toBe('redis');

    await first.set('shared-key', 'value-from-first', 5_000);
    await expect(second.get('shared-key')).resolves.toBe('value-from-first');

    await second.invalidate('shared-key');
    await expect(first.get('shared-key')).resolves.toBeNull();
  });
});
