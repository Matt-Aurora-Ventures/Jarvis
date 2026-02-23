import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  __resetRateLimitProviderWarningForTests,
  createRateLimitProvider,
  getRateLimitProviderMode,
} from '../rate-limit-provider';

type MutableEnv = {
  JARVIS_RATE_LIMIT_PROVIDER?: string;
  JARVIS_STRICT_DISTRIBUTED_STATE?: string;
  REDIS_URL?: string;
  UPSTASH_REDIS_REST_URL?: string;
  UPSTASH_REDIS_REST_TOKEN?: string;
};

const originalEnv: MutableEnv = {
  JARVIS_RATE_LIMIT_PROVIDER: process.env.JARVIS_RATE_LIMIT_PROVIDER,
  JARVIS_STRICT_DISTRIBUTED_STATE: process.env.JARVIS_STRICT_DISTRIBUTED_STATE,
  REDIS_URL: process.env.REDIS_URL,
  UPSTASH_REDIS_REST_URL: process.env.UPSTASH_REDIS_REST_URL,
  UPSTASH_REDIS_REST_TOKEN: process.env.UPSTASH_REDIS_REST_TOKEN,
};

function resetProviderEnv(): void {
  delete process.env.JARVIS_RATE_LIMIT_PROVIDER;
  delete process.env.JARVIS_STRICT_DISTRIBUTED_STATE;
  delete process.env.REDIS_URL;
  delete process.env.UPSTASH_REDIS_REST_URL;
  delete process.env.UPSTASH_REDIS_REST_TOKEN;
}

function mockUpstashLimiterPipeline(): void {
  const buckets = new Map<string, number[]>();

  vi.stubGlobal('fetch', vi.fn(async (_url: string, init?: RequestInit) => {
    const rawBody = String(init?.body || '[]');
    const body = JSON.parse(rawBody) as string[][];
    const command = body?.[0] || [];
    const op = String(command[0] || '').toUpperCase();

    if (op !== 'EVAL') {
      return {
        ok: false,
        status: 400,
        text: async () => `unsupported op: ${op}`,
      } as unknown as Response;
    }

    const key = String(command[3] || '');
    const now = Number(command[5] || Date.now());
    const windowMs = Math.max(1, Number(command[6] || 60_000));
    const maxRequests = Math.max(1, Number(command[7] || 1));
    const windowStart = now - windowMs;

    const active = (buckets.get(key) || []).filter((t) => t > windowStart);
    if (active.length >= maxRequests) {
      const oldest = active[0];
      const retry = Math.max(1, oldest + windowMs - now);
      buckets.set(key, active);
      return {
        ok: true,
        json: async () => [{ result: [0, 0, retry] }],
      } as unknown as Response;
    }

    active.push(now);
    buckets.set(key, active);
    const remaining = Math.max(0, maxRequests - active.length);
    return {
      ok: true,
      json: async () => [{ result: [1, remaining, 0] }],
    } as unknown as Response;
  }));
}

describe('rate-limit-provider', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.unstubAllGlobals();
    resetProviderEnv();
    vi.restoreAllMocks();
    __resetRateLimitProviderWarningForTests();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    process.env.JARVIS_RATE_LIMIT_PROVIDER = originalEnv.JARVIS_RATE_LIMIT_PROVIDER;
    process.env.JARVIS_STRICT_DISTRIBUTED_STATE = originalEnv.JARVIS_STRICT_DISTRIBUTED_STATE;
    process.env.REDIS_URL = originalEnv.REDIS_URL;
    process.env.UPSTASH_REDIS_REST_URL = originalEnv.UPSTASH_REDIS_REST_URL;
    process.env.UPSTASH_REDIS_REST_TOKEN = originalEnv.UPSTASH_REDIS_REST_TOKEN;
    __resetRateLimitProviderWarningForTests();
  });

  it('defaults to memory mode when redis signals are absent', () => {
    const provider = createRateLimitProvider({ keyPrefix: 'test', maxRequests: 2, windowMs: 1_000 });

    expect(provider.mode).toBe('memory');
    expect(getRateLimitProviderMode()).toBe('memory');
  });

  it('falls back to memory mode and warns when redis is requested', () => {
    process.env.JARVIS_RATE_LIMIT_PROVIDER = 'redis';
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    const provider = createRateLimitProvider({ keyPrefix: 'test', maxRequests: 2, windowMs: 1_000 });

    expect(provider.mode).toBe('memory');
    expect(getRateLimitProviderMode()).toBe('memory');
    expect(warnSpy).toHaveBeenCalled();
  });

  it('reports memory mode when upstash url is present', () => {
    process.env.UPSTASH_REDIS_REST_URL = 'https://example.upstash.io';
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

    expect(getRateLimitProviderMode()).toBe('memory');
    expect(warnSpy).toHaveBeenCalled();
  });

  it('throws when strict distributed guard is enabled and redis is requested', () => {
    process.env.JARVIS_RATE_LIMIT_PROVIDER = 'redis';
    process.env.JARVIS_STRICT_DISTRIBUTED_STATE = 'true';

    expect(() => createRateLimitProvider({ keyPrefix: 'strict', maxRequests: 1, windowMs: 1_000 }))
      .toThrow(/redis mode requested for rate-limit-provider/i);
  });

  it('enforces sliding-window request limits and returns retryAfter', async () => {
    const provider = createRateLimitProvider({ keyPrefix: 'api', maxRequests: 2, windowMs: 1_000 });

    await expect(provider.check('1.1.1.1')).resolves.toMatchObject({ allowed: true, remaining: 1 });
    await expect(provider.check('1.1.1.1')).resolves.toMatchObject({ allowed: true, remaining: 0 });

    const blocked = await provider.check('1.1.1.1');
    expect(blocked.allowed).toBe(false);
    expect(blocked.remaining).toBe(0);
    expect(blocked.retryAfterMs).toBeGreaterThan(0);

    vi.advanceTimersByTime(1_001);
    await expect(provider.check('1.1.1.1')).resolves.toMatchObject({ allowed: true, remaining: 1 });
  });

  it('isolates limiter keys across prefixes', async () => {
    const first = createRateLimitProvider({ keyPrefix: 'first', maxRequests: 1, windowMs: 1_000 });
    const second = createRateLimitProvider({ keyPrefix: 'second', maxRequests: 1, windowMs: 1_000 });

    await expect(first.check('2.2.2.2')).resolves.toMatchObject({ allowed: true });
    await expect(first.check('2.2.2.2')).resolves.toMatchObject({ allowed: false });

    await expect(second.check('2.2.2.2')).resolves.toMatchObject({ allowed: true });
  });

  it('shares redis-backed limiter state across provider instances', async () => {
    process.env.JARVIS_RATE_LIMIT_PROVIDER = 'redis';
    process.env.UPSTASH_REDIS_REST_URL = 'https://example.upstash.io';
    process.env.UPSTASH_REDIS_REST_TOKEN = 'token';
    mockUpstashLimiterPipeline();

    const first = createRateLimitProvider({ keyPrefix: 'shared', maxRequests: 1, windowMs: 1_000 });
    const second = createRateLimitProvider({ keyPrefix: 'shared', maxRequests: 1, windowMs: 1_000 });

    expect(first.mode).toBe('redis');
    expect(second.mode).toBe('redis');

    await expect(first.check('9.9.9.9')).resolves.toMatchObject({ allowed: true, remaining: 0 });
    await expect(second.check('9.9.9.9')).resolves.toMatchObject({ allowed: false, remaining: 0 });
  });
});
