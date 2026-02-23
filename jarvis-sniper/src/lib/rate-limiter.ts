import { createRateLimitProvider, type RateLimitProvider } from './rate-limit-provider';

/**
 * Simple in-memory IP-based rate limiter using a sliding window algorithm.
 *
 * Tracks individual request timestamps per IP, so the window slides naturally.
 */

export interface RateLimiterConfig {
  /** Maximum requests allowed per window. Default: 60 */
  maxRequests?: number;
  /** Window duration in milliseconds. Default: 60_000 (1 minute) */
  windowMs?: number;
}

export interface RateLimitResult {
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
      // Blocked - calculate when the oldest request in window expires
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

    // Allowed - record this request
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

export interface SharedRateLimiter {
  mode: 'memory' | 'redis';
  check(ip: string): Promise<RateLimitResult>;
}

function createSharedRateLimiter(
  keyPrefix: string,
  config: Required<RateLimiterConfig>,
): SharedRateLimiter {
  const provider: RateLimitProvider = createRateLimitProvider({
    keyPrefix,
    maxRequests: config.maxRequests,
    windowMs: config.windowMs,
  });

  return {
    mode: provider.mode,
    check: async (ip: string) => provider.check(ip),
  };
}

/**
 * Shared rate limiter instances for API routes.
 * Different routes can have different limits.
 */

/** General API rate limiter: 60 req/min per IP */
export const apiRateLimiter = createSharedRateLimiter('api', { maxRequests: 60, windowMs: 60_000 });

/** RPC proxy limiter: higher cap because web3 polling/subscriptions are chatty */
export const rpcRateLimiter = createSharedRateLimiter('rpc', { maxRequests: 300, windowMs: 60_000 });

/** Bags quote endpoint: stricter limit (30 req/min) - most expensive upstream call */
export const quoteRateLimiter = createSharedRateLimiter('quote', { maxRequests: 30, windowMs: 60_000 });

/** Bags swap endpoint: strict limit (20 req/min) - involves transaction building */
export const swapRateLimiter = createSharedRateLimiter('swap', { maxRequests: 20, windowMs: 60_000 });

/** Autonomy control routes: very low throughput by design (scheduler + manual checks). */
export const autonomyRateLimiter = createSharedRateLimiter('autonomy', { maxRequests: 6, windowMs: 60_000 });

/** Trade telemetry: low-volume, but must tolerate bursts (position closes + retries). */
export const telemetryRateLimiter = new RateLimiter({ maxRequests: 120, windowMs: 60_000 });

/**
 * Helper to extract client IP from a Next.js request.
 *
 * On managed platforms (Firebase/Vercel/GCP), x-forwarded-for is normalized
 * by trusted ingress and the first hop is the original client address.
 * We use the first non-empty entry for stable, expected per-user limiting.
 */
export function getClientIp(request: Request): string {
  const forwarded = request.headers.get('x-forwarded-for');
  if (forwarded) {
    const ips = forwarded.split(',').map((ip) => ip.trim()).filter(Boolean);
    if (ips.length > 0) return ips[0];
  }
  const realIp = request.headers.get('x-real-ip');
  if (realIp) return realIp.trim();

  return 'unknown';
}
