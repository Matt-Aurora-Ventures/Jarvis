import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { RateLimiter } from '../rate-limiter';

describe('RateLimiter', () => {
  let limiter: RateLimiter;

  beforeEach(() => {
    limiter = new RateLimiter({ maxRequests: 5, windowMs: 60_000 });
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('check', () => {
    it('allows requests under the limit', () => {
      const result = limiter.check('192.168.1.1');
      expect(result.allowed).toBe(true);
      expect(result.remaining).toBe(4);
    });

    it('tracks requests per IP independently', () => {
      // Use 3 from IP A
      limiter.check('10.0.0.1');
      limiter.check('10.0.0.1');
      limiter.check('10.0.0.1');

      // IP B should still have full quota
      const resultB = limiter.check('10.0.0.2');
      expect(resultB.allowed).toBe(true);
      expect(resultB.remaining).toBe(4);
    });

    it('blocks requests over the limit', () => {
      for (let i = 0; i < 5; i++) {
        limiter.check('192.168.1.1');
      }
      const result = limiter.check('192.168.1.1');
      expect(result.allowed).toBe(false);
      expect(result.remaining).toBe(0);
    });

    it('returns retryAfterMs when blocked', () => {
      for (let i = 0; i < 5; i++) {
        limiter.check('192.168.1.1');
      }
      const result = limiter.check('192.168.1.1');
      expect(result.allowed).toBe(false);
      expect(result.retryAfterMs).toBeGreaterThan(0);
      expect(result.retryAfterMs).toBeLessThanOrEqual(60_000);
    });

    it('resets after the time window elapses', () => {
      // Exhaust quota
      for (let i = 0; i < 5; i++) {
        limiter.check('192.168.1.1');
      }
      expect(limiter.check('192.168.1.1').allowed).toBe(false);

      // Advance past window
      vi.advanceTimersByTime(60_001);

      const result = limiter.check('192.168.1.1');
      expect(result.allowed).toBe(true);
      expect(result.remaining).toBe(4);
    });

    it('correctly counts remaining requests', () => {
      expect(limiter.check('ip').remaining).toBe(4); // 1st request, 4 left
      expect(limiter.check('ip').remaining).toBe(3); // 2nd request, 3 left
      expect(limiter.check('ip').remaining).toBe(2);
      expect(limiter.check('ip').remaining).toBe(1);
      expect(limiter.check('ip').remaining).toBe(0); // 5th request, 0 left
      expect(limiter.check('ip').remaining).toBe(0); // 6th request, blocked
    });
  });

  describe('default configuration', () => {
    it('defaults to 60 requests per minute', () => {
      const defaultLimiter = new RateLimiter();
      // Should allow 60 requests
      for (let i = 0; i < 60; i++) {
        expect(defaultLimiter.check('test-ip').allowed).toBe(true);
      }
      expect(defaultLimiter.check('test-ip').allowed).toBe(false);
    });
  });

  describe('cleanup', () => {
    it('cleans up stale entries over time', () => {
      // Create entries for 20 IPs
      for (let i = 0; i < 20; i++) {
        limiter.check(`ip-${i}`);
      }

      // Advance past window so all entries become stale
      vi.advanceTimersByTime(61_000);

      // A new request should work and trigger cleanup
      const result = limiter.check('fresh-ip');
      expect(result.allowed).toBe(true);
    });
  });

  describe('sliding window behavior', () => {
    it('uses a sliding window that considers request timestamps', () => {
      // Make 3 requests at time 0
      limiter.check('ip');
      limiter.check('ip');
      limiter.check('ip');

      // Advance 30 seconds
      vi.advanceTimersByTime(30_000);

      // Make 2 more requests (should be at limit now)
      limiter.check('ip');
      limiter.check('ip');

      // 6th request should be blocked (5 requests in last 60s)
      expect(limiter.check('ip').allowed).toBe(false);

      // Advance 31 more seconds (first 3 requests now outside window)
      vi.advanceTimersByTime(31_000);

      // Should be allowed again (only 2 requests in last 60s window)
      const result = limiter.check('ip');
      expect(result.allowed).toBe(true);
    });
  });
});
