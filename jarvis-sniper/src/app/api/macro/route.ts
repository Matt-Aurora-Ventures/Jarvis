import { NextResponse } from 'next/server';
import { graduationCache } from '@/lib/server-cache';
import { apiRateLimiter, getClientIp } from '@/lib/rate-limiter';
import { determineRegime, determineBtcTrend } from '@/hooks/useMacroData';

/**
 * Server-side macro market data endpoint.
 *
 * Fetches BTC and SOL prices + 24h change from CoinGecko free API,
 * computes market regime and BTC trend, and caches for 60 seconds.
 *
 * Rate limiting: shares the general API rate limiter (60 req/min per IP).
 */

const COINGECKO_URL =
  'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,solana&vs_currencies=usd&include_24hr_change=true';

const MACRO_CACHE_KEY = 'macro:latest';
const MACRO_TTL_MS = 60_000; // 60 seconds

/** Fetch with a timeout to prevent hanging when CoinGecko is slow/unreachable */
async function fetchWithTimeout(url: string, timeoutMs = 8000): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      headers: { Accept: 'application/json' },
      signal: controller.signal,
    });
    return res;
  } finally {
    clearTimeout(timer);
  }
}

export async function GET(request: Request) {
  try {
    // Rate limit check
    const ip = getClientIp(request);
    const limit = apiRateLimiter.check(ip);
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
    const cached = graduationCache.get(MACRO_CACHE_KEY);
    if (cached) {
      return NextResponse.json(cached, {
        headers: {
          'X-Cache': 'HIT',
          'X-RateLimit-Remaining': String(limit.remaining),
        },
      });
    }

    // Fetch from CoinGecko
    const res = await fetchWithTimeout(COINGECKO_URL);
    if (!res.ok) {
      console.warn(`[Macro] CoinGecko returned ${res.status}`);
      return NextResponse.json(
        { error: 'Upstream API error', btcPrice: null, solPrice: null, regime: null, btcTrend: null },
        { status: 502 },
      );
    }

    const json = await res.json();

    const btcPrice: number = json.bitcoin?.usd ?? 0;
    const btcChange24h: number = json.bitcoin?.usd_24h_change ?? 0;
    const solPrice: number = json.solana?.usd ?? 0;
    const solChange24h: number = json.solana?.usd_24h_change ?? 0;

    const payload = {
      btcPrice,
      btcChange24h,
      solPrice,
      solChange24h,
      regime: determineRegime(btcChange24h),
      btcTrend: determineBtcTrend(btcChange24h),
      timestamp: Date.now(),
    };

    // Cache the response
    graduationCache.set(MACRO_CACHE_KEY, payload, MACRO_TTL_MS);

    return NextResponse.json(payload, {
      headers: {
        'X-Cache': 'MISS',
        'X-RateLimit-Remaining': String(limit.remaining),
      },
    });
  } catch (err) {
    console.error('[Macro] Unexpected error:', err);
    return NextResponse.json(
      { error: 'Internal server error', btcPrice: null, solPrice: null, regime: null, btcTrend: null },
      { status: 500 },
    );
  }
}
