/**
 * Simple in-memory IP-based rate limiter using a sliding window algorithm.
 *
 * Tracks individual request timestamps per IP, so the window slides naturally.
 * Designed for single-process Next.js with 50-100 concurrent users.
 *
 * No Redis dependency — in-memory Map is sufficient for this scale.
 */

interface RateLimiterConfig {
  /** Maximum requests allowed per window. Default: 60 */
  maxRequests?: number;
  /** Window duration in milliseconds. Default: 60_000 (1 minute) */
  windowMs?: number;
}

interface RateLimitResult {
  /** Whether the request is allowed */
  allowed: boolean;
  /** Remaining requests in the current window */
  remaining: number;
  /** Milliseconds until the client can retry (only set when blocked) */
  retryAfterMs?: number;
}

export class RateLimiter {
  private readonly maxRequests: number;
  private readonly windowMs: number;
  /** Map from IP to sorted array of request timestamps */
  private requests = new Map<string, number[]>();
  private lastCleanup = Date.now();
  private readonly cleanupIntervalMs = 120_000; // Cleanup stale IPs every 2 min

  constructor(config: RateLimiterConfig = {}) {
    this.maxRequests = config.maxRequests ?? 60;
    this.windowMs = config.windowMs ?? 60_000;
  }

  /**
   * Check whether a request from the given IP is allowed.
   * If allowed, the request is counted. If blocked, retryAfterMs is provided.
   */
  check(ip: string): RateLimitResult {
    this.maybeCleanup();

    const now = Date.now();
    const windowStart = now - this.windowMs;

    // Get existing timestamps, filter out expired ones
    let timestamps = this.requests.get(ip) || [];
    timestamps = timestamps.filter((t) => t > windowStart);

    if (timestamps.length >= this.maxRequests) {
      // Blocked — calculate when the oldest request in window expires
      const oldestInWindow = timestamps[0];
      const retryAfterMs = oldestInWindow + this.windowMs - now;

      // Still update the filtered list (remove stale entries)
      this.requests.set(ip, timestamps);

      return {
        allowed: false,
        remaining: 0,
        retryAfterMs: Math.max(1, retryAfterMs),
      };
    }

    // Allowed — record this request
    timestamps.push(now);
    this.requests.set(ip, timestamps);

    return {
      allowed: true,
      remaining: this.maxRequests - timestamps.length,
    };
  }

  /**
   * Periodic cleanup of IPs with no recent activity.
   */
  private maybeCleanup(): void {
    const now = Date.now();
    if (now - this.lastCleanup < this.cleanupIntervalMs) return;
    this.lastCleanup = now;

    const windowStart = now - this.windowMs;
    for (const [ip, timestamps] of this.requests) {
      const active = timestamps.filter((t) => t > windowStart);
      if (active.length === 0) {
        this.requests.delete(ip);
      } else {
        this.requests.set(ip, active);
      }
    }
  }
}

/**
 * Shared rate limiter instances for API routes.
 * Different routes can have different limits.
 */

/** General API rate limiter: 60 req/min per IP */
export const apiRateLimiter = new RateLimiter({ maxRequests: 60, windowMs: 60_000 });

/** Bags quote endpoint: stricter limit (30 req/min) — most expensive upstream call */
export const quoteRateLimiter = new RateLimiter({ maxRequests: 30, windowMs: 60_000 });

/** Bags swap endpoint: strict limit (20 req/min) — involves transaction building */
export const swapRateLimiter = new RateLimiter({ maxRequests: 20, windowMs: 60_000 });

/**
 * Helper to extract client IP from a Next.js request.
 * Checks common headers for reverse proxy setups, falls back to 'unknown'.
 */
export function getClientIp(request: Request): string {
  // Next.js doesn't expose IP directly on Request, check headers
  const forwarded = request.headers.get('x-forwarded-for');
  if (forwarded) {
    // x-forwarded-for can contain multiple IPs, take the first (client)
    return forwarded.split(',')[0].trim();
  }
  const realIp = request.headers.get('x-real-ip');
  if (realIp) return realIp.trim();

  return 'unknown';
}
