import { NextResponse } from 'next/server';
import { runBagsBacktest, backtestCache, type BagsBacktestResult } from '@/lib/bags-backtest';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';

/**
 * Bags.fm Backtest API
 *
 * GET  — Returns cached backtest results (runs fresh if cache empty, 1h TTL)
 * POST — Triggers fresh backtest with optional custom parameters
 *
 * Response shape:
 * {
 *   totalTokens, tokensWithData, graduationStats,
 *   topStrategies: top 10 by Sharpe ratio,
 *   bestStrategy, cached: boolean
 * }
 */

function formatResponse(result: BagsBacktestResult, cached: boolean) {
  const sorted = [...result.strategyResults].sort(
    (a, b) => b.sharpeRatio - a.sharpeRatio,
  );

  return {
    totalTokens: result.totalTokens,
    tokensWithData: result.tokensWithData,
    topStrategies: sorted.slice(0, 10),
    bestStrategy: result.bestStrategy,
    graduationStats: result.graduationStats,
    cached,
  };
}

export async function GET(request: Request): Promise<NextResponse> {
  try {
    // Rate limit check
    const ip = getClientIp(request);
    const limit = await apiRateLimiter.check(ip);
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

    // Check cache first
    const cached = backtestCache.get('bags-backtest');
    if (cached) {
      return NextResponse.json(formatResponse(cached, true));
    }

    // Run fresh backtest
    const result = await runBagsBacktest();
    backtestCache.set('bags-backtest', result, 3600_000); // 1h TTL

    return NextResponse.json(formatResponse(result, false));
  } catch (err) {
    console.error('[bags-backtest] GET error:', err);
    return NextResponse.json(
      { error: 'Backtest failed', details: err instanceof Error ? err.message : 'Unknown' },
      { status: 500 },
    );
  }
}

export async function POST(request: Request): Promise<NextResponse> {
  try {
    // Rate limit check
    const ip = getClientIp(request);
    const limit = await apiRateLimiter.check(ip);
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

    // Invalidate cache
    backtestCache.invalidate('bags-backtest');

    // Parse optional custom params
    let customParams: Record<string, unknown> = {};
    try {
      customParams = await request.json();
    } catch {
      // Empty body is fine
    }

    // Run fresh backtest with optional params
    const result = await runBagsBacktest(customParams as any);
    backtestCache.set('bags-backtest', result, 3600_000); // 1h TTL

    return NextResponse.json(formatResponse(result, false));
  } catch (err) {
    console.error('[bags-backtest] POST error:', err);
    return NextResponse.json(
      { error: 'Backtest failed', details: err instanceof Error ? err.message : 'Unknown' },
      { status: 500 },
    );
  }
}
