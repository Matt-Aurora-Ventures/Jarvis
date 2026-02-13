import { NextResponse } from 'next/server';
import {
  getCachedTVData,
  XSTOCKS_TO_TV_SYMBOL,
  getMarketPhase,
} from '@/lib/tv-screener';
import type { TVStockData } from '@/lib/tv-screener';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';

/**
 * GET /api/tv-screener
 *
 * Returns TradingView stock data for all mapped xStocks/Index/Commodity tickers.
 *
 * Response shape:
 * {
 *   success: boolean,
 *   marketPhase: MarketPhase,
 *   count: number,
 *   timestamp: string,
 *   data: Record<string, TVStockData>,   // keyed by real ticker (AAPL, MSFT, ...)
 *   xstocksMap: Record<string, string>,  // xStocks ticker -> real ticker
 * }
 *
 * On error, returns { success: false, error, data: {}, xstocksMap: {} } with
 * status 200 so callers can gracefully degrade instead of failing on HTTP errors.
 *
 * Cache-Control: 30s server cache with 60s stale-while-revalidate.
 */
export async function GET(request: Request): Promise<NextResponse> {
  try {
    // Rate limit check
    const ip = getClientIp(request);
    const limit = apiRateLimiter.check(ip);
    if (!limit.allowed) {
      return NextResponse.json(
        {
          success: false,
          error: 'Rate limit exceeded',
          marketPhase: getMarketPhase(),
          count: 0,
          timestamp: new Date().toISOString(),
          data: {},
          xstocksMap: {},
        },
        {
          status: 429,
          headers: {
            'Retry-After': String(Math.ceil((limit.retryAfterMs || 60_000) / 1000)),
            'X-RateLimit-Remaining': '0',
          },
        },
      );
    }

    // Fetch all TV stock data (cache-aware, 60s TTL)
    const allTVData = await getCachedTVData();

    // Build the response data: only include tickers that exist in our mapping
    // AND were successfully fetched from TradingView
    const data: Record<string, TVStockData> = {};
    const xstocksMap: Record<string, string> = {};

    for (const [xTicker, realTicker] of Object.entries(XSTOCKS_TO_TV_SYMBOL)) {
      xstocksMap[xTicker] = realTicker;

      const tvData = allTVData[realTicker];
      if (tvData) {
        data[realTicker] = tvData;
      }
    }

    const marketPhase = getMarketPhase();

    const response = NextResponse.json({
      success: true,
      marketPhase,
      count: Object.keys(data).length,
      timestamp: new Date().toISOString(),
      data,
      xstocksMap,
    });

    response.headers.set(
      'Cache-Control',
      'public, s-maxage=30, stale-while-revalidate=60',
    );

    return response;
  } catch (err) {
    console.error('[api/tv-screener] Error:', err);

    return NextResponse.json({
      success: false,
      error: err instanceof Error ? err.message : String(err),
      marketPhase: getMarketPhase(),
      count: 0,
      timestamp: new Date().toISOString(),
      data: {},
      xstocksMap: {},
    });
  }
}
