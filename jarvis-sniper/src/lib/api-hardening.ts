/**
 * API Route Hardening Utilities
 *
 * Provides a `withApiHardening` wrapper that adds:
 * - try/catch with structured error responses
 * - Optional rate limiting per route
 * - Optional Cache-Control headers
 * - Optional fallback data on failure (graceful degradation)
 *
 * Designed for Next.js App Router API routes.
 */

import { NextResponse } from 'next/server';
import { type RateLimiter, getClientIp } from '@/lib/rate-limiter';

export interface ApiHardeningOptions {
  /** Route name for logging (e.g., 'graduations', 'macro') */
  routeName: string;

  /** Optional rate limiter instance to apply */
  rateLimiter?: RateLimiter;

  /** Optional Cache-Control s-maxage in seconds */
  cacheSecs?: number;

  /** Optional stale-while-revalidate in seconds (used with cacheSecs) */
  staleSecs?: number;

  /**
   * Optional fallback data returned as 200 instead of 500 on failure.
   * Enables graceful degradation for non-critical endpoints.
   */
  fallbackData?: Record<string, unknown>;
}

type HandlerFn = (request: Request) => Promise<Record<string, unknown>>;

/**
 * Wraps an API route handler with production-hardening features.
 *
 * Usage:
 * ```ts
 * export const GET = withApiHardening(
 *   async (request) => {
 *     const data = await fetchData();
 *     return { items: data };
 *   },
 *   { routeName: 'my-route', cacheSecs: 30 }
 * );
 * ```
 */
export function withApiHardening(
  handler: HandlerFn,
  options: ApiHardeningOptions,
): (request: Request) => Promise<NextResponse> {
  const {
    routeName,
    rateLimiter,
    cacheSecs,
    staleSecs,
    fallbackData,
  } = options;

  return async (request: Request): Promise<NextResponse> => {
    try {
      // Rate limiting
      if (rateLimiter) {
        const ip = getClientIp(request);
        const limit = await rateLimiter.check(ip);
        if (!limit.allowed) {
          return NextResponse.json(
            { error: 'Rate limit exceeded' },
            {
              status: 429,
              headers: {
                'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
                'X-RateLimit-Remaining': '0',
              },
            },
          );
        }
      }

      // Execute handler
      const data = await handler(request);

      // Build response with optional caching
      const headers: Record<string, string> = {};
      if (cacheSecs) {
        const stale = staleSecs ?? cacheSecs * 2;
        headers['Cache-Control'] = `public, s-maxage=${cacheSecs}, stale-while-revalidate=${stale}`;
      }

      return NextResponse.json(data, { headers });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.error(`[api/${routeName}] Error:`, message);

      // Graceful degradation: return fallback data as 200 instead of 500
      if (fallbackData) {
        return NextResponse.json(
          { ...fallbackData, _fallback: true, _error: message },
          { status: 200 },
        );
      }

      return NextResponse.json(
        {
          error: 'Internal server error',
          // Only expose error details in development — never leak internals in production
          ...(process.env.NODE_ENV !== 'production' ? { details: message } : {}),
        },
        { status: 500 },
      );
    }
  };
}
