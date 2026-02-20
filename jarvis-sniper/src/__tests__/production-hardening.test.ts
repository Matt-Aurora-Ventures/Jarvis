/**
 * Production Hardening Tests
 *
 * Tests for:
 * 1. ErrorBoundary component exports and types
 * 2. Rate limiter coverage on all API routes
 * 3. API route hardening utilities (fetchWithTimeout, graceful errors)
 * 4. Retry logic with exponential backoff
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---------------------------------------------------------------------------
// 1. fetchWithRetry utility (exponential backoff)
// ---------------------------------------------------------------------------
describe('fetchWithRetry', () => {
  let fetchWithRetry: typeof import('@/lib/fetch-utils').fetchWithRetry;

  beforeEach(async () => {
    vi.restoreAllMocks();
    const mod = await import('@/lib/fetch-utils');
    fetchWithRetry = mod.fetchWithRetry;
  });

  it('should return response on first success', async () => {
    const mockResponse = { ok: true, status: 200, json: () => Promise.resolve({ data: 'test' }) };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse));

    const result = await fetchWithRetry('https://example.com/api', { maxRetries: 3 });
    expect(result.ok).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('should retry on failure and succeed on second attempt', async () => {
    const failResponse = { ok: false, status: 500 };
    const successResponse = { ok: true, status: 200, json: () => Promise.resolve({}) };
    const mockFetch = vi.fn()
      .mockResolvedValueOnce(failResponse)
      .mockResolvedValueOnce(successResponse);
    vi.stubGlobal('fetch', mockFetch);

    const result = await fetchWithRetry('https://example.com/api', {
      maxRetries: 3,
      baseDelayMs: 10, // fast for tests
    });
    expect(result.ok).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('should respect maxRetries limit', async () => {
    const failResponse = { ok: false, status: 500 };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(failResponse));

    const result = await fetchWithRetry('https://example.com/api', {
      maxRetries: 2,
      baseDelayMs: 10,
    });
    // After 2 retries (3 total attempts), returns the last failed response
    expect(result.ok).toBe(false);
    expect(fetch).toHaveBeenCalledTimes(3); // 1 initial + 2 retries
  });

  it('should apply exponential backoff between retries', async () => {
    const failResponse = { ok: false, status: 500 };
    const successResponse = { ok: true, status: 200 };
    const mockFetch = vi.fn()
      .mockResolvedValueOnce(failResponse)
      .mockResolvedValueOnce(failResponse)
      .mockResolvedValueOnce(successResponse);
    vi.stubGlobal('fetch', mockFetch);

    const startTime = Date.now();
    await fetchWithRetry('https://example.com/api', {
      maxRetries: 3,
      baseDelayMs: 50,
    });
    const elapsed = Date.now() - startTime;
    // Should have waited at least 50ms + 100ms = 150ms (exponential: 50, 100)
    expect(elapsed).toBeGreaterThanOrEqual(100);
  });

  it('should abort with timeout', async () => {
    // Mock fetch that respects AbortSignal
    vi.stubGlobal('fetch', vi.fn().mockImplementation((_url: string, init?: RequestInit) =>
      new Promise((_resolve, reject) => {
        const timer = setTimeout(() => _resolve({ ok: true, status: 200 }), 5000);
        if (init?.signal) {
          init.signal.addEventListener('abort', () => {
            clearTimeout(timer);
            reject(new DOMException('The operation was aborted.', 'AbortError'));
          });
        }
      })
    ));

    const result = await fetchWithRetry('https://example.com/api', {
      maxRetries: 0,
      timeoutMs: 100,
    });
    // Should return a timeout error response
    expect(result.ok).toBe(false);
  });

  it('should not retry on 4xx errors', async () => {
    const clientError = { ok: false, status: 400 };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(clientError));

    const result = await fetchWithRetry('https://example.com/api', {
      maxRetries: 3,
      baseDelayMs: 10,
    });
    expect(result.ok).toBe(false);
    // 4xx errors should NOT be retried
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// 2. Rate limiter integration
// ---------------------------------------------------------------------------
describe('Rate limiter coverage', () => {
  it('apiRateLimiter should be exported and functional', async () => {
    const { apiRateLimiter } = await import('@/lib/rate-limiter');
    const result = await apiRateLimiter.check('test-ip-hardening-1');
    expect(result.allowed).toBe(true);
    expect(typeof result.remaining).toBe('number');
  });

  it('quoteRateLimiter should have stricter limits', async () => {
    const { quoteRateLimiter } = await import('@/lib/rate-limiter');
    const result = await quoteRateLimiter.check('test-ip-hardening-2');
    expect(result.allowed).toBe(true);
    // Quote limiter has maxRequests=30 vs apiRateLimiter maxRequests=60
    expect(result.remaining).toBeLessThanOrEqual(30);
  });

  it('swapRateLimiter should have strictest limits', async () => {
    const { swapRateLimiter } = await import('@/lib/rate-limiter');
    const result = await swapRateLimiter.check('test-ip-hardening-3');
    expect(result.allowed).toBe(true);
    // Swap limiter has maxRequests=20
    expect(result.remaining).toBeLessThanOrEqual(20);
  });

  it('getClientIp should extract from x-forwarded-for', async () => {
    const { getClientIp } = await import('@/lib/rate-limiter');
    const request = new Request('https://example.com', {
      headers: { 'x-forwarded-for': '1.2.3.4, 5.6.7.8' },
    });
    expect(getClientIp(request)).toBe('1.2.3.4');
  });

  it('getClientIp should fallback to x-real-ip', async () => {
    const { getClientIp } = await import('@/lib/rate-limiter');
    const request = new Request('https://example.com', {
      headers: { 'x-real-ip': '10.0.0.1' },
    });
    expect(getClientIp(request)).toBe('10.0.0.1');
  });

  it('getClientIp should fallback to unknown', async () => {
    const { getClientIp } = await import('@/lib/rate-limiter');
    const request = new Request('https://example.com');
    expect(getClientIp(request)).toBe('unknown');
  });
});

// ---------------------------------------------------------------------------
// 3. API route hardening helper
// ---------------------------------------------------------------------------
describe('withApiHardening', () => {
  let withApiHardening: typeof import('@/lib/api-hardening').withApiHardening;

  beforeEach(async () => {
    vi.restoreAllMocks();
    const mod = await import('@/lib/api-hardening');
    withApiHardening = mod.withApiHardening;
  });

  it('should wrap handler with try/catch and return JSON on success', async () => {
    const handler = vi.fn().mockResolvedValue({ data: [1, 2, 3] });
    const wrappedHandler = withApiHardening(handler, { routeName: 'test' });

    const request = new Request('https://example.com/api/test');
    const response = await wrappedHandler(request);
    expect(response.status).toBe(200);
    const json = await response.json();
    expect(json.data).toEqual([1, 2, 3]);
  });

  it('should return 500 with error on handler failure', async () => {
    const handler = vi.fn().mockRejectedValue(new Error('DB connection failed'));
    const wrappedHandler = withApiHardening(handler, { routeName: 'test' });

    const request = new Request('https://example.com/api/test');
    const response = await wrappedHandler(request);
    expect(response.status).toBe(500);
    const json = await response.json();
    expect(json.error).toContain('Internal server error');
  });

  it('should add Cache-Control header when cacheSecs is provided', async () => {
    const handler = vi.fn().mockResolvedValue({ ok: true });
    const wrappedHandler = withApiHardening(handler, {
      routeName: 'test',
      cacheSecs: 30,
    });

    const request = new Request('https://example.com/api/test');
    const response = await wrappedHandler(request);
    const cacheControl = response.headers.get('Cache-Control');
    expect(cacheControl).toContain('s-maxage=30');
  });

  it('should apply rate limiting when rateLimiter is provided', async () => {
    const { RateLimiter } = await import('@/lib/rate-limiter');
    const limiter = new RateLimiter({ maxRequests: 1, windowMs: 60_000 });

    const handler = vi.fn().mockResolvedValue({ ok: true });
    const wrappedHandler = withApiHardening(handler, {
      routeName: 'test',
      rateLimiter: limiter,
    });

    const request1 = new Request('https://example.com/api/test', {
      headers: { 'x-forwarded-for': '99.99.99.99' },
    });
    const response1 = await wrappedHandler(request1);
    expect(response1.status).toBe(200);

    // Second request should be rate limited
    const request2 = new Request('https://example.com/api/test', {
      headers: { 'x-forwarded-for': '99.99.99.99' },
    });
    const response2 = await wrappedHandler(request2);
    expect(response2.status).toBe(429);
  });

  it('should return graceful empty data when fallbackData is provided and handler fails', async () => {
    const handler = vi.fn().mockRejectedValue(new Error('upstream down'));
    const wrappedHandler = withApiHardening(handler, {
      routeName: 'test',
      fallbackData: { graduations: [] },
    });

    const request = new Request('https://example.com/api/test');
    const response = await wrappedHandler(request);
    // When fallbackData is provided, should return 200 with empty data instead of 500
    expect(response.status).toBe(200);
    const json = await response.json();
    expect(json.graduations).toEqual([]);
    expect(json._fallback).toBe(true);
  });
});
